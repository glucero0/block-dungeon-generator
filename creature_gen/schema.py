"""Checks a creature file before it is written. Loaders must not eval any field."""

import math
import re

from .species import SPECIES

_TOP = frozenset({
    'name', 'description', 'species', 'seed', 'plan', 'scale', 'options',
    'stats', 'materials', 'joints', 'parts', 'weapons',
})
_JOINT = frozenset({'name', 'parent', 'position', 'rotation'})
_PART = frozenset({'name', 'joint', 'material', 'geometry', 'position', 'rotation'})
_STATS = (
    'health', 'damage', 'moveSpeed', 'wanderFactor', 'radius',
    'sightRange', 'windup', 'recover', 'minWindup', 'minRecover',
)
_STAT_RANGE = {
    'health': (1, 400),
    'damage': (1, 80),
    'moveSpeed': (0.2, 20),
    'wanderFactor': (0, 1),
    'radius': (0.15, 3),
    'sightRange': (1, 80),
    'windup': (0.05, 3),
    'recover': (0.05, 4),
    'minWindup': (0, 3),
    'minRecover': (0, 4),
}
_WEAPONS = frozenset({'sword', 'mace', 'hammer', 'bow'})
_MATERIAL = frozenset({'color', 'roughness', 'metalness'})
_FUR = _MATERIAL | frozenset({'length', 'tip', 'pattern'})
_FUR_BELLY = _FUR | frozenset({'belly'})
_FUR_PATTERNS = frozenset({'solid', 'agouti', 'brindle', 'patch'})
_HUMANOID = (
    'fall', 'spine', 'skull',
    'SkeletonArm_R', 'SkeletonArm_L', 'Forearm_R', 'Forearm_L',
    'WristJoint_R', 'WristJoint_L', 'HandSocket_R', 'HandSocket_L',
    'Hip_L', 'Hip_R', 'Knee_L', 'Knee_R',
)
_QUADRUPED = (
    'body',
    'Hip_FL', 'Hip_FR', 'Hip_BL', 'Hip_BR',
    'Knee_FL', 'Knee_FR', 'Knee_BL', 'Knee_BR',
    'neck', 'head', 'tail',
)
_PARENT = {
    'spine': 'fall',
    'skull': 'spine',
    'SkeletonArm_R': 'spine',
    'SkeletonArm_L': 'spine',
    'Forearm_R': 'SkeletonArm_R',
    'Forearm_L': 'SkeletonArm_L',
    'WristJoint_R': 'Forearm_R',
    'WristJoint_L': 'Forearm_L',
    'HandSocket_R': 'WristJoint_R',
    'HandSocket_L': 'WristJoint_L',
    'Hip_L': 'fall',
    'Hip_R': 'fall',
    'Knee_L': 'Hip_L',
    'Knee_R': 'Hip_R',
    'Hip_FL': 'body',
    'Hip_FR': 'body',
    'Hip_BL': 'body',
    'Hip_BR': 'body',
    'Knee_FL': 'Hip_FL',
    'Knee_FR': 'Hip_FR',
    'Knee_BL': 'Hip_BL',
    'Knee_BR': 'Hip_BR',
    'neck': 'body',
    'head': 'neck',
    'tail': 'body',
}
_NAME = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-' ")
_DESCRIPTION = _NAME | set('.,')
_FORBIDDEN_CHARS = set('();`{}')
_FORBIDDEN_WORDS = re.compile(r'\b(sin|cos|eval|exec)\b', re.IGNORECASE)
_MAX_HEIGHT = 8.5


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
        raise ValueError('a creature file cannot carry an expression')


def _walk(value):
    if isinstance(value, dict):
        if 'prefab' in value:
            raise ValueError('a creature file must not include the campfire prefab')
        for key, item in value.items():
            _reject_text(key)
            _walk(item)
    elif isinstance(value, list):
        for item in value:
            _walk(item)
    else:
        _reject_text(value)


def _rotation(value, label):
    if not isinstance(value, dict) or set(value) != {'x', 'y', 'z', 'unit'} or value.get('unit') != 'degrees':
        raise ValueError(f'{label} rotation must be degrees')
    for axis in ('x', 'y', 'z'):
        _number(value[axis], -180, 180, label)


def _geometry(geometry, label):
    if not isinstance(geometry, dict):
        raise ValueError(f'{label} needs a geometry')
    kind = geometry.get('type')
    specs = {
        'box': (('width', 0.02, 5), ('height', 0.02, 5), ('depth', 0.02, 5)),
        'sphere': (('radius', 0.012, 1.6),),
        'cylinder': (('radiusTop', 0, 1.6), ('radiusBottom', 0, 1.6), ('height', 0.02, 6)),
        'capsule': (('radius', 0.012, 1.6), ('length', 0.04, 6)),
        'cone': (('radius', 0.01, 1), ('height', 0.03, 2.5)),
        'torus': (('radius', 0.03, 2), ('tube', 0.008, 0.4)),
    }
    wholes = {
        'sphere': (('widthSegments', 3, 24), ('heightSegments', 3, 16)),
        'cylinder': (('radialSegments', 3, 24),),
        'capsule': (('capSegments', 1, 8), ('radialSegments', 3, 16)),
        'cone': (('radialSegments', 3, 24),),
        'torus': (('radialSegments', 3, 16), ('tubularSegments', 3, 32)),
    }
    if kind not in specs:
        raise ValueError(f'{label} has an unknown geometry')
    allowed = {'type'}
    for name, low, high in specs[kind]:
        _number(geometry.get(name), low, high, f'{label} {name}')
        allowed.add(name)
    for name, low, high in wholes.get(kind, ()):
        _whole(geometry.get(name), low, high, f'{label} {name}')
        allowed.add(name)
    if set(geometry) != allowed:
        raise ValueError(f'{label} geometry has an unexpected field')


def _half(geometry):
    kind = geometry['type']
    if kind == 'box':
        return geometry['width'] / 2, geometry['height'] / 2, geometry['depth'] / 2
    if kind == 'sphere':
        return (geometry['radius'],) * 3
    if kind == 'cylinder':
        radius = max(geometry['radiusTop'], geometry['radiusBottom'])
        return radius, geometry['height'] / 2, radius
    if kind == 'capsule':
        reach = geometry['length'] / 2 + geometry['radius']
        return geometry['radius'], reach, geometry['radius']
    if kind == 'cone':
        return geometry['radius'], geometry['height'] / 2, geometry['radius']
    reach = geometry['radius'] + geometry['tube']
    return reach, reach, reach


def _euler(record):
    rotation = record.get('rotation')
    if not rotation:
        return (0.0, 0.0, 0.0)
    return tuple(math.radians(rotation[axis]) for axis in ('x', 'y', 'z'))


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


def _ancestors(joints, name):
    by_name = {record['name']: record for record in joints}
    ordered = []

    def walk(current, seen):
        if current in seen:
            raise ValueError('joints must not form a loop')
        record = by_name[current]
        if record['parent'] is not None:
            walk(record['parent'], seen | {current})
        ordered.append(record)

    walk(name, frozenset())
    return ordered


def _bounds(joints, parts):
    """World bounds after joint and part rotations, so a horizontal chest is not counted as tall."""
    low = math.inf
    high = -math.inf
    for record in parts:
        half = _half(record['geometry'])
        corners = [
            (sx * half[0], sy * half[1], sz * half[2])
            for sx in (-1.0, 1.0)
            for sy in (-1.0, 1.0)
            for sz in (-1.0, 1.0)
        ]
        corners = [_rotate(point, *_euler(record)) for point in corners]
        position = record['position']
        corners = [(point[0] + position[0], point[1] + position[1], point[2] + position[2]) for point in corners]
        for joint_record in reversed(_ancestors(joints, record['joint'])):
            corners = [_rotate(point, *_euler(joint_record)) for point in corners]
            origin = joint_record['position']
            corners = [(point[0] + origin[0], point[1] + origin[1], point[2] + origin[2]) for point in corners]
        for _, y, _ in corners:
            low = min(low, y)
            high = max(high, y)
    if high - low > _MAX_HEIGHT or low < -0.8 or high > _MAX_HEIGHT:
        raise ValueError('the figure is outside the height limit')


def _chain(plan, by_name):
    required = _HUMANOID if plan == 'humanoid' else _QUADRUPED
    root = 'fall' if plan == 'humanoid' else 'body'
    for name in required:
        record = by_name.get(name)
        if record is None:
            raise ValueError(f'{plan} is missing {name}')
        expect = None if name == root else _PARENT[name]
        if record['parent'] != expect:
            raise ValueError(f'{name} is parented to the wrong joint')


def validate(creature):
    """Raise ValueError when a creature file is not safe to write."""
    if not isinstance(creature, dict) or set(creature) - _TOP:
        raise ValueError('creature file has an unexpected field')
    _walk(creature)
    species = creature.get('species')
    if species not in SPECIES:
        raise ValueError('species is not in the roster')
    plan = SPECIES[species]['plan']
    if creature.get('plan') != plan:
        raise ValueError('plan does not match the species')
    name = creature.get('name')
    if not isinstance(name, str) or not 3 <= len(name) <= 64 or any(char not in _NAME for char in name):
        raise ValueError('name must be plain words')
    description = creature.get('description')
    if not isinstance(description, str) or not 12 <= len(description) <= 180:
        raise ValueError('description must be a short sentence')
    if any(char not in _DESCRIPTION for char in description):
        raise ValueError('description must be plain words')
    seed = creature.get('seed')
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError('seed must be zero or greater')
    _number(creature.get('scale'), 0.25, 2, 'scale')
    options = creature.get('options')
    if options != {'species': species, 'seed': seed}:
        raise ValueError('options must record the species and seed')
    stats = creature.get('stats')
    if not isinstance(stats, dict) or set(stats) != set(_STATS):
        raise ValueError('stats must match the skeletal warrior fields')
    for key in _STATS:
        low, high = _STAT_RANGE[key]
        _number(stats.get(key), low, high, key)
    if stats['minWindup'] > stats['windup'] + 1e-9 or stats['minRecover'] > stats['recover'] + 1e-9:
        raise ValueError('minimum windup and recover must stay under the full times')
    weapons = creature.get('weapons', None)
    if plan == 'humanoid':
        if not isinstance(weapons, list) or not 1 <= len(weapons) <= 4:
            raise ValueError('a humanoid needs one to four weapons')
        seen = []
        for weapon in weapons:
            if not isinstance(weapon, dict) or set(weapon) != {'id', 'range'}:
                raise ValueError('a weapon needs an id and a range')
            if weapon['id'] not in _WEAPONS or weapon['id'] in seen:
                raise ValueError('weapons must be unique ids of sword, mace, hammer, or bow')
            _number(weapon['range'], 0.5, 40, 'range')
            seen.append(weapon['id'])
    elif 'weapons' in creature:
        raise ValueError('a quadruped has no weapon cycle')
    materials = creature.get('materials')
    if not isinstance(materials, dict) or not materials:
        raise ValueError('materials are required')
    for key, entry in materials.items():
        if not isinstance(key, str) or not key.isalpha() or not key.islower():
            raise ValueError('material name must be a lowercase word')
        if not isinstance(entry, dict) or set(entry) not in (_MATERIAL, _FUR, _FUR_BELLY):
            raise ValueError(f'{key} material has an unexpected field')
        if set(entry) >= _FUR and key != 'fur':
            raise ValueError(f'{key} material has an unexpected field')
        _hex_color(entry['color'], key)
        _number(entry['roughness'], 0, 1, f'{key} roughness')
        _number(entry['metalness'], 0, 1, f'{key} metalness')
        if 'length' in entry:
            _number(entry['length'], 0.008, 0.8, f'{key} length')
            _hex_color(entry['tip'], f'{key} tip')
            if entry['pattern'] not in _FUR_PATTERNS:
                raise ValueError(f'{key} pattern is not a fur pattern')
        if 'belly' in entry:
            _hex_color(entry['belly'], f'{key} belly')
    if plan == 'quadruped' and (not isinstance(materials.get('fur'), dict) or 'length' not in materials['fur']):
        raise ValueError('a quadruped needs a fur coat')
    joints = creature.get('joints')
    if not isinstance(joints, list) or not 8 <= len(joints) <= 24:
        raise ValueError('a creature needs its joints')
    by_name = {}
    roots = 0
    for record in joints:
        if not isinstance(record, dict) or set(record) - _JOINT:
            raise ValueError('a joint has an unexpected field')
        joint_name = record.get('name')
        if not isinstance(joint_name, str) or not joint_name.replace('_', '').isalnum() or not joint_name[0].isalpha():
            raise ValueError('joint name must be a single word')
        if joint_name in by_name:
            raise ValueError('joint names must be unique')
        parent = record.get('parent', 'missing')
        if parent is None:
            roots += 1
        elif not isinstance(parent, str):
            raise ValueError(f'{joint_name} needs a parent')
        record['position'] = list(_vec(record.get('position'), -12, 12, joint_name))
        if 'rotation' in record:
            _rotation(record['rotation'], joint_name)
        by_name[joint_name] = record
    if roots != 1:
        raise ValueError('a creature needs one root joint')
    for record in joints:
        parent = record['parent']
        if parent is not None and parent not in by_name:
            raise ValueError(f'{record["name"]} parent is missing')
    _chain(plan, by_name)
    parts = creature.get('parts')
    if not isinstance(parts, list) or not 4 <= len(parts) <= 96:
        raise ValueError('a creature needs its parts')
    names = []
    used = set()
    for record in parts:
        if not isinstance(record, dict) or set(record) - _PART:
            raise ValueError('a part has an unexpected field')
        part_name = record.get('name')
        if not isinstance(part_name, str) or not part_name.isalnum() or not part_name[0].isalpha():
            raise ValueError('part name must be a single word')
        names.append(part_name)
        joint_name = record.get('joint')
        if joint_name not in by_name:
            raise ValueError(f'{part_name} is not on a joint')
        if record.get('material') not in materials:
            raise ValueError(f'{part_name} uses an unknown material')
        used.add(record['material'])
        _geometry(record.get('geometry'), part_name)
        record['position'] = list(_vec(record.get('position'), -12, 12, part_name))
        if 'rotation' in record:
            _rotation(record['rotation'], part_name)
    if len(names) != len(set(names)):
        raise ValueError('part names must be unique')
    if used != set(materials):
        raise ValueError('every material must be used')
    _bounds(joints, parts)
    return creature
