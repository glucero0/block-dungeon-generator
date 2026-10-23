"""Outdoor trail, arch, trees, and zone transitions.

This follows the approach built in Harper's Row `rooms.js` (`shapeAncientRuins`),
anchored to the entrance block's south edge.
"""

import math

PATH_WIDTH = 12
PATH_LENGTH = 56
COURT_DEPTH = 9
COURT_EXTRA = 16
VESTIBULE_DEPTH = 2.7
TRAIL_CLEARANCE = 3
PATH_SAMPLES = 20
CORRIDOR_HALF = (PATH_WIDTH + TRAIL_CLEARANCE) / 2
VISTA_LENGTH = 118
VISTA_STEPS = 22

DEAD_TREE_VARIANTS = (
    {'branches': 3, 'height': 4.4},
    {'branches': 5, 'height': 6.2},
    {'branches': 4, 'height': 5.0},
    {'branches': 7, 'height': 7.1},
    {'branches': 2, 'height': 1.35},
)

ZONE_LABELS = {
    'worn-trail': 'Worn Trail',
    'ancient-ruins': 'The Ancient Ruins',
    'world-hub': 'Mountain Pass',
}

DAY = {
    'clearColor': '#c5d0d6',
    'ambientLightIntensity': 0.55,
    'fog': {'color': '#c5d0d6', 'near': 28, 'far': 110, 'density': 0.009},
    'skyboxVisible': True,
}

INTERIOR = {
    'clearColor': '#000000',
    'ambientLightIntensity': 0.012,
    'fog': {'color': '#000000', 'near': 8, 'far': 20},
    'skyboxVisible': False,
}

TRAIL_DESCRIPTION = (
    'A worn dirt path ends at a weathered stone arch. Thin clouds cross a pale blue sky, '
    'and pale sun falls between dead trees on the parched ground. Beyond the pass, scrub '
    'and dead trees follow the path until a mountain range meets it.'
)

VISTA_DESCRIPTION = (
    'Scrub and dead trees follow a long dirt path away from the pass until the mountain range meets it.'
)


def _polygon(rect):
    return [
        [rect['x'], rect['z']],
        [rect['x'] + rect['w'], rect['z']],
        [rect['x'] + rect['w'], rect['z'] + rect['d']],
        [rect['x'], rect['z'] + rect['d']],
    ]


def _stamp_frame(samples):
    last = len(samples) - 1
    for index, sample in enumerate(samples):
        prev = samples[max(0, index - 1)]
        nxt = samples[min(last, index + 1)]
        tx = nxt['x'] - prev['x']
        tz = nxt['z'] - prev['z']
        length = math.hypot(tx, tz) or 1
        tx /= length
        tz /= length
        sample['tx'] = tx
        sample['tz'] = tz
        sample['nx'] = -tz
        sample['nz'] = tx
    return samples


def entrance_door_width(rect):
    return min(6.4, max(4.8, rect.w * 0.4))


def _trail_shape(rng):
    """Seed-driven bend, wobble, and length for the worn trail."""
    return {
        'bend': rng.choice((-1, 1)),
        'amp': rng.uniform(1.2, 4.0),
        'wobble': rng.uniform(0.0, 1.1),
        'phase': rng.uniform(0.0, math.pi * 2),
        'length': rng.uniform(48.0, 68.0),
    }


def _trail_samples(mid_x, z0, shape):
    samples = []
    for index in range(PATH_SAMPLES + 1):
        t = index / PATH_SAMPLES
        sway = math.sin(t * math.pi) * shape['amp'] + math.sin(t * math.pi * 2) * shape['wobble']
        samples.append({
            'x': mid_x + shape['bend'] * sway,
            'z': z0 + t * shape['length'],
            'half': PATH_WIDTH / 2 + math.sin(t * 8.4 + shape['phase']) * 0.42 + math.sin(t * 3.1 + 0.7) * 0.26,
            't': t,
        })
    return _stamp_frame(samples)


def _closest(px, pz, ax, az, bx, bz):
    abx = bx - ax
    abz = bz - az
    len2 = abx * abx + abz * abz
    t = 0 if len2 <= 0 else ((px - ax) * abx + (pz - az) * abz) / len2
    t = max(0, min(1, t))
    return ax + abx * t, az + abz * t


def _trail_distance(samples, x, z):
    best = math.inf
    for index in range(len(samples) - 1):
        a = samples[index]
        b = samples[index + 1]
        cx, cz = _closest(x, z, a['x'], a['z'], b['x'], b['z'])
        best = min(best, math.hypot(x - cx, z - cz))
    return best


def _blocks_prop(samples, x, z):
    if not samples:
        return False
    end = samples[-1]
    if _trail_distance(samples, x, z) < CORRIDOR_HALF - 0.05:
        return True
    if z >= end['z'] - 0.5 and abs(x - end['x']) < CORRIDOR_HALF:
        return True
    return False


def _point_on_trail(samples, t):
    scaled = min(0.999, max(0, t)) * (len(samples) - 1)
    index = int(math.floor(scaled))
    frac = scaled - index
    a = samples[index]
    b = samples[min(len(samples) - 1, index + 1)]
    return {
        'x': a['x'] + (b['x'] - a['x']) * frac,
        'z': a['z'] + (b['z'] - a['z']) * frac,
        'half': a['half'] + (b['half'] - a['half']) * frac,
        'nx': a['nx'] + (b['nx'] - a['nx']) * frac,
        'nz': a['nz'] + (b['nz'] - a['nz']) * frac,
        'tx': a['tx'] + (b['tx'] - a['tx']) * frac,
        'tz': a['tz'] + (b['tz'] - a['tz']) * frac,
    }


def _nearest_sample(samples, x, z):
    best = samples[0]
    best_dist = math.inf
    for sample in samples:
        dist = math.hypot(sample['x'] - x, sample['z'] - z)
        if dist < best_dist:
            best_dist = dist
            best = sample
    return best


def _vista_tree(sample, side, lateral, index, variant, scale_mul):
    spec = DEAD_TREE_VARIANTS[variant]
    along = ((index % 5) - 2) * 0.85
    return {
        'x': sample['x'] + sample['nx'] * side * lateral + sample['tx'] * along,
        'z': sample['z'] + sample['nz'] * side * lateral + sample['tz'] * along,
        'nx': sample['nx'],
        'nz': sample['nz'],
        'tx': sample['tx'],
        'tz': sample['tz'],
        'scale': (0.78 + (index % 5) * 0.1) * scale_mul,
        'rotationY': (index * 1.17) % (math.pi * 2),
        'lean': (1 if index % 2 == 0 else -1) * (6 + (index % 4)) * (math.pi / 180),
        'leanAxis': (index * 0.73) % (math.pi * 2),
        'variant': variant,
        'branches': spec['branches'],
        'height': spec['height'],
    }


def _mountain_vista(end, hub, sway=-3.1):
    path = []
    for index in range(VISTA_STEPS + 1):
        t = index / VISTA_STEPS
        path.append({
            'x': end['x'] + math.sin(t * math.pi) * sway,
            'z': end['z'] + t * VISTA_LENGTH,
            'half': end['half'] + (4.35 - end['half']) * t,
            't': t,
        })
    _stamp_frame(path)
    far = path[-1]
    mountains = [
        {'x': far['x'] - 96, 'z': far['z'] + 22, 'height': 62, 'radius': 38, 'yaw': 0.4, 'depth': 0.82},
        {'x': far['x'] - 62, 'z': far['z'] + 10, 'height': 90, 'radius': 42, 'yaw': 0.2, 'depth': 0.74},
        {'x': far['x'] - 34, 'z': far['z'] + 2, 'height': 108, 'radius': 36, 'yaw': -0.3, 'depth': 0.7},
        {'x': far['x'] - 14, 'z': far['z'] + 6, 'height': 74, 'radius': 28, 'yaw': 0.15, 'depth': 0.78},
        {'x': far['x'], 'z': far['z'] + 14, 'height': 86, 'radius': 32, 'yaw': 0.05, 'depth': 0.66},
        {'x': far['x'] + 16, 'z': far['z'] + 6, 'height': 78, 'radius': 28, 'yaw': -0.2, 'depth': 0.76},
        {'x': far['x'] + 40, 'z': far['z'] + 4, 'height': 114, 'radius': 40, 'yaw': 0.35, 'depth': 0.72},
        {'x': far['x'] + 72, 'z': far['z'] + 14, 'height': 96, 'radius': 44, 'yaw': -0.15, 'depth': 0.8},
        {'x': far['x'] + 104, 'z': far['z'] + 26, 'height': 64, 'radius': 36, 'yaw': 0.5, 'depth': 0.84},
        {'x': far['x'] - 48, 'z': far['z'] - 2, 'height': 28, 'radius': 30, 'yaw': 0.25, 'depth': 0.7},
        {'x': far['x'] - 22, 'z': far['z'] - 8, 'height': 22, 'radius': 26, 'yaw': 0.6, 'depth': 0.62},
        {'x': far['x'], 'z': far['z'] - 2, 'height': 16, 'radius': 20, 'yaw': 0.1, 'depth': 0.55},
        {'x': far['x'] + 22, 'z': far['z'] - 8, 'height': 20, 'radius': 24, 'yaw': -0.4, 'depth': 0.6},
        {'x': far['x'] + 50, 'z': far['z'] - 2, 'height': 30, 'radius': 32, 'yaw': -0.55, 'depth': 0.68},
    ]
    trees = []
    scrub = []
    clear_z = hub['z'] + hub['d'] + 1.6
    for index in range(1, len(path)):
        sample = path[index]
        if sample['z'] < clear_z or sample['t'] > 0.8:
            continue
        side = -1 if index % 2 == 0 else 1
        lateral = sample['half'] + 2.6 + (index % 4) * 1.15
        trees.append(_vista_tree(sample, side, lateral, index, index % len(DEAD_TREE_VARIANTS), 1))
        if index % 2 == 0:
            trees.append(_vista_tree(sample, side, lateral + 6.5, index + 11, (index + 2) % len(DEAD_TREE_VARIANTS), 0.82))
        for brush_side in (-1, 1):
            brush_lateral = sample['half'] + 1.35 + ((index + (1 if brush_side > 0 else 0)) % 3) * 0.7
            along = ((index % 3) - 1) * 1.15
            scrub.append({
                'x': sample['x'] + sample['nx'] * brush_side * brush_lateral + sample['tx'] * along,
                'z': sample['z'] + sample['nz'] * brush_side * brush_lateral + sample['tz'] * along,
                'scale': 0.75 + (index % 4) * 0.22,
                'rotationY': (index * 1.31 + (0.4 if brush_side > 0 else 0)) % (math.pi * 2),
                'variant': (index + (1 if brush_side > 0 else 0)) % 2,
            })
            if index % 3 != 0:
                continue
            far_lateral = brush_lateral + 4.8
            scrub.append({
                'x': sample['x'] + sample['nx'] * brush_side * far_lateral - sample['tx'] * 0.8,
                'z': sample['z'] + sample['nz'] * brush_side * far_lateral - sample['tz'] * 0.8,
                'scale': 0.6 + (index % 3) * 0.2,
                'rotationY': (index * 0.77) % (math.pi * 2),
                'variant': index % 2,
            })
    return {
        'description': VISTA_DESCRIPTION,
        'path': path,
        'mountains': mountains,
        'scrub': scrub,
        'trees': trees,
    }


def _scatter_trees(rng, samples, count=30):
    trees = []
    end = samples[-1]
    guard = 0
    while len(trees) < count and guard < 900:
        guard += 1
        if len(trees) > 2 and rng.random() < 0.62:
            anchor = trees[rng.randrange(0, len(trees))]
            along = rng.uniform(-2.2, 2.2)
            out = rng.uniform(0.35, 2.6)
            x = anchor['x'] + anchor['nx'] * out + anchor['tx'] * along
            z = anchor['z'] + anchor['nz'] * out + anchor['tz'] * along
        else:
            sample = _point_on_trail(samples, 0.05 + rng.random() * 0.74)
            side = -1 if rng.random() < 0.5 else 1
            lateral = sample['half'] + TRAIL_CLEARANCE / 2 + 0.85 + rng.random() * 6.5
            x = sample['x'] + sample['nx'] * side * lateral
            z = sample['z'] + sample['nz'] * side * lateral
        if _blocks_prop(samples, x, z):
            continue
        if z < samples[0]['z'] + 1 or z > end['z'] - 8:
            continue
        if any(math.hypot(tree['x'] - x, tree['z'] - z) < 3.35 for tree in trees):
            continue
        nearest = _nearest_sample(samples, x, z)
        variant = rng.randrange(0, len(DEAD_TREE_VARIANTS))
        spec = DEAD_TREE_VARIANTS[variant]
        trees.append({
            'x': x,
            'z': z,
            'nx': nearest['nx'],
            'nz': nearest['nz'],
            'tx': nearest['tx'],
            'tz': nearest['tz'],
            'scale': 0.7 + rng.random() * 0.6,
            'rotationY': rng.random() * math.pi * 2,
            'lean': (5 + rng.random() * 5) * (math.pi / 180) * (-1 if rng.random() < 0.5 else 1),
            'leanAxis': rng.random() * math.pi * 2,
            'variant': variant,
            'branches': spec['branches'],
            'height': spec['height'],
        })
    return trees


# type: (zone, scale range). Zones: 'court' is the flagged yard in front of the arch,
# 'trail' is the verge beside the path, 'any' picks either.
SCENERY_TYPES = {
    'boulder': ('trail', (0.8, 1.9)),
    'scrub': ('trail', (0.6, 1.3)),
    'standing-stone': ('any', (0.9, 1.4)),
    'gravestone': ('court', (0.8, 1.2)),
    'fallen-column': ('court', (0.9, 1.3)),
    'broken-statue': ('court', (0.9, 1.2)),
    'rubble': ('court', (0.7, 1.3)),
    'cart-wreck': ('trail', (0.9, 1.2)),
    'campfire-ashes': ('trail', (0.8, 1.1)),
    'supply-crate': ('trail', (0.8, 1.1)),
    'signpost': ('trail', (0.9, 1.1)),
}

# Each dressing is a weighted mix of the types above.
DRESSINGS = {
    'overgrown': {'boulder': 4, 'standing-stone': 2, 'scrub': 5},
    'graveyard': {'gravestone': 6, 'standing-stone': 1, 'scrub': 2, 'boulder': 1},
    'fallen-hall': {'fallen-column': 4, 'broken-statue': 2, 'rubble': 3, 'boulder': 1, 'scrub': 2},
    'abandoned-camp': {
        'cart-wreck': 2, 'campfire-ashes': 2, 'supply-crate': 2, 'signpost': 1, 'scrub': 3, 'boulder': 1,
    },
}

SCENERY_SPACING = 2.4
SCENERY_TREE_GAP = 2.0


def _scenery_spot(rng, zone, samples, court, mid_x, door_width):
    if zone == 'any':
        zone = 'court' if rng.random() < 0.4 else 'trail'
    if zone == 'court':
        side = -1 if rng.random() < 0.5 else 1
        lane = door_width / 2 + 3.0
        x = mid_x + side * rng.uniform(lane, court['w'] / 2 - 2.0)
        z = court['z'] + rng.uniform(1.4, court['d'] - 1.4)
        return x, z
    sample = _point_on_trail(samples, 0.08 + rng.random() * 0.78)
    side = -1 if rng.random() < 0.5 else 1
    lateral = sample['half'] + TRAIL_CLEARANCE / 2 + 0.6 + rng.random() * 7
    return sample['x'] + sample['nx'] * side * lateral, sample['z'] + sample['nz'] * side * lateral


def _scatter_scenery(rng, samples, court, mid_x, door_width, trees, clutter):
    """Ruin dressing around the approach. Returns (dressing name, items)."""
    name = rng.choice(sorted(DRESSINGS))
    mix = DRESSINGS[name]
    types = sorted(mix)
    weights = [mix[kind] for kind in types]
    target = int(rng.randint(6, 16) * clutter * 2 + rng.random())
    end = samples[-1]
    items = []
    attempts = 0
    while len(items) < target and attempts < target * 20:
        attempts += 1
        kind = rng.choices(types, weights)[0]
        zone, (lo, hi) = SCENERY_TYPES[kind]
        x, z = _scenery_spot(rng, zone, samples, court, mid_x, door_width)
        if _blocks_prop(samples, x, z):
            continue
        if z < court['z'] + 1 or z > end['z'] - 8:
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
    return name, items


def _exterior(court, samples, vestibule):
    polygon = [
        [vestibule['x'], vestibule['z']],
        [vestibule['x'] + vestibule['w'], vestibule['z']],
        [vestibule['x'] + vestibule['w'], court['z']],
        [court['x'] + court['w'], court['z']],
        [court['x'] + court['w'], court['z'] + court['d']],
    ]
    for sample in samples:
        polygon.append([sample['x'] + sample['half'], sample['z']])
    for sample in reversed(samples):
        polygon.append([sample['x'] - sample['half'], sample['z']])
    polygon.append([court['x'], court['z'] + court['d']])
    polygon.append([court['x'], court['z']])
    polygon.append([vestibule['x'], court['z']])
    return polygon


def _trigger(x, z, width, depth):
    return {
        'minX': x - width / 2,
        'maxX': x + width / 2,
        'minZ': z - depth / 2,
        'maxZ': z + depth / 2,
    }


def _preset(preset):
    fog = dict(preset['fog']) if preset.get('fog') else None
    return {
        'clearColor': preset['clearColor'],
        'ambientLightIntensity': preset['ambientLightIntensity'],
        'fog': fog,
        'skyboxVisible': preset['skyboxVisible'],
    }


def build_approach(ante, rng, clutter=0.5):
    """Return the outdoor fields for one antechamber rectangle.

    The trail bend, trail length, tree count, and ruin dressing all come from `rng`.
    `clutter` (0 to 1) scales how much scenery is placed.
    """
    rect = ante
    south_z = rect.z + rect.d
    mid_x = rect.x + rect.w / 2
    door_width = entrance_door_width(rect)
    court_w = rect.w + COURT_EXTRA * 2
    court = {'x': mid_x - court_w / 2, 'z': south_z, 'w': court_w, 'd': COURT_DEPTH}
    shape = _trail_shape(rng)
    samples = _trail_samples(mid_x, court['z'] + court['d'], shape)
    end = samples[-1]
    path = {'x': mid_x - PATH_WIDTH / 2, 'z': samples[0]['z'], 'w': PATH_WIDTH, 'd': shape['length']}
    trees = _scatter_trees(rng, samples, rng.randint(18, 42))
    dressing, scenery = _scatter_scenery(rng, samples, court, mid_x, door_width, trees, clutter)
    vista_sway = -shape['bend'] * rng.uniform(2.0, 4.0)
    vestibule = {
        'x': mid_x - door_width / 2,
        'z': south_z - VESTIBULE_DEPTH,
        'w': door_width,
        'd': VESTIBULE_DEPTH,
    }
    hub = {'x': end['x'] - 9, 'z': end['z'] + 2.2, 'w': 18, 'd': 16}
    approach_point = _point_on_trail(samples, 0.34)
    toward_x = mid_x - approach_point['x']
    toward_z = south_z - approach_point['z']
    toward_len = math.hypot(toward_x, toward_z) or 1
    inner_spawn_z = min(rect.z + rect.d - 4.6, max(rect.z + 2.4, south_z - 5))
    return_point = _point_on_trail(samples, 0.82)
    entrance = {
        'a': [mid_x - door_width / 2, south_z],
        'b': [mid_x + door_width / 2, south_z],
        'width': door_width,
        'height': 7.2,
        'openingWidth': rect.w,
        'mouthA': [rect.x, south_z],
        'mouthB': [rect.x + rect.w, south_z],
    }
    return {
        'entrance': entrance,
        'vestibule': _polygon(vestibule),
        'exterior': _exterior(court, samples, vestibule),
        'hub': _polygon(hub),
        'trees': trees,
        'scenery': scenery,
        'zoneLabels': dict(ZONE_LABELS),
        'approach': {
            'shell': {
                'facadeHeight': 13,
                'flankHeight': 6.5,
                'cornice': {'height': 1.15, 'depth': 1.35, 'overhang': 1.2, 'y': 12.5},
            },
            'court': court,
            'path': path,
            'samples': samples,
            'southZ': south_z,
            'midX': mid_x,
            'vestibule': vestibule,
            'hub': hub,
            'corridorWidth': PATH_WIDTH + TRAIL_CLEARANCE,
            'lighting': 'day',
            'description': TRAIL_DESCRIPTION,
            'dressing': dressing,
            'vista': _mountain_vista(end, hub, vista_sway),
        },
        'transitions': [
            {
                'id': 'ruin-entry',
                'sourceZoneId': 'worn-trail',
                'targetZoneId': 'ancient-ruins',
                'targetSpawnPoint': {'x': mid_x, 'y': 0, 'z': inner_spawn_z, 'rotationY': 0},
                'transitionType': 'fade',
                'fadeDurationMs': 600,
                'environmentalPreset': _preset(INTERIOR),
                'volume': _trigger(mid_x, south_z - 2.05, door_width - 0.6, 1.1),
                'requiresGate': True,
            },
            {
                'id': 'ruin-exit',
                'sourceZoneId': 'ancient-ruins',
                'targetZoneId': 'worn-trail',
                'targetSpawnPoint': {'x': mid_x, 'y': 0, 'z': south_z + 4.2, 'rotationY': math.pi},
                'transitionType': 'fade',
                'fadeDurationMs': 600,
                'environmentalPreset': _preset(DAY),
                'volume': _trigger(mid_x, south_z - 0.65, door_width - 0.6, 1.0),
            },
            {
                'id': 'mountain-pass',
                'sourceZoneId': 'worn-trail',
                'targetZoneId': 'world-hub',
                'targetSpawnPoint': {
                    'x': end['x'],
                    'y': 0,
                    'z': hub['z'] + hub['d'] * 0.45,
                    'rotationY': math.pi,
                },
                'transitionType': 'fade',
                'fadeDurationMs': 300,
                'environmentalPreset': _preset(DAY),
                'volume': _trigger(end['x'], end['z'] - 0.2, PATH_WIDTH, 1.8),
            },
            {
                'id': 'mountain-return',
                'sourceZoneId': 'world-hub',
                'targetZoneId': 'worn-trail',
                'targetSpawnPoint': {
                    'x': return_point['x'],
                    'y': 0,
                    'z': return_point['z'],
                    'rotationY': 0,
                },
                'transitionType': 'fade',
                'fadeDurationMs': 300,
                'environmentalPreset': _preset(DAY),
                'volume': _trigger(end['x'], hub['z'] + 1.3, PATH_WIDTH, 1.6),
            },
        ],
        'gateInward': {'x': 0, 'z': -1},
        'start': {
            'x': approach_point['x'],
            'z': approach_point['z'],
            'yaw': math.atan2(-toward_x / toward_len, -toward_z / toward_len),
        },
    }
