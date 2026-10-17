"""Purged, censored fill/second-leg/markout research model diagnostics.

Runs only on explicit own-order labels. PAPER_MODEL is a simulator claim, not
observed venue liquidity or FIFO position. Unverified VENUE_EXECUTION text
provenance is also NOT independent proof of execution.
"""
import argparse
from collections import Counter
import hashlib
from pathlib import Path

from research.phase3.polybot_sdk.learning import train, example
from research.phase3.polybot_sdk.model import decode, dumps, integer
from research.phase3.polybot_sdk.runtime import private_write

MAX_LABELS = 100000
TARGETS = ('fill', 'second_leg', 'adverse_selection')
PROVENANCES = ('PAPER_MODEL', 'VENUE_EXECUTION')


def summarize_labels(rows, target, horizon_ms):
    positives = negatives = censored = 0
    delays = []
    for row in rows:
        e = example(row, target, horizon_ms)
        if e is None:
            censored += 1
            continue
        if e.label:
            positives += 1
        else:
            negatives += 1
        if target == 'fill' and e.label and e.fill_delay_ms is not None:
            delays.append(e.fill_delay_ms)
    delays.sort()
    return {'positive':positives, 'negative':negatives, 'censored':censored,
            'observedFillLatencyP50Ms':delays[len(delays)//2] if delays else None,
            'observedFillLatencyP90Ms':delays[min(len(delays)-1,(len(delays)*9+9)//10-1)] if delays else None,
            'censoredNotAssumedUnfilled':True}


def evaluate_models(rows, holdout_start_ms, *, horizon_ms=5000,
                    min_train=1000, min_holdout=200, min_class=20):
    if type(rows) is not list or not rows or len(rows)>MAX_LABELS:
        raise ValueError('Bounded nonempty label dataset required')
    cut = integer(holdout_start_ms)
    if cut <= 0 or type(horizon_ms) is not int or not 1 <= horizon_ms <= 600000:
        raise ValueError('Invalid predeclared evaluation horizons')
    raw, provenance, seen = [], set(), set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Nonobject label')
        key = row['marketId'], row['orderId']
        if key in seen:
            raise ValueError('Duplicate market/order label')
        seen.add(key)
        if row['provenance'] not in PROVENANCES:
            raise ValueError('Unknown label provenance')
        provenance.add(row['provenance'])
        # Validates causal price/queue features and all three outcome clocks.
        example(row, 'fill', horizon_ms)
        example(row, 'second_leg', horizon_ms)
        if row.get('markout') is not None:
            example(row, 'adverse_selection', horizon_ms)
        raw.append(row)
    if len(provenance) != 1:
        raise ValueError('Mixing PAPER and venue labels would invalidate evidence')
    source = next(iter(provenance))
    evaluation={}
    for target in TARGETS:
        artifact = train(raw, cut, target=target, horizon_ms=horizon_ms,
                         min_train=min_train, min_holdout=min_holdout, min_class=min_class)
        # Preserve numeric calibration metrics but not a misleading live-ready model.
        selected = {k:artifact.get(k) for k in
                    ('status','trainingRows','holdoutRows','purgedRows','censoredRows',
                     'holdoutBrier','baselineBrier','calibration','trainingFillDelayP50Ms')}
        selected['targetSemantics'] = {
            'fill':'Own order full/partial fill before order submission + horizon',
            'second_leg':'Unconditional full intent group completion before initial submission + horizon',
            'adverse_selection':'Negative post-fill price markout after a complete observation horizon'
        }[target]
        selected['labelSummary'] = summarize_labels(raw, target, horizon_ms)
        selected['venueCalibrated'] = False
        selected['modelQualified'] = False
        evaluation[target]=selected
    return {'schema':1,'scope':'OFFLINE_CENSORED_VENUE_OR_PAPER_MODEL_DIAGNOSTICS',
            'datasetSha256':hashlib.sha256(dumps(raw).encode()).hexdigest(),
            'sourceProvenance':source,
            'sourceClaimsVerifiedExternally':False,
            'holdoutStartMs':cut,'horizonMs':horizon_ms,
            'rows':len(raw),'targets':evaluation,
            'calibratedVenueModelAvailable':False,
            'preRegisteredProspectiveHoldout':False,
            'realOrderExecutionEnabled':False,
            'decision':'NO_GO','liveAllowed':False}


def main():
    parser=argparse.ArgumentParser(description='Offline censor-aware fill/outcome research, never funded')
    parser.add_argument('labels',help='Recorded own-order label JSONL; no manufactured trades')
    parser.add_argument('--holdout-start-ms',type=int,required=True)
    parser.add_argument('--horizon-ms',type=int,default=5000)
    parser.add_argument('--min-train',type=int,default=1000)
    parser.add_argument('--min-holdout',type=int,default=200)
    parser.add_argument('--min-class',type=int,default=20)
    parser.add_argument('--output',required=True)
    opts=parser.parse_args()
    rows=[]
    with Path(opts.labels).open(encoding='utf-8') as stream:
        for line in stream:
            if line.strip():
                rows.append(decode(line))
            if len(rows)>MAX_LABELS:
                raise ValueError('Unbounded label dataset')
    result=evaluate_models(rows,opts.holdout_start_ms,horizon_ms=opts.horizon_ms,
                           min_train=opts.min_train,min_holdout=opts.min_holdout,min_class=opts.min_class)
    private_write(opts.output,result)
    print(dumps(result))


if __name__=='__main__':
    main()
