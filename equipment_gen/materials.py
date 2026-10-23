"""Named colours for a recipe. Parts refer to these keys."""

PALETTE = {
    'iron': {'color': '#8b939c', 'roughness': 0.45, 'metalness': 0.82},
    'bronze': {'color': '#a56b3c', 'roughness': 0.42, 'metalness': 0.74},
    'steel': {'color': '#d5dde4', 'roughness': 0.32, 'metalness': 0.88},
    'oak': {'color': '#8a5a32', 'roughness': 0.78, 'metalness': 0.04},
    'ash': {'color': '#c4a574', 'roughness': 0.72, 'metalness': 0.04},
    'leather': {'color': '#6b4634', 'roughness': 0.84, 'metalness': 0.02},
    'rust': {'color': '#6d5848', 'roughness': 0.7, 'metalness': 0.35},
    'gold': {'color': '#d4af37', 'roughness': 0.35, 'metalness': 0.9},
    'cord': {'color': '#a89878', 'roughness': 0.88, 'metalness': 0.0},
    'cloth': {'color': '#5c4033', 'roughness': 0.9, 'metalness': 0.0},
}

METAL_TITLE = {'iron': 'Iron', 'bronze': 'Bronze', 'steel': 'Steel'}
WOOD_TITLE = {'oak': 'Oak-gripped', 'ash': 'Ash-gripped'}
KIND_TITLE = {
    'sword': 'Sword',
    'shield': 'Shield',
    'torch': 'Torch',
    'mace': 'Mace',
    'axe': 'Axe',
    'hammer': 'Hammer',
    'spear': 'Spear',
    'dagger': 'Dagger',
    'bow': 'Bow',
}
MOTIF_TITLE = {
    'bar': 'Straight',
    'winged': 'Winged',
    'disc': 'Disced',
    'flanged': 'Flanged',
    'spiked': 'Spiked',
    'knobbed': 'Knobbed',
    'single': 'One-bitted',
    'double': 'Double-bitted',
    'war': 'Spiked',
    'mallet': 'Mallet',
    'leaf': 'Leaf-headed',
    'spike': 'Spiked',
    'short': 'Short',
    'long': 'Long',
    'round': 'Round',
    'heater': 'Heater',
    'tower': 'Tower',
    'cup': 'Cupped',
    'cage': 'Caged',
    'brand': 'Brand',
}


def take(materials, name):
    """Copy one palette entry into the item. Later edits cannot change the palette."""
    if name not in PALETTE:
        raise ValueError(f'unknown material {name}')
    if name not in materials:
        source = PALETTE[name]
        materials[name] = {
            'color': source['color'],
            'roughness': source['roughness'],
            'metalness': source['metalness'],
        }
    return name


def item_name(wood, metal, motif, kind):
    return f'{WOOD_TITLE[wood]} {METAL_TITLE[metal]} {MOTIF_TITLE[motif]} {KIND_TITLE[kind]}'
