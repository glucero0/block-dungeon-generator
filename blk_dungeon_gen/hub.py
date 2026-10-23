"""A small starting hub: one structure on a plaza, with named spokes (paths) leaving it.

The player spawns at `hubArea.respawn` when a game starts and again after a death. Each spoke
ends in a transition trigger (`to-<name>`) that the game points at another location, and has an
arrival spawn (`from-<name>`) for coming back. The output uses the same document shape as the
ruins, so the same viewer and loader code can read it.
"""

import math
import re

from . import structures
from .approach import (
    DAY,
    DEAD_TREE_VARIANTS,
    SCENERY_TYPES,
    _closest,
    _preset,
    _stamp_frame,
    _trigger,
    _vista_tree,
)
from .blocks import Block, Rect
from .emit import _round, _sconce
from .props import place_props
from .seeding import sub_rng

MAX_SPOKES = 8
DEFAULT_SPOKES = 3
MAX_NAME = 32
NAME_PATTERN = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
RESERVED_NAMES = ('hub', 'hub-interior')

SPOKE_WIDTH = 8.0
SPOKE_SAMPLES = 12
MOUTH_INSET = 1.0
MIN_RADIUS = 20.0
MAX_RADIUS = 90.0
MIN_CHORD = 13.0
STRUCTURE_CLEAR = 7.5
RESPAWN_BELOW_DOOR = 6.0
RESPAWN_BESIDE_FIRE = 3.0
PLAZA_SIDES = 40
VISTA_STEPS = 14
VISTA_END_HALF = 2.4
MOUNTAIN_COUNT = 16

HUB_MIX = {'boulder': 3, 'scrub': 5, 'standing-stone': 1, 'supply-crate': 1, 'cart-wreck': 1}
SCENERY_SPACING = 2.4
SCENERY_TREE_GAP = 2.0
TREE_SPACING = 3.35

HUT_INTERIOR = {
    'clearColor': '#1a1410',
    'ambientLightIntensity': 0.32,
    'fog': {'color': '#1a1410', 'near': 10, 'far': 40},
    'skyboxVisible': False,
}

ZONE_HUB = 'hub'
ZONE_INTERIOR = 'hub-interior'


def clean_names(names, spokes):
    """Validate spoke names and return one name per spoke. Missing names become spoke-N."""
    if names is None:
        names = []
    if isinstance(names, (str, bytes)) or not isinstance(names, (list, tuple)):
        raise TypeError('names must be a list of strings')
    if spokes is None:
        spokes = len(names) if names else DEFAULT_SPOKES
    if isinstance(spokes, bool) or not isinstance(spokes, int):
        raise TypeError('spokes must be an int')
    if spokes < 1 or spokes > MAX_SPOKES:
        raise ValueError(f'spokes must be from 1 to {MAX_SPOKES}')
    if len(names) > spokes:
        raise ValueError('more spoke names than spokes')
    result = []
    for name in names:
        if not isinstance(name, str):
            raise TypeError('names must be a list of strings')
        if len(name) > MAX_NAME or not NAME_PATTERN.match(name):
            raise ValueError(
                f'bad spoke name {name!r}: use lowercase letters, digits and single hyphens, '
                f'1 to {MAX_NAME} characters'
            )
        if name in RESERVED_NAMES:
            raise ValueError(f'spoke name {name!r} is reserved')
        if name in result:
            raise ValueError(f'duplicate spoke name {name!r}')
        result.append(name)
    number = 1
    while len(result) < spokes:
        candidate = f'spoke-{number}'
        number += 1
        if candidate not in result:
            result.append(candidate)
    return result


def _facing(dx, dz):
    """Yaw that faces the direction (dx, dz). 0 faces -Z, the same as `start` and transitions."""
    return math.atan2(-dx, -dz)


def _rect_distance(x, z, rect):
    dx = max(rect['x'] - x, 0.0, x - (rect['x'] + rect['w']))
    dz = max(rect['z'] - z, 0.0, z - (rect['z'] + rect['d']))
    return math.hypot(dx, dz)


def _corners_fit(cx, cz, half_w, half_d, radius):
    return all(
        math.hypot(cx + sx * half_w, cz + sz * half_d) <= radius - 1.5
        for sx in (-1, 1) for sz in (-1, 1)
    )


def _plan(kind, width, depth, cx, count):
    """Pick the plaza radius and put the structure on its north side.

    Returns the radius, structure centre, outer bounds, respawn point, and the arc (start
    angle and slot width) the spokes are spread over. The radius grows until the structure,
    the respawn point, and every spoke mouth fit with room between them.
    """
    reach = structures.margin(kind)
    half_w = width / 2 + reach
    half_d = depth / 2 + reach
    radius = max(MIN_RADIUS + max(0, count - 3) * 1.5, math.hypot(half_w, half_d) + 12)
    while radius <= MAX_RADIUS:
        cz = -radius
        while cz < 0 and not _corners_fit(cx, cz, half_w, half_d, radius):
            cz += 0.25
        if not _corners_fit(cx, cz, half_w, half_d, radius):
            radius += 2
            continue
        south = cz + depth / 2
        respawn_z = south + (RESPAWN_BELOW_DOOR if kind.enterable else RESPAWN_BESIDE_FIRE)
        if math.hypot(cx, respawn_z) > radius - 6:
            radius += 2
            continue
        bounds = {'x': cx - half_w, 'z': cz - half_d, 'w': half_w * 2, 'd': half_d * 2}
        theta = math.atan2(cz, cx)

        def allowed(angle):
            mx = (radius - MOUTH_INSET) * math.cos(angle)
            mz = (radius - MOUTH_INSET) * math.sin(angle)
            return _rect_distance(mx, mz, bounds) >= STRUCTURE_CLEAR

        def gap(sign):
            delta = 0.0
            while delta < math.pi:
                if allowed(theta + sign * delta):
                    return delta
                delta += 0.01
            return math.pi

        before = gap(-1)
        after = gap(1)
        arc = math.pi * 2 - before - after
        if arc <= 0:
            radius += 2
            continue
        slot = arc / count
        if count > 1 and (radius - MOUTH_INSET) * 2 * math.sin(slot * 0.35) < MIN_CHORD:
            radius += 2
            continue
        return {
            'radius': radius,
            'cz': cz,
            'bounds': bounds,
            'respawn': (cx, respawn_z),
            'start': theta + after,
            'slot': slot,
        }
    raise RuntimeError('could not fit the hub')


def _plaza_polygon(radius):
    return [
        [_round(math.cos(math.pi * 2 * i / PLAZA_SIDES) * radius),
         _round(math.sin(math.pi * 2 * i / PLAZA_SIDES) * radius)]
        for i in range(PLAZA_SIDES)
    ]


def _build_spoke(index, name, angle, radius, rng):
    length = rng.uniform(16.0, 24.0)
    bend = rng.choice((-1, 1)) * rng.uniform(0.6, 2.2)
    wobble = rng.uniform(0.0, 0.5)
    phase = rng.uniform(0.0, math.pi * 2)
    dx = math.cos(angle)
    dz = math.sin(angle)
    nx = -dz
    nz = dx
    samples = []
    for step in range(SPOKE_SAMPLES + 1):
        t = step / SPOKE_SAMPLES
        along = radius - MOUTH_INSET + t * length
        lateral = bend * math.sin(t * math.pi) + wobble * math.sin(t * math.pi * 2)
        samples.append({
            'x': dx * along + nx * lateral,
            'z': dz * along + nz * lateral,
            'half': SPOKE_WIDTH / 2 + math.sin(t * 8.4 + phase) * 0.3,
            't': t,
        })
    _stamp_frame(samples)
    return {
        'id': f'spoke-{index}',
        'name': name,
        'index': index,
        'angle': angle,
        'width': SPOKE_WIDTH,
        'length': length,
        'direction': (dx, dz),
        'samples': samples,
    }


def _round_deep(value):
    if isinstance(value, float):
        return _round(value)
    if isinstance(value, dict):
        return {key: _round_deep(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_round_deep(item) for item in value]
    return value


def _spoke_vista(spoke, rng):
    """The path carries on past the spoke's end, narrowing, with scrub and dead trees beside it.

    The game attaches the next location at the end of the spoke. This is what the player sees
    on the way there, so a spoke never stops at bare ground.
    """
    end = spoke['samples'][-1]
    length = rng.uniform(60.0, 80.0)
    sway = rng.choice((-1, 1)) * rng.uniform(2.0, 4.0)
    path = []
    for step in range(VISTA_STEPS + 1):
        t = step / VISTA_STEPS
        along = t * length
        lateral = math.sin(t * math.pi) * sway
        path.append({
            'x': end['x'] + end['tx'] * along + end['nx'] * lateral,
            'z': end['z'] + end['tz'] * along + end['nz'] * lateral,
            'half': end['half'] + (VISTA_END_HALF - end['half']) * t,
            't': t,
        })
    _stamp_frame(path)
    trees = []
    scrub = []
    for index in range(1, len(path)):
        sample = path[index]
        if sample['t'] > 0.8:
            continue
        side = -1 if index % 2 == 0 else 1
        lateral = sample['half'] + 2.6 + (index % 4) * 1.15
        trees.append(_vista_tree(sample, side, lateral, index, index % len(DEAD_TREE_VARIANTS), 1))
        if index % 2 == 0:
            trees.append(_vista_tree(sample, side, lateral + 6.5, index + 11, (index + 2) % len(DEAD_TREE_VARIANTS), 0.82))
        for brush_side in (-1, 1):
            reach = sample['half'] + 1.35 + ((index + (1 if brush_side > 0 else 0)) % 3) * 0.7
            along = ((index % 3) - 1) * 1.15
            scrub.append({
                'x': sample['x'] + sample['nx'] * brush_side * reach + sample['tx'] * along,
                'z': sample['z'] + sample['nz'] * brush_side * reach + sample['tz'] * along,
                'scale': 0.75 + (index % 4) * 0.22,
                'rotationY': (index * 1.31 + (0.4 if brush_side > 0 else 0)) % (math.pi * 2),
                'variant': (index + (1 if brush_side > 0 else 0)) % 2,
            })
    return _round_deep({'path': path, 'trees': trees, 'scrub': scrub})


def _mountains(radius, rng):
    """A ring of far mountains all round the hub, beyond the end of every spoke's vista."""
    items = []
    for index in range(MOUNTAIN_COUNT):
        angle = (index + rng.uniform(-0.3, 0.3)) * math.pi * 2 / MOUNTAIN_COUNT
        reach = radius + rng.uniform(150.0, 190.0)
        items.append({
            'x': math.cos(angle) * reach,
            'z': math.sin(angle) * reach,
            'height': rng.uniform(55.0, 115.0),
            'radius': rng.uniform(30.0, 44.0),
            'yaw': rng.uniform(-0.5, 0.5),
            'depth': rng.uniform(0.6, 0.84),
        })
    return _round_deep(items)


def _spoke_distance(spokes, x, z):
    """Distance from a point to the nearest spoke centreline."""
    best = math.inf
    for spoke in spokes:
        samples = spoke['samples']
        for index in range(len(samples) - 1):
            a = samples[index]
            b = samples[index + 1]
            cx, cz = _closest(x, z, a['x'], a['z'], b['x'], b['z'])
            best = min(best, math.hypot(x - cx, z - cz))
    return best


def _oriented_trigger(sample, back):
    """Axis-aligned trigger volume around a short slab across the spoke."""
    cx = sample['x'] - sample['tx'] * back
    cz = sample['z'] - sample['tz'] * back
    half_along = 0.9
    half_across = SPOKE_WIDTH / 2 - 0.4
    xs = []
    zs = []
    for a in (-half_along, half_along):
        for b in (-half_across, half_across):
            xs.append(cx + sample['tx'] * a + sample['nx'] * b)
            zs.append(cz + sample['tz'] * a + sample['nz'] * b)
    volume = _trigger((min(xs) + max(xs)) / 2, (min(zs) + max(zs)) / 2, max(xs) - min(xs), max(zs) - min(zs))
    return {key: _round(value) for key, value in volume.items()}


def _spoke_record(spoke):
    samples = spoke['samples']
    mouth = samples[0]
    end = samples[-1]
    return {
        'id': spoke['id'],
        'name': spoke['name'],
        'index': spoke['index'],
        'angle': _round(spoke['angle']),
        'width': spoke['width'],
        'length': _round(spoke['length']),
        'direction': [_round(spoke['direction'][0]), _round(spoke['direction'][1])],
        'samples': [{key: _round(value) for key, value in sample.items()} for sample in samples],
        'mouth': {'x': _round(mouth['x']), 'z': _round(mouth['z'])},
        'end': {'x': _round(end['x']), 'z': _round(end['z']), 'yaw': _round(_facing(end['tx'], end['tz']))},
        'transitionOut': f'to-{spoke["name"]}',
        'transitionIn': f'from-{spoke["name"]}',
        'polygon': _spoke_polygon(spoke),
        'vista': spoke['vista'],
    }


def _spoke_polygon(spoke):
    samples = spoke['samples']
    left = [[_round(s['x'] + s['nx'] * s['half']), _round(s['z'] + s['nz'] * s['half'])] for s in samples]
    right = [[_round(s['x'] - s['nx'] * s['half']), _round(s['z'] - s['nz'] * s['half'])] for s in samples]
    return left + right[::-1]


def _scatter_trees(rng, radius, spokes, bounds, respawn, count):
    trees = []
    guard = 0
    while len(trees) < count and guard < 1500:
        guard += 1
        angle = rng.uniform(0, math.pi * 2)
        reach = rng.uniform(radius - 5.0, radius + 14.0)
        x = math.cos(angle) * reach
        z = math.sin(angle) * reach
        if _spoke_distance(spokes, x, z) < SPOKE_WIDTH / 2 + 2.8:
            continue
        if _rect_distance(x, z, bounds) < 4.0:
            continue
        if math.hypot(x - respawn[0], z - respawn[1]) < 5.0:
            continue
        if any(math.hypot(tree['x'] - x, tree['z'] - z) < TREE_SPACING for tree in trees):
            continue
        variant = rng.randrange(0, len(DEAD_TREE_VARIANTS))
        spec = DEAD_TREE_VARIANTS[variant]
        trees.append({
            'x': _round(x),
            'z': _round(z),
            'nx': _round(-math.sin(angle)),
            'nz': _round(math.cos(angle)),
            'tx': _round(math.cos(angle)),
            'tz': _round(math.sin(angle)),
            'scale': _round(0.7 + rng.random() * 0.6),
            'rotationY': _round(rng.random() * math.pi * 2),
            'lean': _round((5 + rng.random() * 5) * (math.pi / 180) * (-1 if rng.random() < 0.5 else 1)),
            'leanAxis': _round(rng.random() * math.pi * 2),
            'variant': variant,
            'branches': spec['branches'],
            'height': spec['height'],
        })
    return trees


def _signposts(rng, spokes):
    """One signpost beside each spoke mouth, labelled with the spoke name."""
    items = []
    for spoke in spokes:
        mouth = spoke['samples'][0]
        side = rng.choice((-1, 1))
        lateral = mouth['half'] + 1.5
        x = mouth['x'] + mouth['nx'] * side * lateral - mouth['tx'] * 2.0
        z = mouth['z'] + mouth['nz'] * side * lateral - mouth['tz'] * 2.0
        items.append({
            'type': 'signpost',
            'x': _round(x),
            'z': _round(z),
            'rotationY': _round(math.atan2(-x, -z)),
            'scale': 1.0,
            'label': spoke['name'],
        })
    return items


def _scatter_scenery(rng, radius, spokes, bounds, respawn, trees, signs, clutter):
    types = sorted(HUB_MIX)
    weights = [HUB_MIX[kind] for kind in types]
    target = int(rng.randint(6, 16) * clutter * 2 + rng.random())
    items = list(signs)
    wanted = len(signs) + target
    attempts = 0
    while len(items) < wanted and attempts < target * 20 + 20:
        attempts += 1
        kind = rng.choices(types, weights)[0]
        lo, hi = SCENERY_TYPES[kind][1]
        angle = rng.uniform(0, math.pi * 2)
        reach = rng.uniform(4.0, radius + 10.0)
        x = math.cos(angle) * reach
        z = math.sin(angle) * reach
        if _spoke_distance(spokes, x, z) < SPOKE_WIDTH / 2 + 1.5:
            continue
        if _rect_distance(x, z, bounds) < 2.5:
            continue
        if math.hypot(x - respawn[0], z - respawn[1]) < 4.0:
            continue
        if any(math.hypot(item['x'] - x, item['z'] - z) < SCENERY_SPACING for item in items):
            continue
        if any(math.hypot(tree['x'] - x, tree['z'] - z) < SCENERY_TREE_GAP for tree in trees):
            continue
        item = {
            'type': kind,
            'x': round(x, 4),
            'z': round(z, 4),
            'rotationY': round(rng.uniform(0, math.pi * 2), 4),
            'scale': round(rng.uniform(lo, hi), 3),
        }
        if kind == 'scrub':
            item['variant'] = rng.randrange(0, 2)
        items.append(item)
    return items


def _interior(kind, structure, entrance, seed, clutter):
    rect = structure['rect']
    block = Block(kind.type, 'chamber', 0, Rect(rect['x'], rect['z'], rect['w'], rect['d']),
                  run=max(rect['w'], rect['d']), span=min(rect['w'], rect['d']))
    doors = [{'a': entrance['a'], 'b': entrance['b']}]
    sconce = _sconce(block, doors, sub_rng(seed, 'hub', 'sconce'))
    avoid = [(sconce['x'], sconce['z'], 2.0)]
    props = place_props(block, kind.theme, doors, avoid, sub_rng(seed, 'hub', 'props'), clutter)
    return {
        'id': 'space-0',
        'index': 0,
        'kind': 'chamber',
        'name': kind.label,
        'theme': kind.theme,
        'rect': dict(rect),
        'run': _round(block.run),
        'span': _round(block.span),
        'polygon': [list(point) for point in structure['polygon']],
        'spawns': [],
        'brazier': None,
        'sconce': sconce,
        'rocks': [],
        'props': props,
        'lighting': 'interior',
        'floor': 0,
        'y': 0.0,
        'storyHeight': _round(kind.height),
        'block': kind.type,
        'stair': None,
        'chest': None,
        'role': 'shelter',
        'description': kind.description,
    }


def _entrance(kind, structure):
    door = structure['door']
    half = door['width'] / 2
    a = [_round(door['x'] - half), door['z']]
    b = [_round(door['x'] + half), door['z']]
    return {
        'a': a,
        'b': b,
        'width': door['width'],
        'height': door['height'],
        'openingWidth': door['width'],
        'mouthA': list(a),
        'mouthB': list(b),
        'name': f'{kind.label} Door',
        'type': 'gate' if kind.type == 'castle' else 'door',
    }


def _structure_transitions(kind, structure):
    door = structure['door']
    rect = structure['rect']
    cx = door['x']
    wide = door['width'] - 0.6
    inside = door['z'] - 2.4
    return [
        {
            'id': 'structure-entry',
            'sourceZoneId': ZONE_HUB,
            'targetZoneId': ZONE_INTERIOR,
            'targetSpawnPoint': {'x': _round(cx), 'y': 0, 'z': _round(min(inside, rect['z'] + rect['d'] - 1.0)),
                                 'rotationY': 0},
            'transitionType': 'fade',
            'fadeDurationMs': 400,
            'environmentalPreset': _preset(HUT_INTERIOR),
            'volume': {key: _round(value) for key, value in _trigger(cx, door['z'] + 1.2, wide, 1.1).items()},
        },
        {
            'id': 'structure-exit',
            'sourceZoneId': ZONE_INTERIOR,
            'targetZoneId': ZONE_HUB,
            'targetSpawnPoint': {'x': _round(cx), 'y': 0, 'z': _round(door['z'] + 3.2), 'rotationY': _round(math.pi)},
            'transitionType': 'fade',
            'fadeDurationMs': 400,
            'environmentalPreset': _preset(DAY),
            'volume': {key: _round(value) for key, value in _trigger(cx, door['z'] - 1.0, wide, 1.0).items()},
        },
    ]


def _spoke_transitions(spokes):
    transitions = []
    for spoke in spokes:
        samples = spoke['samples']
        arrive = samples[int(SPOKE_SAMPLES * 0.6)]
        transitions.append({
            'id': f'to-{spoke["name"]}',
            'sourceZoneId': ZONE_HUB,
            'targetZoneId': spoke['name'],
            'targetSpawnPoint': None,
            'transitionType': 'fade',
            'fadeDurationMs': 300,
            'environmentalPreset': _preset(DAY),
            'volume': _oriented_trigger(samples[-1], 1.0),
        })
        transitions.append({
            'id': f'from-{spoke["name"]}',
            'sourceZoneId': spoke['name'],
            'targetZoneId': ZONE_HUB,
            'targetSpawnPoint': {
                'x': _round(arrive['x']),
                'y': 0,
                'z': _round(arrive['z']),
                'rotationY': _round(_facing(-arrive['tx'], -arrive['tz'])),
            },
            'transitionType': 'fade',
            'fadeDurationMs': 300,
            'environmentalPreset': _preset(DAY),
            'volume': None,
        })
    return transitions


def generate_hub(seed=1, spokes=None, names=None, structure=None, clutter=0.5):
    """Build a hub document: one structure, a respawn point, and named spokes.

    `spokes` is 1 to 8 (default 3, or the number of `names`). `names` label the first spokes
    and the rest are called spoke-N. `structure` is one of `structures.names()`, or None to let
    the seed pick. `clutter` is 0 to 1 and scales interior props and scenery.
    """
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise TypeError('seed must be an int')
    if isinstance(clutter, bool) or not isinstance(clutter, (int, float)):
        raise TypeError('clutter must be a number')
    if not math.isfinite(clutter) or clutter < 0 or clutter > 1:
        raise ValueError('clutter must be from 0 to 1')
    spoke_names = clean_names(names, spokes)
    if structure is not None and (not isinstance(structure, str) or structure not in structures.STRUCTURES):
        raise ValueError('structure must be one of: ' + ', '.join(structures.names()))

    kind = structures.pick(structure, sub_rng(seed, 'hub', 'structure'))
    size_rng = sub_rng(seed, 'hub', 'size')
    width, depth = structures.footprint(kind, size_rng)
    cx = round(size_rng.uniform(-2.0, 2.0), 2)

    plan = _plan(kind, width, depth, cx, len(spoke_names))
    radius = plan['radius']
    cz = round(plan['cz'], 2)
    built = structures.build(kind, cx, cz, width, depth)
    respawn = plan['respawn']

    spoke_rng = sub_rng(seed, 'hub', 'spokes')
    spoke_list = []
    for index, name in enumerate(spoke_names):
        jitter = spoke_rng.uniform(-0.15, 0.15) * plan['slot']
        angle = plan['start'] + (index + 0.5) * plan['slot'] + jitter
        spoke_list.append(_build_spoke(index, name, angle, radius, spoke_rng))

    vista_rng = sub_rng(seed, 'hub', 'vista')
    for spoke in spoke_list:
        spoke['vista'] = _spoke_vista(spoke, vista_rng)
    mountains = _mountains(radius, vista_rng)

    bounds = plan['bounds']
    tree_rng = sub_rng(seed, 'hub', 'trees')
    trees = _scatter_trees(tree_rng, radius, spoke_list, bounds, respawn, tree_rng.randint(18, 36))
    scenery_rng = sub_rng(seed, 'hub', 'scenery')
    signs = _signposts(scenery_rng, spoke_list)
    scenery = _scatter_scenery(scenery_rng, radius, spoke_list, bounds, respawn, trees, signs, clutter)

    entrance = None
    rooms = []
    transitions = []
    if kind.enterable:
        entrance = _entrance(kind, built)
        rooms.append(_interior(kind, built, entrance, seed, clutter))
        transitions.extend(_structure_transitions(kind, built))
    transitions.extend(_spoke_transitions(spoke_list))

    rx, rz = respawn
    yaw = _round(_facing(cx - rx, cz - rz))
    labels = {ZONE_HUB: 'The Hub'}
    if kind.enterable:
        labels[ZONE_INTERIOR] = kind.label
    return {
        'seed': int(seed) & 0xFFFFFFFF,
        'kind': 'hub',
        'floors': 1,
        'options': {'clutter': round(float(clutter), 3), 'structure': kind.type, 'spokes': spoke_names},
        'area': _round(width * depth),
        'rooms': rooms,
        'doors': [],
        'start': {'x': _round(rx), 'z': _round(rz), 'yaw': yaw},
        'lastRoomId': None,
        'areaName': 'The Hub',
        'requirements': [],
        'entrance': entrance,
        'structure': built,
        'trees': trees,
        'scenery': scenery,
        'zoneLabels': labels,
        'transitions': transitions,
        'hubArea': {
            'center': {'x': 0, 'z': 0},
            'radius': _round(radius),
            'plaza': _plaza_polygon(radius),
            'respawn': {'x': _round(rx), 'y': 0, 'z': _round(rz), 'yaw': yaw},
            'spokeWidth': SPOKE_WIDTH,
            'environment': _preset(DAY),
            'mountains': mountains,
            'spokes': [_spoke_record(spoke) for spoke in spoke_list],
        },
    }
