"""The way out of the ruins: a gate in the exit chamber and an outdoor exit trail.

The exit trail is its own zone, like the entrance trail. It is built by the same code as the
entrance approach (court, bending trail, trees, scenery, mountain vista), so the two look alike.
It sits to the west of the ruins, away from every room and from the entrance trail, so it never
overlaps a floor. A fade transition joins the gate to the trail.
"""

import math

from .approach import DAY, INTERIOR, PATH_WIDTH, _preset, _trigger, build_approach, entrance_door_width
from .blocks import OPPOSITE, Rect

GAP_WEST = 60.0
GATE_HEIGHT = 7.0
GATE_PROBE = 1.5
OUTWARD = {'N': (0, -1), 'S': (0, 1), 'W': (-1, 0), 'E': (1, 0)}

EXIT_TRAIL_DESCRIPTION = (
    'A weathered stone arch opens onto a worn dirt path. Dead trees and scrub follow the path '
    'away from the ruins until a mountain range meets it.'
)

ZONE_LABELS = {
    'exit-trail': 'Exit Trail',
    'exit-pass': 'Open Country',
}


def _round(value):
    return round(float(value), 4)


def _entry_wall(layout, block):
    """The wall of `block` that its entry link lies on."""
    rect = block.rect
    for link in layout.links:
        if link.child is not block:
            continue
        if abs(link.z0 - link.z1) < 1e-6:
            return 'N' if abs(link.z0 - rect.z) < 0.1 else 'S'
        return 'W' if abs(link.x0 - rect.x) < 0.1 else 'E'
    return 'S'


def _wall_point(rect, wall):
    """Midpoint of a wall, as (x, z)."""
    if wall == 'N':
        return rect.x + rect.w / 2, rect.z
    if wall == 'S':
        return rect.x + rect.w / 2, rect.z + rect.d
    if wall == 'W':
        return rect.x, rect.z + rect.d / 2
    return rect.x + rect.w, rect.z + rect.d / 2


def _probe(rect, wall, width):
    """A slab just outside a wall, used to check that no other room is flush against it."""
    mx, mz = _wall_point(rect, wall)
    if wall in ('N', 'S'):
        x = mx - width / 2
        z = rect.z - GATE_PROBE if wall == 'N' else rect.z + rect.d
        return Rect(x, z, width, GATE_PROBE)
    x = rect.x - GATE_PROBE if wall == 'W' else rect.x + rect.w
    return Rect(x, mz - width / 2, GATE_PROBE, width)


def pick_gate(layout, block):
    """Choose the exit chamber's gate wall: opposite the entry door when nothing is against it."""
    rect = block.rect
    width = entrance_door_width(rect)
    entry = _entry_wall(layout, block)
    order = [OPPOSITE[entry]] + [wall for wall in 'NSEW' if wall not in (entry, OPPOSITE[entry])]
    wall = order[0]
    for candidate in order:
        if not layout.hits(_probe(rect, candidate, width), [block.floor]):
            wall = candidate
            break
    mx, mz = _wall_point(rect, wall)
    if wall in ('N', 'S'):
        a = [mx - width / 2, mz]
        b = [mx + width / 2, mz]
    else:
        a = [mx, mz - width / 2]
        b = [mx, mz + width / 2]
    return {
        'a': [_round(a[0]), _round(a[1])],
        'b': [_round(b[0]), _round(b[1])],
        'width': _round(width),
        'height': GATE_HEIGHT,
        'openingWidth': _round(width),
        'mouthA': [_round(a[0]), _round(a[1])],
        'mouthB': [_round(b[0]), _round(b[1])],
        'name': 'Exit Gate',
        'type': 'stone_portal',
        'from': block.id,
        'y': _round(block.floor * 10.0),
        'wall': wall,
        'facing': list(OUTWARD[wall]),
    }


def _gate_volume(rect, wall, width):
    """Trigger volume just inside the gate."""
    mx, mz = _wall_point(rect, wall)
    ox, oz = OUTWARD[wall]
    cx = mx - ox * 0.65
    cz = mz - oz * 0.65
    span = width - 0.6
    if wall in ('N', 'S'):
        return _trigger(cx, cz, span, 1.0)
    return _trigger(cx, cz, 1.0, span)


def _rounded(volume):
    return {key: _round(value) for key, value in volume.items()}


def _origin(layout, gate_z):
    """The rectangle that stands in for the exit arch's building, west of every room.

    It is level with the gate, so the exit trail lies roughly beside the exit chamber.
    """
    west = min(block.rect.x for block in layout.blocks)
    return Rect(west - GAP_WEST - 8.0, gate_z - 30.0, 16.0, 12.5)


def build_exit(layout, block, rng, clutter, entrance_transitions):
    """Return the gate, the exit trail area, the new zone labels, and the new transitions."""
    gate = pick_gate(layout, block)
    rect = block.rect
    origin = _origin(layout, (gate['a'][1] + gate['b'][1]) / 2)
    area = build_approach(origin, rng, clutter)
    approach = area['approach']
    approach['description'] = EXIT_TRAIL_DESCRIPTION
    arch = dict(area['entrance'])
    arch.update({'name': 'Exit Arch', 'type': 'stone_portal'})
    mid_x = approach['midX']
    south_z = approach['southZ']
    door_width = arch['width']
    ox, oz = OUTWARD[gate['wall']]
    inside_x = _wall_point(rect, gate['wall'])[0] - ox * 3.0
    inside_z = _wall_point(rect, gate['wall'])[1] - oz * 3.0
    pass_spawn = next(item['targetSpawnPoint'] for item in entrance_transitions if item['id'] == 'mountain-pass')
    end = approach['samples'][-1]

    transitions = [
        {
            'id': 'ruin-leave',
            'sourceZoneId': 'ancient-ruins',
            'targetZoneId': 'exit-trail',
            'targetSpawnPoint': {'x': _round(mid_x), 'y': 0, 'z': _round(south_z + 4.2), 'rotationY': _round(math.pi)},
            'transitionType': 'fade',
            'fadeDurationMs': 600,
            'environmentalPreset': _preset(DAY),
            'volume': _rounded(_gate_volume(rect, gate['wall'], gate['width'])),
            'y': gate['y'],
            'floor': block.floor,
        },
        {
            'id': 'ruin-return',
            'sourceZoneId': 'exit-trail',
            'targetZoneId': 'ancient-ruins',
            'targetSpawnPoint': {
                'x': _round(inside_x),
                'y': gate['y'],
                'z': _round(inside_z),
                'rotationY': _round(math.atan2(ox, oz)),
            },
            'transitionType': 'fade',
            'fadeDurationMs': 600,
            'environmentalPreset': _preset(INTERIOR),
            'volume': _rounded(_trigger(mid_x, south_z - 0.65, door_width - 0.6, 1.0)),
        },
        {
            'id': 'exit-pass',
            'sourceZoneId': 'exit-trail',
            'targetZoneId': 'world-hub',
            'targetSpawnPoint': dict(pass_spawn),
            'transitionType': 'fade',
            'fadeDurationMs': 300,
            'environmentalPreset': _preset(DAY),
            'volume': _rounded(_trigger(end['x'], end['z'] - 0.2, PATH_WIDTH, 1.8)),
        },
    ]
    exit_area = {
        'name': ZONE_LABELS['exit-trail'],
        'origin': {'x': _round(origin.x), 'z': _round(origin.z), 'w': origin.w, 'd': origin.d},
        'arch': arch,
        'vestibule': area['vestibule'],
        'exterior': area['exterior'],
        'hub': area['hub'],
        'trees': area['trees'],
        'scenery': area['scenery'],
        'approach': approach,
    }
    return gate, exit_area, dict(ZONE_LABELS), transitions
