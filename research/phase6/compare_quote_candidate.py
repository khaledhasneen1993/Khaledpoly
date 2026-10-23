"""One predeclared quote candidate on diagnostic development tapes; never qualification."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def screening(baseline, candidate):
    before = dict(baseline['configuration']); after = dict(candidate['configuration'])
    if before.pop('makerImprovementTicks', 1) != 1 or after.pop('makerImprovementTicks') != 0 or before != after:
        raise ValueError('Only the predeclared quote improvement may differ')
    if baseline.get('inputSha256') != candidate.get('inputSha256') or not baseline.get('inputSha256'):
        raise ValueError('Comparison requires identical nonempty input hashes')
    if not all(r.get('recordingClosedCleanly') for r in (baseline, candidate)):
        raise ValueError('Incomplete tape cannot be screened')
    gates = {
        'positiveNetRealizedPnl': candidate['netRealizedPnl'] > 0,
        'betterNetPnlThanBaseline': candidate['netRealizedPnl'] > baseline['netRealizedPnl'],
        'atLeastOneCompletedPair': len(candidate['pairCompletions']) > 0,
        'noResidualHoldings': all(h['shares'] == 0 for h in candidate['holdings'].values()),
        'noRiskBreaches': candidate['riskBreaches'] == 0 and not candidate['halted'],
        'drawdownWithinExistingLimit': candidate['maxDrawdown'] <= 50,
        'expiryResidualWithinExistingLimit': candidate['residualExpiryWorstCaseNotional'] <= 5,
    }
    keys = ('submittedOrders', 'fills', 'filledOrders', 'netRealizedPnl', 'cash', 'maxDrawdown',
            'riskBreaches', 'residualExpiryWorstCaseNotional', 'quantityPairCompletion', 'orderTerminalReasons')
    return {'scope': 'DEVELOPMENT_ONLY_SINGLE_CANDIDATE_SCREEN',
            'baseline': {k: baseline.get(k) for k in keys}, 'candidate': {k: candidate.get(k) for k in keys},
            'gates': gates, 'candidateWorthIndependentTest': all(gates.values()),
            'inputSha256': baseline['inputSha256'], 'decision': 'NO_GO', 'liveAllowed': False,
            'qualificationGateUnchanged': 'research/phase2/acceptance.json',
            'reason': 'Diagnostic tapes are development data; require a frozen independent baseline/stress holdout'}


def run(tape, output, expected_orders):
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    reports = {}
    for name, config in (('baseline', 'research/phase2/research-config.json'), ('candidate', 'research/phase6/quote-candidate.json')):
        subprocess.run(['java', '-Xmx2g', '-Dloader.main=com.polybot.hft.executor.replay.ClosedLoopMain',
                        '-cp', 'executor-service/target/executor-service-0.6.0.jar',
                        'org.springframework.boot.loader.launch.PropertiesLauncher', str(tape), str(output/name), config, '--raw'],
                       check=True, timeout=1500)
        reports[name] = json.loads((output/name/'report.json').read_text())
        if name == 'baseline' and (reports[name]['submittedOrders'] != expected_orders or reports[name]['fills'] != 0):
            raise ValueError('Baseline no longer reproduces known submitted orders and zero fills')
    result = screening(reports['baseline'], reports['candidate'])
    result['candidateConfigSha256'] = hashlib.sha256(Path('research/phase6/quote-candidate.json').read_bytes()).hexdigest()
    (output/'comparison.json').write_text(json.dumps(result, indent=2)); print(json.dumps(result), flush=True)


def main():
    p = argparse.ArgumentParser(); p.add_argument('--input-root', required=True); p.add_argument('--output', required=True)
    p.add_argument('--expected-baseline-orders', type=int, required=True); a = p.parse_args()
    tapes = [*Path(a.input_root).rglob('events.jsonl.gz'), *Path(a.input_root).rglob('events.jsonl')]
    if len(tapes) != 1: raise ValueError('Expected one unambiguous recorded tape')
    run(tapes[0], a.output, a.expected_baseline_orders)


if __name__ == '__main__': main()
