"""Candidate risk primitive only. No strategy wiring, fills, account or future labels."""
from decimal import Decimal


def assess(quantity, first_price, second_price, exit_budget_available, redemption_cost, *, enabled=False):
    values=[Decimal(str(x)) for x in (quantity,first_price,second_price,exit_budget_available,redemption_cost)]
    if any(not x.is_finite() for x in values):raise ValueError('Finite risk inputs required')
    q,a,b,budget,cost=values
    if q<=0 or not 0<a<1 or not 0<b<1 or budget<0 or cost<0:
        raise ValueError('Invalid residual-risk inputs')
    # One leg could fill fully while its peer never fills and no lawful exit is available.
    worst=q*max(a,b)+cost
    return dict(enabled=enabled,allow=not enabled or worst<=budget,
                worstCaseUnpairedLoss=str(worst),availableExitBudget=str(budget),
                decision='RESEARCH_ONLY_NOT_CONNECTED',independentPaperQualificationAllowed=False)
