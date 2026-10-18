"""Re-screen existing complete DEVELOPMENT census; no tape replay, RPC or executions."""
from collections import Counter
from decimal import Decimal, localcontext
import argparse
import hashlib
import json
from pathlib import Path
from research.phase6.residual_entry_risk import assess

BASE = Path('research/experiments/transaction-linked-census-20261018')
ORDERS = Path('research/experiments/residual-entry-risk-20261018/result/only-pair-diagnostic.json')


def recover_quantity(row, config):
    # Quantity was not exported by the old census. Reproduce its exact Decimal
    # expression on EVERY lawful .01 size up to the frozen cap; require a unique
    # solution. This is census quantity recovery, NOT recovered market metadata.
    with localcontext() as ctx:
        ctx.prec = 28
        cost = Decimal(config['mergeCost']); cap = Decimal(config['orderShares'])
        if not 0 < cost or not 0 < cap <= 100:
            raise ValueError('Need positive cost and bounded quantity grid')
        edge = 1-Decimal(row['printPrice'])-Decimal(row['otherQuote'])
        observed = Decimal(row['netEdgeUpperBound'])
        matches = [Decimal(i)/100 for i in range(1, int(cap*100)+1)
                   if (edge*(Decimal(i)/100)-cost)/(Decimal(i)/100) == observed]
    if len(matches) != 1:
        raise ValueError('Census quantity absent/ambiguous; never default optimistically')
    return matches[0]


def screen(census, config, orders=None):
    if (census['examplesTruncated'] or not census['recordingClosedCleanly']
            or census['fillsInferred'] or census['pnlInferred']):
        raise ValueError('Require complete clean no-fill census')
    counted = Counter((str(r['improvementTicks']), r['route']) for r in census['examples'])
    for policy in ('0', '1'):
        for route, key in [('DIRECT_SELL', 'policyCounts'), ('COMPLEMENT_BUY_CANDIDATE', 'complementBuyCandidateCounts')]:
            if counted[policy, route] != census[key][policy].get('NECESSARY_CONDITIONS_ONLY', 0):
                raise ValueError('Census examples/counts mismatch')
    if sum(counted.values()) != sum(counted[p,r] for p in ('0','1') for r in ('DIRECT_SELL','COMPLEMENT_BUY_CANDIDATE')):
        raise ValueError('Unknown policy/route')
    counts = Counter(); passed = []; quantities = Counter()
    for row in census['examples']:
        q = recover_quantity(row, config); quantities[str(q)] += 1
        risk = assess(q, row['printPrice'], row['otherQuote'], config['maxExitLoss'], config['redemptionCost'], enabled=True)
        counts[str(row['improvementTicks']), row['route'], risk['allow']] += 1
        if not risk['allow']:
            continue
        item = dict(row, recoveredCensusQuantity=str(q), worstCaseUnpairedLoss=risk['worstCaseUnpairedLoss'],
                    availableBudgetAssumption='FULL_UNUSED_FROZEN_EXIT_BUDGET_UPPER_BOUND', marketMetadataRecovered=False)
        if orders is not None:
            same = [o for o in orders if o['token'] == row['token'] and o['buy']
                    and Decimal(str(o['price'])) == Decimal(row['printPrice'])]
            active = [o for o in same if o['activatedMs'] <= row['sourceMs'] <= row['at'] <= o['terminalMs']]
            item['actualLegacyGuardMatchingActiveOrderIds'] = [o['id'] for o in active]
            item['actualLegacyGuardOrderLifeVerified'] = True
        passed.append(item)
    return dict(logicalTapeSha256=census['logicalTapeSha256'], sourceRows=census['rows'],
        completeNecessaryExamples=len(census['examples']), recoveredCensusQuantityCounts=dict(quantities),
        counts=[dict(policy=p, route=r, passesWorstCaseRisk=b, observations=n)
                for (p,r,b),n in sorted(counts.items())], riskAdmissibleExamples=passed,
        riskAdmissibleExamplesAreNotUniqueTrades=True, complementRouteNotReceiptVerified=True,
        actualEntryDecisionStateReconstructed=False, actualLegacyGuardOrderLifeVerified=orders is not None)


def attach_historical_qb0(result, report, config):
    if (report['rows'] != result['sourceRows'] or not report['recordingClosedCleanly']
            or report['configuration']['makerImprovementTicks'] != 0
            or any(Decimal(str(report['configuration'][k])) != Decimal(str(v)) for k,v in config.items())):
        raise ValueError('Wrong historical QB0 dataset/configuration')
    for row in result['riskAdmissibleExamples']:
        if row['improvementTicks'] != 0:
            continue
        same = [o for o in report['makerExecutionDiagnostics'] if o['token'] == row['token'] and o['buy']
                and Decimal(str(o['price'])) == Decimal(row['printPrice'])]
        submitted = [o for o in same if o['submittedMs'] <= row['at'] <= o['terminalMs']]
        active = [o for o in submitted if o['activatedMs'] is not None
                  and o['activatedMs'] <= row['sourceMs'] <= row['at'] <= o['terminalMs']]
        row['historicalUnguardedQb0MatchingSubmittedOrderIds'] = [o['id'] for o in submitted]
        row['historicalUnguardedQb0MatchingActiveOrderIds'] = [o['id'] for o in active]
    result['historicalUnguardedQb0LifeComparedNotCombinedGuardReplay'] = True


def build():
    freeze = json.loads(Path('research/phase6/risk-feasible-census-freeze.json').read_text())
    for path, expected in freeze['filesSha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected:
            raise ValueError('Frozen development screen changed: '+path)
    config = json.loads(Path('research/phase2/research-config.json').read_text())
    original = screen(json.loads((BASE/'original.json').read_text()), config)
    fresh = screen(json.loads((BASE/'fresh.json').read_text()), config,
                   json.loads(ORDERS.read_text())['makerExecutionDiagnostics'])
    for name, result in [('original', original), ('fresh', fresh)]:
        report = json.loads(Path('research/experiments/quote-qb0-20261018/'+name+'-candidate-report.json').read_text())
        attach_historical_qb0(result, report, config)
    return dict(scope='COMPLETE_SAVED_CENSUS_RISK_FEASIBILITY_UPPER_BOUND_NOT_EXECUTION',
        variantsAlreadyTested=['LEGACY_IMPROVE_1', 'REJECTED_QB0_JOIN_0'],
        original=original, fresh=fresh, fillsCreated=0, netPnlRecomputed=False,
        parameterSearchPerformed=False, independentPaperQualificationAllowed=False,
        combinedQb0PlusRiskGuardAccountNeverTested=True,
        runtimeChanges=False, liveAllowed=False, decision='NO_GO',
        omittedConstraints=['actual metadata/minimum at decision', 'dynamic risk premium',
            'decision timing', 'activation', 'queue', 'settlement route confirmation', 'GAP cancellation',
            'already used account exit-loss budget'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output', required=True); args = parser.parse_args()
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(build(), indent=2)+'\n')
