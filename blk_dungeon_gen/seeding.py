"""Independent random streams, so one feature never shifts another feature's output."""

import random


def sub_rng(seed, *parts):
    """A `random.Random` keyed on the layout seed plus a feature name and index.

    String seeds are hashed with SHA-512 by `random`, so the stream is the same on
    every run and platform. Procedural generation only; this is not for secrets.
    """
    key = ':'.join([str(int(seed) & 0xFFFFFFFF)] + [str(part) for part in parts])
    return random.Random(key)
