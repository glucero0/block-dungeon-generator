"""The one flame the game spawns.

A campfire pit and a wall torch carry the same particles and the same light.
The pit also names the mesh the fire sits in. There is no small or large variant.
"""

CAMPFIRE_PREFAB = 'prefabs/campfire_lit.glb'


def flame():
    """A fresh copy, so one placement cannot change another."""
    return {
        'vfx': {
            'type': 'particle-system',
            'preset': 'campfire_flames',
            'emitter': {
                'rate': 30,
                'lifetime': [0.6, 1.2],
                'colorStart': '#ffaa22',
                'colorEnd': '#220500',
                'blendMode': 'additive',
            },
        },
        'light': {
            'type': 'point',
            'color': '#ff7a18',
            'intensity': 2.5,
            'distance': 8.0,
            'flicker': {
                'speed': 12.0,
                'variance': 0.4,
            },
        },
    }
