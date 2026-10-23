"""Small geometry helpers shared by the room emitters."""

import math


def clearance(x, z, rect):
    """Distance from a point to the nearest wall of `rect`. Negative when outside."""
    inside = rect.x <= x <= rect.x + rect.w and rect.z <= z <= rect.z + rect.d
    dx = min(x - rect.x, rect.x + rect.w - x)
    dz = min(z - rect.z, rect.z + rect.d - z)
    dist = min(dx, dz)
    return dist if inside else -dist


def closest(px, pz, ax, az, bx, bz):
    """Point on segment a-b nearest to p."""
    abx = bx - ax
    abz = bz - az
    len2 = abx * abx + abz * abz
    t = 0 if len2 <= 0 else ((px - ax) * abx + (pz - az) * abz) / len2
    t = max(0.0, min(1.0, t))
    return ax + abx * t, az + abz * t


def segment_distance(px, pz, ax, az, bx, bz):
    cx, cz = closest(px, pz, ax, az, bx, bz)
    return math.hypot(px - cx, pz - cz)


def door_distance(x, z, doors):
    best = math.inf
    for door in doors:
        best = min(best, segment_distance(x, z, door['a'][0], door['a'][1], door['b'][0], door['b'][1]))
    return best


def candidates(rect, step):
    """Grid of points inside `rect`, kept 1.6 m off every wall."""
    points = []
    x = rect.x + 1.6
    while x <= rect.x + rect.w - 1.6 + 1e-6:
        z = rect.z + 1.6
        while z <= rect.z + rect.d - 1.6 + 1e-6:
            points.append((x, z))
            z += step
        x += step
    return points
