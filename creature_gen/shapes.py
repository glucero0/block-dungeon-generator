"""Closed shapes in game units. A capsule is the skeletal warrior long bone."""


def num(value):
    return round(float(value), 4)


def vec(x, y, z):
    return [num(x), num(y), num(z)]


def joint(name, parent, position, rotation=None):
    record = {'name': name, 'parent': parent, 'position': vec(*position)}
    if rotation is not None:
        record['rotation'] = {
            'x': num(rotation[0]),
            'y': num(rotation[1]),
            'z': num(rotation[2]),
            'unit': 'degrees',
        }
    return record


def part(name, joint_name, material, geometry, position, rotation=None):
    record = {
        'name': name,
        'joint': joint_name,
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


def sphere(radius, width_segments=10, height_segments=8):
    return {
        'type': 'sphere',
        'radius': num(radius),
        'widthSegments': int(width_segments),
        'heightSegments': int(height_segments),
    }


def cylinder(radius_top, radius_bottom, height, segments=8):
    return {
        'type': 'cylinder',
        'radiusTop': num(radius_top),
        'radiusBottom': num(radius_bottom),
        'height': num(height),
        'radialSegments': int(segments),
    }


def capsule(radius, length, cap_segments=2, radial_segments=6):
    """`length` is the cylindrical middle, matching Three.js CapsuleGeometry."""
    return {
        'type': 'capsule',
        'radius': num(radius),
        'length': num(max(0.04, length)),
        'capSegments': int(cap_segments),
        'radialSegments': int(radial_segments),
    }


def cone(radius, height, segments=6):
    return {
        'type': 'cone',
        'radius': num(radius),
        'height': num(height),
        'radialSegments': int(segments),
    }


def torus(radius, tube, radial=6, tubular=12):
    return {
        'type': 'torus',
        'radius': num(radius),
        'tube': num(tube),
        'radialSegments': int(radial),
        'tubularSegments': int(tubular),
    }


def long_bone(total, radius):
    """A bone whose overall length is `total`, the way skeleton.js builds longBone."""
    middle = max(0.04, total - radius * 2)
    return capsule(radius, middle)
