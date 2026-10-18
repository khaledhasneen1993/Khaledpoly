"""Evaluate the already committed DQ3-0 rule on immutable selected decision states."""
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from research.phase6.depth_quote_lab import propose
from research.phase6.entry_witness_result import analyze,load


def screen():
    frozen=json.loads(Path('research/phase6/depth-quote-candidate-freeze.json').read_text())
    for p,d in frozen['filesSha256'].items():
        if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=d:raise ValueError('Frozen DQ3 source/evidence changed: '+p)
    analyze()
    config=json.loads(Path('research/phase2/research-config.json').read_text())
    report=json.loads(load()['report.json'],parse_float=Decimal);rows=[]
    for w in report['entryDecisionWitnesses']:
        proposal=propose(w,config)
        rows.append(dict(at=w['at'],originalSequence=w['originalSequence'],actualLegacyReason=w['actualDecisionReasonDelta'],
            originalQuantity=w['quantity'],originalRequiredEdge=w['requiredEdge'],
            originalMinSize=w['market']['minSize'],proposal=proposal,
            additionalPricedState=proposal is not None and 'PAIR_SUBMITTED' not in w['actualDecisionReasonDelta']))
    additional=sum(r['additionalPricedState'] for r in rows)
    return dict(experiment='DQ3-0',scope='SELECTED_DEVELOPMENT_STATE_PRICE_FEASIBILITY_NOT_ACCOUNT_REPLAY',
        preregistrationCommit='0cc9cc16633ef20eea1129f2793322b683acb29d',states=rows,
        actualLegacyPairSubmittedStates=sum('PAIR_SUBMITTED' in r['actualLegacyReason'] for r in rows),
        candidatePricedStates=sum(r['proposal'] is not None for r in rows),additionalPricedStates=additional,
        candidateStateTrajectorySimulated=False,fillsCreated=0,netPnlRecomputed=False,
        queueFeeLatencyRiskLimitsChanged=False,independentPaperQualificationAllowed=False,liveAllowed=False,
        decision='NEXT_NECESSARY_TRAFFIC_SCREEN_ONLY' if additional else 'REJECT_NO_ADDITIONAL_PRICE_FEASIBILITY',
        note='Independent actual legacy account snapshots, NOT causal successive candidate submissions. Existing displayed depth is not guaranteed future queue or fill. No account promotion or independent capture.')


if __name__=='__main__':
    print(json.dumps(screen(),indent=2,default=str))
