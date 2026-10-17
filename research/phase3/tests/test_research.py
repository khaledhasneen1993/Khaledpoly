import copy
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from decimal import Decimal as D
from unittest.mock import patch
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from research.phase3.polybot_sdk.model import validate, decode, dumps
from research.phase3.polybot_sdk.client import PaperClient, NoRedirect
from research.phase3.polybot_sdk.strategy import propose, evaluate
from research.phase3.polybot_sdk.runtime import shadow_run, replay_shadow

BASE = 1800000000000
TOKEN = 'phase3-test-token-with-32-characters'


def fixture():
    return {'schema': 1, 'mode': 'PAPER', 'researchOnly': True, 'executionEnabled': False,
            'liveAllowed': False, 'sessionId': 'fixture', 'sequence': 1,
            'inputMs': BASE, 'generatedMs': BASE, 'maxBookAgeMs': 2000,
            'metadataMaxAgeMs': 60000, 'truncated': False,
            'account': {'id': 'paper-default', 'cash': '500', 'availableCash': '500',
                        'halted': False, 'pendingTakers': 0, 'holdings': {}, 'orders': {}},
            'markets': [{'condition': 'market', 'first': 'a', 'second': 'b', 'startMs': BASE,
                         'endMs': BASE + 900000, 'tick': '.01', 'minSize': '5', 'feeRate': '.07',
                         'feeExponent': 1, 'accepting': True, 'observedMs': BASE, 'evidence': 'fixture'}],
            'books': {t: {'sourceMs': BASE, 'receivedMs': BASE, 'depthTruncated': False,
                          'bids': [{'price': '.4', 'size': '100'}],
                          'asks': [{'price': '.6', 'size': '100'}]} for t in ('a', 'b')}}


class ResearchTest(unittest.TestCase):
    def test_detached_decimal_observation(self):
        source = fixture()
        source['account']['cash'] = source['account']['availableCash'] = D('500.123456789123456789')
        obs = validate(source, BASE)
        source['books']['a']['bids'][0]['price'] = '.99'
        self.assertEqual(D(obs['account']['cash']), D('500.123456789123456789'))
        self.assertEqual(obs['books']['a']['bids'][0]['price'], '.4')

    def test_fail_closed_flags_and_clock(self):
        for key, value in [('mode', 'LIVE'), ('executionEnabled', True), ('liveAllowed', True),
                           ('truncated', True), ('schema', True), ('inputMs', BASE + 1),
                           ('generatedMs', BASE - 1), ('maxBookAgeMs', 999999), ('sequence', 0)]:
            data = fixture()
            data[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate(data, BASE)
        with self.assertRaises(ValueError):
            validate(fixture(), BASE + 2001)

    def test_book_validation(self):
        for change in ({'sourceMs': BASE + 1}, {'receivedMs': BASE + 1},
                       {'bids': [{'price': '.7', 'size': '1'}]},
                       {'asks': [{'price': '.6', 'size': '-1'}]}):
            data = fixture()
            data['books']['a'].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate(data, BASE)

    def test_reservation_accounting(self):
        data = fixture()
        data['account']['orders']['one'] = {'token': 'a', 'buy': True, 'price': '.4', 'remaining': '5'}
        with self.assertRaises(ValueError):
            validate(data, BASE)
        data['account']['availableCash'] = '498'
        validate(data, BASE)
        data['account']['orders']['one']['buy'] = False
        data['account']['availableCash'] = '500'
        with self.assertRaises(ValueError):
            validate(data, BASE)

    def test_metadata_identity_and_fee_validation(self):
        for change in ({'second': 'a'}, {'feeRate': '-1'}, {'feeExponent': 9}, {'observedMs': BASE + 1}):
            data = fixture()
            data['markets'][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate(data, BASE)

    def test_no_unowned_sells_and_passive_prices(self):
        obs = validate(fixture(), BASE)
        rows = propose(obs)['admitted']
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(x['buy'] and x['price'] < D('.6') for x in rows))
        self.assertTrue(all(x['price'] % D('.01') == 0 and x['expiresMs'] > BASE for x in rows))
        self.assertFalse(evaluate(obs)['executionEnabled'])
        self.assertIsNone(evaluate(obs)['netPnl'])

    def test_inventory_skew_and_no_cash_credit_for_sells(self):
        obs = fixture()
        obs['account']['holdings']['a'] = {'shares': '10', 'basis': '4'}
        rows = propose(validate(obs, BASE))['admitted']
        self.assertTrue(any(not x['buy'] and x['size'] <= 10 for x in rows))
        self.assertLess(next(x['price'] for x in rows if x['buy'] and x['token'] == 'a'), D('.41'))
        obs['account']['cash'] = obs['account']['availableCash'] = '0'
        rows = propose(validate(obs, BASE))['admitted']
        self.assertTrue(all(not x['buy'] for x in rows))

    def test_budget_group_and_existing_order_bounds(self):
        obs = validate(fixture(), BASE)
        result = propose(obs, per_group=D('3'))
        self.assertEqual(len(result['admitted']), 1)
        self.assertLessEqual(result['worstCaseAcquisitionExposure'], D('3'))
        self.assertEqual(len(propose(obs, gross_limit=D('1'))['admitted']), 0)
        obs['account']['orders']['one'] = {'token': 'a', 'buy': True, 'price': '.4', 'remaining': '5'}
        obs['account']['availableCash'] = '498'
        result = propose(validate(obs, BASE))
        self.assertTrue(all(x['token'] != 'a' for x in result['admitted']))

    def test_halt_pending_stale_and_truncated_abstain(self):
        for field, value in [('halted', True), ('pendingTakers', 1)]:
            obs = fixture()
            obs['account'][field] = value
            self.assertEqual(propose(validate(obs, BASE))['admitted'], [])
        obs = fixture()
        for book in obs['books'].values():
            book['depthTruncated'] = True
        self.assertEqual(propose(validate(obs, BASE))['admitted'], [])
        obs = fixture()
        for book in obs['books'].values():
            book['sourceMs'] = BASE - 2001
        self.assertEqual(propose(validate(obs, BASE))['admitted'], [])

    def test_json_duplicates_and_nonfinite(self):
        for raw in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}'):
            with self.assertRaises(ValueError):
                decode(raw)

    def test_origin_credentials_redirect_security(self):
        for origin in ('http://example.com', 'https://user:pass@example.com', 'https://example.com/path',
                       'https://example.com?token=x'):
            with self.assertRaises(ValueError):
                PaperClient(origin, TOKEN)
        with self.assertRaises(ValueError):
            PaperClient('http://localhost', 'short')
        with self.assertRaises(ValueError):
            NoRedirect().redirect_request(None, None, 302, '', {}, 'https://example.com')

    def test_actual_http_get_auth_and_identity(self):
        state, methods = fixture(), []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                methods.append(self.command)
                if self.headers.get('X-Polybot-Token') != TOKEN:
                    self.send_response(401)
                    self.end_headers()
                    return
                self.send_response(200)
                self.end_headers()
                self.wfile.write(dumps(state).encode())
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        origin = 'http://127.0.0.1:' + str(server.server_port)
        try:
            client = PaperClient(origin, TOKEN)
            self.assertEqual(client.snapshot(BASE)['sessionId'], 'fixture')
            state['sessionId'] = 'restarted'
            with self.assertRaises(ValueError):
                client.snapshot(BASE)
            with self.assertRaises(HTTPError):
                PaperClient(origin, TOKEN + 'wrong').snapshot(BASE)
            self.assertEqual(methods, ['GET', 'GET', 'GET'])
        finally:
            server.shutdown()
            server.server_close()
            worker.join()

    def test_record_replay_and_tamper_detection(self):
        class Client:
            def snapshot(self):
                return validate(fixture(), BASE)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'run'
            report = shadow_run(Client(), path, seconds=.01)
            self.assertEqual(report['snapshots'], 1)
            self.assertIsNone(report['netPnl'])
            self.assertEqual(replay_shadow(path, Path(directory) / 'replay.json')['matchedSnapshots'], 1)
            self.assertNotIn(TOKEN, (path / 'manifest.json').read_text())
            with self.assertRaises(FileExistsError):
                shadow_run(Client(), path, seconds=.01)
            tape = path / 'observations.jsonl'
            tape.write_text(tape.read_text().replace('UNVALIDATED_SHADOW_ONLY', 'tampered'))
            with self.assertRaises(ValueError):
                replay_shadow(path, Path(directory) / 'bad.json')

    def test_failed_recording_and_sequence_regression(self):
        class Client:
            def snapshot(self):
                raise ValueError('Unsafe data')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'run'
            with self.assertRaises(ValueError):
                shadow_run(Client(), path, seconds=.01)
            self.assertFalse(decode((path / 'report.json').read_text())['complete'])
            with self.assertRaises(ValueError):
                replay_shadow(path, Path(directory) / 'bad.json')

    def test_java_http_contract(self):
        path = ROOT / 'executor-service/target/phase3-snapshot.json'
        self.assertTrue(path.exists(), 'Run Maven verify before Python contract tests')
        data = decode(path.read_text())
        obs = validate(data, data['generatedMs'])
        self.assertEqual(obs['sequence'], 2)
        self.assertEqual(set(obs['books']), {'a', 'b'})
        self.assertFalse(obs['liveAllowed'])


if __name__ == '__main__':
    unittest.main()
