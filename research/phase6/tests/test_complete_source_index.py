import copy
import json
from pathlib import Path
import unittest

from research.phase6.complete_source_index import (
    COUNT, IDENTITIES_SHA, SourceIdentityIndex, evidence, reconstruct, validate_rows,
)
from research.phase6.expanded_receipt_pool import build, identities


class CompleteSourceIndexTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows, cls.source, cls.proof = reconstruct()
        cls.actual = identities(build())['observations']

    def consumer(self, subset=True):
        return SourceIdentityIndex(self.rows, self.source, subset=subset)

    def consume(self, consumer, observation):
        return consumer.consume(observation['seq'], observation['eventIndex'],
                                observation['at'], observation['data'])

    def test_all_original_identities_and_global_uniqueness(self):
        self.assertEqual(self.proof['observations'], COUNT)
        self.assertEqual(self.proof['uniqueTransactions'], COUNT)
        self.assertEqual(self.proof['uniquePublicTradeIds'], COUNT)
        self.assertEqual(self.proof['identitiesSha256'], IDENTITIES_SHA)
        self.assertEqual(sum(r['coverage'] == 'BOUND_CONSERVED_GROUP' for r in self.rows), 451)

    def test_all643_real_preimages_not_full_source_consumption(self):
        reader = self.consumer()
        for actual in self.actual:
            row = self.consume(reader, actual)
            self.assertEqual(row['seq'], actual['seq'])
        self.assertEqual(reader.report()['consumedOriginalPreimages'], 643)
        self.assertFalse(reader.report()['completeOriginalConsumption'])
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            reader.require_complete()
        self.assertTrue(reader.report()['failed'])
        with self.assertRaisesRegex(ValueError, 'poisoned'):
            self.consume(reader, self.actual[0])

    def test_all_index_mutations_fail(self):
        mutations = [
            lambda r: r.pop(),
            lambda r: r.reverse(),
            lambda r: r[1].update(transactionHash=r[0]['transactionHash']),
            lambda r: r[1].update(publicTradeIdSha256=r[0]['publicTradeIdSha256']),
            lambda r: r[1].update(seq=r[0]['seq'], eventIndex=r[0]['eventIndex']),
            lambda r: r[0].update(transactionHash=None),
            lambda r: r[0].update(price='NaN'),
            lambda r: r[0].update(size='0'),
            lambda r: r[0].update(sourceMs=True),
            lambda r: r[0].update(side='SELL' if r[0]['side'] == 'BUY' else 'BUY'),
            lambda r: r[0].update(coverage='EXECUTION_AUTHORIZED'),
            lambda r: r[0].update(extra='not original'),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutations.index(mutation)):
                rows = copy.deepcopy(self.rows)
                mutation(rows)
                with self.assertRaises(ValueError):
                    validate_rows(rows, self.source)

    def test_changed_normalized_or_original_bytes_poison(self):
        for key, value in [('token', '1'), ('side', 'INVALID'), ('sourceMs', 0),
                           ('price', '0.123456'), ('size', '999999'), ('tradeId', '{}')]:
            with self.subTest(field=key):
                reader = self.consumer()
                actual = copy.deepcopy(self.actual[0])
                actual['data'][key] = value
                with self.assertRaises(ValueError):
                    self.consume(reader, actual)
                self.assertTrue(reader.report()['failed'])
                with self.assertRaisesRegex(ValueError, 'poisoned'):
                    self.consume(reader, self.actual[0])
        reader = self.consumer()
        actual = copy.deepcopy(self.actual[0])
        actual['data']['tradeId'] += ' '
        with self.assertRaises(ValueError):
            self.consume(reader, actual)

    def test_coordinates_time_and_missing_observation_fail_closed(self):
        for field, value in [('seq', -1), ('eventIndex', 99999), ('at', 0), ('seq', True)]:
            reader = self.consumer()
            actual = copy.deepcopy(self.actual[0]); actual[field] = value
            with self.assertRaises(ValueError):
                self.consume(reader, actual)
        # Starting from a later available preimage must not skip earlier observations.
        reader = self.consumer(subset=False)
        self.assertNotEqual((self.actual[1]['seq'], self.actual[1]['eventIndex']),
                            (self.rows[0]['seq'], self.rows[0]['eventIndex']))
        with self.assertRaises(ValueError):
            self.consume(reader, self.actual[1])
        self.assertTrue(reader.report()['failed'])

    def test_duplicate_and_reversed_consumption_fail(self):
        for first, second in [(self.actual[0], self.actual[0]),
                              (self.actual[1], self.actual[0])]:
            reader = self.consumer()
            self.consume(reader, first)
            with self.assertRaises(ValueError):
                self.consume(reader, second)
            self.assertTrue(reader.report()['failed'])

    def test_caller_cannot_mutate_validated_index(self):
        rows = copy.deepcopy(self.rows)
        reader = SourceIdentityIndex(rows, self.source, subset=True)
        key = (self.actual[0]['seq'], self.actual[0]['eventIndex'])
        row = next(r for r in rows if (r['seq'], r['eventIndex']) == key)
        row['size'] = '999999'
        returned = self.consume(reader, self.actual[0])
        returned['size'] = '999999'
        self.assertEqual(reader.report()['consumedOriginalPreimages'], 1)

    def test_retained_proof_reproduced_without_runtime_authority(self):
        stored = json.loads(Path('research/experiments/complete-source-index-20261020/proof.json').read_bytes())
        self.assertEqual(evidence(), stored)
        self.assertEqual(stored['unknownPreimagesNotInvented'], 15674)
        for field in ('runtimeOptimizationImplemented', 'atomicSessionGuardImplemented',
                      'marketNetPnlRecomputed', 'fullAccountReplayAuthorized',
                      'independentPaperQualificationAllowed', 'liveAllowed'):
            self.assertFalse(stored[field])


if __name__ == '__main__':
    unittest.main()
