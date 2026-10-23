# blk-dungeon-gen

A Python generator that snaps dungeon blocks into the Ancient Ruins JSON used by the Harper's Row game (`../harpers-row`). The file has the same rooms, doors, arch, trail, trees, and zone transitions as `ancientRuinsData.json`, plus a floor height on every room so stairwells can stack stories.

The generator uses only the Python standard library.

## Blocks

North is the deeper ruin (`-Z`). The arch stays on the south edge of the entrance.

- **Entrance** — the antechamber under the arch. Walking back out through it returns to the trail.
- **Exit** — the last chamber. Clearing it finishes the descent. It is not a second door to the outdoors.
- **Small room** and **big room** — chambers. A doorway block sits between a passage and a room.
- **Hallway** — a 6 by 16 metre passage. Two hallways joined end to end share a full-width opening.
- **Doorway** — a short 6 by 4 metre neck. The opening on the room side is narrower than the hall side.
- **Hub** — a square chamber with three openings: one stem and two opposite arms, a T.
- **Stairwell** — one shaft that spans two stories. The lower door is at that story's floor and the upper door is 10 metres higher, on the opposite end.

## Run

```bash
python -m blk_dungeon_gen --seed 1 --floors 2 --chambers 8 -o out/ruins.json
```

`--chambers` counts the entrance, the exit, hubs, and other rooms. Hallways, doorways, and stairwells are added as the links between them. `--floors` is the number of stories (1 to 8). The same seed always writes the same file.

To play a layout, copy the JSON over `src/ancientRuinsData.json` in Harper's Row. The game draws each room at its `y`, and a stairwell ramps from `stair.fromY` to `stair.toY`. A room with no `y` is still the ground floor, so the original baked ruins load unchanged.

## Test

```bash
python -m unittest discover -s tests -v
```
