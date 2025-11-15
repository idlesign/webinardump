import argparse
import logging
from pathlib import Path

from .dumpers import Dumper


def get_user_input(param: str, hint: str, *, choices: list[str] | None = None) -> str:

    choices = set(choices or [])

    while True:
        data = input(f'{hint}: ')
        data = data.strip()
        if not data or (choices and data not in choices):
            continue

        return data


def main():
    parser = argparse.ArgumentParser(prog='webinardump')
    parser.add_argument('-t', '--target', type=Path, default=Path(), help='Directory to dump to')
    parser.add_argument('--timeout', type=int, default=3, help='Request timeout')
    parser.add_argument('--rmax', type=int, default=10, help='Max concurrent requests number')
    parser.add_argument('--debug', help='Show debug information', action='store_true')

    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO, format='%(levelname)-8s: %(message)s')

    dumper_choices = []
    print('Available dumpers:')

    for idx, dumper in enumerate(Dumper.registry, 1):
        print(f'{idx} — {dumper.title}')
        dumper_choices.append(f'{idx}')

    chosen = get_user_input('', 'Select dumper number', choices=dumper_choices)

    dumper = Dumper.registry[int(chosen)-1](
        target_dir=args.target,
        timeout=args.timeout,
        concurrent=args.rmax,
    )
    dumper.run(get_user_input)
