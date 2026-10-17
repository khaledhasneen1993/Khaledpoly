"""Installable, versioned declarative strategy SDK.

An external Python strategy may compute a JSON proposal in its *own*
environment; this process never imports or executes user strategy code,
has no wallet, and cannot submit even PAPER orders. Risk is centralized
in the existing Java/Python PAPER review contract.
"""
import argparse
import hashlib
from pathlib import Path

from research.phase3.polybot_sdk.model import decode, dumps, integer, validate
from research.phase3.polybot_sdk.runtime import private_write
from research.phase6.external_strategy import ExternalStrategyReview, PROPOSAL

CONTRACT_VERSION = "1.0"


def compile_declarative(snapshot, input_spec, *, at_ms=None):
    obs=validate(snapshot,at_ms)
    if (not isinstance(input_spec,dict)
            or set(input_spec)!={'schema','version','strategyId','proposals'}
            or input_spec['schema']!=1 or input_spec['version']!=CONTRACT_VERSION):
        raise ValueError('Unsupported declarative PAPER SDK version/shape')
    items=input_spec['proposals']
    if not isinstance(items,list) or not 1<=len(items)<=32:
        raise ValueError('External strategy hypothesis count out of bounds')
    for candidate in items:
        if not isinstance(candidate,dict) or set(candidate)!=PROPOSAL:
            raise ValueError('No arbitrary external strategy execution commands')
    return {'schema':1,'version':CONTRACT_VERSION,'strategyId':input_spec['strategyId'],
            'sessionId':obs['sessionId'],'accountId':obs['account']['id'],
            'snapshotSequence':integer(obs['sequence']),
            'observedMs':integer(obs['generatedMs']),
            'proposals':decode(dumps(items))}


def preview(snapshot, input_spec, *, at_ms=None, reviewer=None):
    envelope=compile_declarative(snapshot,input_spec,at_ms=at_ms)
    reviewed=(reviewer or ExternalStrategyReview()).review(
        snapshot,envelope,at_ms=at_ms)
    return {'schema':1,'scope':'VERSIONED_EXTERNAL_PAPER_RESEARCH_SDK',
            'contractVersion':CONTRACT_VERSION,'envelope':envelope,
            'review':reviewed,'envelopeSha256':hashlib.sha256(
                dumps(envelope).encode('utf-8')).hexdigest(),
            'callerStrategyExecutedInProcess':False,'venueOrdersSubmitted':0,
            'paperOrdersSubmitted':0,'walletAccess':False,
            'executionEnabled':False,'liveAllowed':False,'decision':'NO_GO'}


def main():
    cli=argparse.ArgumentParser(description='Offline declarative external PAPER-only SDK')
    cli.add_argument('--snapshot',required=True)
    cli.add_argument('--spec',required=True,help='Declarative strategy proposal JSON; no Python imports')
    cli.add_argument('--at-ms',type=int,default=None,
                     help='Explicit replay clock for recorded PAPER snapshots')
    cli.add_argument('--output',required=True)
    options=cli.parse_args()
    obs=decode(Path(options.snapshot).read_text(encoding='utf-8'))
    spec=decode(Path(options.spec).read_text(encoding='utf-8'))
    result=preview(obs,spec,at_ms=options.at_ms)
    private_write(options.output,result)
    print(dumps(result))


if __name__=='__main__':
    main()
