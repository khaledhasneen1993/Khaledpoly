import argparse
import os
from pathlib import Path
from .client import PaperClient
from .model import decode, dumps, validate
from .runtime import shadow_run, replay_shadow


def main():
    parser = argparse.ArgumentParser(description='PAPER research and opt-in virtual execution. No venue order submission.')
    commands = parser.add_subparsers(dest='command', required=True)
    inspect = commands.add_parser('inspect')
    inspect.add_argument('snapshot')
    inspect.add_argument('--replay-clock', action='store_true', help='Use recorded availability time for offline inspection')
    shadow = commands.add_parser('shadow')
    shadow.add_argument('--url', default='http://127.0.0.1:8080')
    shadow.add_argument('--seconds', type=float, default=60)
    shadow.add_argument('--interval', type=float, default=1)
    shadow.add_argument('--output', required=True)
    shadow.add_argument('--groups', help='JSON condition-to-correlation-group mapping; fixed for this run')
    shadow.add_argument('--strategy', choices=('inventory-mm-shadow', 'event-probability', 'complete-set'), default='inventory-mm-shadow')
    shadow.add_argument('--fill-model', help='Research-only model artifact, embedded in the run manifest')
    shadow.add_argument('--features', help='Append-only feature JSONL with source and availability times')
    execute = commands.add_parser('execute-paper')
    execute.add_argument('--url', default='http://127.0.0.1:8080')
    execute.add_argument('--seconds', type=float, default=60)
    execute.add_argument('--interval', type=float, default=1)
    execute.add_argument('--strategy', choices=('inventory-mm-shadow', 'event-probability', 'complete-set'), default='inventory-mm-shadow')
    execute.add_argument('--features')
    execute.add_argument('--output', required=True)
    reconcile = commands.add_parser('reconcile-paper')
    reconcile.add_argument('directory')
    reconcile.add_argument('--url', default='http://127.0.0.1:8080')
    reconcile.add_argument('--output', required=True)
    settlement = commands.add_parser('settle-paper-group')
    settlement.add_argument('event_id')
    settlement.add_argument('--url', default='http://127.0.0.1:8080')
    labels = commands.add_parser('build-labels')
    labels.add_argument('tape')
    labels.add_argument('--output', required=True)
    discovery = commands.add_parser('discover')
    discovery.add_argument('--category', choices=('politics', 'sports'), required=True)
    discovery.add_argument('--limit', type=int, default=20)
    discovery.add_argument('--output', required=True)
    public = commands.add_parser('collect-signals')
    public.add_argument('--seconds', type=float, default=60)
    public.add_argument('--interval', type=float, default=5)
    public.add_argument('--symbol', default='BTCUSDT')
    public.add_argument('--output', required=True)
    learning = commands.add_parser('train-model')
    learning.add_argument('labels')
    learning.add_argument('--target', choices=('fill', 'second_leg', 'adverse_selection'), default='fill')
    learning.add_argument('--holdout-start', required=True, help='Timezone-aware ISO timestamp, fixed before collecting holdout')
    learning.add_argument('--output', required=True)
    risk = commands.add_parser('portfolio-risk')
    risk.add_argument('snapshot')
    risk.add_argument('panel', help='JSON list of [availability_ms, {token:bid}]')
    risk.add_argument('--output', required=True)
    bench = commands.add_parser('profile')
    bench.add_argument('snapshot')
    bench.add_argument('--iterations', type=int, default=500)
    bench.add_argument('--output', required=True)
    accounts = commands.add_parser('accounts')
    accounts.add_argument('configuration', help='Isolated origins/state paths/roles and tokenEnv references, never raw credentials')
    accounts.add_argument('--output', required=True)
    baskets = commands.add_parser('basket')
    baskets.add_argument('scenario', help='JSON universe, prices, size and costs; hypothetical only')
    baskets.add_argument('--output', required=True)
    predict = commands.add_parser('predict')
    predict.add_argument('model')
    predict.add_argument('features')
    replay = commands.add_parser('replay-shadow')
    replay.add_argument('directory')
    replay.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.command == 'inspect':
        data = decode(Path(args.snapshot).read_text())
        result = validate(data, data['generatedMs'] if args.replay_clock else None)
    elif args.command == 'shadow':
        token = os.environ.get('POLYBOT_EXECUTOR_TOKEN', '')
        groups = decode(Path(args.groups).read_text()) if args.groups else None
        result = shadow_run(PaperClient(args.url, token), args.output, args.seconds, args.interval, groups, args.strategy, args.features, decode(Path(args.fill_model).read_text()) if args.fill_model else None)
    elif args.command == 'execute-paper':
        from .execution import execute_paper, PaperExecutionClient
        result = execute_paper(PaperExecutionClient(args.url, os.environ.get('POLYBOT_EXECUTOR_TOKEN', '')),
                               args.output, args.seconds, args.interval, args.strategy, args.features)
    elif args.command == 'reconcile-paper':
        from .execution import reconcile_paper, PaperExecutionClient
        result = reconcile_paper(PaperExecutionClient(args.url, os.environ.get('POLYBOT_EXECUTOR_TOKEN', '')), args.directory, args.output)
    elif args.command == 'settle-paper-group':
        from .execution import PaperExecutionClient
        result = PaperExecutionClient(args.url, os.environ.get('POLYBOT_EXECUTOR_TOKEN', '')).settle_group(args.event_id)
    elif args.command == 'build-labels':
        from .labels import build_labels
        result = build_labels(args.tape, args.output)
    elif args.command == 'discover':
        from .discovery import UniverseDiscovery
        from .runtime import private_write
        result = UniverseDiscovery().discover(args.category, args.limit)
        private_write(args.output, result)
    elif args.command == 'collect-signals':
        from .collector import collect
        result = collect(args.output, args.seconds, args.interval, args.symbol)
    elif args.command == 'train-model':
        from datetime import datetime
        from .learning import train
        from .runtime import private_write
        cutoff = datetime.fromisoformat(args.holdout_start.replace('Z', '+00:00'))
        if cutoff.tzinfo is None:
            raise ValueError('Holdout boundary requires a timezone')
        with open(args.labels) as stream:
            result = train((decode(row) for row in stream if row.strip()), int(cutoff.timestamp() * 1000), args.target)
        private_write(args.output, result)
    elif args.command == 'portfolio-risk':
        from .portfolio import historical_risk
        from .runtime import private_write
        data = decode(Path(args.snapshot).read_text())
        result = historical_risk(validate(data, data['generatedMs']), decode(Path(args.panel).read_text()))
        private_write(args.output, result)
    elif args.command == 'profile':
        from .profile import benchmark
        from .runtime import private_write
        result = benchmark(decode(Path(args.snapshot).read_text()), args.iterations)
        private_write(args.output, result)
    elif args.command == 'accounts':
        from .accounts import AccountRegistry
        from .runtime import private_write
        config = decode(Path(args.configuration).read_text())
        registry, errors = AccountRegistry(config), {}
        for row in config:
            try:
                registry.accept(row['alias'], PaperClient(row['origin'], os.environ[row['tokenEnv']]).snapshot())
            except (ValueError, KeyError, OSError) as exc:
                errors[row['alias']] = type(exc).__name__
        import time
        result = registry.report()
        result['fundValuation'] = registry.fund_valuation(int(time.time() * 1000))
        result['errors'] = errors
        private_write(args.output, result)
    elif args.command == 'basket':
        from .baskets import analyze_basket
        from .runtime import private_write
        data = decode(Path(args.scenario).read_text())
        result = analyze_basket(data['universe'], data['prices'], data['size'], data.get('costs', 0))
        private_write(args.output, result)
    elif args.command == 'predict':
        from .learning import predict
        result = predict(decode(Path(args.model).read_text()), decode(Path(args.features).read_text()))
    else:
        result = replay_shadow(args.directory, args.output)
    print(dumps(result))
