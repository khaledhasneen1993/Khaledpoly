"""Re-decode all eight immutable receipts offline, never infer counterfactual fills."""
import base64
import hashlib
import io
import json
import unittest
import zipfile
from research.phase6.dq3_bottleneck_receipts import ROOT,selection,summarize
from research.phase6.receipt_audit import corroborate
from research.phase6.route_coverage_audit import routes


class Dq3BottleneckResultTest(unittest.TestCase):
    def test_exact_eight_receipts_conserved_and_zero_price_compatible_volume(self):
        raw=base64.b64decode((ROOT/'bottleneck-result/artifact.zip.b64').read_bytes())
        self.assertEqual(hashlib.sha256(raw).hexdigest(),'7b937464f275b0b562e12d3f203517a9c138448930761bb72178eb9fffe961dd')
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            self.assertEqual(len(z.infolist()),11)
            report=json.loads(z.read('report.json'));spec=selection()
            self.assertEqual(json.loads(z.read('selection.json')),spec)
            self.assertTrue(report['complete']);self.assertEqual(report['errors'],[])
            self.assertEqual(report['rpcCalls']['eth_getTransactionReceipt'],8)
            pair={q['token'] for q in spec['state']['quotes']};results=[]
            for item in spec['transactions']:
                data=json.loads(z.read('raw/'+item['transactionHash']+'.json'))
                row=corroborate(item['sample'],data['receipt'],data['block'],report['eventTopics'])
                row['routeConservation']=routes(row,pair);results.append(row)
            self.assertEqual(results,report['results'])
            actual=summarize(dict(complete=True,results=results),spec)
            self.assertEqual(actual,json.loads(z.read('route-summary.json')))
            self.assertEqual(actual,json.loads((ROOT/'bottleneck-result/route-summary.json').read_text()))
            self.assertEqual(actual['targetBuyAtOrBelowOwnBidSharesRaw'],0)
            self.assertEqual(actual['fillsCreated'],0)
            self.assertFalse(actual['observedActivationOrQueueProven'])
            self.assertFalse(actual['netPnlRecomputed'])
            self.assertFalse(actual['otherLegAudited']);self.assertFalse(actual['otherStatesAudited'])


if __name__=='__main__':unittest.main()
