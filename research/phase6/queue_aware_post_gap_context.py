"""One frozen original post-GAP data window, no orders/RPC/model/PnL."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
from research.phase3.polybot_sdk.tapes import open_tape
from research.phase6.dq3_last_activation import extract
from research.phase6.queue_aware_causal import QROOT


def spec():
    cfg=json.loads(Path('research/phase2/research-config.json').read_text());gap=1792269760873;first=1792269754123
    return dict(startMs=gap-cfg['maxBookAgeMs'],endMs=first+cfg['unhedgedMs']+cfg['maxBookAgeMs'],
        maxBookAgeMs=cfg['maxBookAgeMs'],sourceRows=6163831,
        logicalTapeSha256='cd850df52d7f9994526603130f2942008f8f49ba80495d82b70dea66f0dc6d8b',
        states=[dict(originalSequence=260656,submitMs=gap)],firstModelAllocationMs=first,firstGapMs=gap,
        unchangedUnhedgedDeadlineMs=first+cfg['unhedgedMs'])


def summarize(context,pair):
    s=context['spec'];books={};first=None;gaps=[];samples=[];anchor=False
    def affected(v):return set(v.get('tokens',[]))|({v['token']} if 'token' in v else set())
    for rec in context['records']:
        row=rec['input'];at=row['arrivalMs'];events=row['data']['events'] if row['kind']=='RESEARCH_FRAME' else [dict(kind=row['kind'][9:],data=row['data'])]
        for ix,event in enumerate(events):
            k=event['kind'];v=event['data']
            if k in ('GAP','FEED_ERROR') and (not affected(v) or affected(v)&pair):
                books.clear();gaps.append(dict(seq=row['seq'],eventIndex=ix,at=at,kind=k,reason=v.get('reason')))
                if row['seq']==s['states'][0]['originalSequence'] and at==s['firstGapMs'] and v.get('reason')=='invalid_depth':anchor=True
            elif k=='BOOK' and v['token'] in pair:
                token=v['token'];old=books.get(token);source=v['sourceMs']
                if not 0<=at-source<=s['maxBookAgeMs'] or old and source<old['sourceMs']:books.pop(token,None)
                else:books[token]=v
            elif k=='TRADE' and v['token'] in pair and at>s['firstGapMs']:
                sample=json.loads(v['tradeId'])
                if sample['asset_id']!=v['token'] or int(sample['timestamp'])!=v['sourceMs']:raise ValueError('Changed original post-GAP sample')
                samples.append(dict(seq=row['seq'],eventIndex=ix,at=at,sourceMs=v['sourceMs'],sample=sample))
        if at>s['firstGapMs'] and events and first is None and all(t in books and books[t]['bids'] and books[t]['asks'] and 0<=at-books[t]['sourceMs']<=s['maxBookAgeMs'] for t in pair):
            first=dict(seq=row['seq'],at=at,books={t:books[t] for t in sorted(pair)})
    if not anchor:raise ValueError('Original first GAP anchor absent')
    return dict(scope='ORIGINAL_POST_GAP_DATA_ONLY_NO_STRATEGY_OR_ACCOUNT',spec=s,
        firstFreshBothBookCallback=first,scopedGaps=gaps,allOriginalPairTradesAfterGap=samples,
        observationCount=len(samples),unknownReceiptLabels=len(samples),receiptRequests=0,
        hypotheticalOrdersCreated=0,modelFillsCreated=0,candidateAccountSimulated=False,netPnlRecomputed=False,
        independentPaperQualificationAllowed=False,liveAllowed=False)


def main():
    p=argparse.ArgumentParser();p.add_argument('--input-root',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    f=json.loads(Path('research/phase6/queue-aware-post-gap-freeze.json').read_text())
    for path,sha in f['filesSha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=sha:raise ValueError('Frozen post-GAP source changed '+path)
    s=spec()
    if s!=f['spec']:raise ValueError('Changed original window/risk deadline')
    tapes=[*Path(a.input_root).rglob('events.jsonl.gz'),*Path(a.input_root).rglob('events.jsonl')]
    if len(tapes)!=1:raise ValueError('Require one complete original tape')
    with open_tape(tapes[0]) as stream:context=extract(stream,s,max_bytes=128000000)
    pair=set(json.loads((QROOT/'causal-bindings.json').read_text())['pair']);summary=summarize(context,pair)
    out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    raw=(json.dumps(context,separators=(',',':'))+'\n').encode();(out/'context.json.gz').write_bytes(gzip.compress(raw,mtime=0))
    (out/'data-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in ['allOriginalPairTradesAfterGap','firstFreshBothBookCallback','scopedGaps']}))


if __name__=='__main__':main()
