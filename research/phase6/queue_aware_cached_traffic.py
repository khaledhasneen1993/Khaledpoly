"""Reprice already-complete quote-agnostic actual receipts at frozen QW0 bids.

Original observation binding is NEVER rewritten to manufacture a different
targetBid match. New evaluation quote and original census quote remain separate.
"""
import base64
from decimal import Decimal as D
import hashlib
import io
import json
from pathlib import Path
import zipfile
from research.phase6.dq3_bottleneck_receipts import traffic
from research.phase6.dq3_last_selected_leg import ROOT,previous_evidence
from research.phase6.receipt_audit import corroborate
from research.phase6.route_coverage_audit import routes

QROOT=Path('research/experiments/queue-aware-quote-20261019')


def actual_priced_volume(parts,token,bid):
    numerator,denominator=D(str(bid)).as_integer_ratio()
    return sum(p['sharesRaw'] for p in parts if p['makerToken']==token and p['makerSide']=='BUY'
        and p['collateralRaw']*denominator<=numerator*p['sharesRaw'])


def cached_evidence():
    e=previous_evidence();raw=base64.b64decode((ROOT/'last-leg-result/artifact.zip.b64').read_bytes())
    if hashlib.sha256(raw).hexdigest()!='3da8eced1b9824d1b2e86641fad7754c2a1fad817d6a45a4d4094bd534c9fabd':
        raise ValueError('Changed complete last19 receipt artifact')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        r=json.loads(z.read('report.json'))
        if not r['complete'] or r['errors']:raise ValueError('Incomplete previous receipts')
        for name in z.namelist():
            if name.startswith('raw/'):
                data=json.loads(z.read(name));tx=data['receipt']['transactionHash']
                if tx in e:raise ValueError('Duplicate receipt cache transaction')
                e[tx]=dict(data=data,topics=r['eventTopics'])
    if len(e)!=68:raise ValueError('Wrong complete receipt cache')
    return e


def analyze():
    f=json.loads(Path('research/phase6/queue-aware-cached-traffic-freeze.json').read_text())
    for path,sha in f['filesSha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=sha:raise ValueError('Changed frozen cached gate '+path)
    e=cached_evidence();original=traffic()['states'];out=[]
    for selected in f['selection']:
        state=next(s for s in original if s['selection']['originalSequence']==selected['originalSequence'])
        if selected['activationDueMs']!=state['selection']['activationDueMs'] or selected['terminalMs']!=state['terminalMs']:
            raise ValueError('Changed original source window')
        token=selected['newTargetQuote']['token'];pair={q['token'] for q in state['selection']['quotes']}
        observations=[o for o in state['observations'] if o['targetToken']==token]
        if not observations:raise ValueError('Require complete nonempty target leg')
        volume=0;txs=[]
        for o in observations:
            sample=dict(o['sample'],arrivalMs=o['arrivalMs']);tx=sample['transaction_hash']
            if tx not in e:raise ValueError('Incomplete cached leg; never treat missing receipt as zero')
            data=e[tx]['data'];decoded=corroborate(sample,data['receipt'],data['block'],e[tx]['topics'])
            route=routes(decoded,pair)
            if not route['uniqueConservedGroup']:raise ValueError('Ambiguous actual source settlement route')
            parts=route['matchingGroups'][0]['components']
            volume+=actual_priced_volume(parts,token,selected['newTargetQuote']['price']);txs.append(tx)
        if len(txs)!=len(set(txs)):raise ValueError('Duplicate observation volume requires explicit handling')
        out.append(dict(originalSequence=selected['originalSequence'],originalCensusQuotes=state['selection']['quotes'],
            qw0TargetQuote=selected['newTargetQuote'],completeTargetObservations=len(observations),
            completeActualPriceCompatibleSharesRaw=volume,transactionHashes=txs,
            originalPublicObservationBindingUnmodified=True))
    positive=sum(x['completeActualPriceCompatibleSharesRaw']>0 for x in out)
    return dict(experiment='QW0',scope='COMPLETE_CACHED_ACTUAL_COMPONENTS_AT_NEW_QUOTES_NOT_ACCOUNT_EXECUTION',
        states=out,selectedStarts=len(out),positiveActualPricedTargetLegs=positive,newPublicReads=0,newTapeScans=0,
        overlappingVolumesMustNotBeSummed=True,activationQueueOrRestingCancelProven=False,
        fillsCreated=0,netPnlRecomputed=False,independentPaperQualificationAllowed=False,liveAllowed=False,
        decision='REJECT_THESE_SELECTED_STARTS_NO_ACTUAL_PRICED_TARGET_VOLUME' if positive==0
            else 'ONLY_POSITIVE_SELECTED_STARTS_NEED_FROZEN_CAUSAL_LIFETIME_GATE')


if __name__=='__main__':print(json.dumps(analyze(),indent=2))
