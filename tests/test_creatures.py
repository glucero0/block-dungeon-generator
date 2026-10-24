"""Creature files on the Harper's Row skeletal warrior template."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from creature_gen import SPECIES_IDS, generate_creature
from creature_gen.__main__ import main
from creature_gen.schema import validate
from creature_gen.species import WEAPONS


def _joint(creature, name):
    return next(record for record in creature['joints'] if record['name'] == name)


def _part(creature, name):
    return next(record for record in creature['parts'] if record['name'] == name)


def _capsule_half(record):
    geometry = record['geometry']
    return geometry['length'] / 2 + geometry['radius']


def _withers(creature):
    chest = _part(creature, 'chest')
    return chest['position'][1] + chest['geometry']['radius']


def _torso_length(creature):
    chest = _part(creature, 'chest')
    pelvis = _part(creature, 'pelvis')
    return (chest['position'][2] + _capsule_half(chest)) - (pelvis['position'][2] - _capsule_half(pelvis))


class CreatureTests(unittest.TestCase):
    def test_every_species_is_deterministic(self):
        for species in SPECIES_IDS:
            for seed in (0, 1, 7):
                first = generate_creature(species, seed)
                second = generate_creature(species, seed)
                self.assertEqual(first, second)
                self.assertEqual(first['species'], species)
                self.assertEqual(first['seed'], seed)
                self.assertEqual(first['options'], {'species': species, 'seed': seed})
                self.assertLessEqual(first['stats']['minWindup'], first['stats']['windup'])
                self.assertLessEqual(first['stats']['minRecover'], first['stats']['recover'])
                self.assertNotIn('prefab', json.dumps(first))
                validate(first)

    def test_seed_changes_colour_and_keeps_joints(self):
        for species in SPECIES_IDS:
            first = generate_creature(species, 1)
            second = generate_creature(species, 2)
            self.assertEqual(first['joints'], second['joints'])
            self.assertNotEqual(first['materials'], second['materials'])

    def test_skeleton_matches_the_template(self):
        skeleton = generate_creature('skeleton', 1)
        self.assertEqual(skeleton['scale'], 1)
        self.assertEqual(skeleton['plan'], 'humanoid')
        self.assertEqual(_part(skeleton, 'pelvis')['position'], [0.0, 2.95, 0.0])
        self.assertEqual(_joint(skeleton, 'spine')['position'], [0.0, 3.05, 0.0])
        self.assertEqual(_joint(skeleton, 'skull')['position'], [0.0, 1.16, 0.03])
        self.assertEqual(_joint(skeleton, 'Hip_L')['position'], [-0.18, 2.9, 0.0])
        self.assertEqual(_joint(skeleton, 'Hip_R')['position'], [0.18, 2.9, 0.0])
        self.assertEqual(_joint(skeleton, 'spine')['parent'], 'fall')
        self.assertEqual(_joint(skeleton, 'Forearm_R')['parent'], 'SkeletonArm_R')
        self.assertEqual(_joint(skeleton, 'HandSocket_R')['parent'], 'WristJoint_R')
        self.assertIn('bone', skeleton['materials'])
        self.assertNotIn('skin', skeleton['materials'])
        self.assertNotIn('hair', skeleton['materials'])
        self.assertFalse(any(part['name'] == 'hair' for part in skeleton['parts']))
        self.assertEqual(
            skeleton['weapons'],
            [{'id': item['id'], 'range': item['range']} for item in WEAPONS],
        )

    def test_human_goblin_and_wolf(self):
        human = generate_creature('human', 1)
        goblin = generate_creature('goblin', 1)
        wolf = generate_creature('wolf', 1)
        for key in ('skin', 'hair', 'cloth'):
            self.assertIn(key, human['materials'])
            self.assertTrue(any(part['material'] == key for part in human['parts']))
        self.assertEqual(
            [joint['name'] for joint in human['joints']],
            [joint['name'] for joint in generate_creature('skeleton', 1)['joints']],
        )
        self.assertLess(goblin['scale'], human['scale'])
        self.assertIn('fur', wolf['materials'])
        self.assertNotIn('cloth', wolf['materials'])
        self.assertNotIn('weapons', wolf)
        hips = [joint for joint in wolf['joints'] if joint['name'].startswith('Hip_')]
        self.assertEqual(len(hips), 4)
        self.assertGreater(_part(wolf, 'snout')['position'][2], 0)
        self.assertGreater(_joint(wolf, 'head')['position'][2], 0)

    def test_quadruped_proportions(self):
        unit = 3.2
        horse = generate_creature('horse', 1)
        rat = generate_creature('rat', 1)
        self.assertEqual(horse['scale'], 1)
        self.assertEqual(rat['scale'], 1)
        for creature in (horse, rat):
            self.assertEqual(_part(creature, 'chest')['geometry']['type'], 'capsule')
            self.assertEqual(_part(creature, 'pelvis')['geometry']['type'], 'capsule')
            self.assertEqual(_part(creature, 'cranium')['geometry']['type'], 'capsule')
            self.assertEqual(_part(creature, 'jaw')['geometry']['type'], 'capsule')
            self.assertEqual(_part(creature, 'snout')['geometry']['type'], 'cone')
            self.assertGreater(
                _part(creature, 'chest')['geometry']['radius'],
                _part(creature, 'pelvis')['geometry']['radius'],
            )
            neck = _part(creature, 'neck')['geometry']
            self.assertEqual(neck['type'], 'cylinder')
            self.assertGreater(neck['radiusBottom'], neck['radiusTop'])
            self.assertGreater(_joint(creature, 'neck')['rotation']['x'], 25)
            self.assertEqual({_part(creature, 'eyeL')['geometry']['type'], _part(creature, 'eyeR')['geometry']['type']}, {'sphere'})
            self.assertEqual({_part(creature, 'earL')['geometry']['type'], _part(creature, 'earR')['geometry']['type']}, {'cone'})
            self.assertAlmostEqual(_part(creature, 'eyeL')['position'][0], -_part(creature, 'eyeR')['position'][0], places=4)
            for label in ('FL', 'FR', 'BL', 'BR'):
                for bone in ('upper', 'lower', 'cannon', 'hoof'):
                    self.assertEqual(_part(creature, f'{bone}{label}')['geometry']['type'], 'capsule')
                self.assertEqual(_joint(creature, f'Ankle_{label}')['parent'], f'Knee_{label}')
            self.assertGreater(_joint(creature, 'Knee_BL')['position'][2], 0)
            self.assertLess(_joint(creature, 'Ankle_BL')['position'][2], 0)
            self.assertGreater(_part(creature, 'tail0')['position'][1], _part(creature, 'tail2')['position'][1])
            self.assertFalse(any(part['geometry']['type'] == 'box' for part in creature['parts']))
        self.assertAlmostEqual(_withers(horse), 1.6 * unit, places=2)
        self.assertAlmostEqual(_torso_length(horse), 2.4 * unit, places=2)
        self.assertAlmostEqual(_withers(rat), 0.10 * unit, places=2)
        self.assertAlmostEqual(_torso_length(rat), 0.25 * unit, places=2)
        self.assertEqual(len([part for part in horse['parts'] if part['name'].startswith('mane')]), 5)
        self.assertTrue(any(part['name'].startswith('antler') for part in generate_creature('deer', 1)['parts']))
        self.assertTrue(any(part['name'].startswith('tusk') for part in generate_creature('boar', 1)['parts']))

    def test_fur_colour_and_length_follow_the_seed(self):
        patterns = {'solid', 'agouti', 'brindle', 'patch'}
        for species in ('wolf', 'bear', 'boar', 'horse', 'deer', 'rat'):
            first = generate_creature(species, 1)['materials']['fur']
            second = generate_creature(species, 2)['materials']['fur']
            self.assertIn(first['pattern'], patterns)
            self.assertEqual(len(first['tip']), 7)
            self.assertNotEqual(first['length'], second['length'])
            self.assertTrue(
                first['color'] != second['color'] or first['tip'] != second['tip'] or first['pattern'] != second['pattern']
            )
        wolf = generate_creature('wolf', 1)
        later = generate_creature('wolf', 5)
        self.assertEqual(wolf['joints'], later['joints'])
        self.assertNotEqual(wolf['materials']['fur']['length'], later['materials']['fur']['length'])
        bear = [generate_creature('bear', seed)['materials']['fur']['length'] for seed in range(8)]
        horse_coat = [generate_creature('horse', seed)['materials']['fur']['length'] for seed in range(8)]
        rat = [generate_creature('rat', seed)['materials']['fur']['length'] for seed in range(8)]
        self.assertGreater(min(bear), max(horse_coat))
        self.assertGreater(min(horse_coat), max(rat))
        for entry in generate_creature('human', 1)['materials'].values():
            self.assertEqual(set(entry), {'color', 'roughness', 'metalness'})
        wolf_fur = generate_creature('wolf', 1)['materials']['fur']
        self.assertGreaterEqual(wolf_fur['roughness'], 0.85)
        self.assertLessEqual(wolf_fur['roughness'], 0.95)
        self.assertEqual(wolf_fur['metalness'], 0)
        self.assertEqual(len(wolf_fur['belly']), 7)

    def test_wolf_is_a_canid(self):
        wolf = generate_creature('wolf', 1)
        horse = generate_creature('horse', 1)
        self.assertGreater(_joint(wolf, 'neck')['rotation']['x'], 90)
        self.assertLess(_joint(horse, 'neck')['rotation']['x'], 90)
        chest = _part(wolf, 'chest')['geometry']['radius']
        abdomen = _part(wolf, 'abdomen')['geometry']['radius']
        pelvis = _part(wolf, 'pelvis')['geometry']['radius']
        self.assertGreater(chest, abdomen)
        self.assertGreater(abdomen, pelvis)
        self.assertGreater(_part(wolf, 'abdomen')['position'][1], _part(wolf, 'chest')['position'][1])
        self.assertEqual(_part(wolf, 'cranium')['geometry']['type'], 'capsule')
        self.assertNotIn('rotation', _part(wolf, 'cranium'))
        cheeks = _part(wolf, 'cheeks')['geometry']
        self.assertEqual(cheeks['type'], 'cylinder')
        self.assertEqual(_part(wolf, 'cheeks')['rotation']['z'], -90)
        self.assertGreater(cheeks['height'], cheeks['radiusTop'] * 2)
        self.assertGreater(_part(wolf, 'snout')['position'][1], 0)
        self.assertLess(_part(wolf, 'earL')['rotation']['x'], -90)
        self.assertEqual(_part(wolf, 'earL')['geometry']['type'], 'cone')
        self.assertLess(_joint(wolf, 'Hip_FL')['position'][1], _withers(wolf))
        self.assertGreater(_part(wolf, 'hoofFL')['position'][2], 0)
        self.assertLess(_joint(wolf, 'Ankle_BL')['position'][2], 0)
        self.assertGreater(
            _part(wolf, 'tail0')['geometry']['radius'],
            _part(wolf, 'tail3')['geometry']['radius'],
        )
        self.assertLess(_part(wolf, 'tail0')['position'][1], 0)
        self.assertGreater(_part(wolf, 'tail0')['position'][1], _part(wolf, 'tail3')['position'][1])
        self.assertTrue(any(part['name'] == 'belly' for part in wolf['parts']))

    def test_rejected_files(self):
        for args in (('drake', 1), ('human', -1), ('human', True)):
            with self.assertRaises(ValueError):
                generate_creature(*args)
        creature = generate_creature('skeleton', 1)
        creature['version'] = 1
        with self.assertRaises(ValueError):
            validate(creature)
        creature = generate_creature('skeleton', 1)
        creature['weapons'][0]['id'] = 'spear'
        with self.assertRaises(ValueError):
            validate(creature)
        creature = generate_creature('skeleton', 1)
        creature['joints'] = [joint for joint in creature['joints'] if joint['name'] != 'Hip_L']
        with self.assertRaises(ValueError):
            validate(creature)
        creature = generate_creature('human', 1)
        creature['description'] = 'eval is not allowed here'
        with self.assertRaises(ValueError):
            validate(creature)
        creature = generate_creature('skeleton', 1)
        creature['materials']['bone']['prefab'] = 'prefabs/campfire_lit.glb'
        with self.assertRaises(ValueError):
            validate(creature)
        creature = generate_creature('skeleton', 1)
        creature['stats']['minWindup'] = creature['stats']['windup'] + 1
        with self.assertRaises(ValueError):
            validate(creature)
        creature = generate_creature('wolf', 1)
        creature['weapons'] = [{'id': 'sword', 'range': 2}]
        with self.assertRaises(ValueError):
            validate(creature)
        creature = generate_creature('wolf', 1)
        creature['materials']['fur']['pattern'] = 'stripe'
        with self.assertRaises(ValueError):
            validate(creature)
        creature = generate_creature('wolf', 1)
        for key in ('length', 'tip', 'pattern'):
            del creature['materials']['fur'][key]
        with self.assertRaises(ValueError):
            validate(creature)
        creature = generate_creature('human', 1)
        creature['materials']['skin']['length'] = 0.2
        with self.assertRaises(ValueError):
            validate(creature)

    def test_cli_writes_one_file_or_every_species(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'skeleton.json'
            main(['--seed', '1', '--species', 'skeleton', '-o', str(path)])
            written = json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(written, generate_creature('skeleton', 1))
            folder = Path(directory) / 'all'
            main(['--seed', '0', '--all', '-o', str(folder)])
            self.assertEqual(sorted(item.stem for item in folder.glob('*.json')), sorted(SPECIES_IDS))
            errors = (
                ['--seed', '-1', '--species', 'human', '-o', str(path)],
                ['--all', '--species', 'human', '-o', str(folder)],
                ['-o', str(path)],
                ['--all', '-o', str(path)],
            )
            for args in errors:
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    main(args)


if __name__ == '__main__':
    unittest.main()
