"""Write a generated Ancient Ruins or hub JSON file.

    python -m blk_dungeon_gen --seed 1 --floors 2 --chambers 8 --density normal --clutter 0.5 -o out/ruins.json
    python -m blk_dungeon_gen --hub --seed 1 --structure house --spoke ruins --spoke forest -o out/hub.json
"""

import argparse
import json
from pathlib import Path

from .density import DENSITY
from .emit import generate_layout
from .hub import generate_hub
from .structures import names as structure_names


def main(argv=None):
    parser = argparse.ArgumentParser(description='Generate an Ancient Ruins layout from snap-together blocks, '
                                                 'or a small starting hub with --hub.')
    parser.add_argument('--seed', type=int, default=1, help='deterministic layout seed')
    parser.add_argument('--floors', type=int, default=2, help='stories linked by stairwells (1-8)')
    parser.add_argument('--chambers', type=int, default=8, help='entrance, exit, rooms, and hubs (2-30)')
    parser.add_argument('--density', choices=sorted(DENSITY, key=DENSITY.get), default='normal',
                        help='enemy spawn density (default: normal)')
    parser.add_argument('--clutter', type=float, default=0.5,
                        help='room props and outdoor scenery, 0 to 1 (default: 0.5)')
    parser.add_argument('--hub', action='store_true',
                        help='write a starting hub instead of ruins (ignores --floors, --chambers, --density)')
    parser.add_argument('--structure', choices=structure_names(), default=None,
                        help='hub structure (default: chosen from the seed)')
    parser.add_argument('--spokes', type=int, default=None,
                        help='number of hub paths, 1 to 8 (default: 3, or the number of --spoke names)')
    parser.add_argument('--spoke', action='append', default=None, metavar='NAME',
                        help='name a hub path, for example --spoke ruins; repeat for more')
    parser.add_argument('-o', '--output', required=True, help='JSON file to write')
    args = parser.parse_args(argv)
    if args.seed < 0:
        parser.error('seed must be zero or greater')
    if not 0 <= args.clutter <= 1:
        parser.error('clutter must be from 0 to 1')
    if not args.hub and (args.structure is not None or args.spokes is not None or args.spoke):
        parser.error('--structure, --spokes, and --spoke need --hub')
    if args.hub:
        try:
            layout = generate_hub(args.seed, spokes=args.spokes, names=args.spoke,
                                  structure=args.structure, clutter=args.clutter)
        except (TypeError, ValueError) as error:
            parser.error(str(error))
        summary = (f'hub: {layout["structure"]["type"]}, {len(layout["hubArea"]["spokes"])} spokes, '
                   f'seed {layout["seed"]}')
    else:
        layout = generate_layout(args.seed, floors=args.floors, chambers=args.chambers,
                                 density=args.density, clutter=args.clutter)
        summary = f'{len(layout["rooms"])} rooms, {layout["floors"]} floors, seed {layout["seed"]}'
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(layout, indent=2) + '\n', encoding='utf-8')
    print(f'wrote {path} ({summary})')


if __name__ == '__main__':
    main()
