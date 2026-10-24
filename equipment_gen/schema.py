"""Checks a recipe before it is written. Loaders must not eval any field."""

import math
import re

from blk_dungeon_gen.fire import flame

KINDS = ('sword', 'shield', 'torch', 'mace', 'axe', 'hammer', 'spear', 'dagger', 'bow')
LEFT_HAND = frozenset({'torch', 'shield'})
COMBAT_KINDS = frozenset({'sword', 'dagger', 'mace', 'axe', 'hammer', 'spear', 'bow'})

MAX_REACH = {
    'dagger': 1.4,
    'sword': 2.9,
    'mace': 2.4,
    'axe': 2.4,
    'hammer': 2.4,
    'spear': 4.7,
    'torch': 1.0,
    'shield': 2.4,
    'bow': 3.9,
}
MIN_SPAN = {
    'dagger': 0.6,
    'sword': 1.5,
    'mace': 1.0,
    'axe': 1.0,
    'hammer': 1.0,
    'spear': 3.0,
    'torch': 0.5,
    'shield': 0.9,
    'bow': 2.2,
}

_ITEM_KEYS = frozenset({
    'version', 'kind', 'id', 'name', 'seed', 'hand', 'parent', 'castShadow',
    'materials', 'parts', 'grip', 'options', 'combat',
})
_PART_KEYS = frozenset({'name', 'material', 'geometry', 'position', 'rotation', 'type', 'vfx', 'light'})
_FORBIDDEN_CHARS = set('();`{}')
_FORBIDDEN_WORDS = re.compile(r'\b(sin|cos|eval|exec)\b', re.IGNORECASE)
_NAME = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-' ")


def _number(value, low, high, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{label} must be a number')
    if not math.isfinite(value) or value < low or value > high:
        raise ValueError(f'{label} is out of range')
    return float(value)


def _whole(value, low, high, label):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f'{label} must be a whole number')
    if value < low or value > high:
        raise ValueError(f'{label} is out of range')
    return value


def _vec(value, low, high, label):
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError(f'{label} must be three numbers')
    return tuple(_number(axis, low, high, label) for axis in value)


def _hex_color(value, label):
    if not isinstance(value, str) or len(value) != 7 or value[0] != '#':
        raise ValueError(f'{label} must be a #rrggbb colour')
    try:
        int(value[1:], 16)
    except ValueError:
        raise ValueError(f'{label} must be a #rrggbb colour') from None
    return value


def _reject_text(value):
    if not isinstance(value, str):
        return
    if any(char in value for char in _FORBIDDEN_CHARS) or _FORBIDDEN_WORDS.search(value):
        raise ValueError('a recipe cannot carry an expression')


def _walk(value):
    if isinstance(value, dict):
        if 'prefab' in value:
            raise ValueError('a recipe must not include the campfire prefab')
        for key, item in value.items():
            _reject_text(key)
            _walk(item)
    elif isinstance(value, list):
        for item in value:
            _walk(item)
    else:
        _reject_text(value)


def _rotate(point, rx, ry, rz):
    """XYZ Euler, matching Three.js: X first, then Y, then Z."""
    x, y, z = point
    cx, sx = math.cos(rx), math.sin(rx)
    y, z = y * cx - z * sx, y * sx + z * cx
    cy, sy = math.cos(ry), math.sin(ry)
    x, z = x * cy + z * sy, -x * sy + z * cy
    cz, sz = math.cos(rz), math.sin(rz)
    x, y = x * cz - y * sz, x * sz + y * cz
    return (x, y, z)


def _local_box(geometry):
    kind = geometry['type']
    if kind == 'box':
        half = (geometry['width'] / 2, geometry['height'] / 2, geometry['depth'] / 2)
        return half, (0.0, 0.0, 0.0)
    if kind == 'cylinder':
        radius = max(geometry['radiusTop'], geometry['radiusBottom'])
        return (radius, geometry['height'] / 2, radius), (0.0, 0.0, 0.0)
    if kind == 'sphere':
        radius = geometry['radius']
        return (radius, radius, radius), (0.0, 0.0, 0.0)
    if kind == 'cone':
        return (geometry['radius'], geometry['height'] / 2, geometry['radius']), (0.0, 0.0, 0.0)
    if kind == 'torus':
        reach = geometry['radius'] + geometry['tube']
        return (reach, reach, geometry['tube']), (0.0, 0.0, 0.0)
    if kind == 'plane':
        return (geometry['width'] / 2, geometry['height'] / 2, 0.001), (0.0, 0.0, 0.0)
    if kind == 'lathe':
        radii = [point[0] for point in geometry['points']]
        heights = [point[1] for point in geometry['points']]
        low, high = min(heights), max(heights)
        radius = max(radii)
        return (radius, (high - low) / 2, radius), (0.0, (low + high) / 2, 0.0)
    if kind == 'blade':
        width = max(geometry['baseWidth'], geometry['tipWidth'])
        return (width / 2, geometry['length'] / 2, geometry['thickness'] / 2), (0.0, 0.0, 0.0)
    if kind == 'shield':
        return (geometry['width'] / 2, geometry['height'] / 2, geometry['thickness'] / 2), (0.0, 0.0, 0.0)
    curve = geometry['curve']
    pts = (curve['from'], curve['control'], curve['to'])
    xs = [point[0] for point in pts]
    ys = [point[1] for point in pts]
    zs = [point[2] for point in pts]
    radius = geometry['radius']
    half = ((max(xs) - min(xs)) / 2 + radius, (max(ys) - min(ys)) / 2 + radius, (max(zs) - min(zs)) / 2 + radius)
    center = ((max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2, (max(zs) + min(zs)) / 2)
    return half, center


def _geometry(geometry, label):
    if not isinstance(geometry, dict):
        raise ValueError(f'{label} needs a geometry')
    kind = geometry.get('type')
    specs = {
        'box': (('width', 0.002, 2.5), ('height', 0.002, 2.5), ('depth', 0.002, 2.5)),
        'cylinder': (('radiusTop', 0, 1.2), ('radiusBottom', 0, 1.2), ('height', 0.008, 3.4)),
        'sphere': (('radius', 0.004, 0.6),),
        'cone': (('radius', 0.003, 0.5), ('height', 0.008, 0.8)),
        'torus': (('radius', 0.008, 1.2), ('tube', 0.002, 0.2)),
        'plane': (('width', 0.01, 2), ('height', 0.01, 2)),
        'blade': (
            ('length', 0.05, 2.2), ('baseWidth', 0.008, 0.5), ('tipWidth', 0, 0.5),
            ('thickness', 0.003, 0.08), ('fuller', 0, 1),
        ),
        'shield': (('width', 0.3, 1.7), ('height', 0.3, 1.9), ('thickness', 0.01, 0.12)),
        'tube': (('radius', 0.002, 0.08),),
    }
    wholes = {
        'cylinder': (('radialSegments', 3, 32),),
        'sphere': (('widthSegments', 3, 32), ('heightSegments', 3, 24)),
        'cone': (('radialSegments', 3, 32),),
        'torus': (('radialSegments', 3, 24), ('tubularSegments', 3, 48)),
        'lathe': (('segments', 3, 32),),
        'blade': (('segments', 2, 16),),
        'tube': (('tubularSegments', 3, 48), ('radialSegments', 3, 24)),
    }
    if kind not in specs and kind != 'lathe':
        raise ValueError(f'{label} has an unknown geometry')
    allowed = {'type'}
    for name, low, high in specs.get(kind, ()):
        _number(geometry.get(name), low, high, f'{label} {name}')
        allowed.add(name)
    for name, low, high in wholes.get(kind, ()):
        _whole(geometry.get(name), low, high, f'{label} {name}')
        allowed.add(name)
    if kind == 'blade' and geometry['tipWidth'] > geometry['baseWidth'] + 1e-6:
        raise ValueError(f'{label} tip is wider than its base')
    if kind == 'shield':
        if geometry.get('outline') not in ('round', 'heater', 'tower'):
            raise ValueError(f'{label} has an unknown shield outline')
        allowed.add('outline')
    if kind == 'lathe':
        points = geometry.get('points')
        if not isinstance(points, list) or not 3 <= len(points) <= 16:
            raise ValueError(f'{label} lathe needs 3 to 16 points')
        for point in points:
            if not isinstance(point, list) or len(point) != 2:
                raise ValueError(f'{label} lathe point must be radius and height')
            _number(point[0], 0.001, 0.6, f'{label} radius')
            _number(point[1], -0.4, 2.4, f'{label} height')
        allowed.add('points')
    if kind == 'tube':
        curve = geometry.get('curve')
        if not isinstance(curve, dict) or curve.get('type') != 'quadratic':
            raise ValueError(f'{label} tube needs a quadratic curve')
        for name in ('from', 'control', 'to'):
            _vec(curve.get(name), -2.2, 2.2, f'{label} curve')
        if set(curve) != {'type', 'from', 'control', 'to'}:
            raise ValueError(f'{label} curve has an unexpected field')
        allowed.add('curve')
    if set(geometry) != allowed:
        raise ValueError(f'{label} geometry has an unexpected field')


def _part_corners(record):
    position = _vec(record.get('position'), -4, 4, record.get('name', 'part'))
    rotation = record.get('rotation')
    if rotation is None:
        angles = (0.0, 0.0, 0.0)
    else:
        if not isinstance(rotation, dict) or set(rotation) != {'x', 'y', 'z', 'unit'} or rotation.get('unit') != 'degrees':
            raise ValueError(f'{record.get("name", "part")} rotation must be degrees')
        angles = tuple(math.radians(_number(rotation[axis], -180, 180, 'rotation')) for axis in ('x', 'y', 'z'))
    if record.get('type') == 'group':
        half, center = (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)
    else:
        half, center = _local_box(record['geometry'])
    corners = []
    for sx in (-1.0, 1.0):
        for sy in (-1.0, 1.0):
            for sz in (-1.0, 1.0):
                local = (center[0] + sx * half[0], center[1] + sy * half[1], center[2] + sz * half[2])
                turned = _rotate(local, *angles)
                corners.append((turned[0] + position[0], turned[1] + position[1], turned[2] + position[2]))
    return corners


def _combat(combat):
    if not isinstance(combat, dict) or set(combat) != {'range', 'arcRadians', 'damage', 'attackInterval'}:
        raise ValueError('combat must be range, arc, damage, and attack interval')
    _number(combat['range'], 0.4, 40, 'range')
    _number(combat['arcRadians'], 0.05, 3.2, 'arc')
    _number(combat['damage'], 1, 80, 'damage')
    _number(combat['attackInterval'], 0.2, 2.5, 'attack interval')


def validate(item):
    """Raise ValueError when a recipe is not safe to write."""
    if not isinstance(item, dict) or set(item) - _ITEM_KEYS:
        raise ValueError('recipe has an unexpected field')
    _walk(item)
    if item.get('version') != 1:
        raise ValueError('version must be 1')
    kind = item.get('kind')
    if kind not in KINDS or item.get('id') != kind:
        raise ValueError('kind is not a known equipment id')
    name = item.get('name')
    if not isinstance(name, str) or not 3 <= len(name) <= 64 or any(char not in _NAME for char in name):
        raise ValueError('name must be plain words')
    seed = item.get('seed')
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError('seed must be zero or greater')
    hand = 'left' if kind in LEFT_HAND else 'right'
    if item.get('hand') != hand or item.get('parent') != f'{hand}HandSocket':
        raise ValueError('hand does not match the kind')
    if item.get('castShadow') is not False:
        raise ValueError('castShadow must be false')
    options = item.get('options')
    if options != {'kind': kind, 'seed': seed, 'tier': options.get('tier') if isinstance(options, dict) else None}:
        raise ValueError('options must record the kind, seed, and tier')
    tier = options['tier']
    if isinstance(tier, bool) or not isinstance(tier, int) or not 1 <= tier <= 5:
        raise ValueError('tier must be from 1 to 5')
    grip = item.get('grip')
    if not isinstance(grip, dict) or set(grip) != {'restRotation'}:
        raise ValueError('grip needs a rest rotation')
    rest = grip['restRotation']
    if not isinstance(rest, dict) or set(rest) != {'x', 'y', 'z', 'unit'} or rest.get('unit') != 'degrees':
        raise ValueError('rest rotation must be degrees')
    for axis in ('x', 'y', 'z'):
        _number(rest[axis], -180, 180, 'rest rotation')
    materials = item.get('materials')
    if not isinstance(materials, dict) or not materials:
        raise ValueError('materials are required')
    for key, entry in materials.items():
        if not isinstance(key, str) or not key.isalpha() or not key.islower():
            raise ValueError('material name must be a lowercase word')
        if not isinstance(entry, dict) or set(entry) != {'color', 'roughness', 'metalness'}:
            raise ValueError(f'{key} material has an unexpected field')
        _hex_color(entry['color'], key)
        _number(entry['roughness'], 0, 1, f'{key} roughness')
        _number(entry['metalness'], 0, 1, f'{key} metalness')
    parts = item.get('parts')
    if not isinstance(parts, list) or not 2 <= len(parts) <= 40:
        raise ValueError('a recipe needs between 2 and 40 parts')
    names = []
    flames = 0
    corners = []
    expected = flame()
    for record in parts:
        if not isinstance(record, dict) or set(record) - _PART_KEYS:
            raise ValueError('a part has an unexpected field')
        part_name = record.get('name')
        if not isinstance(part_name, str) or not part_name.isalnum() or not part_name[0].isalpha():
            raise ValueError('part name must be a single word')
        names.append(part_name)
        if record.get('type') == 'group':
            if 'geometry' in record or 'material' in record:
                raise ValueError(f'{part_name} is a socket and has no mesh')
            if 'vfx' in record or 'light' in record:
                if record.get('vfx') != expected['vfx'] or record.get('light') != expected['light']:
                    raise ValueError('fire must match the campfire flame')
                flames += 1
        else:
            if 'type' in record or 'vfx' in record or 'light' in record:
                raise ValueError(f'{part_name} cannot carry fire')
            if record.get('material') not in materials:
                raise ValueError(f'{part_name} uses an unknown material')
            _geometry(record.get('geometry'), part_name)
        corners.extend(_part_corners(record))
    if len(names) != len(set(names)):
        raise ValueError('part names must be unique')
    if kind == 'torch':
        sockets = [record for record in parts if record.get('name') == 'TorchTipSocket']
        if len(sockets) != 1 or flames != 1 or sockets[0].get('type') != 'group':
            raise ValueError('a torch needs one TorchTipSocket with the campfire flame')
    elif flames:
        raise ValueError('only a torch carries fire')
    if kind in COMBAT_KINDS:
        _combat(item.get('combat'))
    elif 'combat' in item:
        raise ValueError(f'{kind} has no combat block')
    reach = max(math.sqrt(x * x + y * y + z * z) for x, y, z in corners)
    xs = [point[0] for point in corners]
    ys = [point[1] for point in corners]
    zs = [point[2] for point in corners]
    span = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    if reach > MAX_REACH[kind]:
        raise ValueError(f'{kind} extends to {reach:.2f}, past {MAX_REACH[kind]}')
    if span < MIN_SPAN[kind]:
        raise ValueError(f'{kind} spans {span:.2f}, under {MIN_SPAN[kind]}')
    return item
