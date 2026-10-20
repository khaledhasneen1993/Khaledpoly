import copy
import json
from pathlib import Path
import tempfile
import unittest
from research.phase6.first_blocker_receipt import ROOT,retained,selection,collect,decode
from research.phase6.receipt_audit import EXCHANGES

class FirstBlockerReceiptTest(unittest.TestCase):
    def fixture(self,spec):
        # Synthetic ABI fixture ONLY: no market result is produced by these tests.
        address=sorted(EXCHANGES)[0];wallet='0x'+'0'*24+'c'*40
        maker='0x'+'a'*64;taker='0x'+'b'*64;tx=spec['transactionHash'];block='0x'+'9'*64
        encode=lambda xs:'0x'+''.join(format(x,'064x') for x in xs)
        token=int(spec['sample']['asset_id']);other=int(next(p for p in spec['pair'] if int(p)!=token))
        filled=spec['topics']['filled'];matched=spec['topics']['matched']
        rows=[dict(logIndex='0x1',address=address,topics=[filled,maker,'0x'+'0'*24+'d'*40,wallet],data=encode([0,other,86_000_000,200_000_000,0,0,0])),
              dict(logIndex='0x2',address=address,topics=[filled,taker,wallet,'0x'+'0'*24+address[2:]],data=encode([0,token,114_000_000,200_000_000,0,0,0])),
              dict(logIndex='0x3',address=address,topics=[matched,taker,wallet],data=encode([0,token,114_000_000,200_000_000]))]
        for row in rows:row['transactionHash']=tx
        return dict(receipt=dict(transactionHash=tx,status='0x1',blockHash=block,logs=rows),block=dict(hash=block,timestamp=hex(1792269588)))

    def test_exact_retained_proof_and_single_source_selection(self):
        proof,source,expected=retained();self.assertEqual(source['seq'],97);self.assertEqual(source['eventIndex'],0)
        self.assertTrue(proof['noOrdersOrExecutionsBeforeBlocker']);self.assertFalse(proof['noOrderOptimizationProven'])
        s=selection();self.assertEqual(s['maxNewReceiptRequests'],1);self.assertEqual(s['sample']['transaction_hash'],expected['transactionHash'])
        self.assertFalse(s['marketNetPnlRecomputed']);self.assertFalse(s['liveAllowed'])

    def test_changed_proof_or_selection_rejected_before_network(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'bad.zip';path.write_bytes((ROOT/'original-diagnosis.zip').read_bytes()+b'x')
            with self.assertRaisesRegex(ValueError,'artifact'):retained(path)
            bad=selection();bad['maxNewReceiptRequests']=2
            with self.assertRaisesRegex(ValueError,'exact frozen'):collect(bad,Path(temp)/'out',read=lambda *_:self.fail('network'))

    def test_synthetic_conserved_route_and_one_receipt_budget(self):
        s=selection();data=self.fixture(s);calls=[]
        def read(method,params):
            calls.append((method,params));return {'eth_chainId':'0x89','eth_getTransactionReceipt':data['receipt'],'eth_getBlockByHash':data['block']}[method]
        with tempfile.TemporaryDirectory() as temp:
            r=collect(s,temp,read=read);self.assertTrue(r['complete']);self.assertEqual(r['route']['fillsCreated'],0)
            self.assertEqual(r['rpcCalls'],{'eth_chainId':1,'eth_getTransactionReceipt':1,'eth_getBlockByHash':1})
            calls.clear();resumed=collect(s,temp,read=read);self.assertEqual(resumed['rpcCalls'],{'eth_chainId':1})
        self.assertEqual([m for m,_ in calls],['eth_chainId'])

    def test_block_failure_preserves_receipt_without_refetch(self):
        s=selection();data=self.fixture(s)
        def broken(method,params):
            if method=='eth_getBlockByHash':raise OSError('SYNTHETIC transient block failure')
            return '0x89' if method=='eth_chainId' else data['receipt']
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError,'unresolved'):collect(s,temp,read=broken)
            self.assertEqual(json.loads((Path(temp)/'raw.json').read_text())['receipt'],data['receipt'])
            def resumed(method,params):
                if method=='eth_getTransactionReceipt':self.fail('successful receipt refetched')
                return '0x89' if method=='eth_chainId' else data['block']
            r=collect(s,temp,read=resumed);self.assertTrue(r['complete']);self.assertEqual(r['rpcCalls'],{'eth_chainId':1,'eth_getBlockByHash':1})

    def test_bad_chain_and_unconserved_receipt_never_become_labels(self):
        s=selection();data=self.fixture(s);bad=copy.deepcopy(data);bad['receipt']['status']='0x0'
        with self.assertRaisesRegex(ValueError,'status'):decode(s,bad)
        bad=copy.deepcopy(data);bad['receipt']['logs'].append(bad['receipt']['logs'][0])
        with self.assertRaisesRegex(ValueError,'Duplicate'):decode(s,bad)
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError,'unresolved'):collect(s,temp,read=lambda *_:'0x1')
            r=json.loads((Path(temp)/'report.json').read_text());self.assertFalse(r['complete']);self.assertEqual(r['rpcCalls'],{'eth_chainId':1})

if __name__=='__main__':unittest.main()
