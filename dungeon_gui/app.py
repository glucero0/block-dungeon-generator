"""Four tabs that expose the generator options and write into out/."""

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from blk_dungeon_gen.structures import names as structure_names
from creature_gen.species import SPECIES_IDS
from equipment_gen.schema import KINDS

from .preview import Preview
from .write import (
    creature_name,
    dungeon_name,
    gear_name,
    hub_name,
    studio_root,
    write_creature,
    write_dungeon,
    write_gear,
    write_hub,
)

_PREFERRED = ('hut', 'house', 'tent', 'campfire', 'castle')
_known_structures = tuple(structure_names())
_STRUCTURES = ('from seed',) + tuple(name for name in _PREFERRED if name in _known_structures) + tuple(
    name for name in _known_structures if name not in _PREFERRED
)


def _shown(path):
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


class _Tab(ttk.Frame):
    """One generator form: fields, a filename, Generate, and a status line."""

    def __init__(self, master):
        super().__init__(master, padding=16)
        self.columnconfigure(1, weight=1)
        self._row = 0
        self._name_edited = False
        self._setting_name = False
        self.filename = tk.StringVar()

    def add(self, label, widget):
        ttk.Label(self, text=label).grid(row=self._row, column=0, sticky='w', pady=4, padx=(0, 16))
        widget.grid(row=self._row, column=1, sticky='ew', pady=4)
        self._row += 1
        return widget

    def spin(self, label, low, high, initial, step=1):
        widget = ttk.Spinbox(self, from_=low, to=high, increment=step, width=20, command=self.refresh_name)
        widget.set(str(initial))
        widget.bind('<KeyRelease>', lambda _event: self.refresh_name())
        return self.add(label, widget)

    def choice(self, label, values, initial):
        widget = ttk.Combobox(self, values=values, state='readonly', width=20)
        widget.set(initial)
        widget.bind('<<ComboboxSelected>>', lambda _event: self.refresh_name())
        return self.add(label, widget)

    def entry(self, label):
        widget = ttk.Entry(self, width=22)
        widget.bind('<KeyRelease>', lambda _event: self.refresh_name())
        return self.add(label, widget)

    def check(self, label, command):
        variable = tk.BooleanVar(value=False)
        widget = ttk.Checkbutton(self, text=label, variable=variable, command=command)
        widget.grid(row=self._row, column=1, sticky='w', pady=4)
        self._row += 1
        return variable

    def finish(self, folder_label):
        self.file_entry = self.add(folder_label, ttk.Entry(self, textvariable=self.filename, width=22))
        self.filename.trace_add('write', self._on_filename)
        ttk.Button(self, text='Generate', command=self.generate).grid(
            row=self._row, column=1, sticky='w', pady=(12, 4))
        self._row += 1
        self.status = ttk.Label(self, text='Choose options and generate.', wraplength=420, justify='left')
        self.status.grid(row=self._row, column=0, columnspan=2, sticky='ew', pady=(8, 0))
        self.preview = Preview(self)
        self.preview.grid(row=self._row + 1, column=0, columnspan=2, sticky='nsew', pady=(12, 0))
        self.rowconfigure(self._row + 1, weight=1)
        self.refresh_name()

    def _on_filename(self, *_args):
        if not self._setting_name:
            self._name_edited = True

    def refresh_name(self):
        if self._name_edited:
            return
        try:
            suggested = self.suggested_name()
        except (TypeError, ValueError, AttributeError):
            return
        self._setting_name = True
        self.filename.set(suggested)
        self._setting_name = False

    def suggested_name(self):
        raise NotImplementedError

    def produce(self):
        raise NotImplementedError

    def generate(self):
        self.refresh_name()
        try:
            paths = self.produce()
        except (TypeError, ValueError) as error:
            self.status.configure(text=str(error), foreground='#9f1239')
            return
        if len(paths) == 1:
            message = f'Wrote {_shown(paths[0])}'
        else:
            message = f'Wrote {len(paths)} files in {_shown(paths[0].parent)}'
        self.status.configure(text=message, foreground='#166534')
        self.preview.show_file(self.preview_path(paths))

    def preview_path(self, paths):
        return paths[0]

    def filename_text(self):
        return self.filename.get()


class DungeonTab(_Tab):
    def __init__(self, master):
        super().__init__(master)
        self.seed = self.spin('Seed', 0, 1_000_000, 1)
        self.floors = self.spin('Floors', 1, 8, 2)
        self.chambers = self.spin('Chambers', 2, 30, 8)
        self.density = self.choice('Density', ('low', 'normal', 'high'), 'normal')
        self.clutter = self.spin('Clutter', 0, 1, '0.5', step=0.1)
        self.theme = self.choice('Theme', ('mixed', 'stone', 'wood', 'cave'), 'mixed')
        self.creature = self.choice('Creature', ('unset',) + tuple(SPECIES_IDS), 'unset')
        self.finish('File in out/dungeons')

    def _values(self):
        return (
            self.seed.get(), self.floors.get(), self.chambers.get(), self.density.get(),
            self.clutter.get(), self.theme.get(), self.creature.get(),
        )

    def suggested_name(self):
        return dungeon_name(*self._values())

    def produce(self):
        return write_dungeon(studio_root(), *self._values(), self.filename_text())


class HubTab(_Tab):
    def __init__(self, master):
        super().__init__(master)
        self.seed = self.spin('Seed', 0, 1_000_000, 1)
        self.structure = self.choice('Structure', _STRUCTURES, 'from seed')
        self.spokes = self.spin('Spokes', 1, 8, 3)
        self.names = self.entry('Names (comma separated)')
        self.clutter = self.spin('Clutter', 0, 1, '0.5', step=0.1)
        self.theme = self.choice('Theme', ('mixed', 'stone', 'wood', 'cave'), 'mixed')
        self.creature = self.choice('Creature', ('unset',) + tuple(SPECIES_IDS), 'unset')
        self.finish('File in out/hubs')

    def _values(self):
        return (
            self.seed.get(), self.structure.get(), self.spokes.get(), self.names.get(),
            self.clutter.get(), self.theme.get(), self.creature.get(),
        )

    def suggested_name(self):
        return hub_name(*self._values())

    def produce(self):
        return write_hub(studio_root(), *self._values(), self.filename_text())


class _AllTab(_Tab):
    """Gear or creatures: an All switch disables the single-item fields."""

    def __init__(self, master, all_label):
        super().__init__(master)
        self.all_label = all_label

    def build_all(self, menu):
        self.menu = menu
        self.all_flag = self.check(self.all_label, self._toggle_all)

    def _toggle_all(self):
        if not hasattr(self, 'file_entry'):
            return
        state = 'disabled' if self.all_flag.get() else 'readonly'
        self.menu.configure(state=state)
        self.file_entry.configure(state='disabled' if self.all_flag.get() else 'normal')
        self.refresh_name()


class GearTab(_AllTab):
    def __init__(self, master):
        super().__init__(master, 'All kinds')
        self.seed = self.spin('Seed', 0, 1_000_000, 1)
        self.kind = self.choice('Kind', KINDS, 'sword')
        self.tier = self.spin('Tier', 1, 5, 1)
        self.build_all(self.kind)
        self.finish('File in out/gear')

    def suggested_name(self):
        return gear_name(self.kind.get(), self.seed.get(), self.tier.get())

    def produce(self):
        return write_gear(
            studio_root(), self.seed.get(), self.kind.get(), self.tier.get(),
            self.all_flag.get(), self.filename_text(),
        )

    def preview_path(self, paths):
        if len(paths) == 1:
            return paths[0]
        wanted = gear_name(self.kind.get(), self.seed.get(), self.tier.get())
        for path in paths:
            if path.name == wanted:
                return path
        return paths[0]


class CreatureTab(_AllTab):
    def __init__(self, master):
        super().__init__(master, 'All species')
        self.seed = self.spin('Seed', 0, 1_000_000, 1)
        self.species = self.choice('Species', SPECIES_IDS, 'skeleton')
        self.build_all(self.species)
        self.finish('File in out/creatures')

    def suggested_name(self):
        return creature_name(self.species.get(), self.seed.get())

    def produce(self):
        return write_creature(
            studio_root(), self.seed.get(), self.species.get(),
            self.all_flag.get(), self.filename_text(),
        )

    def preview_path(self, paths):
        if len(paths) == 1:
            return paths[0]
        wanted = creature_name(self.species.get(), self.seed.get())
        for path in paths:
            if path.name == wanted:
                return path
        return paths[0]


def main():
    root = tk.Tk()
    root.title('Block Dungeon Generator')
    root.minsize(540, 920)
    root.geometry('560x920')
    notebook = ttk.Notebook(root)
    notebook.pack(fill='both', expand=True, padx=8, pady=8)
    notebook.add(DungeonTab(notebook), text='Dungeons')
    notebook.add(HubTab(notebook), text='Hubs')
    notebook.add(GearTab(notebook), text='Gear')
    notebook.add(CreatureTab(notebook), text='Creatures')
    root.mainloop()
