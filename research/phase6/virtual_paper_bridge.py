"""Opt-in virtual PAPER proposal execution through the EXISTING Java ledger.

This adapter NEVER has exchange routes or wallet/signature credentials.
Enabled=False by default. Java PaperExchangeSimulator /paper remains the sole
reservation, matching and fee-accounting authority. The durable local journal
only records exact requests and receipts for replay of unknown outcomes.
"""
import argparse
import fcntl
import os
from pathlib import Path
from urllib.error import HTTPError, URLError

from research.phase3.polybot_sdk.execution import PaperExecutionClient
from research.phase3.polybot_sdk.model import decode, dumps, integer, validate
from research.phase3.polybot_sdk.runtime import private_write
from research.phase6.external_strategy import ExternalStrategyReview
from research.phase6.paper_screen_bridge import digest, _sync_folder


def validate_virtual_receipt(data, request):
    if (not isinstance(data, dict)
            or data.get('id') != request['id']
            or data.get('status') not in ('PAPER_SUBMITTED','PAPER_ALREADY_RECORDED','PAPER_REJECTED')
            or data.get('virtualOnly') is not True
            or data.get('executionEnabled') is not False
            or data.get('liveAllowed') is not False):
        raise ValueError('Unsafe or unrelated Java PAPER execution receipt')
    return data


class DurableVirtualPaperOrders:
    def __init__(self, client, reviewer=None):
        self.client=client
        self.reviewer=reviewer if reviewer is not None else ExternalStrategyReview()

    def run(self, directory, observation, envelope, *, enable_virtual=False,
            at_ms=None, account_gate=None):
        if enable_virtual is not True:
            raise PermissionError('Explicit virtual PAPER-order activation required')
        folder=Path(directory)
        resume=(folder/'manifest.json').exists()
        checked_at=integer(observation['generatedMs']) if resume else at_ms
        snap=validate(observation,checked_at)
        if snap.get('paperExecutionEnabled') is not True:
            raise PermissionError('Java executor must explicitly enable virtual PAPER execution')
        reviewed=self.reviewer.review(snap,envelope,at_ms=checked_at,account_gate=account_gate)
        requests=reviewed['approvedPaperScreenRequests']
        if len(requests)!=reviewed['admittedResearchCandidates'] or len(requests)>32:
            raise ValueError('Unsafe external allocation count')
        manifest={'schema':1,'mode':'EXPLICIT_VIRTUAL_PAPER_EXECUTION',
                  'sessionId':snap['sessionId'],'accountId':snap['account']['id'],
                  'snapshotSha256':digest(snap),'envelopeSha256':digest(envelope),
                  'requests':[{'id':p['id'],'sha256':digest(p)} for p in requests],
                  'realOrdersEnabled':False,'virtualOnly':True,'liveAllowed':False}
        folder.mkdir(parents=True,exist_ok=True,mode=0o700)
        fd=os.open(str(folder/'.lock'),os.O_RDWR|os.O_CREAT,0o600)
        try:
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            frozen=folder/'manifest.json'
            first=not frozen.exists()
            if first:
                if {p.name for p in folder.iterdir()}!={'.lock'}:
                    raise ValueError('Unidentified preexisting virtual order files')
                private_write(frozen,manifest)
                _sync_folder(folder)
            elif decode(frozen.read_text(encoding='utf-8'))!=manifest:
                raise ValueError('Virtual PAPER order outbox identity conflict')
            for i,req in enumerate(requests,1):
                stored=folder/('request-%04d.json'%i)
                if not stored.exists():
                    if not first:
                        raise ValueError('Missing frozen virtual order')
                    private_write(stored,req)
                    _sync_folder(folder)
                elif decode(stored.read_text(encoding='utf-8'))!=req:
                    raise ValueError('Virtual request changed on disk')
            statuses={'PAPER_SUBMITTED':0,'PAPER_ALREADY_RECORDED':0,'PAPER_REJECTED':0}
            unknown=0
            for i,req in enumerate(requests,1):
                target=folder/('receipt-%04d.json'%i)
                if target.exists():
                    result=validate_virtual_receipt(
                        decode(target.read_text(encoding='utf-8')),req)
                    statuses[result['status']]+=1
                    continue
                try:
                    remote=validate(self.client.snapshot(now_ms=at_ms),at_ms)
                    if (remote.get('paperExecutionEnabled') is not True
                            or remote['sessionId']!=snap['sessionId']
                            or remote['account']['id']!=snap['account']['id']):
                        # A restart on a different account/session may never
                        # resubmit a previous external strategy proposal.
                        raise ValueError('Changed PAPER account/session during retry')
                    if first and digest(remote)!=manifest['snapshotSha256']:
                        raise ValueError('PAPER snapshot changed before first virtual admission')
                    # The request was fsynced before this call; retries are
                    # IDENTICAL and the Java Ledger.reserveBatch is the
                    # only authority that may mutate virtual balances.
                    result=validate_virtual_receipt(self.client.retry_identical(req),req)
                except (HTTPError,URLError,TimeoutError,OSError):
                    unknown+=1  # Next run may replay this identical client ID.
                    continue
                private_write(target,result)
                _sync_folder(folder)
                statuses[result['status']]+=1
            return {'schema':1,'scope':'OPT_IN_DURABLE_VIRTUAL_PAPER_LEDGER_BRIDGE',
                    'frozenVirtualRequests':len(requests),
                    'receiptCounts':statuses,'unknownOutcomes':unknown,
                    'firstRun':first,'sameIdRecoveryOnly':True,
                    'javaLedgerIsAuthoritative':True,'realOrdersEnabled':False,
                    'walletOrSigningEnabled':False,'liveAllowed':False,
                    'decision':'NO_GO'}
        finally:
            os.close(fd)


def main():
    p=argparse.ArgumentParser(description='Explicit virtual PAPER orders only; no LIVE')
    p.add_argument('--origin',required=True)
    p.add_argument('--snapshot',required=True)
    p.add_argument('--envelope',required=True)
    p.add_argument('--outbox',required=True)
    p.add_argument('--token-env',default='POLYBOT_EXECUTOR_TOKEN')
    p.add_argument('--enable-virtual-paper-only',action='store_true',
                   help='Required: authorize VIRTUAL PAPER reservations, never venue orders')
    a=p.parse_args()
    import re
    if not re.fullmatch('[A-Z][A-Z0-9_]{0,63}',a.token_env):
        p.error('Invalid token environment variable')
    token=os.environ.get(a.token_env)
    if not token:
        p.error('Missing PAPER executor token environment variable')
    client=PaperExecutionClient(a.origin,token)
    snap=decode(Path(a.snapshot).read_text(encoding='utf-8'))
    envelope=decode(Path(a.envelope).read_text(encoding='utf-8'))
    result=DurableVirtualPaperOrders(client).run(a.outbox,snap,envelope,
                        enable_virtual=a.enable_virtual_paper_only)
    print(dumps(result))


if __name__=='__main__':
    main()
