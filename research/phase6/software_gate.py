"""Fail-closed engineering-only software release inventory.

CI runs this LAST after Java/Python verification. It cannot certify the
prospective seven-day source coverage, real venue fills, oracle decisions,
economic profits, or funded/real-world execution.
"""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess

from research.phase3.polybot_sdk.model import dumps
from research.phase3.polybot_sdk.runtime import private_write

REQUIRED = (
    'research/phase4/recorder.py', 'research/phase4/audit.py',
    'research/phase4/capture_supervisor.py', 'research/phase4/tests/test_capture_supervisor.py',
    'research/phase4/final_gate.py',
    'research/phase5/cex_signals.py', 'research/phase5/cex_forward.py',
    'research/phase5/event_rules.py', 'research/phase5/paper_strategy_adapter.py',
    'research/phase5/fill_research.py', 'research/phase5/portfolio_risk.py',
    'research/phase5/walk_forward.py',
    'research/phase6/sdk.py', 'research/phase6/external_strategy.py',
    'research/phase6/cross_account_gate.py',
    'research/phase6/paper_screen_bridge.py',
    'research/phase6/virtual_paper_bridge.py',
    'research/phase6/polygon_costs.py',
    'polybot-core/src/main/java/com/polybot/hft/risk/AccountLedger.java',
    'polybot-core/src/main/java/com/polybot/hft/paper/ResearchProposalInbox.java',
    'executor-service/src/main/java/com/polybot/hft/executor/web/ResearchProposalController.java',
    'polybot-core/src/test/java/com/polybot/hft/risk/AccountLedgerConcurrencyTest.java',
    'polybot-core/src/test/java/com/polybot/hft/risk/AccountLedgerAccountingStressTest.java',
    'polybot-core/src/test/java/com/polybot/hft/risk/AccountLedgerPerformanceBaselineTest.java',
    'research/phase5/tests/test_paper_strategy_adapter.py',
    'research/phase6/tests/test_virtual_paper_bridge.py',
    'research/phase6/tests/test_sdk.py',
    '.github/workflows/verify.yml','pyproject.toml',
)

def inventory(directory, *, expected_revision=None, ci_context=False):
    root=Path(directory).resolve()
    if not root.is_dir():
        raise ValueError('Project root not available')
    digest={}
    missing=[]
    for rel in REQUIRED:
        path=root/rel
        if not path.is_file() or path.is_symlink() or path.stat().st_size<10:
            missing.append(rel)
        else:
            digest[rel]=hashlib.sha256(path.read_bytes()).hexdigest()
    revision=None
    try:
        revision=subprocess.run(['git','rev-parse','HEAD'],cwd=root,check=True,
                                stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                text=True,timeout=10).stdout.strip()
    except (subprocess.SubprocessError,OSError):
        pass
    exact_revision=expected_revision is not None and revision==expected_revision
    checks_reached=bool(ci_context and exact_revision and not missing)
    return {'schema':1,'scope':'SOFTWARE_ONLY_PAPER_RESEARCH_ACCEPTANCE_MANIFEST',
            'revision':revision,'expectedRevisionMatched':exact_revision,
            'componentFilesChecked':len(REQUIRED),'present':len(digest),
            'missing':missing,'sha256ByComponent':digest,
            'reachedAfterConfiguredCiTestSteps':checks_reached,
            'engineeringArtifactsPresent':not missing,
            'softwareReviewCandidate':checks_reached,
            'untrustedExternalStrategyCodeExecuted':False,
            'sevenFullUtcDaysMarketCaptureVerified':False,
            'venueFillAndQueueModelVerified':False,
            'bybitReachabilityVerified':False,
            'oracleAndNegativeRiskTerminalEvidenceVerified':False,
            'prospectiveIndependentHoldoutVerified':False,
            'realMoneyExecutionPermitted':False,
            'liveAllowed':False,'decision':'NO_GO'}


def main():
    parser=argparse.ArgumentParser(description='Offline software-only PAPER acceptance manifest')
    parser.add_argument('--root',default='.')
    parser.add_argument('--output',required=True)
    p=parser.parse_args()
    # Workflow runs this last; local calls cannot impersonate build proof.
    ci=(os.environ.get('GITHUB_ACTIONS')=='true' and
        os.environ.get('CI')=='true' and
        os.environ.get('GITHUB_WORKFLOW')=='Polybot verification')
    result=inventory(p.root,expected_revision=os.environ.get('GITHUB_SHA'),
                     ci_context=ci)
    private_write(p.output,result)
    print(dumps({'revision':result['revision'],'scope':result['scope'],
                 'engineeringArtifactsPresent':result['engineeringArtifactsPresent'],
                 'softwareReviewCandidate':result['softwareReviewCandidate'],
                 'decision':'NO_GO','liveAllowed':False,
                 'missing':result['missing']}))
    if result['missing'] or (ci and not result['softwareReviewCandidate']):
        raise SystemExit('Engineering artifact/revision gate FAILED')


if __name__=='__main__':
    main()
