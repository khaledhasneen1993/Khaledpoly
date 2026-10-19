"""One fixed fee-positive first-exit candidate, research only; no extra parameters."""
import argparse
import hashlib
import json
from pathlib import Path
from research.phase6.queue_aware_recovery_exit import prepare as baseline


def prepare():
    r=baseline()
    return dict(**{k:v for k,v in r.items() if k!='scope'},
        scope='CONDITIONAL_FEE_POSITIVE_FIRST_EXIT_CANDIDATE_NOT_FULL_ACCOUNT',
        candidateRule='WHEN_NO_OPEN_ORDER_AND_NOT_OVERDUE_TAKE_ARGMAX_COMPLETE_SELL_IF_NET_PER_SHARE_GE_ORIGINAL_MINIMUM_EDGE',
        executionNetEdgeMustBeRechecked=True,baselineAndCandidateUseIdenticalConditionalStateAndSource=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
    f=json.loads(Path('research/phase6/queue-aware-fee-positive-exit-freeze.json').read_text())
    for path,sha in f['filesSha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=sha:raise ValueError('Frozen fee-positive input changed '+path)
    r=prepare();p=Path(a.output);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps(dict(scope=r['scope'],minimumEdge=r['config']['minimumEdge'],bindings=len(r['bindings']),newPublicReads=0)))


if __name__=='__main__':main()
