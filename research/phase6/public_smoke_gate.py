"""Strict CI artifact reconciliation across CEX, read-only and virtual PAPER smokes.

A green process exit alone is not acceptance: verify exact non-LIVE scopes,
uncorrupted reporting structure and replay consistency, even if Bybit blocks.
This is SOFTWARE-ONLY evidence and deliberately never promotes strategies.
"""
import argparse
import hashlib
from pathlib import Path

from research.phase3.polybot_sdk.model import decode, dumps, integer
from research.phase3.polybot_sdk.runtime import private_write

SPEC = {
    'capture': ('research/output/phase3-public/summary.json',
                'PUBLIC_INTEGRATION_SMOKE_NOT_QUALIFICATION'),
    'paper': ('research/output/phase3-public-execution/execution-verification.json',
              'PUBLIC_INTEGRATION_SMOKE_NOT_QUALIFICATION'),
    'signals': ('research/output/phase5-cex-signals.json',
                'PUBLIC_SPOT_SIGNAL_ABLATION_NOT_A_STRATEGY'),
    'forward': ('research/output/phase5-cex-forward.json',
                'PUBLIC_CEX_FORWARD_PRICE_DIAGNOSTICS'),
}
MAX_BYTES = 4 * 1024 * 1024


def _read(root, label):
    relative, scope = SPEC[label]
    path = root / relative
    if path.is_symlink() or not path.is_file():
        raise ValueError('Missing or symlinked CI artifact: ' + label)
    if not 5 <= path.stat().st_size <= MAX_BYTES:
        raise ValueError('Invalid bounded CI artifact size: ' + label)
    raw = path.read_bytes()
    item = decode(raw)
    if not isinstance(item, dict) or item.get('scope') != scope:
        raise ValueError('Unrecognized CI artifact scope: ' + label)
    if item.get('decision') != 'NO_GO' or item.get('liveAllowed') is not False:
        raise ValueError('Unqualified artifact claimed LIVE permission: ' + label)
    return item, hashlib.sha256(raw).hexdigest()


def audit(root):
    folder = Path(root).resolve()
    rows = {}
    hashes = {}
    for label in SPEC:
        item, digest = _read(folder, label)
        rows[label] = item
        hashes[label] = digest
    capture = rows['capture']
    paper = rows['paper']
    signals = rows['signals']
    forward = rows['forward']

    if (capture.get('paperExecutionMode') is not False
            or capture.get('phase4CaptureIntegrity') != 'PASS'
            or integer(capture.get('signalCollectorExit')) != 0
            or capture.get('newStrategiesExecuted') is not False
            or capture.get('observedPaperAccount') is not None
            or not isinstance(capture.get('signalRowsByVenue'), dict)
            or set(capture['signalRowsByVenue']) != {'binance-spot', 'bybit-spot'}):
        raise ValueError('Read-only PAPER/CEX capture invariants violated')
    if (paper.get('paperExecutionMode') is not True
            or paper.get('phase4CaptureIntegrity') != 'PASS'
            or integer(paper.get('signalCollectorExit')) != 0
            or paper.get('executionReplayParity') != 'MATCH_REPORT_AND_ACTION_AUDIT'
            or not isinstance(paper.get('executionReplay'), dict)
            or paper['executionReplay'].get('decision') != 'NO_GO'
            or not isinstance(paper.get('virtualExecutionReceipts'), dict)
            or not isinstance(paper.get('executionLabels'), dict)
            or not isinstance(paper.get('observedPaperAccount'), dict)):
        raise ValueError('Virtual PAPER replay/account invariants violated')

    if (signals.get('liveAllowed') is not False or
            signals.get('strategyQualified') is not False or
            signals.get('predictionQualified') is not False or
            signals.get('venueFillEvidence') is not False):
        raise ValueError('Signals falsely qualified an unverified strategy')
    if (forward.get('liveAllowed') is not False or
            forward.get('netTradeProfitabilityProven') is not False or
            forward.get('prospectivelyPreregistered') is not False or
            forward.get('dataSource') != 'PUBLIC_PRINT_NOT_EXECUTABLE_QUOTE'):
        raise ValueError('Forward public print incorrectly promoted to fill evidence')
    if not isinstance(signals.get('perVenueSymbol'), dict) or not isinstance(forward.get('perVenueStrategy'), dict):
        raise ValueError('Missing bounded source-isolated CEX diagnostics')

    return {'schema': 1, 'scope': 'PHASE6_SOFTWARE_PUBLIC_PAPER_EVIDENCE_AUDIT',
            'verifiedArtifacts': len(SPEC),
            'sha256ByArtifact': hashes,
            'cexSourceCount': len(capture['signalRowsByVenue']),
            'virtualPaperExecutionReplayParity': paper['executionReplayParity'],
            'sourceBlockOrMissingDataStillPossible': True,
            'prospectiveSevenUtcDayAuditCompleted': False,
            'genuineVenueFillsVerified': False,
            'oracleResolutionIndependentlyVerified': False,
            'strategyProfitabilityProven': False,
            'realMoneyExecutionEnabled': False, 'liveAllowed': False,
            'decision': 'NO_GO'}


def main():
    cli = argparse.ArgumentParser(description='Verify Stage-6 PUBLIC + PAPER smoke evidence')
    cli.add_argument('--root', default='.')
    cli.add_argument('--output', required=True)
    args = cli.parse_args()
    result = audit(args.root)
    private_write(args.output, result)
    print(dumps(result))


if __name__ == '__main__':
    main()
