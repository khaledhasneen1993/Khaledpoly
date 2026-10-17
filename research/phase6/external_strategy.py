"""Restricted external-strategy JSON contract into existing PAPER-only allocator.

No dynamic imports, plugins executed, signed orders, wallet, fund transfer,
or network execution. The Java ledger remains the sole reservation authority.
"""
import hashlib
import re

from research.phase3.polybot_sdk.advanced import allocate
from research.phase3.polybot_sdk.model import dumps, integer, number, validate

ENVELOPE={'schema','version','strategyId','sessionId','accountId',
          'snapshotSequence','observedMs','proposals'}
PROPOSAL={'id','edge','legs'}
LEG={'condition','token','buy','price','size','expiresMs'}


class ExternalStrategyReview:
    def __init__(self, per_order='25', per_group='25', gross_limit='100'):
        self.risk_limits=tuple(number(v) for v in (per_order,per_group,gross_limit))
        if any(value<=0 for value in self.risk_limits):
            raise ValueError('Nonpositive external strategy research cap')
        self._receipts={}

    def review(self, observation, envelope, at_ms=None, account_gate=None):
        snap=validate(observation,at_ms)
        if not isinstance(envelope,dict) or set(envelope)!=ENVELOPE:
            raise ValueError('Unexpected strategy payload fields')
        if envelope.get('schema')!=1 or envelope.get('version')!='1.0':
            raise ValueError('Unsupported strategy protocol')
        strategy=envelope.get('strategyId')
        if not isinstance(strategy,str) or not re.fullmatch(r'[a-z0-9-]{1,64}',strategy):
            raise ValueError('Invalid strategy identity')
        if (envelope['sessionId']!=snap['sessionId']
              or envelope['accountId']!=snap['account']['id']
              or integer(envelope['snapshotSequence'])!=integer(snap['sequence'])):
            raise ValueError('External strategy mixed accounts or replayed a different sequence')
        when=integer(envelope['observedMs'])
        if when!=integer(snap['generatedMs']):
            raise ValueError('External strategy observed an unbound clock')
        candidates=envelope['proposals']
        if not isinstance(candidates,list) or not 1<=len(candidates)<=32:
            raise ValueError('Invalid external candidate count')
        seen=set()
        for item in candidates:
            if not isinstance(item,dict) or set(item)!=PROPOSAL:
                raise ValueError('Undeclared strategy command')
            identity=item['id']
            if not isinstance(identity,str) or not re.fullmatch(r'[A-Za-z0-9:_-]{1,128}',identity) or identity in seen:
                raise ValueError('Duplicate/invalid strategy proposal')
            seen.add(identity)
            if number(item['edge'])<=0 or number(item['edge'])>1:
                raise ValueError('Invalid hypothetical edge range')
            legs=item['legs']
            if not isinstance(legs,list) or not 1<=len(legs)<=16:
                raise ValueError('Invalid proposal group size')
            for leg in legs:
                if not isinstance(leg,dict) or set(leg)!=LEG:
                    raise ValueError('Undeclared external order fields')
                if type(leg['buy']) is not bool:
                    raise ValueError('Ambiguous virtual order side')
        if account_gate is not None:
            if (not isinstance(account_gate,dict) or account_gate.get('scope')!='READ_ONLY_CROSS_ACCOUNT_PAPER_RISK_GATE'
                    or account_gate.get('mayStudyPaperProposals') is not True
                    or account_gate.get('mayReserveOrSubmit') is not False
                    or account_gate.get('liveAllowed') is not False):
                raise PermissionError('Cross-account study gate failed')
        key=snap['sessionId'],snap['account']['id'],strategy,integer(snap['sequence'])
        source_hash=hashlib.sha256(dumps(envelope).encode()).hexdigest()
        existing=self._receipts.get(key)
        if existing is not None:
            if existing['envelopeSha256']!=source_hash:
                raise ValueError('Strategy snapshot idempotency conflict')
            return dict(existing, replayedIdentical=True)
        allocation=allocate(snap,candidates,per_order=self.risk_limits[0],
                            per_group=self.risk_limits[1],gross_limit=self.risk_limits[2])
        # Track idempotency for successful and rejected proposals alike.
        output={'schema':1,'scope':'EXTERNAL_PAPER_STRATEGY_REVIEW',
                'strategyId':strategy,'accountId':snap['account']['id'],
                'snapshotSequence':snap['sequence'],
                'envelopeSha256':source_hash,
                'admittedResearchCandidates':len(allocation['admitted']),
                'rejections':allocation['rejected'],
                'replayedIdentical':False,
                'venueOrdersSubmitted':0,'accountBalancesModified':False,
                'executionEnabled':False,'liveAllowed':False,'decision':'NO_GO'}
        self._receipts[key]=output
        return output
