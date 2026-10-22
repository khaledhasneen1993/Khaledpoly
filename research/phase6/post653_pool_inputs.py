"""Materialize complete source index plus frozen exact655 pool for one replay."""
import argparse
import json
from pathlib import Path

from research.phase6.post653_receipt_pool import build,identities,canonical
from research.phase6.source_lag_guard_inputs import prepare as prefix


def prepare(output):
    result=prefix(output);out=Path(output);pool=build();pool_raw=canonical(pool);source_raw=canonical(identities(pool))
    (out/'pool/pool.json').write_bytes(pool_raw);(out/'pool/source-identities.json').write_bytes(source_raw)
    summary=dict(scope='COMPLETE_SOURCE_INDEX_WITH_EXACT655_PARTIAL_POOL_NOT_TAPE',prefix=result,
        poolBindings=655,actualComponents=1557,completeSourceIdentities=16317,
        originalTapeReplayed=False,marketNetPnlRecomputed=False,liveAllowed=False)
    (out/'post653-pool-inputs.json').write_text(json.dumps(summary,indent=2)+'\n');return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();print(json.dumps(prepare(a.output),indent=2))
