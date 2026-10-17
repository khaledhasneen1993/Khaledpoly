"""Read-only multi-account risk/ledger reconciliation using existing PAPER registry.

No funds can be transferred, reserved, submitted or signed by this adapter.
The Java AccountLedger remains the only durable reservation authority.
"""
from decimal import Decimal

from research.phase3.polybot_sdk.model import number, integer


class CrossAccountPaperGate:
    def __init__(self, registry, account_caps, global_cap, group_cap):
        if (not isinstance(account_caps,dict) or not 1<=len(account_caps)<=32
                or any(not isinstance(k,str) or not k or number(v)<=0 for k,v in account_caps.items())):
            raise ValueError('Invalid per-account risk policy')
        self.registry=registry
        self.account_caps={k:number(v) for k,v in account_caps.items()}
        self.global_cap=number(global_cap)
        self.group_cap=number(group_cap)
        if self.global_cap<=0 or self.group_cap<=0:
            raise ValueError('Risk caps must be positive')

    def inspect(self, at_ms):
        """Reconcile existing valid PAPER snapshots; never change account state."""
        now=integer(at_ms)
        report=self.registry.report()
        aliases=set(report['accounts'])
        missing=set(report['missingAccounts'])
        if aliases|missing != set(self.account_caps) or aliases & missing:
            raise ValueError('Risk policy aliases do not match isolated account registry')
        valuation=self.registry.fund_valuation(now)
        account_exposure={}
        settlement_exposure={}
        reasons=[]
        if missing:
            reasons.append('MISSING_ISOLATED_ACCOUNTS')
        if not valuation['complete']:
            reasons.append('INCOMPLETE_OR_STALE_VALUATION')
        if any(not v['researchAllowed'] for v in report['accounts'].values()):
            reasons.append('MISSING_RESEARCH_PERMISSION')
        for alias, entry in sorted(report['accounts'].items()):
            observation=entry['account']
            markets={t:m['condition'] for m in
                     self.registry._latest[alias]['markets'] for t in (m['first'],m['second'])}
            exposure=Decimal(0)
            def consume(token,amount):
                nonlocal exposure
                if amount<0:
                    raise ValueError('Negative exposure in account ledger')
                exposure+=amount
                group=markets.get(token,'UNKNOWN_UNGROUPED')
                settlement_exposure[group]=settlement_exposure.get(group,Decimal(0))+amount
            for token, holding in observation['holdings'].items():
                consume(token,number(holding['basis']))
            for order in observation['orders'].values():
                if order['buy']:
                    consume(order['token'],number(order['price'])*number(order['remaining']))
            account_exposure[alias]=exposure
            if exposure>self.account_caps[alias]:
                reasons.append('ACCOUNT_CAP_EXCEEDED:'+alias)
        total=sum(account_exposure.values(),Decimal(0))
        if total>self.global_cap:
            reasons.append('GLOBAL_GROSS_EXPOSURE_CAP_EXCEEDED')
        if any(v>self.group_cap for v in settlement_exposure.values()):
            reasons.append('CORRELATED_SETTLEMENT_GROUP_CAP_EXCEEDED')
        if settlement_exposure.get('UNKNOWN_UNGROUPED',Decimal(0))>0:
            reasons.append('UNKNOWN_SETTLEMENT_GROUP')
        # Explicit fail closed: no permission to send even virtual orders.
        return {'schema':1,'scope':'READ_ONLY_CROSS_ACCOUNT_PAPER_RISK_GATE',
                'accounts':{k:{'worstCaseAcquisitionExposureUsd':str(v),
                                'capUsd':str(self.account_caps[k])}
                            for k,v in sorted(account_exposure.items())},
                'combinedExposureUsd':str(total),
                'settlementGroupExposureUsd':{k:str(v) for k,v in sorted(settlement_exposure.items())},
                'globalCapUsd':str(self.global_cap),
                'groupCapUsd':str(self.group_cap),
                'missingAccounts':sorted(missing),
                'reconciliationComplete':not reasons,
                'issues':sorted(set(reasons)),
                'mayStudyPaperProposals':not reasons,
                'mayReserveOrSubmit':False,
                'capitalTransfersEnabled':False,
                'venueFillEvidence':False,
                'executionEnabled':False,'liveAllowed':False,
                'decision':'NO_GO'}
