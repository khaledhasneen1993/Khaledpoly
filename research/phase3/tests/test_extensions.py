from pathlib import Path
import sys
import tempfile
import unittest
from decimal import Decimal as D
from unittest.mock import patch
from urllib.error import HTTPError
from io import BytesIO

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from test_research import fixture, BASE
from research.phase3.polybot_sdk.model import validate, dumps, decode
from research.phase3.polybot_sdk.features import Observation, FeatureStore, normalize_trades
from research.phase3.polybot_sdk.feature_tail import FeatureTail
from research.phase3.polybot_sdk.collector import PublicCollector, retry_delay
from research.phase3.polybot_sdk.advanced import candidates, allocate
from research.phase3.polybot_sdk.learning import example, train, predict, FEATURES
from research.phase3.polybot_sdk.portfolio import historical_risk
from research.phase3.polybot_sdk.accounts import AccountRegistry
from research.phase3.polybot_sdk.baskets import analyze_basket, convert_no, collateral_check, gas_scenario
from research.phase3.polybot_sdk.runtime import shadow_run, replay_shadow
from research.phase3.polybot_sdk.strategy import evaluate

HASH = 'a' * 64


def observation(venue='forecast', symbol='market', kind='first_outcome_probability', value='.8', source=BASE, received=BASE):
    return Observation(venue, symbol, kind, D(value), source, received, HASH)


def label(order, market, start, yes, provenance='PAPER_MODEL'):
    return {'orderId': str(order), 'marketId': str(market), 'submittedMs': start, 'featureObservedMs': start,
            'labelEndMs': start + 5000, 'fillMs': start + 10 if yes else None, 'cancelMs': None,
            'provenance': provenance,
            'features': dict(zip(FEATURES, ('.1', '20', '0', '10', '60', '.01')))}


class FeatureTest(unittest.TestCase):
    def test_availability_not_exchange_sorting_and_no_old_refresh(self):
        store = FeatureStore()
        store.add(observation(source=BASE - 100, received=BASE + 100))
        self.assertIsNone(store.latest('forecast', 'market', 'first_outcome_probability', BASE))
        store.add(observation(source=BASE - 200, received=BASE + 200))
        self.assertEqual(store.regressions, 1)
        self.assertEqual(store.latest('forecast', 'market', 'first_outcome_probability', BASE + 200).source_ms, BASE - 100)
        self.assertEqual(store.available(BASE + 2000), [])

    def test_bounded_and_future_evidence(self):
        with self.assertRaises(ValueError):
            observation(source=BASE + 1)
        store = FeatureStore(max_keys=1)
        store.add(observation())
        with self.assertRaises(ValueError):
            store.add(observation(symbol='other'))
        with self.assertRaises(ValueError):
            store.add(observation(received=BASE - 1, source=BASE - 2))

    def test_official_payload_parsers_keep_source_time(self):
        rows = normalize_trades('binance-spot', 'BTCUSDT', [{'a': 1, 'p': '60000', 'q': '.1', 'T': BASE - 100}], BASE)
        self.assertEqual(rows[0].source_ms, BASE - 100)
        bybit = {'retCode': 0, 'result': {'category': 'spot', 'list': [{'execId': 'x', 'symbol': 'BTCUSDT', 'price': '60001', 'size': '.1', 'time': str(BASE - 50)}]}}
        store = FeatureStore()
        store.add(rows[0])
        store.add(normalize_trades('bybit-spot', 'BTCUSDT', bybit, BASE)[0])
        self.assertFalse(store.divergence('BTCUSDT', BASE)['arbitrageProven'])
        bybit['result']['list'][0]['symbol'] = 'ETHUSDT'
        with self.assertRaises(ValueError):
            normalize_trades('bybit-spot', 'BTCUSDT', bybit, BASE)

    def test_incremental_tail_partial_line_and_rotation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'features.jsonl'
            line = dumps(observation().record())
            path.write_text(line[:20])
            tail, store = FeatureTail(path), FeatureStore()
            self.assertEqual(tail.update(store), 0)
            path.write_text(line + '\n')
            self.assertEqual(tail.update(store), 1)
            self.assertEqual(tail.update(store), 0)
            path.write_text('')
            with self.assertRaises(ValueError):
                tail.update(store)

    def test_category_discovery_preserves_ids_and_partial_universe(self):
        from research.phase3.polybot_sdk.discovery import UniverseDiscovery
        client = UniverseDiscovery()
        payloads = [{'id': '2', 'slug': 'politics'}, {'markets': [{'conditionId': '0x' + '1' * 64,
                    'version': 'v2', 'positionIds': ['1', '2'], 'clobTokenIds': None}], 'next_cursor': 'next'}]
        with patch.object(client, '_get', side_effect=payloads):
            result = client.discover('politics')
        self.assertTrue(result['partialUniverse'])
        self.assertEqual(result['markets'][0]['positionIds'], ['1', '2'])
        self.assertFalse(result['markets'][0]['executionAdapterVerified'])
        with self.assertRaises(ValueError):
            client.discover('guessed-category')

    def test_rate_limits_and_retry_after(self):
        self.assertEqual(retry_delay('120'), 120)
        self.assertEqual(retry_delay('Thu, 01 Jan 1970 00:02:00 GMT', now=0), 120)
        self.assertEqual(retry_delay('bad'), 60)
        self.assertEqual(retry_delay('NaN'), 60)
        client = PublicCollector('binance-spot')
        class Opener:
            def open(self, *args, **kwargs):
                raise HTTPError('url', 429, 'rate', {'Retry-After': '180'}, BytesIO())
        client._opener = Opener()
        status, rows = client.poll(BASE)
        self.assertEqual(status['retryAtMs'], BASE + 180000)
        self.assertEqual(rows, [])
        self.assertEqual(client.poll(BASE + 1)[0]['status'], 'BACKOFF')

    def test_bybit_forbidden_response_has_ten_minute_cooldown(self):
        client = PublicCollector('bybit-spot')
        class Opener:
            def open(self, *args, **kwargs):
                raise HTTPError('url', 403, 'forbidden', {}, BytesIO())
        client._opener = Opener()
        status, rows = client.poll(BASE)
        self.assertEqual(status['retryAtMs'], BASE + 600000)
        self.assertEqual(rows, [])
        self.assertEqual(client.poll(BASE + 599999)[0]['status'], 'BACKOFF')


class AdvancedStrategyTest(unittest.TestCase):
    def test_forecast_requires_explicit_resolution_risk(self):
        snapshot, store = validate(fixture(), BASE), FeatureStore()
        store.add(observation())
        self.assertEqual(candidates(snapshot, store, 'event-probability'), [])
        store.add(observation(kind='resolution_risk', value='0'))
        proposals = candidates(snapshot, store, 'event-probability')
        self.assertTrue(proposals)
        result = allocate(snapshot, proposals)
        self.assertTrue(result['admitted'])
        self.assertFalse(result['executionEnabled'])
        store.add(observation(kind='resolution_risk', value='1', source=BASE + 1, received=BASE + 1))
        snapshot['generatedMs'] = BASE + 1
        self.assertEqual(candidates(snapshot, store, 'event-probability'), [])

    def test_complete_set_atomic_cash_and_dynamic_threshold(self):
        snapshot = validate(fixture(), BASE)
        proposals = candidates(snapshot, FeatureStore(), 'complete-set')
        self.assertEqual(len(proposals), 1)
        self.assertEqual(len(proposals[0]['legs']), 2)
        result = allocate(snapshot, proposals, per_group=D('3'))
        self.assertEqual(result['admitted'], [])
        self.assertEqual(result['proposalCashRemaining'], D(500))
        self.assertTrue(allocate(snapshot, proposals)['admitted'])
        self.assertIsNone(proposals[0]['fillProbability'])
        self.assertGreater(proposals[0]['dynamicThreshold'], D('.03'))

    def test_portfolio_greedy_shared_correlation_budget(self):
        snapshot = fixture()
        second = dict(snapshot['markets'][0], condition='second', first='c', second='d')
        snapshot['markets'].append(second)
        snapshot['books']['c'] = snapshot['books']['a'].copy()
        snapshot['books']['d'] = snapshot['books']['b'].copy()
        snapshot = validate(snapshot, BASE)
        proposals = candidates(snapshot, FeatureStore(), 'complete-set')
        result = allocate(snapshot, proposals, groups={'market': 'one', 'second': 'one'}, per_group=D('5'))
        self.assertEqual(len(result['admitted']), 1)
        self.assertLessEqual(result['worstCaseAcquisitionExposure'], D(5))
        self.assertEqual(len(allocate(snapshot, proposals + proposals)['admitted']), 2)

    def test_invalid_expired_marketable_short_are_rejected(self):
        snapshot = validate(fixture(), BASE)
        for key, value in [('price', '.6'), ('expiresMs', BASE), ('size', '1000'), ('buy', False)]:
            item = candidates(snapshot, FeatureStore(), 'complete-set')[0]
            item['legs'][0][key] = value
            self.assertEqual(allocate(snapshot, [item])['admitted'], [])

    def test_feature_evidence_is_replayed_with_proposals(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'features.jsonl'
            path.write_text(dumps(observation().record()) + '\n' + dumps(observation(kind='resolution_risk', value='0').record()) + '\n')
            class Client:
                def snapshot(self):
                    return validate(fixture(), BASE)
            run = Path(directory) / 'run'
            shadow_run(Client(), run, seconds=.01, strategy='event-probability', feature_path=path)
            self.assertEqual(replay_shadow(run, Path(directory) / 'replay.json')['matchedSnapshots'], 1)
            row = decode((run / 'observations.jsonl').read_text())
            self.assertEqual(len(row['featureEvidence']), 2)
            self.assertTrue(row['allocation']['admitted'])

    def test_missing_local_evidence_aborts_instead_of_becoming_network_error(self):
        class Client:
            def snapshot(self):
                return validate(fixture(), BASE)
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / 'run'
            with self.assertRaises(FileNotFoundError):
                shadow_run(Client(), run, seconds=.01, feature_path=Path(directory) / 'missing.jsonl')
            report = decode((run / 'report.json').read_text())
            self.assertFalse(report['complete'])
            self.assertEqual(report['networkErrors'], 0)

    def test_model_artifact_and_float_predictions_round_trip_exactly(self):
        data = [label(i, 'train' + str(i), 1000, i % 2) for i in range(40)]
        data += [label('test' + str(i), 'test' + str(i), 200000, i % 2) for i in range(40)]
        artifact = train(data, 100000, min_train=20, min_holdout=20, min_class=5)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'features.jsonl'
            path.write_text(dumps(observation(venue='polymarket', kind='volatility', value='.01').record()) + '\n')
            class Client:
                def snapshot(self):
                    return validate(fixture(), BASE)
            run = Path(directory) / 'run'
            shadow_run(Client(), run, seconds=.01, strategy='complete-set', feature_path=path, fill_model=artifact)
            self.assertEqual(replay_shadow(run, Path(directory) / 'replay.json')['matchedSnapshots'], 1)
            row = decode((run / 'observations.jsonl').read_text())
            proposal = row['allocation']['admitted'][0]
            self.assertIsNotNone(proposal['fillProbability'])
            self.assertFalse(proposal['fillModelQualified'])


class LearningTest(unittest.TestCase):
    def test_v2_size_depth_imbalance_contract_trains_and_infers(self):
        data = [label(i, 'train'+str(i), 1000, i%2) for i in range(40)]
        data += [label('test'+str(i), 'test'+str(i), 200000, i%2) for i in range(40)]
        for row in data:
            row['featuresV2'] = dict(row['features'], order_size='5', order_depth_ratio='.05', book_imbalance='0')
        artifact = train(data,100000,min_train=20,min_holdout=20,min_class=5,feature_schema='v2')
        self.assertEqual(len(artifact['model']['weights']),9)
        self.assertFalse(predict(artifact,data[0]['featuresV2'])['qualified'])
        with self.assertRaises(ValueError): predict(artifact,data[0]['features'])
        store=FeatureStore();store.add(observation(venue='polymarket',kind='volatility',value='.01'))
        proposals=candidates(validate(fixture(),BASE),store,'complete-set',fill_model=artifact)
        self.assertIsNotNone(proposals[0]['fillProbability'])
        self.assertFalse(proposals[0]['fillModelQualified'])

    def test_early_cancel_censored_and_future_features_rejected(self):
        row = label('1', 'm', 1000, False)
        row['cancelMs'] = 2000
        self.assertIsNone(example(row))
        row['featureObservedMs'] = 1001
        with self.assertRaises(ValueError):
            example(row)

    def test_second_leg_and_adverse_selection_targets(self):
        row = label('1', 'm', 1000, True)
        self.assertEqual(example(row, 'second_leg').label, 0)
        row['secondLegMs'] = 2000
        self.assertEqual(example(row, 'second_leg').label, 1)
        row['markout'], row['markoutObservedMs'], row['labelEndMs'] = '-.1', 6010, 6010
        self.assertEqual(example(row, 'adverse_selection').label, 1)
        row['markoutObservedMs'] = 6000
        with self.assertRaises(ValueError):
            example(row, 'adverse_selection')

    def test_missing_labels_are_insufficient_never_fake_model(self):
        artifact = train([], 100000)
        self.assertIsNone(artifact['model'])
        self.assertFalse(artifact['modelQualified'])
        self.assertIsNone(predict(artifact, {})['probability'])

    def test_group_purge_baseline_calibration_and_unqualified_prediction(self):
        data = [label(i, 'train' + str(i), 1000, i % 2) for i in range(40)]
        data += [label('test' + str(i), 'test' + str(i), 200000, i % 2) for i in range(40)]
        data += [label('cross1', 'cross', 1000, True), label('cross2', 'cross', 200000, False)]
        artifact = train(data, 100000, min_train=20, min_holdout=20, min_class=5)
        self.assertEqual(artifact['purgedRows'], 2)
        self.assertEqual(artifact['status'], 'RESEARCH_MODEL_UNQUALIFIED')
        self.assertAlmostEqual(artifact['holdoutBrier'], artifact['baselineBrier'])
        self.assertEqual(sum(x['count'] for x in artifact['calibration']), 40)
        self.assertFalse(predict(artifact, data[0]['features'])['qualified'])
        data[0]['provenance'] = 'VENUE_EXECUTION'
        self.assertIsNone(train(data, 100000, min_train=20, min_holdout=20, min_class=5)['model'])

    def test_duplicate_labels_and_cancellation_tie_are_invalid(self):
        row = label('1', 'm', 1000, True)
        with self.assertRaises(ValueError):
            train([row, row], 100000)
        row['cancelMs'] = row['fillMs']
        with self.assertRaises(ValueError):
            example(row)


class PortfolioAndIsolationTest(unittest.TestCase):
    def test_joint_history_anti_correlation_and_future_unknown(self):
        snapshot = fixture()
        snapshot['account']['holdings'] = {t: {'shares': '10', 'basis': '4'} for t in ('a', 'b')}
        snapshot['generatedMs'] = BASE + 2000
        snapshot['inputMs'] = BASE + 2000
        panel = [(BASE, {'a': '.4', 'b': '.6'}), (BASE + 1000, {'a': '.5', 'b': '.5'}), (BASE + 2000, {'a': '.4', 'b': '.6'})]
        risk = historical_risk(snapshot, panel, min_samples=2)
        self.assertEqual(risk['var'], 0)
        self.assertEqual(risk['correlations']['a']['b'], D(-1))
        self.assertEqual(risk['worstCaseAcquisitionExposure'], 8)
        with self.assertRaises(ValueError):
            historical_risk(snapshot, panel + [(BASE + 3000, {'a': '.4'})])
        self.assertIsNone(historical_risk(snapshot, panel[:-1], min_samples=2)['var'])

    def test_missing_intervals_not_interpolated_constant_correlation_unknown(self):
        snapshot = fixture()
        snapshot['account']['holdings']['a'] = {'shares': '5', 'basis': '2'}
        snapshot['generatedMs'] = BASE + 3000
        panel = [(BASE, {'a': '.4'}), (BASE + 1000, {'a': '.4'}), (BASE + 3000, {'a': '.4'})]
        self.assertIsNone(historical_risk(snapshot, panel, min_samples=2)['var'])
        panel.insert(2, (BASE + 2000, {'a': '.4'}))
        self.assertIsNone(historical_risk(snapshot, panel, min_samples=2)['correlations']['a']['a'])

    def config(self):
        return [{'alias': 'a', 'origin': 'http://127.0.0.1:8080', 'stateDirectory': '/tmp/account-a', 'roles': ['read', 'research']},
                {'alias': 'b', 'origin': 'http://127.0.0.1:8081', 'stateDirectory': '/tmp/account-b', 'roles': ['read']}]

    def test_account_isolation_permissions_and_cross_routing(self):
        registry = AccountRegistry(self.config())
        registry.accept('a', fixture(), BASE)
        self.assertTrue(registry.research_allowed('a'))
        with self.assertRaises(ValueError):
            registry.accept('b', fixture(), BASE)
        second = fixture()
        second['sessionId'] = 'other'
        registry.accept('b', second, BASE)
        self.assertFalse(registry.research_allowed('b'))
        self.assertEqual(registry.report()['aggregateCash'], 1000)
        self.assertFalse(registry.report()['capitalTransfersEnabled'])
        self.assertEqual(registry.fund_valuation(BASE)['aggregateIndicativeNav'], 1000)
        self.assertIsNone(registry.fund_valuation(BASE + 3000)['aggregateIndicativeNav'])

    def test_rejects_shared_or_nested_account_state(self):
        config = self.config()
        config[1]['stateDirectory'] = config[0]['stateDirectory'] + '/nested'
        with self.assertRaises(ValueError):
            AccountRegistry(config)

    def test_multi_outcome_conversion_and_collateral_are_scenarios(self):
        data = {'outcomes': ['a', 'b', 'c'], 'metadataSha256': HASH, 'negativeRisk': True, 'augmented': False, 'complete': True}
        result = analyze_basket(data, {'a': '.2', 'b': '.3', 'c': '.4'}, 5, '.01')
        self.assertEqual(result['hypotheticalNet'], D('.49'))
        self.assertEqual(set(convert_no(data, 'a')['hypotheticalYesShares']), {'b', 'c'})
        data['augmented'] = True
        self.assertIsNone(analyze_basket(data, {'a': '.2', 'b': '.3', 'c': '.4'}, 5)['hypotheticalPayout'])
        with self.assertRaises(ValueError):
            convert_no(data, 'a')
        evidence = {'chainId': 137, 'tokenAddress': '0x' + '1' * 40, 'symbol': 'pUSD', 'decimals': 6, 'observedMs': BASE, 'evidenceSha256': HASH}
        self.assertFalse(collateral_check(evidence, BASE)['chainVerified'])
        evidence['symbol'] = 'USDC'
        with self.assertRaises(ValueError):
            collateral_check(evidence, BASE)
        self.assertEqual(gas_scenario(100000, 10**9, 1, 2)['estimatedPerItemUsd'], D('.00005'))
