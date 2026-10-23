"""Structural checks for a generated Ancient Ruins document."""

import unittest

from blk_dungeon_gen import generate_layout

REQUIRED = (
    'seed', 'area', 'rooms', 'doors', 'start', 'lastRoomId', 'areaName', 'requirements',
    'entrance', 'vestibule', 'exterior', 'hub', 'trees', 'zoneLabels', 'approach',
    'transitions', 'gateInward',
)
TRANSITION_IDS = ('ruin-entry', 'ruin-exit', 'mountain-pass', 'mountain-return')


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


if __name__ == '__main__':
    unittest.main()
