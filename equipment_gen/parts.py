"""Part records. Shapes stay inside the geometry allowlist."""

from .materials import take


def num(value):
    return round(float(value), 4)


def vec(x, y, z):
    return [num(x), num(y), num(z)]


def part(name, material, geometry, position, rotation=None):
    record = {
        'name': name,
        'material': material,
        'geometry': geometry,
        'position': vec(*position),
    }
    if rotation is not None:
        record['rotation'] = {
            'x': num(rotation[0]),
            'y': num(rotation[1]),
            'z': num(rotation[2]),
            'unit': 'degrees',
        }
    return record


def box(width, height, depth):
    return {'type': 'box', 'width': num(width), 'height': num(height), 'depth': num(depth)}


def cylinder(radius_top, radius_bottom, height, segments=12):
    return {
        'type': 'cylinder',
        'radiusTop': num(radius_top),
        'radiusBottom': num(radius_bottom),
        'height': num(height),
        'radialSegments': int(segments),
    }


def sphere(radius, width_segments=12, height_segments=8):
    return {
        'type': 'sphere',
        'radius': num(radius),
        'widthSegments': int(width_segments),
        'heightSegments': int(height_segments),
    }


def cone(radius, height, segments=8):
    return {
        'type': 'cone',
        'radius': num(radius),
        'height': num(height),
        'radialSegments': int(segments),
    }


def torus(radius, tube, radial=8, tubular=16):
    return {
        'type': 'torus',
        'radius': num(radius),
        'tube': num(tube),
        'radialSegments': int(radial),
        'tubularSegments': int(tubular),
    }


def lathe(points, segments=12):
    return {
        'type': 'lathe',
        'points': [[num(radius), num(y)] for radius, y in points],
        'segments': int(segments),
    }


def tube(start, control, end, radius, tubular=16, radial=8):
    return {
        'type': 'tube',
        'curve': {
            'type': 'quadratic',
            'from': vec(*start),
            'control': vec(*control),
            'to': vec(*end),
        },
        'radius': num(radius),
        'tubularSegments': int(tubular),
        'radialSegments': int(radial),
    }


def blade(length, base_width, tip_width, thickness, fuller=0, segments=6):
    return {
        'type': 'blade',
        'length': num(length),
        'baseWidth': num(base_width),
        'tipWidth': num(tip_width),
        'thickness': num(thickness),
        'fuller': num(fuller),
        'segments': int(segments),
    }


def shield_face(outline, width, height, thickness):
    return {
        'type': 'shield',
        'outline': outline,
        'width': num(width),
        'height': num(height),
        'thickness': num(thickness),
    }


def ring(name, material, radius, tube, y, materials):
    """A band around the Y axis. A torus is built in the XY plane, so it is tipped flat."""
    take(materials, material)
    return part(name, material, torus(radius, tube, 6, 14), (0, y, 0), (90, 0, 0))


def add_grip(parts, materials, rng, length, radius, y0, wood, metal, tier):
    """A turned haft from y0 upward, with wraps, a collar, and a pommel below y0.

    Returns the Y where the working end begins. Tier changes fittings only, so it
    does not draw extra random numbers.
    """
    flare = radius * 1.2
    parts.append(part('grip', wood, lathe((
        (radius * 0.72, 0),
        (radius * 1.08, length * 0.14),
        (radius * 0.9, length * 0.48),
        (radius * 1.02, length * 0.8),
        (flare, length),
    ), 12), (0, y0, 0)))
    wraps = 2 if rng.random() < 0.55 else 1
    if tier >= 2:
        wraps = min(3, wraps + 1)
    for index in range(wraps):
        along = (index + 1) / (wraps + 1)
        parts.append(ring(f'wrap{index + 1}', 'cord', radius * 1.2, max(0.004, radius * 0.28), y0 + length * along, materials))
    collar_h = max(0.014, length * 0.12)
    parts.append(part('collar', metal, cylinder(radius * 1.25, radius * 1.4, collar_h, 12), (0, y0 + length - collar_h * 0.35, 0)))
    parts.append(part('pommel', metal, sphere(radius * 1.35, 10, 8), (0, y0 - radius * 0.85, 0)))
    if tier >= 3:
        parts.append(part(
            'pommelCap', metal,
            cylinder(radius * 0.55, radius * 0.85, max(0.012, radius * 0.7), 10),
            (0, y0 - radius * 2.15, 0),
        ))
    if tier >= 5:
        parts.append(ring('inlay', 'gold', radius * 1.28, max(0.0035, radius * 0.14), y0 + length * 0.5, materials))
    return y0 + length
