"""Export ALL451 conserved mixed-side routes from retained receipts, offline only."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
from research.phase6.queue_aware_recovery_result import load,verify
from research.phase6.queue_aware_causal import QROOT
from research.phase6.queue_aware_post_gap_result import LOGICAL_SHA,COMPRESSED_SHA
from research.phase6.receipt_audit import corroborate
from research.phase6.route_coverage_audit import routes


def export():
    spec,evidence,summary=load();proof=verify(spec,evidence,summary)
    by_key={(r['normalizedSeq'],r['eventIndex']):r for r in summary['results']}
    trades={};digest=hashlib.sha256()
    with gzip.open(QROOT/'post-gap-result/context.records.jsonl.gz','rb') as source:
        for line in source:
            digest.update(line);row=json.loads(line)['input']
            events=row['data'].get('events',[]) if row['kind']=='RESEARCH_FRAME' else [dict(kind=row['kind'][9:],data=row['data'])]
            for ix,event in enumerate(events):
                key=(row['seq'],ix)
                if key in by_key:
                    if event['kind']!='TRADE' or key in trades:raise ValueError('Original label coordinate is not a unique TRADE')
                    trades[key]=(row['arrivalMs'],event['data'])
                elif (event['kind']=='TRADE' and event['data']['token'] in spec['pair']
                        and spec['window']['firstGapMs']<row['arrivalMs']<=spec['window']['endMs']):
                    raise ValueError('Unknown original pair observation; never suppress missing coverage')
    if digest.hexdigest()!=LOGICAL_SHA or set(trades)!=set(by_key):raise ValueError('Incomplete retained source/labels')
    bindings=[];counts={}
    for key,r in by_key.items():
        at,trade=trades[key];sample=r['sample'];tx=r['transactionHash'];e=evidence[tx]
        if (at!=r['arrivalMs'] or json.loads(trade['tradeId'])!=sample
                or sample['asset_id']!=trade['token'] or sample['side']!=trade['side']):raise ValueError('Changed original public trade identity')
        decoded=corroborate(sample,e['data']['receipt'],e['data']['block'],e['topics'])
        conserved=routes(decoded,set(spec['pair']))
        if not conserved['uniqueConservedGroup']:raise ValueError('Ambiguous mixed-side group')
        group=conserved['matchingGroups'][0]
        matches=[m for m in decoded['matches'] if m['exchange']==group['exchange'] and m['ordersMatchedLogIndex']==group['groupLogIndex']]
        for m in matches:counts[m['matchType']]=counts.get(m['matchType'],0)+1
        bindings.append(dict(seq=key[0],eventIndex=key[1],at=at,sourceMs=trade['sourceMs'],
            transactionHash=tx,publicTradeIdSha256=hashlib.sha256(trade['tradeId'].encode()).hexdigest(),
            token=trade['token'],side=trade['side'],price=trade['price'],size=trade['size'],pair=spec['pair'],matches=matches))
    return dict(schema=1,experiment='CONSERVED-MIXED-LAB0',partialLabels=True,
        logicalTapeSha256=spec['originalTapeLogicalSha256'],contextLogicalSha256=LOGICAL_SHA,
        contextCompressedSha256=COMPRESSED_SHA,expectedBindingCount=451,expectedComponentCount=1038,
        coverage=dict(pair=spec['pair'],afterMs=spec['window']['firstGapMs'],throughMs=spec['window']['endMs'],
            allOriginalPairObservationsWithinWindow=True,unknownScopedObservation='FAIL_CLOSED'),
        routeComponentCounts=counts,receiptVerification=proof,bindings=bindings,
        adapterOnlyNotAccountReplay=True,modelFillsCreated=0,netPnlRecomputed=False,
        candidateAccountSimulated=False,independentPaperQualificationAllowed=False,liveAllowed=False)


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
    root=export();path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(root,indent=2)+'\n')
    print(json.dumps(dict(bindings=len(root['bindings']),components=root['expectedComponentCount'],routes=root['routeComponentCounts'],newPublicReads=0,accountSimulated=False)))


if __name__=='__main__':main()
