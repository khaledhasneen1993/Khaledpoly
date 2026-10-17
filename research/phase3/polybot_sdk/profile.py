"""Measured Python screening latency; this is not network/order latency."""
import platform
import statistics
import time
from .model import validate
from .strategy import evaluate
from .runtime import implementation_hash


def benchmark(data, iterations=500):
    if not 10 <= iterations <= 10000:
        raise ValueError('Benchmark requires 10..10000 observations')
    values = []
    for _ in range(iterations):
        start = time.perf_counter_ns()
        observation = validate(data, data['generatedMs'])
        evaluate(observation)
        values.append((time.perf_counter_ns() - start) / 1000000)
    values.sort()
    return {'scope': 'IN_PROCESS_SINGLE_RECORDED_OBSERVATION', 'samples': iterations,
            'python': platform.python_version(), 'platform': platform.platform(),
            'implementationHash': implementation_hash(), 'p50Ms': statistics.median(values),
            'p95Ms': values[int(.95 * (len(values) - 1))], 'p99Ms': values[int(.99 * (len(values) - 1))],
            'maxMs': max(values), 'orderNetworkLatencyMeasured': False,
            'rustGrpcMigrationJustified': False, 'executionEnabled': False}
