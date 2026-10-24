"""Structural checks for a generated Ancient Ruins document."""

import contextlib
import io
import json
import math
import tempfile
import unittest
from pathlib import Path

from creature_gen.species import SPECIES, SPECIES_IDS

from blk_dungeon_gen import generate_hub, generate_layout
from blk_dungeon_gen.__main__ import main
from blk_dungeon_gen.approach import DRESSINGS, SCENERY_TYPES
from blk_dungeon_gen.blocks import Block, Rect
from blk_dungeon_gen.density import spawn_count
from blk_dungeon_gen.emit import NAMES
from blk_dungeon_gen.fire import CAMPFIRE_PREFAB, flame
from blk_dungeon_gen.hub import _rect_distance, clean_names
from blk_dungeon_gen.props import PROPS
from blk_dungeon_gen.structures import STRUCTURES, names

REQUIRED = (
    'seed', 'area', 'rooms', 'doors', 'start', 'lastRoomId', 'areaName', 'requirements',
    'entrance', 'vestibule', 'exterior', 'hub', 'trees', 'zoneLabels', 'approach',
    'transitions', 'gateInward',
)
TRANSITION_IDS = (
    'ruin-entry', 'ruin-exit', 'mountain-pass', 'mountain-return',
    'ruin-leave', 'ruin-return', 'exit-pass',
)


def _edge_distance(x, z, polygon):
    best = 1e9
    count = len(polygon)
    for index in range(count):
        ax, az = polygon[index]
        bx, bz = polygon[(index + 1) % count]
        abx = bx - ax
        abz = bz - az
        len2 = abx * abx + abz * abz
        t = 0 if len2 <= 0 else ((x - ax) * abx + (z - az) * abz) / len2
        t = max(0.0, min(1.0, t))
        best = min(best, ((x - (ax + abx * t)) ** 2 + (z - (az + abz * t)) ** 2) ** 0.5)
    return best


def _overlaps(a, b):
    return (
        a['x'] < b['x'] + b['w'] - 0.02
        and b['x'] < a['x'] + a['w'] - 0.02
        and a['z'] < b['z'] + b['d'] - 0.02
        and b['z'] < a['z'] + a['d'] - 0.02
    )


class LayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.layout = generate_layout(1, floors=2, chambers=8)

    def test_seed_is_deterministic(self):
        again = generate_layout(1, floors=2, chambers=8)
        self.assertEqual(self.layout, again)

    def test_document_shape(self):
        for key in REQUIRED:
            self.assertIn(key, self.layout)
        self.assertEqual(self.layout['seed'], 1)
        self.assertEqual(self.layout['floors'], 2)
        self.assertEqual(self.layout['areaName'], 'The Ancient Ruins')
        self.assertEqual(self.layout['requirements'], ['torch', 'mace'])
        self.assertEqual([item['id'] for item in self.layout['transitions']], list(TRANSITION_IDS))
        self.assertGreaterEqual(len(self.layout['trees']), 1)
        self.assertIn('samples', self.layout['approach'])
        self.assertIn('shell', self.layout['approach'])

    def test_entrance_and_exit(self):
        rooms = self.layout['rooms']
        self.assertEqual(rooms[0]['role'], 'antechamber')
        self.assertEqual(rooms[0]['block'], 'entrance')
        self.assertEqual(rooms[0]['y'], 0)
        exits = [room for room in rooms if room.get('role') == 'exit']
        self.assertEqual(len(exits), 1)
        self.assertEqual(self.layout['lastRoomId'], exits[0]['id'])
        self.assertIsNone(exits[0]['chest'])

    def test_blocks_and_links(self):
        blocks = {room['block'] for room in self.layout['rooms']}
        self.assertTrue({'entrance', 'exit', 'hallway', 'doorway', 'hub', 'stairwell', 'small-room', 'big-room'} <= blocks)
        rooms = {room['id']: room for room in self.layout['rooms']}
        for door in self.layout['doors']:
            parent = rooms[door['from']]
            child = rooms[door['to']]
            if parent['block'] == 'hallway' and child['block'] == 'hallway':
                self.assertAlmostEqual(door['width'], door['openingWidth'], places=3)
        for room in self.layout['rooms']:
            if room['block'] != 'hub':
                continue
            degree = sum(1 for door in self.layout['doors'] if door['from'] == room['id'] or door['to'] == room['id'])
            self.assertEqual(degree, 3)

    def test_doors_lie_on_both_rooms(self):
        rooms = {room['id']: room for room in self.layout['rooms']}
        for door in self.layout['doors']:
            for room_id in (door['from'], door['to']):
                polygon = rooms[room_id]['polygon']
                for point in (door['a'], door['b']):
                    self.assertLess(_edge_distance(point[0], point[1], polygon), 0.2)

    def test_no_same_floor_overlap(self):
        occupied = {}
        for room in self.layout['rooms']:
            floors = [room['floor']]
            if room['block'] == 'stairwell':
                floors.append(room['floor'] + 1)
            for floor in floors:
                occupied.setdefault(floor, []).append(room['rect'])
        for rects in occupied.values():
            for index, rect in enumerate(rects):
                for other in rects[index + 1:]:
                    self.assertFalse(_overlaps(rect, other))

    def test_stair_links_floors(self):
        rooms = {room['id']: room for room in self.layout['rooms']}
        stairs = [room for room in self.layout['rooms'] if room['block'] == 'stairwell']
        self.assertEqual(len(stairs), 1)
        stair = stairs[0]
        self.assertEqual(stair['storyHeight'], 20)
        self.assertEqual(stair['stair']['toY'] - stair['stair']['fromY'], 10)
        links = [door for door in self.layout['doors'] if door['from'] == stair['id'] or door['to'] == stair['id']]
        self.assertEqual(len(links), 2)
        sills = sorted(door['y'] for door in links)
        self.assertEqual(sills[1] - sills[0], 10)
        for door in links:
            other_id = door['to'] if door['from'] == stair['id'] else door['from']
            other = rooms[other_id]
            self.assertEqual(other['y'], door['y'])
            for point in (door['a'], door['b']):
                self.assertLess(_edge_distance(point[0], point[1], stair['polygon']), 0.2)

    def test_graph_reaches_the_exit(self):
        rooms = {room['id']: room for room in self.layout['rooms']}
        neighbors = {room_id: set() for room_id in rooms}
        for door in self.layout['doors']:
            neighbors[door['from']].add(door['to'])
            neighbors[door['to']].add(door['from'])
        seen = {self.layout['rooms'][0]['id']}
        stack = [self.layout['rooms'][0]['id']]
        while stack:
            current = stack.pop()
            for nxt in neighbors[current]:
                if nxt in seen:
                    continue
                seen.add(nxt)
                stack.append(nxt)
        self.assertIn(self.layout['lastRoomId'], seen)
        self.assertEqual(len(seen), len(rooms))

    def test_other_seeds_and_a_single_floor(self):
        other = generate_layout(2, floors=2, chambers=8)
        self.assertNotEqual(
            [room['rect'] for room in other['rooms']],
            [room['rect'] for room in self.layout['rooms']],
        )
        single = generate_layout(3, floors=1, chambers=4)
        self.assertEqual(single['floors'], 1)
        self.assertFalse(any(room['block'] == 'stairwell' for room in single['rooms']))
        self.assertEqual(single['rooms'][0]['role'], 'antechamber')

    def test_wall_torches_carry_the_same_flame(self):
        found = 0
        for room in generate_layout(1, floors=3)['rooms']:
            sconce = room['sconce']
            if sconce is None:
                continue
            found += 1
            self.assertEqual(sconce['vfx'], flame()['vfx'])
            self.assertEqual(sconce['light'], flame()['light'])
            self.assertNotIn('prefab', sconce)
        self.assertGreater(found, 0)


def _spawn_total(layout):
    return sum(len(room['spawns']) for room in layout['rooms'])


def _trail_distance(samples, x, z):
    best = 1e9
    for index in range(len(samples) - 1):
        a = samples[index]
        b = samples[index + 1]
        abx = b['x'] - a['x']
        abz = b['z'] - a['z']
        len2 = abx * abx + abz * abz
        t = 0 if len2 <= 0 else ((x - a['x']) * abx + (z - a['z']) * abz) / len2
        t = max(0.0, min(1.0, t))
        best = min(best, ((x - (a['x'] + abx * t)) ** 2 + (z - (a['z'] + abz * t)) ** 2) ** 0.5)
    return best


class DensityTests(unittest.TestCase):
    def test_density_scales_spawn_totals(self):
        for seed in (1, 2, 3):
            low = _spawn_total(generate_layout(seed, density='low'))
            normal = _spawn_total(generate_layout(seed, density='normal'))
            high = _spawn_total(generate_layout(seed, density='high'))
            self.assertLess(low, normal)
            self.assertLess(normal, high)

    def test_depth_raises_the_count(self):
        room = Block('big-room', 'chamber', 0, Rect(0, 0, 28, 24))
        self.assertLess(spawn_count(room, 'normal', 0.0), spawn_count(room, 'normal', 1.0))

    def test_exit_gets_a_guard(self):
        plain = Block('small-room', 'chamber', 0, Rect(0, 0, 16, 16))
        last = Block('exit', 'chamber', 0, Rect(0, 0, 16, 16), role='exit')
        self.assertEqual(spawn_count(last, 'normal', 1.0), spawn_count(plain, 'normal', 1.0) + 1)

    def test_quiet_blocks_stay_empty(self):
        for room in generate_layout(1, density='high')['rooms']:
            if room['block'] in ('entrance', 'stairwell', 'doorway'):
                self.assertEqual(room['spawns'], [])
            elif room['kind'] == 'chamber':
                self.assertGreaterEqual(len(room['spawns']), 1)

    def test_density_keeps_the_layout(self):
        low = generate_layout(1, density='low')
        high = generate_layout(1, density='high')
        for key in ('rect', 'theme', 'sconce'):
            self.assertEqual([room[key] for room in low['rooms']], [room[key] for room in high['rooms']])
        self.assertEqual(low['doors'], high['doors'])
        self.assertEqual(low['trees'], high['trees'])


class PropTests(unittest.TestCase):
    def test_props_follow_the_rules(self):
        for seed in (1, 2, 3):
            layout = generate_layout(seed, clutter=1.0)
            self.assertGreater(sum(len(room['props']) for room in layout['rooms']), 0)
            doors = layout['doors']
            for room in layout['rooms']:
                if room['kind'] != 'chamber':
                    self.assertEqual(room['props'], [])
                    continue
                allowed = {kind.type for kind in PROPS[room['theme']]}
                rect = room['rect']
                linked = [door for door in doors if room['id'] in (door['from'], door['to'])]
                for prop in room['props']:
                    self.assertIn(prop['type'], allowed)
                    self.assertGreater(prop['x'], rect['x'])
                    self.assertLess(prop['x'], rect['x'] + rect['w'])
                    self.assertGreater(prop['z'], rect['z'])
                    self.assertLess(prop['z'], rect['z'] + rect['d'])
                    for door in linked:
                        self.assertGreaterEqual(
                            _edge_distance(prop['x'], prop['z'], [door['a'], door['b']]) - 0, 2.0)
                    for spawn in room['spawns']:
                        self.assertGreaterEqual(math.hypot(prop['x'] - spawn[0], prop['z'] - spawn[1]), 1.9)

    def test_every_theme_has_props(self):
        self.assertEqual(set(PROPS), set(NAMES))

    def test_clutter_scales_props(self):
        def count(clutter):
            layout = generate_layout(1, clutter=clutter)
            return sum(len(room['props']) for room in layout['rooms'])
        self.assertEqual(count(0), 0)
        self.assertLess(count(0.2), count(1.0))

    def test_clutter_zero_clears_scenery(self):
        self.assertEqual(generate_layout(1, clutter=0)['scenery'], [])


class OutsideTests(unittest.TestCase):
    def test_scenery_stays_off_the_trail(self):
        for seed in range(1, 6):
            layout = generate_layout(seed, clutter=1.0)
            samples = layout['approach']['samples']
            self.assertGreater(len(layout['scenery']), 0)
            self.assertIn(layout['approach']['dressing'], DRESSINGS)
            for item in layout['scenery']:
                self.assertIn(item['type'], SCENERY_TYPES)
                self.assertGreater(_trail_distance(samples, item['x'], item['z']), 7.0)

    def test_trail_varies_by_seed(self):
        bends = set()
        lengths = set()
        for seed in range(1, 13):
            layout = generate_layout(seed)
            samples = layout['approach']['samples']
            bends.add(samples[len(samples) // 2]['x'] > layout['approach']['midX'])
            lengths.add(round(layout['approach']['path']['d'], 1))
        self.assertEqual(bends, {True, False})
        self.assertGreater(len(lengths), 6)


class OptionTests(unittest.TestCase):
    def test_options_are_recorded_and_deterministic(self):
        first = generate_layout(4, density='high', clutter=0.8)
        again = generate_layout(4, density='high', clutter=0.8)
        self.assertEqual(first, again)
        self.assertEqual(first['options'], {
            'density': 'high', 'clutter': 0.8, 'theme': None, 'creature': None,
        })
        self.assertNotIn('enemyName', first)

    def test_bad_options_are_rejected(self):
        for kwargs, error in (
            ({'density': 'extreme'}, ValueError),
            ({'clutter': -0.1}, ValueError),
            ({'clutter': 1.1}, ValueError),
            ({'clutter': float('nan')}, ValueError),
            ({'clutter': 'lots'}, TypeError),
            ({'clutter': True}, TypeError),
            ({'theme': 'marble'}, ValueError),
            ({'theme': 1}, ValueError),
            ({'theme': True}, ValueError),
            ({'creature': 'dragon'}, ValueError),
            ({'creature': 3}, ValueError),
            ({'creature': True}, ValueError),
        ):
            with self.assertRaises(error):
                generate_layout(1, **kwargs)

    def test_cli_rejects_bad_clutter(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                main(['--clutter', '2', '-o', 'unused.json'])


class ThemeAndCreatureTests(unittest.TestCase):
    def test_passages_stay_stone_until_a_theme_is_forced(self):
        layout = generate_layout(1)
        self.assertIsNone(layout['options']['theme'])
        for room in layout['rooms']:
            if room['block'] in ('entrance', 'hallway', 'doorway', 'stairwell'):
                self.assertEqual(room['theme'], 'stone')
        mixed = False
        for seed in range(1, 8):
            themes = {
                room['theme'] for room in generate_layout(seed)['rooms']
                if room['block'] not in ('entrance', 'hallway', 'doorway', 'stairwell')
            }
            if len(themes) > 1:
                mixed = True
                break
        self.assertTrue(mixed)

    def test_theme_dresses_every_room_and_keeps_the_shell(self):
        plain = generate_layout(1, floors=2, chambers=8)
        for theme in ('stone', 'wood', 'cave'):
            dressed = generate_layout(1, floors=2, chambers=8, theme=theme)
            again = generate_layout(1, floors=2, chambers=8, theme=theme)
            self.assertEqual(dressed, again)
            self.assertEqual(dressed['options']['theme'], theme)
            self.assertTrue(all(room['theme'] == theme for room in dressed['rooms']))
            self.assertEqual(dressed['doors'], plain['doors'])
            for key in ('rect', 'sconce', 'floor', 'y', 'block'):
                self.assertEqual(
                    [room[key] for room in dressed['rooms']],
                    [room[key] for room in plain['rooms']],
                )
            self.assertEqual(dressed['rooms'][0]['description'], {
                'stone': 'A stone threshold under the arch. Pale daylight fails a few steps in, and the passage beyond is black.',
                'wood': 'A timber threshold under the arch. Pale daylight fails a few steps in, and the passage beyond is black.',
                'cave': 'A rock threshold under the arch. Pale daylight fails a few steps in, and the passage beyond is black.',
            }[theme])
            allowed = {kind.type for kind in PROPS[theme]}
            for room in dressed['rooms']:
                for prop in room['props']:
                    self.assertIn(prop['type'], allowed)
                if theme != 'cave':
                    self.assertEqual(room['rocks'], [])

    def test_cave_rooms_can_hold_rocks(self):
        found = False
        for seed in range(1, 6):
            layout = generate_layout(seed, theme='cave', chambers=12)
            if any(room['rocks'] for room in layout['rooms']):
                found = True
                break
        self.assertTrue(found)

    def test_creature_names_every_spawn_and_keeps_the_layout(self):
        plain = generate_layout(1, floors=2, chambers=8)
        for species in SPECIES_IDS:
            populated = generate_layout(1, floors=1, chambers=2, creature=species)
            self.assertEqual(populated['options']['creature'], species)
            self.assertEqual(populated['enemyName'], SPECIES[species]['title'])
        wolves = generate_layout(1, floors=2, chambers=8, creature='wolf')
        again = generate_layout(1, floors=2, chambers=8, creature='wolf')
        self.assertEqual(wolves, again)
        self.assertEqual(wolves['enemyName'], 'Wolf')
        self.assertGreater(sum(len(room['spawns']) for room in wolves['rooms']), 0)
        copy = json.loads(json.dumps(wolves))
        copy.pop('enemyName')
        copy['options']['creature'] = None
        self.assertEqual(copy, plain)

    def test_theme_and_creature_together_are_deterministic(self):
        first = generate_layout(4, theme='wood', creature='goblin', density='low', clutter=0.2)
        again = generate_layout(4, theme='wood', creature='goblin', density='low', clutter=0.2)
        self.assertEqual(first, again)
        self.assertEqual(first['options']['theme'], 'wood')
        self.assertEqual(first['options']['creature'], 'goblin')
        self.assertTrue(all(room['theme'] == 'wood' for room in first['rooms']))

    def test_hub_theme_overrides_material_and_keeps_the_plaza(self):
        plain = generate_hub(1, structure='house', clutter=1.0)
        stone = generate_hub(1, structure='house', clutter=1.0, theme='stone')
        self.assertEqual(stone['options']['theme'], 'stone')
        self.assertEqual(stone['structure']['theme'], 'stone')
        self.assertEqual(stone['structure']['material'], 'stone')
        self.assertEqual(stone['rooms'][0]['theme'], 'stone')
        self.assertEqual(stone['hubArea'], plain['hubArea'])
        self.assertEqual(stone['structure']['rect'], plain['structure']['rect'])
        self.assertEqual(plain['structure']['material'], 'timber')
        allowed = {kind.type for kind in PROPS['stone']}
        self.assertGreater(len(stone['rooms'][0]['props']), 0)
        for prop in stone['rooms'][0]['props']:
            self.assertIn(prop['type'], allowed)
        wood = generate_hub(1, structure='house', theme='wood')
        self.assertEqual(wood['structure']['material'], 'timber')
        tent = generate_hub(1, structure='tent', theme='wood')
        self.assertEqual(tent['structure']['material'], 'canvas')
        cave = generate_hub(2, structure='castle', theme='cave', clutter=1.0)
        self.assertEqual(cave['structure']['material'], 'stone')
        self.assertEqual(cave['rooms'][0]['theme'], 'cave')
        cave_props = {kind.type for kind in PROPS['cave']}
        for prop in cave['rooms'][0]['props']:
            self.assertIn(prop['type'], cave_props)

    def test_hub_records_a_creature_without_spawns(self):
        house = generate_hub(1, structure='house', creature='bear')
        self.assertEqual(house['enemyName'], 'Bear')
        self.assertEqual(house['options']['creature'], 'bear')
        self.assertEqual(house['rooms'][0]['spawns'], [])
        camp = generate_hub(1, structure='campfire', creature='rat')
        self.assertEqual(camp['enemyName'], 'Rat')
        self.assertEqual(camp['rooms'], [])
        self.assertIsNone(generate_hub(1)['options']['creature'])
        for bad in ('dragon', 3, True):
            with self.assertRaises(ValueError):
                generate_hub(1, creature=bad)
        with self.assertRaises(ValueError):
            generate_hub(1, theme='marble')

    def test_cli_writes_theme_and_creature(self):
        with tempfile.TemporaryDirectory() as folder:
            ruins = Path(folder) / 'ruins.json'
            hub = Path(folder) / 'hub.json'
            with contextlib.redirect_stdout(io.StringIO()):
                main(['--seed', '1', '--theme', 'wood', '--creature', 'goblin', '-o', str(ruins)])
                main(['--hub', '--seed', '1', '--structure', 'house', '--theme', 'stone', '--creature', 'orc',
                      '-o', str(hub)])
            ruin_doc = json.loads(ruins.read_text(encoding='utf-8'))
            hub_doc = json.loads(hub.read_text(encoding='utf-8'))
            self.assertEqual(ruin_doc['options']['theme'], 'wood')
            self.assertEqual(ruin_doc['options']['creature'], 'goblin')
            self.assertEqual(ruin_doc['enemyName'], 'Goblin')
            self.assertTrue(all(room['theme'] == 'wood' for room in ruin_doc['rooms']))
            self.assertEqual(hub_doc['structure']['material'], 'stone')
            self.assertEqual(hub_doc['enemyName'], 'Orc')
            self.assertEqual(ruin_doc, generate_layout(1, theme='wood', creature='goblin'))
            self.assertEqual(hub_doc, generate_hub(1, structure='house', theme='stone', creature='orc'))

    def test_cli_rejects_unknown_theme_and_creature(self):
        for argv in (['--theme', 'marble'], ['--creature', 'dragon'], ['--hub', '--theme', 'brick']):
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit, msg=str(argv)):
                    main(argv + ['-o', 'unused.json'])


def _inside(point_x, point_z, rect, slack=0.0):
    return (rect['x'] - slack <= point_x <= rect['x'] + rect['w'] + slack
            and rect['z'] - slack <= point_z <= rect['z'] + rect['d'] + slack)


class ExitTests(unittest.TestCase):
    def test_exit_gate_sits_on_the_exit_chamber_wall(self):
        for seed in range(1, 11):
            for floors in (1, 2, 3):
                doc = generate_layout(seed, floors=floors)
                room = next(r for r in doc['rooms'] if r['id'] == doc['lastRoomId'])
                gate = doc['exitGate']
                rect = room['rect']
                self.assertEqual(gate['from'], room['id'])
                self.assertEqual(gate['y'], room['y'])
                (ax, az), (bx, bz) = gate['a'], gate['b']
                walls = {'N': rect['z'], 'S': rect['z'] + rect['d'], 'W': rect['x'], 'E': rect['x'] + rect['w']}
                on_wall = az == bz == walls[gate['wall']] if gate['wall'] in 'NS' else ax == bx == walls[gate['wall']]
                self.assertTrue(on_wall, (seed, floors))
                self.assertAlmostEqual(math.hypot(bx - ax, bz - az), gate['width'], places=3)

    def test_gate_is_not_against_another_room(self):
        for seed in range(1, 11):
            doc = generate_layout(seed, floors=2)
            room = next(r for r in doc['rooms'] if r['id'] == doc['lastRoomId'])
            gate = doc['exitGate']
            fx, fz = gate['facing']
            mx = (gate['a'][0] + gate['b'][0]) / 2 + fx * 0.8
            mz = (gate['a'][1] + gate['b'][1]) / 2 + fz * 0.8
            for other in doc['rooms']:
                if other['id'] == room['id'] or other['floor'] != room['floor']:
                    continue
                self.assertFalse(_inside(mx, mz, other['rect']), (seed, other['id']))

    def test_exit_trail_is_clear_of_every_room_and_the_entrance_trail(self):
        for seed in range(1, 11):
            doc = generate_layout(seed, floors=2)
            area = doc['exitArea']
            west = min(r['rect']['x'] for r in doc['rooms'])
            polygon = area['exterior']
            self.assertLess(max(x for x, _ in polygon), west - 20)
            entrance = doc['exterior']
            self.assertLess(max(x for x, _ in polygon), min(x for x, _ in entrance) - 10)

    def test_exit_trail_has_the_same_outdoor_parts_as_the_entrance(self):
        doc = generate_layout(2)
        area = doc['exitArea']
        for key in ('arch', 'vestibule', 'exterior', 'hub', 'trees', 'scenery', 'approach'):
            self.assertIn(key, area)
        approach = area['approach']
        self.assertEqual(set(approach['vista']), set(doc['approach']['vista']))
        self.assertGreater(len(approach['vista']['mountains']), 5)
        self.assertGreater(len(approach['vista']['trees']), 0)
        self.assertGreater(len(approach['vista']['scrub']), 0)
        self.assertGreaterEqual(len(area['trees']), 18)
        self.assertIn(approach['dressing'], DRESSINGS)
        for item in area['scenery']:
            self.assertIn(item['type'], SCENERY_TYPES)
            self.assertGreater(_trail_distance(approach['samples'], item['x'], item['z']), 7.0)
        self.assertIn('exit-trail', doc['zoneLabels'])
        self.assertIn('exit-pass', doc['zoneLabels'])

    def test_exit_transitions_join_the_gate_to_the_trail(self):
        for floors in (1, 2, 3):
            doc = generate_layout(3, floors=floors)
            room = next(r for r in doc['rooms'] if r['id'] == doc['lastRoomId'])
            by_id = {t['id']: t for t in doc['transitions']}
            leave, back, onward = by_id['ruin-leave'], by_id['ruin-return'], by_id['exit-pass']
            self.assertEqual((leave['sourceZoneId'], leave['targetZoneId']), ('ancient-ruins', 'exit-trail'))
            self.assertEqual((back['sourceZoneId'], back['targetZoneId']), ('exit-trail', 'ancient-ruins'))
            self.assertEqual((onward['sourceZoneId'], onward['targetZoneId']), ('exit-trail', 'world-hub'))
            volume = leave['volume']
            self.assertTrue(_inside((volume['minX'] + volume['maxX']) / 2, (volume['minZ'] + volume['maxZ']) / 2,
                                    room['rect']))
            self.assertEqual(leave['y'], room['y'])
            self.assertEqual(leave['floor'], room['floor'])
            spawn = back['targetSpawnPoint']
            self.assertTrue(_inside(spawn['x'], spawn['z'], room['rect']))
            self.assertEqual(spawn['y'], room['y'])
            arrive = leave['targetSpawnPoint']
            samples = doc['exitArea']['approach']['samples']
            self.assertLess(arrive['z'], samples[0]['z'] + 10)
            self.assertLess(abs(arrive['x'] - doc['exitArea']['approach']['midX']), 1.0)
            self.assertEqual(onward['targetSpawnPoint'], by_id['mountain-pass']['targetSpawnPoint'])

    def test_exit_does_not_move_the_entrance_trail(self):
        doc = generate_layout(1, floors=2, chambers=8)
        trail = doc['approach']['samples']
        self.assertGreater(len(trail), 5)
        self.assertEqual(doc['entrance']['a'][1], doc['approach']['southZ'])
        self.assertEqual([t['id'] for t in doc['transitions'][:4]], list(TRANSITION_IDS[:4]))


def _plaza_fit(doc):
    """Every corner of the structure's outer bounds lies inside the plaza circle."""
    bounds = doc['structure']['bounds']
    radius = doc['hubArea']['radius']
    return all(
        math.hypot(bounds['x'] + sx * bounds['w'], bounds['z'] + sz * bounds['d']) <= radius
        for sx in (0, 1) for sz in (0, 1)
    )


def _spoke_gap(a, b):
    return min(math.hypot(p['x'] - q['x'], p['z'] - q['z']) for p in a['samples'] for q in b['samples'])


class HubTests(unittest.TestCase):
    def test_same_seed_and_options_match(self):
        first = generate_hub(5, spokes=4, names=['ruins'], structure='house', clutter=0.7)
        again = generate_hub(5, spokes=4, names=['ruins'], structure='house', clutter=0.7)
        self.assertEqual(first, again)
        self.assertNotEqual(first, generate_hub(6, spokes=4, names=['ruins'], structure='house', clutter=0.7))

    def test_document_shape(self):
        doc = generate_hub(1)
        for key in ('seed', 'kind', 'options', 'rooms', 'doors', 'start', 'areaName', 'structure',
                    'trees', 'scenery', 'zoneLabels', 'transitions', 'hubArea'):
            self.assertIn(key, doc)
        self.assertEqual(doc['kind'], 'hub')
        self.assertEqual(doc['floors'], 1)
        self.assertEqual(doc['doors'], [])
        self.assertNotIn('kind', generate_layout(1))
        json.dumps(doc)

    def test_every_structure_type_builds(self):
        self.assertEqual(set(names()), {'campfire', 'castle', 'house', 'hut', 'tent'})
        for kind in names():
            for seed in range(1, 6):
                doc = generate_hub(seed, structure=kind)
                structure = doc['structure']
                self.assertEqual(structure['type'], kind)
                self.assertEqual(doc['options']['structure'], kind)
                self.assertTrue(_plaza_fit(doc), (kind, seed))
                ids = [t['id'] for t in doc['transitions']]
                if STRUCTURES[kind].enterable:
                    self.assertEqual(len(doc['rooms']), 1)
                    self.assertEqual(doc['rooms'][0]['theme'], STRUCTURES[kind].theme)
                    self.assertIn('structure-entry', ids)
                    self.assertIn('structure-exit', ids)
                    self.assertIsNotNone(doc['entrance'])
                    self.assertIsNotNone(structure['door'])
                else:
                    self.assertEqual(doc['rooms'], [])
                    self.assertNotIn('structure-entry', ids)
                    self.assertIsNone(doc['entrance'])
                    self.assertIsNone(structure['door'])
                    pit = next(part for part in structure['parts'] if part['type'] == 'fire-pit')
                    self.assertEqual(pit['y'], 0.0)
                    self.assertEqual(pit['prefab'], CAMPFIRE_PREFAB)
                    self.assertEqual(pit['vfx'], flame()['vfx'])
                    self.assertEqual(pit['light'], flame()['light'])
        pit = next(part for part in generate_hub(
            26, names=['smallruins', 'largeruins', 'medruins'], structure='campfire',
        )['structure']['parts'] if part['type'] == 'fire-pit')
        self.assertEqual((pit['x'], pit['y'], pit['z'], pit['radius']), (1.17, 0.0, -13.75, 1.1))
        castle = generate_hub(1, structure='castle')['structure']
        self.assertEqual(sum(part['type'] == 'tower' for part in castle['parts']), 4)

    def test_seed_picks_the_structure(self):
        picked = {generate_hub(seed)['structure']['type'] for seed in range(40)}
        self.assertGreaterEqual(len(picked), 4)
        for seed in (1, 2, 3, 9):
            doc = generate_hub(seed)
            self.assertEqual(doc, generate_hub(seed, structure=doc['options']['structure']))

    def test_interior_props_follow_the_room(self):
        for kind in ('hut', 'house', 'tent', 'castle'):
            doc = generate_hub(3, structure=kind, clutter=1.0)
            room = doc['rooms'][0]
            allowed = {prop.type for prop in PROPS[room['theme']]}
            for prop in room['props']:
                self.assertIn(prop['type'], allowed)
                self.assertGreater(_edge_distance(prop['x'], prop['z'], room['polygon']), 0.5)
            self.assertEqual(room['sconce']['vfx'], flame()['vfx'])
            self.assertEqual(room['sconce']['light'], flame()['light'])
            self.assertNotIn('prefab', room['sconce'])

    def test_spokes_clear_the_structure_and_each_other(self):
        for kind in names():
            for count in (1, 3, 8):
                for seed in (1, 2, 3):
                    doc = generate_hub(seed, spokes=count, structure=kind)
                    spokes = doc['hubArea']['spokes']
                    self.assertEqual(len(spokes), count)
                    bounds = doc['structure']['bounds']
                    for index, spoke in enumerate(spokes):
                        for sample in spoke['samples']:
                            self.assertGreater(_rect_distance(sample['x'], sample['z'], bounds), 4.5)
                        for other in spokes[index + 1:]:
                            self.assertGreater(_spoke_gap(spoke, other), spoke['width'], (kind, count, seed))

    def test_spoke_names_and_defaults(self):
        self.assertEqual([s['name'] for s in generate_hub(1)['hubArea']['spokes']],
                         ['spoke-1', 'spoke-2', 'spoke-3'])
        doc = generate_hub(1, names=['ruins', 'forest'])
        self.assertEqual(doc['options']['spokes'], ['ruins', 'forest'])
        doc = generate_hub(1, spokes=4, names=['ruins'])
        self.assertEqual(doc['options']['spokes'], ['ruins', 'spoke-1', 'spoke-2', 'spoke-3'])
        self.assertEqual(len(generate_hub(1, spokes=1)['hubArea']['spokes']), 1)

    def test_every_spoke_has_paired_transitions(self):
        doc = generate_hub(2, names=['ruins', 'forest', 'mine'], structure='hut')
        ids = [t['id'] for t in doc['transitions']]
        self.assertEqual(len(ids), len(set(ids)))
        by_id = {t['id']: t for t in doc['transitions']}
        radius = doc['hubArea']['radius']
        for spoke in doc['hubArea']['spokes']:
            out = by_id[f'to-{spoke["name"]}']
            back = by_id[f'from-{spoke["name"]}']
            self.assertEqual(out['sourceZoneId'], 'hub')
            self.assertEqual(out['targetZoneId'], spoke['name'])
            self.assertIsNone(out['targetSpawnPoint'])
            end = spoke['end']
            volume = out['volume']
            self.assertTrue(volume['minX'] - 1 <= end['x'] <= volume['maxX'] + 1)
            self.assertTrue(volume['minZ'] - 1 <= end['z'] <= volume['maxZ'] + 1)
            self.assertEqual(back['sourceZoneId'], spoke['name'])
            self.assertEqual(back['targetZoneId'], 'hub')
            self.assertIsNone(back['volume'])
            spawn = back['targetSpawnPoint']
            self.assertGreater(math.hypot(spawn['x'], spawn['z']), radius - 2)
            self.assertLess(_trail_distance(spoke['samples'], spawn['x'], spawn['z']), 1.0)

    def test_respawn_matches_start_and_is_clear(self):
        for kind in names():
            for seed in range(1, 5):
                doc = generate_hub(seed, structure=kind)
                respawn = doc['hubArea']['respawn']
                self.assertEqual(
                    (doc['start']['x'], doc['start']['z'], doc['start']['yaw']),
                    (respawn['x'], respawn['z'], respawn['yaw']))
                self.assertLess(math.hypot(respawn['x'], respawn['z']), doc['hubArea']['radius'] - 5)
                self.assertGreater(_rect_distance(respawn['x'], respawn['z'], doc['structure']['rect']), 1.5)
                for spoke in doc['hubArea']['spokes']:
                    self.assertGreater(_trail_distance(spoke['samples'], respawn['x'], respawn['z']), 4.5)

    def test_trees_and_scenery_stay_off_the_spokes(self):
        for seed in range(1, 6):
            doc = generate_hub(seed, clutter=1.0)
            bounds = doc['structure']['bounds']
            self.assertGreater(len(doc['trees']), 0)
            for item in doc['trees'] + [i for i in doc['scenery'] if i['type'] != 'signpost']:
                self.assertGreater(_rect_distance(item['x'], item['z'], bounds), 2.0)
                for spoke in doc['hubArea']['spokes']:
                    self.assertGreater(_trail_distance(spoke['samples'], item['x'], item['z']), 5.0)

    def test_each_spoke_gets_a_labelled_signpost(self):
        for clutter in (0, 1):
            doc = generate_hub(4, names=['ruins', 'forest'], clutter=clutter)
            signs = sorted(i['label'] for i in doc['scenery'] if i['type'] == 'signpost')
            self.assertEqual(signs, ['forest', 'ruins'])
            if clutter == 0:
                self.assertEqual(len(doc['scenery']), 2)

    def test_spokes_continue_into_the_distance(self):
        for seed in range(1, 6):
            doc = generate_hub(seed, spokes=4)
            area = doc['hubArea']
            radius = area['radius']
            self.assertEqual(area['environment']['skyboxVisible'], True)
            self.assertGreaterEqual(len(area['mountains']), 12)
            for mountain in area['mountains']:
                self.assertGreater(math.hypot(mountain['x'], mountain['z']), radius + 100)
            for spoke in area['spokes']:
                vista = spoke['vista']
                first = vista['path'][0]
                self.assertAlmostEqual(first['x'], spoke['end']['x'], places=2)
                self.assertAlmostEqual(first['z'], spoke['end']['z'], places=2)
                self.assertGreater(len(vista['trees']), 5)
                self.assertGreater(len(vista['scrub']), 5)
                reach = max(math.hypot(p['x'], p['z']) for p in vista['path'])
                self.assertGreater(reach, math.hypot(spoke['end']['x'], spoke['end']['z']) + 40)
                self.assertLess(reach, min(math.hypot(m['x'], m['z']) - m['radius'] for m in area['mountains']))

    def test_clutter_scales_scenery(self):
        quiet = generate_hub(1, clutter=0)
        busy = generate_hub(1, clutter=1)
        self.assertEqual(quiet['trees'], busy['trees'])
        self.assertGreater(len(busy['scenery']), len(quiet['scenery']))

    def test_bad_options_are_rejected(self):
        for kwargs, error in (
            ({'names': ['../etc']}, ValueError),
            ({'names': ['Ruins']}, ValueError),
            ({'names': ['a b']}, ValueError),
            ({'names': ['']}, ValueError),
            ({'names': ['-a']}, ValueError),
            ({'names': ['a--b']}, ValueError),
            ({'names': ['x' * 33]}, ValueError),
            ({'names': ['hub']}, ValueError),
            ({'names': ['hub-interior']}, ValueError),
            ({'names': ['ruins', 'ruins']}, ValueError),
            ({'names': ['a', 'b'], 'spokes': 1}, ValueError),
            ({'names': 'ruins'}, TypeError),
            ({'names': [3]}, TypeError),
            ({'spokes': 0}, ValueError),
            ({'spokes': 9}, ValueError),
            ({'spokes': True}, TypeError),
            ({'spokes': 2.5}, TypeError),
            ({'structure': 'palace'}, ValueError),
            ({'structure': 7}, ValueError),
            ({'clutter': 2}, ValueError),
            ({'clutter': float('nan')}, ValueError),
            ({'clutter': True}, TypeError),
            ({'seed': 'one'}, TypeError),
        ):
            with self.assertRaises(error, msg=str(kwargs)):
                generate_hub(**{'seed': 1, **kwargs})
        self.assertEqual(len(clean_names(['a' * 32], None)), 1)

    def test_cli_writes_a_hub(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'nested' / 'hub.json'
            with contextlib.redirect_stdout(io.StringIO()):
                main(['--hub', '--seed', '3', '--structure', 'tent', '--spoke', 'ruins', '--spoke', 'forest',
                      '-o', str(target)])
            doc = json.loads(target.read_text(encoding='utf-8'))
            self.assertEqual(doc['kind'], 'hub')
            self.assertEqual(doc['structure']['type'], 'tent')
            self.assertEqual(doc['options']['spokes'], ['ruins', 'forest'])
            self.assertEqual(doc, generate_hub(3, names=['ruins', 'forest'], structure='tent'))

    def test_cli_rejects_bad_hub_options(self):
        for argv in (
            ['--hub', '--spoke', '../x'],
            ['--hub', '--spokes', '9'],
            ['--hub', '--spokes', '1', '--spoke', 'a', '--spoke', 'b'],
            ['--hub', '--structure', 'palace'],
            ['--structure', 'hut'],
            ['--spokes', '2'],
            ['--spoke', 'ruins'],
        ):
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit, msg=str(argv)):
                    main(argv + ['-o', 'unused.json'])


if __name__ == '__main__':
    unittest.main()
