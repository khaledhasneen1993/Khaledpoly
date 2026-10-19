"""Same-state DEVELOPMENT exit comparison; never full-account/holdout qualification."""
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
from research.phase6.queue_aware_causal import QROOT
from research.phase6.queue_aware_recovery_exit import prepare as baseline_input
from research.phase6.queue_aware_fee_positive_exit import prepare as candidate_input
from research.phase6.queue_aware_first_exit_result import saved as baseline_result
from research.phase6.queue_aware_fee_positive_result import saved as candidate_result

FREEZE=Path('research/phase6/queue-aware-fee-positive-exit-freeze.json')
EXTRA={'candidateRule','executionNetEdgeMustBeRechecked','baselineAndCandidateUseIdenticalConditionalStateAndSource'}


def identical_inputs(base,candidate):
    if set(candidate)-set(base)!=EXTRA or set(base)-set(candidate):raise ValueError('Unexpected candidate input surface')
    if any(base[k]!=candidate[k] for k in base if k!='scope'):raise ValueError('Baseline/candidate source, state or costs differ')
    if not candidate['executionNetEdgeMustBeRechecked'] or not candidate['baselineAndCandidateUseIdenticalConditionalStateAndSource']:raise ValueError('Changed execution/same-source contract')


def compare():
    freeze=json.loads(FREEZE.read_text())
    for path,sha in freeze['filesSha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=sha:raise ValueError('Frozen file changed '+path)
    base=baseline_input();candidate=candidate_input();identical_inputs(base,candidate)
    if candidate['candidateRule']!=freeze['candidateRule'] or candidate['scope']!=freeze['scope']:raise ValueError('Changed frozen candidate rule')
    b=baseline_result();c=candidate_result()
    bnet=D(b['conditionalRoundTripNetAfterCosts']);cnet=D(c['conditionalRoundTripNetAfterCosts'])
    if bnet!=D(freeze['baselineConditionalNetAfterCosts']):raise ValueError('Changed retained baseline')
    return dict(scope='SAME_STATE_SELECTED_DEVELOPMENT_FIRST_EXIT_COMPONENT_ONLY',
        candidateFrozenBeforeEvaluationCommit='1b1ae2bfcd7d8981d5e9c70cbc0a1a7170925102',
        candidateFreezeSha256=hashlib.sha256(FREEZE.read_bytes()).hexdigest(),
        logicalDevelopmentTapeSha256='cd850df52d7f9994526603130f2942008f8f49ba80495d82b70dea66f0dc6d8b',
        retainedContextSha256='69bdd106567b5730fdff368bcbd39446164187ae2499912cfa26191925ba96cf',
        baselineRunId=39287345589,candidateRunId=39296060855,
        inputEquality='ALL_INPUT_FIELDS_IDENTICAL_EXCEPT_SCOPE_AND_EXPLICIT_FROZEN_RULE_FIELDS',
        frozenConditionalBasis='2.40',conditionalShares='5',
        baseline=b,candidate=c,conditionalNetImprovement=str(cnet-bnet),
        selectionBias='ONE_PREVIOUSLY_SELECTED_DEVELOPMENT_POSITION; NOT_AN_UNBIASED_STRATEGY_SAMPLE',
        feesGasAndQueueUnchanged=True,newPublicReads=0,newFullSourceScans=0,
        fullAccountPnl=None,readiness='NO_GO',
        blockers=['QW0 entry and fee-positive exit are research probes, not integrated canonical ResearchSession policies',
            'Full account baseline/candidate replay including all orders, cash, inventory, merges, re-entry and account risk is missing',
            'Existing canonical settlement-label adapter is limited to BUY public takers; mixed-side receipt coverage needs safe integration',
            'Frozen independent multi-market PAPER and unchanged acceptance criteria remain untested for this candidate'],
        candidateAccountSimulated=False,holdoutInspected=False,independentPaperQualificationAllowed=False,liveAllowed=False)


if __name__=='__main__':print(json.dumps(compare(),indent=2))
