"""First preregistered QW0 gate, same immutable34 witnesses, no account replay."""
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from research.phase6.queue_aware_quote_lab import propose
from research.phase6.depth_quote_lab import propose as baseline
from research.phase6.entry_witness_result import analyze,load


def screen():
    f=json.loads(Path('research/phase6/queue-aware-quote-freeze.json').read_text())
    for path,sha in f['filesSha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=sha:raise ValueError('Changed frozen QW0 input '+path)
    analyze();cfg=json.loads(Path('research/phase2/research-config.json').read_text())
    witnesses=json.loads(load()['report.json'],parse_float=Decimal)['entryDecisionWitnesses'];rows=[]
    for w in witnesses:
        b=baseline(w,cfg);p=propose(w,cfg)
        changed=p is not None and b is not None and (p['firstBid'],p['secondBid'])!=(b['firstBid'],b['secondBid'])
        rows.append(dict(originalSequence=w['originalSequence'],at=w['at'],actualLegacyReason=w['actualDecisionReasonDelta'],
            originalQuantity=w['quantity'],originalMinSize=w['market']['minSize'],baselineDQ3=b,proposal=p,
            changedPricedPair=changed,additionalLawfulStateVsLegacy=p is not None and 'PAIR_SUBMITTED' not in w['actualDecisionReasonDelta']))
    additional=sum(r['additionalLawfulStateVsLegacy'] for r in rows);changed=sum(r['changedPricedPair'] for r in rows)
    return dict(experiment='QW0',preregistrationCommit='62c72e053e4ae29dc0e34fdff7e95174123212a1',
        scope='SAME_SELECTED_LEGACY_DEVELOPMENT_WITNESSES_PRICE_SCREEN_NOT_ACCOUNT_PERFORMANCE',states=rows,
        witnessCount=len(rows),actualLegacySubmittedStates=sum('PAIR_SUBMITTED' in r['actualLegacyReason'] for r in rows),
        baselineDQ3PricedStates=sum(r['baselineDQ3'] is not None for r in rows),
        candidatePricedStates=sum(r['proposal'] is not None for r in rows),additionalLawfulStatesVsLegacy=additional,
        changedPricedPairsVsDQ3=changed,originalSizeBlockedStatesStillBlocked=sum(r['originalQuantity']<r['originalMinSize'] and r['proposal'] is None for r in rows),
        queueProxiesAreNotActivationOrFills=True,candidateAccountSimulated=False,fillsCreated=0,netPnlRecomputed=False,
        feesQueueRiskLimitsOrAcceptanceRelaxed=False,independentPaperQualificationAllowed=False,liveAllowed=False,
        decision='SEPARATELY_FREEZE_NECESSARY_TRAFFIC_ONLY' if additional and changed else 'REJECT_PREREGISTERED_PRICE_GATE')


if __name__=='__main__':print(json.dumps(screen(),indent=2,default=str))
