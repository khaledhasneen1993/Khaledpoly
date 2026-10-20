import copy
from decimal import Decimal as D
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from research.phase6.postactivation_receipts import selection,decode,collect
from research.phase6.receipt_audit import EXCHANGES


class TwoOriginalReceiptTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.spec=selection()

    def fixture(self,item):
        spec=self.spec;address=sorted(EXCHANGES)[0];wallet='0x'+'0'*24+'c'*40;maker='0x'+'a'*64;taker='0x'+'b'*64
        encode=lambda xs:'0x'+''.join(format(x,'064x') for x in xs)
        token=int(item['sample']['asset_id']);other=int(next(p for p in spec['pair'] if int(p)!=token));q=int(D(item['sample']['size'])*1000000);c=int(D(item['sample']['price'])*q);tx=item['transactionHash'];block='0x'+'9'*64
        rows=[dict(logIndex='0x1',address=address,topics=[spec['topics']['filled'],maker,'0x'+'0'*24+'d'*40,wallet],data=encode([0,other,q-c,q,0,0,0])),dict(logIndex='0x2',address=address,topics=[spec['topics']['filled'],taker,wallet,'0x'+'0'*24+address[2:]],data=encode([0,token,c,q,0,0,0])),dict(logIndex='0x3',address=address,topics=[spec['topics']['matched'],taker,wallet],data=encode([0,token,c,q]))]
        for row in rows:row['transactionHash']=tx
        # Same synthetic block for both transactions; timestamp within120s of both original sources.
        return dict(receipt=dict(transactionHash=tx,status='0x1',blockHash=block,logs=rows),block=dict(hash=block,timestamp=hex(1792269595)))

    def test_exact_actual_selection(self):
        self.assertEqual([x['seq'] for x in self.spec['transactions']],[9035,82964]);self.assertEqual(self.spec['maxNewReceiptRequests'],2)

    def test_changed_selection_no_network(self):
        bad=copy.deepcopy(self.spec);bad['maxNewReceiptRequests']=3
        with tempfile.TemporaryDirectory() as tmp,patch('research.phase6.postactivation_receipts.selection',return_value=self.spec):
            with self.assertRaises(ValueError):collect(bad,tmp,read=lambda *_:self.fail('network'))

    def test_synthetic_routes_checkpoint_and_shared_block_budget(self):
        data={x['transactionHash']:self.fixture(x) for x in self.spec['transactions']}
        def read(method,args):
            if method=='eth_chainId':return '0x89'
            if method=='eth_getTransactionReceipt':return data[args[0]]['receipt']
            return next(iter(data.values()))['block']
        with tempfile.TemporaryDirectory() as tmp,patch('research.phase6.postactivation_receipts.selection',return_value=self.spec):
            r=collect(self.spec,tmp,read=read);self.assertEqual(r['rpcCalls'],{'eth_chainId':1,'eth_getTransactionReceipt':2,'eth_getBlockByHash':1});self.assertEqual(r['modelFillsCreated'],0)
            resumed=collect(self.spec,tmp,read=lambda method,_:'0x89' if method=='eth_chainId' else self.fail('successful read repeated'));self.assertEqual(resumed['rpcCalls'],{'eth_chainId':1})

    def test_failed_block_preserves_both_receipts(self):
        data={x['transactionHash']:self.fixture(x) for x in self.spec['transactions']}
        def broken(method,args):
            if method=='eth_getBlockByHash':raise OSError('SYNTHETIC transient failure')
            return '0x89' if method=='eth_chainId' else data[args[0]]['receipt']
        with tempfile.TemporaryDirectory() as tmp,patch('research.phase6.postactivation_receipts.selection',return_value=self.spec):
            with self.assertRaises(ValueError):collect(self.spec,tmp,read=broken)
            for tx in data:self.assertIn('receipt',json.loads((Path(tmp)/'raw'/(tx+'.json')).read_bytes()))
            def resumed(method,args):
                if method=='eth_getTransactionReceipt':self.fail('receipt refetched')
                return '0x89' if method=='eth_chainId' else next(iter(data.values()))['block']
            r=collect(self.spec,tmp,read=resumed);self.assertEqual(r['rpcCalls'],{'eth_chainId':1,'eth_getBlockByHash':1})

    def test_bad_chain_status_and_source_time_rejected(self):
        item=self.spec['transactions'][0];data=self.fixture(item)
        for key,value in [('status','0x0'),('transactionHash','0x'+'0'*64)]:
            bad=copy.deepcopy(data);bad['receipt'][key]=value
            with self.assertRaises(ValueError):decode(self.spec,item,bad)
        bad=copy.deepcopy(data);bad['block']['timestamp']='0x1'
        with self.assertRaises(ValueError):decode(self.spec,item,bad)
        with tempfile.TemporaryDirectory() as tmp,patch('research.phase6.postactivation_receipts.selection',return_value=self.spec):
            with self.assertRaises(ValueError):collect(self.spec,tmp,read=lambda *_:'0x1')
            self.assertEqual(json.loads((Path(tmp)/'report.json').read_bytes())['rpcCalls'],{'eth_chainId':1})
