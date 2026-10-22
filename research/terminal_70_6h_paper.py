#!/usr/bin/env python3
"""Read-only Polymarket BTC 15m maker-pair paper observer. Never signs or submits orders.
Conservative proxy fills from future best-ask crossings; not actual queue/venue fills.
"""
import argparse
import datetime as dt
import json
import os
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request

GAMMA = "https://gamma-api.polymarket.com/markets/slug/"
CLOB = "https://clob.polymarket.com/book?token_id="
SHARES = 5.0
CAP = 0.98
START_USDC = 70.0
MERGE_COST = 0.02
EXIT_HAIRCUT = 0.02
POLL_SECONDS = 10

def stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def get_json(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": "khaledpoly-readonly-paper-research/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)

def market_for_slot(slot):
    slug = "btc-updown-15m-" + str(slot)
    data = get_json(GAMMA + slug)
    tokens = data.get("clobTokenIds") or data.get("clob_token_ids")
    if isinstance(tokens, str):
        tokens = json.loads(tokens)
    if not isinstance(tokens, list) or len(tokens) < 2:
        raise ValueError("Missing two CLOB token IDs")
    return {"slug":slug, "yes":str(tokens[0]), "no":str(tokens[1])}

def level(book, side):
    levels = book.get(side, [])
    rows = []
    for r in levels:
        try:
            p, size = float(r["price"]), float(r["size"])
            if 0 < p < 1 and size >= SHARES:
                rows.append((p, size))
        except (TypeError, ValueError, KeyError):
            pass
    if not rows:
        return None
    return (max if side == "bids" else min)(rows, key=lambda x:x[0])[0]

def quote(m):
    y, n = get_json(CLOB + urllib.parse.quote(m["yes"])), get_json(CLOB + urllib.parse.quote(m["no"]))
    return {"yes":{"bid":level(y,"bids"),"ask":level(y,"asks")},
            "no":{"bid":level(n,"bids"),"ask":level(n,"asks")}}

def emit(path, kind, **values):
    with path.open("a", encoding="utf8") as f:
        f.write(json.dumps({"ts":stamp(),"event":kind,**values},sort_keys=True)+"\n")

def counters():
    return {"markets_seen":0,"paired_placed":0,"yes_fills":0,"no_fills":0,
            "merged":0,"one_sided":0,"zero_fills":0,"api_errors":0,
            "gross_wins":0.0,"realized_losses":0.0,"gas_estimate":0.0}

def load(path):
    if path.exists():
        s=json.loads(path.read_text())
        if float(s["initial_usdc"]) != START_USDC:
            raise ValueError("Starting cash does not match 70 USDC")
        return s
    return {"initial_usdc":START_USDC,"cash":START_USDC,"realized_pnl":0.0,
            "counters":counters(),"history":[],"stages_done":0}

def save(path, state):
    tmp=path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state,indent=2,sort_keys=True))
    os.replace(tmp,path)

def close_position(s, p, q, events, reason):
    filled=[leg for leg in ("yes","no") if p["filled"][leg]]
    if len(filled)==2:
        cost=SHARES*(p["prices"]["yes"]+p["prices"]["no"])
        pnl=SHARES-cost-MERGE_COST
        s["cash"]+=SHARES-MERGE_COST
        s["counters"]["merged"]+=1
        s["counters"]["gross_wins"]+=SHARES-cost
        s["counters"]["gas_estimate"]+=MERGE_COST
        event="paired_merge"
    elif len(filled)==1:
        leg=filled[0]
        liquidation_bid=q.get(leg,{}).get("bid")
        # If quote disappeared, value inventory conservatively at zero.
        liquidation_bid=liquidation_bid if liquidation_bid is not None else 0.0
        proceeds=SHARES*liquidation_bid*(1.0-EXIT_HAIRCUT)
        pnl=proceeds-SHARES*p["prices"][leg]
        s["cash"]+=proceeds
        s["counters"]["one_sided"]+=1
        s["counters"]["realized_losses"]+=min(0.0,pnl)
        event="one_sided_liquidation"
    else:
        pnl=0.0
        s["counters"]["zero_fills"]+=1
        event="cancel_unfilled"
    s["realized_pnl"]+=pnl
    entry={"ts":stamp(),"market":p["slug"],"reason":reason,"result":event,
           "legs":filled,"pnl_usdc":round(pnl,6),"cash_usdc":round(s["cash"],6)}
    s["history"].append(entry)
    emit(events,event,**entry)
    return None

def run(s, stage_seconds, events, state_path, heartbeat_seconds):
    start=time.monotonic()
    until=start+stage_seconds
    active=None
    last_slot=None
    last_q={}
    last_heartbeat=0
    consecutive_failures=0
    while time.monotonic() < until:
        now=int(time.time())
        slot=(now//900)*900
        left=slot+900-now
        try:
            if slot != last_slot:
                if active:
                    active=close_position(s,active,last_q,events,"new_slot")
                last_slot=slot
                m=market_for_slot(slot)
                s["counters"]["markets_seen"]+=1
                emit(events,"market_discovered",slug=m["slug"])
            else:
                m=market_for_slot(slot) if active is None else None
            # For nonactive cycles, rediscover token IDs; skip if market unavailable.
            if active:
                m={"slug":active["slug"],"yes":active["tokens"]["yes"],"no":active["tokens"]["no"]}
            if m is None:
                raise ValueError("No market metadata")
            q=quote(m)
            last_q=q
            consecutive_failures=0
            if active:
                # Only future order book samples can fill a previously posted order.
                if now>active["created_at"]:
                    for side in ("yes","no"):
                        ask=q[side]["ask"]
                        if not active["filled"][side] and ask is not None and ask <= active["prices"][side]+1e-9:
                            cost=SHARES*active["prices"][side]
                            if s["cash"]>=cost:
                                active["filled"][side]=True
                                s["cash"]-=cost
                                s["counters"][side+"_fills"]+=1
                                emit(events,"proxy_fill",slug=active["slug"],side=side,price=active["prices"][side],cost=cost)
                if all(active["filled"].values()):
                    active=close_position(s,active,q,events,"both_proxy_filled")
                elif left<=60:
                    active=close_position(s,active,q,events,"cut_loss_60s")
            elif left>240 and 5<=now-slot<=120:
                yp=q["yes"]["bid"]; np=q["no"]["bid"]
                ya=q["yes"]["ask"]; na=q["no"]["ask"]
                # Rest at existing bids: no aggressive taking, combined price cap.
                if all(v is not None for v in (yp,np,ya,na)) and yp<ya and np<na and yp+np<=CAP and s["cash"]>=SHARES*(yp+np):
                    active={"slug":m["slug"],"tokens":{"yes":m["yes"],"no":m["no"]},
                            "prices":{"yes":yp,"no":np},"created_at":now,
                            "filled":{"yes":False,"no":False}}
                    s["counters"]["paired_placed"]+=1
                    emit(events,"paper_pair_placed",slug=m["slug"],yes_bid=yp,no_bid=np,
                         total_reserved=SHARES*(yp+np))
            if time.monotonic()-last_heartbeat>=heartbeat_seconds:
                last_heartbeat=time.monotonic()
                save(state_path,s)
                print(json.dumps({"stage_elapsed_seconds":int(last_heartbeat-start),
                      "cash":round(s["cash"],4),"pnl":round(s["realized_pnl"],4),
                      "paired_placed":s["counters"]["paired_placed"],
                      "merged":s["counters"]["merged"],
                      "api_errors":s["counters"]["api_errors"]}),flush=True)
        except Exception as exc:
            s["counters"]["api_errors"]+=1
            consecutive_failures+=1
            if consecutive_failures<=5 or consecutive_failures%30==0:
                emit(events,"data_error",error=str(exc)[:180])
        time.sleep(min(POLL_SECONDS,max(0,until-time.monotonic())))
    if active:
        close_position(s,active,last_q,events,"stage_boundary_mark_to_bid")
    s["stages_done"]+=1
    save(state_path,s)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--duration-seconds",type=int,default=10800)
    p.add_argument("--output-dir",default="paper_runs/terminal_70_6h")
    p.add_argument("--heartbeat-seconds",type=int,default=60)
    p.add_argument("--self-test",action="store_true")
    a=p.parse_args()
    if a.self_test:
        assert level({"bids":[{"price":"0.48","size":"5"},{"price":"0.49","size":"8"}]},"bids")==0.49
        assert level({"asks":[{"price":"0.52","size":"6"},{"price":"0.51","size":"5"}]},"asks")==0.51
        assert level({"asks":[{"price":"0.52","size":"4"}]},"asks") is None
        test={"initial_usdc":START_USDC,"cash":START_USDC-4.9,"realized_pnl":0,"counters":counters(),"history":[]}
        testp={"slug":"test","filled":{"yes":True,"no":True},"prices":{"yes":0.49,"no":0.49}}
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            close_position(test,testp,{},pathlib.Path(td)/"events.jsonl","unit_test")
        assert abs(test["cash"]-(START_USDC+0.08))<1e-9
        print("SELF_TEST_PASS")
        return
    if a.duration_seconds<1 or a.duration_seconds>12000:
        raise SystemExit("duration must be 1..12000 seconds")
    output=pathlib.Path(a.output_dir)
    output.mkdir(parents=True,exist_ok=True)
    state=output/"state.json"; events=output/"events.jsonl"
    s=load(state)
    run(s,a.duration_seconds,events,state,a.heartbeat_seconds)
    summary={"started_with_usdc":START_USDC,"cash_usdc":round(s["cash"],5),
             "realized_pnl_usdc":round(s["realized_pnl"],5),
             "return_pct":round(100*s["realized_pnl"]/START_USDC,4),
             "stages_done":s["stages_done"],"metrics":s["counters"],
             "model":"Future-best-ask-cross proxy only, NOT actual maker queue fills",
             "estimated_cost_per_merge_usdc":MERGE_COST,"one_sided_exit_haircut":EXIT_HAIRCUT,
             "maker_rebates_included":False,"trades":s["history"]}
    (output/"summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True))
    print("PAPER_SUMMARY "+json.dumps({k:v for k,v in summary.items() if k!="trades"}),flush=True)

if __name__=="__main__":
    main()
