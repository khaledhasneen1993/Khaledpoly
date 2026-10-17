"""Per-executor observation isolation and proposal permissions. No fund transfer or execution."""
from pathlib import Path
import re
from .client import PaperClient
from .model import number, validate


class AccountRegistry:
    def __init__(self, configuration):
        self._accounts, self._bindings, self._latest = {}, {}, {}
        origins, paths = set(), set()
        if not 1 <= len(configuration) <= 32:
            raise ValueError('Account registry must contain 1..32 isolated executors')
        for row in configuration:
            alias, origin = row['alias'], row['origin'].rstrip('/')
            path = str(Path(row['stateDirectory']).resolve())
            if (not re.fullmatch('[A-Za-z0-9_-]{1,64}', alias) or alias in self._accounts
                    or origin in origins or path in paths or set(row['roles']) - {'read', 'research'}
                    or not row['roles']):
                raise ValueError('Duplicate account, shared endpoint/state or invalid permissions')
            # Validate the same origin restrictions as the authenticated client without retaining a token.
            PaperClient(origin, 'configuration-validation-token-32')
            for other in paths:
                if Path(other) in Path(path).parents or Path(path) in Path(other).parents:
                    raise ValueError('Account state directories cannot overlap')
            self._accounts[alias] = {'origin': origin, 'stateDirectory': path, 'roles': tuple(row['roles'])}
            origins.add(origin)
            paths.add(path)

    def accept(self, alias, snapshot, now_ms=None):
        if alias not in self._accounts or 'read' not in self._accounts[alias]['roles']:
            raise PermissionError('Unknown account or missing read permission')
        observation = validate(snapshot, now_ms)
        binding = observation['sessionId'], observation['account']['id']
        if binding in (v for k, v in self._bindings.items() if k != alias):
            raise ValueError('Same executor observation routed to multiple accounts')
        if alias in self._bindings and self._bindings[alias] != binding:
            raise ValueError('Account session changed; reconcile with a new registry')
        previous = self._latest.get(alias)
        if previous and (int(observation['sequence']) < int(previous['sequence'])
                         or int(observation['inputMs']) < int(previous['inputMs'])):
            raise ValueError('Account observation regressed')
        self._bindings[alias], self._latest[alias] = binding, observation
        return observation

    def research_allowed(self, alias):
        return alias in self._accounts and 'research' in self._accounts[alias]['roles'] and alias in self._latest

    def fund_valuation(self, now_ms):
        valuations = {}
        for alias, obs in sorted(self._latest.items()):
            cash, inventory, known = number(obs['account']['cash']), number(0), True
            if not 0 <= int(now_ms) - int(obs['generatedMs']) <= int(obs['maxBookAgeMs']):
                known = False
            for token, holding in obs['account']['holdings'].items():
                if number(holding['shares']) == 0:
                    continue
                book = obs['books'].get(token)
                if (not book or not book['bids'] or book['depthTruncated']
                        or not 0 <= int(now_ms) - int(book['sourceMs']) <= int(obs['maxBookAgeMs'])):
                    known = False
                    continue
                # Top-bid mark is indicative, never a depth-adjusted executable liquidation price.
                inventory += number(holding['shares']) * number(book['bids'][0]['price'])
            valuations[alias] = {'cash': cash, 'indicativeNav': cash + inventory if known else None,
                                 'realizedPnl': obs['account'].get('realizedPnl'), 'fees': obs['account'].get('fees'),
                                 'liquidationValueVerified': False}
        complete = len(valuations) == len(self._accounts) and all(x['indicativeNav'] is not None for x in valuations.values())
        return {'accounts': valuations, 'aggregateIndicativeNav': sum((x['indicativeNav'] for x in valuations.values()), number(0)) if complete else None,
                'complete': complete, 'capitalTransfersEnabled': False, 'executionEnabled': False}

    def report(self):
        return {'accounts': {alias: {'sessionId': obs['sessionId'], 'sequence': obs['sequence'],
                                      'account': obs['account'], 'researchAllowed': self.research_allowed(alias)}
                             for alias, obs in sorted(self._latest.items())},
                'missingAccounts': sorted(set(self._accounts) - set(self._latest)),
                'aggregateCash': sum((number(obs['account']['cash']) for obs in self._latest.values()), number(0)),
                'capitalTransfersEnabled': False, 'executionEnabled': False, 'liveAllowed': False}
