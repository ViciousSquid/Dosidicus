"""The phone has the desktop's three save slots (src/save_slots.py).

The slot logic itself is tested in tests/test_save_slots.py; here, that the
phone ships it, keeps its saves the same way, and follows the same rules.
"""
import ast
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'android'))

APP = (ROOT / 'android' / 'dosidicus_mobile' / 'ui' / 'app.py').read_text(encoding='utf-8')
SCREEN = (ROOT / 'android' / 'dosidicus_mobile' / 'ui' / 'slots_screen.py').read_text(encoding='utf-8')


def _method(name):
    tree = ast.parse(APP)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(APP, node)
    raise AssertionError(f'no {name} in the phone app')


def test_the_phone_build_ships_the_slot_logic():
    staging = (ROOT / 'android' / 'prepare_apk.py').read_text(encoding='utf-8')
    assert "'save_slots'" in staging


def test_a_phone_save_is_a_desktop_save_in_a_slot(tmp_path):
    """saves/{uuid}.zip, which the desktop's slots read as their own."""
    from dosidicus_mobile.engine import Simulation, Squid
    from src.save_slots import SaveSlots, normal
    sim = Simulation(tank_size=(800, 600), squid=Squid(tank_size=(800, 600)))
    sim.squid.name = 'Miso'
    squid = normal(sim.squid.uuid)
    slots = SaveSlots(tmp_path / 'saves')
    (tmp_path / 'saves').mkdir()
    path = tmp_path / 'saves' / (squid.replace('-', '_') + '.zip')
    sim.save(str(path))
    assert zipfile.is_zipfile(path)
    assert slots.record_save(squid) == 1
    entry = slots.describe()[0]
    assert (entry['name'], entry['uuid'], entry['active']) == ('Miso', squid, True)
    assert 'timeline.json' in zipfile.ZipFile(path).namelist()       # and it carries its life
    assert json.loads((tmp_path / 'saves' / 'slots.json').read_text())['slots']['1'] == squid


def test_the_one_save_a_phone_had_becomes_a_slots_squid():
    adopt = _method('_adopt_single_save')
    assert 'squid_save.zip' in adopt and 'os.replace(old, target)' in adopt
    assert "name = str(self.sim.squid.uuid).replace('-', '_') + '.zip'" in _method('save_path')


def test_a_replaced_squid_is_gone_but_never_one_with_a_slot_of_its_own():
    save = _method('_save')
    assert 'if held and held != squid and self.slots.slot_of(squid) is None:' in save
    assert save.index('self.slots.delete(active)') < save.index('self.sim.save(self.save_path)')
    assert 'self.slots.record_save(squid)' in save


def test_opening_a_slot_saves_the_squid_left_behind_first():
    opened = _method('open_slot')
    assert opened.index('self._save()') < opened.index('self.slots.set_active(slot)')
    assert 'self.new_game()' in opened and 'Simulation.load(path)' in opened


def test_the_phones_chooser_is_the_desktops():
    """The same colours and the same rule about the squid being played."""
    desktop = (ROOT / 'src' / 'slot_chooser.py').read_text(encoding='utf-8')
    for colour in ('#bfe8bd', '#f9cfa0', '#f3aaaa'):
        assert colour in desktop and colour in SCREEN
    assert "return not entry.get('empty') and entry['slot'] != self.playing" in SCREEN
    assert "'New game'" in SCREEN and "'Choose a slot'" in SCREEN and "'Delete which?'" in SCREEN
    menu = (ROOT / 'android' / 'dosidicus_mobile' / 'ui' / 'menu.py').read_text(encoding='utf-8')
    assert '"Save slots"' in menu


def test_renaming_the_squid_on_the_phone_renames_its_slot():
    """The slot reads its name from the save, so a rename saves at once, and
    the slots are shown from a save made that moment. The file keeps the
    squid's uuid as its name (save_path)."""
    menu = (ROOT / 'android' / 'dosidicus_mobile' / 'ui' / 'menu.py').read_text(encoding='utf-8')
    rename = menu[menu.index("squid.name = name.text.strip()"):]
    assert rename.index('app.save_now()') < rename.index('popup.dismiss()')
    opened = SCREEN[SCREEN.index('def open_slots(app):'):]
    assert opened.index('app.save_now()') < opened.index('SlotsView(')
