"""Correlated, whole-portfolio historical scenario VaR/ES research only.

No independent-marginal VaR summing and no production risk admission.
A distribution of hypothetical scenario PnLs is not measured venue risk.
"""
import argparse
from decimal import Decimal, ROUND_CEILING
from pathlib import Path

from research.phase3.polybot_sdk.model import number, integer, decode, dumps
from research.phase3.polybot_sdk.runtime import private_write


def measure(positions, scenarios, confidence='0.95', min_scenarios=100):
    alpha = number(confidence)
    if not Decimal('.5') <= alpha < Decimal(1):
        raise ValueError('Invalid confidence level')
    if type(min_scenarios) is not int or not 1 <= min_scenarios <= 10000:
        raise ValueError('Invalid minimum scenario count')
    if (not isinstance(positions, list) or not 1 <= len(positions) <= 256
            or not isinstance(scenarios, list) or not 1 <= len(scenarios) <= 100000):
        raise ValueError('Invalid position/scenario evidence bounds')
    exposures = {}
    ids = set()
    for row in positions:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not row['id'] or row['id'] in ids:
            raise ValueError('Invalid/duplicated position')
        ids.add(row['id'])
        group = row.get('groupId')
        if not isinstance(group, str) or not group.strip():
            raise ValueError('Every position requires a correlation/settlement group')
        size = number(row['exposureUsd'])
        if not Decimal(0) < size <= Decimal('1000000000000'):
            raise ValueError('Invalid position exposure')
        exposures[group] = exposures.get(group, Decimal(0)) + size
    losses, recorded_ids, last = [], set(), -1
    for row in scenarios:
        if not isinstance(row, dict) or not isinstance(row.get('scenarioId'), str) or not row['scenarioId'] or row['scenarioId'] in recorded_ids:
            raise ValueError('Missing/duplicated scenario ID')
        recorded_ids.add(row['scenarioId'])
        timestamp = integer(row['observedMs'])
        if timestamp <= last:
            raise ValueError('Scenario timestamps must advance')
        last = timestamp
        values = row.get('pnlReturnByGroup')
        if not isinstance(values,dict) or set(values) != set(exposures):
            raise ValueError('Incomplete correlated scenario vector')
        pnl = Decimal(0)
        for group, size in exposures.items():
            value = number(values[group])
            if not Decimal(-1) <= value <= Decimal(10):
                raise ValueError('Unbounded scenario payoff')
            pnl += size*value
        losses.append(-pnl)
    sorted_losses = sorted(losses)
    size=len(losses)
    # Historic loss VaR is max(0, empirical alpha quantile); ES is
    # arithmetic average of the worst ceil((1-alpha)*N) joint outcomes.
    rank=max(1, (alpha*size).to_integral_value(rounding=ROUND_CEILING))
    tail=max(1, ((1-alpha)*size).to_integral_value(rounding=ROUND_CEILING))
    var=max(Decimal(0),sorted_losses[int(rank)-1])
    es=max(Decimal(0),sum(sorted_losses[-int(tail):],Decimal(0))/tail)
    peak_loss=max(Decimal(0),sorted_losses[-1])
    total=sum(exposures.values(),Decimal(0))
    return {'schema':1,'scope':'UNQUALIFIED_CORRELATED_PORTFOLIO_SCENARIO_RISK',
            'groups':len(exposures),'positions':len(positions),'scenarioCount':size,
            'sufficientScenarioCount':size>=min_scenarios,
            'confidence':str(alpha), 'historicalVaRUsd':str(var),
            'historicalExpectedShortfallUsd':str(es),
            'worstObservedScenarioLossUsd':str(peak_loss),
            'largestCorrelatedGroupExposureUsd':str(max(exposures.values())),
            'grossAcquisitionExposureUsd':str(total),
            'groupConcentration':{g:str(v/total) for g,v in sorted(exposures.items())},
            'scenarioVectorsObservedOnSameClock':True,
            'independentOracleSettlementsVerified':False,
            'marginOrLiquidationModeled':False,
            'riskQualified':False,'decision':'NO_GO','liveAllowed':False}


def main():
    parser=argparse.ArgumentParser(description='Offline portfolio joint-scenario risk diagnostics')
    parser.add_argument('--positions',required=True)
    parser.add_argument('--scenarios',required=True)
    parser.add_argument('--confidence',default='0.95')
    parser.add_argument('--min-scenarios',type=int,default=100)
    parser.add_argument('--output',required=True)
    opts=parser.parse_args()
    positions=decode(Path(opts.positions).read_text(encoding='utf-8'))
    with Path(opts.scenarios).open(encoding='utf-8') as stream:
        scenarios=[]
        for line in stream:
            if line.strip():
                scenarios.append(decode(line))
            if len(scenarios)>100000:
                raise ValueError('Scenario count exceeded bound')
    out=measure(positions,scenarios,opts.confidence,opts.min_scenarios)
    private_write(opts.output,out)
    print(dumps(out))


if __name__=='__main__':
    main()
