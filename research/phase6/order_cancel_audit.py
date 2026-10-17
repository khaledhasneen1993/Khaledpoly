"""Read-only causal audit of recorded order terminals. No replay or parameter changes."""
import argparse
from collections import Counter,deque
from decimal import Decimal
import json
from pathlib import Path
import re
import tarfile

KIND=re.compile(rb'"kind"\s*:\s*"([^"\\]+)"')

def raw_assets(raw):
    if raw is None:return set()
    text=json.loads(raw)['data']['text']
    if text.upper() in ('PING','PONG'):return set()
    value=json.loads(text);nodes=value if isinstance(value,list) else [value]
    return {token for node in nodes for token in [node.get('asset_id'),*(x.get('asset_id') for x in node.get('price_changes',[]))] if token}

def audit(stream,ledger):
    outstanding={};orders={};metadata={};token_end={};last_input=None;last_raw=None
    reasons=Counter();stale=Counter();invalid=Counter();scope=Counter();read_rows=0;complete=False
    def context(line):
        row=json.loads(line);kind=row['kind'];data=row['data'];events=data.get('events',[]) if kind=='RESEARCH_FRAME' else [{'kind':kind.removeprefix('RESEARCH_'),'data':data}]
        gaps=[]
        for event in events:
            if event['kind']!='GAP':continue
            g=dict(event['data']);tokens={g['token']} if g.get('token') else raw_assets(last_raw) if kind=='RESEARCH_FRAME' else set()
            g['affectedTokensFromRecordedPayload']=sorted(tokens);gaps.append(g)
        return row,events,gaps
    for line in stream:
        read_rows+=1
        match=KIND.search(line[:1024])
        if match is None:raise ValueError('Missing journal kind')
        kind=match.group(1).decode()
        if kind=='RAW_MARKET':last_raw=line;continue
        if kind in ('RESEARCH_META','RESEARCH_FRAME','RESEARCH_GAP','RESEARCH_TICK','RESEARCH_RESOLUTION','RESEARCH_FEED_ERROR','RESEARCH_MARKET_UNAVAILABLE'):
            last_input=line
            if kind=='RESEARCH_FRAME' and not outstanding and b'"GAP"' not in line:continue
            row,events,gaps=context(line);at=row['arrivalMs']
            if kind=='RESEARCH_META':
                m=row['data'];metadata[m['condition']]=m
                for token in (m['first'],m['second']):token_end[token]=m['endMs']
            for gap in gaps:
                reasons[gap.get('reason','unknown')]+=1
                tokens=gap['affectedTokensFromRecordedPayload']
                scope['noRecoverableAssets' if not tokens else 'onlyExpiredAssets' if all(t in token_end and token_end[t]<=at for t in tokens) else 'hasCurrentOrUnknownAssets']+=1
                if gap.get('reason')=='stale_source':
                    age=gap.get('observedMs',at)-gap.get('sourceMs',-1)
                    stale['futureTimestamp' if age<0 else 'over2000ms' if age>2000 else 'within2000msAtJournal']+=1
                if gap.get('reason')=='invalid_depth':invalid[gap.get('detail','unknown')]+=1
            for identity,order in outstanding.items():
                token=order['token'];interesting=[]
                for event in events:
                    data=event['data'];ek=event['kind']
                    if ek=='GAP':interesting.append({'kind':ek,'reason':data.get('reason'),'token':data.get('token')})
                    elif ek=='BOOK' and data.get('token')==token:
                        def best(side,buy):
                            levels=data.get(side,[])
                            if not levels:return None
                            return (max if buy else min)(levels,key=lambda x:Decimal(str(x['price'])))
                        interesting.append({'kind':ek,'sourceMs':data.get('sourceMs'),'bid':best('bids',True),'ask':best('asks',False)})
                    elif ek=='TRADE' and data.get('token')==token:
                        order['sameTokenPrints']+=1
                        if data.get('side')=='SELL' and Decimal(str(data['price']))==Decimal(str(order['price'])):
                            order['samePriceSellPrints']+=1
                            order['samePriceSellVolume']+=Decimal(str(data['size']))
                        interesting.append({'kind':ek,**data})
                    elif ek=='TICK_SIZE' and data.get('token')==token:interesting.append({'kind':ek,**data})
                if interesting:order['recentInputs'].append({'at':at,'seq':row['seq'],'events':interesting[:8]})
        elif kind=='SESSION_ORDER':
            row=json.loads(line);data=row['data'];identity=data['id']
            if identity in orders:raise ValueError('Duplicate order ID')
            order=dict(data,token=ledger['orders'][identity]['token'],sameTokenPrints=0,samePriceSellPrints=0,samePriceSellVolume=Decimal(0),recentInputs=deque(maxlen=6))
            orders[identity]=order;outstanding[identity]=order
        elif kind=='SESSION_ORDER_TERMINAL':
            row=json.loads(line);data=row['data'];identity=data['id']
            order=outstanding.pop(identity,None)
            if order is None:raise ValueError('Unknown terminal')
            parent,events,gaps=context(last_input)
            affected=set().union(*(set(g['affectedTokensFromRecordedPayload']) for g in gaps)) if gaps else set()
            market=metadata[order['condition']];pair={market['first'],market['second']}
            order.update(terminal=data,lifetimeMs=data['at']-order['at'],terminalInputKind=parent['kind'],terminalInputSeq=parent['seq'],terminalInputArrivalMs=parent['arrivalMs'],terminalInputGaps=gaps,
                directGapInput=bool(gaps),gapAssetsDisjointFromPair=bool(gaps and affected and not affected&pair))
        elif kind=='RUN_END':complete=json.loads(line)['data'].get('complete') is True
    rows=[]
    for order in orders.values():
        row=dict(order);row['samePriceSellVolume']=str(row['samePriceSellVolume']);row['recentInputs']=list(row['recentInputs']);rows.append(row)
    life=sorted(row['lifetimeMs'] for row in rows if 'lifetimeMs' in row)
    return {'scope':'RECORDED_CAUSAL_TERMINAL_AUDIT','journalRows':read_rows,'recordingClosedCleanly':complete,'orders':len(rows),'outstanding':list(outstanding),
        'terminalStatuses':dict(Counter(row['terminal']['status'] for row in rows if 'terminal' in row)),
        'gapInputTerminals':sum(row.get('directGapInput',False) for row in rows),
        'unrelatedAssetGapTerminals':sum(row.get('gapAssetsDisjointFromPair',False) for row in rows),
        'terminatedBefore250ms':sum(row.get('lifetimeMs',999999)<250 for row in rows),
        'lifetimeMs':{'min':min(life) if life else None,'max':max(life) if life else None,'median':life[len(life)//2] if life else None},
        'gapReasons':dict(reasons),'staleSourceClassification':dict(stale),'invalidDepthDetails':dict(invalid),'gapAssetScope':dict(scope),'orderAudit':rows}

def main():
    p=argparse.ArgumentParser();p.add_argument('--archive',required=True);p.add_argument('--ledger',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    ledger=json.loads(Path(a.ledger).read_text());result=None
    with tarfile.open(a.archive,'r|gz') as archive:
        for member in archive:
            if member.isfile() and member.name.startswith('two-hour/ingestor/') and member.name.endswith('/events.jsonl'):
                if result is not None:raise ValueError('Multiple journals')
                result=audit(archive.extractfile(member),ledger)
    if result is None:raise ValueError('Missing journal')
    target=Path(a.output);target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(result,separators=(',',':')))
    print(json.dumps({k:v for k,v in result.items() if k!='orderAudit'},separators=(',',':')))
if __name__=='__main__':main()
