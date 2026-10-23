import copy
import gzip
import hashlib
import io
import json
import unittest
from pathlib import Path
from research.phase6.full_tape_coverage_result import ROOT,read_archive,verify,cache_inventory,canonical
from research.phase6.mixed_replay_labels import export


class FullCoverageResultTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report,cls.compressed,_=read_archive(ROOT/'artifact.zip');cls.labels=export()
        path=Path('research/phase6/full-tape-coverage-freeze.json');cls.frozen=json.loads(path.read_text())
        cls.sha=hashlib.sha256(path.read_bytes()).hexdigest()
        cls.inspection=json.loads(Path(cls.frozen['referenceInspection']).read_text())

    def check(self,report=None,compressed=None):
        return verify(self.report if report is None else report,self.compressed if compressed is None else compressed,
                      self.labels,self.inspection,self.frozen,self.sha)

    def test_all_original_trade_identities_reconstructed_not_only_missing_counts(self):
        proof,missing,tokens=self.check()
        self.assertEqual(proof['originalTradeObservations'],16317)
        self.assertEqual(proof['validatedBindings'],451);self.assertEqual(proof['missingObservations'],15866)
        self.assertEqual(proof['missingUniqueTransactions'],15866);self.assertEqual(proof['missingRepeatedTransactionObservations'],0)
        self.assertTrue(proof['allTradeIdentityDigestReproduced'])
        self.assertEqual(proof['allObservationIdentitiesSha256'],'1f8d1d953f3755b8244c7ac11f7a3f72ccd8d73b1c9807b7cec417b6b710c1c2')
        self.assertFalse(proof['fullAccountReplayAuthorized']);self.assertFalse(proof['netPnlRecomputed'])
        inventory=cache_inventory(missing,tokens,{missing[0]['transactionHash']:object()})
        self.assertEqual(inventory['existingReceiptCandidates'],1)
        self.assertEqual(inventory['missingTransactionsOutsideReviewedCache'],15865)
        self.assertTrue(inventory['cachedPresenceIsNotCorroboration'])
        self.assertEqual(inventory['newValidatedLabels'],0)

    def test_counts_source_and_first_blocker_cannot_change(self):
        for mutate in [lambda r:r.update(logicalTapeSha256='0'*64),
                       lambda r:r.update(missingObservationCount=15865),
                       lambda r:r['coverageCounts'].update(MISSING_SCOPED_PAIR_LABEL=0),
                       lambda r:r['firstMissingByReason']['MISSING_SCOPED_PAIR_LABEL'].update(seq=98),
                       lambda r:r.update(allObservationIdentitiesSha256='0'*64)]:
            report=copy.deepcopy(self.report);mutate(report)
            with self.assertRaises(ValueError):self.check(report)

    def test_no_scope_promotion_or_zero_unknown_coverage(self):
        for field in ('uncoveredObservationsTreatedAsZero','publicAggregateFallbackAllowed','observedTradeRoutesFullyLabeled',
                      'fullAccountReplayAuthorized','netPnlRecomputed','independentPaperQualificationAllowed','liveAllowed'):
            report=copy.deepcopy(self.report);report[field]=True
            with self.assertRaisesRegex(ValueError,'scope promotion'):self.check(report)

    def test_missing_stream_tamper_rejected_even_if_local_hashes_updated(self):
        rows=[json.loads(line) for line in gzip.decompress(self.compressed).splitlines()]
        rows[-1]['price']='0.12345'
        logical=b''.join(canonical(row) for row in rows);compressed=gzip.compress(logical,mtime=0)
        report=copy.deepcopy(self.report)
        report.update(missingObservationBytes=len(logical),missingObservationsLogicalSha256=hashlib.sha256(logical).hexdigest(),
                      missingObservationsCompressedSha256=hashlib.sha256(compressed).hexdigest())
        with self.assertRaisesRegex(ValueError,'identity reconstruction'):self.check(report,compressed)

    def test_duplicate_or_reordered_missing_coordinates_rejected(self):
        rows=[json.loads(line) for line in gzip.decompress(self.compressed).splitlines()]
        rows[1]=copy.deepcopy(rows[0]);compressed=gzip.compress(b''.join(canonical(row) for row in rows),mtime=0)
        report=copy.deepcopy(self.report);report['missingObservationsCompressedSha256']=hashlib.sha256(compressed).hexdigest()
        with self.assertRaisesRegex(ValueError,'duplicate/out-of-order'):self.check(report,compressed)


if __name__=='__main__':unittest.main()
