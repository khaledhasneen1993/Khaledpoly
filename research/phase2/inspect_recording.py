#!/usr/bin/env python3
"""Summarize actual capture quality. Callback receipt includes upstream/JDK buffering."""
import bisect
import collections
import json
import pathlib
import sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]))
from research.phase3.polybot_sdk.tapes import open_tape, recorded_tapes

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
    frames = processing = append = intervals = queue_wait = ingress = 0
    last_journal = {}
    run_id = None
    clean = False
    framed = False
    pending_frame = None
    previous_frame = 0
    observations = collections.Counter()
    heartbeats = 0
    last_heartbeat = {}
    disconnects = []

    def observation(kind, data, at):
        observations[kind] += 1
        if kind == 'GAP':
            gaps[data.get('reason', 'unknown')] += 1
            if data.get('reason') == 'disconnect' and len(disconnects) < 20:
                disconnects.append(dict(at=at, **data))
            if data.get('reason') == 'stale_source':
                age, process = data.get('callbackSourceAgeMs'), data.get('processingAgeMs')
                stage = 'unmeasured'
                if age is not None and process is not None:
                    stage = 'already_stale_at_callback' if age > 2000 else 'crossed_limit_during_processing'
                    if age < -1000:
                        stage = 'future_source_or_clock_error'
                stale_stages[stage] += 1
        elif kind == 'BOOK':
            normalization.add(at - data['sourceMs'])
    with open_tape(tape, 'rt') as stream:
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
            elif kind == 'DATASET_CONFIG':
                framed = data.get('format') == 'normalized-public-v2'
            elif kind == 'RESEARCH_FRAME':
                frame_id = data.get('frameId')
                if not framed or pending_frame is None or frame_id != pending_frame:
                    raise ValueError('Frame has no matching raw observation')
                if not isinstance(data.get('events'), list):
                    raise ValueError('Invalid frame events')
                for event in data['events']:
                    if event.get('kind') not in {'BOOK', 'TRADE', 'TICK_SIZE', 'GAP'}:
                        raise ValueError('Invalid frame event')
                    observation(event['kind'], event['data'], row['arrivalMs'])
                previous_frame, pending_frame = frame_id, None
            elif kind in {'RESEARCH_BOOK', 'RESEARCH_GAP', 'RESEARCH_TRADE', 'RESEARCH_TICK_SIZE'}:
                if framed and kind != 'RESEARCH_GAP':
                    raise ValueError('Unframed market observation in v2 dataset')
                observation(kind[9:], data, row['arrivalMs'])
            elif kind == 'RAW_MARKET':
                if framed:
                    frame_id = data.get('frameId', -1)
                    if pending_frame is not None or frame_id <= previous_frame:
                        raise ValueError('Missing, duplicate or unordered frame boundary')
                    pending_frame = frame_id
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
            elif kind == 'WS_HEARTBEAT':
                heartbeats += 1
                last_heartbeat = data
            elif kind == 'WS_PIPELINE':
                intervals += 1
                frames += data['frames']
                processing = max(processing, data.get('maxDecoderProcessingMicros', data.get('maxCallbackProcessingMicros', 0)))
                ingress = max(ingress, data.get('maxIngressCallbackMicros', 0))
                append = max(append, data['maxRawAppendMicros'])
                queue_wait = max(queue_wait, data.get('maxQueueWaitMicros', 0))
                last_journal = data['journal']
    if pending_frame is not None:
        raise ValueError('Raw observation without completed frame')
    return {'frameAtomicity': 'recorded-frame-v1' if framed else 'legacy-unframed',
            'normalizedEvents': dict(observations),
            'heartbeat': {'samples': heartbeats, 'lastSample': last_heartbeat, 'disconnects': disconnects},
            'run': pathlib.Path(tape).parent.name, 'events': dict(counts),
            'durationMs': None if first is None else last - first, 'errors': errors,
            'gapReasons': dict(gaps), 'staleStages': dict(stale_stages),
            'callbackSourceAge': source_age.report(), 'callbackToJournal': dispatch.report(),
            'normalizedSourceAge': normalization.report(), 'recordingClosedCleanly': clean,
            'pipeline': {'intervals': intervals, 'frames': frames,
                         'maxDecoderProcessingMicros': processing, 'maxIngressCallbackMicros': ingress, 'maxRawAppendMicros': append,
                         'maxQueueWaitMicros': queue_wait,
                         'lastJournalSample': last_journal},
            'decision': 'NO_GO',
            'reason': 'Short diagnostic capture does not meet the preregistered heldout acceptance gate'}


def main():
    root = pathlib.Path(sys.argv[1])
    summary = [inspect(tape) for tape in recorded_tapes(root)]
    if not summary:
        raise ValueError('No recording files produced')
    (root / 'collection-summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
