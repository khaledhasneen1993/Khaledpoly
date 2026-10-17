"""Durable, fail-closed bridge from external strategy REVIEW to Java PAPER /screen.

This module NEVER invokes the Java /paper admission endpoint. It cannot
reserve/submit a virtual order, sign or transfer money. It persists exact
reviewed screen requests before an HTTP call; crash recovery GETs the
server's durable SCREEN receipt and never generates a fresh client ID.
"""
import fcntl
import hashlib
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request

from research.phase3.polybot_sdk.client import PaperClient
from research.phase3.polybot_sdk.model import decode, dumps, integer, validate
from research.phase3.polybot_sdk.runtime import private_write
from research.phase6.external_strategy import ExternalStrategyReview

MAX_RESPONSE = 65536


def digest(data):
    return hashlib.sha256(dumps(data).encode('utf-8')).hexdigest()


def guard_admission_snapshot(original, current, requests, *, exact_sequence):
    """Bind account state and original quote lifetime, not the GET response clock."""
    if (current['sessionId'] != original['sessionId']
            or current['account']['id'] != original['account']['id']
            or digest(current['account']) != digest(original['account'])
            or integer(current['sequence']) < integer(original['sequence'])
            or exact_sequence and integer(current['sequence']) != integer(original['sequence'])):
        raise ValueError('Executor snapshot changed before PAPER admission')
    now = integer(current['generatedMs'])
    if not integer(original['generatedMs']) <= now <= integer(original['generatedMs']) + 250:
        raise ValueError('Original PAPER observation expired')
    if any(integer(leg['expiresMs']) <= now for req in requests for leg in req['legs']):
        raise ValueError('Original PAPER quote expired')


def _sync_folder(folder):
    fd = os.open(str(folder), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _receipt(receipt, request):
    if (not isinstance(receipt, dict)
            or receipt.get('id') != request['id']
            or receipt.get('status') != 'SCREENED_SHADOW_ONLY'
            or integer(receipt.get('sequence')) != integer(request['sequence'])
            or receipt.get('executionEnabled') is not False
            or receipt.get('liveAllowed') is not False
            or receipt.get('decision') != 'NO_GO'
            or integer(receipt.get('expiresMs')) <= 0):
        raise ValueError('Invalid or unrelated durable PAPER screen receipt')
    return receipt


class PaperScreenClient(PaperClient):
    """Token-authenticated SCREEN/receipt only, never the /paper endpoint."""

    def screen_identical(self, proposal):
        url = self._url.rsplit('/', 1)[0] + '/proposals/screen'
        request = Request(url, data=dumps(proposal).encode('utf-8'), method='POST',
                          headers={'X-Polybot-Token': self._token,
                                   'Content-Type': 'application/json'})
        with self._opener.open(request, timeout=self._timeout) as response:
            if response.status != 200:
                raise ValueError('Unexpected PAPER screen response')
            raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            raise ValueError('Oversized PAPER screen receipt')
        return _receipt(decode(raw), proposal)

    def saved_receipt(self, proposal):
        """404 remains UNKNOWN, not permission to submit a new order."""
        from urllib.parse import quote
        url = (self._url.rsplit('/', 1)[0] + '/proposals/screen-receipts/'
               + quote(proposal['id'], safe=''))
        request = Request(url, method='GET',
                          headers={'X-Polybot-Token': self._token})
        try:
            with self._opener.open(request, timeout=self._timeout) as response:
                if response.status != 200:
                    raise ValueError('Unexpected saved PAPER receipt status')
                raw = response.read(MAX_RESPONSE + 1)
        except HTTPError as exc:
            if exc.code == 404:
                return None
            raise
        if len(raw) > MAX_RESPONSE:
            raise ValueError('Oversized stored PAPER receipt')
        return _receipt(decode(raw), proposal)


class DurablePaperScreen:
    def __init__(self, client, reviewer=None):
        self.client = client
        self.reviewer = reviewer if reviewer is not None else ExternalStrategyReview()

    def run(self, directory, observation, envelope, *, at_ms=None, account_gate=None):
        path=Path(directory)
        recovery=(path/'manifest.json').exists()
        # Old snapshots are allowed ONLY to reconcile an already-frozen
        # outbox via read-only GET. They can NEVER authorize a new screen.
        checked_at=(integer(observation['generatedMs']) if recovery else at_ms)
        snap = validate(observation, checked_at)
        review = self.reviewer.review(snap, envelope, at_ms=checked_at, account_gate=account_gate)
        requests = review['approvedPaperScreenRequests']
        if len(requests) != review['admittedResearchCandidates']:
            raise ValueError('Mismatched allocation and approved research requests')
        if len(set(r['id'] for r in requests)) != len(requests):
            raise ValueError('Duplicate durable screening identity')
        manifest = {'schema':1,'mode':'JAVA_PAPER_SCREEN_ONLY',
                    'snapshotSha256':digest(snap),'envelopeSha256':digest(envelope),
                    'sessionId':snap['sessionId'],'accountId':snap['account']['id'],
                    'sequence':integer(snap['sequence']),
                    'requests':[{'id':r['id'],'sha256':digest(r)} for r in requests],
                    'executionEnabled':False,'liveAllowed':False}
        path.mkdir(mode=0o700,parents=True,exist_ok=True)
        lock_fd=os.open(str(path/'.lock'),os.O_RDWR|os.O_CREAT,0o600)
        try:
            fcntl.flock(lock_fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            frozen=path/'manifest.json'
            first_run=not frozen.exists()
            if first_run:
                # A partial/tampered directory must not be silently reused.
                if set(x.name for x in path.iterdir()) != {'.lock'}:
                    raise ValueError('Unidentified preexisting outbox files')
                private_write(frozen,manifest)
                _sync_folder(path)
            elif decode(frozen.read_text(encoding='utf-8')) != manifest:
                raise ValueError('Outbox snapshot/envelope changed after preparation')
            for i,proposal in enumerate(requests,1):
                target=path/('request-%04d.json' % i)
                if not target.exists():
                    if not first_run:
                        raise ValueError('Missing previously journaled request')
                    private_write(target,proposal)
                    _sync_folder(path)
                elif decode(target.read_text(encoding='utf-8')) != proposal:
                    raise ValueError('Previously journaled PAPER request changed')
            # Only a first-ever run may POST. Resume never re-POSTs missing
            # receipts: it queries the Java durable inbox without mutations.
            confirmed=unknown=0
            for i,proposal in enumerate(requests,1):
                receipt_file=path/('receipt-%04d.json' % i)
                if receipt_file.exists():
                    _receipt(decode(receipt_file.read_text(encoding='utf-8')),proposal)
                    confirmed+=1
                    continue
                answer=None
                try:
                    if first_run:
                        # Every first submission is bound to the exact remote
                        # account snapshot. Re-check after previous screens.
                        current=validate(self.client.snapshot(now_ms=at_ms),at_ms)
                        guard_admission_snapshot(snap,current,[proposal],exact_sequence=True)
                        answer=self.client.screen_identical(proposal)
                    else:
                        answer=self.client.saved_receipt(proposal)
                except (HTTPError, URLError, TimeoutError, OSError):
                    # Unknown HTTP outcome: recover by read-only GET next run.
                    answer=None
                if answer is None:
                    unknown+=1
                    continue
                _receipt(answer,proposal)
                private_write(receipt_file,answer)
                _sync_folder(path)
                confirmed+=1
            return {'schema':1,'scope':'DURABLE_JAVA_PAPER_SCREEN_BRIDGE',
                    'accountId':snap['account']['id'],'screenRequests':len(requests),
                    'confirmedScreenReceipts':confirmed,
                    'unknownRemoteReceipts':unknown,
                    'firstRun':first_run,
                    'recoveryPolicy':'READ_ONLY_GET_NO_NEW_ID_NO_RESUBMISSION',
                    'paperReservationsMade':False,
                    'venueOrdersSubmitted':0,'liveAllowed':False,
                    'executionEnabled':False,'decision':'NO_GO'}
        finally:
            os.close(lock_fd)



def main():
    import argparse
    parser=argparse.ArgumentParser(
        description='Screen external PAPER proposals in Java durable inbox (NO ORDERS)')
    parser.add_argument('--origin',required=True,help='Java PAPER endpoint; HTTPS or local HTTP')
    parser.add_argument('--snapshot',required=True,help='Exact recent PAPER snapshot JSON')
    parser.add_argument('--envelope',required=True,help='Strict versioned external strategy JSON')
    parser.add_argument('--outbox',required=True,help='Immutable local screen request journal')
    parser.add_argument('--token-env',default='POLYBOT_EXECUTOR_TOKEN',
                        help='Environment variable with API token; never logged or written')
    args=parser.parse_args()
    import re
    if not re.fullmatch('[A-Z][A-Z0-9_]{0,63}',args.token_env):
        parser.error('Invalid environment token name')
    token=os.environ.get(args.token_env)
    if not token:
        parser.error('Missing executor token environment variable')
    observation=decode(Path(args.snapshot).read_text(encoding='utf-8'))
    envelope=decode(Path(args.envelope).read_text(encoding='utf-8'))
    client=PaperScreenClient(args.origin,token)
    outcome=DurablePaperScreen(client).run(args.outbox,observation,envelope)
    print(dumps(outcome))


if __name__=='__main__':
    main()
