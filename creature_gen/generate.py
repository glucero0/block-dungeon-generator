"""Build one creature from a species and a seed."""

from .humanoid import build_humanoid
from .quadruped import build_quadruped
from .schema import validate
from .species import SPECIES


def generate_creature(species, seed):
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError('seed must be zero or greater')
    if species not in SPECIES:
        raise ValueError('species is not in the roster')
    if SPECIES[species]['plan'] == 'humanoid':
        creature = build_humanoid(species, seed)
    else:
        creature = build_quadruped(species, seed)
    return validate(creature)
