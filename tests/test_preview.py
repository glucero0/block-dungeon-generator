"""The studio preview turns a generated file into shaded blocks, with no zoom control."""

import math
import tempfile
import tkinter as tk
import unittest
from pathlib import Path

from blk_dungeon_gen.emit import generate_layout
from blk_dungeon_gen.hub import generate_hub
from creature_gen.generate import generate_creature
from equipment_gen.generate import generate_item

from dungeon_gui.preview import faces_of, project


def _colors(faces):
    return {color for _face, color in faces}


def _span(faces):
    points = [point for face, _color in faces for point in face]
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    zs = [point[2] for point in points]
    return max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)


class FaceTests(unittest.TestCase):
    def test_a_wood_dungeon_uses_wood_and_marks_the_entrance(self):
        faces = faces_of(generate_layout(1, floors=1, chambers=2, theme='wood', creature='wolf'))
        colors = _colors(faces)
        self.assertIn('#8a5a34', colors)
        self.assertIn('#34d399', colors)
        self.assertTrue(all(color.startswith('#') and len(color) == 7 for color in colors))

    def test_a_stone_house_and_a_campfire_keep_their_shapes(self):
        house = faces_of(generate_hub(1, spokes=3, structure='house', theme='stone'))
        self.assertIn('#64748b', _colors(house))
        campfire = faces_of(generate_hub(1, spokes=2, structure='campfire'))
        self.assertIn('#c2410c', _colors(campfire))
        self.assertIn('#6b4630', _colors(campfire))

    def test_a_sword_stands_taller_than_it_is_wide(self):
        width, height, depth = _span(faces_of(generate_item('sword', 1, 1)))
        self.assertGreater(height, width)
        self.assertGreater(height, depth)

    def test_a_creature_stands_above_the_ground(self):
        faces = faces_of(generate_creature('wolf', 1))
        _width, height, depth = _span(faces)
        self.assertGreater(height, 0.5)
        self.assertGreater(max(_width, depth), height)

    def test_a_bad_color_falls_back_and_junk_draws_nothing(self):
        faces = faces_of({
            'kind': 'sword',
            'materials': {'iron': {'color': 'red'}},
            'parts': [{
                'material': 'iron',
                'geometry': {'type': 'box', 'width': 1, 'height': 2, 'depth': 1},
                'position': [0, 0, 0],
            }],
        })
        self.assertEqual(_colors(faces), {'#94a3b8'})
        self.assertEqual(faces_of({'parts': [{'geometry': {'type': 'box'}}]}), [])
        self.assertEqual(faces_of('nope'), [])
        self.assertEqual(faces_of({'rooms': [{'polygon': 'nope'}]}), [])

    def test_turning_moves_the_picture_without_a_zoom(self):
        faces = [([(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)], '#ff0000')]
        flat = project(faces, 0, 0, 200, 200)
        turned = project(faces, math.pi / 2, 0, 200, 200)
        self.assertNotEqual(flat[0][0], turned[0][0])
        self.assertTrue(flat[0][1].startswith('#') and len(flat[0][1]) == 7)


class PreviewWindowTests(unittest.TestCase):
    def test_the_box_draws_and_the_arrows_turn_it(self):
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest('tkinter has no display')
        root.withdraw()
        try:
            from dungeon_gui.app import GearTab
            from dungeon_gui.preview import Preview

            tab = GearTab(root)
            paths = [Path('other.json'), Path('sword-s1-t1.json')]
            self.assertEqual(tab.preview_path(paths).name, 'sword-s1-t1.json')
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / 'sword.json'
                path.write_text(
                    '{"kind":"sword","materials":{"iron":{"color":"#8b939c"}},'
                    '"parts":[{"material":"iron","geometry":{"type":"box","width":0.2,"height":1.2,"depth":0.05},'
                    '"position":[0,0.6,0]}]}',
                    encoding='utf-8',
                )
                preview = Preview(root)
                preview.canvas.configure(width=320, height=240)
                root.update_idletasks()
                preview.show_file(path)
                self.assertGreater(len(preview.canvas.find_all()), 0)
                before = preview.yaw
                preview.turn_right()
                preview.tilt()
                self.assertNotEqual(preview.yaw, before)
                self.assertNotEqual(preview.pitch, 0.45)
                preview.show_file(Path(folder) / 'missing.json')
                self.assertEqual(preview.canvas.itemcget(preview.canvas.find_all()[0], 'text'),
                                 'Could not preview this file.')
        finally:
            root.destroy()
