import unittest
from unittest.mock import patch
from research.phase6.receipt_audit import decode_matches, rpc, EXCHANGES


class ReceiptAuditTest(unittest.TestCase):
    def logs(self):
        address=sorted(EXCHANGES)[0]; topics={'filled':'0x'+'1'*64,'matched':'0x'+'2'*64}
        maker='0x'+'a'*64; taker='0x'+'b'*64; wallet='0x'+'0'*24+'c'*40
        encode=lambda values:'0x'+''.join(format(x,'064x') for x in values)
        logs=[dict(logIndex='0x1',address=address,topics=[topics['filled'],maker,'0x'+'0'*24+'d'*40,wallet],data=encode([0,11,400000,1000000,0,0,0])),
              dict(logIndex='0x2',address=address,topics=[topics['filled'],taker,wallet,'0x'+'0'*24+address[2:]],data=encode([0,22,600000,1000000,0,0,0])),
              dict(logIndex='0x3',address=address,topics=[topics['matched'],taker,wallet],data=encode([0,22,600000,1000000]))]
        return logs,topics

    def test_mint_route_joins_one_maker_and_one_taker_not_two_fills(self):
        logs,topics=self.logs(); result=decode_matches(logs,topics)
        self.assertEqual(len(result),1); self.assertEqual(result[0]['matchType'],'MINT')
        self.assertEqual(result[0]['maker']['token'],'11');self.assertEqual(result[0]['taker']['token'],'22')

    def test_duplicates_unclosed_groups_and_untrusted_addresses(self):
        logs,topics=self.logs()
        with self.assertRaises(ValueError): decode_matches(logs+[logs[0]],topics)
        with self.assertRaises(ValueError): decode_matches(logs[:-1],topics)
        for row in logs: row['address']='0x'+'0'*40
        self.assertEqual(decode_matches(logs,topics),[])

    def test_rpc_cannot_submit_or_sign_anything(self):
        with patch('research.phase6.receipt_audit.urlopen') as network:
            for method in ('eth_sendTransaction','eth_sendRawTransaction','personal_sign'):
                with self.assertRaises(ValueError):rpc(method,[])
            network.assert_not_called()
