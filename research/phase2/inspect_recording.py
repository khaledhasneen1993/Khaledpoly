#!/usr/bin/env python3
"""Summarize actual capture quality. Callback receipt includes upstream/JDK buffering."""
import bisect
import collections
import json
import pathlib
import sys

BUCKETS = [-1000, -1, 0, 1, 5, 10, 25, 50, 100, 250, 500, 1000, 1500, 2000, 3000, 5000, 10000]


class Histogram:
    def __init__(self):
        self.counts = collections.Counter()
        self.count = 0
        self.maximum = None

    def add(self, value):
        self.counts[bisect.bisect_left(BUCKETS, value)] += 1
        self.count += 1
        self.maximum = value if self.maximum is None else max(self.maximum, value)

    def report(self):
        return {'count': self.count, 'maxMs': self.maximum,
                'upperBoundMs': {str(BUCKETS[i]) if i < len(BUCKETS) else '>10000': n
                                 for i, n in sorted(self.counts.items())}}


def inspect(tape):
    counts = collections.Counter()
    gaps = collections.Counter()
    stale_stages = collections.Counter()
    errors = []
    first = last = None
    expected = 0
    source_age = Histogram()
    dispatch = Histogram()
    normalization = Histogram()
    frames = processing = append = intervals = 0
    last_journal = {}
    run_id = None
    clean = False
    with pathlib.Path(tape).open() as stream:
        for line in stream:
            row = json.loads(line)
            expected += 1
            if row['seq'] != expected:
                raise ValueError('Recording sequence gap')
            if run_id is None:
                run_id = row['runId']
            if row['runId'] != run_id:
                raise ValueError('Mixed recording runs')
            if last is not None and row['arrivalMs'] < last:
                raise ValueError('Receive clock regressed')
            counts[row['kind']] += 1
            if first is None:
                first = row['arrivalMs']
            last = row['arrivalMs']
            kind, data = row['kind'], row['data']
            if clean:
                raise ValueError('Events after RUN_END')
            if kind == 'RUN_END':
                clean = data.get('complete') is True
            elif kind == 'RESEARCH_FEED_ERROR':
                # Bound memory even for a long recording with repeated transport failures.
                if len(errors) < 20:
                    errors.append(data)
            elif kind == 'RESEARCH_GAP':
                gaps[data.get('reason', 'unknown')] += 1
                if data.get('reason') == 'stale_source':
                    age = data.get('callbackSourceAgeMs')
                    process = data.get('processingAgeMs')
                    stage = 'unmeasured'
                    if age is not None and process is not None:
                        stage = 'already_stale_at_callback' if age > 2000 else 'crossed_limit_during_processing'
                        if age < -1000:
                            stage = 'future_source_or_clock_error'
                    stale_stages[stage] += 1
            elif kind == 'RAW_MARKET':
                received = data.get('callbackReceivedMs', row['arrivalMs'])
                if 'callbackReceivedMs' in data:
                    dispatch.add(row['arrivalMs'] - received)
                try:
                    root = json.loads(data['text'])
                    for node in root if isinstance(root, list) else [root]:
                        stamp = int(node.get('timestamp', 0))
                        if stamp > 0:
                            if stamp < 100000000000:
                                stamp *= 1000
                            source_age.add(received - stamp)
                except (ValueError, TypeError, AttributeError):
                    pass
            elif kind == 'RESEARCH_BOOK':
                normalization.add(row['arrivalMs'] - data['sourceMs'])
            elif kind == 'WS_PIPELINE':
                intervals += 1
                frames += data['frames']
                processing = max(processing, data['maxCallbackProcessingMicros'])
                append = max(append, data['maxRawAppendMicros'])
                last_journal = data['journal']
    return {'run': pathlib.Path(tape).parent.name, 'events': dict(counts),
            'durationMs': None if first is None else last - first, 'errors': errors,
            'gapReasons': dict(gaps), 'staleStages': dict(stale_stages),
            'callbackSourceAge': source_age.report(), 'callbackToJournal': dispatch.report(),
            'normalizedSourceAge': normalization.report(), 'recordingClosedCleanly': clean,
            'pipeline': {'intervals': intervals, 'frames': frames,
                         'maxCallbackProcessingMicros': processing, 'maxRawAppendMicros': append,
                         'lastJournalSample': last_journal},
            'decision': 'NO_GO',
            'reason': 'Short diagnostic capture does not meet the preregistered heldout acceptance gate'}


def main():
    root = pathlib.Path(sys.argv[1])
    summary = [inspect(tape) for tape in root.glob('*/events.jsonl')]
    if not summary:
        raise ValueError('No recording files produced')
    (root / 'collection-summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
