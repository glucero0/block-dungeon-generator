"""Write a generated creature file.

    python -m creature_gen --seed 1 --species skeleton -o out/skeleton.json
    python -m creature_gen --seed 1 --all -o out/creatures
"""

import argparse
import json
from pathlib import Path

from .generate import generate_creature
from .species import SPECIES_IDS


def _write(creature, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(creature, indent=2) + '\n', encoding='utf-8')
    print(f'wrote {path} ({creature["name"]}, seed {creature["seed"]})')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Generate a creature file.')
    parser.add_argument('--seed', type=int, default=1, help='deterministic seed, zero or greater')
    parser.add_argument('--species', choices=SPECIES_IDS, default=None, help='roster id, such as skeleton or wolf')
    parser.add_argument('--all', action='store_true', help='write every species into the output directory')
    parser.add_argument('-o', '--output', required=True, help='JSON file to write, or a directory with --all')
    args = parser.parse_args(argv)
    if args.seed < 0:
        parser.error('seed must be zero or greater')
    if args.all and args.species:
        parser.error('--species and --all cannot be used together')
    if not args.all and args.species is None:
        parser.error('--species is required unless --all is set')
    try:
        if args.all:
            directory = Path(args.output)
            if directory.exists() and not directory.is_dir():
                parser.error('output must be a directory when --all is set')
            directory.mkdir(parents=True, exist_ok=True)
            for species in SPECIES_IDS:
                _write(generate_creature(species, args.seed), directory / f'{species}.json')
        else:
            _write(generate_creature(args.species, args.seed), args.output)
    except (TypeError, ValueError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
