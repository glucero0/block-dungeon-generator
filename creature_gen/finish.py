"""Shared file fields: the skeletal warrior stats, plus a small seed nudge."""

from .species import SPECIES, WEAPONS, stat_block


def _nudge_int(rng, base, spread, low, high):
    shifted = int(round(base + (rng.random() * 2 - 1) * spread))
    return max(low, min(high, shifted))


def _nudge_speed(rng, base, spread):
    shifted = base + (rng.random() * 2 - 1) * spread
    return round(max(0.2, min(20.0, shifted)), 2)


def assemble(species_id, seed, rng, name, materials, joints, parts):
    """Stats and weapons around a built body. Health, damage, and speed take the nudge."""
    spec = SPECIES[species_id]
    stats = stat_block(spec['stats'])
    stats['health'] = _nudge_int(rng, stats['health'], 3, 1, 400)
    stats['damage'] = _nudge_int(rng, stats['damage'], 1, 1, 80)
    stats['moveSpeed'] = _nudge_speed(rng, stats['moveSpeed'], 0.15)
    creature = {
        'name': name,
        'description': spec['description'],
        'species': species_id,
        'seed': seed,
        'plan': spec['plan'],
        'scale': spec['scale'],
        'options': {'species': species_id, 'seed': seed},
        'stats': stats,
        'materials': materials,
        'joints': joints,
        'parts': parts,
    }
    if spec['plan'] == 'humanoid':
        creature['weapons'] = [{'id': item['id'], 'range': item['range']} for item in WEAPONS]
    return creature
