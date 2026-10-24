"""The studio writer keeps every file inside its own folder."""

import json
import tempfile
import unittest
from pathlib import Path

from blk_dungeon_gen.structures import names as structure_names
from creature_gen.species import SPECIES_IDS
from equipment_gen.schema import KINDS

from dungeon_gui.write import (
    creature_name,
    dungeon_name,
    gear_name,
    hub_name,
    write_creature,
    write_dungeon,
    write_gear,
    write_hub,
)


def _load(path):
    return json.loads(path.read_text(encoding='utf-8'))


class NameTests(unittest.TestCase):
    def test_defaults_use_the_options(self):
        self.assertEqual(
            dungeon_name(1, 2, 8, 'normal', 0.5, 'stone', 'wolf'),
            's1-f2-c8-normal-k0p5-stone-wolf.json',
        )
        self.assertEqual(
            hub_name(1, 'house', 3, 'ruins, forest', 0.5, None, None),
            's1-house-p3-ruins-forest-k0p5-mixed-unset.json',
        )
        self.assertEqual(gear_name('sword', 1, 2), 'sword-s1-t2.json')
        self.assertEqual(creature_name('wolf', 1), 'wolf-s1.json')

    def test_a_long_hub_name_stays_short(self):
        names = ', '.join(f'n{index}' + ('a' * 30) for index in range(8))
        name = hub_name(1, 'house', 8, names, 0.5, 'cave', 'orc')
        self.assertLessEqual(len(name), 120)
        self.assertTrue(name.endswith('.json'))


class WriterTests(unittest.TestCase):
    def test_dungeon_lands_in_its_folder_and_repeats(self):
        with tempfile.TemporaryDirectory() as folder:
            first = write_dungeon(folder, 1, 1, 2, 'low', 0, 'stone', 'wolf', 'keep.json')
            again = write_dungeon(folder, '1', '1', '2', 'low', '0', 'stone', 'wolf', 'keep.json')
            self.assertEqual(first[0].parent.name, 'dungeons')
            self.assertEqual(first[0].read_bytes(), again[0].read_bytes())
            document = _load(first[0])
            self.assertEqual(document['options']['theme'], 'stone')
            self.assertEqual(document['options']['creature'], 'wolf')
            self.assertEqual(document['enemyName'], 'Wolf')
            self.assertTrue(all(room['theme'] == 'stone' for room in document['rooms']))

    def test_mixed_theme_and_unset_creature_stay_empty(self):
        with tempfile.TemporaryDirectory() as folder:
            path = write_dungeon(folder, 1, 1, 2, 'normal', 0.5, 'mixed', 'unset', 'plain.json')[0]
            document = _load(path)
            self.assertIsNone(document['options']['theme'])
            self.assertIsNone(document['options']['creature'])
            self.assertNotIn('enemyName', document)

    def test_hub_lands_in_its_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            path = write_hub(
                folder, 1, 'house', 3, 'ruins, forest', 0.5, 'stone', 'unset', 'hub.json')[0]
            self.assertEqual(path.parent.name, 'hubs')
            document = _load(path)
            self.assertEqual(document['kind'], 'hub')
            self.assertEqual(document['structure']['type'], 'house')
            self.assertEqual(document['structure']['material'], 'stone')
            self.assertEqual([spoke['name'] for spoke in document['hubArea']['spokes'][:2]],
                             ['ruins', 'forest'])
            self.assertIsNone(document['options']['creature'])

    def test_from_seed_picks_a_known_structure(self):
        with tempfile.TemporaryDirectory() as folder:
            document = _load(write_hub(
                folder, 1, 'from seed', 3, '', 0.5, 'mixed', 'bear', 'auto.json')[0])
            self.assertIn(document['structure']['type'], structure_names())
            self.assertEqual(document['enemyName'], 'Bear')
            self.assertEqual(document['rooms'][0]['spawns'] if document['rooms'] else [], [])

    def test_gear_one_and_all(self):
        with tempfile.TemporaryDirectory() as folder:
            one = write_gear(folder, 1, 'sword', 2, False, 'blade.json')
            self.assertEqual(one[0].parent.name, 'gear')
            self.assertEqual(_load(one[0])['kind'], 'sword')
            paths = write_gear(folder, 3, 'sword', 1, True, '../escape.json')
            self.assertEqual(len(paths), len(KINDS))
            self.assertEqual({path.name for path in paths}, {gear_name(kind, 3, 1) for kind in KINDS})
            self.assertTrue(all(path.parent.name == 'gear' for path in paths))
            self.assertEqual(paths[0].read_bytes(), write_gear(folder, 3, 'ignored', 1, True, 'nope.json')[0].read_bytes())

    def test_creatures_one_and_all(self):
        with tempfile.TemporaryDirectory() as folder:
            one = write_creature(folder, 1, 'goblin', False, 'goblin.json')
            self.assertEqual(one[0].parent.name, 'creatures')
            self.assertEqual(_load(one[0])['options']['species'], 'goblin')
            paths = write_creature(folder, 4, 'goblin', True, '../escape.json')
            self.assertEqual({path.name for path in paths}, {creature_name(species, 4) for species in SPECIES_IDS})
            self.assertTrue(all(path.parent.name == 'creatures' for path in paths))

    def test_bad_names_and_paths_write_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cases = (
                lambda: write_dungeon(folder, 1, 1, 2, 'normal', 0.5, 'marble', 'wolf', 'a.json'),
                lambda: write_dungeon(folder, 1, 9, 2, 'normal', 0.5, 'stone', 'wolf', 'a.json'),
                lambda: write_dungeon(folder, -1, 1, 2, 'normal', 0.5, 'stone', 'wolf', 'a.json'),
                lambda: write_dungeon(folder, 1, 1, 2, 'normal', 0.5, 'stone', 'dragon', 'a.json'),
                lambda: write_dungeon(folder, 1, 1, 2, 'normal', 2, 'stone', 'wolf', 'a.json'),
                lambda: write_dungeon(folder, 1, 1, 2, 'normal', 0.5, 'stone', 'wolf', '../x.json'),
                lambda: write_dungeon(folder, 1, 1, 2, 'normal', 0.5, 'stone', 'wolf', 'nested/a.json'),
                lambda: write_dungeon(folder, 1, 1, 2, 'normal', 0.5, 'stone', 'wolf', '..\\x.json'),
                lambda: write_dungeon(folder, 1, 1, 2, 'normal', 0.5, 'stone', 'wolf', 'con.json'),
                lambda: write_hub(folder, 1, 'palace', 3, '', 0.5, 'mixed', 'unset', 'a.json'),
                lambda: write_hub(folder, 1, 'house', 3, 'Hub', 0.5, 'mixed', 'unset', 'a.json'),
                lambda: write_hub(folder, 1, 'house', 9, '', 0.5, 'mixed', 'unset', 'a.json'),
                lambda: write_gear(folder, 1, 'wand', 1, False, 'a.json'),
                lambda: write_gear(folder, 1, 'sword', 9, False, 'a.json'),
                lambda: write_creature(folder, 1, 'dragon', False, 'a.json'),
                lambda: write_creature(folder, 1, 'wolf', 'yes', 'a.json'),
            )
            for case in cases:
                with self.assertRaises(ValueError):
                    case()
            self.assertEqual(list(root.rglob('*.json')), [])


if __name__ == '__main__':
    unittest.main()
