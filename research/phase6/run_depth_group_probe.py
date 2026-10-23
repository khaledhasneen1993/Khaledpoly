"""Reproduce frozen four-case development calibration from original RAW rows."""
import argparse
import base64
import gzip
import hashlib
import json
from decimal import Decimal as D
from pathlib import Path
from research.phase6.depth_group_probe import Probe


ROOT=Path('research/experiments/depth-group-probe-20261018')


def run():
    freeze=json.loads((ROOT/'freeze.json').read_text())
    for name,digest in freeze['filesSha256'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest:
            raise ValueError('Frozen source/evidence/config changed: '+name)
    evidence=json.loads(gzip.decompress(base64.b64decode((ROOT/'evidence.json.gz.b64').read_bytes(),validate=True)))
    results=[]
    for case in evidence['cases']:
        row=evidence['rows'][str(case['snapshotSeq'])];snapshot=json.loads(row['data']['text'])
        snapshot_at=row['arrivalMs']
        outcomes={}
        for name,enabled in [('baseline',False),('quarantineCandidate',True)]:
            p=Probe(case['token'],snapshot,snapshot_at,enabled,freeze['quarantineMaxMs'])
            prefix_error=None
            for seq in case['prefixRawSequences']:
                row=evidence['rows'][str(seq)]
                status=p.accept(json.loads(row['data']['text']),row['arrivalMs'])
                if status['status']!='PREFIX_CONSISTENT':
                    prefix_error=dict(status='PREFIX_UNVERIFIED',firstUnverifiedRawSeq=seq,
                        probeStatus=status['status'],bookPublished=False)
                    break
            if prefix_error:
                outcomes[name]=prefix_error
                continue
            row=evidence['rows'][str(case['triggerRawSeq'])]
            initial=p.accept(json.loads(row['data']['text']),row['arrivalMs'])
            result=initial
            used=[]
            if enabled:
                if initial['status']!='QUARANTINED':raise ValueError('Expected proven incomplete group')
                for seq in case['followupRawSequences']:
                    row=evidence['rows'][str(seq)];message=json.loads(row['data']['text'])
                    if message.get('event_type')!='price_change':continue
                    result=p.accept(message,row['arrivalMs']);used.append(seq)
                    if result['status']!='QUARANTINED':break
            elif initial['status']!='WAIT_FULL_SNAPSHOT':raise ValueError('Baseline no longer reproduces invalidation')
            outcomes[name]=dict(result,usedFollowupRawSequences=used)
            if enabled and result['status']=='RECOVERY_CANDIDATE':
                confirmation=evidence['rows'][str(case['confirmationSnapshotSeq'])]
                full=json.loads(confirmation['data']['text'])
                actual={side:{D(str(x['price'])):D(str(x['size'])) for x in full[side]
                    if D(str(x['size']))>0} for side in ('bids','asks')}
                trigger=evidence['rows'][str(case['triggerRawSeq'])]
                baseline_delay=confirmation['arrivalMs']-trigger['arrivalMs']
                outcomes[name].update(confirmationSnapshotSeq=case['confirmationSnapshotSeq'],
                    confirmationFullDepthEqual=actual==p.recovered_book,
                    confirmationSourceAndHashEqual=(int(full['timestamp'])==result['sourceMs'] and full['hash']==result['hash']),
                    baselineFullSnapshotDelayMs=baseline_delay,latencyGainMs=baseline_delay-result['delayMs'])
        results.append(dict(anchorSeq=case['anchorSeq'],token=case['token'],snapshotSeq=case['snapshotSeq'],
            triggerRawSeq=case['triggerRawSeq'],outcomes=outcomes))
    return dict(scope='FOUR_SELECTED_DEVELOPMENT_RAW_GROUPS_NOT_STRATEGY_OR_FILL_QUALIFICATION',
        sourceContextArtifact=12134459459,quarantineMaxMs=freeze['quarantineMaxMs'],cases=results,
        baselineInvalidations=sum(x['outcomes']['baseline']['status']=='WAIT_FULL_SNAPSHOT' for x in results),
        unverifiedPrefixCases=sum(x['outcomes']['baseline']['status']=='PREFIX_UNVERIFIED' for x in results),
        baselinePolicy='STRICT_PREFIX_VALIDATION_THEN_DISABLED_PROBE_NOT_FULL_RUNTIME_REPLAY',
        recoveryCandidates=sum(x['outcomes']['quarantineCandidate']['status']=='RECOVERY_CANDIDATE' for x in results),
        candidateWorthIndependentTest=False,
        rejectionReasons=['NO_LATENCY_GAIN_VERSUS_ACTUAL_FULL_SNAPSHOT_IN_SELECTED_CASES',
                          'SELECTED_DEVELOPMENT_COMPONENT_PROBE_NOT_STRATEGY_QUALIFICATION'],
        originalAccountNetPnl=-0.85,netPnlRecomputed=False,fillsCreated=0,productionEnabled=False,
        historicalGapOrMarkoutRetracted=False,hashCryptographicallyVerified=False,
        decision='NO_GO',liveAllowed=False,independentPaperQualificationAllowed=False,
        limitation='Opaque hash/source/top agreement in selected groups is conditional recovery evidence, not a cryptographic full-book proof or independent production validation.')


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
    result=run()
    with Path(a.output).open('x') as out:out.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
