"""Theme-driven clutter for chambers: urns, caskets, barrels, rubble, and the like.

Each prop is `{type, x, z, rotationY, scale}`. `rotationY` is a yaw in radians where
0 faces +Z. Wall props face into the room. Props keep clear of doors, the walkway
between doors, spawns, the chest, and the sconce, so a room can always be crossed.
"""

import math
from collections import namedtuple

from .spatial import candidates, clearance, door_distance, segment_distance

# mode: 'wall' hugs a wall, 'free' stands in the open, 'cluster' is a small pile.
# spacing: how far apart two props of this kind sit, in metres.
PropKind = namedtuple('PropKind', 'type weight mode spacing scale')

PROPS = {
    'stone': (
        PropKind('urn', 4, 'wall', 1.3, (0.8, 1.2)),
        PropKind('casket', 3, 'wall', 2.6, (0.9, 1.1)),
        PropKind('broken-pillar', 2, 'free', 2.8, (0.8, 1.2)),
        PropKind('rubble', 3, 'cluster', 1.8, (0.7, 1.3)),
    ),
    'wood': (
        PropKind('barrel', 4, 'wall', 1.4, (0.85, 1.15)),
        PropKind('crate', 4, 'wall', 1.4, (0.8, 1.2)),
        PropKind('shelf', 2, 'wall', 2.4, (0.9, 1.1)),
        PropKind('plank-pile', 2, 'cluster', 1.8, (0.7, 1.3)),
    ),
    'cave': (
        PropKind('stalagmite', 4, 'free', 2.2, (0.7, 1.4)),
        PropKind('bone-pile', 2, 'cluster', 1.8, (0.7, 1.2)),
        PropKind('rubble', 3, 'cluster', 1.8, (0.7, 1.3)),
    ),
}

AREA_PER_PROP = 80.0
MAX_PROPS = 12
WALL_INSET = 0.9
WALL_STEP = 1.5
DOOR_CLEAR = 3.0
WALL_WALK_CLEAR = 1.2
FREE_WALK_CLEAR = 2.0
FREE_WALL_CLEAR = 2.2
CLUSTER_PIECE_SPACING = 0.6


def _target(block, clutter, rng):
    """How many props to place. Fractions round up at random, so 0 stays 0."""
    base = block.rect.w * block.rect.d / AREA_PER_PROP * clutter
    return max(0, min(MAX_PROPS, int(base + rng.random())))


def _wall_points(rect):
    """Spots just off each wall, each with its inward normal."""
    points = []
    x = rect.x + 1.6
    while x <= rect.x + rect.w - 1.6 + 1e-6:
        points.append((x, rect.z + WALL_INSET, 0, 1))
        points.append((x, rect.z + rect.d - WALL_INSET, 0, -1))
        x += WALL_STEP
    z = rect.z + 1.6
    while z <= rect.z + rect.d - 1.6 + 1e-6:
        points.append((rect.x + WALL_INSET, z, 1, 0))
        points.append((rect.x + rect.w - WALL_INSET, z, -1, 0))
        z += WALL_STEP
    return points


def _walkways(rect, doors):
    """Lines between the inner side of each door that props must not block."""
    cx = rect.x + rect.w / 2
    cz = rect.z + rect.d / 2
    ends = []
    for door in doors:
        mx = (door['a'][0] + door['b'][0]) / 2
        mz = (door['a'][1] + door['b'][1]) / 2
        dx = cx - mx
        dz = cz - mz
        length = math.hypot(dx, dz) or 1
        ends.append((mx + dx / length * 2.5, mz + dz / length * 2.5))
    if not ends:
        return []
    if len(ends) == 1:
        return [(ends[0], (cx, cz))]
    return [(a, b) for index, a in enumerate(ends) for b in ends[index + 1:]]


def _fits(x, z, mode, spacing, rect, doors, walkways, avoid, placed):
    if mode == 'wall':
        if clearance(x, z, rect) < WALL_INSET - 0.05:
            return False
        walk_clear = WALL_WALK_CLEAR
    else:
        if clearance(x, z, rect) < FREE_WALL_CLEAR:
            return False
        walk_clear = FREE_WALK_CLEAR
    if door_distance(x, z, doors) < DOOR_CLEAR:
        return False
    for a, b in walkways:
        if segment_distance(x, z, a[0], a[1], b[0], b[1]) < walk_clear:
            return False
    for ax, az, radius in avoid:
        if math.hypot(x - ax, z - az) < radius:
            return False
    for ox, oz, other in placed:
        if math.hypot(x - ox, z - oz) < min(spacing, other):
            return False
    return True


def _record(kind, x, z, yaw, rng):
    lo, hi = kind.scale
    return {
        'type': kind.type,
        'x': round(x, 4),
        'z': round(z, 4),
        'rotationY': round(yaw, 4),
        'scale': round(rng.uniform(lo, hi), 3),
    }


def place_props(block, theme, doors, avoid, rng, clutter):
    """Return the props for one chamber.

    `doors` are every opening on the room (add the arch for the antechamber).
    `avoid` is a list of `(x, z, radius)` points already taken by spawns, the
    chest, and the sconce.
    """
    kinds = PROPS.get(theme)
    if not kinds or block.kind != 'chamber':
        return []
    target = _target(block, clutter, rng)
    if target <= 0:
        return []
    rect = block.rect
    walkways = _walkways(rect, doors)
    pools = {
        'wall': _wall_points(rect),
        'free': [(x, z, None, None) for x, z in candidates(rect, 2)],
    }
    rng.shuffle(pools['wall'])
    rng.shuffle(pools['free'])
    weights = [kind.weight for kind in kinds]
    placed = []
    props = []
    attempts = 0
    while len(props) < target and attempts < target * 8:
        attempts += 1
        kind = rng.choices(kinds, weights)[0]
        pool = pools['wall' if kind.mode == 'wall' else 'free']
        spot = None
        for index, (x, z, nx, nz) in enumerate(pool):
            if _fits(x, z, kind.mode, kind.spacing, rect, doors, walkways, avoid, placed):
                spot = pool.pop(index)
                break
        if spot is None:
            continue
        x, z, nx, nz = spot
        yaw = math.atan2(nx, nz) if nx is not None else rng.uniform(0, math.pi * 2)
        props.append(_record(kind, x, z, yaw, rng))
        placed.append((x, z, kind.spacing))
        if kind.mode != 'cluster':
            continue
        for _ in range(rng.randint(1, 2)):
            angle = rng.uniform(0, math.pi * 2)
            reach = rng.uniform(0.7, 1.5)
            px = x + math.cos(angle) * reach
            pz = z + math.sin(angle) * reach
            if _fits(px, pz, 'free', CLUSTER_PIECE_SPACING, rect, doors, walkways, avoid, placed):
                props.append(_record(kind, px, pz, rng.uniform(0, math.pi * 2), rng))
                placed.append((px, pz, CLUSTER_PIECE_SPACING))
    return props
