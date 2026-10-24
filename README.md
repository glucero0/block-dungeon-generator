# blk-dungeon-gen

A Python generator that snaps dungeon blocks into the Ancient Ruins JSON used by the Harper's Row game (`../harpers-row`). The file has the same rooms, doors, arch, trail, trees, and zone transitions as `ancientRuinsData.json`, plus a floor height on every room so stairwells can stack stories. With `--hub` it writes a small starting hub instead, with one structure and named paths for the game to connect to other locations.

The generator uses only the Python standard library. A second command, `equipment_gen`, writes held equipment. A third, `creature_gen`, writes creatures on the Harper's Row skeletal warrior template. See [Equipment](#equipment) and [Creatures](#creatures).

## Blocks

North is the deeper ruin (`-Z`). The arch stays on the south edge of the entrance.

- **Entrance** — the antechamber under the arch. Walking back out through it returns to the trail.
- **Exit** — the last chamber. Clearing it finishes the descent. A gate in that chamber opens onto an outdoor exit trail.
- **Small room** and **big room** — chambers. A doorway block sits between a passage and a room.
- **Hallway** — a 6 by 16 metre passage. Two hallways joined end to end share a full-width opening.
- **Doorway** — a short 6 by 4 metre neck. The opening on the room side is narrower than the hall side.
- **Hub** — a square chamber with three openings: one stem and two opposite arms, a T.
- **Stairwell** — one shaft that spans two stories. The lower door is at that story's floor and the upper door is 10 metres higher, on the opposite end.

## Run

```bash
python -m blk_dungeon_gen --seed 1 --floors 2 --chambers 8 --density normal --clutter 0.5 -o out/ruins.json
```

| Option | Default | Meaning |
| --- | --- | --- |
| `--seed` | `1` | Layout seed, zero or greater. |
| `--floors` | `2` | Number of stories, 1 to 8. |
| `--chambers` | `8` | Counts the entrance, the exit, hubs, and other rooms, 2 to 30. Hallways, doorways, and stairwells are added as the links between them. |
| `--density` | `normal` | Enemy spawns: `low`, `normal`, or `high`. |
| `--clutter` | `0.5` | Room props and outdoor scenery, from `0` (none) to `1` (most). |
| `--hub` | off | Write a starting hub instead of ruins. See [Hub](#hub). `--floors`, `--chambers`, and `--density` are ignored in this mode. |
| `--structure` | from the seed | Hub only: `hut`, `house`, `tent`, `campfire`, or `castle`. |
| `--spokes` | `3` | Hub only: number of paths leaving the hub, 1 to 8. Defaults to the number of `--spoke` names when you give any. |
| `--spoke` | none | Hub only: name a path, for example `--spoke ruins`. Repeat it for more paths. |
| `-o`, `--output` | required | JSON file to write. |

The same seed and the same options always write the same file, so keep the options with the seed if you want to regenerate a file. Changing `--density` or `--clutter` leaves the rooms, doors, themes, sconces, and trees where they were. Only the spawns, props, and scenery change.

### Enemies

Each chamber starts from a count based on its size, scaled by `--density` (low 0.5, normal 1, high 1.5). The count then scales with depth: rooms next to the entrance get about 0.75 times as many, and the deepest room about 1.25 times. Every chamber except the entrance keeps at least one spawn, and the exit gets one extra guard. Long hallways can hold a spawn too. The entrance, doorways, and stairwells never do. Spawns are `[x, z]` points in each room's `spawns`; the game picks what appears.

### Props and outdoor scenery

- **Room props** — each chamber has a `props` list of `{type, x, z, rotationY, scale}`. The type follows the room's theme: urns, caskets, broken pillars, and rubble for stone; barrels, crates, shelves, and plank piles for wood; stalagmites, bone piles, and rubble for cave. `rotationY` is a yaw in radians where 0 faces +Z. Wall props face into the room. Props keep clear of doors, the walkway between doors, spawns, the chest, and the sconce. Cave rooms keep their `rocks`.
- **Fire** — a wall sconce and a campfire pit carry the same flame, so the game can spawn it. `vfx` is a particle system (`preset`, `emitter` rate, lifetime, colours, and blend mode) and `light` is a flickering point light (colour, intensity, distance). There is one flame, not a small or large variant. A sconce is still `{x, z, nx, nz}` plus that flame. The campfire pit also has `y`, `radius`, and `prefab`.
- **The approach** — the trail's bend direction and amount, its length, and the tree count all change with the seed. A top-level `scenery` list holds ruin dressing in one of four moods, named in `approach.dressing`: `overgrown`, `graveyard`, `fallen-hall`, or `abandoned-camp`. Scenery stays out of the trail and the arch's door lane.
- **Options** — the top-level `options` object records the `density` and `clutter` used.

The exit chamber has an `exitGate` on a wall that does not face another room. `exitArea` is an outdoor zone to the west of the ruins, built the same way as the entrance: a stone arch, a worn path, trees, shrubs and rocks, and a mountain vista. Fade transitions `ruin-leave` and `ruin-return` join the gate to that trail (`ruin-leave` carries `y` and `floor`, so the trigger sits on the exit chamber's story), and `exit-pass` continues toward the same distant pass as the entrance. The exit trail's zone ids are `exit-trail` and `exit-pass`.

To play a layout, copy the JSON over `src/ancientRuinsData.json` in Harper's Row. The game draws each room at its `y`, and a stairwell ramps from `stair.fromY` to `stair.toY`. A room with no `y` is still the ground floor, so the original baked ruins load unchanged.

## Hub

A hub is a small, safe starting place for a game. It has one structure on a round plaza, a point where the player spawns when a game starts and again after a death, and named paths (spokes) leaving the plaza. The game loads the hub and connects each spoke to another location.

```bash
python -m blk_dungeon_gen --hub --seed 1 --structure house --spoke ruins --spoke forest -o out/hub.json
```

- **Structure** — one of `hut` (low hip roof), `house` (pitched roof), `tent` (canvas cone), `campfire` (fire ring with log seats and no roof), or `castle` (keep with four corner towers). With no `--structure`, the seed picks the type, so each seed gives a different kind of hub. Size and position vary with the seed. The structure types are a table in `blk_dungeon_gen/structures.py`, so a new type is one new entry. The hut, house, tent, and castle each have one interior room in `rooms` (with a sconce and props that match its theme) and a door in `entrance`. The campfire has no room. Its `fire-pit` part is the same flame as a sconce, plus `prefab` (`prefabs/campfire_lit.glb`), `y`, and `radius`.
- **Respawn** — `hubArea.respawn` is `{x, y, z, yaw}`. `start` has the same `x`, `z`, and `yaw`, so code that reads `start` still works. `yaw` follows the `start` convention: 0 faces `-Z`.
- **Spokes** — `hubArea.spokes` lists each path with its `name`, `width`, `length`, centreline `samples`, `polygon`, `mouth` (where it leaves the plaza), and `end` (where it stops). The paths are spread around the plaza and stay clear of the structure. Each spoke is a short stub, so the game attaches the rest of the way to the location it names. Past that end, `vista` continues the path as it narrows, with scrub and dead trees. `hubArea.mountains` is a ring of distant peaks around the whole hub, and `hubArea.environment` is the daylight sky.
- **Names** — spoke names use lowercase letters, digits, and single hyphens, 1 to 32 characters, and must be unique. `hub` and `hub-interior` are reserved. Spokes without a name are called `spoke-1`, `spoke-2`, and so on. Bad names, counts, or structure types stop the run with an error.
- **Transitions** — each spoke has two entries in `transitions`, in the same format as the ruin's transitions. `to-<name>` leaves the hub: `sourceZoneId` is `hub`, `targetZoneId` is the spoke name, `volume` is the trigger at the end of the path, and `targetSpawnPoint` is `null` for the game to fill in. `from-<name>` arrives from that location: `sourceZoneId` is the spoke name, `targetZoneId` is `hub`, `targetSpawnPoint` is a point on the path facing the plaza, and `volume` is `null` because the trigger belongs to the other zone. The enterable structures also have `structure-entry` and `structure-exit` between zones `hub` and `hub-interior`.
- **Scenery** — `trees` and `scenery` surround the plaza and stay off the spokes. Each spoke has a `signpost` in `scenery` labelled with its name. `--clutter` scales the other scenery and the room props.
- **Other fields** — the file also has `kind: 'hub'`, `areaName: 'The Hub'`, `floors: 1`, an empty `doors`, a `structure` object (type, roof, material, footprint, parts, door), and `options` with the `clutter`, `structure`, and `spokes` used. It has no `exterior`, `approach`, or `lastRoomId`.

Forcing a different `--structure` changes more than the building. The plaza and the spokes are laid out around it, so they move too. The same seed, structure, and spoke names always write the same file.

## Equipment

`equipment_gen` writes one held item: a sword, shield, torch, mace, axe, hammer, spear, dagger, or bow. The file is a version 1 recipe of named parts (a grip, a blade, a boss, and so on), materials, and a grip rotation. Harper's Row does not build the mesh from these files yet. A torch is the exception for fire: its `TorchTipSocket` carries the same `vfx` and `light` as a wall sconce and the campfire pit, so the game can spawn that flame in the cup and the light from it. The torch does not include the campfire prefab.

```bash
python -m equipment_gen --seed 1 --kind sword --tier 2 -o out/sword.json
python -m equipment_gen --seed 1 --tier 1 --all -o out/equipment
```

| Option | Default | Meaning |
| --- | --- | --- |
| `--seed` | `1` | Item seed, zero or greater. |
| `--kind` | required | `sword`, `shield`, `torch`, `mace`, `axe`, `hammer`, `spear`, `dagger`, or `bow`. |
| `--tier` | `1` | Ornament and a small bump to damage and reach, 1 to 5. |
| `--all` | off | Write every kind into the `-o` directory, one `<kind>.json` each. |
| `-o`, `--output` | required | JSON file to write, or a directory with `--all`. |

The same seed, kind, and tier always write the same file. Those three values are stored in `options`. Changing the tier keeps the same name and motif and adds fittings: an extra wrap from tier 2, a pommel cap from tier 3, and a thin inlay at tier 5. Weapons and the bow also record `combat` (range, arc, damage, attack interval). A shield and a torch do not.

The grip sits near the origin and the working end runs toward `+Y`. The right hand holds the sword, mace, axe, hammer, spear, dagger, and bow. The left hand holds the torch and the shield.

Each part is a closed shape: `box`, `cylinder`, `sphere`, `cone`, `torus`, `plane`, `lathe`, `tube`, `blade`, or `shield`. A `blade` is a tapered diamond section. A `shield` is a `round`, `heater`, or `tower` face. A `tube` is a quadratic curve, used for the bow stave and string. A socket is a part with `type: group` and no mesh. Only that socket may carry `vfx` and `light`, and on a torch those two objects are the campfire flame from `blk_dungeon_gen/fire.py`.

`equipment-visualizer.html` is a standalone preview, on the same pattern as the dungeon viewer. It has no build step. Open it in a browser, and it shows a built-in sword. Upload a file, drop one onto the page, or open **JSON**, paste a recipe, and apply it. Drag to orbit, scroll to zoom, and right-drag to pan. The part list and a click on the mesh show that part's JSON. A torch draws the point light and a small flame at `TorchTipSocket`. The particle system itself is left for the game. A file that is not valid JSON shows an error and leaves the current item in place.

If the view shows a blank page because the browser blocked a module load from `file://`, serve the folder:

```bash
python -m http.server 8000
```

Then browse to `http://localhost:8000/equipment-visualizer.html`.

## Creatures

`creature_gen` writes one creature. The `stats` object uses the same fields as Harper's Row `content/creatures/skeletelWarrior.json`: `health`, `damage`, `moveSpeed`, `wanderFactor`, `radius`, `sightRange`, `windup`, `recover`, `minWindup`, and `minRecover`. A humanoid also has `weapons`. Each weapon id is `sword`, `mace`, `hammer`, or `bow`, with a range. The game reads those fields for the skeletal warrior. Joints and parts are stored beside them, in game units (3.2 units to a metre), for the preview.

```bash
python -m creature_gen --seed 1 --species skeleton -o out/skeleton.json
python -m creature_gen --seed 1 --all -o out/creatures
```

| Option | Default | Meaning |
| --- | --- | --- |
| `--seed` | `1` | Creature seed, zero or greater. |
| `--species` | required | `skeleton`, `human`, `goblin`, `orc`, `elf`, `dwarf`, `zombie`, `wolf`, `bear`, `boar`, `horse`, `deer`, or `rat`. |
| `--all` | off | Write every species into the `-o` directory, one `<species>.json` each. |
| `-o`, `--output` | required | JSON file to write, or a directory with `--all`. |

The same seed and species always write the same file. Those two values are stored in `options`. The seed changes colours and extra meshes such as hair and cloth. On a quadruped it also changes the fur colour, the tip colour, the pattern, and the fur length. Humanoid joint positions stay on the skeletal warrior rig multiplied by `scale`. Scale 1 matches the game: the pelvis is at y `2.95`, the spine joint at y `3.05`, the skull at y `1.16`, and the hips at y `2.9`. `+Y` is up and the figure faces `+Z`.

Humanoids are `skeleton`, `human`, `goblin`, `orc`, `elf`, `dwarf`, and `zombie`. They share `fall`, `spine`, `skull`, `SkeletonArm_R` and `SkeletonArm_L`, `Forearm_R` and `Forearm_L`, `WristJoint_R` and `WristJoint_L`, `HandSocket_R` and `HandSocket_L`, `Hip_L` and `Hip_R`, and `Knee_L` and `Knee_R`. A skeleton is bone, with ember eyes and an iron scrap, and has no skin or hair. A human has skin, hair, and clothes. A goblin is shorter, with large ears and rags. The hand sockets are empty. Weapon meshes stay in the game, which seats them on those sockets.

Quadrupeds are `wolf`, `bear`, `boar`, `horse`, `deer`, and `rat`. Scale is 1, and the body is measured in metres times 3.2. A horse stands about 1.6 m at the withers, with a 2.4 m torso. A rat stands about 0.1 m, with a 0.25 m torso. The torso is two capsules along `Z`: a broader chest and a narrower pelvis. The neck is a cylinder, wider at the shoulder, pitched forward and up. The head is a capsule, with a jaw capsule, a snout cone, two ear cones, and a pair of inset eye spheres. Each leg has `Hip_*`, `Knee_*`, and `Ankle_*` for `FL`, `FR`, `BL`, and `BR`, and the parts are an upper bone, a lower bone, a cannon, and a foot. The hind lower bone sets the hock back. A hoof uses the socket material, and a paw uses fur. The tail is a chain of capsules on `tail`, drooping toward the ground. A horse adds a mane of draped capsules. A deer has antlers and a boar has tusks. They have fur and omit `weapons`, so the current Harper's Row loader would reject one of these files in place of the skeletal warrior. The `fur` material adds `length` (game units), `tip` (`#rrggbb`), and `pattern` (`solid`, `agouti`, `brindle`, or `patch`). Length starts from the species coat, about 10 cm for a bear, 1.8 cm for a horse, and 0.6 cm for a rat, then the seed scales it between 0.65 and 1.35. The preview paints a strand texture on the other coats. A wolf coat carries `belly` as well, and the preview displaces that fur with simplex noise — longer on the neck, belly, and tail — using a rough non-metallic shader and a soft sheen. There is no outer shell. Hooves, eyes, antlers, and tusks stay smooth. A wolf carries its head low: the neck pitches past horizontal, the chest is a deep barrel, the abdomen tucks up into a lean pelvis, the hind hock sits low, and the tail is thick at the base and hangs.

`creature-visualizer.html` is a standalone preview, on the same pattern as the equipment viewer. It has no build step. Open it in a browser, and it shows a built-in skeletal warrior. Upload a file, drop one onto the page, or open **JSON**, paste a creature, and apply it. Drag to orbit, scroll to zoom, and right-drag to pan. The figure walks. A humanoid also plays a strike, using the same joint rotations as the game: torso `tx` and `ty`, shoulder `sx`, `sy`, and `sz`, elbow `ex`, wrist `wx`, hip and knee x, and the fall bob. A quadruped trots. The part list and a click on the mesh show that part's JSON. The sidebar shows species, scale, stats, and weapons. A stand-in blade in the right hand is drawn for a humanoid and is not written into the file. A file that is not valid JSON shows an error and leaves the current creature in place.

If the view shows a blank page because the browser blocked a module load from `file://`, serve the folder:

```bash
python -m http.server 8000
```

Then browse to `http://localhost:8000/creature-visualizer.html`.

## View a layout

`dungeon-visualizer.html` is a standalone viewer called Dungeon Cartographer. Use it to look at the JSON this generator writes, with no game needed. It has no build step and no install.

1. Generate a layout, for example `python -m blk_dungeon_gen --seed 1 --floors 2 --chambers 8 -o out/ruins.json`.
2. Open `dungeon-visualizer.html` in a modern browser. Double-clicking the file is enough, and no web server is needed.
3. Load your file with any of these:
   - **Upload .json** in the top bar.
   - Drag the file anywhere onto the page.
   - **JSON Drawer** to paste or edit JSON, then apply it.
   - **Load Sample Ruins** to see the built-in example.

A file that is not valid JSON shows an error message and leaves the current map in place.

### What you can do

- **Plan and 3D** — the `Plan` and `3D` buttons switch views. Plan is a top-down map with a 1 metre grid. 3D is an orbit view you can rotate, pan, and zoom. In 3D each story sits at its real height, 10 metres apart, and a stairwell is drawn as a ramp from `stair.fromY` to `stair.toY`.
- **Floors** — when a file has more than one floor, a floor selector (`All`, `F1`, `F2`, ...) appears next to the view buttons. Pick a floor to show only that story in both views. A stairwell shows on both floors it joins. The trail and scenery show on `All` and `F1`. Zone triggers follow their own floor, so the exit gate's trigger stays with the exit chamber. In Plan, `All` draws every floor on one map, so rooms on different stories can overlap; pick a floor to separate them.
- **Entrance and exit** — the antechamber is outlined in green and the final chamber in gold, each with an `ENTRANCE` or `EXIT` badge that stays visible when zoomed out. In 3D each has a coloured light beam and a floating label. The **Landmarks** buttons in the layers panel (`Entrance`, `Exit`, and `Exit trail` when the file has one) jump to them and switch floors if needed. Searching for `exit` or `entrance` finds them too. They are found from each room's `role` (`antechamber`, `exit`).
- **Outdoor exits and vistas** — the exit trail is drawn west of the ruins, with the same path, trees, shrubs, and rocks as the entrance. Both trails, and each hub spoke, continue as a narrowing path. Distant mountains are faint circles in Plan and peaks in 3D, and they sit outside the fitted frame so the map stays on the paths. With **Sky & Horizon** on, the 3D view uses a daylight sky. That layer hides the peaks and the sky; Outdoor / Trail hides the paths, trees, and shrubs.
- **Hubs** — a file made with `--hub` shows the plaza, each spoke with its name, and the structure drawn with its own roof or parts (hip, pitched, cone, towers, or a fire ring with seats). The campfire and each wall torch use the file's `light` colour, intensity, and distance in 3D. The particle system itself is left for the game. A `RESPAWN` badge marks the spawn point, and in 3D each spoke ends in a beam with its name. The trigger for each `to-<name>` transition is a dashed box at the end of its spoke, and each `from-<name>` landing point is a diamond. The **Landmarks** buttons jump to `Respawn` and to each spoke. The structure follows the Rooms layer, and the plaza and spokes follow Outdoor / Trail.
- **Navigate** — drag to pan, scroll or use the `+` and `-` buttons to zoom, and press `Space` or **Fit Map** to frame the whole layout.
- **Inspect** — click a room, door, or other entity to see its position, elevation (`y`), size, attributes, and raw JSON in the right panel. **Copy** copies that JSON fragment, and **Focus Camera** centres on it. `Esc` clears the selection.
- **Search** — type in the top search box to jump to a room or entity by name.
- **Layers** — toggle rooms, outdoor trail, sky and horizon, doors and gates, torches, chests, enemies, props and scenery, spawns and triggers, and grid lines. The stats box counts props and scenery together, and the header shows the `density` and `clutter` the file was made with.

The viewer runs entirely in the browser and does not upload your file anywhere. It does load Tailwind CSS, Three.js, Google Fonts, and Phosphor Icons from public CDNs, so it needs an internet connection the first time you open it.

If the 3D view shows "3D view could not start" (some browsers or privacy extensions block module loads from `file://` pages), serve the folder instead. This is optional:

```bash
python -m http.server 8000
```

Then browse to `http://localhost:8000/dungeon-visualizer.html`.

## Test

```bash
python -m unittest discover -s tests -v
```
