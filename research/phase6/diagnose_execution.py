"""Summarize measured eligibility; no counterfactual fills or strategy qualification."""
import argparse
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path


def diagnose(report):
    rows = report.get('makerExecutionDiagnostics')
    if not isinstance(rows, list):
        raise ValueError('Matcher diagnostics missing; do not infer queue or fill eligibility')
    if len({row['id'] for row in rows}) != len(rows):
        raise ValueError('Duplicate diagnostic order IDs')
    reasons = Counter(); prints = Counter(); active = []
    queue_blocked = eligible = no_print = 0
    for row in rows:
        reasons[row['terminalReason']] += 1
        observations = row['printObservations']; prints.update(observations)
        active.append(row['activeMs'])
        count = observations.get('ELIGIBLE_PRINT', 0)
        eligible += count > 0
        no_print += not observations
        if count and Decimal(str(row['remainingShares'])) > 0:
            queue_blocked += Decimal(str(row['eligiblePrintVolume'])) <= Decimal(str(row['initialQueueAhead']))
    return {'scope': 'MEASURED_CONSERVATIVE_MATCHER_NOT_VENUE_EXECUTION',
            'orders': len(rows), 'activatedOrders': sum(row['activatedMs'] is not None for row in rows),
            'ordersWithoutSameTokenPrint': no_print, 'ordersWithEligiblePrint': eligible,
            'ordersWithEligibleVolumeNotExceedingInitialQueue': queue_blocked,
            'totalActiveOrderMs': sum(active), 'terminalReasons': dict(reasons),
            'printObservations': dict(prints), 'printCountsArePerOrder': True,
            'submittedOrders': report.get('submittedOrders'), 'fills': report.get('fills'),
            'cash': report.get('cash'), 'netRealizedPnl': report.get('netRealizedPnl'),
            'riskBreaches': report.get('riskBreaches'), 'maxDrawdown': report.get('maxDrawdown'),
            'strategyRevision': report.get('strategyRevision'), 'inputSha256': report.get('inputSha256'),
            'decision': 'NO_GO', 'liveAllowed': False}


def main():
    p = argparse.ArgumentParser(); p.add_argument('report'); p.add_argument('output'); a = p.parse_args()
    result = diagnose(json.loads(Path(a.report).read_text()))
    Path(a.output).write_text(json.dumps(result, indent=2)); print(json.dumps(result))


if __name__ == '__main__': main()
