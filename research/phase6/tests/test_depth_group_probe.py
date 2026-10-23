import unittest
from research.phase6.depth_group_probe import Probe


class DepthGroupProbeTest(unittest.TestCase):
    def probe(self, enabled=False):
        return Probe('a',dict(event_type='book',asset_id='a',timestamp='1000',
            bids=[dict(price='.51',size='5'),dict(price='.5',size='4'),dict(price='.49',size='3')],
            asks=[dict(price='.66',size='2')]),1000,enabled)

    def delta(self, side, price, size, source='1010', hash='a'*40, bid='.49',ask='.5'):
        return dict(event_type='price_change',timestamp=source,price_changes=[dict(asset_id='a',
            side=side,price=price,size=size,hash=hash,best_bid=bid,best_ask=ask)])

    def test_default_off_and_real_removals_needed_before_candidate(self):
        first=self.delta('SELL','.5','2')
        self.assertEqual(self.probe().accept(first,1010)['status'],'WAIT_FULL_SNAPSHOT')
        p=self.probe(True);self.assertEqual(p.accept(first,1010)['status'],'QUARANTINED')
        self.assertEqual(p.accept(self.delta('BUY','.51','0'),1012)['status'],'QUARANTINED')
        r=p.accept(self.delta('BUY','.5','0'),1013)
        self.assertEqual(r['status'],'RECOVERY_CANDIDATE');self.assertEqual(r['delayMs'],3)
        self.assertFalse(r['bookPublished']);self.assertFalse(r['priorGapRetracted'])
        self.assertFalse(r['hashCryptographicallyVerified'])

    def test_hash_timestamp_hints_and_deadline_changes_fail_closed(self):
        for delta,at in [(self.delta('BUY','.51','0',hash='b'*40),1012),
                         (self.delta('BUY','.51','0',source='1011'),1012),
                         (self.delta('BUY','.51','0',bid='.48'),1012),
                         (self.delta('BUY','.51','0'),1261)]:
            p=self.probe(True);p.accept(self.delta('SELL','.5','2'),1010)
            self.assertEqual(p.accept(delta,at)['status'],'WAIT_FULL_SNAPSHOT')

    def test_hint_alone_never_deletes_unreported_levels(self):
        p=self.probe(True);p.accept(self.delta('SELL','.5','2'),1010)
        self.assertEqual(p.accept(self.delta('SELL','.5','2'),1011)['status'],'QUARANTINED')
        self.assertIn(__import__('decimal').Decimal('.51'),p.pending['book']['bids'])
        self.assertEqual(p.accept(self.delta('BUY','.51','0',hash=''),1012)['status'],'WAIT_FULL_SNAPSHOT')

    def test_snapshot_and_clock_prerequisites(self):
        p=self.probe(True)
        self.assertEqual(p.accept(self.delta('BUY','.4','2',source='999'),1010)['status'],'WAIT_FULL_SNAPSHOT')
        p=self.probe(True)
        self.assertEqual(p.accept(self.delta('BUY','.4','2',source='1011'),1010)['status'],'WAIT_FULL_SNAPSHOT')

    def test_non_crossed_but_hint_inconsistent_prefix_remains_unverified(self):
        p=self.probe(True)
        self.assertEqual(p.accept(self.delta('BUY','.4','2',bid='.49',ask='.66'),1010)['status'],'QUARANTINED')
        self.assertIsNotNone(p.pending)

    def test_recorded_four_cases_use_an_independent_snapshot_clock_per_mode(self):
        from research.phase6.run_depth_group_probe import run
        r=run()
        self.assertEqual(r['baselineInvalidations'],4)
        self.assertEqual(r['recoveryCandidates'],4)
        self.assertEqual(r['unverifiedPrefixCases'],0)
        self.assertEqual([x['outcomes']['quarantineCandidate']['delayMs'] for x in r['cases']],[3,3,2,2])
        for case in r['cases']:
            self.assertTrue(case['outcomes']['quarantineCandidate']['confirmationFullDepthEqual'])
            self.assertTrue(case['outcomes']['quarantineCandidate']['confirmationSourceAndHashEqual'])
            self.assertEqual(case['outcomes']['quarantineCandidate']['latencyGainMs'],0)
        self.assertFalse(r['candidateWorthIndependentTest'])
        self.assertEqual(r,run())
        self.assertFalse(r['productionEnabled']);self.assertEqual(r['fillsCreated'],0)
        self.assertFalse(r['netPnlRecomputed']);self.assertFalse(r['historicalGapOrMarkoutRetracted'])
