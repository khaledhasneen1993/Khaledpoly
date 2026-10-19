import base64
import hashlib
import io
import json
import unittest
import zipfile
from research.phase6.dq3_last_selected_leg import ROOT,previous_evidence,next_selection,coverage


class LastLegResultTest(unittest.TestCase):
    def test_redecode_all19_receipts_and_close_only_selected_necessary_legs(self):
        raw=base64.b64decode((ROOT/'last-leg-result/artifact.zip.b64').read_bytes())
        self.assertEqual(hashlib.sha256(raw).hexdigest(),'3da8eced1b9824d1b2e86641fad7754c2a1fad817d6a45a4d4094bd534c9fabd')
        evidence=previous_evidence();spec=next_selection(evidence)
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            self.assertEqual(len(z.infolist()),23)
            self.assertEqual(json.loads(z.read('selection.json')),spec)
            r=json.loads(z.read('report.json'));self.assertTrue(r['complete']);self.assertEqual(r['errors'],[])
            self.assertEqual(r['rpcCalls'],dict(eth_chainId=1,eth_getTransactionReceipt=19,eth_getBlockByHash=10))
            for t in spec['transactions']:
                tx=t['transactionHash'];self.assertNotIn(tx,evidence)
                data=json.loads(z.read('raw/'+tx+'.json'));evidence[tx]=dict(data=data,topics=r['eventTopics'])
            actual=coverage(evidence)  # Independently re-decode and conserve each component.
            self.assertEqual(actual,json.loads(z.read('complete-selected-legs-coverage.json')))
            self.assertEqual(actual,json.loads((ROOT/'last-leg-result/coverage.json').read_text()))
        self.assertEqual(actual['receiptCacheTransactions'],68)
        complete=[l for l in actual['legs'] if l['complete']];self.assertEqual(len(complete),11)
        last=next(l for l in complete if l['originalSequence']==299650)
        self.assertEqual(last['actualPriceCompatibleSharesRaw'],639910619)
        self.assertTrue(all(l['actualPriceCompatibleSharesRaw'] is None for l in actual['legs'] if not l['complete']))
        self.assertEqual(actual['fillsCreated'],0);self.assertFalse(actual['netPnlRecomputed'])


if __name__=='__main__':unittest.main()
