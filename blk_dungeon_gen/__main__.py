"""Write a generated Ancient Ruins JSON file.

    python -m blk_dungeon_gen --seed 1 --floors 2 --chambers 8 -o out/ruins.json
"""

import argparse
import json
from pathlib import Path

from .emit import generate_layout


def main(argv=None):
    parser = argparse.ArgumentParser(description='Generate an Ancient Ruins layout from snap-together blocks.')
    parser.add_argument('--seed', type=int, default=1, help='deterministic layout seed')
    parser.add_argument('--floors', type=int, default=2, help='stories linked by stairwells (1-8)')
    parser.add_argument('--chambers', type=int, default=8, help='entrance, exit, rooms, and hubs (2-30)')
    parser.add_argument('-o', '--output', required=True, help='JSON file to write')
    args = parser.parse_args(argv)
    if args.seed < 0:
        parser.error('seed must be zero or greater')
    layout = generate_layout(args.seed, floors=args.floors, chambers=args.chambers)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(layout, indent=2) + '\n', encoding='utf-8')
    print(f'wrote {path} ({len(layout["rooms"])} rooms, {layout["floors"]} floors, seed {layout["seed"]})')


if __name__ == '__main__':
    main()
