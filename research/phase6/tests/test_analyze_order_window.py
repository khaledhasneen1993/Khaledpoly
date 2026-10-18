import unittest
from research.phase6.analyze_order_window import analyze
from research.phase6.receipt_audit import decode_matches
from research.phase6.tests import test_receipt_audit as fixture
import copy
import json
from pathlib import Path
from research.phase6.order_window import read_evidence


class AnalyzeWindowTest(unittest.TestCase):
    def evidence(self):
        books=[dict(kind='BOOK',data=dict(token=t,sourceMs=s,bids=[dict(price='.4',size='10')],
                                           asks=[dict(price='.8',size='10')])) for t,s in [('a',19),('b',19)]]
        trade=dict(kind='TRADE',data=dict(token='a',side='BUY',price='.4',size='1',sourceMs=18,tradeId='{}'))
        spec=dict(tokens=['a','b'],condition='m',orderIds=['o'],orders=[dict(id='o',buy=True,token='b',price='.6',activatedMs=10,terminalMs=30)])
        return dict(logicalTapeSha256='x',windows=[dict(spec=spec,rows=[dict(seq=1,arrivalMs=20,kind='RESEARCH_FRAME',data=dict(events=books+[trade]))])])

    def test_latest_book_inside_same_frame_is_not_earlier_than_old_trade(self):
        result=analyze(self.evidence(),dict(results=[]))
        observation=result['windows'][0]['complementTradesDuringRecordedActiveOrders'][0]
        self.assertTrue(observation['bothBooksFresh'])
        self.assertFalse(observation['tradeNotBeforeEitherBook'])
        self.assertFalse(observation['receiptAvailable'])
        self.assertFalse(result['fillsInferred'])

    def test_gap_and_terminal_boundaries_cannot_resurrect_orders(self):
        evidence=self.evidence();window=evidence['windows'][0]
        events=window['rows'][0]['data']['events']
        events.insert(2,dict(kind='GAP',data=dict(reason='disconnect')))
        result=analyze(evidence,dict(results=[]))
        self.assertFalse(result['windows'][0]['complementTradesDuringRecordedActiveOrders'][0]['bothBooksFresh'])
        window['spec']['orders'][0]['terminalMs']=20
        self.assertEqual(analyze(evidence,dict(results=[]))['windows'][0]['complementTradesDuringRecordedActiveOrders'],[])

    def test_one_receipt_portion_identity_not_recredited_on_duplicate_print(self):
        evidence=self.evidence();window=evidence['windows'][0];spec=window['spec']
        spec['tokens']=['11','22'];spec['orders'][0].update(token='11',price='.4',activatedMs=19)
        events=window['rows'][0]['data']['events']
        events[0]['data']['token']='11';events[1]['data']['token']='22'
        tx='0x'+'7'*64
        events[2]['data'].update(token='22',price='.6',tradeId=json.dumps({'transaction_hash':tx}))
        events.append(copy.deepcopy(events[2]))
        logs,topics=fixture.ReceiptAuditTest().logs()
        receipts=dict(results=[dict(transactionHash=tx,matches=decode_matches(logs,topics))])
        result=analyze(evidence,receipts)['windows'][0]
        observations=result['complementTradesDuringRecordedActiveOrders']
        self.assertFalse(observations[0]['sourceStrictlyAfterObservedActivation'])
        self.assertFalse(observations[0]['mintMakerPortions'][0]['alreadyObserved'])
        self.assertTrue(observations[1]['mintMakerPortions'][0]['alreadyObserved'])
        self.assertEqual(result['uniqueMintMakerIdentities'],1)

    def test_cancel_request_and_due_reported_without_extending_order_life(self):
        evidence=self.evidence()
        audit=dict(events=[dict(kind='CANCEL_REQUEST',at=15,data=dict(id='o'))])
        observation=analyze(evidence,dict(results=[]),audit=audit)['windows'][0]['complementTradesDuringRecordedActiveOrders'][0]
        self.assertFalse(observation['observedBeforeCancelRequest'])
        self.assertTrue(observation['observedBeforeCancelDue'])
        self.assertEqual(observation['cancelDueMsFromFrozen250ms'],265)
        evidence['windows'][0]['spec']['orders'][0]['terminalMs']=20
        self.assertEqual(analyze(evidence,dict(results=[]),audit=audit)['windows'][0]['complementTradesDuringRecordedActiveOrders'],[])

    def test_real_committed_window_and_cancel_audit_reproduce_diagnostic(self):
        folder=Path('research/experiments/order-window-20261018')
        evidence=read_evidence(folder/'evidence.json.gz.b64')
        receipts=json.loads(Path('research/experiments/candidate-receipt-audit-20261018/offline-volume-labels.json').read_text())
        audit=json.loads((folder/'baseline-order-audit.json').read_text())
        result=analyze(evidence,receipts,audit=audit)
        expected=json.loads((folder/'causal-diagnostic-with-cancels.json').read_text())
        self.assertEqual(result,expected)
        corroborated=[o for o in result['windows'][0]['complementTradesDuringRecordedActiveOrders'] if o['mintMakerPortions']]
        self.assertEqual(len(corroborated),5)
        self.assertTrue(all(o['observedBeforeCancelRequest'] and o['tradeNotBeforeEitherBook'] for o in corroborated))
        self.assertFalse(result['fillsInferred'])
