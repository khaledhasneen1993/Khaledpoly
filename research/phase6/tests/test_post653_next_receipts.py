import copy
from decimal import Decimal as D
import tempfile
import unittest
from unittest.mock import patch

from research.phase6.post653_next_receipts import selection,decode,collect
from research.phase6.receipt_audit import EXCHANGES


class Post653NextReceiptsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.spec=selection()

    def fixture(self,item):
        spec=self.spec;address=sorted(EXCHANGES)[0];wallet='0x'+'0'*24+'c'*40;maker='0x'+'a'*64;taker='0x'+'b'*64
        encode=lambda xs:'0x'+''.join(format(x,'064x') for x in xs);token=int(item['sample']['asset_id']);other=token+1;q=int(D(item['sample']['size'])*1000000);c=int(D(item['sample']['price'])*q);tx=item['transactionHash'];block='0x'+'9'*64
        rows=[dict(logIndex='0x1',address=address,topics=[spec['topics']['filled'],maker,'0x'+'0'*24+'d'*40,wallet],data=encode([0,other,q-c,q,0,0,0])),dict(logIndex='0x2',address=address,topics=[spec['topics']['filled'],taker,wallet,'0x'+'0'*24+address[2:]],data=encode([0,token,c,q,0,0,0])),dict(logIndex='0x3',address=address,topics=[spec['topics']['matched'],taker,wallet],data=encode([0,token,c,q]))]
        for row in rows:row['transactionHash']=tx
        return dict(receipt=dict(transactionHash=tx,status='0x1',blockHash=block,logs=rows),block=dict(hash=block,timestamp=hex(int(item['sample']['timestamp'])//1000)))

    def test_exact_retained_targets(self):
        self.assertEqual([x['seq'] for x in self.spec['transactions']],[9379,83158]);self.assertEqual(self.spec['maxNewReceiptRequests'],2)
        self.assertEqual(len(set(self.spec['conditions'])),1)
        self.assertEqual(self.spec['sourceReplayArtifactSha256'],'46eb57490c0b64e2f21ed89d3ee04fcf827100a679972e28ca5a8f91b754e142')

    def test_changed_selection_no_network(self):
        bad=copy.deepcopy(self.spec);bad['maxNewReceiptRequests']=3
        with tempfile.TemporaryDirectory() as tmp,patch('research.phase6.post653_next_receipts.selection',return_value=self.spec):
            with self.assertRaises(ValueError):collect(bad,tmp,read=lambda *_:self.fail('network'))

    def test_synthetic_routes_and_bounded_reads(self):
        data={x['transactionHash']:self.fixture(x) for x in self.spec['transactions']};data[self.spec['transactions'][1]['transactionHash']]['receipt']['blockHash']='0x'+'8'*64;data[self.spec['transactions'][1]['transactionHash']]['block']['hash']='0x'+'8'*64
        def read(method,args):
            if method=='eth_chainId':return '0x89'
            if method=='eth_getTransactionReceipt':return data[args[0]]['receipt']
            return next(v['block'] for v in data.values() if v['block']['hash'].lower()==args[0].lower())
        with tempfile.TemporaryDirectory() as tmp,patch('research.phase6.post653_next_receipts.selection',return_value=self.spec):
            r=collect(self.spec,tmp,read=read);self.assertEqual(r['rpcCalls'],{'eth_chainId':1,'eth_getTransactionReceipt':2,'eth_getBlockByHash':2});self.assertEqual(r['modelFillsCreated'],0)

    def test_bad_receipt_and_time_rejected(self):
        item=self.spec['transactions'][0];data=self.fixture(item);bad=copy.deepcopy(data);bad['receipt']['status']='0x0'
        with self.assertRaises(ValueError):decode(self.spec,item,bad)
        bad=copy.deepcopy(data);bad['block']['timestamp']='0x1'
        with self.assertRaises(ValueError):decode(self.spec,item,bad)


if __name__=='__main__':unittest.main()
