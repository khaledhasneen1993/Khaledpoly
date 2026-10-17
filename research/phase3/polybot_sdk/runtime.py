"""Private append-only shadow recordings and exact deterministic replay."""
import hashlib
import math
import os
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from .model import decode, dumps, validate
from .strategy import evaluate


def implementation_hash():
    digest = hashlib.sha256()
    for p in sorted(Path(__file__).parent.glob('*.py')):
        digest.update(p.name.encode())
        digest.update(p.read_bytes())
    return digest.hexdigest()


def private_write(path, data):
    with open(path, 'x', encoding='utf-8') as output:
        os.chmod(path, 0o600)
        output.write(dumps(data) + '\n')
        output.flush()
        os.fsync(output.fileno())


def shadow_run(client, directory, seconds=60, interval=1, groups=None):
    if not math.isfinite(seconds) or not 0 < seconds <= 86400 or not math.isfinite(interval) or not .25 <= interval <= 60:
        raise ValueError('Invalid shadow duration or sampling interval')
    path = Path(directory)
    path.mkdir(mode=0o700, parents=True, exist_ok=False)
    configuration = {'strategy': 'inventory-mm-shadow', 'groups': groups or {}, 'seconds': str(seconds), 'interval': str(interval)}
    manifest = {'schema': 1, 'mode': 'SHADOW', 'implementationHash': implementation_hash(),
                'configuration': configuration, 'configurationHash': hashlib.sha256(dumps(configuration).encode()).hexdigest(),
                'researchOnly': True, 'executionEnabled': False, 'liveAllowed': False}
    private_write(path / 'manifest.json', manifest)
    count, errors, previous, identity, complete = 0, 0, None, None, False
    deadline = time.monotonic() + seconds
    digest = hashlib.sha256()
    try:
        with open(path / 'observations.jsonl', 'x', encoding='utf-8') as tape:
            os.chmod(path / 'observations.jsonl', 0o600)
            while time.monotonic() < deadline:
                delay = interval
                try:
                    snapshot = client.snapshot()
                    current = (snapshot['sessionId'], snapshot['account']['id'])
                    sequence = int(snapshot['sequence'])
                    if identity and (current != identity or sequence < previous):
                        raise ValueError('Session or account changed, or sequence regressed')
                    if previous is None or sequence > previous:
                        row = evaluate(snapshot, groups)
                        encoded = (dumps(row) + '\n').encode()
                        tape.write(encoded.decode())
                        tape.flush()
                        os.fsync(tape.fileno())
                        digest.update(encoded)
                        count += 1
                    identity, previous = current, sequence
                except HTTPError as exc:
                    errors += 1
                    if exc.code in (401, 403, 404) or (400 <= exc.code < 500 and exc.code != 429):
                        raise
                    delay = max(interval, 60)  # Conservative cooldown for throttling/server errors.
                except (URLError, TimeoutError, OSError):
                    errors += 1
                remaining = deadline - time.monotonic()
                if remaining > 0:
                    time.sleep(min(delay, remaining))
        complete = True
    finally:
        report = {'complete': complete, 'snapshots': count, 'networkErrors': errors,
                  'tapeSha256': digest.hexdigest(), 'fills': None, 'netPnl': None,
                  'decision': 'NO_GO', 'executionEnabled': False, 'liveAllowed': False}
        private_write(path / 'report.json', report)
    return report


def replay_shadow(directory, output):
    path = Path(directory)
    manifest, report = (decode((path / name).read_text()) for name in ('manifest.json', 'report.json'))
    config = manifest['configuration']
    if (manifest['mode'] != 'SHADOW' or not report['complete'] or report['snapshots'] < 1
            or manifest['implementationHash'] != implementation_hash()
            or manifest['configurationHash'] != hashlib.sha256(dumps(config).encode()).hexdigest()):
        raise ValueError('Incomplete run or changed implementation/configuration')
    digest, count, previous, identity = hashlib.sha256(), 0, None, None
    with open(path / 'observations.jsonl', 'rb') as tape:
        while raw := tape.readline(8 * 1024 * 1024 + 1):
            if len(raw) > 8 * 1024 * 1024 or not raw.endswith(b'\n'):
                raise ValueError('Invalid or oversized recording row')
            digest.update(raw)
            row = decode(raw)
            obs = row['observation']
            snapshot = validate(obs, now_ms=obs['generatedMs'])
            current, sequence = (snapshot['sessionId'], snapshot['account']['id']), int(snapshot['sequence'])
            if identity and (current != identity or sequence <= previous):
                raise ValueError('Noncausal replay identity')
            if dumps(evaluate(snapshot, config['groups'])) != dumps(row):
                raise ValueError('Shadow replay mismatch')
            identity, previous = current, sequence
            count += 1
    if count != report['snapshots'] or digest.hexdigest() != report['tapeSha256']:
        raise ValueError('Recording count or checksum mismatch')
    result = {'status': 'SHADOW_REPLAY_MATCH', 'matchedSnapshots': count, 'tapeSha256': digest.hexdigest(),
              'fills': None, 'netPnl': None, 'decision': 'NO_GO', 'executionEnabled': False, 'liveAllowed': False}
    private_write(output, result)
    return result
