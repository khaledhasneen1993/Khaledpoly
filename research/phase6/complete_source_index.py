"""Complete original identity index; NOT settlement labels or skip authority.

Reconstructs the exact retained census, with no RPC, capture or execution.
The strict Python consumer is a reference contract, not wired to the engine.
"""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re

from research.phase6.full_tape_coverage_result import (
    ROOT, IDENTITY_FIELDS, MISSING, canonical, read_archive, verify,
)

COUNT = 16317
SOURCE_SHA = 'cd850df52d7f9994526603130f2942008f8f49ba80495d82b70dea66f0dc6d8b'
IDENTITIES_SHA = '1f8d1d953f3755b8244c7ac11f7a3f72ccd8d73b1c9807b7cec417b6b710c1c2'
FREEZE_SHA = '60fd2d3307b4fce9e01facd1cbbeabcb5950ef79bc20b004a353697bc3edcd6e'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def validate_rows(rows, report):
    """Check ALL observations jointly, including previously bound transactions."""
    if (report['logicalTapeSha256'] != SOURCE_SHA
            or report['allObservationIdentitiesSha256'] != IDENTITIES_SHA
            or report['normalizedTradeObservations'] != COUNT or len(rows) != COUNT):
        raise ValueError('Incomplete/changed original source index')
    previous = (-1, -1)
    last_at = -1
    txs, public_ids = set(), set()
    hasher = hashlib.sha256()
    for row in rows:
        if set(row) != IDENTITY_FIELDS:
            raise ValueError('Changed identity schema')
        if any(type(row[k]) is not int or row[k] < 0
               for k in ('seq', 'eventIndex', 'at', 'sourceMs')):
            raise ValueError('Invalid source coordinates/clocks')
        key = (row['seq'], row['eventIndex'])
        tx, public_id = row['transactionHash'], row['publicTradeIdSha256']
        if (key <= previous or not 1 <= row['seq'] < report['sourceRows']
                or row['at'] < last_at or not report['startMs'] <= row['at'] <= report['endMs']):
            raise ValueError('Duplicate/out-of-order source coordinates/clock')
        if (not isinstance(tx, str) or re.fullmatch('0x[0-9a-f]{64}', tx) is None
                or not isinstance(public_id, str) or re.fullmatch('[0-9a-f]{64}', public_id) is None):
            raise ValueError('Missing/malformed original transaction/public identity')
        if tx in txs or public_id in public_ids:
            raise ValueError('Global transaction/public identity reuse')
        if (not isinstance(row['token'], str) or not row['token'].isdigit()
                or not isinstance(row['condition'], str)
                or re.fullmatch('0x[0-9a-f]{64}', row['condition']) is None
                or row['side'] not in ('BUY', 'SELL')
                or row['coverage'] not in MISSING | {'BOUND_CONSERVED_GROUP'}):
            raise ValueError('Invalid original market/classification')
        for name in ('price', 'size'):
            value = Decimal(str(row[name]))
            if not value.is_finite() or value <= 0 or name == 'price' and value >= 1:
                raise ValueError('Invalid original price/size')
        txs.add(tx)
        public_ids.add(public_id)
        previous, last_at = key, row['at']
        hasher.update(canonical(row))
    if hasher.hexdigest() != IDENTITIES_SHA:
        raise ValueError('Changed exact original identity bytes')
    return dict(observations=len(rows), uniqueTransactions=len(txs),
                uniquePublicTradeIds=len(public_ids), globalIdentityReuse=False,
                identitiesSha256=hasher.hexdigest())


def reconstruct():
    from research.phase6.mixed_replay_labels import export
    labels = export()
    freeze_path = Path('research/phase6/full-tape-coverage-freeze.json')
    if digest(freeze_path.read_bytes()) != FREEZE_SHA:
        raise ValueError('Changed original coverage freeze')
    frozen = json.loads(freeze_path.read_bytes())
    report, compressed, _ = read_archive(ROOT / 'artifact.zip')
    inspection = json.loads(Path(frozen['referenceInspection']).read_bytes())
    proof, missing, _ = verify(report, compressed, labels, inspection, frozen,
                               digest(freeze_path.read_bytes()))
    conditions = [k for k, v in report['coverageByCondition'].items()
                  if v.get('BOUND_CONSERVED_GROUP')]
    if len(conditions) != 1:
        raise ValueError('Original bound condition differs')
    rows = list(missing)
    for binding in labels['bindings']:
        row = {k: binding[k] for k in IDENTITY_FIELDS - {'condition', 'coverage'}}
        row.update(condition=conditions[0], coverage='BOUND_CONSERVED_GROUP')
        rows.append(row)
    rows.sort(key=lambda r: (r['seq'], r['eventIndex']))
    index_proof = validate_rows(rows, report)
    if index_proof['identitiesSha256'] != proof['allObservationIdentitiesSha256']:
        raise ValueError('Prior independent census differs')
    return rows, report, index_proof


class SourceIdentityIndex:
    """Single-pass fail-closed reference consumer; never returns execution labels.

    Full mode requires the immediate next original identity. Subset mode only
    tests retained raw preimages and cannot prove full-source consumption.
    Failures permanently poison the instance, including incomplete finalization.
    """
    def __init__(self, rows, report, *, subset=False):
        self.proof = validate_rows(rows, report)
        # Own canonical copies: callers cannot mutate identities after validation.
        self._rows = tuple(json.loads(canonical(r)) for r in rows)
        self._keys = {(r['seq'], r['eventIndex']): i for i, r in enumerate(self._rows)}
        self._subset = subset
        if type(subset) is not bool:
            raise ValueError('Explicit boolean consumption scope required')
        self._last = -1
        self._consumed = 0
        self._failed = False

    def consume(self, seq, index, at, data):
        if self._failed:
            raise ValueError('Source identity index is poisoned')
        try:
            if any(type(v) is not int for v in (seq, index, at, data['sourceMs'])):
                raise ValueError('Exact integer source coordinates/clocks required')
            position = self._keys.get((seq, index))
            if position is None or position <= self._last:
                raise ValueError('Unknown/duplicate/out-of-order original observation')
            if not self._subset and position != self._last + 1:
                raise ValueError('Missing original observation before current input')
            row = self._rows[position]
            raw = data['tradeId']
            if not isinstance(raw, str) or len(raw.encode()) > 1024 * 1024:
                raise ValueError('Invalid bounded original trade bytes')
            if (at != row['at'] or data['sourceMs'] != row['sourceMs']
                    or any(data[k] != row[k] for k in ('token', 'side'))
                    or any(Decimal(str(data[k])) != Decimal(str(row[k])) for k in ('price', 'size'))
                    or digest(raw.encode()) != row['publicTradeIdSha256']
                    or json.loads(raw)['transaction_hash'] != row['transactionHash']):
                raise ValueError('Actual original identity/preimage differs')
            self._last = position
            self._consumed += 1
            # Return identity facts only. Coverage is historical, not execution permission.
            return dict(row)
        except Exception as error:
            self._failed = True
            raise ValueError('Fail-closed source identity verification') from error

    def require_complete(self):
        if self._failed or self._subset or self._consumed != COUNT:
            self._failed = True
            raise ValueError('Incomplete original source consumption; no full replay proof')

    def report(self):
        return dict(self.proof, consumedOriginalPreimages=self._consumed,
                    subsetPreimageTestOnly=self._subset, failed=self._failed,
                    completeOriginalConsumption=(not self._failed and not self._subset
                                                 and self._consumed == COUNT),
                    settlementRoutesValidatedByIndex=False, runtimeSkipAuthorized=False)


def evidence():
    from research.phase6.expanded_receipt_pool import build, identities
    rows, source, proof = reconstruct()
    consumer = SourceIdentityIndex(rows, source, subset=True)
    actual = identities(build())['observations']
    for observation in actual:
        consumer.consume(observation['seq'], observation['eventIndex'],
                         observation['at'], observation['data'])
    if len(actual) != 643:
        raise ValueError('Require all available643 original preimages')
    result = dict(scope='COMPLETE_CENSUS_INDEX_WITH_PARTIAL_RAW_PREIMAGE_PROOF_NOT_EXECUTION',
                  logicalTapeSha256=SOURCE_SHA, index=proof, preimages=consumer.report(),
                  unknownPreimagesNotInvented=COUNT-len(actual), newPublicReads=0,
                  originalTapeRescanned=False, runtimeOptimizationImplemented=False,
                  atomicSessionGuardImplemented=False, marketNetPnlRecomputed=False,
                  fullAccountReplayAuthorized=False, independentPaperQualificationAllowed=False,
                  liveAllowed=False, decision='NO_GO')
    try:
        consumer.require_complete()
    except ValueError:
        result['partialPreimagesCorrectlyRejectedAsFullConsumption'] = True
    else:
        raise ValueError('Subset must not certify full original consumption')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = (json.dumps(evidence(), indent=2) + '\n').encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists() and args.output.read_bytes() != result:
        raise ValueError('Refuse to replace different retained identity proof')
    args.output.write_bytes(result)
    print(result.decode(), end='')
