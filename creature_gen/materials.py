"""Named colours. A creature copies the ones it uses into its file."""

PALETTE = {
    'bone': {'color': '#e4dcc8', 'roughness': 0.72, 'metalness': 0.04},
    'boneash': {'color': '#c9c1ad', 'roughness': 0.78, 'metalness': 0.05},
    'bonedark': {'color': '#b3a890', 'roughness': 0.8, 'metalness': 0.06},
    'socket': {'color': '#1c140f', 'roughness': 0.9, 'metalness': 0.02},
    'ember': {'color': '#ff6a1a', 'roughness': 0.4, 'metalness': 0.0},
    'iron': {'color': '#8b939c', 'roughness': 0.45, 'metalness': 0.82},
    'leather': {'color': '#6b4634', 'roughness': 0.84, 'metalness': 0.02},
    'fair': {'color': '#e6b898', 'roughness': 0.72, 'metalness': 0.0},
    'tan': {'color': '#c48a62', 'roughness': 0.74, 'metalness': 0.0},
    'olive': {'color': '#a67c52', 'roughness': 0.76, 'metalness': 0.0},
    'brown': {'color': '#8a5a3b', 'roughness': 0.78, 'metalness': 0.0},
    'deep': {'color': '#5c3a2e', 'roughness': 0.8, 'metalness': 0.0},
    'pale': {'color': '#d7d0c4', 'roughness': 0.7, 'metalness': 0.0},
    'moss': {'color': '#6f8f4e', 'roughness': 0.78, 'metalness': 0.0},
    'lime': {'color': '#8faf62', 'roughness': 0.76, 'metalness': 0.0},
    'pine': {'color': '#4f6b3a', 'roughness': 0.8, 'metalness': 0.0},
    'sage': {'color': '#7d8a72', 'roughness': 0.78, 'metalness': 0.0},
    'slate': {'color': '#6e7c74', 'roughness': 0.76, 'metalness': 0.02},
    'black': {'color': '#1c140f', 'roughness': 0.85, 'metalness': 0.0},
    'auburn': {'color': '#7a3b24', 'roughness': 0.82, 'metalness': 0.0},
    'blonde': {'color': '#d8c07a', 'roughness': 0.74, 'metalness': 0.0},
    'white': {'color': '#efeae2', 'roughness': 0.7, 'metalness': 0.0},
    'russet': {'color': '#8c3d32', 'roughness': 0.88, 'metalness': 0.0},
    'navy': {'color': '#2c3d55', 'roughness': 0.88, 'metalness': 0.0},
    'forest': {'color': '#3d5344', 'roughness': 0.9, 'metalness': 0.0},
    'sand': {'color': '#b9a07a', 'roughness': 0.9, 'metalness': 0.0},
    'grey': {'color': '#8a8680', 'roughness': 0.86, 'metalness': 0.0},
    'furgrey': {'color': '#8d8a84', 'roughness': 0.9, 'metalness': 0.0},
    'furbrown': {'color': '#6b4a32', 'roughness': 0.9, 'metalness': 0.0},
    'furblack': {'color': '#2a2724', 'roughness': 0.92, 'metalness': 0.0},
    'furtawny': {'color': '#c4a36a', 'roughness': 0.88, 'metalness': 0.0},
}

TONE_TITLE = {
    'bone': 'Pale',
    'boneash': 'Ash',
    'bonedark': 'Dark',
    'fair': 'Fair',
    'tan': 'Tan',
    'olive': 'Olive',
    'brown': 'Brown',
    'deep': 'Deep',
    'pale': 'Pallid',
    'moss': 'Moss',
    'lime': 'Lime',
    'pine': 'Pine',
    'sage': 'Sage',
    'slate': 'Slate',
    'black': 'Black',
    'auburn': 'Auburn',
    'blonde': 'Blonde',
    'white': 'White',
    'furgrey': 'Grey',
    'furbrown': 'Brown',
    'furblack': 'Black',
    'furtawny': 'Tawny',
}

HAIR_TITLE = {'cap': 'Short-haired', 'long': 'Long-haired', 'hood': 'Hooded'}


def paint(materials, role, variant):
    """Copy one palette entry under a role name such as skin or fur."""
    if variant not in PALETTE:
        raise ValueError(f'unknown material {variant}')
    source = PALETTE[variant]
    materials[role] = {
        'color': source['color'],
        'roughness': source['roughness'],
        'metalness': source['metalness'],
    }
    return role


_FUR_PATTERNS = ('solid', 'agouti', 'brindle', 'patch')


def _scale_hex(color, factor):
    value = int(color[1:], 16)
    channels = []
    for shift in (16, 8, 0):
        channel = (value >> shift) & 255
        channels.append(max(0, min(255, int(round(channel * factor)))))
    return '#{:02x}{:02x}{:02x}'.format(*channels)


def fur_coat(materials, tone, rng, coat_units):
    """Fur colour, tip, pattern, and length. `coat_units` is the species length before the seed."""
    paint(materials, 'fur', tone)
    coat = materials['fur']
    coat['color'] = _scale_hex(coat['color'], 0.82 + rng.random() * 0.36)
    lighter = rng.random() < 0.65
    factor = (1.25 + rng.random() * 0.7) if lighter else (0.28 + rng.random() * 0.3)
    coat['tip'] = _scale_hex(coat['color'], factor)
    coat['pattern'] = _FUR_PATTERNS[rng.randrange(len(_FUR_PATTERNS))]
    coat['length'] = round(coat_units * (0.65 + rng.random() * 0.7), 4)
    return coat


def wolf_coat(materials, tone, rng, coat_units):
    """Grizzle, tan tips, and a cream belly. Roughness stays in the fur range."""
    paint(materials, 'fur', tone)
    coat = materials['fur']
    coat['color'] = _scale_hex(coat['color'], 0.85 + rng.random() * 0.3)
    tans = ('#b08968', '#c4a574', '#8d7355', '#d9c4a0')
    creams = ('#f3ead8', '#e6d7c3', '#f7f1e6', '#ddcfb8')
    coat['tip'] = _scale_hex(tans[rng.randrange(len(tans))], 0.9 + rng.random() * 0.25)
    coat['belly'] = creams[rng.randrange(len(creams))]
    coat['pattern'] = _FUR_PATTERNS[rng.randrange(len(_FUR_PATTERNS))]
    coat['roughness'] = round(0.86 + rng.random() * 0.09, 2)
    coat['metalness'] = 0.0
    coat['length'] = round(coat_units * (0.65 + rng.random() * 0.7), 4)
    return coat
