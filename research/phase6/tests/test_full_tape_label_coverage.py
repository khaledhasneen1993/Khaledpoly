import copy
import hashlib
import io
import json
import unittest
from research.phase6.full_tape_label_coverage import census


class FullTapeCoverageTest(unittest.TestCase):
    def fixture(self):
        tx = '0x' + 'a' * 64
        trade = dict(token='a', side='BUY', price='.4', size='5', sourceMs=3,
                     tradeId=json.dumps(dict(transaction_hash=tx)))
        values = [('DATASET_CONFIG', dict(format='normalized-public-v2', strategyIndependent=True)),
                  ('RESEARCH_META', dict(condition='m', first='a', second='b')),
                  ('RAW_MARKET', dict(frameId=1, text='original public frame')),
                  ('RESEARCH_FRAME', dict(frameId=1, events=[dict(kind='TRADE', data=trade)])),
                  ('RUN_END', dict(complete=True))]
        rows = [dict(schema=1, seq=i+1, runId='r', arrivalMs=i, kind=k, data=d) for i,(k,d) in enumerate(values)]
        labels = dict(experiment='CONSERVED-MIXED-LAB0', coverage=dict(pair=['a','b']), expectedBindingCount=1,
            bindings=[dict(seq=4, eventIndex=0, at=3, sourceMs=3, token='a', side='BUY', price='.4', size='5',
                           transactionHash=tx, publicTradeIdSha256=hashlib.sha256(trade['tradeId'].encode()).hexdigest())])
        return rows, labels

    def run_case(self, rows, labels, *, expected_sha=None, expected_rows=None):
        tape = b''.join((json.dumps(row) + '\n').encode() for row in rows)
        digest = hashlib.sha256(tape).hexdigest()
        labels = copy.deepcopy(labels); labels['logicalTapeSha256'] = digest
        emitted = []
        report = census(io.BytesIO(tape), labels, emitted.append,
                        expected_sha=expected_sha or digest, expected_rows=expected_rows or len(rows))
        return report, emitted

    def test_exact_binding_never_authorizes_account_or_profit(self):
        report, emitted = self.run_case(*self.fixture())
        self.assertEqual(report['consumedBindings'], 1); self.assertEqual(report['missingObservationCount'], 0)
        self.assertEqual(emitted, []); self.assertTrue(report['observedTradeRoutesFullyLabeled'])
        for key in ('fullAccountReplayAuthorized','netPnlRecomputed','liveAllowed','independentPaperQualificationAllowed'):
            self.assertFalse(report[key])

    def test_missing_scoped_other_unknown_and_known_duplicate_conserve_census(self):
        rows, labels = self.fixture(); base = rows[3]['data']['events'][0]
        for token, tx in [('b','b'),('c','c'),('unknown','d'),('b','a')]:
            event = copy.deepcopy(base); event['data']['token'] = token
            event['data']['tradeId'] = json.dumps(dict(transaction_hash='0x'+tx*64))
            rows[3]['data']['events'].append(event)
        meta = dict(schema=1,runId='r',arrivalMs=1,kind='RESEARCH_META',data=dict(condition='n',first='c',second='d'))
        rows.insert(2,meta)
        for i,row in enumerate(rows):row['seq']=i+1
        labels['bindings'][0]['seq']=5
        report, emitted = self.run_case(rows,labels)
        self.assertEqual(report['normalizedTradeObservations'],5);self.assertEqual(report['missingObservationCount'],3)
        self.assertEqual(len(emitted),3);self.assertEqual(report['coverageCounts']['KNOWN_TRANSACTION_AGGREGATE_SUPPRESSED'],1)
        self.assertEqual(set(report['firstMissingByReason']),{'MISSING_SCOPED_PAIR_LABEL','OTHER_MARKET_UNBOUND_NO_AGGREGATE_FALLBACK','UNKNOWN_MARKET_UNBOUND'})
        self.assertEqual(report['missingObservationsLogicalSha256'],hashlib.sha256(b''.join(emitted)).hexdigest())
        self.assertFalse(report['observedTradeRoutesFullyLabeled']);self.assertFalse(report['uncoveredObservationsTreatedAsZero'])

    def test_changed_bound_identity_side_quantity_coordinate_and_time_fail(self):
        for name,value in [('size','6'),('side','SELL'),('sourceMs',2),('tradeId','{}'),('price','.41')]:
            rows,labels=self.fixture();rows[3]['data']['events'][0]['data'][name]=value
            with self.assertRaisesRegex(ValueError,'bound observation'):self.run_case(rows,labels)
        rows,labels=self.fixture();labels['bindings'][0]['seq']=3
        with self.assertRaisesRegex(ValueError,'consumption'):self.run_case(rows,labels)

    def test_all_rows_even_tail_are_checked(self):
        rows,labels=self.fixture();rows.append(copy.deepcopy(rows[-1]));rows[-1]['seq']=6
        with self.assertRaisesRegex(ValueError,'chronology'):self.run_case(rows,labels)
        rows,labels=self.fixture();rows[-1]['data']['complete']=False
        with self.assertRaisesRegex(ValueError,'Incomplete RUN_END'):self.run_case(rows,labels)
        rows,labels=self.fixture();rows[-1]['runId']='other'
        with self.assertRaisesRegex(ValueError,'chronology'):self.run_case(rows,labels)
        with self.assertRaisesRegex(ValueError,'manifest/source'):self.run_case(*self.fixture(),expected_sha='0'*64)
        with self.assertRaisesRegex(ValueError,'Incomplete original'):self.run_case(*self.fixture(),expected_rows=6)

    def test_atomic_frames_and_unknown_events_not_silently_omitted(self):
        for mutate in [lambda r:r[3]['data'].update(frameId=2),
                       lambda r:r[3]['data']['events'].append(dict(kind='NEW_KIND',data={})),
                       lambda r:r[3]['data'].update(decodedMs=100),
                       lambda r:r[2].update(kind='IGNORED_RAW')]:
            rows,labels=self.fixture();mutate(rows)
            with self.assertRaises(ValueError):self.run_case(rows,labels)

    def test_missing_transaction_kept_as_missing_not_guessed(self):
        rows,labels=self.fixture();event=copy.deepcopy(rows[3]['data']['events'][0]);event['data'].update(token='b',tradeId='not-json')
        rows[3]['data']['events'].append(event)
        report,emitted=self.run_case(rows,labels)
        self.assertEqual(report['missingObservationCount'],1)
        self.assertIsNone(json.loads(emitted[0])['transactionHash'])

    def test_duplicate_labels_and_ambiguous_markets_fail_closed(self):
        rows,labels=self.fixture();labels['bindings']*=2;labels['expectedBindingCount']=2
        with self.assertRaisesRegex(ValueError,'Duplicate'):self.run_case(rows,labels)
        rows,labels=self.fixture();row=copy.deepcopy(rows[1]);row['data']['second']='c';rows.insert(2,row)
        for i,row in enumerate(rows):row['seq']=i+1
        with self.assertRaisesRegex(ValueError,'pair identity changed'):self.run_case(rows,labels)


if __name__=='__main__':unittest.main()
