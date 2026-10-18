"""Bounded public, read-only settlement corroboration. Never produces simulated fills."""
import argparse
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path
import re
import time
from urllib.request import Request, urlopen

RPC = 'https://polygon-bor-rpc.publicnode.com'
EXCHANGES = {'0xe111180000d2663c0091e4f400237545b87b996b', '0xe2222d279d744050d28e00520010520000310f59'}
SIGNATURES = {'filled': 'OrderFilled(bytes32,address,address,uint8,uint256,uint256,uint256,uint256,bytes32,bytes32)',
              'matched': 'OrdersMatched(bytes32,address,uint8,uint256,uint256,uint256)'}


def event_topics():
    from Crypto.Hash import keccak  # Optional audit-only dependency; never use SHA3-256 as Ethereum Keccak.
    return {name: '0x'+keccak.new(digest_bits=256, data=signature.encode()).hexdigest()
            for name,signature in SIGNATURES.items()}


def rpc(method, params):
    if method not in ('eth_chainId','eth_getTransactionReceipt','eth_getBlockByHash'):
        raise ValueError('Only public read-only RPC methods allowed')
    request = Request(RPC, data=json.dumps({'jsonrpc':'2.0','id':1,'method':method,'params':params}).encode(),
                      headers={'Content-Type':'application/json','User-Agent':'Khaledpoly-PAPER-receipt-audit'})
    with urlopen(request,timeout=15) as response: raw = response.read(4*1024*1024+1)
    if len(raw)>4*1024*1024: raise ValueError('Oversized public receipt')
    value=json.loads(raw)
    if value.get('error') or 'result' not in value: raise ValueError('Public RPC returned an error')
    return value['result']


def words(data, expected):
    if not re.fullmatch('0x[0-9a-fA-F]{'+str(expected*64)+'}',data): raise ValueError('Unexpected event ABI size')
    return [int(data[i:i+64],16) for i in range(2,len(data),64)]


def decode_matches(logs, topics):
    pending = {}; matches = []; seen = set()
    for log in sorted(logs,key=lambda row:int(row['logIndex'],16)):
        index=int(log['logIndex'],16)
        if index in seen: raise ValueError('Duplicate receipt log index')
        seen.add(index)
        address=log['address'].lower(); ts=log.get('topics',[])
        if address not in EXCHANGES or not ts: continue
        if log.get('removed'): raise ValueError('Removed receipt event')
        if ts[0] == topics['filled']:
            if len(ts)!=4: raise ValueError('Invalid OrderFilled indexed fields')
            side,token,making,taking,fee,builder,metadata=words(log['data'],7)
            if side not in (0,1) or making<=0 or taking<=0: raise ValueError('Invalid fill event amounts')
            pending.setdefault(address,[]).append({'orderHash':ts[1], 'maker':'0x'+ts[2][-40:].lower(),
                'taker':'0x'+ts[3][-40:].lower(), 'side':'BUY' if side==0 else 'SELL', 'token':str(token),
                'makingRaw':making,'takingRaw':taking,'feeRaw':fee,'logIndex':index})
        elif ts[0] == topics['matched']:
            if len(ts)!=3: raise ValueError('Invalid OrdersMatched indexed fields')
            side,token,making,taking=words(log['data'],4)
            batch=pending.pop(address,[]); taker_hash=ts[1]; taker_maker='0x'+ts[2][-40:].lower()
            takers=[row for row in batch if row['orderHash']==taker_hash and row['maker']==taker_maker]
            if len(takers)!=1: raise ValueError('Cannot uniquely join taker aggregate event')
            taker=takers[0]
            if (taker['token'],taker['side'],taker['makingRaw'],taker['takingRaw']) != (str(token),'BUY' if side==0 else 'SELL',making,taking):
                raise ValueError('Taker aggregate events disagree')
            makers=[row for row in batch if row['orderHash']!=taker_hash and row['taker']==taker_maker]
            if not makers or len(makers)!=len(batch)-1: raise ValueError('Unmatched maker event in settlement group')
            for maker in makers:
                same_side=maker['side']==taker['side']; same_token=maker['token']==taker['token']
                if same_side == same_token: raise ValueError('Inconsistent settlement pair fields')
                kind=('MINT' if taker['side']=='BUY' else 'MERGE') if same_side else 'DIRECT'
                matches.append({'exchange':address,'matchType':kind,'maker':maker,'taker':taker,
                                'ordersMatchedLogIndex':index})
    if any(pending.values()): raise ValueError('Unclosed settlement group')
    return matches


def corroborate(sample, receipt, block, topics):
    tx=sample['transaction_hash'].lower()
    if receipt is None: raise ValueError('Receipt not found')
    if receipt.get('transactionHash','').lower()!=tx or int(receipt['status'],16)!=1:
        raise ValueError('Receipt hash/status mismatch')
    if not block or block['hash'].lower()!=receipt['blockHash'].lower(): raise ValueError('Receipt block mismatch')
    if any(log.get('transactionHash','').lower()!=tx for log in receipt['logs']): raise ValueError('Mixed transaction logs')
    matches=decode_matches(receipt['logs'],topics); quantities=[]
    for row in matches:
        taker=row['taker']; shares=taker['takingRaw'] if taker['side']=='BUY' else taker['makingRaw']
        collateral=taker['makingRaw'] if taker['side']=='BUY' else taker['takingRaw']
        if taker['token']==sample['asset_id'] and taker['side']==sample['side']:
            quantities.append({'orderHash':taker['orderHash'],
                'priceDifference':str(abs(Decimal(collateral)/Decimal(shares)-Decimal(sample['price']))),
                'sizeDifference':str(abs(Decimal(shares)/Decimal(1000000)-Decimal(sample['size'])))})
    # A taker can appear once per maker. Do not count its aggregate multiple times.
    unique={row['orderHash']:row for row in quantities}
    return {'transactionHash':tx, 'blockHash':receipt['blockHash'],
            'blockTimestampMs':int(block['timestamp'],16)*1000,'recordedTradeTimestampMs':int(sample['timestamp']),
            'matches':matches,'matchTypes':dict(Counter(row['matchType'] for row in matches)),
            'takerAggregateComparisons':list(unique.values()),'sample':sample,
            'counterfactualQueueAllocationProven':False,'simulatedFillsCreated':False}


def run(paths, output):
    output=Path(output); output.mkdir(parents=True,exist_ok=False)
    topics=event_topics(); samples={}; errors=[]; results=[]
    for path in paths:
        report=json.loads(Path(path).read_text())
        for sample in report['rawLastTradeSamples']:
            tx=sample.get('transaction_hash','')
            if not re.fullmatch('0x[0-9a-fA-F]{64}',tx): raise ValueError('Invalid recorded transaction hash')
            samples.setdefault(tx,sample)
    if not 1<=len(samples)<=10: raise ValueError('Audit requires at most ten fixed recorded samples')
    try:
        if int(rpc('eth_chainId',[]),16)!=137: raise ValueError('Wrong public chain')
        for number,(tx,sample) in enumerate(samples.items()):
            try:
                receipt=rpc('eth_getTransactionReceipt',[tx])
                if receipt is None: raise ValueError('Recorded receipt not found')
                block=rpc('eth_getBlockByHash',[receipt['blockHash'],False])
                (output/('receipt-'+str(number)+'.json')).write_text(json.dumps({'receipt':receipt,'block':block}))
                results.append(corroborate(sample,receipt,block,topics))
            except (OSError,ValueError,KeyError,TypeError) as error:
                errors.append({'transactionHash':tx,'error':str(error)[:200]})
            time.sleep(.5)
    except (OSError,ValueError,KeyError,TypeError) as error:
        errors.append({'scope':'RPC_CHAIN_CHECK','error':str(error)[:200]})
    summary={'scope':'PUBLIC_RECORDED_TRANSACTION_SETTLEMENT_AUDIT','rpc':RPC,'chainId':137,
             'requestedTransactions':len(samples),'corroboratedReceipts':len(results),'results':results,'errors':errors,
             'complete':len(results)==len(samples),'decision':'NO_GO','liveAllowed':False,
             'note':'Public settlements corroborate route semantics, never hypothetical maker queue position or profitability.'}
    (output/'report.json').write_text(json.dumps(summary,indent=2)); print(json.dumps(summary),flush=True)
    if not results: raise RuntimeError('No receipt evidence obtained; inspect retained error report')


def main():
    p=argparse.ArgumentParser(); p.add_argument('--census',action='append',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();run(a.census,a.output)


if __name__=='__main__':main()
