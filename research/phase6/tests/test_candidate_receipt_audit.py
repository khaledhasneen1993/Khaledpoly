import copy
import json
from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch
from research.phase6.candidate_receipt_audit import select_samples, label_candidate, revalidate_saved
from research.phase6.receipt_audit import decode_matches
from research.phase6.tests import test_receipt_audit as fixture


class CandidateAuditTest(unittest.TestCase):
    def report(self):
        return json.loads(Path('research/experiments/transaction-linked-census-20261018/original.json').read_text())

    def test_first_five_unique_legacy_candidates_are_outcome_blind(self):
        report = self.report()
        selected = select_samples(report, 'original')
        self.assertEqual(len(selected), 5)
        self.assertEqual(len({s['transaction_hash'] for s in selected}), 5)
        self.assertEqual([int(s['timestamp']) for s in selected], sorted(int(s['timestamp']) for s in selected))
        report['examples'].reverse()
        self.assertEqual(selected, select_samples(report, 'original'))

    def test_fail_closed_on_truncation_count_and_pair_mismatch(self):
        report = self.report(); report['examplesTruncated'] = True
        with self.assertRaises(ValueError): select_samples(report, 'original')
        report = self.report(); report['complementBuyCandidateCounts']['1']['NECESSARY_CONDITIONS_ONLY'] += 1
        with self.assertRaises(ValueError): select_samples(report, 'original')
        report = self.report()
        for row in report['examples']: row['secondToken'] = row['firstToken']
        with self.assertRaises(ValueError): select_samples(report, 'original')

    def matches(self):
        logs, topics = fixture.ReceiptAuditTest().logs()
        return decode_matches(logs, topics)

    def sample(self):
        return {'side':'BUY','asset_id':'22','price':'.6','size':'1','targetToken':'11','targetPrice':'.4'}

    def test_one_mint_portion_not_aggregate_plus_maker(self):
        label = label_candidate(self.sample(), self.matches())
        self.assertTrue(label['uniqueConservedGroup'])
        group = label['matchingGroups'][0]
        self.assertEqual(group['targetMintSharesAtImpliedPrice'], '1')
        self.assertEqual(group['makerSharesSum'], '1')
        self.assertFalse(label['queueAllocationProven'])
        self.assertFalse(label['usableAsEarlierDecisionFeature'])

    def test_mixed_route_does_not_credit_direct_shares_to_mint(self):
        rows = self.matches(); rows[0]['maker']['takingRaw'] = 400000
        rows[0]['maker']['makingRaw'] = 160000
        direct = copy.deepcopy(rows[0]); direct['matchType'] = 'DIRECT'
        direct['maker'].update(side='SELL', token='22', makingRaw=600000, takingRaw=360000, logIndex=8)
        label = label_candidate(self.sample(), rows + [direct])
        group = label['matchingGroups'][0]
        self.assertTrue(label['uniqueConservedGroup'])
        self.assertEqual(group['targetMintShares'], '0.4')
        self.assertEqual(group['directShares'], '0.6')

    def test_ambiguous_groups_and_nonconservation_are_not_unique_evidence(self):
        rows = self.matches(); second = copy.deepcopy(rows[0]); second['ordersMatchedLogIndex'] += 1
        self.assertFalse(label_candidate(self.sample(), rows + [second])['uniqueConservedGroup'])
        rows[0]['maker']['takingRaw'] += 1
        self.assertFalse(label_candidate(self.sample(), rows)['uniqueConservedGroup'])

    def test_wrong_public_price_size_token_or_maker_price(self):
        for key, value in [('price','.61'), ('size','2'), ('asset_id','33')]:
            sample = self.sample(); sample[key] = value
            self.assertEqual(label_candidate(sample, self.matches())['matchingPublicAggregateCount'], 0)
        sample = self.sample(); sample['targetPrice'] = '.41'
        group = label_candidate(sample, self.matches())['matchingGroups'][0]
        self.assertEqual(group['targetMintSharesAtImpliedPrice'], '0')

    def test_public_price_not_assumed_to_be_weighted_aggregate(self):
        sample = self.sample(); sample['price'] = '.61'
        label = label_candidate(sample, self.matches())
        self.assertEqual(label['matchingPublicAggregateCount'], 0)
        self.assertTrue(label['uniqueIdentityConservedGroup'])
        self.assertFalse(label['identityMatchingGroups'][0]['publicPriceMatchesWeightedAggregate'])

    def test_integer_collateral_rounding_reported_separately_not_as_fill(self):
        rows = self.matches(); rows[0]['maker']['makingRaw'] += 1
        label = label_candidate(self.sample(), rows)
        group = label['identityMatchingGroups'][0]
        self.assertEqual(group['targetMintSharesAtImpliedPrice'], '0')
        self.assertEqual(group['targetMintSharesWithinOneCollateralUnit'], '1')
        self.assertFalse(label['simulatedFillsCreated'])

    def test_committed_selection_matches_both_reports(self):
        folder = Path('research/experiments/transaction-linked-census-20261018')
        samples = [sample for name in ('original','fresh')
                   for sample in select_samples(json.loads((folder/(name+'.json')).read_text()), str(folder/(name+'.json')))]
        frozen = json.loads((folder/'fixed-selection.json').read_text())
        self.assertEqual(samples, frozen['samples'])

    def test_real_saved_receipts_reproduce_without_network_or_duplicate_volume(self):
        from decimal import Decimal
        folder = Path('research/experiments/candidate-receipt-audit-20261018')
        with tempfile.TemporaryDirectory() as temporary, patch('research.phase6.receipt_audit.rpc') as network:
            result = revalidate_saved(folder, Path(temporary)/'report.json')
            network.assert_not_called()
        groups = [r['candidateSettlementLabel']['identityMatchingGroups'][0] for r in result['results']]
        self.assertEqual(len(groups),10)
        self.assertTrue(all(g['shareConservation'] for g in groups))
        self.assertEqual(sum(Decimal(g['takerShares']) for g in groups), Decimal('623.652586'))
        self.assertEqual(sum(Decimal(g['directShares']) for g in groups), Decimal('28.06'))
        self.assertEqual(sum(Decimal(g['targetMintSharesAtImpliedPrice']) for g in groups), Decimal('530.97'))
