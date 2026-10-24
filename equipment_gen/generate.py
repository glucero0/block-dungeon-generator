"""Build one held item from a kind, a seed, and a tier."""

from blk_dungeon_gen.fire import flame
from blk_dungeon_gen.seeding import sub_rng

from .materials import item_name, take
from .parts import add_grip, blade, box, cone, cylinder, lathe, num, part, ring, shield_face, sphere, torus, tube, vec
from .schema import COMBAT_KINDS, KINDS, LEFT_HAND, validate

# range, arc, damage, attack interval. Tier scales damage and reach a little.
_BASE = {
    'dagger': (2.2, 1.05, 9, 0.34),
    'sword': (3.8, 0.95, 16, 0.48),
    'mace': (3.2, 0.9, 18, 0.52),
    'axe': (3.4, 1.05, 20, 0.56),
    'hammer': (3.2, 0.8, 22, 0.6),
    'spear': (5.2, 0.5, 14, 0.5),
    'bow': (14.0, 0.2, 12, 0.85),
}


def _combat(kind, tier, rng):
    reach, arc, damage, interval = _BASE[kind]
    jitter = 0.97 + rng.random() * 0.06
    scale = 1 + (tier - 1) * 0.06
    return {
        'range': num(reach * (1 + (tier - 1) * 0.025)),
        'arcRadians': num(arc),
        'damage': num(damage * jitter * scale),
        'attackInterval': num(max(0.25, interval - (tier - 1) * 0.02)),
    }


def _finish(kind, seed, tier, name, parts, materials, rng, grip):
    hand = 'left' if kind in LEFT_HAND else 'right'
    item = {
        'version': 1,
        'kind': kind,
        'id': kind,
        'name': name,
        'seed': seed,
        'hand': hand,
        'parent': f'{hand}HandSocket',
        'castShadow': False,
        'materials': materials,
        'parts': parts,
        'grip': {
            'restRotation': {'x': num(grip[0]), 'y': num(grip[1]), 'z': num(grip[2]), 'unit': 'degrees'},
        },
        'options': {'kind': kind, 'seed': seed, 'tier': tier},
    }
    if kind in COMBAT_KINDS:
        item['combat'] = _combat(kind, tier, rng)
    return validate(item)


def _choice(rng):
    wood = rng.choice(('oak', 'ash'))
    metal = rng.choice(('iron', 'bronze', 'steel'))
    return wood, metal


def _open_materials(wood, metal, *extra):
    materials = {}
    take(materials, wood)
    take(materials, metal)
    for name in extra:
        take(materials, name)
    return materials


def build_blade_weapon(seed, tier, kind):
    rng = sub_rng(seed, kind)
    wood, metal = _choice(rng)
    motif = rng.choice(('bar', 'winged', 'disc'))
    dagger = kind == 'dagger'
    grip_len = (0.21 if dagger else 0.36) + rng.random() * (0.03 if dagger else 0.04)
    blade_len = (0.44 if dagger else 1.32) + rng.random() * (0.12 if dagger else 0.4)
    radius = 0.03 if dagger else 0.036
    width = (0.064 if dagger else 0.096) + rng.random() * (0.016 if dagger else 0.032)
    materials = _open_materials(wood, metal)
    parts = []
    top = add_grip(parts, materials, rng, grip_len, radius, 0, wood, metal, tier)
    guard_w = (0.2 if dagger else 0.4) + rng.random() * (0.04 if dagger else 0.12)
    if motif == 'bar':
        parts.append(part('guard', metal, box(guard_w, 0.032, 0.072), (0, top, 0)))
    elif motif == 'winged':
        parts.append(part('guard', metal, box(guard_w * 0.72, 0.028, 0.06), (0, top, 0)))
        span = 0.14 if dagger else 0.2
        parts.append(part('quillonL', metal, cylinder(0.016, 0.008, span, 8), (-span * 0.4, top + 0.02, 0), (0, 0, 66)))
        parts.append(part('quillonR', metal, cylinder(0.016, 0.008, span, 8), (span * 0.4, top + 0.02, 0), (0, 0, -66)))
    else:
        disc = 0.06 if dagger else 0.092
        parts.append(part('guard', metal, cylinder(disc, disc, 0.028, 14), (0, top, 0)))
    fuller = 0.4 if kind == 'sword' and tier >= 2 else 0
    thickness = 0.02 if dagger else 0.032
    parts.append(part(
        'blade', metal,
        blade(blade_len, width, 0.008, thickness, fuller, 8),
        (0, top + blade_len / 2 + 0.016, 0),
    ))
    return _finish(kind, seed, tier, item_name(wood, metal, motif, kind), parts, materials, rng, (15, 0, 25))


def build_mace(seed, tier):
    rng = sub_rng(seed, 'mace')
    wood, metal = _choice(rng)
    motif = rng.choice(('flanged', 'spiked', 'knobbed'))
    grip_len = 0.92 + rng.random() * 0.16
    head_r = 0.144 + rng.random() * 0.036
    materials = _open_materials(wood, metal, 'rust')
    parts = []
    top = add_grip(parts, materials, rng, grip_len, 0.04, 0, wood, metal, tier)
    head_y = top + head_r * 0.3
    parts.append(part('head', 'rust', sphere(head_r, 12, 10), (0, head_y, 0)))
    if motif == 'flanged':
        parts.append(part('flangeA', metal, box(head_r * 3.2, head_r * 0.4, head_r * 0.6), (0, head_y, 0)))
        parts.append(part('flangeB', metal, box(head_r * 0.4, head_r * 2.4, head_r * 0.6), (0, head_y, 0)))
    elif motif == 'spiked':
        spike_h = max(0.12, head_r * 1.1)
        places = (
            ('spikeTop', (0, head_y + head_r * 0.7, 0), None),
            ('spikeR', (head_r * 0.85, head_y, 0), (0, 0, -90)),
            ('spikeL', (-head_r * 0.85, head_y, 0), (0, 0, 90)),
            ('spikeF', (0, head_y, head_r * 0.85), (90, 0, 0)),
            ('spikeB', (0, head_y, -head_r * 0.85), (-90, 0, 0)),
        )
        for name, position, rotation in places:
            parts.append(part(name, metal, cone(0.026, spike_h, 6), position, rotation))
    else:
        parts.append(ring('band', metal, head_r * 0.9, 0.016, head_y, materials))
    return _finish('mace', seed, tier, item_name(wood, metal, motif, 'mace'), parts, materials, rng, (15, 0, 25))


def build_axe(seed, tier):
    rng = sub_rng(seed, 'axe')
    wood, metal = _choice(rng)
    motif = rng.choice(('single', 'double'))
    grip_len = 1.0 + rng.random() * 0.16
    bit_len = 0.24 + rng.random() * 0.07
    bit_tall = 0.3 + rng.random() * 0.08
    materials = _open_materials(wood, metal)
    parts = []
    top = add_grip(parts, materials, rng, grip_len, 0.038, 0, wood, metal, tier)
    head_y = top + 0.02
    parts.append(part('eye', metal, box(0.096, 0.18, 0.096), (0, head_y, 0)))
    # Length runs along local Y. A -90 degree roll lays that length out along +X.
    parts.append(part(
        'bit', metal, blade(bit_len, bit_tall, 0.024, 0.04, 0, 4),
        (0.048 + bit_len / 2, head_y, 0), (0, 0, -90),
    ))
    if motif == 'double':
        parts.append(part(
            'bitB', metal, blade(bit_len, bit_tall, 0.024, 0.04, 0, 4),
            (-0.048 - bit_len / 2, head_y, 0), (0, 0, 90),
        ))
    return _finish('axe', seed, tier, item_name(wood, metal, motif, 'axe'), parts, materials, rng, (15, 0, 25))


def build_hammer(seed, tier):
    rng = sub_rng(seed, 'hammer')
    wood, metal = _choice(rng)
    motif = rng.choice(('war', 'mallet'))
    grip_len = 0.96 + rng.random() * 0.16
    materials = _open_materials(wood, metal, 'rust')
    parts = []
    top = add_grip(parts, materials, rng, grip_len, 0.04, 0, wood, metal, tier)
    head_y = top + 0.04
    if motif == 'mallet':
        parts.append(part('head', 'rust', box(0.48, 0.22, 0.22), (0, head_y, 0)))
        parts.append(part('bandL', metal, box(0.056, 0.24, 0.24), (-0.14, head_y, 0)))
        parts.append(part('bandR', metal, box(0.056, 0.24, 0.24), (0.14, head_y, 0)))
    else:
        parts.append(part('head', 'rust', box(0.32, 0.16, 0.16), (0, head_y, 0)))
        parts.append(part('face', metal, box(0.08, 0.2, 0.2), (0.18, head_y, 0)))
        parts.append(part('spike', metal, cone(0.032, 0.24, 6), (-0.26, head_y, 0), (0, 0, 90)))
    return _finish('hammer', seed, tier, item_name(wood, metal, motif, 'hammer'), parts, materials, rng, (15, 0, 25))


def build_spear(seed, tier):
    rng = sub_rng(seed, 'spear')
    wood, metal = _choice(rng)
    motif = rng.choice(('leaf', 'spike'))
    shaft_len = 3.0 + rng.random() * 0.32
    head_len = (0.52 if motif == 'leaf' else 0.32) + rng.random() * (0.16 if motif == 'leaf' else 0.1)
    shaft_r = 0.032
    materials = _open_materials(wood, metal, 'leather')
    parts = []
    parts.append(part('shaft', wood, cylinder(shaft_r * 0.85, shaft_r, shaft_len, 10), (0, shaft_len / 2, 0)))
    parts.append(ring('grip', 'leather', shaft_r * 1.45, 0.01, shaft_len * 0.32, materials))
    if tier >= 2:
        parts.append(ring('wrap1', 'cord', shaft_r * 1.55, 0.008, shaft_len * 0.4, materials))
    parts.append(part('butt', metal, cylinder(shaft_r * 1.15, shaft_r * 0.7, 0.08, 10), (0, 0.04, 0)))
    if tier >= 3:
        parts.append(part('pommelCap', metal, sphere(shaft_r * 1.25, 8, 6), (0, -0.016, 0)))
    parts.append(part('collar', metal, cylinder(shaft_r * 1.45, shaft_r * 1.15, 0.1, 10), (0, shaft_len - 0.04, 0)))
    if motif == 'leaf':
        parts.append(part(
            'head', metal,
            blade(head_len, 0.104, 0.008, 0.024, 0.3 if tier >= 2 else 0, 6),
            (0, shaft_len + head_len / 2 - 0.04, 0),
        ))
    else:
        parts.append(part('head', metal, cone(0.032, head_len, 8), (0, shaft_len + head_len / 2 - 0.03, 0)))
    if tier >= 5:
        parts.append(ring('inlay', 'gold', shaft_r * 1.8, 0.008, shaft_len - 0.14, materials))
    return _finish('spear', seed, tier, item_name(wood, metal, motif, 'spear'), parts, materials, rng, (15, 0, 20))


def build_shield(seed, tier):
    rng = sub_rng(seed, 'shield')
    wood, metal = _choice(rng)
    outline = rng.choice(('round', 'heater', 'tower'))
    if outline == 'round':
        width = 1.16 + rng.random() * 0.52
        height = width
    elif outline == 'heater':
        width = 1.0 + rng.random() * 0.28
        height = 1.4 + rng.random() * 0.32
    else:
        width = 1.0 + rng.random() * 0.2
        height = 1.64 + rng.random() * 0.2
    thick = 0.08
    materials = _open_materials(wood, metal, 'leather')
    parts = [part('board', wood, shield_face(outline, width, height, thick), (0, 0, 0))]
    planks = 4 if outline == 'tower' else 3
    for index in range(planks):
        x = (index - (planks - 1) / 2) * (width * 0.62 / (planks - 1))
        parts.append(part(f'plank{index + 1}', wood, box(max(0.04, width * 0.07), height * 0.7, 0.016), (x, 0, thick / 2)))
    boss_r = 0.104 + (0.024 if tier >= 3 else 0)
    parts.append(part('boss', metal, lathe((
        (0.024, 0),
        (boss_r * 0.7, boss_r * 0.28),
        (boss_r, boss_r * 0.55),
        (boss_r * 0.3, boss_r * 0.82),
        (0.02, boss_r),
    ), 12), (0, 0, thick / 2), (90, 0, 0)))
    if outline == 'round':
        parts.append(part('rim', metal, torus(width / 2 - 0.028, 0.024, 8, 24), (0, 0, 0)))
    else:
        parts.append(part('rimTop', metal, box(width * 0.9, 0.04, thick + 0.012), (0, height / 2 - 0.024, 0)))
        bottom = width * (0.5 if outline == 'heater' else 0.9)
        parts.append(part('rimBottom', metal, box(bottom, 0.04, thick + 0.012), (0, -height / 2 + 0.032, 0)))
        parts.append(part('rimL', metal, box(0.036, height * 0.84, thick + 0.012), (-width / 2 + 0.024, 0, 0)))
        parts.append(part('rimR', metal, box(0.036, height * 0.84, thick + 0.012), (width / 2 - 0.024, 0, 0)))
    parts.append(part('grip', 'leather', cylinder(0.028, 0.028, max(0.24, width * 0.32), 8), (0, 0, -thick / 2 - 0.036), (0, 0, 90)))
    if tier >= 2:
        span = width * 0.26
        for index, (x, y) in enumerate(((span, span * 0.15), (-span, span * 0.15), (span * 0.5, -span * 0.45), (-span * 0.5, -span * 0.45))):
            parts.append(part(f'rivet{index + 1}', metal, sphere(0.024, 6, 5), (x, y, thick / 2 + 0.016)))
    if tier >= 5:
        parts.append(part('inlay', 'gold', torus(boss_r * 1.4, 0.01, 6, 16), (0, 0, thick / 2 + boss_r * 0.3)))
        take(materials, 'gold')
    return _finish('shield', seed, tier, item_name(wood, metal, outline, 'shield'), parts, materials, rng, (0, -12, 8))


def build_bow(seed, tier):
    rng = sub_rng(seed, 'bow')
    wood, metal = _choice(rng)
    long = rng.random() < 0.5
    motif = 'long' if long else 'short'
    reach = (1.48 if long else 1.24) + rng.random() * 0.07
    brace = 0.3 + rng.random() * 0.08
    materials = _open_materials(wood, metal, 'leather', 'cloth')
    parts = [part('stave', wood, tube((0, reach, brace), (0, 0, -brace * 0.6), (0, -reach, brace), 0.03, 20, 8), (0, 0, 0))]
    parts.append(part('grip', 'leather', cylinder(0.044, 0.04, 0.28, 10), (0, 0, 0)))
    parts.append(ring('wrap1', 'cord', 0.056, 0.008, 0.07, materials))
    if tier >= 2:
        parts.append(ring('wrap2', 'cord', 0.056, 0.008, -0.07, materials))
    parts.append(part('string', metal, tube((0, reach, brace), (0, 0, brace), (0, -reach, brace), 0.007, 8, 5), (0, 0, 0)))
    arrow_len = 1.16
    center_z = brace - arrow_len / 2
    parts.append(part('arrowShaft', wood, cylinder(0.012, 0.012, arrow_len, 8), (0, 0.04, center_z), (-90, 0, 0)))
    parts.append(part('arrowHead', metal, cone(0.026, 0.14, 6), (0, 0.04, center_z - arrow_len / 2 - 0.03), (-90, 0, 0)))
    parts.append(part('vaneA', 'cloth', box(0.09, 0.016, 0.16), (0, 0.04, brace - 0.1)))
    parts.append(part('vaneB', 'cloth', box(0.016, 0.09, 0.16), (0, 0.04, brace - 0.1)))
    if tier >= 3:
        parts.append(ring('band', metal, 0.04, 0.007, 0, materials))
    if tier >= 5:
        parts.append(ring('inlay', 'gold', 0.064, 0.007, 0.14, materials))
    return _finish('bow', seed, tier, item_name(wood, metal, motif, 'bow'), parts, materials, rng, (0, 0, 0))


def build_torch(seed, tier):
    rng = sub_rng(seed, 'torch')
    wood, metal = _choice(rng)
    motif = rng.choice(('cup', 'cage', 'brand'))
    shaft_len = 0.5 + rng.random() * 0.06
    radius = 0.02 + rng.random() * 0.004
    flare = 0.048 + rng.random() * 0.01
    materials = _open_materials(wood, metal)
    parts = [part('shaft', wood, lathe((
        (radius * 0.85, 0),
        (radius * 1.08, shaft_len * 0.18),
        (radius * 0.9, shaft_len * 0.55),
        (radius * 1.15, shaft_len * 0.86),
        (radius * 1.3, shaft_len),
    ), 12), (0, 0, 0))]
    wraps = 3 if motif == 'brand' else 1
    if tier >= 2 and wraps < 3:
        wraps += 1
    for index in range(wraps):
        along = (index + 1) / (wraps + 1)
        parts.append(ring(f'wrap{index + 1}', 'cord', radius * 1.28, max(0.004, radius * 0.24), shaft_len * along, materials))
    if motif == 'brand':
        take(materials, 'cloth')
        parts.append(part('cloth', 'cloth', cylinder(radius * 1.5, radius * 1.35, 0.08, 10), (0, shaft_len * 0.7, 0)))
    cup_h = 0.1
    cup_y = shaft_len + cup_h * 0.28
    parts.append(part('cup', metal, cylinder(flare, flare * 0.62, cup_h, 12), (0, cup_y, 0)))
    if tier >= 3:
        parts.append(ring('lip', metal, flare * 0.98, 0.005, cup_y + cup_h * 0.4, materials))
    if motif == 'cage':
        bar_h = cup_h + 0.05
        for index, (x, z) in enumerate(((1, 0), (-1, 0), (0, 1), (0, -1))):
            parts.append(part(
                f'bar{index + 1}', metal, cylinder(0.0045, 0.0045, bar_h, 5),
                (x * flare * 0.82, cup_y + 0.015, z * flare * 0.82),
            ))
        parts.append(ring('cageRing', metal, flare, 0.004, cup_y + cup_h * 0.5, materials))
    if tier >= 5:
        parts.append(ring('inlay', 'gold', radius * 1.45, 0.0035, shaft_len * 0.42, materials))
    socket = {'name': 'TorchTipSocket', 'type': 'group', 'position': vec(0, cup_y + cup_h / 2, 0)}
    socket.update(flame())
    parts.append(socket)
    return _finish('torch', seed, tier, item_name(wood, metal, motif, 'torch'), parts, materials, rng, (-15, 0, -10))


_BUILDERS = {
    'sword': lambda seed, tier: build_blade_weapon(seed, tier, 'sword'),
    'dagger': lambda seed, tier: build_blade_weapon(seed, tier, 'dagger'),
    'mace': build_mace,
    'axe': build_axe,
    'hammer': build_hammer,
    'spear': build_spear,
    'shield': build_shield,
    'bow': build_bow,
    'torch': build_torch,
}


def generate_item(kind, seed=1, tier=1):
    """One recipe. The same kind, seed, and tier always return the same dict."""
    if kind not in KINDS:
        raise ValueError(f'unknown kind {kind}')
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError('seed must be zero or greater')
    if isinstance(tier, bool) or not isinstance(tier, int) or not 1 <= tier <= 5:
        raise ValueError('tier must be from 1 to 5')
    return _BUILDERS[kind](seed, tier)
