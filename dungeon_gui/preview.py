"""A flat preview of one generated file. No zoom, and no mesh library.

Shapes become boxes or prisms. The picture scales to the object's size, so
turning it does not change how large it is.
"""

import json
import math
import re
from pathlib import Path

import tkinter as tk
from tkinter import ttk

_HEX = re.compile(r'^#[0-9a-fA-F]{6}$')
_DEFAULT = '#94a3b8'
_MAX_FACES = 2400
_ROOM_WALL = 4.0

# Stone stays slate. Wood and cave match the cartographer's tints.
_FLOOR = {'stone': '#334155', 'wood': '#5c4030', 'cave': '#44403c'}
_WALL = {'stone': '#64748b', 'wood': '#8a5a34', 'cave': '#78716c'}
_BUILDING = {
    'timber': ('#5c4030', '#8a5a34'),
    'canvas': ('#a8a090', '#d6d3c4'),
    'stone': ('#334155', '#64748b'),
    'logs': ('#3f2c20', '#6b4630'),
}


def _num(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number) or abs(number) > 100_000:
        return None
    return number


def _span(geometry, name):
    value = _num(geometry.get(name)) if isinstance(geometry, dict) else None
    if value is None or value <= 0:
        return None
    return value


def _color(value):
    if isinstance(value, str) and _HEX.fullmatch(value):
        return value.lower()
    return _DEFAULT


def _shade(color, factor):
    factor = max(0.0, min(1.0, factor))
    red = int(color[1:3], 16)
    green = int(color[3:5], 16)
    blue = int(color[5:7], 16)
    return f'#{int(red * factor):02x}{int(green * factor):02x}{int(blue * factor):02x}'


def _material_color(document, name):
    materials = document.get('materials')
    if not isinstance(materials, dict) or not isinstance(name, str):
        return _DEFAULT
    record = materials.get(name)
    if not isinstance(record, dict):
        return _DEFAULT
    return _color(record.get('color'))


def _vec(value):
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        return None
    point = (_num(value[0]), _num(value[1]), _num(value[2]))
    if None in point:
        return None
    return point


def _polygon(value):
    if not isinstance(value, list) or not 3 <= len(value) <= 64:
        return []
    points = []
    for point in value:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            return []
        x, z = _num(point[0]), _num(point[1])
        if x is None or z is None:
            return []
        points.append((x, z))
    return points


def _euler(record):
    rotation = record.get('rotation') if isinstance(record, dict) else None
    if not isinstance(rotation, dict):
        return (0.0, 0.0, 0.0)
    angles = []
    for axis in ('x', 'y', 'z'):
        value = _num(rotation.get(axis))
        angles.append(0.0 if value is None else math.radians(value))
    return tuple(angles)


def _rotate(point, rx, ry, rz):
    """XYZ Euler, matching Three.js and creature_gen.schema: X, then Y, then Z."""
    x, y, z = point
    cx, sx = math.cos(rx), math.sin(rx)
    y, z = y * cx - z * sx, y * sx + z * cx
    cy, sy = math.cos(ry), math.sin(ry)
    x, z = x * cy + z * sy, -x * sy + z * cy
    cz, sz = math.cos(rz), math.sin(rz)
    x, y = x * cz - y * sz, x * sz + y * cz
    return (x, y, z)


def _local_aabb(geometry):
    """Local min and max corners. None when the shape is not one we draw."""
    if not isinstance(geometry, dict):
        return None
    kind = geometry.get('type')
    if kind == 'box':
        width, height, depth = _span(geometry, 'width'), _span(geometry, 'height'), _span(geometry, 'depth')
        if None in (width, height, depth):
            return None
        return (-width / 2, -height / 2, -depth / 2), (width / 2, height / 2, depth / 2)
    if kind == 'sphere':
        radius = _span(geometry, 'radius')
        if radius is None:
            return None
        return (-radius, -radius, -radius), (radius, radius, radius)
    if kind == 'cylinder':
        radius = max(_span(geometry, 'radiusTop') or 0, _span(geometry, 'radiusBottom') or 0)
        height = _span(geometry, 'height')
        if radius <= 0 or height is None:
            return None
        return (-radius, -height / 2, -radius), (radius, height / 2, radius)
    if kind == 'capsule':
        radius, length = _span(geometry, 'radius'), _span(geometry, 'length')
        if None in (radius, length):
            return None
        reach = length / 2 + radius
        return (-radius, -reach, -radius), (radius, reach, radius)
    if kind == 'cone':
        radius, height = _span(geometry, 'radius'), _span(geometry, 'height')
        if None in (radius, height):
            return None
        return (-radius, -height / 2, -radius), (radius, height / 2, radius)
    if kind == 'torus':
        radius, tube = _span(geometry, 'radius'), _span(geometry, 'tube')
        if None in (radius, tube):
            return None
        reach = radius + tube
        return (-reach, -reach, -tube), (reach, reach, tube)
    if kind == 'blade':
        length = _span(geometry, 'length')
        thickness = _span(geometry, 'thickness')
        base = _num(geometry.get('baseWidth'))
        tip = _num(geometry.get('tipWidth'))
        if None in (length, thickness, base, tip) or base < 0 or tip < 0:
            return None
        width = max(base, tip)
        if width <= 0:
            return None
        return (-width / 2, -length / 2, -thickness / 2), (width / 2, length / 2, thickness / 2)
    if kind == 'shield':
        width, height, thickness = _span(geometry, 'width'), _span(geometry, 'height'), _span(geometry, 'thickness')
        if None in (width, height, thickness):
            return None
        return (-width / 2, -height / 2, -thickness / 2), (width / 2, height / 2, thickness / 2)
    if kind == 'lathe':
        points = geometry.get('points')
        if not isinstance(points, list) or not points or len(points) > 64:
            return None
        radii = []
        heights = []
        for point in points:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                return None
            radius, y = _num(point[0]), _num(point[1])
            if radius is None or y is None or radius < 0:
                return None
            radii.append(radius)
            heights.append(y)
        radius = max(radii)
        if radius <= 0:
            return None
        return (-radius, min(heights), -radius), (radius, max(heights), radius)
    if kind == 'tube':
        curve = geometry.get('curve')
        radius = _span(geometry, 'radius')
        if not isinstance(curve, dict) or radius is None:
            return None
        samples = []
        for key in ('from', 'control', 'to'):
            point = _vec(curve.get(key))
            if point is None:
                return None
            samples.append(point)
        xs, ys, zs = zip(*samples)
        return (
            (min(xs) - radius, min(ys) - radius, min(zs) - radius),
            (max(xs) + radius, max(ys) + radius, max(zs) + radius),
        )
    return None


def _quads(lo, hi):
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    corners = (
        (x0, y0, z0), (x1, y0, z0), (x0, y1, z0), (x1, y1, z0),
        (x0, y0, z1), (x1, y0, z1), (x0, y1, z1), (x1, y1, z1),
    )
    # Indices follow the tuple above: x changes fastest in pairs of y, then z.
    order = (
        (0, 1, 3, 2), (4, 6, 7, 5),
        (0, 2, 6, 4), (1, 5, 7, 3),
        (0, 4, 5, 1), (2, 3, 7, 6),
    )
    return [[corners[index] for index in face] for face in order]


def _ancestors(joints, name):
    """Joint first, then its parent, up to the root. Raises when the chain is broken."""
    by_name = {}
    for record in joints:
        if isinstance(record, dict) and isinstance(record.get('name'), str):
            by_name[record['name']] = record
    ordered = []
    seen = set()
    current = name
    while current is not None:
        if current in seen or len(ordered) > 32 or current not in by_name:
            raise ValueError('joints must not form a loop')
        record = by_name[current]
        seen.add(current)
        ordered.append(record)
        parent = record.get('parent')
        current = parent if isinstance(parent, str) else None
    return ordered


def _place(face, record, joints):
    corners = [_rotate(point, *_euler(record)) for point in face]
    position = _vec(record.get('position'))
    if position is None:
        raise ValueError('part has no position')
    corners = [
        (point[0] + position[0], point[1] + position[1], point[2] + position[2])
        for point in corners
    ]
    if joints is None:
        return corners
    joint_name = record.get('joint')
    if not isinstance(joint_name, str):
        raise ValueError('part has no joint')
    for joint_record in _ancestors(joints, joint_name):
        corners = [_rotate(point, *_euler(joint_record)) for point in corners]
        origin = _vec(joint_record.get('position'))
        if origin is None:
            raise ValueError('joint has no position')
        corners = [
            (point[0] + origin[0], point[1] + origin[1], point[2] + origin[2])
            for point in corners
        ]
    return corners


def _part_faces(document, joints):
    faces = []
    parts = document.get('parts')
    if not isinstance(parts, list):
        return faces
    for record in parts:
        if len(faces) >= _MAX_FACES or not isinstance(record, dict) or record.get('type') == 'group':
            continue
        bounds = _local_aabb(record.get('geometry'))
        if bounds is None:
            continue
        color = _material_color(document, record.get('material'))
        try:
            for face in _quads(*bounds):
                faces.append((_place(face, record, joints), color))
        except (TypeError, ValueError):
            continue
    return faces


def _add(faces, corners, color):
    if len(faces) < _MAX_FACES:
        faces.append((corners, color))


def _add_box(faces, lo, hi, color):
    for face in _quads(lo, hi):
        _add(faces, face, color)


def _add_yaw_box(faces, x, y, z, length, height, depth, yaw, color):
    lo = (-length / 2, -height / 2, -depth / 2)
    hi = (length / 2, height / 2, depth / 2)
    cy, sy = math.cos(yaw), math.sin(yaw)
    for face in _quads(lo, hi):
        placed = []
        for px, py, pz in face:
            placed.append((x + px * cy + pz * sy, y + py, z - px * sy + pz * cy))
        _add(faces, placed, color)


def _add_prism(faces, polygon, y0, height, floor, wall):
    y1 = y0 + height
    _add(faces, [(x, y0, z) for x, z in polygon], floor)
    _add(faces, [(x, y1, z) for x, z in polygon], wall)
    count = len(polygon)
    for index, (x, z) in enumerate(polygon):
        x2, z2 = polygon[(index + 1) % count]
        _add(faces, [(x, y0, z), (x2, y0, z2), (x2, y1, z2), (x, y1, z)], wall)


def _structure_polygon(structure):
    polygon = _polygon(structure.get('polygon'))
    if polygon:
        return polygon
    rect = structure.get('rect')
    if not isinstance(rect, dict):
        return []
    x, z = _num(rect.get('x')), _num(rect.get('z'))
    width, depth = _num(rect.get('w')), _num(rect.get('d'))
    if None in (x, z, width, depth) or width <= 0 or depth <= 0:
        return []
    return [(x, z), (x + width, z), (x + width, z + depth), (x, z + depth)]


def _add_structure(structure, faces):
    before = len(faces)
    floor, wall = _BUILDING.get(structure.get('material'), _BUILDING['stone'])
    polygon = _structure_polygon(structure)
    height = _num(structure.get('height'))
    if polygon and height is not None and height > 0.05:
        _add_prism(faces, polygon, 0.0, height, floor, wall)
    parts = structure.get('parts')
    if isinstance(parts, list):
        for part in parts:
            if not isinstance(part, dict):
                continue
            x, z = _num(part.get('x')), _num(part.get('z'))
            if x is None or z is None:
                continue
            kind = part.get('type')
            if kind == 'tower':
                radius, tower = _num(part.get('radius')), _num(part.get('height'))
                if radius is None or tower is None or radius <= 0 or tower <= 0:
                    continue
                _add_box(faces, (x - radius, 0.0, z - radius), (x + radius, tower, z + radius), wall)
            elif kind == 'fire-pit':
                radius = _num(part.get('radius')) or 0.6
                _add_box(faces, (x - radius, 0.0, z - radius), (x + radius, 0.45, z + radius), '#c2410c')
            elif kind == 'log-seat':
                length = _num(part.get('length')) or 2.0
                yaw = _num(part.get('rotationY')) or 0.0
                if length <= 0:
                    continue
                _add_yaw_box(faces, x, 0.2, z, length, 0.35, 0.4, yaw, '#6b4630')
    return len(faces) > before


def _add_rooms(document, faces):
    rooms = document.get('rooms')
    if not isinstance(rooms, list):
        return
    for room in rooms:
        if not isinstance(room, dict):
            continue
        polygon = _polygon(room.get('polygon'))
        if not polygon:
            continue
        y = _num(room.get('y')) or 0.0
        story = _num(room.get('storyHeight'))
        height = _ROOM_WALL if story is None or story <= 0 else min(story, _ROOM_WALL)
        role, block = room.get('role'), room.get('block')
        theme = room.get('theme') if isinstance(room.get('theme'), str) else 'stone'
        if role == 'exit' or block == 'exit':
            floor, wall = '#facc15', '#ca8a04'
        elif role == 'antechamber' or block == 'entrance':
            floor, wall = '#34d399', '#059669'
        else:
            floor = _FLOOR.get(theme, _FLOOR['stone'])
            wall = _WALL.get(theme, _WALL['stone'])
        _add_prism(faces, polygon, y, height, floor, wall)


def faces_of(document):
    """World-space faces for a dungeon, hub, gear item, or creature. Empty when nothing draws."""
    if not isinstance(document, dict):
        return []
    try:
        if document.get('joints') and document.get('parts'):
            return _part_faces(document, document['joints'])[:_MAX_FACES]
        if document.get('parts'):
            return _part_faces(document, None)[:_MAX_FACES]
        faces = []
        structure = document.get('structure')
        drew_building = isinstance(structure, dict) and _add_structure(structure, faces)
        if not drew_building:
            _add_rooms(document, faces)
        return faces[:_MAX_FACES]
    except (TypeError, ValueError):
        return []


def _view(point, yaw, pitch):
    x, y, z = point
    cy, sy = math.cos(yaw), math.sin(yaw)
    x, z = x * cy + z * sy, -x * sy + z * cy
    cp, sp = math.cos(pitch), math.sin(pitch)
    y, z = y * cp - z * sp, y * sp + z * cp
    return (x, y, z)


def _normal(points):
    ax, ay, az = points[1][0] - points[0][0], points[1][1] - points[0][1], points[1][2] - points[0][2]
    bx, by, bz = points[2][0] - points[0][0], points[2][1] - points[0][1], points[2][2] - points[0][2]
    nx, ny, nz = ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length < 1e-8:
        return (0.0, 0.0, 1.0)
    return (nx / length, ny / length, nz / length)


def project(faces, yaw, pitch, width, height):
    """Screen polygons, far to near. Scale comes from the object's size, not from a zoom control."""
    if width < 2 or height < 2:
        return []
    points = [point for face, _color in faces for point in face]
    if not points:
        return []
    xs, ys, zs = zip(*points)
    center = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2)
    radius = 0.5 * math.sqrt(
        (max(xs) - min(xs)) ** 2 + (max(ys) - min(ys)) ** 2 + (max(zs) - min(zs)) ** 2
    )
    radius = max(radius, 1e-4)
    scale = (min(width, height) * 0.5 - 16) / radius
    if scale <= 0:
        return []
    light = (0.35, 0.8, 0.45)
    light_length = math.sqrt(sum(axis * axis for axis in light))
    light = tuple(axis / light_length for axis in light)
    ordered = []
    for face, color in faces:
        if len(face) < 3:
            continue
        viewed = [_view((point[0] - center[0], point[1] - center[1], point[2] - center[2]), yaw, pitch) for point in face]
        depth = sum(point[2] for point in viewed) / len(viewed)
        shade = 0.42 + 0.58 * abs(sum(axis * lit for axis, lit in zip(_normal(viewed), light)))
        screen = [
            (width / 2 + point[0] * scale, height / 2 - point[1] * scale)
            for point in viewed
        ]
        ordered.append((depth, screen, _shade(color, shade)))
    ordered.sort(key=lambda item: item[0])
    return [(screen, color) for _depth, screen, color in ordered]


class Preview(ttk.Frame):
    """The picture under a generator form. Side arrows turn it. The bottom arrow tilts it."""

    def __init__(self, master):
        super().__init__(master)
        self.faces = []
        self.message = 'Generate to preview.'
        self.yaw = 0.6
        self.pitch = 0.45
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        ttk.Button(self, text='◀', width=3, command=self.turn_left).grid(row=0, column=0, sticky='ns', padx=(0, 4))
        self.canvas = tk.Canvas(
            self, background='#11151c', highlightthickness=1, highlightbackground='#2e384d', height=280,
        )
        self.canvas.grid(row=0, column=1, sticky='nsew')
        ttk.Button(self, text='▶', width=3, command=self.turn_right).grid(row=0, column=2, sticky='ns', padx=(4, 0))
        ttk.Button(self, text='▼', width=3, command=self.tilt).grid(row=1, column=1, pady=(6, 0))
        self.canvas.bind('<Configure>', lambda _event: self.redraw())

    def turn_left(self):
        self.yaw = (self.yaw - 0.4) % math.tau
        self.redraw()

    def turn_right(self):
        self.yaw = (self.yaw + 0.4) % math.tau
        self.redraw()

    def tilt(self):
        self.pitch += 0.35
        if self.pitch > 1.2:
            self.pitch = 0.15
        self.redraw()

    def show_file(self, path):
        try:
            document = json.loads(Path(path).read_text(encoding='utf-8'))
        except (OSError, UnicodeError, json.JSONDecodeError):
            document = None
        if not isinstance(document, dict):
            self.faces = []
            self.message = 'Could not preview this file.'
            self.redraw()
            return
        self.faces = faces_of(document)
        self.message = 'Nothing to draw.' if not self.faces else ''
        self.redraw()

    def redraw(self):
        canvas = self.canvas
        canvas.delete('all')
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        if width < 2:
            width = canvas.winfo_reqwidth()
        if height < 2:
            height = canvas.winfo_reqheight()
        if width < 2 or height < 2:
            return
        if not self.faces:
            canvas.create_text(width / 2, height / 2, text=self.message, fill='#94a3b8')
            return
        for points, color in project(self.faces, self.yaw, self.pitch, width, height):
            flat = [coord for point in points for coord in point]
            if len(flat) >= 6:
                canvas.create_polygon(*flat, fill=color, outline=color)
