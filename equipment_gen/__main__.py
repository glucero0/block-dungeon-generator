"""Write a generated equipment recipe.

    python -m equipment_gen --seed 1 --kind sword --tier 2 -o out/sword.json
    python -m equipment_gen --seed 1 --tier 1 --all -o out/equipment
"""

import argparse
import json
from pathlib import Path

from .generate import generate_item
from .schema import KINDS


def _write(item, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(item, indent=2) + '\n', encoding='utf-8')
    print(f'wrote {path} ({item["name"]}, seed {item["seed"]})')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Generate a held equipment recipe.')
    parser.add_argument('--seed', type=int, default=1, help='deterministic seed, zero or greater')
    parser.add_argument('--kind', choices=KINDS, default=None, help='sword, shield, torch, mace, axe, hammer, spear, dagger, or bow')
    parser.add_argument('--tier', type=int, default=1, help='ornament and a small stat bump, 1 to 5 (default: 1)')
    parser.add_argument('--all', action='store_true', help='write every kind into the output directory')
    parser.add_argument('-o', '--output', required=True, help='JSON file to write, or a directory with --all')
    args = parser.parse_args(argv)
    if args.seed < 0:
        parser.error('seed must be zero or greater')
    if not 1 <= args.tier <= 5:
        parser.error('tier must be from 1 to 5')
    if args.all and args.kind:
        parser.error('--kind and --all cannot be used together')
    if not args.all and args.kind is None:
        parser.error('--kind is required unless --all is set')
    try:
        if args.all:
            directory = Path(args.output)
            if directory.exists() and not directory.is_dir():
                parser.error('output must be a directory when --all is set')
            directory.mkdir(parents=True, exist_ok=True)
            for kind in KINDS:
                _write(generate_item(kind, args.seed, args.tier), directory / f'{kind}.json')
        else:
            _write(generate_item(args.kind, args.seed, args.tier), args.output)
    except (TypeError, ValueError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
