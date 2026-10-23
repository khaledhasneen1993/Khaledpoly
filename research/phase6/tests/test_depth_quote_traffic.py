import hashlib
import io
import json
import unittest
from research.phase6.depth_quote_traffic import collect


class DepthQuoteTrafficTest(unittest.TestCase):
    def fixture(self,source=1290,side='BUY',gap_at=None):
        rows=[dict(kind='DATASET_CONFIG',arrivalMs=0,data=dict(format='normalized-public-v2'))]
        frame=0
        def add(at,events,original):
            nonlocal frame
            frame+=1
            rows.append(dict(kind='RAW_MARKET',arrivalMs=at,data=dict(frameId=frame,text=json.dumps(original))))
            rows.append(dict(kind='RESEARCH_FRAME',arrivalMs=at,data=dict(frameId=frame,events=events)))
        add(1000,[dict(kind='BOOK',data=dict(token='a'))],dict(event_type='book'))
        if gap_at is not None:add(gap_at,[dict(kind='GAP',data=dict(token='b',reason='invalid_depth'))],dict(event_type='price_change'))
        token='b' if side=='BUY' else 'a'
        # Deliberately different public price: never reject a potential mixed
        # maker component by weighted/last public or 1-public-price arithmetic.
        sample=dict(asset_id=token,side=side,price='.9',size='6',timestamp=str(source),event_type='last_trade_price',transaction_hash='0x'+'1'*64)
        add(1300,[dict(kind='TRADE',data=dict(token=token,side=side,price='.9',size='6',sourceMs=source,tradeId=json.dumps(sample)))],sample)
        rows.append(dict(kind='RUN_END',arrivalMs=2000,data=dict(complete=True)))
        raw=b''.join((json.dumps(dict(r,schema=1,seq=i,runId='r'))+'\n').encode() for i,r in enumerate(rows,1))
        selection=[dict(id='q',condition='c',submitMs=1000,activationDueMs=1250,endMs=2000,originalSequence=3,
                        quotes=[dict(token='a',price='.48'),dict(token='b',price='.47')])]
        spec=dict(sourceRows=len(rows),logicalTapeSha256=hashlib.sha256(raw).hexdigest(),maxBookAgeMs=2000,activationMs=250)
        return raw,selection,spec

    def test_buy_and_sell_require_actual_receipts_not_aggregate_price(self):
        for side in ('BUY','SELL'):
            raw,selection,spec=self.fixture(side=side);r=collect(io.BytesIO(raw),selection,spec)
            self.assertEqual(r['observationCount'],1);self.assertEqual(r['fillsCreated'],0)
            self.assertFalse(r['netPnlRecomputed']);self.assertTrue(r['activationIsRelaxedDueTimeUpperBoundNotObserved'])
            self.assertFalse(r['states'][0]['observations'][0]['publicPriceEqualsQuote'])

    def test_pre_activation_and_gap_never_create_traffic(self):
        for options in (dict(source=1249),dict(gap_at=1200),dict(gap_at=1299)):
            raw,selection,spec=self.fixture(**options);r=collect(io.BytesIO(raw),selection,spec)
            self.assertEqual(r['observationCount'],0);self.assertEqual(r['decision'],'REJECT_SELECTED_START_STATES_NO_NECESSARY_TRAFFIC')

    def test_original_hash_clean_end_anchor_and_frame_binding_required(self):
        raw,selection,spec=self.fixture()
        with self.assertRaises(ValueError):collect(io.BytesIO(raw),selection,dict(spec,logicalTapeSha256='0'*64))
        with self.assertRaises(ValueError):collect(io.BytesIO(raw[:-1]),selection,spec)
        bad=[dict(selection[0],originalSequence=4)]
        with self.assertRaisesRegex(ValueError,'anchor'):collect(io.BytesIO(raw),bad,spec)
        changed=raw.replace(b'"frameId": 1',b'"frameId": 99',1)
        with self.assertRaisesRegex(ValueError,'Unbound'):collect(io.BytesIO(changed),selection,spec)


if __name__=='__main__':unittest.main()
