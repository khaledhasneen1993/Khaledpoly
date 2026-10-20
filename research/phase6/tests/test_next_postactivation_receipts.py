import copy
from decimal import Decimal as D
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from research.phase6.next_postactivation_receipts import selection,decode,collect
from research.phase6.receipt_audit import EXCHANGES


class NextTwoReceiptTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.spec=selection()

    def fixture(self,item):
        spec=self.spec;address=sorted(EXCHANGES)[0];wallet='0x'+'0'*24+'c'*40;maker='0x'+'a'*64;taker='0x'+'b'*64
        encode=lambda xs:'0x'+''.join(format(x,'064x') for x in xs)
        token=int(item['sample']['asset_id']);other=int(next(p for p in spec['pair'] if int(p)!=token));q=int(D(item['sample']['size'])*1000000);c=int(D(item['sample']['price'])*q);tx=item['transactionHash'];block='0x'+'9'*64
        rows=[dict(logIndex='0x1',address=address,topics=[spec['topics']['filled'],maker,'0x'+'0'*24+'d'*40,wallet],data=encode([0,other,q-c,q,0,0,0])),dict(logIndex='0x2',address=address,topics=[spec['topics']['filled'],taker,wallet,'0x'+'0'*24+address[2:]],data=encode([0,token,c,q,0,0,0])),dict(logIndex='0x3',address=address,topics=[spec['topics']['matched'],taker,wallet],data=encode([0,token,c,q]))]
        for row in rows:row['transactionHash']=tx
        return dict(receipt=dict(transactionHash=tx,status='0x1',blockHash=block,logs=rows),block=dict(hash=block,timestamp=hex(int(item['sample']['timestamp'])//1000)))

    def test_exact_retained_targets(self):
        self.assertEqual([x['seq'] for x in self.spec['transactions']],[9060,82986]);self.assertEqual(self.spec['maxNewReceiptRequests'],2)
        self.assertEqual(self.spec['sourceReplayArtifactSha256'],'ae76233de5e1ec7f209508aca9499afa2cf98184f173c4d398f8424d837b40a3')

    def test_changed_selection_no_network(self):
        bad=copy.deepcopy(self.spec);bad['maxNewReceiptRequests']=3
        with tempfile.TemporaryDirectory() as tmp,patch('research.phase6.next_postactivation_receipts.selection',return_value=self.spec):
            with self.assertRaises(ValueError):collect(bad,tmp,read=lambda *_:self.fail('network'))

    def test_synthetic_routes_checkpoint_and_shared_block_budget(self):
        data={x['transactionHash']:self.fixture(x) for x in self.spec['transactions']}
        def read(method,args):
            if method=='eth_chainId':return '0x89'
            if method=='eth_getTransactionReceipt':return data[args[0]]['receipt']
            return data[self.spec['transactions'][0]['transactionHash']]['block']
        # Use separate actual blocks so the fixture remains source-time valid.
        data[self.spec['transactions'][1]['transactionHash']]['receipt']['blockHash']='0x'+'8'*64
        data[self.spec['transactions'][1]['transactionHash']]['block']['hash']='0x'+'8'*64
        def bounded(method,args):
            if method=='eth_chainId':return '0x89'
            if method=='eth_getTransactionReceipt':return data[args[0]]['receipt']
            return next(v['block'] for v in data.values() if v['block']['hash'].lower()==args[0].lower())
        with tempfile.TemporaryDirectory() as tmp,patch('research.phase6.next_postactivation_receipts.selection',return_value=self.spec):
            r=collect(self.spec,tmp,read=bounded);self.assertEqual(r['rpcCalls'],{'eth_chainId':1,'eth_getTransactionReceipt':2,'eth_getBlockByHash':2});self.assertEqual(r['modelFillsCreated'],0)
            resumed=collect(self.spec,tmp,read=lambda method,_:'0x89' if method=='eth_chainId' else self.fail('successful read repeated'));self.assertEqual(resumed['rpcCalls'],{'eth_chainId':1})

    def test_bad_chain_status_and_time_rejected(self):
        item=self.spec['transactions'][0];data=self.fixture(item)
        for key,value in [('status','0x0'),('transactionHash','0x'+'0'*64)]:
            bad=copy.deepcopy(data);bad['receipt'][key]=value
            with self.assertRaises(ValueError):decode(self.spec,item,bad)
        bad=copy.deepcopy(data);bad['block']['timestamp']='0x1'
        with self.assertRaises(ValueError):decode(self.spec,item,bad)
        with tempfile.TemporaryDirectory() as tmp,patch('research.phase6.next_postactivation_receipts.selection',return_value=self.spec):
            with self.assertRaises(ValueError):collect(self.spec,tmp,read=lambda *_:'0x1')
            self.assertEqual(json.loads((Path(tmp)/'report.json').read_bytes())['rpcCalls'],{'eth_chainId':1})
