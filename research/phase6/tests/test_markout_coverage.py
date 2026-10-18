import hashlib
import io
import json
from pathlib import Path
import unittest
from research.phase6.markout_coverage import Coverage, audit


class MarkoutCoverageTest(unittest.TestCase):
    def fill(self, token='a', condition='m', at=1000):
        return dict(orderId='order-'+token, token=token, condition=condition, at=at,
                    buy=True, size=5, price='.4', liquidity='MAKER')

    def event(self, kind, data, at):
        return (kind, data, dict(at=at, kind=kind))

    def book(self, at, token='a', source=None):
        return self.event('BOOK', dict(token=token, sourceMs=at if source is None else source,
            bids=[dict(price='.5',size=100)], asks=[dict(price='.6',size=100)]), at)

    def start(self, fills=None, pairs=None):
        pairs=pairs or {'m':['a','b']}; fills=fills or [self.fill()]
        c=Coverage(fills,pairs,2000)
        c.arrival(0,[self.event('META',dict(condition=k, first=v[0],second=v[1],observedMs=0),0)
                     for k,v in pairs.items()])
        c.arrival(1000,[self.book(1000, f['token']) for f in fills]
            +[self.event('TRADE',dict(token=f['token']),1000) for f in fills])
        return c

    def test_clean_continuity_gives_all_three_horizons_not_account_pnl(self):
        c=self.start()
        for at in range(2000,32000,1000): c.arrival(at,[self.book(at)])
        r=c.report()
        self.assertEqual(r['statusCounts'],{'VALID':3})
        self.assertEqual([x['markoutNotAccountPnl'] for x in r['horizons']],['0.75']*3)
        self.assertFalse(r['netPnlRecomputed']);self.assertFalse(r['fillsInferred'])
        self.assertFalse(r['liveAllowed']);self.assertEqual(r['decision'],'NO_GO')

    def test_paired_scope_does_not_invalidate_unrelated_market(self):
        c=self.start([self.fill(),self.fill('c','n')],{'m':['a','b'],'n':['c','d']})
        c.arrival(1500,[self.event('GAP',dict(token='b'),1500)])
        for at in range(2000,32000,1000):c.arrival(at,[self.book(at,'a'),self.book(at,'c')])
        r=c.report();self.assertEqual(r['statusCounts'],{'DATA_GAP':3,'VALID':3})
        self.assertTrue(all(x['status']=='DATA_GAP' for x in r['horizons'] if x['token']=='a'))

    def test_completed_horizon_survives_global_gap_recovery_never_resurrects(self):
        c=self.start();c.arrival(2000,[self.book(2000)])
        c.arrival(2500,[self.event('GAP',{},2500)])
        for at in range(3000,32000,1000):c.arrival(at,[self.book(at)])
        self.assertEqual(c.report()['statusCounts'],{'VALID':1,'DATA_GAP':2})

    def test_same_arrival_gap_preempts_book_even_if_book_listed_first(self):
        c=self.start()
        c.arrival(2000,[self.book(2000),self.event('GAP',dict(token='b'),2000)])
        self.assertEqual(c.report()['statusCounts'],{'DATA_GAP':3})

    def test_silence_is_stale_and_exact_boundary_is_not_stale(self):
        c=self.start();c.arrival(3000,[self.book(3000)])
        self.assertEqual(c.report()['statusCounts'],{'VALID':1,'RECORDING_ENDED_BEFORE_CLEAN_OBSERVATION':2})
        c=self.start();c.arrival(3001,[self.book(3001)])
        self.assertEqual(c.report()['statusCounts'],{'STALE_DEPTH':3})

    def test_invalid_and_regressed_books_never_create_zero_return_samples(self):
        for source in [999,2001,-1]:
            c=self.start();c.arrival(2000,[self.book(2000,source=source)])
            r=c.report();self.assertEqual(r['statusCounts'],{'INVALID_BOOK':3})
            self.assertTrue(all('markoutNotAccountPnl' not in x for x in r['horizons']))

    def test_missing_fill_trigger_metadata_and_bad_gap_scope_fail_closed(self):
        c=Coverage([self.fill()],{'m':['a','b']},2000)
        with self.assertRaises(ValueError):c.arrival(1000,[self.book(1000)])
        c=self.start()
        with self.assertRaises(ValueError):c.scope({'tokens':'a'})
        c=self.start()
        with self.assertRaises(ValueError):c.arrival(1000,[])
        c=Coverage([self.fill()],{'m':['a','b']},2000)
        with self.assertRaises(ValueError):c.report()

    def tape(self, complete=True, bad_frame=False):
        events=[('DATASET_CONFIG',0,{'format':'normalized-public-v2'}),
            ('RESEARCH_META',0,dict(condition='m',first='a',second='b',observedMs=0)),
            ('RAW_MARKET',1000,dict(frameId=1,text='fixture')),
            ('RESEARCH_FRAME',1000,dict(frameId=2 if bad_frame else 1,events=[
                dict(kind=k,data=d) for k,d,p in [self.book(1000),self.event('TRADE',{'token':'a'},1000)]])),
            ('RESEARCH_BOOK',2000,self.book(2000)[1]),
            ('RUN_END',2000,{'complete':complete})]
        return b''.join((json.dumps(dict(schema=1,runId='r',seq=i,kind=k,arrivalMs=at,data=d))+'\n').encode()
            for i,(k,at,d) in enumerate(events,1))

    def test_full_tape_provenance_frame_binding_and_clean_end_required(self):
        raw=self.tape()
        r=audit(io.BytesIO(raw),[self.fill()],{'m':['a','b']},2000,hashlib.sha256(raw).hexdigest())
        self.assertEqual(r['sourceRows'],6);self.assertEqual(r['statusCounts']['VALID'],1)
        for data,digest in [(raw,'0'*64),(self.tape(False),None),(self.tape(bad_frame=True),None),
                            (raw+b'{}\n',None),(raw[:-1],None)]:
            with self.assertRaises((ValueError,KeyError)):
                audit(io.BytesIO(data),[self.fill()],{'m':['a','b']},2000,digest or hashlib.sha256(data).hexdigest())

    def test_frozen_sources_and_original_account_are_unchanged(self):
        f=json.loads(Path('research/phase6/markout-coverage-freeze.json').read_text())
        for name,digest in f['filesSha256'].items():
            self.assertEqual(hashlib.sha256(Path(name).read_bytes()).hexdigest(),digest,name)
        self.assertFalse(f['liveAllowed']);self.assertFalse(f['independentPaperQualificationAllowed'])
        report=json.loads(Path(f['originalReport']).read_text())
        self.assertEqual(report['netRealizedPnl'],-.85);self.assertEqual(report['cash'],499.15)


if __name__=='__main__':unittest.main()
