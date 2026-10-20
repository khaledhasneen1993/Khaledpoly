"""Verify native 642-identity parity and separately scoped synthetic guards."""
import argparse
from decimal import Decimal as D
import json
from pathlib import Path

ROOT=Path('research/experiments/native-receipt-pool-20261020')


def verify(proof,default_after,provenance):
    if (proof['scope']!='NATIVE_PARTIAL_POOL_PARITY_AND_SYNTHETIC_SESSION_NOT_MARKET_ACCOUNT'
            or proof['originalObservations']!=642 or proof['rejectionGuardsPassed']!=39 or proof['roundingBoundaryCases']!=2
            or proof['sourceIdentitiesSha256']!='2c849a88837b0724e71bfc02bcddbbfa28da238a5ee2fe4c7f325236b3501056'
            or proof['poolLogicalSha256']!='745dadce6749d701ba6048ab1ef76f3f43b354c058e27e9163c2174725aaceea'
            or proof['portionsLogicalSha256']!='3fd8f2d4ce916cd2a70919431e81ec878cb26e94ad7e293ff81e515f6bce092c'):
        raise ValueError('Native original identities/component parity differs')
    for field in ('fullAccountMarketComparisonPerformed','marketNetPnlRecomputed','independentPaperQualificationAllowed','liveAllowed'):
        if proof[field] is not False:raise ValueError('No market/account qualification allowed')
    if proof['modelMarketFillsCreated']!=0:raise ValueError('No market fills inferred')
    pool=proof['poolReader']
    if (pool['experiment']!='CONSERVED-RECEIPT-POOL0' or pool['bindings']!=642 or pool['consumedBindings']!=642
            or pool['actualComponents']!=1516 or pool['failed'] is not False or not pool['strictPartialPool']
            or not pool['nativePartialPoolReaderImplemented']):raise ValueError('Incomplete native pool consumption')
    for field in ('aggregateFallbackAllowed','fullOriginalTapeCoverageProven','fullAccountReplayAuthorized','independentPaperQualificationAllowed','liveAllowed'):
        if pool[field] is not False:raise ValueError('Partial pool scope differs')
    synthetic=proof['syntheticSession'];s=synthetic['session']
    if (synthetic['inputKind']!='SYNTHETIC_ONLY_NOT_MARKET' or not synthetic['canonicalQueueConserved']
            or not synthetic['unknownCoveredTransactionAtWrongCoordinateHaltsCancels'] or not synthetic['subsequentInputBlocked']
            or not synthetic['existingCashAndInventoryPreserved'] or D(synthetic['syntheticCash'])!=498
            or D(synthetic['syntheticShares'])!=5):raise ValueError('Synthetic failure guard scope differs')
    cfg=json.loads(Path('research/phase2/research-config.json').read_text())
    if any(D(str(s['configuration'][k]))!=D(str(value)) for k,value in cfg.items()):raise ValueError('Original risk/fee/queue/config changed')
    if (not s['halted'] or s['openOrderCount']!=0 or D(str(s['cash']))!=498
            or D(str(s['holdings']['a']['shares']))!=5 or D(str(s['holdings']['a']['basis']))!=2
            or D(str(s['feesAndSettlementCosts']))!=0 or not s['frozenQw0AndFeePositivePoliciesIntegrated']
            or s['fullOriginalTapeCoverageProven'] or s['liveAllowed'] or s['independentPaperQualificationAllowed']):
        raise ValueError('Canonical halt/cancel/cash/inventory preservation differs')
    volume=s['settlementVolumeConservation']
    if any(D(str(volume[k]))!=v for k,v in [('venueQuantity',D(300)),('queueAbsorbed',D(200)),('allocatedQuantity',D(5)),('unusedQuantity',D(95))]):
        raise ValueError('Original synthetic queue/volume conservation differs')
    original=json.loads(Path('research/experiments/session-bridge-20261019/default-before.json').read_text(),parse_float=D)
    if default_after!=original:raise ValueError('Complete default-off report parity differs')
    if (provenance['defaultCoreFilesModified']!=0 or not provenance['frozenCausalRulesPortedWithoutParameterChanges']
            or provenance['integratedSessionSha256']!='a57c2fd2efa14d7704a5c177e962e81855be9374687eec478faf368a72856251'
            or provenance['fullOriginalTapeCoverageProven'] or provenance['liveAllowed'] or provenance['independentPaperQualificationAllowed']):
        raise ValueError('Isolated native source build provenance differs')
    return dict(scope='VERIFIED_NATIVE_PARTIAL_POOL_AND_SYNTHETIC_SESSION_NOT_MARKET_ACCOUNT',originalIdentities=642,
        conservedComponentTuples=1516,rejectionGuards=39,conservativeRoundingBoundaryCases=2,
        allSourceIdentitiesAndTuplesMatchPython=True,completeDefaultOffParity=True,
        unknownAnyMarketFailsWithoutAggregateFallback=True,syntheticUnknownHaltsCancelsPreservesInventory=True,
        fullOriginalTapeCoverageProven=False,fullAccountMarketComparisonPerformed=False,marketNetPnlRecomputed=False,
        modelMarketFillsCreated=0,independentPaperQualificationAllowed=False,liveAllowed=False)


def saved(root=ROOT):
    def read(n):return json.loads((root/n).read_text(),parse_float=D)
    return verify(read('native-pool-proof.json'),read('default-after.json'),read('build-provenance.json'))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);a=p.parse_args();print(json.dumps(saved(a.root),indent=2))
