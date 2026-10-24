"""Humanoids on the skeletal warrior joint tree.

Joint spacing is buildMesh in Harper's Row src/skeleton.js, multiplied by one
scale. Shoulder, elbow, wrist, hip, and knee stay that far apart for every seed.
"""

from blk_dungeon_gen.seeding import sub_rng

from .finish import assemble
from .materials import HAIR_TITLE, TONE_TITLE, paint
from .shapes import box, cone, joint, long_bone, part, sphere, torus
from .species import SPECIES


def _at(scale, x, y, z):
    return (x * scale, y * scale, z * scale)


def build_humanoid(species_id, seed):
    spec = SPECIES[species_id]
    rng = sub_rng(seed, species_id)
    scale = spec['scale']
    bulk = spec['bulk']
    tone = spec['tones'][seed % len(spec['tones'])]
    style = None
    garment = spec['clothes']
    if spec['hair'] == 'varied':
        style = ('cap', 'long', 'hood')[rng.randrange(3)]
    if garment == 'town':
        garment = 'robe' if rng.random() < 0.35 else 'tunic'

    materials = {}
    body = 'bone'
    eye = 'ember'
    if spec['flesh']:
        hair_tone = spec['hair_tones'][seed % len(spec['hair_tones'])]
        cloth_tone = spec['cloth_tones'][seed % len(spec['cloth_tones'])]
        paint(materials, 'skin', tone)
        paint(materials, 'hair', hair_tone)
        paint(materials, 'cloth', cloth_tone)
        paint(materials, 'leather', 'leather')
        paint(materials, 'socket', 'socket')
        if spec['tusks']:
            paint(materials, 'bone', 'bone')
        body = 'skin'
        eye = 'socket'
        name = f'{TONE_TITLE[tone]} {HAIR_TITLE[style]} {spec["title"]}'
    else:
        paint(materials, 'bone', tone)
        paint(materials, 'socket', 'socket')
        paint(materials, 'ember', 'ember')
        paint(materials, 'iron', 'iron')
        name = f'{TONE_TITLE[tone]} {spec["title"]}'

    def wide(value):
        return value * scale * bulk

    def span(value):
        return value * scale

    def bone(total, radius):
        return long_bone(span(total), wide(radius))

    hunch = (spec['hunch'], 0, 0) if spec['hunch'] else None
    joints = [
        joint('fall', None, (0, 0, 0)),
        joint('spine', 'fall', _at(scale, 0, 3.05, 0), hunch),
        joint('skull', 'spine', _at(scale, 0, 1.16, 0.03)),
    ]
    for side, label in ((1, 'R'), (-1, 'L')):
        arm = f'SkeletonArm_{label}'
        fore = f'Forearm_{label}'
        wrist = f'WristJoint_{label}'
        joints.append(joint(arm, 'spine', _at(scale, 0.48 * side, 0.85, 0)))
        joints.append(joint(fore, arm, _at(scale, 0, -0.98, 0)))
        joints.append(joint(wrist, fore, _at(scale, 0, -0.86, 0)))
        joints.append(joint(f'HandSocket_{label}', wrist, _at(scale, 0, -0.02, 0.06)))
    for side, label in ((-1, 'L'), (1, 'R')):
        hip = f'Hip_{label}'
        joints.append(joint(hip, 'fall', _at(scale, 0.18 * side, 2.9, 0)))
        joints.append(joint(f'Knee_{label}', hip, _at(scale, 0, -1.28, 0)))

    parts = [
        part('pelvis', 'fall', body, box(wide(0.62), span(0.22), wide(0.32)), _at(scale, 0, 2.95, 0)),
        part('column', 'spine', body, box(wide(0.22), span(0.85), wide(0.2)), _at(scale, 0, 0.45, 0)),
        part('neck', 'spine', body, bone(0.42, 0.07), _at(scale, 0, 0.98, 0.03)),
        part('cranium', 'skull', body, sphere(wide(0.26), 8, 6), _at(scale, 0, 0.18, -0.02)),
        part('jaw', 'skull', body, box(wide(0.22), span(0.08), wide(0.16)), _at(scale, 0, -0.08, 0.08)),
    ]
    if not spec['flesh']:
        for index in range(4):
            parts.append(part(
                f'rib{index}', 'spine', 'bone',
                torus(span(0.38), wide(0.035)),
                _at(scale, 0, 0.28 + index * 0.18, 0.04),
                (90, 0, 0),
            ))
        parts.append(part(
            'cage', 'spine', 'socket',
            box(wide(0.5), span(0.36), wide(0.08)),
            _at(scale, 0, 0.55, 0.12),
        ))
        parts.append(part(
            'scrap', 'SkeletonArm_R', 'iron',
            box(wide(0.24), span(0.1), wide(0.16)),
            _at(scale, 0.02, -0.2, 0.06),
        ))
    for side, label in ((-1, 'L'), (1, 'R')):
        parts.append(part(f'upper{label}', f'SkeletonArm_{label}', body, bone(0.95, 0.07), _at(scale, 0, -0.5, 0)))
        parts.append(part(f'fore{label}', f'Forearm_{label}', body, bone(0.85, 0.055), _at(scale, 0, -0.42, 0)))
        parts.append(part(
            f'hand{label}', f'WristJoint_{label}', body,
            box(wide(0.16), span(0.14), wide(0.16)),
            (0, 0, 0),
        ))
        parts.append(part(
            f'thumb{label}', f'WristJoint_{label}', body,
            box(wide(0.06), span(0.1), wide(0.06)),
            _at(scale, 0.08 * side, 0.02, 0.08),
        ))
        parts.append(part(f'thigh{label}', f'Hip_{label}', body, bone(1.25, 0.08), _at(scale, 0, -0.65, 0)))
        parts.append(part(f'shin{label}', f'Knee_{label}', body, bone(1.2, 0.06), _at(scale, 0, -0.6, 0)))
        parts.append(part(
            f'eye{label}', 'skull', eye,
            sphere(max(0.014, span(0.02)), 6, 5),
            _at(scale, 0.1 * side, 0.08, 0.14),
        ))
    if spec['flesh']:
        _clothes(parts, scale, bulk, garment, style)
        _features(parts, scale, bulk, spec, style)
    return assemble(species_id, seed, rng, name, materials, joints, parts)


def _clothes(parts, scale, bulk, garment, style):
    def wide(value):
        return value * scale * bulk

    def span(value):
        return value * scale

    if garment == 'robe':
        parts.append(part(
            'robe', 'spine', 'cloth',
            box(wide(0.58), span(1.35), wide(0.36)),
            _at(scale, 0, 0.05, 0.02),
        ))
    elif garment == 'rags':
        parts.append(part(
            'rags', 'spine', 'cloth',
            box(wide(0.5), span(0.62), wide(0.3)),
            _at(scale, 0.02, 0.28, 0.04),
            (0, 0, 8),
        ))
    else:
        parts.append(part(
            'tunic', 'spine', 'cloth',
            box(wide(0.5), span(0.7), wide(0.32)),
            _at(scale, 0, 0.32, 0.02),
        ))
        for label in ('L', 'R'):
            parts.append(part(
                f'trouser{label}', f'Hip_{label}', 'cloth',
                box(wide(0.2), span(0.7), wide(0.22)),
                _at(scale, 0, -0.4, 0),
            ))
    parts.append(part(
        'belt', 'spine', 'leather',
        box(wide(0.56), span(0.08), wide(0.34)),
        _at(scale, 0, 0.02, 0.02),
    ))
    for label in ('L', 'R'):
        parts.append(part(
            f'boot{label}', f'Knee_{label}', 'leather',
            box(wide(0.16), span(0.22), wide(0.28)),
            _at(scale, 0, -1.02, 0.04),
        ))
    if style == 'hood':
        parts.append(part(
            'hood', 'skull', 'cloth',
            sphere(wide(0.32), 8, 6),
            _at(scale, 0, 0.16, -0.04),
        ))


def _features(parts, scale, bulk, spec, style):
    def wide(value):
        return value * scale * bulk

    def span(value):
        return value * scale

    if style == 'long':
        parts.append(part(
            'hair', 'skull', 'hair',
            long_bone(span(0.7), wide(0.08)),
            _at(scale, 0, -0.05, -0.2),
            (18, 0, 0),
        ))
    else:
        parts.append(part(
            'hair', 'skull', 'hair',
            sphere(wide(0.2), 8, 6),
            _at(scale, 0, 0.32, -0.02),
        ))
    if spec['ears'] == 'large':
        for side, label in ((-1, 'L'), (1, 'R')):
            parts.append(part(
                f'ear{label}', 'skull', 'skin',
                cone(wide(0.1), span(0.32)),
                _at(scale, 0.2 * side, 0.12, 0),
                (0, 0, 70 * side),
            ))
    elif spec['ears'] == 'pointed':
        for side, label in ((-1, 'L'), (1, 'R')):
            parts.append(part(
                f'ear{label}', 'skull', 'skin',
                cone(wide(0.05), span(0.2)),
                _at(scale, 0.16 * side, 0.2, 0),
                (0, 0, 60 * side),
            ))
    if spec['tusks']:
        for side, label in ((-1, 'L'), (1, 'R')):
            parts.append(part(
                f'tusk{label}', 'skull', 'bone',
                cone(wide(0.035), span(0.16)),
                _at(scale, 0.06 * side, -0.1, 0.16),
                (80, 0, 0),
            ))
    if spec['beard']:
        parts.append(part(
            'beard', 'skull', 'hair',
            long_bone(span(0.32), wide(0.07)),
            _at(scale, 0, -0.16, 0.1),
        ))
