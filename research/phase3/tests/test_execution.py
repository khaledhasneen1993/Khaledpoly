from pathlib import Path
import sys
import tempfile
import unittest
from io import BytesIO
from decimal import Decimal as D
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from test_research import BASE, TOKEN, fixture
from test_extensions import label
from research.phase3.polybot_sdk.execution import PaperExecutionClient, execute_paper, reconcile_paper
from research.phase3.polybot_sdk.model import decode, dumps
from research.phase3.polybot_sdk.labels import build_labels
from research.phase3.polybot_sdk.learning import train


class ExecutionAndLabelsTest(unittest.TestCase):
    def test_paper_client_requires_explicit_virtual_mode_and_fixed_route(self):
        client = PaperExecutionClient('http://127.0.0.1:8080', TOKEN)
        observation = fixture()
        with patch('research.phase3.polybot_sdk.model.time.time', return_value=BASE / 1000):
            with self.assertRaises(ValueError):
                client.submit(observation, 'test', [], 'one')
        requests = []
        class Response(BytesIO):
            status = 200
        class Opener:
            def open(self, request, timeout):
                requests.append(request)
                return Response(dumps({'id': 'one', 'status': 'PAPER_SUBMITTED', 'virtualOnly': True,
                                       'executionEnabled': False, 'liveAllowed': False}).encode())
        client._opener = Opener()
        observation['paperExecutionEnabled'] = True
        with patch('research.phase3.polybot_sdk.model.time.time', return_value=BASE / 1000):
            receipt = client.submit(observation, 'test', [], 'one')
        self.assertEqual(receipt['status'], 'PAPER_SUBMITTED')
        self.assertEqual(requests[0].full_url, 'http://127.0.0.1:8080/api/research/v1/proposals/paper')
        self.assertEqual(requests[0].method, 'POST')
        client.retry_identical(decode(requests[0].data))
        self.assertEqual(requests[0].data, requests[1].data)

    def test_unknown_post_outcome_has_durable_identical_request_and_reconciliation(self):
        requests = []
        class Client:
            def snapshot(self):
                row = fixture()
                row['paperExecutionEnabled'] = True
                return row
            def retry_identical(self, request):
                requests.append(request)
                raise TimeoutError('Unknown POST outcome')
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / 'run'
            with self.assertRaises(TimeoutError):
                execute_paper(Client(), run, seconds=.01)
            rows = [decode(line) for line in (run / 'execution.jsonl').read_text().splitlines()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['kind'], 'PAPER_REQUEST')
            self.assertEqual(requests[0], requests[1])
            self.assertEqual(rows[0]['proposal']['id'], requests[0]['id'])
            self.assertFalse(decode((run / 'report.json').read_text())['complete'])
            class Recovery:
                def retry_identical(self, request):
                    self.received = request
                    return {'id': request['id'], 'status': 'PAPER_ALREADY_RECORDED', 'virtualOnly': True,
                            'executionEnabled': False, 'liveAllowed': False}
            recovery = Recovery()
            result = reconcile_paper(recovery, run, Path(directory) / 'reconciled.json')
            self.assertEqual(result['newIdsCreated'], 0)
            self.assertEqual(recovery.received, rows[0]['proposal'])

    def test_java_real_http_execution_builds_causal_labels(self):
        tape = ROOT / 'executor-service/target/phase3-execution-events.jsonl'
        self.assertTrue(tape.exists(), 'Maven HTTP execution/replay test must run first')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'labels'
            report = build_labels(tape, output)
            self.assertEqual(report['ordersWithFeatures'], 2)
            self.assertEqual(report['fillLabels'], 2)
            self.assertEqual(report['secondLegLabels'], 2)
            self.assertEqual(report['markoutLabels'], 2)
            self.assertFalse(report['venueExecutionEvidence'])
            rows = [decode(line) for line in (output / 'labels.jsonl').read_text().splitlines()]
            self.assertTrue(all(row['featureObservedMs'] <= row['submittedMs'] <= row['fillMs'] for row in rows))
            self.assertTrue(all(D(row['markout']) == D('.09') for row in rows))
            self.assertIsNone(train(rows, BASE + 100000)['model'])

    def test_label_builder_refuses_incomplete_recording(self):
        with tempfile.TemporaryDirectory() as directory:
            tape = Path(directory) / 'tape.jsonl'
            tape.write_text(dumps({'schema': 1, 'seq': 1, 'runId': 'one', 'arrivalMs': BASE,
                                   'kind': 'RUN_END', 'data': {'complete': False}}) + '\n')
            with self.assertRaises(ValueError):
                build_labels(tape, Path(directory) / 'labels')

    def test_cross_market_intent_groups_are_purged_together(self):
        data = [label('one', 'first-market', 1000, True), label('two', 'second-market', 200000, False)]
        for row in data:
            row['groupId'] = 'same-external-intent'
        report = train(data, 100000, min_train=1, min_holdout=1, min_class=1)
        self.assertEqual(report['purgedRows'], 2)
        self.assertEqual(report['trainingRows'], 0)
        self.assertEqual(report['holdoutRows'], 0)
