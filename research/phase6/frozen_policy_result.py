"""Exact Python/Java rule parity and synthetic integrated-session accounting only."""
from decimal import Decimal as D
import argparse
import json
from pathlib import Path
from research.phase6.frozen_policy_cases import prepare

ROOT=Path('research/experiments/frozen-strategy-profile-20261020')


def rule_parity(result):
    source=prepare()
    if result['scope']!='FROZEN_RULE_PARITY_NOT_ACCOUNT' or len(result['quotes'])!=42 or len(result['exits'])!=18:raise ValueError('Rule parity scope/count differs')
    for case,actual in zip(source['quotes'],result['quotes']):
        expected=case['expected']
        if (expected is None)!=(actual is None):raise ValueError('Frozen quote admission differs')
        if expected is None:continue
        if set(expected)!=set(actual):raise ValueError('Frozen quote fields differ')
        for k,v in expected.items():
            if (actual[k]!=v if isinstance(v,bool) else D(str(actual[k]))!=D(str(v))):raise ValueError('Frozen quote value/objective differs '+k)
    for case,actual in zip(source['exits'],result['exits']):
        for k,v in case['expected'].items():
            if (actual[k]!=v if k=='action' else D(str(actual[k]))!=D(str(v))):raise ValueError('Frozen exit choice differs '+k)


def verify(parity,proof,default_after):
    rule_parity(parity)
    baseline=json.loads(Path('research/experiments/session-bridge-20261019/default-before.json').read_text(),parse_float=D)
    if baseline!=default_after:raise ValueError('Default-off full report parity differs')
    if (proof['scope']!='INTEGRATED_FROZEN_POLICIES_SYNTHETIC_ONLY_NOT_MARKET_PNL' or proof['defaultCoreFilesModified']!=0
            or proof['modelMarketFillsCreated']!=0 or proof['marketNetPnlRecomputed'] or proof['fullAccountMarketComparisonPerformed']
            or proof['independentPaperQualificationAllowed'] or proof['liveAllowed']):raise ValueError('Synthetic-only integrated scope differs')
    cfg=json.loads(Path('research/phase2/research-config.json').read_text())
    for name in ['positive','netEdgeRejected']:
        case=proof[name];s=case['session'];v=s['settlementVolumeConservation']
        if (case['inputKind']!='SYNTHETIC_NOT_MARKET' or not s['frozenQw0AndFeePositivePoliciesIntegrated'] or s['researchLabelBridgeOnly']
                or s['fullOriginalTapeCoverageProven'] or s['independentPaperQualificationAllowed'] or s['liveAllowed'] or s['decision']!='NO_GO'):
            raise ValueError('Integrated session scope differs')
        if any(D(str(s['configuration'][k]))!=D(str(value)) for k,value in cfg.items()):raise ValueError('Fees, queue, latency or risk configuration changed')
        if any(D(str(v[k]))!=value for k,value in [('venueQuantity',D(300)),('queueAbsorbed',D(200)),('allocatedQuantity',D(5)),('unusedQuantity',D(95))]):raise ValueError('Synthetic conserved queue/allocation differs')
        if any(D(str(d['initialQueueAhead']))!=200 for d in s['makerExecutionDiagnostics'][:2]):raise ValueError('Actual entry queue relaxed')
        entries=[e['value'] for e in case['events'] if e['kind']=='QW0_DECISION']
        choices=[e['value'] for e in case['events'] if e['kind']=='HEDGE_DECISION']
        if (len(entries)!=1 or entries[0]['at']!=1251 or D(str(entries[0]['quote']['firstBid']))!=D('.4')
                or D(str(entries[0]['quote']['secondBid']))!=D('.4') or not choices
                or choices[0]['at']!=6821 or choices[0]['choice']['action']!='TAKER_SELL'):raise ValueError('Canonical entry/cancel ACK/exit trajectory differs')
    positive=proof['positive'];p=positive['session'];fills=[e['value'] for e in positive['events'] if e['kind']=='TAKER_FILL']
    if (D(str(p['cash']))!=D('500.11376') or D(str(p['netRealizedPnl']))!=D('.11376') or D(str(p['feesAndSettlementCosts']))!=D('.08624')
            or D(str(p['holdings']['a']['shares']))!=0 or len(fills)!=1 or fills[0]['fill']['at']!=7071 or fills[0]['purpose']!='POSITIVE_EDGE_EXIT'):
        raise ValueError('Synthetic actual positive exit fee/cash/timing differs')
    n=proof['netEdgeRejected']['session']
    if (D(str(n['cash']))!=498 or D(str(n['holdings']['a']['shares']))!=5 or D(str(n['feesAndSettlementCosts']))!=0
            or n['decisionReasons'].get('TAKER_NET_EDGE')!=1 or any(e['kind']=='TAKER_FILL' for e in proof['netEdgeRejected']['events'])):
        raise ValueError('Deteriorated execution-net edge guard differs')
    return dict(scope='VERIFIED_FROZEN_RULE_PORT_AND_SYNTHETIC_SESSION_NOT_MARKET_PNL',developmentWitnessProposals=34,
        additionalSyntheticQuoteCases=8,feePositiveChoiceCases=18,completeDefaultOffParity=True,
        canonicalEntryQueueAndCancelAckPreserved=True,actualExecutionNetRechecked=True,
        frozenRulesIntegratedInExplicitOfflineProfile=True,fullAccountMarketComparisonPerformed=False,
        modelMarketFillsCreated=0,marketNetPnlRecomputed=False,independentPaperQualificationAllowed=False,liveAllowed=False)


def saved(root=ROOT):
    def read(n):return json.loads((root/n).read_text(),parse_float=D)
    return verify(read('rule-parity.json'),read('strategy-proof.json'),read('default-after.json'))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);a=p.parse_args();print(json.dumps(saved(a.root),indent=2))
