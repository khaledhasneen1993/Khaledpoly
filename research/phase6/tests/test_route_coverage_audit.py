import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from research.phase6.route_coverage_audit import routes, collect
from research.phase6.receipt_audit import EXCHANGES
from research.phase6.tests import test_receipt_audit as fixtures


class RouteCoverageAuditTest(unittest.TestCase):
    def group(self, buy, route):
        taker=dict(token='22',side='BUY' if buy else 'SELL',makingRaw=600000 if buy else 1000000,
            takingRaw=1000000 if buy else 400000,orderHash='0x'+'a'*64)
        complementary=route!='DIRECT'
        maker=dict(token='11' if complementary else '22',
            side=taker['side'] if complementary else 'SELL' if buy else 'BUY',logIndex=2)
        maker_buy=maker['side']=='BUY';cost=400000 if maker_buy else 600000
        maker.update(makingRaw=cost if maker_buy else 1000000,takingRaw=1000000 if maker_buy else cost)
        return dict(sample=dict(asset_id='22',side=taker['side'],size='1'),matches=[dict(
            exchange=sorted(EXCHANGES)[0],ordersMatchedLogIndex=3,taker=taker,maker=maker,matchType=route)])

    def test_buy_sell_direct_mint_merge_each_conserve_both_units(self):
        for buy,route in [(True,'MINT'),(True,'DIRECT'),(False,'DIRECT'),(False,'MERGE')]:
            result=routes(self.group(buy,route),{'11','22'})
            self.assertTrue(result['uniqueConservedGroup'])
            self.assertEqual(result['matchingGroups'][0]['routeSharesRaw'],{route:1000000})
            self.assertFalse(result['queueAllocationProven']);self.assertEqual(result['fillsCreated'],0)

    def test_collateral_share_and_duplicate_fail_closed(self):
        for mutate in [lambda r:r['matches'][0]['taker'].update(makingRaw=600001),
                       lambda r:r['matches'][0]['maker'].update(takingRaw=1000001),
                       lambda r:r['matches'].append(copy.deepcopy(r['matches'][0]))]:
            result=self.group(True,'MINT');mutate(result)
            with self.assertRaises(ValueError):routes(result,{'11','22'})

    def test_cached_receipt_and_resume_make_only_public_chain_read(self):
        with tempfile.TemporaryDirectory() as folder:
            logs,topics=fixtures.ReceiptAuditTest().logs();tx='0x'+'7'*64;block_hash='0x'+'8'*64
            for log in logs:log['transactionHash']=tx
            cached=Path(folder)/'cached.json'
            cached.write_text(json.dumps(dict(receipt=dict(transactionHash=tx,status='0x1',blockHash=block_hash,logs=logs),
                block=dict(hash=block_hash,timestamp='0x1'))))
            sample=dict(transaction_hash=tx,asset_id='22',side='BUY',size='1',price='.6',timestamp='1000',arrivalMs=1100)
            selection=dict(cohorts=[dict(role='r',transactions=[tx],orderDiagnostic=dict(activatedMs=1000,terminalMs=1200))],
                transactions=[dict(transactionHash=tx,sample=sample,roles=['r'],existingCachedReceipt=str(cached))],maxNewReceiptRequests=0)
            read=Mock(return_value='0x89');out=Path(folder)/'out'
            for _ in range(2):
                result=collect(selection,out,{'11','22'},topics=topics,read=read)
                self.assertTrue(result['complete']);self.assertEqual(result['uniqueConservedGroups'],1)
                self.assertEqual(result['rpcCalls'],{'eth_chainId':1})
            self.assertEqual(read.call_args_list,[unittest.mock.call('eth_chainId',[])]*2)
            bad=copy.deepcopy(selection);bad['transactions'][0]['sample']['timestamp']='999'
            with self.assertRaises(ValueError):collect(bad,out,{'11','22'},topics=topics,read=read)
            self.assertEqual(read.call_count,2)
