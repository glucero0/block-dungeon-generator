"""The one structure at the middle of a hub: a hut, a house, a tent, a campfire, or a castle.

Each entry is data, like `PROPS`. To add a type, add a row to `STRUCTURES`. The viewer reads
`roof` to pick a shape and falls back to a plain box for a roof it does not know.

roof: 'hip' (low pyramid), 'pitched' (gable), 'cone', 'battlements', or 'none'.
material: how the viewer colours the walls ('timber', 'canvas', 'stone', 'logs').
theme: the room theme, so the interior gets the matching props (`PROPS`).
"""

import math
from collections import namedtuple

from .fire import CAMPFIRE_PREFAB, flame

Kind = namedtuple(
    'Kind',
    'type label theme material roof enterable width depth height door_width door_height description',
)

STRUCTURES = {
    'hut': Kind(
        'hut', 'Hut', 'wood', 'timber', 'hip', True, (9.0, 11.0), (8.0, 10.0), 4.2, 3.2, 2.7,
        'A one-room hut of rough timber under a low thatched roof. A lamp burns by the wall.',
    ),
    'house': Kind(
        'house', 'House', 'wood', 'timber', 'pitched', True, (12.0, 15.0), (10.0, 12.0), 5.4, 3.6, 3.0,
        'A timber house with a pitched roof and a stone chimney. The room inside is warm and dry.',
    ),
    'tent': Kind(
        'tent', 'Tent', 'wood', 'canvas', 'cone', True, (8.0, 9.5), (8.0, 9.5), 5.0, 2.8, 2.6,
        'A canvas tent on a ring of stakes. Bedrolls and supply sacks are packed against the cloth.',
    ),
    'campfire': Kind(
        'campfire', 'Campfire', 'wood', 'logs', 'none', False, (7.0, 8.0), (7.0, 8.0), 0.0, 0.0, 0.0,
        'A fire ring with log seats around it. There is no roof, only the sky and the smoke.',
    ),
    'castle': Kind(
        'castle', 'Keep', 'stone', 'stone', 'battlements', True, (22.0, 26.0), (18.0, 22.0), 9.0, 6.0, 6.5,
        'A small castle with a square keep and four corner towers. The hall inside is cold and bare.',
    ),
}

TOWER_RADIUS = 3.4
TOWER_EXTRA = 4.0
FIRE_RADIUS = 1.1
SEAT_RING = 2.7
SEATS = 4

# A cave interior has no cloth or timber shell, so the walls stay stone.
THEME_MATERIALS = {'stone': 'stone', 'wood': 'timber', 'cave': 'stone'}


def names():
    return sorted(STRUCTURES)


def with_theme(kind, theme):
    """Dress `kind` in `theme`. None, or the kind's own theme, leaves its material alone.

    A tent is already wood and stays canvas. A campfire is already wood and stays logs.
    `stone` and `cave` use stone walls. `wood` on a stone structure uses timber.
    """
    if theme is None or theme == kind.theme:
        return kind
    if theme not in THEME_MATERIALS:
        raise ValueError('theme must be one of: ' + ', '.join(THEME_MATERIALS))
    return kind._replace(theme=theme, material=THEME_MATERIALS[theme])


def pick(forced, rng):
    """The forced type, or one chosen from `rng`. Always draws once, so streams stay aligned."""
    chosen = rng.choice(names())
    if forced is None:
        return STRUCTURES[chosen]
    if forced not in STRUCTURES:
        raise ValueError('structure must be one of: ' + ', '.join(names()))
    return STRUCTURES[forced]


def footprint(kind, rng):
    """Seeded width and depth in metres."""
    width = rng.uniform(*kind.width)
    depth = rng.uniform(*kind.depth)
    if kind.roof == 'cone':
        depth = width  # a round structure sits in a square footprint
    return round(width, 2), round(depth, 2)


def margin(kind):
    """How far the structure's parts reach past its footprint."""
    return TOWER_RADIUS if kind.type == 'castle' else 0.0


def _round(value):
    return round(float(value), 4)


def build(kind, cx, cz, width, depth):
    """The `structure` record for a footprint centred on (cx, cz)."""
    x = cx - width / 2
    z = cz - depth / 2
    rect = {'x': _round(x), 'z': _round(z), 'w': _round(width), 'd': _round(depth)}
    reach = margin(kind)
    bounds = {
        'x': _round(x - reach),
        'z': _round(z - reach),
        'w': _round(width + reach * 2),
        'd': _round(depth + reach * 2),
    }
    parts = []
    if kind.type == 'castle':
        for sx in (-1, 1):
            for sz in (-1, 1):
                parts.append({
                    'type': 'tower',
                    'x': _round(cx + sx * width / 2),
                    'z': _round(cz + sz * depth / 2),
                    'radius': TOWER_RADIUS,
                    'height': _round(kind.height + TOWER_EXTRA),
                })
    if kind.type == 'campfire':
        pit = {
            'type': 'fire-pit',
            'x': _round(cx),
            'y': 0.0,
            'z': _round(cz),
            'radius': FIRE_RADIUS,
            'prefab': CAMPFIRE_PREFAB,
        }
        pit.update(flame())
        parts.append(pit)
        for index in range(SEATS):
            angle = math.pi * 2 * index / SEATS + math.pi / 4
            sx = cx + math.cos(angle) * SEAT_RING
            sz = cz + math.sin(angle) * SEAT_RING
            parts.append({
                'type': 'log-seat',
                'x': _round(sx),
                'z': _round(sz),
                'rotationY': _round(math.atan2(cx - sx, cz - sz) + math.pi / 2),
                'length': 2.0,
            })
    door = None
    if kind.enterable:
        door = {
            'x': _round(cx),
            'z': _round(cz + depth / 2),
            'width': kind.door_width,
            'height': kind.door_height,
            'facing': 'S',
        }
    return {
        'type': kind.type,
        'label': kind.label,
        'theme': kind.theme,
        'material': kind.material,
        'roof': kind.roof,
        'enterable': kind.enterable,
        'height': kind.height,
        'rect': rect,
        'polygon': [
            [rect['x'], rect['z']],
            [_round(x + width), rect['z']],
            [_round(x + width), _round(z + depth)],
            [rect['x'], _round(z + depth)],
        ],
        'bounds': bounds,
        'parts': parts,
        'door': door,
        'description': kind.description,
    }
