import copy
import gzip
import hashlib
import json
import unittest
from research.phase6.cached_receipt_pool import ROOT,load_inputs,build,lookup,portions_sha


class CachedReceiptPoolTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.args=load_inputs();cls.pool=build(*cls.args)
        cls.binding=next(b for b in cls.pool['bindings'] if b['origin']=='RECOVERY451')
        key=(cls.binding['seq'],cls.binding['eventIndex'])
        with gzip.open('research/experiments/queue-aware-quote-20261019/post-gap-result/context.records.jsonl.gz','rt') as stream:
            for line in stream:
                row=json.loads(line)['input']
                if row['seq']==key[0]:
                    cls.original=row['data']['events'][key[1]]['data'];break

    def test_all191_rebound_and_original451_preserved_without_scope_promotion(self):
        pool=self.pool
        self.assertEqual(len(pool['bindings']),642);self.assertEqual(pool['reboundCachedBindings'],191)
        old={(b['seq'],b['eventIndex']):b for b in self.args[1]['bindings']}
        for b in pool['bindings']:
            if b['origin']=='RECOVERY451':
                self.assertEqual({k:b[k] for k in old[(b['seq'],b['eventIndex'])]},old[(b['seq'],b['eventIndex'])])
        self.assertEqual(pool['remainingUnboundObservations'],15675)
        self.assertNotEqual(pool['experiment'],'CONSERVED-MIXED-LAB0')
        for field in ('allOriginalPairObservationsWithinWindow','nativePoolConsumerImplemented','netPnlRecomputed',
                      'candidateAccountSimulated','fullAccountReplayAuthorized','independentPaperQualificationAllowed','liveAllowed'):
            self.assertFalse(pool[field])
        self.assertEqual(pool['newPublicReads'],0);self.assertEqual(pool['modelFillsCreated'],0)

    def test_saved_pool_exact_source_routes_and_portion_digest(self):
        raw=gzip.decompress((ROOT/'bindings.json.gz').read_bytes())
        self.assertEqual(json.loads(raw),self.pool)
        report=json.loads((ROOT/'report.json').read_text())
        self.assertEqual(hashlib.sha256(raw).hexdigest(),report['poolLogicalSha256'])
        self.assertEqual(portions_sha(self.pool),report['portionsLogicalSha256'])
        self.assertEqual(sum(report['routeComponentCounts'].values()),report['expectedComponentCount'])
        self.assertEqual(sum(report['reboundRouteComponentCounts'].values()),report['expectedComponentCount']-1038)

    def test_191_selection_not_filtered_and_unknown_metadata_not_guessed(self):
        args=list(self.args);tx=next(r['transactionHash'] for r in args[2] if r['transactionHash'] in args[3])
        args[2]=[r for r in args[2] if r['transactionHash']!=tx]
        with self.assertRaisesRegex(ValueError,'ALL191'):build(*args)
        args=list(self.args);args[0]=dict(args[0],negativeRisk=True)
        with self.assertRaisesRegex(ValueError,'binary market'):build(*args)
        args=list(self.args);args[2]=copy.deepcopy(args[2])
        next(r for r in args[2] if r['transactionHash'] in args[3])['condition']='unproven-other-market'
        with self.assertRaisesRegex(ValueError,'guessed metadata'):build(*args)

    def test_cached_receipt_status_or_duplicate_log_invalidates_whole_pool(self):
        tx=next(r['transactionHash'] for r in self.args[2] if r['transactionHash'] in self.args[3])
        for mutate in [lambda r:r.update(status='0x0'),lambda r:r['logs'].append(copy.deepcopy(r['logs'][0]))]:
            args=list(self.args);args[3]=dict(args[3]);args[3][tx]=copy.deepcopy(args[3][tx]);mutate(args[3][tx]['data']['receipt'])
            with self.assertRaises(ValueError):build(*args)

    def test_lookup_requires_actual_original_trade_bytes_and_exact_coordinate(self):
        b=self.binding
        self.assertEqual(lookup(self.pool,b['seq'],b['eventIndex'],b['at'],self.original),b)
        for name,value in [('side','SELL' if b['side']=='BUY' else 'BUY'),('size','0.1'),('price','0.12345'),
                           ('sourceMs',b['sourceMs']-1),('tradeId',self.original['tradeId']+' ')]:
            data=dict(self.original);data[name]=value
            with self.assertRaisesRegex(ValueError,'original source identity'):lookup(self.pool,b['seq'],b['eventIndex'],b['at'],data)
        with self.assertRaisesRegex(ValueError,'original source identity'):lookup(self.pool,b['seq'],b['eventIndex'],b['at']+1,self.original)

    def test_unknown_and_duplicate_lookup_are_never_zero_or_aggregate(self):
        with self.assertRaisesRegex(ValueError,'incomplete pool is not zero'):lookup(self.pool,97,0,0,self.original)
        pool=dict(self.pool,bindings=[*self.pool['bindings'],self.binding])
        with self.assertRaisesRegex(ValueError,'duplicate source'):lookup(pool,self.binding['seq'],self.binding['eventIndex'],self.binding['at'],self.original)
        for key in ('allOriginalPairObservationsWithinWindow','fullAccountReplayAuthorized','liveAllowed'):
            pool=dict(self.pool);pool[key]=True
            with self.assertRaisesRegex(ValueError,'Partial offline'):lookup(pool,self.binding['seq'],self.binding['eventIndex'],self.binding['at'],self.original)


if __name__=='__main__':unittest.main()
