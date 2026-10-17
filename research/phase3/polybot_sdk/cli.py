import argparse
import os
from pathlib import Path
from .client import PaperClient
from .model import decode, dumps, validate
from .runtime import shadow_run, replay_shadow


def main():
    parser = argparse.ArgumentParser(description='Read-only PAPER research. No order submission.')
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
        result = shadow_run(PaperClient(args.url, token), args.output, args.seconds, args.interval, groups)
    else:
        result = replay_shadow(args.directory, args.output)
    print(dumps(result))
