"""Stamp entrance, rooms, hallways, hubs, and stairwells into one connected layout."""

import random

from .blocks import (
    PASSAGE,
    PERPENDICULAR,
    Block,
    Link,
    Rect,
    centered_offset,
    offsets,
    overlaps,
    place_rect,
    socket_on,
)


class Layout:
    def __init__(self):
        self.blocks = []
        self.links = []
        self.open = []
        self.occupied = {}

    def hits(self, rect, floors, extra=()):
        for floor in floors:
            for other in self.occupied.get(floor, ()):
                if overlaps(rect, other):
                    return True
        for other in extra:
            if other is not None and overlaps(rect, other):
                return True
        return False

    def add_block(self, block):
        self.blocks.append(block)
        for floor in block.floors:
            self.occupied.setdefault(floor, []).append(block.rect)

    def close(self, socket):
        socket.open = False
        if socket in self.open:
            self.open.remove(socket)

    def link(self, socket, child):
        self.links.append(Link(socket.owner, child, socket))
        self.close(socket)


def _fits_passage(layout, socket, along, extra=()):
    rect = place_rect(socket, PASSAGE, along, 0)
    if rect is None or layout.hits(rect, [socket.floor], extra):
        return None
    return rect


def _passage(layout, socket, name, along, run):
    rect = _fits_passage(layout, socket, along)
    if rect is None:
        return None
    block = Block(name, 'corridor', socket.floor, rect, run=run, span=PASSAGE)
    far = socket_on(rect, socket.direction, socket.floor, block, 0)
    layout.add_block(block)
    layout.link(socket, block)
    layout.open.append(far)
    return far


def attach_hallway(layout, socket):
    return _passage(layout, socket, 'hallway', 16, 16)


def attach_doorway(layout, socket):
    return _passage(layout, socket, 'doorway', 4, 4)


def _room_choices(name):
    if name == 'big-room':
        return ((28.0, 24.0), (24.0, 28.0))
    if name == 'exit':
        return ((16.0, 16.0),)
    return ((16.0, 16.0),)


def _commit_room(layout, socket, name, rect, exit_sockets):
    block = Block(
        name,
        'chamber',
        socket.floor,
        rect,
        role='exit' if name == 'exit' else None,
    )
    opened = []
    for direction, offset in exit_sockets:
        opened.append(socket_on(rect, direction, socket.floor, block, offset))
    layout.add_block(block)
    layout.link(socket, block)
    for sock in opened:
        layout.open.append(sock)
    return opened


def attach_passthrough(layout, socket, rng, prefer_big):
    """Doorway, a room with an onward socket, and a doorway out."""
    names = ('big-room', 'small-room') if prefer_big else ('small-room', 'big-room')
    travel = socket.direction
    onward = (travel,) + PERPENDICULAR[travel]
    door_rect = _fits_passage(layout, socket, 4)
    if door_rect is None:
        return None
    probe = socket_on(door_rect, travel, socket.floor, None, 0)
    for name in names:
        for cross, along in _room_choices(name):
            slides = offsets(cross)
            rng.shuffle(slides)
            for slide in slides:
                rect = place_rect(probe, cross, along, slide)
                if rect is None or layout.hits(rect, [socket.floor], (door_rect,)):
                    continue
                edge_for = lambda direction, rect=rect: rect.w if direction in ('N', 'S') else rect.d
                for direction in onward:
                    exits = offsets(edge_for(direction))
                    rng.shuffle(exits)
                    for offset in exits:
                        exit_sock = socket_on(rect, direction, socket.floor, None, offset)
                        if exit_sock is None:
                            continue
                        if _fits_passage(layout, exit_sock, 4, extra=(door_rect, rect)) is None:
                            continue
                        far = attach_doorway(layout, socket)
                        if far is None:
                            return None
                        opened = _commit_room(layout, far, name, rect, ((direction, offset),))
                        out = attach_doorway(layout, opened[0])
                        if out is None:
                            return None
                        return out
    return None


def _plan_branch(layout, socket, rng, extra):
    bases = []
    hall_rect = _fits_passage(layout, socket, 16, extra)
    if hall_rect is not None:
        hall_far = socket_on(hall_rect, socket.direction, socket.floor, None, 0)
        bases.append(('hallway', hall_rect, hall_far))
    bases.append(('direct', None, socket))
    for kind, hall_rect_used, door_socket in bases:
        door_extra = tuple(extra) + ((hall_rect_used,) if hall_rect_used is not None else ())
        door_rect = _fits_passage(layout, door_socket, 4, door_extra)
        if door_rect is None:
            continue
        probe = socket_on(door_rect, door_socket.direction, socket.floor, None, 0)
        packed = door_extra + (door_rect,)
        for name in ('small-room', 'big-room'):
            for cross, along in _room_choices(name):
                slides = offsets(cross)
                rng.shuffle(slides)
                for slide in slides:
                    rect = place_rect(probe, cross, along, slide)
                    if rect is None or layout.hits(rect, [socket.floor], packed):
                        continue
                    return {
                        'kind': kind,
                        'name': name,
                        'slide': slide,
                        'cross': cross,
                        'along': along,
                        'rects': tuple(item for item in (hall_rect_used, door_rect, rect) if item is not None),
                        'socket': socket,
                    }
    return None


def _commit_branch(layout, plan):
    socket = plan['socket']
    if plan['kind'] == 'hallway':
        socket = attach_hallway(layout, socket)
        if socket is None:
            return False
    far = attach_doorway(layout, socket)
    if far is None:
        return False
    rect = place_rect(far, plan['cross'], plan['along'], plan['slide'])
    if rect is None:
        return False
    _commit_room(layout, far, plan['name'], rect, ())
    return True


def attach_hub(layout, socket, rng):
    """A T junction: stem on `socket`, a dead-end arm, and a hallway that continues."""
    hub_rect = place_rect(socket, 14, 14, 4)
    if hub_rect is None or layout.hits(hub_rect, [socket.floor]):
        return None
    hub = Block('hub', 'chamber', socket.floor, hub_rect)
    arms = [
        socket_on(hub_rect, direction, socket.floor, hub, centered_offset(hub_rect, direction))
        for direction in PERPENDICULAR[socket.direction]
    ]
    order = [0, 1]
    rng.shuffle(order)
    for branch_index in order:
        branch_sock = arms[branch_index]
        cont_sock = arms[1 - branch_index]
        branch_plan = _plan_branch(layout, branch_sock, rng, (hub_rect,))
        if branch_plan is None:
            continue
        if _fits_passage(layout, cont_sock, 16, extra=(hub_rect,) + branch_plan['rects']) is None:
            continue
        layout.add_block(hub)
        layout.link(socket, hub)
        for arm in arms:
            layout.open.append(arm)
        if not _commit_branch(layout, branch_plan):
            return None
        return attach_hallway(layout, cont_sock)
    return None


def attach_stair(layout, socket):
    slide = (12 - PASSAGE) / 2
    rect = place_rect(socket, 12, 16, slide)
    floors = [socket.floor, socket.floor + 1]
    if rect is None or layout.hits(rect, floors):
        return None
    block = Block('stairwell', 'stairwell', socket.floor, rect, run=16, span=12)
    upper = socket_on(
        rect,
        socket.direction,
        socket.floor + 1,
        block,
        centered_offset(rect, socket.direction),
    )
    layout.add_block(block)
    layout.link(socket, block)
    layout.open.append(upper)
    return upper


def attach_exit(layout, socket, rng):
    door_rect = _fits_passage(layout, socket, 4)
    if door_rect is None:
        return False
    probe = socket_on(door_rect, socket.direction, socket.floor, None, 0)
    slides = offsets(16)
    rng.shuffle(slides)
    for slide in slides:
        rect = place_rect(probe, 16, 16, slide)
        if rect is None or layout.hits(rect, [socket.floor], (door_rect,)):
            continue
        far = attach_doorway(layout, socket)
        if far is None:
            return False
        _commit_room(layout, far, 'exit', rect, ())
        return True
    return False


def _entrance(layout):
    rect = Rect(0, 0, 16, 12.5)
    block = Block('entrance', 'chamber', 0, rect, role='antechamber')
    sock = socket_on(rect, 'N', 0, block, centered_offset(rect, 'N'))
    layout.add_block(block)
    layout.open.append(sock)
    return sock


def _quota(floors, chambers):
    remaining = chambers - 2
    if remaining < 0:
        return None
    base, extra = divmod(remaining, floors)
    quota = [base + (1 if index < extra else 0) for index in range(floors)]
    if remaining >= 2 and quota[0] < 2:
        for index in range(1, floors):
            while quota[0] < 2 and quota[index] > 0:
                quota[index] -= 1
                quota[0] += 1
        if quota[0] < 2:
            return None
    return quota


def try_build(rng, floors, chambers):
    quota = _quota(floors, chambers)
    if quota is None:
        return None
    layout = Layout()
    main = _entrance(layout)
    placed_hub = False
    big_pending = True
    for floor in range(floors):
        main = attach_hallway(layout, main)
        if main is None:
            return None
        if floor == 0:
            chained = attach_hallway(layout, main)
            if chained is not None:
                main = chained
        need = quota[floor]
        guard = 0
        while need > 0 and guard < 24:
            guard += 1
            if not placed_hub and need >= 2:
                far = attach_hub(layout, main, rng)
                if far is None:
                    return None
                main = far
                placed_hub = True
                need -= 2
                continue
            if rng.random() < 0.45:
                shifted = attach_hallway(layout, main)
                if shifted is not None:
                    main = shifted
            far = attach_passthrough(layout, main, rng, prefer_big=big_pending)
            if far is None:
                shifted = attach_hallway(layout, main)
                if shifted is None:
                    return None
                main = shifted
                far = attach_passthrough(layout, main, rng, prefer_big=big_pending)
                if far is None:
                    return None
            main = far
            big_pending = False
            need -= 1
        if need > 0:
            return None
        if floor < floors - 1:
            upper = attach_stair(layout, main)
            if upper is None:
                shifted = attach_hallway(layout, main)
                if shifted is None:
                    return None
                upper = attach_stair(layout, shifted)
                if upper is None:
                    return None
            main = upper
        elif not attach_exit(layout, main, rng):
            shifted = attach_hallway(layout, main)
            if shifted is None or not attach_exit(layout, shifted, rng):
                return None
    if layout.open:
        return None
    return layout


def _connected(layout):
    if not layout.blocks:
        return False
    neighbors = {id(block): [] for block in layout.blocks}
    for link in layout.links:
        neighbors[id(link.parent)].append(link.child)
        neighbors[id(link.child)].append(link.parent)
    start = layout.blocks[0]
    goal = next(block for block in layout.blocks if block.block == 'exit')
    seen = {id(start)}
    queue = [start]
    while queue:
        current = queue.pop()
        if current is goal:
            return True
        for nxt in neighbors[id(current)]:
            if id(nxt) in seen:
                continue
            seen.add(id(nxt))
            queue.append(nxt)
    return False


def valid(layout, floors, chambers):
    if layout is None or not _connected(layout):
        return False
    if layout.open:
        return False
    if layout.blocks[0].block != 'entrance':
        return False
    exits = [block for block in layout.blocks if block.block == 'exit']
    if len(exits) != 1:
        return False
    if sum(1 for block in layout.blocks if block.block == 'stairwell') != max(0, floors - 1):
        return False
    if sum(1 for block in layout.blocks if block.kind == 'chamber') != chambers:
        return False
    if chambers >= 4 and not any(block.block == 'hub' for block in layout.blocks):
        return False
    for hub in (block for block in layout.blocks if block.block == 'hub'):
        degree = sum(1 for link in layout.links if link.parent is hub or link.child is hub)
        if degree != 3:
            return False
    for rects in layout.occupied.values():
        for index, rect in enumerate(rects):
            for other in rects[index + 1:]:
                if overlaps(rect, other):
                    return False
    return True


def assemble(seed, floors, chambers, attempts=80):
    rng = random.Random(seed & 0xFFFFFFFF)
    for _ in range(attempts):
        layout = try_build(rng, floors, chambers)
        if valid(layout, floors, chambers):
            return layout, rng
    raise RuntimeError('could not assemble a layout for this seed')
