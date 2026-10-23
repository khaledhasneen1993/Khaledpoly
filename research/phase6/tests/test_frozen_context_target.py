import unittest
from research.phase6.extract_frozen_context import validate_target


class FrozenContextTargetTest(unittest.TestCase):
    def test_exact_frame_and_standalone_gap_accepted(self):
        event=dict(kind='GAP',data=dict(reason='invalid_depth'))
        validate_target(dict(frames=[dict(normalized=dict(arrivalMs=100,data=dict(events=[event])))],standaloneGaps=[]),dict(originalTerminalMs=100))
        validate_target(dict(frames=[],standaloneGaps=[dict(kind='RESEARCH_GAP',arrivalMs=100,data=event['data'])]),dict(originalTerminalMs=100))

    def test_wrong_clock_or_reason_not_silently_missing(self):
        for clock,reason in [(101,'invalid_depth'),(100,'stale')]:
            with self.assertRaisesRegex(ValueError,'GAP absent'):
                validate_target(dict(frames=[],standaloneGaps=[dict(kind='RESEARCH_GAP',arrivalMs=clock,data=dict(reason=reason))]),dict(originalTerminalMs=100))
