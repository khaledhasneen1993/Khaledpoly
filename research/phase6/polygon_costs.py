"""Read-only Polygon batched-settlement cost/latency tradeoff hypotheses.

Does not discover RPC/gas prices, broadcast transactions or execute redemptions.
All inputs are explicit unverified operator or dataset cost assumptions.
"""
from decimal import Decimal, ROUND_CEILING

from research.phase3.polybot_sdk.model import number, integer

ETHER=Decimal(10)**18


def compare_batching(operations, base_gas_units, per_item_gas_units,
                     gas_price_wei, native_usd, wait_ms_by_batch,
                     delay_cost_per_ms_usd):
    n=integer(operations)
    base=integer(base_gas_units)
    item=integer(per_item_gas_units)
    gas=integer(gas_price_wei)
    price=number(native_usd)
    delay_fee=number(delay_cost_per_ms_usd)
    if not 1<=n<=1024 or min(base,item,gas)<0 or price<=0 or delay_fee<0:
        raise ValueError('Invalid gas batch cost scenario')
    if not isinstance(wait_ms_by_batch,dict) or not wait_ms_by_batch:
        raise ValueError('Explicit batch latency scenarios required')
    costs=[]
    individual=n*(base+item)*gas*price/ETHER
    for raw_size,raw_wait in wait_ms_by_batch.items():
        size=integer(raw_size)
        wait=integer(raw_wait)
        if not 1<=size<=min(n,64) or not 0<=wait<=86400000:
            raise ValueError('Invalid bounded batch and waiting time')
        batches=(n+size-1)//size
        gas_used=batches*base+n*item
        gas_usd=Decimal(gas_used)*gas*price/ETHER
        # Delay cost is explicitly an assumption, not an observed swap/MEV price.
        waiting_cost=delay_fee*wait*n
        estimate=gas_usd+waiting_cost
        costs.append({'maxBatchSize':size,'expectedBatches':batches,
                      'estimatedGasUsd':str(gas_usd),
                      'assumedWaitingCostUsd':str(waiting_cost),
                      'scenarioTotalUsd':str(estimate),
                      'grossGasSavingsVersusSinglesUsd':str(individual-gas_usd)})
    ordered=sorted(costs,key=lambda x:(number(x['scenarioTotalUsd']),x['maxBatchSize']))
    return {'schema':1,'scope':'POLYGON_BATCH_GAS_SETTLEMENT_SCENARIO',
            'operations':n,'individualGasScenarioUsd':str(individual),
            'scenarios':costs,'lowestAssumedCostBatchSize':ordered[0]['maxBatchSize'],
            'allCostsExternallyUnverified':True,
            'actualSettlementFinalityMeasured':False,
            'chainConnected':False,'broadcast':False,
            'executionEnabled':False,'liveAllowed':False,'decision':'NO_GO'}
