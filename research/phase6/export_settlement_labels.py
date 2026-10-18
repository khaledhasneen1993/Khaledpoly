"""Freeze exact research replay bindings from already corroborated receipts, no network."""
import argparse
import json
from pathlib import Path
from research.phase6.order_window import read_evidence
from research.phase6.settlement_matching_lab import run, validated_portions


def export():
    folder=Path('research/experiments/order-window-20261018')
    evidence=read_evidence(folder/'evidence.json.gz.b64')
    receipts=json.loads(Path('research/experiments/candidate-receipt-audit-20261018/offline-volume-labels.json').read_text())
    audit=json.loads((folder/'baseline-order-audit.json').read_text())
    calibration=run(evidence,receipts,audit)
    results={r['transactionHash']:r for r in receipts['results']}; bindings=[]
    for binding in calibration['bindings']:
        result=results[binding['transactionHash']];sample=result['sample']
        pair=[sample['asset_id'],sample['targetToken']]
        portions=validated_portions(result,set(pair)); wanted={p['identity'] for p in portions}
        rows=[r for r in result['matches'] if (r['exchange'],result['transactionHash'],r['ordersMatchedLogIndex'],r['maker']['logIndex']) in wanted]
        bindings.append(dict(binding,token=sample['asset_id'],side=sample['side'],price=sample['price'],size=sample['size'],
                             pair=pair,matches=rows))
    return dict(experiment='CS-MINT-LAB0',partialLabels=True,liveAllowed=False,
                logicalTapeSha256=evidence['logicalTapeSha256'],bindings=bindings)


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
    with Path(a.output).open('x') as target:target.write(json.dumps(export(),indent=2)+'\n')


if __name__=='__main__':main()
