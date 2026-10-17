"""Phase-4 data audit requires independent, matching timelines."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from research.phase4 import final_gate
from research.phase3.polybot_sdk.model import dumps

START=1800000000000
DAY=86400000

def cex(start,end,issues=None):
    return {'sessions':2,'issues':issues or [],'startedAtMs':start,'endedAtMs':end}

def clob_report(gaps=None):
    return {'recordingClosedCleanly':True,'gapReasons':gaps or {},'errors':[],
            'frameAtomicity':'recorded-frame-v1','events':{'RAW_MARKET':2},
            'normalizedEvents':{'BOOK':2}}

def tape(path,start,end):
    # Simulate bounded market observations throughout the full time span.
    with path.open('w') as out:
        cursor = start
        while cursor < end:
            out.write(dumps({'arrivalMs':cursor,'kind':'RAW_MARKET'})+'\n')
            cursor += 300000
        out.write(dumps({'arrivalMs':end,'kind':'RUN_END'})+'\n')
    return path

class AcceptanceTest(unittest.TestCase):
    def test_not_enough_common_days_never_passes(self):
        with tempfile.TemporaryDirectory() as d:
            path=tape(Path(d)/'events.jsonl',START,START+8*DAY)
            with patch('research.phase4.audit.audit_capture') as unused:
                with patch('research.phase4.final_gate.audit_capture',
                           return_value=cex(START+3*DAY,START+8*DAY)):
                    with patch('research.phase2.inspect_recording.inspect',return_value=clob_report()):
                        result=final_gate.evaluate(['c'],[path],days=7)
            self.assertIn('INSUFFICIENT_OVERLAPPING_FULL_UTC_DAYS',result['issues'])
            self.assertEqual(result['decision'],'NO_GO')

    def test_even_sufficient_capture_is_not_settlement_or_strategy_approval(self):
        with tempfile.TemporaryDirectory() as d:
            midnight=(START//DAY)*DAY
            path=tape(Path(d)/'events.jsonl',midnight,midnight+8*DAY)
            with patch('research.phase4.final_gate.audit_capture',
                       return_value=cex(midnight,midnight+8*DAY)):
                with patch('research.phase2.inspect_recording.inspect',return_value=clob_report()):
                    result=final_gate.evaluate(['c'],[path],days=7)
            self.assertTrue(result['publicCaptureGatePassed'])
            self.assertFalse(result['phase4Complete'])
            self.assertFalse(result['venueFillEvidence'])
            self.assertFalse(result['marketUniverseAndSettlementEvidenceVerified'])
            self.assertFalse(result['liveAllowed'])

    def test_source_gaps_and_incomplete_frame_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            midnight=(START//DAY)*DAY
            path=tape(Path(d)/'events.jsonl',midnight,midnight+8*DAY)
            bad=clob_report({'disconnect':1})
            bad['recordingClosedCleanly']=False
            with patch('research.phase4.final_gate.audit_capture',
                       return_value=cex(midnight,midnight+8*DAY, ['bybit-spot:SOURCE_ACCESS_BLOCKED'])):
                with patch('research.phase2.inspect_recording.inspect',return_value=bad):
                    result=final_gate.evaluate(['c'],[path],days=7)
            self.assertIn('POLYMARKET_INCOMPLETE_TAPE',result['issues'])
            self.assertIn('POLYMARKET_SOURCE_GAPS_OR_ERRORS',result['issues'])
            self.assertIn('bybit-spot:SOURCE_ACCESS_BLOCKED',result['issues'])
            self.assertFalse(result['publicCaptureGatePassed'])

    def test_hidden_silent_market_gap_is_rejected_even_when_tape_is_closed(self):
        with tempfile.TemporaryDirectory() as d:
            midnight=(START//DAY)*DAY
            path=Path(d)/'events.jsonl'
            path.write_text(
                dumps({'arrivalMs':midnight,'kind':'RAW_MARKET'})+'\n'+
                dumps({'arrivalMs':midnight+4*DAY,'kind':'RUN_END'})+'\n'+
                dumps({'arrivalMs':midnight+8*DAY,'kind':'RAW_MARKET'})+'\n'
            )
            with patch('research.phase4.final_gate.audit_capture',
                       return_value=cex(midnight,midnight+8*DAY)):
                with patch('research.phase2.inspect_recording.inspect',return_value=clob_report()):
                    result=final_gate.evaluate(['c'],[path],days=7)
            self.assertIn('POLYMARKET_SILENT_MARKET_GAP',result['issues'])
            self.assertFalse(result['publicCaptureGatePassed'])

    def test_unterminated_raw_market_row_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'events.jsonl'
            path.write_text(dumps({'arrivalMs':START,'kind':'RAW_MARKET'}))
            with self.assertRaisesRegex(ValueError,'Unterminated'):
                final_gate.journal_stats(path)

    def test_reject_empty_and_truncated_journals(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'empty.jsonl'
            f.write_text('')
            with self.assertRaises(ValueError):
                final_gate.tape_bounds(f)
            f.write_text('{}')
            with self.assertRaises(ValueError):
                final_gate.tape_bounds(f)

if __name__=='__main__':
    unittest.main()
