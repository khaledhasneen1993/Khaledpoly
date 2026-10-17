"""Explicit virtual-order adapter to the coordinated PAPER engine. No venue client exists here."""
import hashlib
import os
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request
import uuid
from .client import PaperClient
from .model import decode, dumps, validate
from .features import FeatureStore
from .feature_tail import FeatureTail
from .strategy import evaluate
from .runtime import implementation_hash, private_write


class PaperExecutionClient(PaperClient):
    def submit(self, observation, strategy, legs, client_id):
        obs = validate(observation)
        if obs.get('paperExecutionEnabled') is not True:
            raise ValueError('Executor has not enabled virtual PAPER order admission')
        proposal = {'id': client_id, 'strategy': strategy, 'sessionId': obs['sessionId'],
                    'accountId': obs['account']['id'], 'sequence': obs['sequence'], 'legs': legs}
        return self.retry_identical(proposal)

    def retry_identical(self, proposal):
        # Only retry this exact payload after an unknown HTTP outcome; never invent a new id.
        request = Request(self._url.rsplit('/', 1)[0] + '/proposals/paper', data=dumps(proposal).encode(),
                          headers={'X-Polybot-Token': self._token, 'Content-Type': 'application/json'}, method='POST')
        try:
            response = self._opener.open(request, timeout=self._timeout)
        except HTTPError as exc:
            if exc.code != 409:
                raise
            response = exc
        with response:
            raw = response.read(65537)
        if len(raw) > 65536:
            raise ValueError('Oversized PAPER receipt')
        result = decode(raw)
        if (result.get('virtualOnly') is not True or result.get('liveAllowed') is not False
                or result.get('executionEnabled') is not False or result.get('id') != proposal['id']
                or result.get('status') not in ('PAPER_SUBMITTED', 'PAPER_ALREADY_RECORDED', 'PAPER_REJECTED')):
            raise ValueError('Invalid virtual-order receipt')
        return result


    def settle_group(self, event_id):
        import re
        if not re.fullmatch('[0-9]{1,24}', event_id):
            raise ValueError('Invalid terminal event id')
        request = Request(self._url.rsplit('/', 1)[0] + '/proposals/settle-paper-group',
                          data=dumps({'eventId': event_id}).encode(),
                          headers={'X-Polybot-Token': self._token, 'Content-Type': 'application/json'}, method='POST')
        with self._opener.open(request, timeout=self._timeout) as response:
            raw = response.read(65537)
        if len(raw) > 65536:
            raise ValueError('Oversized terminal receipt')
        result = decode(raw)
        if (result.get('virtualOnly') is not True or result.get('liveAllowed') is not False
                or result.get('executionEnabled') is not False
                or result.get('id') != 'settle:' + event_id
                or result.get('status') not in ('PAPER_GROUP_REDEEMED', 'PAPER_GROUP_ALREADY_REDEEMED', 'PAPER_GROUP_DEFERRED')):
            raise ValueError('Invalid virtual settlement receipt')
        return result


def execution_groups(row):
    if row['strategy'] == 'inventory-mm-shadow':
        markets = {}
        for leg in row['allocation']['admitted']:
            markets.setdefault(leg['condition'], []).append(leg)
        return list(markets.values())
    return [proposal['legs'] for proposal in row['allocation']['admitted']]


def execute_paper(client, directory, seconds=60, interval=1, strategy='inventory-mm-shadow', feature_path=None):
    if not 0 < seconds <= 86400 or not .25 <= interval <= 60:
        raise ValueError('Invalid PAPER run duration/interval')
    path = Path(directory)
    path.mkdir(mode=0o700, parents=True, exist_ok=False)
    private_write(path / 'manifest.json', {'mode': 'PAPER_EXECUTION', 'implementationHash': implementation_hash(),
                  'strategy': strategy, 'seconds': str(seconds), 'interval': str(interval), 'venueOrders': False,
                  'liveAllowed': False})
    store, tail = FeatureStore(), FeatureTail(feature_path) if feature_path else None
    deadline, counts, complete, previous = time.monotonic() + seconds, {}, False, None
    digest = hashlib.sha256()
    last_snapshot = None
    try:
        with (path / 'execution.jsonl').open('x') as output:
            os.chmod(path / 'execution.jsonl', 0o600)
            def append(record):
                encoded = (dumps(record) + '\n').encode()
                output.write(encoded.decode())
                output.flush()
                os.fsync(output.fileno())
                digest.update(encoded)
            while time.monotonic() < deadline:
                if tail:
                    tail.update(store)
                snapshot = client.snapshot()
                last_snapshot = snapshot
                identity = snapshot['sessionId'], int(snapshot['sequence'])
                if identity != previous:
                    evidence = [r.record() for r in store.available(int(snapshot['generatedMs']))]
                    row = evaluate(snapshot, strategy=strategy, feature_evidence=evidence)
                    receipts = []
                    # A fresh observation is needed after every submitted group: other orders consume cash.
                    for legs in execution_groups(row):
                        current = client.snapshot()
                        current_evidence = [r.record() for r in store.available(int(current['generatedMs']))]
                        fresh = evaluate(current, strategy=strategy, feature_evidence=current_evidence)
                        signature = {(x['condition'], x['token'], x['buy']) for x in legs}
                        legs = next((group for group in execution_groups(fresh)
                                     if {(x['condition'], x['token'], x['buy']) for x in group} == signature), None)
                        if legs is None:
                            continue
                        client_id = 'paper-' + uuid.uuid4().hex
                        proposal = {'id': client_id, 'strategy': strategy, 'sessionId': current['sessionId'],
                                    'accountId': current['account']['id'], 'sequence': current['sequence'], 'legs': legs}
                        if current.get('paperExecutionEnabled') is not True:
                            raise ValueError('PAPER execution mode is not active')
                        proposal = decode(dumps(proposal))
                        append({'kind': 'PAPER_REQUEST', 'proposal': proposal,
                                'proposalSha256': hashlib.sha256(dumps(proposal).encode()).hexdigest()})
                        try:
                            receipt = client.retry_identical(proposal)
                        except HTTPError:
                            raise
                        except (URLError, TimeoutError):
                            # At most one identical retry; a lost response never creates a fresh order id.
                            receipt = client.retry_identical(proposal)
                        append({'kind': 'PAPER_RECEIPT', 'receipt': receipt})
                        receipts.append(receipt)
                        counts[receipt['status']] = counts.get(receipt['status'], 0) + 1
                    record = {'kind': 'PAPER_DECISION', 'observation': snapshot, 'featureEvidence': evidence, 'proposalReceipts': receipts}
                    append(record)
                    previous = identity
                remaining = deadline - time.monotonic()
                if remaining > 0:
                    time.sleep(min(interval, remaining))
        complete = True
    finally:
        private_write(path / 'report.json', {'complete': complete, 'receipts': counts,
                      'executionTapeSha256': digest.hexdigest(), 'venueOrders': False, 'liveAllowed': False,
                      'decision': 'NO_GO', 'pnlSource': 'Executor ledger and print-driven replay only',
                      'lastObservedAccount': last_snapshot['account'] if last_snapshot else None,
                      'accountObservedMs': last_snapshot['generatedMs'] if last_snapshot else None})
    return {'complete': complete, 'receipts': counts, 'liveAllowed': False, 'decision': 'NO_GO'}


def reconcile_paper(client, directory, output):
    """Resolve unknown POST outcomes using the persisted id and identical bytes/fields."""
    path = Path(directory)
    manifest = decode((path / 'manifest.json').read_text())
    if manifest.get('mode') != 'PAPER_EXECUTION' or manifest.get('liveAllowed') is not False:
        raise ValueError('Not a virtual execution run')
    if Path(output).exists():
        raise FileExistsError('Reconciliation output must be new')
    report_path = path / 'report.json'
    if report_path.exists():
        report = decode(report_path.read_text())
        digest = hashlib.sha256()
        with (path / 'execution.jsonl').open('rb') as raw:
            for block in iter(lambda: raw.read(65536), b''):
                digest.update(block)
        if digest.hexdigest() != report['executionTapeSha256']:
            raise ValueError('Outbox checksum mismatch')
    pending = {}
    with (path / 'execution.jsonl').open() as stream:
        for line in stream:
            row = decode(line)
            if row['kind'] == 'PAPER_REQUEST':
                request = row['proposal']
                if row['proposalSha256'] != hashlib.sha256(dumps(request).encode()).hexdigest():
                    raise ValueError('Outbox request checksum mismatch')
                if request['id'] in pending and dumps(pending[request['id']]) != dumps(request):
                    raise ValueError('Outbox id conflict')
                pending[request['id']] = request
            elif row['kind'] == 'PAPER_RECEIPT':
                pending.pop(row['receipt']['id'], None)
    receipts = [client.retry_identical(request) for _, request in sorted(pending.items())]
    result = {'reconciledReceipts': receipts, 'newIdsCreated': 0, 'venueOrders': False, 'liveAllowed': False}
    private_write(output, result)
    return result
