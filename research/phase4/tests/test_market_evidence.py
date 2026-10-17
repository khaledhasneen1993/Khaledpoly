"""Tests for cautious V1/V2 market, event, orderbook, and API evidence."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from research.phase4 import market_evidence as e

CID='0x'+'a'*64
CID2='0x'+'b'*64
HASH='f'*64

def market(protocol='v1', condition=CID, id='1'):
    return {'id':id,'conditionId':condition,'version':protocol,
            'clobTokenIds':'["11","12"]' if protocol=='v1' else None,
            'positionIds':['21','22'] if protocol=='v2' else None}

class MarketEvidenceTest(unittest.TestCase):
    def test_v1_v2_identifiers_are_not_interchangeable(self):
        self.assertEqual(e._identity(market())['outcomeKind'],'clob-token')
        self.assertEqual(e._identity(market('v2'))['outcomeKind'],'position')
        broken=market('v2')
        broken['positionIds']=None
        broken['clobTokenIds']='["11","12"]'
        with self.assertRaises(ValueError):
            e._identity(broken)
        unknown=market()
        unknown['version']='future'
        with self.assertRaises(ValueError):
            e._identity(unknown)

    def test_event_rejects_incomplete_and_duplicate_binary_evidence(self):
        event={'id':'10','markets':[market(),market('v2',CID2,'2')],'negRisk':True}
        report=e.validate_event(event,'10')
        self.assertEqual(len(report['verifiedBinaryMarkets']),2)
        self.assertTrue(report['multiMarketEvent'])
        self.assertFalse(report['negativeRiskUniverseComplete'])
        event['markets'].append(market('v1',CID,'3'))
        report=e.validate_event(event,'10')
        self.assertEqual(len(report['invalidMarketRows']),1)
        self.assertFalse(report['terminalSettlementVerified'])
        with self.assertRaises(ValueError):
            e.validate_event(event,'11')

    def test_book_truncation_and_identity(self):
        book={'asset_id':'11','bids':[{'price':'.4','size':'1'}],
              'asks':[{'price':'.6','size':'1'}]}
        value=e.validate_book(book,'11')
        self.assertTrue(value['sourceIdentityVerified'])
        self.assertFalse(value['venueFillEvidence'])
        book['asset_id']='12'
        with self.assertRaises(ValueError):
            e.validate_book(book,'11')
        book['asset_id']='11'
        book['bids'].append({'price':'.4','size':'2'})
        with self.assertRaises(ValueError):
            e.validate_book(book,'11')

    def test_bounded_fetch_validated_but_always_no_go(self):
        calls=[]
        def fake_http(url):
            calls.append(url)
            if '/tags/slug/' in url:
                return {'id':'745','slug':'sports'}, HASH
            if '/events/keyset?' in url:
                return {'events':[{'id':'10'}], 'next_cursor':'more'}, HASH
            if '/events/10' in url:
                return {'id':'10','markets':[market(), market('v2',CID2,'2')]},HASH
            if '/clob-markets/' in url:
                return {'some':'unqualified fee evidence'},HASH
            if '/book?' in url:
                return {'asset_id':'11','bids':[{'price':'.45','size':'1'}],
                        'asks':[{'price':'.55','size':'1'}]},HASH
            raise AssertionError(url)
        with patch('research.phase4.market_evidence._http',fake_http):
            data=e.collect_event_evidence('sports',limit=1,max_books=2)
        self.assertEqual(data['observedEvents'],1)
        self.assertEqual(data['verifiedMarkets'],2)
        self.assertTrue(data['partialUniverse'])
        self.assertFalse(data['qualifiedFeeCurve'])
        self.assertFalse(data['negativeRiskUniverseComplete'])
        self.assertFalse(data['terminalSettlementVerified'])
        self.assertEqual(data['decision'],'NO_GO')
        self.assertEqual(data['events'][0]['verifiedBinaryMarkets'][1]['books']['status'],
                         'UNVERIFIED_V2_BOOK_ADAPTER')
        self.assertEqual(sum('/book?' in url for url in calls),1)

    def test_bad_page_remains_no_go(self):
        with patch('research.phase4.market_evidence._http',return_value=({'wrong':42},HASH)):
            data=e.collect_event_evidence('politics')
        self.assertEqual(data['errors'][0]['stage'],'discovery')
        self.assertEqual(data['decision'],'NO_GO')
        self.assertFalse(data['venueFillEvidence'])

if __name__ == '__main__':
    unittest.main()
