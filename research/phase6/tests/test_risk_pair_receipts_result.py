import base64
import copy
import hashlib
import io
import json
from pathlib import Path
import unittest
import zipfile
from research.phase6.receipt_audit import corroborate
from research.phase6.route_coverage_audit import routes
from research.phase6.risk_pair_context_audit import ROOT, summarize_routes


def evidence():
    raw = base64.b64decode((ROOT/'receipts/artifact.zip.b64').read_bytes())
    if hashlib.sha256(raw).hexdigest() != '5060cec3209b2b3d2f7929a09e349b08075f0b8064d7f942f1ba622201f775f2':
        raise ValueError('Original two-receipt artifact hash changed')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if len(archive.infolist()) != 6 or any(i.file_size > 1000000 for i in archive.infolist()):
            raise ValueError('Unexpected receipt artifact members/size')
        return {name:json.loads(archive.read(name)) for name in archive.namelist()}


class RiskPairReceiptResultTest(unittest.TestCase):
    def test_original_raw_receipts_redecode_without_rpc(self):
        data = evidence(); selection = data['selection.json']; original = data['report.json']
        self.assertEqual(selection, json.loads((ROOT/'selection.json').read_text()))
        pair = {x['targetOrder']['token'] for x in selection['transactions']}
        rows = []
        for item, expected in zip(selection['transactions'], original['results']):
            cached = data['raw/'+item['transactionHash']+'.json']
            decoded = corroborate(item['sample'], cached['receipt'], cached['block'], original['eventTopics'])
            conserved = routes(decoded, pair)
            self.assertEqual(decoded['matches'], expected['matches'])
            self.assertEqual(conserved, expected['routeConservation'])
            decoded['routeConservation'] = conserved; rows.append(decoded)
        summary = summarize_routes(dict(complete=True, requested=2, results=rows), selection)
        self.assertEqual(summary, data['route-summary.json'])
        self.assertEqual([r['targetBuyAtOrBelowOwnBidSharesRaw'] for r in summary['results']], [0, 0])
        self.assertEqual([r['actualRouteSharesRaw'] for r in summary['results']], [{'MINT':5300000}, {'MINT':24818182}])
        self.assertEqual(original['rpcCalls'], dict(eth_chainId=1, eth_getTransactionReceipt=2, eth_getBlockByHash=1))
        self.assertNotIn('originalAccountNetPnl', original)
        self.assertFalse(original['netPnlRecomputed'])
        self.assertEqual(original['fillsCreated'], 0)
        self.assertEqual(summary['decision'], 'NO_GO')

    def test_receipt_identity_and_ambiguous_group_fail_closed(self):
        data = evidence(); report = data['report.json']; selection = data['selection.json']
        sample = selection['transactions'][0]['sample']
        cached = copy.deepcopy(data['raw/'+sample['transaction_hash']+'.json'])
        cached['receipt']['transactionHash'] = '0x'+'0'*64
        with self.assertRaisesRegex(ValueError, 'hash/status'):
            corroborate(sample, cached['receipt'], cached['block'], report['eventTopics'])
        report['results'][0]['routeConservation']['uniqueConservedGroup'] = False
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            summarize_routes(report, selection)


if __name__ == '__main__':
    unittest.main()
