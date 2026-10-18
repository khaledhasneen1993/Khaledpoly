"""Read only a frozen <=20-transaction selection; conserve actual route volumes."""
import argparse
from collections import Counter, defaultdict
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import time
from research.phase6.receipt_audit import EXCHANGES, corroborate, event_topics, rpc


def routes(result, pair):
    groups=defaultdict(list)
    for match in result['matches']:
        groups[(match['exchange'],match['ordersMatchedLogIndex'],match['taker']['orderHash'])].append(match)
    validated=[];sample=result['sample'];unrelated=0
    for key, rows in groups.items():
        taker=rows[0]['taker'];buy=taker['side']=='BUY'
        if taker['token'] not in pair:
            unrelated+=1
            continue
        if key[0] not in EXCHANGES or taker['side'] not in ('BUY','SELL'):
            raise ValueError('Untrusted route/side')
        for amount in ('makingRaw','takingRaw'):
            if type(taker[amount]) is not int or taker[amount]<=0:raise ValueError('Invalid taker amount')
        shares=collateral=0;seen=set();totals=Counter();parts=[]
        for match in rows:
            maker=match['maker'];kind=match['matchType']
            if match['taker']!=taker or maker['logIndex'] in seen:raise ValueError('Mixed/duplicate maker group')
            seen.add(maker['logIndex'])
            if any(type(maker[k]) is not int or maker[k]<=0 for k in ('makingRaw','takingRaw')):
                raise ValueError('Invalid maker amount')
            if kind=='DIRECT':
                if maker['token']!=taker['token'] or maker['side']==taker['side']:raise ValueError('Invalid DIRECT')
                q=maker['makingRaw'] if buy else maker['takingRaw']
                c=maker['takingRaw'] if buy else maker['makingRaw'];taker_value=c
            elif kind in ('MINT','MERGE'):
                if ({maker['token'],taker['token']}!=set(pair) or maker['side']!=taker['side']
                        or kind!=('MINT' if buy else 'MERGE')):raise ValueError('Invalid complementary route')
                q=maker['takingRaw'] if buy else maker['makingRaw']
                c=maker['makingRaw'] if buy else maker['takingRaw'];taker_value=q-c
            else:raise ValueError('Unsupported route')
            if not 0<c<q:raise ValueError('Invalid component price')
            shares+=q;collateral+=taker_value;totals[kind]+=q
            parts.append(dict(route=kind,makerToken=maker['token'],makerSide=maker['side'],
                sharesRaw=q,collateralRaw=c,makerPrice=str(Decimal(c)/Decimal(q)),makerLogIndex=maker['logIndex']))
        if shares!=(taker['takingRaw'] if buy else taker['makingRaw']) or collateral!=(taker['makingRaw'] if buy else taker['takingRaw']):
            raise ValueError('Route shares/collateral do not conserve')
        if (taker['token']==sample['asset_id'] and taker['side']==sample['side']
                and Decimal(shares)/1000000==Decimal(sample['size'])):
            validated.append(dict(exchange=key[0],groupLogIndex=key[1],takerOrderHash=key[2],
                sharesRaw=shares,collateralRaw=collateral,routeSharesRaw=dict(totals),components=parts))
    return dict(identityMatchingGroups=len(validated),uniqueConservedGroup=len(validated)==1,
        matchingGroups=validated,unrelatedGroupsExcluded=unrelated,queueAllocationProven=False,fillsCreated=0)


def validate_selection(selection, pair):
    txs=selection['transactions']
    if not 1<=len(txs)<=20 or len({x['transactionHash'] for x in txs})!=len(txs):
        raise ValueError('Require <=20 unique frozen transactions')
    cohorts={x['role']:x for x in selection['cohorts']}
    for row in txs:
        sample=row['sample'];tx=row['transactionHash']
        if (not re.fullmatch('0x[0-9a-f]{64}',tx) or sample['transaction_hash']!=tx
                or sample['asset_id'] not in pair or sample['side'] not in ('BUY','SELL') or not row['roles']):
            raise ValueError('Invalid frozen transaction identity')
        for role in row['roles']:
            c=cohorts[role];o=c['orderDiagnostic']
            if (tx not in c['transactions'] or not o['activatedMs']<=int(sample['timestamp'])<=sample['arrivalMs']<=o['terminalMs']):
                raise ValueError('Sample lies outside frozen order lifecycle')


def collect(selection, output, pair, *, topics=None, read=rpc):
    validate_selection(selection,pair)
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    raw_dir=output/'raw';raw_dir.mkdir(exist_ok=True)
    selection_bytes=(json.dumps(selection,sort_keys=True,separators=(',',':'))+'\n').encode()
    checkpoint=output/'selection.json'
    if checkpoint.exists() and checkpoint.read_bytes()!=selection_bytes:raise ValueError('Resume selection changed')
    if not checkpoint.exists():checkpoint.write_bytes(selection_bytes)
    topics=topics or event_topics();results=[];errors=[];blocks={};calls=Counter()
    for item in selection['transactions']:
        path=item.get('existingCachedReceipt')
        if path:
            cached=json.loads(Path(path).read_text());blocks[cached['block']['hash'].lower()]=cached['block']
    def query(method, params):calls[method]+=1;return read(method,params)
    if int(query('eth_chainId',[]),16)!=137:raise ValueError('Wrong public chain')
    for item in selection['transactions']:
        tx=item['transactionHash'];target=raw_dir/(tx+'.json')
        try:
            source=target if target.exists() else Path(item['existingCachedReceipt']) if item.get('existingCachedReceipt') else None
            if source:
                data=json.loads(source.read_text());origin='OUTPUT_CACHE' if source==target else 'COMMITTED_CACHE'
                blocks[data['block']['hash'].lower()]=data['block']
            else:
                if calls['eth_getTransactionReceipt']>=selection.get('maxNewReceiptRequests',20):
                    raise ValueError('Predeclared new-receipt budget exhausted')
                time.sleep(0.5)
                receipt=query('eth_getTransactionReceipt',[tx])
                if not receipt:raise ValueError('Receipt absent')
                block_hash=receipt['blockHash'].lower()
                if block_hash not in blocks:blocks[block_hash]=query('eth_getBlockByHash',[receipt['blockHash'],False])
                data=dict(receipt=receipt,block=blocks[block_hash]);origin='PUBLIC_READ'
            if not target.exists():target.write_text(json.dumps(data,separators=(',',':'))+'\n')
            result=corroborate(item['sample'],data['receipt'],data['block'],topics)
            result.update(roles=item['roles'],receiptOrigin=origin,routeConservation=routes(result,pair))
            results.append(result)
        except (OSError,ValueError,KeyError,TypeError) as error:
            errors.append(dict(transactionHash=tx,error=str(error)[:200]))
    report=dict(scope='FROZEN_SELECTED_DEVELOPMENT_ENTRY_EXIT_ROUTE_AUDIT',requested=len(selection['transactions']),
        corroborated=len(results),complete=not errors and len(results)==len(selection['transactions']),
        results=results,errors=errors,eventTopics=topics,rpcCalls=dict(calls),
        uniqueConservedGroups=sum(x['routeConservation']['uniqueConservedGroup'] for x in results),
        selectionSha256=hashlib.sha256(selection_bytes).hexdigest(),
        fillsCreated=0,netPnlRecomputed=False,originalAccountNetPnl=-0.85,
        independentPaperQualificationAllowed=False,liveAllowed=False,decision='NO_GO',
        note='Actual maker route volumes do not prove counterfactual queue allocation or redirect priority across DIRECT/MINT/MERGE.')
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
    f=json.loads(Path('research/phase6/route-coverage-freeze.json').read_text())
    for name,digest in f['filesSha256'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:raise ValueError('Frozen route audit changed: '+name)
    r=collect(json.loads(Path(f['selection']).read_text()),a.output,set(f['pair']))
    print(json.dumps({k:v for k,v in r.items() if k not in ('results','eventTopics')}),flush=True)
    if not r['complete']:raise SystemExit('Incomplete receipt audit; retain successes/errors, do not broaden selection')


if __name__=='__main__':main()
