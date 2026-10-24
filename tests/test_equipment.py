"""Recipes for held equipment."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from blk_dungeon_gen.fire import flame

from equipment_gen import KINDS, generate_item
from equipment_gen.__main__ import main
from equipment_gen.schema import validate


def _part(item, name):
    return next(part for part in item['parts'] if part['name'] == name)


def _without_seed(item):
    copy = json.loads(json.dumps(item))
    copy['seed'] = 0
    copy['options']['seed'] = 0
    return copy


class EquipmentTests(unittest.TestCase):
    def test_every_kind_is_deterministic_and_inside_its_limits(self):
        for kind in KINDS:
            for seed in (0, 1, 7):
                for tier in (1, 3, 5):
                    first = generate_item(kind, seed, tier)
                    second = generate_item(kind, seed, tier)
                    self.assertEqual(first, second)
                    self.assertEqual(first['version'], 1)
                    self.assertEqual(first['id'], kind)
                    self.assertEqual(first['options'], {'kind': kind, 'seed': seed, 'tier': tier})
                    self.assertNotIn('prefab', json.dumps(first))
                    validate(first)

    def test_seed_changes_the_item_and_tier_keeps_the_name(self):
        for kind in KINDS:
            low = generate_item(kind, 1, 1)
            other = generate_item(kind, 2, 1)
            high = generate_item(kind, 1, 5)
            self.assertNotEqual(_without_seed(low), _without_seed(other))
            self.assertEqual(low['name'], high['name'])
            self.assertFalse(any(part['name'] == 'inlay' for part in low['parts']))
            self.assertTrue(any(part['name'] == 'inlay' for part in high['parts']))

    def test_mesh_is_twice_as_large_except_the_torch(self):
        for seed in (0, 1, 7):
            sword = _part(generate_item('sword', seed, 1), 'blade')['geometry']
            self.assertGreaterEqual(sword['length'], 1.32)
            self.assertLessEqual(sword['length'], 1.72)
            dagger = _part(generate_item('dagger', seed, 1), 'blade')['geometry']
            self.assertGreaterEqual(dagger['length'], 0.44)
            self.assertLessEqual(dagger['length'], 0.56)
            mace = _part(generate_item('mace', seed, 1), 'grip')['geometry']['points'][-1][1]
            self.assertGreaterEqual(mace, 0.92)
            self.assertLessEqual(mace, 1.08)
            axe = _part(generate_item('axe', seed, 1), 'grip')['geometry']['points'][-1][1]
            self.assertGreaterEqual(axe, 1.0)
            self.assertLessEqual(axe, 1.16)
            hammer = _part(generate_item('hammer', seed, 1), 'grip')['geometry']['points'][-1][1]
            self.assertGreaterEqual(hammer, 0.96)
            self.assertLessEqual(hammer, 1.12)
            spear = _part(generate_item('spear', seed, 1), 'shaft')['geometry']['height']
            self.assertGreaterEqual(spear, 3.0)
            self.assertLessEqual(spear, 3.32)
            shield = _part(generate_item('shield', seed, 1), 'board')['geometry']
            self.assertGreaterEqual(shield['width'], 1.0)
            self.assertLessEqual(shield['width'], 1.68)
            self.assertGreaterEqual(shield['height'], 1.0)
            self.assertLessEqual(shield['height'], 1.84)
            bow = _part(generate_item('bow', seed, 1), 'stave')['geometry']['curve']['from'][1]
            self.assertGreaterEqual(bow, 1.24)
            self.assertLessEqual(bow, 1.55)
            torch = _part(generate_item('torch', seed, 1), 'shaft')['geometry']['points'][-1][1]
            self.assertGreaterEqual(torch, 0.5)
            self.assertLessEqual(torch, 0.56)
        self.assertEqual(generate_item('sword', 1, 1)['combat']['range'], 3.8)

    def test_tier_raises_damage_for_weapons(self):
        for kind in ('sword', 'dagger', 'mace', 'axe', 'hammer', 'spear', 'bow'):
            low = generate_item(kind, 3, 1)
            high = generate_item(kind, 3, 5)
            self.assertGreater(high['combat']['damage'], low['combat']['damage'])
            self.assertGreater(high['combat']['range'], low['combat']['range'])
            self.assertLess(high['combat']['attackInterval'], low['combat']['attackInterval'])

    def test_hands_and_fire(self):
        expected = flame()
        for kind in KINDS:
            item = generate_item(kind, 4, 2)
            if kind in ('torch', 'shield'):
                self.assertEqual(item['hand'], 'left')
                self.assertEqual(item['parent'], 'leftHandSocket')
            else:
                self.assertEqual(item['hand'], 'right')
                self.assertEqual(item['parent'], 'rightHandSocket')
            text = json.dumps(item)
            if kind == 'torch':
                socket = next(part for part in item['parts'] if part['name'] == 'TorchTipSocket')
                self.assertEqual(socket['type'], 'group')
                self.assertEqual(socket['vfx'], expected['vfx'])
                self.assertEqual(socket['light'], expected['light'])
                self.assertNotIn('prefab', socket)
                self.assertNotIn('geometry', socket)
                cup = next(part for part in item['parts'] if part['name'] == 'cup')
                self.assertGreater(socket['position'][1], cup['position'][1])
            else:
                self.assertNotIn('"vfx"', text)
                self.assertNotIn('"light"', text)
            if kind in ('shield', 'torch'):
                self.assertNotIn('combat', item)

    def test_rejected_options_and_bad_fields(self):
        for args in (('wand', 1, 1), ('sword', -1, 1), ('sword', True, 1), ('sword', 1, 0), ('sword', 1, 6), ('sword', 1, True)):
            with self.assertRaises(ValueError):
                generate_item(*args)
        item = generate_item('mace', 1, 1)
        item['parts'][0]['geometry']['type'] = 'mesh'
        with self.assertRaises(ValueError):
            validate(item)
        item = generate_item('mace', 1, 1)
        item['parts'][0]['geometry']['points'][0][0] = float('nan')
        with self.assertRaises(ValueError):
            validate(item)
        item = generate_item('sword', 1, 1)
        item['parts'][0]['name'] = 'sin(time)'
        with self.assertRaises(ValueError):
            validate(item)
        item = generate_item('torch', 2, 1)
        item['prefab'] = 'prefabs/campfire_lit.glb'
        with self.assertRaises(ValueError):
            validate(item)
        item = generate_item('torch', 2, 1)
        item['parts'][-1]['vfx']['preset'] = 'other'
        with self.assertRaises(ValueError):
            validate(item)
        item = generate_item('shield', 1, 1)
        item['combat'] = {'range': 1, 'arcRadians': 1, 'damage': 1, 'attackInterval': 1}
        with self.assertRaises(ValueError):
            validate(item)

    def test_cli_writes_one_file_or_every_kind(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sword.json'
            main(['--seed', '1', '--kind', 'sword', '--tier', '2', '-o', str(path)])
            written = json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(written, generate_item('sword', 1, 2))
            folder = Path(directory) / 'all'
            main(['--seed', '0', '--tier', '1', '--all', '-o', str(folder)])
            self.assertEqual(sorted(path.stem for path in folder.glob('*.json')), sorted(KINDS))
            errors = (
                ['--seed', '-1', '--kind', 'sword', '-o', str(path)],
                ['--tier', '9', '--kind', 'sword', '-o', str(path)],
                ['--all', '--kind', 'sword', '-o', str(folder)],
                ['-o', str(path)],
                ['--all', '-o', str(path)],
            )
            for args in errors:
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    main(args)


if __name__ == '__main__':
    unittest.main()
