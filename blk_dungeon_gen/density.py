"""How many enemy spawns each room gets.

The count starts from the room's size, is scaled by the `--density` setting, and
then by how deep the room sits: rooms near the entrance are a little quieter and
the deepest rooms a little busier. The exit gets one extra guard.
"""

DENSITY = {'low': 0.5, 'normal': 1.0, 'high': 1.5}

# Multiplier at the entrance and at the deepest room. Rooms in between are linear.
DEPTH_NEAR = 0.75
DEPTH_FAR = 1.25
EXIT_GUARDS = 1
MAX_SPAWNS = 8


def depth_fractions(layout):
    """Map `id(block)` to 0.0 (entrance) .. 1.0 (farthest block by door count)."""
    neighbors = {id(block): [] for block in layout.blocks}
    for link in layout.links:
        neighbors[id(link.parent)].append(link.child)
        neighbors[id(link.child)].append(link.parent)
    start = layout.blocks[0]
    distance = {id(start): 0}
    queue = [start]
    while queue:
        current = queue.pop(0)
        for nxt in neighbors[id(current)]:
            if id(nxt) not in distance:
                distance[id(nxt)] = distance[id(current)] + 1
                queue.append(nxt)
    farthest = max(distance.values()) or 1
    return {key: value / farthest for key, value in distance.items()}


def base_spawns(block):
    if block.block in ('entrance', 'stairwell', 'doorway'):
        return 0
    area = block.rect.w * block.rect.d
    if block.kind == 'chamber':
        if area < 420:
            return 2
        if area < 780:
            return 3
        if area < 1200:
            return 4
        return 5
    if block.run >= 16 and area >= 90:
        return 2 if area > 180 else 1
    return 0


def spawn_count(block, density, depth):
    """Spawns wanted for `block`. `depth` is its 0..1 fraction from `depth_fractions`."""
    base = base_spawns(block)
    if base == 0:
        return 0
    factor = DENSITY[density] * (DEPTH_NEAR + (DEPTH_FAR - DEPTH_NEAR) * depth)
    count = int(base * factor + 0.5)
    if block.kind == 'chamber':
        count = max(1, count)
    if block.block == 'exit':
        count += EXIT_GUARDS
    return min(count, MAX_SPAWNS)
