"""Four-legged creatures in game units, 3.2 units to a metre.

The torso is a chest capsule and a narrower pelvis capsule. The neck leans
forward. Each leg is an upper bone, a lower bone, a cannon, and a foot, with
the hind hock set back. Harper's Row still animates only the humanoid joints.
"""

import math

from blk_dungeon_gen.seeding import sub_rng

from .finish import assemble
from .materials import TONE_TITLE, fur_coat, paint, wolf_coat
from .shapes import cone, cylinder, joint, long_bone, part, sphere
from .species import SPECIES

# Game units per metre, the same scale as the skeletal warrior in skeleton.js.
UNIT = 3.2

# withers and torso are metres. chest and pelvis are (length, radius).
# neck is (length, base radius, tip radius, pitch degrees from vertical).
# head, snout, and ear are (length, radius).
# A limb entry is (dy, dz) in metres. dy is downward, +dz is forward.
# tail is (length, radius, droop degrees per segment, segment count).
_BODY = {
    'wolf': {
        'withers': 0.74,
        'torso': 1.25,
        'chest': (0.58, 0.21),
        'abdomen': (0.48, 0.115),
        'pelvis': (0.30, 0.085),
        'neck': (0.34, 0.13, 0.08, 112),
        'head': (0.15, 0.07),
        'snout': (0.12, 0.058),
        'ear': (0.13, 0.038),
        'skull': 'wide',
        'stance': 0.12,
        'leg': 0.038,
        'front': ((-0.15, -0.015), (-0.13, 0.02), (-0.10, 0.018), (-0.10, 0.06)),
        'hind': ((-0.16, 0.07), (-0.14, -0.11), (-0.055, -0.012), (-0.125, 0.055)),
        'tail': (0.42, 0.07, 12, 4),
        'tail_hang': 82,
        'tail_taper': 0.24,
        'coat': 0.055,
        'mane': 0,
        'antler': 0.0,
    },
    'bear': {
        'withers': 1.15,
        'torso': 1.55,
        'chest': (0.95, 0.36),
        'pelvis': (0.70, 0.26),
        'neck': (0.32, 0.18, 0.12, 36),
        'head': (0.34, 0.15),
        'snout': (0.16, 0.07),
        'ear': (0.08, 0.035),
        'stance': 0.22,
        'leg': 0.10,
        'front': ((-0.36, -0.05), (-0.30, 0.04), (-0.16, 0.02), (-0.14, 0.10)),
        'hind': ((-0.38, 0.10), (-0.32, -0.08), (-0.08, -0.02), (-0.14, 0.16)),
        'tail': (0.14, 0.04, 18, 3),
        'coat': 0.10,
        'mane': 0,
        'antler': 0.0,
    },
    'boar': {
        'withers': 0.70,
        'torso': 1.20,
        'chest': (0.72, 0.22),
        'pelvis': (0.55, 0.16),
        'neck': (0.20, 0.12, 0.08, 34),
        'head': (0.26, 0.10),
        'snout': (0.22, 0.05),
        'ear': (0.07, 0.025),
        'stance': 0.14,
        'leg': 0.055,
        'front': ((-0.22, -0.04), (-0.18, 0.03), (-0.14, 0.01), (-0.07, 0.03)),
        'hind': ((-0.24, 0.08), (-0.20, -0.06), (-0.12, -0.015), (-0.07, 0.025)),
        'tail': (0.20, 0.014, 20, 3),
        'coat': 0.035,
        'mane': 0,
        'antler': 0.0,
    },
    'horse': {
        'withers': 1.60,
        'torso': 2.40,
        'chest': (1.45, 0.28),
        'pelvis': (1.05, 0.20),
        'neck': (0.85, 0.15, 0.08, 50),
        'head': (0.50, 0.11),
        'snout': (0.30, 0.06),
        'ear': (0.14, 0.03),
        'stance': 0.18,
        'leg': 0.07,
        'front': ((-0.42, -0.12), (-0.38, 0.06), (-0.48, 0.02), (-0.10, 0.04)),
        'hind': ((-0.46, 0.16), (-0.44, -0.15), (-0.46, -0.02), (-0.10, 0.04)),
        'tail': (0.90, 0.04, 12, 6),
        'coat': 0.018,
        'mane': 5,
        'antler': 0.0,
    },
    'deer': {
        'withers': 1.05,
        'torso': 1.35,
        'chest': (0.80, 0.16),
        'pelvis': (0.60, 0.11),
        'neck': (0.42, 0.08, 0.045, 48),
        'head': (0.28, 0.07),
        'snout': (0.16, 0.032),
        'ear': (0.14, 0.028),
        'stance': 0.12,
        'leg': 0.04,
        'front': ((-0.32, -0.06), (-0.28, 0.04), (-0.30, 0.012), (-0.07, 0.02)),
        'hind': ((-0.34, 0.10), (-0.30, -0.09), (-0.28, -0.01), (-0.07, 0.02)),
        'tail': (0.16, 0.016, 16, 3),
        'coat': 0.022,
        'mane': 0,
        'antler': 0.42,
    },
    'rat': {
        'withers': 0.10,
        'torso': 0.25,
        'chest': (0.15, 0.028),
        'pelvis': (0.11, 0.018),
        'neck': (0.03, 0.014, 0.008, 32),
        'head': (0.03, 0.012),
        'snout': (0.022, 0.006),
        'ear': (0.014, 0.0045),
        'stance': 0.022,
        'leg': 0.004,
        'front': ((-0.026, -0.004), (-0.024, 0.003), (-0.022, 0.002), (-0.022, 0.004)),
        'hind': ((-0.028, 0.006), (-0.024, -0.005), (-0.022, -0.002), (-0.022, 0.005)),
        'tail': (0.20, 0.004, 14, 5),
        'coat': 0.006,
        'mane': 0,
        'antler': 0.0,
    },
}


def _m(metres):
    return metres * UNIT


def _fit_capsule(total, radius):
    """Keep a capsule inside the schema when a rat bone is only a few centimetres."""
    total = max(total, 0.07)
    radius = min(max(radius, 0.013), max(0.013, (total - 0.045) / 2))
    return long_bone(total, radius)


def _limb(joints, parts, label, side, origin, segments, radius, hoof):
    """Upper, lower, cannon, and foot. Each joint sits at the end of the bone above it.

    Hind segments put the hock behind the stifle: the femur runs forward and the
    tibia runs back.
    """
    names = ('upper', 'lower', 'cannon', 'hoof')
    joint_names = (f'Hip_{label}', f'Knee_{label}', f'Ankle_{label}')
    parents = ('body', f'Hip_{label}', f'Knee_{label}')
    radii = (radius * 1.2, radius * 0.9, radius * 0.55, radius * (0.7 if hoof else 1.15))
    for index in range(3):
        if index == 0:
            position = origin
        else:
            previous = segments[index - 1]
            position = (0.0, _m(previous[0]), _m(previous[1]))
        joints.append(joint(joint_names[index], parents[index], position))
    for index, (dy, dz) in enumerate(segments):
        offset = (0.0, _m(dy), _m(dz))
        bone_len = math.hypot(offset[1], offset[2])
        pitch = math.degrees(math.atan2(offset[2], offset[1])) if bone_len else 0.0
        host = joint_names[min(index, 2)]
        start = (0.0, 0.0, 0.0) if index < 3 else (0.0, _m(segments[2][0]), _m(segments[2][1]))
        end_y = start[1] + offset[1]
        end_z = start[2] + offset[2]
        parts.append(part(
            f'{names[index]}{label}',
            host,
            'socket' if hoof and index == 3 else 'fur',
            _fit_capsule(bone_len, radii[index]),
            (side * radius * 0.02, (start[1] + end_y) / 2, (start[2] + end_z) / 2),
            (pitch, 0, 0),
        ))


def _tail(parts, length, radius, droop, count, hang=10.0, taper=0.1):
    y = 0.0
    z = 0.0
    angle = hang
    segment = length / count
    for index in range(count):
        rad = math.radians(angle)
        dy = -math.sin(rad) * segment
        dz = -math.cos(rad) * segment
        pitch = math.degrees(math.atan2(dz, dy))
        parts.append(part(
            f'tail{index}',
            'tail',
            'fur',
            _fit_capsule(segment, max(0.013, radius * (1 - taper * index))),
            (0, y + dy / 2, z + dz / 2),
            (pitch, 0, 0),
        ))
        y += dy
        z += dz
        angle = min(angle + droop, 100)


def _mane(parts, neck_len, count):
    for index in range(count):
        along = neck_len * (index + 0.6) / (count + 0.4)
        parts.append(part(
            f'mane{index}',
            'neck',
            'fur',
            _fit_capsule(neck_len / count, neck_len * 0.035),
            (neck_len * 0.03, along, -neck_len * 0.05),
            (-80 - index * 7, 0, 18),
        ))


def build_quadruped(species_id, seed):
    spec = SPECIES[species_id]
    body = _BODY[species_id]
    rng = sub_rng(seed, species_id)
    tone = spec['tones'][seed % len(spec['tones'])]
    materials = {}
    fur_rng = sub_rng(seed, species_id, 'fur')
    if species_id == 'wolf':
        wolf_coat(materials, tone, fur_rng, _m(body['coat']))
    else:
        fur_coat(materials, tone, fur_rng, _m(body['coat']))
    paint(materials, 'socket', 'socket')
    if spec['tusks'] or spec['antlers']:
        paint(materials, 'bone', 'bone')
    name = f'{TONE_TITLE[tone]} {spec["title"]}'

    chest_len, chest_rad = body['chest']
    pelvis_len, pelvis_rad = body['pelvis']
    torso = body['torso']
    chest_z = torso / 2 - chest_len / 2
    pelvis_z = -(torso / 2 - pelvis_len / 2)
    withers = body['withers']
    chest_y = withers - chest_rad
    if 'abdomen' in body:
        pelvis_y = withers - pelvis_rad * 1.2
    else:
        pelvis_y = chest_y - chest_rad * 0.35

    neck_len, neck_base, neck_tip, neck_pitch = body['neck']
    neck_y = withers - chest_rad * 0.15
    neck_z = chest_z + chest_len * 0.42
    head_len, head_rad = body['head']
    snout_len, snout_rad = body['snout']
    ear_len, ear_rad = body['ear']

    joints = [
        joint('body', None, (0, 0, 0)),
        joint('neck', 'body', (_m(0), _m(neck_y), _m(neck_z)), (neck_pitch, 0, 0)),
        joint('head', 'neck', (0, _m(neck_len), _m(0.012))),
        joint('tail', 'body', (_m(0), _m(pelvis_y + pelvis_rad * 0.2), _m(pelvis_z - pelvis_len * 0.42))),
    ]
    parts = [
        part(
            'chest', 'body', 'fur',
            _fit_capsule(_m(chest_len), _m(chest_rad)),
            (_m(0), _m(chest_y), _m(chest_z)),
            (90, 0, 0),
        ),
        part(
            'pelvis', 'body', 'fur',
            _fit_capsule(_m(pelvis_len), _m(pelvis_rad)),
            (_m(0), _m(pelvis_y), _m(pelvis_z)),
            (90, 0, 0),
        ),
    ]
    if 'abdomen' in body:
        abdomen_len, abdomen_rad = body['abdomen']
        abdomen_z = ((chest_z - chest_len / 2) + (pelvis_z + pelvis_len / 2)) / 2
        abdomen_y = (chest_y + pelvis_y) / 2 + chest_rad * 0.12
        parts.append(part(
            'abdomen', 'body', 'fur',
            _fit_capsule(_m(abdomen_len), _m(abdomen_rad)),
            (_m(0), _m(abdomen_y), _m(abdomen_z)),
            (90, 0, 0),
        ))
        parts.append(part(
            'belly', 'body', 'fur',
            _fit_capsule(_m(chest_len) * 0.7, _m(chest_rad) * 0.45),
            (_m(0), _m(chest_y - chest_rad * 0.62), _m(chest_z)),
            (90, 0, 0),
        ))
    if body.get('skull') == 'wide':
        parts.extend((
            part(
                'neck', 'neck', 'fur',
                cylinder(_m(neck_tip), _m(neck_base), _m(neck_len), 12),
                (0, _m(neck_len) / 2, 0),
            ),
            part(
                'cranium', 'head', 'fur',
                _fit_capsule(_m(head_len), _m(head_rad)),
                (0, _m(head_len) * 0.15, 0),
            ),
            part(
                'cheeks', 'head', 'fur',
                cylinder(_m(head_rad) * 0.85, _m(head_rad) * 0.85, _m(head_len) * 1.15, 12),
                (0, _m(head_len) * 0.05, 0),
                (0, 0, -90),
            ),
            part(
                'jaw', 'head', 'fur',
                _fit_capsule(_m(snout_len) * 0.85, _m(snout_rad) * 0.42),
                (0, _m(head_len) * 0.35, _m(snout_rad) * 0.7),
            ),
            part(
                'snout', 'head', 'fur',
                cone(max(0.012, _m(snout_rad)), _m(snout_len), 10),
                (0, _m(head_len) * 0.45 + _m(snout_len) * 0.35, _m(0.015)),
            ),
        ))
    else:
        parts.extend((
            part(
                'neck', 'neck', 'fur',
                cylinder(_m(neck_tip), _m(neck_base), _m(neck_len), 10),
                (0, _m(neck_len) / 2, 0),
            ),
            part(
                'cranium', 'head', 'fur',
                _fit_capsule(_m(head_len), _m(head_rad)),
                (0, 0, _m(head_len) * 0.32),
                (90, 0, 0),
            ),
            part(
                'jaw', 'head', 'fur',
                _fit_capsule(_m(head_len) * 0.62, _m(head_rad) * 0.45),
                (0, -_m(head_rad) * 0.55, _m(head_len) * 0.28),
                (90, 0, 0),
            ),
            part(
                'snout', 'head', 'fur',
                cone(max(0.012, _m(snout_rad)), _m(snout_len), 8),
                (0, -_m(head_rad) * 0.15, _m(head_len) * 0.32 + _m(snout_len) * 0.45),
                (90, 0, 0),
            ),
        ))
    for label, side, kind, z_anchor in (
        ('FL', -1, 'front', chest_z + chest_len * 0.12),
        ('FR', 1, 'front', chest_z + chest_len * 0.12),
        ('BL', -1, 'hind', pelvis_z),
        ('BR', 1, 'hind', pelvis_z),
    ):
        drop = -sum(segment[0] for segment in body[kind])
        origin = (side * _m(body['stance']), _m(drop), _m(z_anchor))
        _limb(joints, parts, label, side, origin, body[kind], _m(body['leg']), spec['hooves'])
    wide = body.get('skull') == 'wide'
    for side, mark in ((-1, 'L'), (1, 'R')):
        if wide:
            parts.append(part(
                f'eye{mark}', 'head', 'socket',
                sphere(max(0.012, _m(head_rad) * 0.22), 8, 6),
                (side * _m(head_rad) * 0.72, _m(head_len) * 0.42, -_m(head_rad) * 0.05),
            ))
            parts.append(part(
                f'ear{mark}', 'head', 'fur',
                cone(max(0.012, _m(ear_rad)), _m(ear_len), 4),
                (
                    side * _m(head_len) * 0.28,
                    math.cos(math.radians(neck_pitch)) * _m(head_rad) * 0.4,
                    -math.sin(math.radians(neck_pitch)) * (_m(head_rad) + _m(ear_len) * 0.15),
                ),
                (-neck_pitch, 0, 8 * side),
            ))
        else:
            parts.append(part(
                f'eye{mark}', 'head', 'socket',
                sphere(max(0.012, _m(head_rad) * 0.22), 6, 5),
                (side * _m(head_rad) * 0.55, _m(head_rad) * 0.15, _m(head_len) * 0.28),
            ))
            parts.append(part(
                f'ear{mark}', 'head', 'fur',
                cone(max(0.012, _m(ear_rad)), max(0.04, _m(ear_len)), 6),
                (side * _m(head_rad) * 0.7, _m(head_rad) * 0.85, -_m(head_len) * 0.05),
                (-18, 0, 38 * side),
            ))
    tail_len, tail_rad, tail_droop, tail_count = body['tail']
    _tail(
        parts, _m(tail_len), _m(tail_rad), tail_droop, tail_count,
        body.get('tail_hang', 10.0), body.get('tail_taper', 0.1),
    )
    if body['mane']:
        _mane(parts, _m(neck_len), body['mane'])
    if spec['antlers']:
        for side, mark in ((-1, 'L'), (1, 'R')):
            parts.append(part(
                f'antler{mark}', 'head', 'bone',
                cone(max(0.012, _m(0.02)), _m(body['antler']), 5),
                (side * _m(head_rad) * 0.45, _m(head_rad) + _m(body['antler']) * 0.35, -_m(head_len) * 0.02),
                (-8, 0, 24 * side),
            ))
    if spec['tusks']:
        for side, mark in ((-1, 'L'), (1, 'R')):
            parts.append(part(
                f'tusk{mark}', 'head', 'bone',
                cone(max(0.012, _m(snout_rad) * 0.28), _m(snout_len) * 0.55, 5),
                (side * _m(snout_rad) * 0.7, -_m(head_rad) * 0.35, _m(head_len) * 0.4),
                (70, 0, 12 * side),
            ))
    return assemble(species_id, seed, rng, name, materials, joints, parts)
