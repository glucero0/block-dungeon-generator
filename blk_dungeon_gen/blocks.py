"""Footprints, sockets, and rectangle tests for the block assembler."""

STORY = 10.0
PASSAGE = 6.0

NARROW_BLOCKS = ('entrance', 'exit', 'small-room', 'big-room')

SIZES = {
    'entrance': (16.0, 12.5),
    'exit': (16.0, 16.0),
    'small-room': (16.0, 16.0),
    'big-room': (28.0, 24.0),
    'doorway': (PASSAGE, 4.0),
    'hallway': (PASSAGE, 16.0),
    'hub': (14.0, 14.0),
    'stairwell': (12.0, 16.0),
}

# Outward direction of travel. North is -Z, toward the deeper ruin.
OPPOSITE = {'N': 'S', 'S': 'N', 'E': 'W', 'W': 'E'}
PERPENDICULAR = {
    'N': ('W', 'E'),
    'S': ('E', 'W'),
    'E': ('N', 'S'),
    'W': ('S', 'N'),
}


class Rect:
    def __init__(self, x, z, w, d):
        self.x = float(x)
        self.z = float(z)
        self.w = float(w)
        self.d = float(d)

    def as_dict(self):
        return {'x': self.x, 'z': self.z, 'w': self.w, 'd': self.d}


class Socket:
    def __init__(self, direction, x0, x1, z0, z1, floor, owner):
        self.direction = direction
        self.x0 = float(x0)
        self.x1 = float(x1)
        self.z0 = float(z0)
        self.z1 = float(z1)
        self.floor = int(floor)
        self.owner = owner
        self.open = True

    def span(self):
        if self.direction in ('N', 'S'):
            return (min(self.x0, self.x1), max(self.x0, self.x1))
        return (min(self.z0, self.z1), max(self.z0, self.z1))

    def length(self):
        start, end = self.span()
        return end - start


class Block:
    def __init__(self, block, kind, floor, rect, run=0.0, span=0.0, role=None):
        self.block = block
        self.kind = kind
        self.floor = int(floor)
        self.rect = rect
        self.run = float(run)
        self.span = float(span)
        self.role = role
        self.floors = [self.floor]
        if block == 'stairwell':
            self.floors = [self.floor, self.floor + 1]


class Link:
    def __init__(self, parent, child, socket):
        self.parent = parent
        self.child = child
        self.x0 = socket.x0
        self.x1 = socket.x1
        self.z0 = socket.z0
        self.z1 = socket.z1
        self.y = socket.floor * STORY
        self.narrow = parent.block in NARROW_BLOCKS or child.block in NARROW_BLOCKS


def overlaps(a, b, pad=0.02):
    return (
        a.x < b.x + b.w - pad
        and b.x < a.x + a.w - pad
        and a.z < b.z + b.d - pad
        and b.z < a.z + a.d - pad
    )


def place_rect(socket, cross, along, slide):
    """Put a block beyond `socket`. `cross` is the edge length, `along` the depth."""
    start, end = socket.span()
    span = end - start
    if span > cross + 0.02 or slide < -0.02 or slide + span > cross + 0.02:
        return None
    if socket.direction == 'N':
        return Rect(start - slide, socket.z0 - along, cross, along)
    if socket.direction == 'S':
        return Rect(start - slide, socket.z0, cross, along)
    if socket.direction == 'E':
        return Rect(socket.x0, start - slide, along, cross)
    if socket.direction == 'W':
        return Rect(socket.x0 - along, start - slide, along, cross)
    return None


def socket_on(rect, direction, floor, owner, offset, length=PASSAGE):
    if direction in ('N', 'S'):
        if offset < -0.02 or offset + length > rect.w + 0.02:
            return None
        x0 = rect.x + offset
        z = rect.z if direction == 'N' else rect.z + rect.d
        return Socket(direction, x0, x0 + length, z, z, floor, owner)
    if offset < -0.02 or offset + length > rect.d + 0.02:
        return None
    z0 = rect.z + offset
    x = rect.x if direction == 'W' else rect.x + rect.w
    return Socket(direction, x, x, z0, z0 + length, floor, owner)


def centered_offset(rect, direction, length=PASSAGE):
    edge = rect.w if direction in ('N', 'S') else rect.d
    return (edge - length) / 2


def polygon_of(rect):
    return [
        [rect.x, rect.z],
        [rect.x + rect.w, rect.z],
        [rect.x + rect.w, rect.z + rect.d],
        [rect.x, rect.z + rect.d],
    ]


def offsets(cross, length=PASSAGE, step=2.0):
    limit = cross - length
    if limit < -0.02:
        return []
    values = []
    cursor = 0.0
    while cursor <= limit + 1e-6:
        values.append(cursor)
        cursor += step
    return values
