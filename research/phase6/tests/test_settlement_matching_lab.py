import copy
import json
from pathlib import Path
import unittest
import random
from research.phase6.settlement_matching_lab import Allocator, Order, D, validated_portions, trade_matches_sample, run
from research.phase6.order_window import read_evidence
from research.phase6.receipt_audit import decode_matches
from research.phase6.tests import test_receipt_audit as fixture


class SettlementLabTest(unittest.TestCase):
    def order(self, name='one', price='.64', size='5', ahead='0', terminal=100):
        return Order(name,'b',True,D(price),D(size),D(ahead),10,terminal)

    def portion(self, quantity='100', price='.63', number=1):
        return dict(identity=('exchange','tx',1,number),token='b',buy=True,
                    price=D(price),quantity=D(quantity),route='MINT')

    def accept(self, allocator, portions=None, at=20, source=19, books=None, **kwargs):
        if books is None:books={t:dict(sourceMs=18,bids=[1],asks=[1]) for t in ('a','b')}
        return allocator.accept(portions or [self.portion()],at=at,source=source,books=books,pair={'a','b'},**kwargs)

    def test_default_off_and_input_orders_never_mutated(self):
        order=self.order();allocator=Allocator([order])
        self.assertEqual(self.accept(allocator),[])
        enabled=Allocator([order],enabled=True)
        self.assertEqual(self.accept(enabled)[0]['quantity'],'5')
        self.assertEqual(order.remaining,D(5))
        self.assertEqual(order.ahead,D(0))

    def test_cross_price_priority_uses_one_volume_budget(self):
        allocator=Allocator([self.order(price='.64',size='3',ahead='2'),self.order('two',price='.63',size='5')],enabled=True)
        result=self.accept(allocator,[self.portion(quantity='5')])
        self.assertEqual([(r['orderId'],r['quantity']) for r in result],[('one','3')])
        self.assertEqual(allocator.audit[0]['queueAbsorbed'],'2')
        self.assertEqual(allocator.audit[0]['unused'],'0')

    def test_same_price_queue_prefix_is_not_counted_twice(self):
        allocator=Allocator([self.order(size='3',ahead='2'),self.order('two',size='3',ahead='5')],enabled=True)
        result=self.accept(allocator,[self.portion(quantity='6')])
        self.assertEqual([r['quantity'] for r in result],['3','1'])
        self.assertEqual(allocator.audit[0]['queueAbsorbed'],'2')

    def test_partial_fills_and_duplicates_cannot_reuse_volume(self):
        allocator=Allocator([self.order(size='5')],enabled=True)
        self.assertEqual(self.accept(allocator,[self.portion(quantity='2')])[0]['quantity'],'2')
        self.assertEqual(self.accept(allocator,[self.portion(quantity='2')]),[])
        self.assertEqual(self.accept(allocator,[self.portion(quantity='2',number=2)])[0]['quantity'],'2')
        self.assertEqual(allocator.orders[0].remaining,D(1))

    def test_cancel_due_and_activation_ties_do_not_fill(self):
        for at,source in [(30,29),(20,10)]:
            allocator=Allocator([self.order(terminal=30)],enabled=True)
            self.assertEqual(self.accept(allocator,at=at,source=source),[])

    def test_gap_stale_future_and_pre_current_book_are_not_eligible(self):
        for books,at,source in [({},20,19),
                ({t:dict(sourceMs=18,bids=[1],asks=[1]) for t in ('a','b')},3000,2999),
                ({t:dict(sourceMs=20,bids=[1],asks=[1]) for t in ('a','b')},20,19),
                ({t:dict(sourceMs=18,bids=[1],asks=[1]) for t in ('a','b')},20,21)]:
            allocator=Allocator([self.order(terminal=10000)],enabled=True)
            self.assertEqual(self.accept(allocator,books=books,at=at,source=source),[])

    def test_discarded_event_cannot_be_resurrected_after_activation(self):
        allocator=Allocator([self.order()],enabled=True)
        self.assertEqual(self.accept(allocator,at=9,source=8),[])
        self.assertEqual(self.accept(allocator,at=20,source=19),[])

    def test_gap_and_stale_invalidation_survive_fresh_book_recovery(self):
        allocator=Allocator([self.order()],enabled=True)
        allocator.invalidate({'a','b'},15)
        self.assertEqual(self.accept(allocator),[])
        allocator=Allocator([self.order()],enabled=True)
        allocator.advance(15,{})
        self.assertEqual(self.accept(allocator),[])
        with self.assertRaises(ValueError):allocator.advance(14,{})

    def test_aggregate_plus_components_and_duplicate_batch_rejected(self):
        allocator=Allocator([self.order()],enabled=True)
        with self.assertRaises(ValueError):self.accept(allocator,legacy_aggregate_used=True)
        with self.assertRaises(ValueError):self.accept(allocator,[self.portion(),self.portion()])

    def receipt(self):
        logs,topics=fixture.ReceiptAuditTest().logs()
        return dict(transactionHash='tx',sample=dict(asset_id='22',side='BUY',size='1'),matches=decode_matches(logs,topics))

    def test_receipt_shares_and_collateral_conservation_both_required(self):
        result=self.receipt();self.assertEqual(validated_portions(result,{'11','22'})[0]['quantity'],D(1))
        for key in ('makingRaw','takingRaw'):
            changed=copy.deepcopy(result);changed['matches'][0]['maker'][key]+=1
            with self.assertRaises(ValueError):validated_portions(changed,{'11','22'})

    def test_mixed_direct_and_mint_parts_replace_not_duplicate_aggregate(self):
        result=self.receipt();mint=result['matches'][0]
        mint['maker'].update(makingRaw=200000,takingRaw=500000)
        direct=copy.deepcopy(mint);direct['matchType']='DIRECT'
        direct['maker'].update(token='22',side='SELL',makingRaw=500000,takingRaw=300000,logIndex=4)
        result['matches'].append(direct)
        portions=validated_portions(result,{'11','22'})
        orders=[Order('buy','11',True,D('.4'),D(1),D(0),10,100),Order('sell','22',False,D('.6'),D(1),D(0),10,100)]
        allocator=Allocator(orders,enabled=True)
        books={t:dict(sourceMs=18,bids=[1],asks=[1]) for t in ('11','22')}
        allocations=allocator.accept(portions,at=20,source=19,books=books,pair={'11','22'})
        self.assertEqual(sum(D(a['quantity']) for a in allocations),D(1))

    def test_untrusted_duplicate_and_ambiguous_receipt_groups_rejected(self):
        result=self.receipt();result['matches'][0]['exchange']='unknown'
        with self.assertRaises(ValueError):validated_portions(result,{'11','22'})
        result=self.receipt();result['matches']*=2
        with self.assertRaises(ValueError):validated_portions(result,{'11','22'})
        result=self.receipt();other=copy.deepcopy(result['matches'][0]);other['ordersMatchedLogIndex']+=1;result['matches'].append(other)
        with self.assertRaises(ValueError):validated_portions(result,{'11','22'})

    def test_randomized_multi_order_bursts_conserve_every_component(self):
        generator=random.Random(419)
        for scenario in range(100):
            orders=[self.order(str(i),price=str(D('.64')-D(i%3)/100),size=str(generator.randint(1,9)),
                               ahead=str(2*generator.randint(0,20))) for i in range(8)]
            allocator=Allocator(orders,enabled=True)
            for number in range(5):
                quantity=generator.randint(1,80)
                self.accept(allocator,[self.portion(quantity=str(quantity),price='.60',number=number)],at=20+number,source=19+number)
                observation=allocator.audit[-1]
                self.assertEqual(sum(D(observation[k]) for k in ('allocated','queueAbsorbed','unused')),D(quantity))
                self.assertTrue(all(o.ahead>=0 and o.remaining>=0 for o in allocator.orders))

    def test_real_fixed_lifecycle_calibration_is_not_pnl_or_closed_loop(self):
        folder=Path('research/experiments/order-window-20261018')
        evidence=read_evidence(folder/'evidence.json.gz.b64')
        receipts=json.loads(Path('research/experiments/candidate-receipt-audit-20261018/offline-volume-labels.json').read_text())
        audit=json.loads((folder/'baseline-order-audit.json').read_text())
        off=run(evidence,receipts,audit);on=run(evidence,receipts,audit,enabled=True)
        self.assertEqual(off['conditionalAllocatedShares'],'0')
        self.assertEqual(len(on['bindings']),5)
        allocations=[a for w in on['windows'] for a in w['conditionalAllocations']]
        self.assertEqual([(a['orderId'],a['quantity'],a['at']) for a in allocations],[('sim-research-4','5',1792269683761)])
        self.assertIsNone(on['netPnlAfterCosts'])
        self.assertFalse(on['independentPaperQualificationAllowed'])
        self.assertFalse(on['actualBotFillsAsserted'])
        self.assertFalse(on['accountMutated'])
        changed=copy.deepcopy(audit);changed['events'][0]['data']['quantity']=6
        with self.assertRaises(ValueError):run(evidence,receipts,changed,enabled=True)

    def test_binding_requires_exact_normalized_and_original_public_fields(self):
        folder=Path('research/experiments/order-window-20261018')
        evidence=read_evidence(folder/'evidence.json.gz.b64')
        receipts=json.loads(Path('research/experiments/candidate-receipt-audit-20261018/offline-volume-labels.json').read_text())
        result=next(r for r in receipts['results'] if r['transactionHash']=='0xeff5d430a86833db0aa6e5bcda6af787a62ba94765d2b33ebb003864718fec57')
        data=next(e['data'] for w in evidence['windows'] for r in w['rows'] if r['kind']=='RESEARCH_FRAME'
                  for e in r['data']['events'] if e['kind']=='TRADE' and trade_matches_sample(e['data'],result))
        for key,value in [('sourceMs',data['sourceMs']+1),('price','.38'),('size','101')]:
            changed=copy.deepcopy(data);changed[key]=value
            self.assertFalse(trade_matches_sample(changed,result))
