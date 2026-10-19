"""Verify isolated-source DEFAULT parity and SYNTHETIC session accounting/stop guards."""
import argparse
from decimal import Decimal as D
import json
from pathlib import Path

ROOT=Path('research/experiments/session-bridge-20261019')


def verify(before,after,bridge,build):
    if before!=after or 'researchLabelBridgeOnly' in before:raise ValueError('Default canonical report parity differs')
    if (bridge['scope']!='SYNTHETIC_CANONICAL_SESSION_BRIDGE_NOT_MARKET_OR_PROFIT_PROOF'
            or not bridge['syntheticEntryBookedThroughCanonicalStrategyMatcherLedger']
            or bridge['duplicateAggregateChangedLedger'] or bridge['rejectionGuardsPassed']!=7
            or not bridge['unknownSourceHaltsCancelsAndBlocksSubsequentInput']
            or bridge['modelMarketFillsCreated']!=0 or bridge['marketNetPnlRecomputed']
            or bridge['fullAccountStrategyComparisonPerformed'] or bridge['frozenQw0AndFeePositivePoliciesIntegrated']
            or bridge['independentPaperQualificationAllowed'] or bridge['liveAllowed']):raise ValueError('Synthetic-only bridge scope/guards differ')
    r=bridge['syntheticTerminalSessionReport'];labels=r['settlementExperiment'];volume=r['settlementVolumeConservation']
    if (D(str(before['cash']))!=D('497.95') or D(str(before['holdings']['a']['shares']))!=5
            or D(str(before['holdings']['a']['basis']))!=D('2.05')
            or D(str(r['cash']))!=D('497.95') or D(str(r['holdings']['a']['shares']))!=5
            or D(str(r['holdings']['a']['basis']))!=D('2.05') or not r['halted'] or r['openOrderCount']!=0
            or not r['researchLabelBridgeOnly'] or r['frozenQw0AndFeePositivePoliciesIntegrated']
            or r['fullOriginalTapeCoverageProven'] or r['independentPaperQualificationAllowed'] or r['liveAllowed']
            or labels['bindings']!=1 or labels['consumedBindings']!=1 or labels['actualComponents']!=1
            or labels['duplicateAggregateSuppressed']!=1 or volume['uniqueMakerComponents']!=1
            or any(D(str(volume[k]))!=v for k,v in [('venueQuantity',D(30)),('allocatedQuantity',D(5)),('queueAbsorbed',D(0)),('unusedQuantity',D(25))])):
        raise ValueError('Synthetic canonical cash/inventory/conservation/stop differs')
    if (build['scope']!='ISOLATED_SOURCE_BUILD_NOT_ACCOUNT_OR_PROFIT_PROOF' or build['coreSources']!=94
            or build['defaultCoreFilesModified']!=0 or build['generatedCoreFilesChanged']!=['polybot-core/src/main/java/com/polybot/hft/paper/ResearchSession.java']
            or build['frozenStrategyChanged'] or build['independentPaperQualificationAllowed'] or build['liveAllowed']):raise ValueError('Isolated build scope differs')
    return dict(scope='VERIFIED_SYNTHETIC_SESSION_BRIDGE_AND_DEFAULT_PARITY_NOT_MARKET_PNL',
        completeDefaultReportParity=True,canonicalSyntheticEntryAndCashInventoryBooking=True,
        coveredAggregateCannotDoubleAllocate=True,unknownScopedSourceHaltsAndCancels=True,
        freshOfflineGuardCases=7,defaultCoreFilesModified=0,frozenQw0AndFeePositivePoliciesIntegrated=False,
        modelMarketFillsCreated=0,marketNetPnlRecomputed=False,independentPaperQualificationAllowed=False,liveAllowed=False)


def saved(root=ROOT):
    def read(name):return json.loads((root/name).read_text(),parse_float=D)
    return verify(read('default-before.json'),read('default-after.json'),read('bridge-proof.json'),read('build-provenance.json'))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);a=p.parse_args();print(json.dumps(saved(a.root),indent=2))
