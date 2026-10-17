"""Purged embargoed rolling-fold strategy accounting on recorded trade PnL only.

No model fitting here; selection of folds/parameters after seeing results is
NOT independently pre-registered and still cannot qualify profitability.
"""
import argparse
from collections import defaultdict
import hashlib
from pathlib import Path

from research.phase3.polybot_sdk.model import integer, dumps, decode
from research.phase3.polybot_sdk.runtime import private_write
from research.phase5.offline_benchmark import normalized_trades, summarize, amount, market_components

MAX_FOLDS=32


def connected_groups(rows):
    parent={}
    def root(a):
        parent.setdefault(a,a)
        while parent[a]!=a:
            parent[a]=parent[parent[a]]
            a=parent[a]
        return a
    for r in rows:
        a,b='market:'+r['marketId'],'group:'+r['groupId']
        parent[root(a)]=root(b)
    groups=defaultdict(list)
    for r in rows:
        groups[root('market:'+r['marketId'])].append(r)
    return list(groups.values())


def evaluate_folds(records, folds, stress_multiplier=2, min_test_groups=30):
    rows, source=normalized_trades(records)
    if not isinstance(folds,list) or not 1<=len(folds)<=MAX_FOLDS:
        raise ValueError('A bounded predeclared list of folds is required')
    if type(min_test_groups) is not int or not 1<=min_test_groups<=10000:
        raise ValueError('Invalid independent market group minimum')
    factor=amount(stress_multiplier,'stress multiplier')
    if not 1<=factor<=10:
        raise ValueError('Invalid cost stress multiplier')
    graph=connected_groups(rows)
    components=market_components(rows)
    strat_ids=sorted(set(r['strategyId'] for r in rows))
    results=[]
    previous_end=None
    for idx, fold in enumerate(folds):
        if not isinstance(fold,dict) or set(fold)!={'trainBeforeMs','testStartMs','testEndMs'}:
            raise ValueError('Invalid fixed fold schema')
        train_end,test_begin,test_end=(integer(fold[k]) for k in
                            ('trainBeforeMs','testStartMs','testEndMs'))
        if not 0<train_end<test_begin<test_end:
            raise ValueError('No positive embargo / invalid test window')
        if previous_end is not None and test_begin<previous_end:
            raise ValueError('Forward tests must not overlap')
        previous_end=test_end
        training,test,purged=[],[],0
        for group in graph:
            if max(x['closedMs'] for x in group)<=train_end:
                training.extend(group)
            elif (min(x['openedMs'] for x in group)>=test_begin
                  and max(x['closedMs'] for x in group)<=test_end):
                test.extend(group)
            else:
                purged+=len(group)
        comparisons={}
        test_sets=[]
        for strategy in strat_ids:
            tr=[x for x in training if x['strategyId']==strategy]
            ho=[x for x in test if x['strategyId']==strategy]
            ids=set((x['marketId'],x['groupId']) for x in ho)
            test_sets.append(ids)
            comparisons[strategy]={'training':summarize(tr,factor),
                'outOfSample':summarize(ho,factor),
                'outOfSampleMarketGroups':len({components[x['marketId']] for x in ho}),
                'sufficientHeldoutGroups':len({components[x['marketId']] for x in ho})>=min_test_groups,
                'qualified':False}
        results.append({'fold':idx,'trainBeforeMs':train_end,
                        'testStartMs':test_begin,'testEndMs':test_end,
                        'embargoMs':test_begin-train_end,
                        'trainRows':len(training),'testRows':len(test),
                        'purgedOrOutOfWindowRows':purged,
                        'strategiesShareSameTestMarketGroups':
                            len(test_sets)>1 and all(v==test_sets[0] for v in test_sets),
                        'strategies':comparisons})
    return {'schema':1,'scope':'PHASE5_PURGED_EMBARGOED_WALK_FORWARD_COST_ACCOUNTING',
            'datasetSha256':hashlib.sha256(dumps(records).encode()).hexdigest(),
            'foldManifestSha256':hashlib.sha256(dumps(folds).encode()).hexdigest(),
            'sourceProvenance':source,'folds':results,
            'selectionBiasIndependentlyChecked':False,
            'prospectiveHoldoutObserved':False,'actualVenueFillsVerified':False,
            'strategyQualified':False,'decision':'NO_GO','liveAllowed':False}


def main():
    cli=argparse.ArgumentParser(description='Offline embargoed strategy folds, no venue trading')
    cli.add_argument('trade_tape',help='Historical gross-trade PnL JSONL')
    cli.add_argument('--folds',required=True,help='Previously frozen fold calendar JSON list')
    cli.add_argument('--stress-multiplier',default='2')
    cli.add_argument('--min-test-groups',type=int,default=30)
    cli.add_argument('--output',required=True)
    args=cli.parse_args()
    rows=[]
    with Path(args.trade_tape).open(encoding='utf-8') as f:
        for line in f:
            if line.strip():
                rows.append(decode(line))
            if len(rows)>100000:
                raise ValueError('Dataset limit exceeded')
    folds=decode(Path(args.folds).read_text(encoding='utf-8'))
    report=evaluate_folds(rows,folds,args.stress_multiplier,args.min_test_groups)
    private_write(args.output,report)
    print(dumps(report))


if __name__=='__main__':
    main()
