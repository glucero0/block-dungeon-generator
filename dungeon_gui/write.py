"""Validate studio fields and write JSON into one of the four output folders.

The output root is an argument so tests can use a temporary directory. The
desktop window passes ``out``. A filename cannot leave its folder.
"""

import hashlib
import json
import math
import re
from pathlib import Path

from blk_dungeon_gen.density import DENSITY
from blk_dungeon_gen.emit import creature_value, generate_layout, theme_value
from blk_dungeon_gen.hub import clean_names, generate_hub
from blk_dungeon_gen.structures import STRUCTURES, names as structure_names
from creature_gen.generate import generate_creature
from creature_gen.species import SPECIES_IDS
from equipment_gen.generate import generate_item
from equipment_gen.schema import KINDS

DUNGEONS = 'dungeons'
HUBS = 'hubs'
GEAR = 'gear'
CREATURES = 'creatures'

_FILE = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,178}\.json')
_WHOLE = re.compile(r'0|[1-9][0-9]*')
_DECIMAL = re.compile(r'(?:0|[1-9][0-9]*)(?:\.[0-9]+)?|\.[0-9]+')
_DEVICES = frozenset(
    {'con', 'prn', 'aux', 'nul'}
    | {f'com{n}' for n in range(1, 10)}
    | {f'lpt{n}' for n in range(1, 10)}
)


def studio_root():
    """The folder the window writes into, relative to the current directory."""
    return Path('out')


def dungeon_name(seed, floors, chambers, density, clutter, theme, creature):
    """Default dungeon filename. The same options always produce the same name."""
    theme_token = _theme(theme) or 'mixed'
    creature_token = _creature(creature) or 'unset'
    return _join([
        f's{_seed(seed)}',
        f'f{_bounded(floors, "floors", 1, 8)}',
        f'c{_bounded(chambers, "chambers", 2, 30)}',
        _density(density),
        f'k{_clutter_token(clutter)}',
        theme_token,
        creature_token,
    ])


def hub_name(seed, structure, spokes, names, clutter, theme, creature):
    """Default hub filename. Supplied spoke names are part of the name."""
    count = _bounded(spokes, 'spokes', 1, 8)
    supplied = _spoke_names(names)
    parts = [
        f's{_seed(seed)}',
        _structure(structure) or 'auto',
        f'p{count}',
    ]
    parts.extend(supplied)
    parts.extend([
        f'k{_clutter_token(clutter)}',
        _theme(theme) or 'mixed',
        _creature(creature) or 'unset',
    ])
    return _join(parts)


def gear_name(kind, seed, tier):
    """One gear file. ``--all`` uses this name for every kind."""
    return f'{_kind(kind)}-s{_seed(seed)}-t{_bounded(tier, "tier", 1, 5)}.json'


def creature_name(species, seed):
    """One creature file. ``--all`` uses this name for every species."""
    return f'{_species(species)}-s{_seed(seed)}.json'


def write_dungeon(root, seed, floors, chambers, density, clutter, theme, creature, filename):
    """Write one ruin layout and return the path."""
    seed = _seed(seed)
    floors = _bounded(floors, 'floors', 1, 8)
    chambers = _bounded(chambers, 'chambers', 2, 30)
    density = _density(density)
    clutter = _clutter(clutter)
    theme = _theme(theme)
    creature = _creature(creature)
    path = _destination(root, DUNGEONS, filename)
    document = generate_layout(
        seed, floors=floors, chambers=chambers, density=density,
        clutter=clutter, theme=theme, creature=creature,
    )
    return [_dump(path, document)]


def write_hub(root, seed, structure, spokes, names, clutter, theme, creature, filename):
    """Write one hub and return the path."""
    seed = _seed(seed)
    structure = _structure(structure)
    spokes = _bounded(spokes, 'spokes', 1, 8)
    names = clean_names(_spoke_names(names), spokes)
    clutter = _clutter(clutter)
    theme = _theme(theme)
    creature = _creature(creature)
    path = _destination(root, HUBS, filename)
    document = generate_hub(
        seed, spokes=spokes, names=names, structure=structure,
        clutter=clutter, theme=theme, creature=creature,
    )
    return [_dump(path, document)]


def write_gear(root, seed, kind, tier, all_kinds, filename):
    """Write one item, or every kind. Return the paths."""
    seed = _seed(seed)
    tier = _bounded(tier, 'tier', 1, 5)
    if _flag(all_kinds):
        paths = []
        for item_kind in KINDS:
            path = _destination(root, GEAR, gear_name(item_kind, seed, tier))
            paths.append(_dump(path, generate_item(item_kind, seed, tier)))
        return paths
    path = _destination(root, GEAR, filename)
    return [_dump(path, generate_item(_kind(kind), seed, tier))]


def write_creature(root, seed, species, all_species, filename):
    """Write one creature, or every species. Return the paths."""
    seed = _seed(seed)
    if _flag(all_species):
        paths = []
        for roster_id in SPECIES_IDS:
            path = _destination(root, CREATURES, creature_name(roster_id, seed))
            paths.append(_dump(path, generate_creature(roster_id, seed)))
        return paths
    path = _destination(root, CREATURES, filename)
    return [_dump(path, generate_creature(_species(species), seed))]


def _dump(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + '\n', encoding='utf-8')
    return path


def _destination(root, folder, filename):
    cleaned = _filename(filename)
    if folder not in (DUNGEONS, HUBS, GEAR, CREATURES):
        raise ValueError('unknown output folder')
    base = (Path(root) / folder).resolve()
    path = (base / cleaned).resolve()
    if path.parent != base:
        raise ValueError('filename must stay inside the output folder')
    return path


def _filename(name):
    if not isinstance(name, str):
        raise ValueError('filename must be a .json name')
    cleaned = name.strip()
    if any(mark in cleaned for mark in ('/', '\\', ':')) or '..' in cleaned:
        raise ValueError('filename must stay inside the output folder')
    if not _FILE.fullmatch(cleaned):
        raise ValueError(
            'filename must end in .json and use letters, digits, dots, underscores, and hyphens'
        )
    if cleaned[:-5].split('.', 1)[0].lower() in _DEVICES:
        raise ValueError('filename is reserved')
    return cleaned


def _join(parts):
    name = '-'.join(str(part) for part in parts) + '.json'
    if len(name) <= 120 and _FILE.fullmatch(name):
        return name
    digest = hashlib.sha256(name.encode('utf-8')).hexdigest()[:10]
    short = re.sub(r'[^A-Za-z0-9._-]', '', name[:48]).strip('.-') or 'layout'
    return f'{short}-{digest}.json'


def _seed(value):
    return _bounded(value, 'seed', 0, None)


def _bounded(value, name, low, high):
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError(f'{name} must be a whole number')
    if isinstance(value, str):
        text = value.strip()
        if not _WHOLE.fullmatch(text):
            raise ValueError(f'{name} must be a whole number')
        number = int(text)
    elif isinstance(value, int):
        number = value
    else:
        raise ValueError(f'{name} must be a whole number')
    if number < low or (high is not None and number > high):
        limit = f'{low} or greater' if high is None else f'from {low} to {high}'
        raise ValueError(f'{name} must be {limit}')
    return number


def _clutter(value):
    if isinstance(value, bool):
        raise ValueError('clutter must be from 0 to 1')
    if isinstance(value, str):
        text = value.strip()
        if not _DECIMAL.fullmatch(text):
            raise ValueError('clutter must be from 0 to 1')
        value = float(text)
    elif not isinstance(value, (int, float)):
        raise ValueError('clutter must be from 0 to 1')
    if not math.isfinite(value) or value < 0 or value > 1:
        raise ValueError('clutter must be from 0 to 1')
    return round(float(value), 3)


def _clutter_token(value):
    number = _clutter(value)
    text = f'{number:.3f}'.rstrip('0').rstrip('.')
    return text.replace('.', 'p')


def _density(value):
    if value not in DENSITY:
        order = sorted(DENSITY, key=DENSITY.get)
        raise ValueError('density must be one of: ' + ', '.join(order))
    return value


def _theme(value):
    if value is None or value == '' or value == 'mixed':
        return None
    return theme_value(value)


def _creature(value):
    if value is None or value == '' or value == 'unset':
        return None
    return creature_value(value)


def _structure(value):
    if value is None or value == '' or value == 'from seed':
        return None
    if value not in STRUCTURES:
        raise ValueError('structure must be one of: ' + ', '.join(structure_names()))
    return value


def _kind(value):
    if value not in KINDS:
        raise ValueError('kind must be one of: ' + ', '.join(KINDS))
    return value


def _species(value):
    if value not in SPECIES_IDS:
        raise ValueError('species must be one of: ' + ', '.join(SPECIES_IDS))
    return value


def _spoke_names(value):
    if value is None or value == '':
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(',') if part.strip()]
    if isinstance(value, (list, tuple)) and not isinstance(value, (str, bytes)):
        return list(value)
    raise ValueError('spoke names must be text')


def _flag(value):
    if isinstance(value, bool):
        return value
    raise ValueError('the all switch must be on or off')
