"""Turn an assembled block layout into the Ancient Ruins JSON document."""

import math

from .approach import build_approach, entrance_door_width
from .assemble import assemble
from .blocks import STORY, polygon_of
from .density import DENSITY, depth_fractions, spawn_count
from .fire import flame
from .exits import build_exit
from .props import place_props
from .seeding import sub_rng
from .spatial import candidates as _candidates
from .spatial import clearance as _clearance
from .spatial import door_distance as _door_distance

NAMES = {
    'stone': ['Stone Gate', 'Stone Cells', 'Mason Hall', 'Stone Vault', 'Old Watch', 'Gallery of Blocks'],
    'wood': ['Wood Hall', 'Timber Barracks', 'Rafter Loft', 'Plank Chapel', 'Dry Stores', 'Cooperage'],
    'cave': ['Cave Bend', 'Damp Gallery', 'Low Cave', 'Echo Cave', 'Cave Crypt', 'Black Hollow'],
}

ENTRANCE_DESCRIPTION = (
    'A stone threshold under the arch. Pale daylight fails a few steps in, and the passage beyond is black.'
)
EXIT_DESCRIPTION = 'The last chamber. The way back to daylight is the arch you already passed through.'


def _round(value):
    return round(float(value), 4)


def _point(x, z):
    return [_round(x), _round(z)]


def _name_for(theme, used, rng):
    pool = NAMES[theme]
    for name in pool:
        if name not in used:
            used.add(name)
            return name
    name = f'{pool[len(used) % len(pool)]} {len(used)}'
    used.add(name)
    return name


def _door_record(link, rng):
    horizontal = abs(link.x1 - link.x0) >= abs(link.z1 - link.z0)
    if horizontal:
        x0, x1 = sorted((link.x0, link.x1))
        z = link.z0
        mouth = x1 - x0
        mouth_a = [x0, z]
        mouth_b = [x1, z]
        if link.narrow and mouth > 4.3:
            width = min(mouth, rng.uniform(4.2, 5.5))
            slack = max(0.0, mouth - width)
            offset = rng.uniform(0, slack) if slack > 0.05 else 0
            a = [x0 + offset, z]
            b = [x0 + offset + width, z]
        else:
            width = mouth
            a = [x0, z]
            b = [x1, z]
    else:
        z0, z1 = sorted((link.z0, link.z1))
        x = link.x0
        mouth = z1 - z0
        mouth_a = [x, z0]
        mouth_b = [x, z1]
        if link.narrow and mouth > 4.3:
            width = min(mouth, rng.uniform(4.2, 5.5))
            slack = max(0.0, mouth - width)
            offset = rng.uniform(0, slack) if slack > 0.05 else 0
            a = [x, z0 + offset]
            b = [x, z0 + offset + width]
        else:
            width = mouth
            a = [x, z0]
            b = [x, z1]
    return {
        'a': _point(*a),
        'b': _point(*b),
        'width': _round(width),
        'height': _round(rng.uniform(6.6, 8.2)),
        'openingWidth': _round(mouth),
        'mouthA': _point(*mouth_a),
        'mouthB': _point(*mouth_b),
        'from': link.parent.id,
        'to': link.child.id,
        'y': _round(link.y),
    }


def _stair_field(block, links):
    attached = [link for link in links if link.parent is block or link.child is block]
    if len(attached) < 2:
        return None
    lower = min(attached, key=lambda link: link.y)
    upper = max(attached, key=lambda link: link.y)

    def center(link):
        return (link.x0 + link.x1) / 2, (link.z0 + link.z1) / 2

    cx = block.rect.x + block.rect.w / 2
    cz = block.rect.z + block.rect.d / 2

    def nudge(x, z):
        dx = cx - x
        dz = cz - z
        length = math.hypot(dx, dz) or 1
        return _point(x + dx / length * 0.8, z + dz / length * 0.8)

    low = nudge(*center(lower))
    high = nudge(*center(upper))
    axis = 'x' if abs(high[0] - low[0]) >= abs(high[1] - low[1]) else 'z'
    return {'axis': axis, 'fromY': _round(lower.y), 'toY': _round(upper.y), 'low': low, 'high': high}


def _place_spawns(block, doors, rng, wanted):
    if wanted <= 0:
        return []
    step = 1.4 if block.kind == 'corridor' else 2
    points = _candidates(block.rect, step)
    rng.shuffle(points)
    taken = []
    for x, z in points:
        if len(taken) >= wanted:
            break
        if _clearance(x, z, block.rect) < 1.45:
            continue
        if _door_distance(x, z, doors) < 2.4:
            continue
        if any(math.hypot(x - ox, z - oz) < 2.3 for ox, oz in taken):
            continue
        taken.append((x, z))
    return [_point(x, z) for x, z in taken]


def _sconce(block, doors, rng):
    rect = block.rect
    options = (
        (rect.x + 0.55, rect.z + rect.d * 0.5, 1, 0),
        (rect.x + rect.w - 0.55, rect.z + rect.d * 0.5, -1, 0),
        (rect.x + rect.w * 0.5, rect.z + 0.55, 0, 1),
        (rect.x + rect.w * 0.5, rect.z + rect.d - 0.55, 0, -1),
    )
    best = options[0]
    best_score = -math.inf
    for option in options:
        score = _door_distance(option[0], option[1], doors) + rng.random()
        if score > best_score:
            best_score = score
            best = option
    record = {'x': _round(best[0]), 'z': _round(best[1]), 'nx': best[2], 'nz': best[3]}
    record.update(flame())
    return record


def _chest(block, sconce, doors, spawns):
    side_x = -sconce['nz']
    side_z = sconce['nx']
    best = None
    best_clear = -math.inf
    lateral = 3.2
    while lateral >= 2.55 - 1e-6:
        for sign in (1, -1):
            inward = 1.9
            while inward <= 3.15 + 1e-6:
                x = sconce['x'] + side_x * sign * lateral + sconce['nx'] * inward
                z = sconce['z'] + side_z * sign * lateral + sconce['nz'] * inward
                space = _clearance(x, z, block.rect)
                inward += 0.25
                if space < 0.6:
                    continue
                if _door_distance(x, z, doors) < 1.5:
                    continue
                if any(math.hypot(x - point[0], z - point[1]) < 1.6 for point in spawns):
                    continue
                if space > best_clear:
                    best_clear = space
                    best = {'x': _round(x), 'z': _round(z)}
                if space >= 1.22 + 1.15 + 0.35:
                    return {'x': _round(x), 'z': _round(z)}
        lateral -= 0.25
    if best:
        return best
    return {
        'x': _round(sconce['x'] + side_x * 2.7 + sconce['nx'] * 2.5),
        'z': _round(sconce['z'] + side_z * 2.7 + sconce['nz'] * 2.5),
    }


def _rocks(block, doors, spawns, rng):
    area = block.rect.w * block.rect.d
    if block.kind != 'chamber' or block.block == 'entrance' or area <= 450:
        return []
    points = _candidates(block.rect, 2)
    rng.shuffle(points)
    rocks = []
    center = (block.rect.x + block.rect.w / 2, block.rect.z + block.rect.d / 2)
    for x, z in points:
        if len(rocks) >= 2:
            break
        if _clearance(x, z, block.rect) < 2.2 or _door_distance(x, z, doors) < 3:
            continue
        if any(math.hypot(x - point[0], z - point[1]) < 2.6 for point in spawns):
            continue
        if math.hypot(x - center[0], z - center[1]) < 2.6:
            continue
        if any(math.hypot(x - rock[0], z - rock[1]) < 3 for rock in rocks):
            continue
        rocks.append(_point(x, z))
    return rocks


def _passage_name(block):
    if block.run > 18:
        return 'Long Passage'
    if block.span < 6.2 and block.block == 'doorway':
        return 'Doorway'
    if block.span < 6.2:
        return 'Narrow Passage'
    return 'Passage'


def _themes(blocks, rng):
    fought = [block for block in blocks if block.kind == 'chamber' and block.block != 'entrance']
    deck = []
    while len(deck) < len(fought):
        cycle = ['stone', 'wood', 'cave']
        rng.shuffle(cycle)
        deck.extend(cycle)
    return {id(block): deck[index] for index, block in enumerate(fought)}


def _prop_doors(block, linked):
    """Openings props must stay clear of. The antechamber also has the outside arch."""
    doors = list(linked)
    if block.block == 'entrance':
        mid = block.rect.x + block.rect.w / 2
        half = entrance_door_width(block.rect) / 2
        south = block.rect.z + block.rect.d
        doors.append({'a': [mid - half, south], 'b': [mid + half, south]})
    return doors


def _avoid_points(spawns, rocks, chest, sconce):
    avoid = [(x, z, 2.0) for x, z in spawns]
    avoid.extend((x, z, 2.0) for x, z in rocks)
    if chest:
        avoid.append((chest['x'], chest['z'], 2.2))
    if sconce:
        avoid.append((sconce['x'], sconce['z'], 2.0))
    return avoid


def emit(layout, rng, seed, floors, density='normal', clutter=0.5):
    themes = _themes(layout.blocks, rng)
    depths = depth_fractions(layout)
    used_names = {'Antechamber'}
    for index, block in enumerate(layout.blocks):
        block.index = index
        block.id = f'space-{index}'

    doors = [_door_record(link, rng) for link in layout.links]
    by_id = {}
    rooms = []
    for block in layout.blocks:
        theme = 'stone' if block.block in ('entrance', 'hallway', 'doorway', 'stairwell') else themes[id(block)]
        if block.block == 'exit':
            theme = themes[id(block)]
        story = STORY * 2 if block.block == 'stairwell' else STORY
        if block.block == 'entrance':
            name = 'Antechamber'
        elif block.kind == 'corridor':
            name = _passage_name(block)
        elif block.block == 'stairwell':
            name = 'Stairwell'
        else:
            name = _name_for(theme, used_names, rng)
        linked = [door for door in doors if door['from'] == block.id or door['to'] == block.id]
        wanted = spawn_count(block, density, depths.get(id(block), 0.0))
        spawns = _place_spawns(block, linked, sub_rng(seed, 'spawns', block.index), wanted)
        room = {
            'id': block.id,
            'index': block.index,
            'kind': block.kind,
            'name': name,
            'theme': theme,
            'rect': {
                'x': _round(block.rect.x),
                'z': _round(block.rect.z),
                'w': _round(block.rect.w),
                'd': _round(block.rect.d),
            },
            'run': _round(block.run),
            'span': _round(block.span),
            'polygon': [_point(x, z) for x, z in polygon_of(block.rect)],
            'spawns': spawns,
            'brazier': None,
            'sconce': None,
            'rocks': [],
            'props': [],
            'lighting': 'underground',
            'floor': block.floor,
            'y': _round(block.floor * STORY),
            'storyHeight': _round(story),
            'block': block.block,
            'stair': _stair_field(block, layout.links) if block.block == 'stairwell' else None,
            'chest': None,
        }
        if block.role:
            room['role'] = block.role
        if block.block == 'entrance':
            room['description'] = ENTRANCE_DESCRIPTION
        elif block.block == 'exit':
            room['description'] = EXIT_DESCRIPTION
        if theme == 'cave':
            room['rocks'] = _rocks(block, linked, spawns, sub_rng(seed, 'rocks', block.index))
        if block.kind == 'chamber' and spawns and block.block not in ('entrance', 'exit'):
            anchor = _sconce(block, linked, sub_rng(seed, 'sconce', block.index))
            room['sconce'] = anchor
            room['chest'] = _chest(block, anchor, linked, spawns)
        if block.kind == 'chamber':
            room['props'] = place_props(
                block,
                theme,
                _prop_doors(block, linked),
                _avoid_points(spawns, room['rocks'], room['chest'], room['sconce']),
                sub_rng(seed, 'props', block.index),
                clutter,
            )
        rooms.append(room)
        by_id[block.id] = room

    ante = layout.blocks[0].rect
    outdoors = build_approach(ante, sub_rng(seed, 'approach'), clutter)
    exit_block = next(block for block in layout.blocks if block.block == 'exit')
    exit_gate, exit_area, exit_labels, exit_transitions = build_exit(
        layout, exit_block, sub_rng(seed, 'exit'), clutter, outdoors['transitions'])
    area = sum(block.rect.w * block.rect.d for block in layout.blocks)
    return {
        'seed': int(seed) & 0xFFFFFFFF,
        'floors': floors,
        'options': {'density': density, 'clutter': round(float(clutter), 3)},
        'area': area,
        'rooms': rooms,
        'doors': doors,
        'start': outdoors['start'],
        'lastRoomId': exit_block.id,
        'areaName': 'The Ancient Ruins',
        'requirements': ['torch', 'mace'],
        'entrance': outdoors['entrance'],
        'vestibule': outdoors['vestibule'],
        'exterior': outdoors['exterior'],
        'hub': outdoors['hub'],
        'trees': outdoors['trees'],
        'scenery': outdoors['scenery'],
        'zoneLabels': {**outdoors['zoneLabels'], **exit_labels},
        'approach': outdoors['approach'],
        'transitions': outdoors['transitions'] + exit_transitions,
        'gateInward': outdoors['gateInward'],
        'exitGate': exit_gate,
        'exitArea': exit_area,
    }


def generate_layout(seed=1, floors=2, chambers=8, density='normal', clutter=0.5):
    """Build a full Ancient Ruins document.

    `chambers` counts the entrance, the exit, T hubs, and other rooms.
    Stairwells, hallways, and doorways are extra structure and are not counted.
    `density` is 'low', 'normal', or 'high' and scales enemy spawns.
    `clutter` is 0 to 1 and scales room props and outdoor scenery.
    """
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise TypeError('seed must be an int')
    if floors < 1 or floors > 8:
        raise ValueError('floors must be from 1 to 8')
    if chambers < 2 or chambers > 30:
        raise ValueError('chambers must be from 2 to 30')
    if density not in DENSITY:
        raise ValueError('density must be one of: ' + ', '.join(DENSITY))
    if isinstance(clutter, bool) or not isinstance(clutter, (int, float)):
        raise TypeError('clutter must be a number')
    if not math.isfinite(clutter) or clutter < 0 or clutter > 1:
        raise ValueError('clutter must be from 0 to 1')
    layout, rng = assemble(seed, floors, chambers)
    return emit(layout, rng, seed, floors, density, clutter)
