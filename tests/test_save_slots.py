"""Three save slots, each a tank with its own squid (src/save_slots.py).

A save is still {uuid}.zip in the saves folder; a slot is a line in
slots.json. Nothing done in one slot may touch another's squid.
"""
import inspect
import json
import os
import time
import zipfile

import pytest

from src.save_slots import SLOTS, SaveSlots, normal, squid_of

A = 'aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa'
B = 'bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb'
C = 'cccccccc-3333-4333-8333-cccccccccccc'
D = 'dddddddd-4444-4444-8444-dddddddddddd'


def _save(folder, squid, name='Squid', file_name=None, age=0, autosave=False, stage='living', older=0):
    path = folder / (file_name or (squid.replace('-', '_') + ('_autosave' if autosave else '') + '.zip'))
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('game_state.json', json.dumps({
            'squid': {'name': name, 'personality': 'timid', 'uuid': squid},
            'lifecycle': {'stage': stage}}))
        archive.writestr('statistics.json', json.dumps({'total_age_seconds': age}))
        archive.writestr('uuid.txt', f'SquidSignature    {squid}')
    if older:
        stamp = time.time() - older
        os.utime(path, (stamp, stamp))
    return path


def test_there_are_three_and_they_start_empty(tmp_path):
    slots = SaveSlots(tmp_path)
    assert SLOTS == 3
    assert [entry['empty'] for entry in slots.describe()] == [True, True, True]
    assert slots.active == 1 and slots.path_for() is None
    assert slots.choose_startup_slot() == 1


def test_saves_keep_their_zip_and_their_squids_name(tmp_path):
    """The file is untouched and still named after the squid; the slot is
    only a line in slots.json."""
    path = _save(tmp_path, A, 'Inky', age=754)
    before = path.read_bytes()
    slots = SaveSlots(tmp_path)
    entry = slots.describe()[0]
    assert (entry['name'], entry['uuid'], entry['empty']) == ('Inky', A, False)
    assert entry['age_seconds'] == 754 and entry['path'] == str(path)
    assert path.read_bytes() == before and path.name == A.replace('-', '_') + '.zip'
    assert json.loads((tmp_path / 'slots.json').read_text()) == {
        'active': 1, 'slots': {'1': A, '2': None, '3': None}}


def test_saves_from_before_slots_and_dropped_in_ones_are_given_slots(tmp_path):
    _save(tmp_path, A, 'Old', older=300)
    _save(tmp_path, B, 'Hatchling', file_name='from-the-breeder.zip', older=100)     # any file name
    _save(tmp_path, A, 'Old', autosave=True, older=200)                              # the same squid
    slots = SaveSlots(tmp_path)
    state = slots.refresh()
    assert state['slots'] == {1: B, 2: A, 3: None}          # newest first, one slot each
    assert squid_of(tmp_path / 'from-the-breeder.zip') == B
    # the newer of a squid's saves is the one opened
    assert slots.path_for(2).endswith('_autosave.zip')
    # a fourth and fifth squid: one slot left, the other is left alone in no slot
    _save(tmp_path, C, 'Third', older=50)
    _save(tmp_path, D, 'Fourth', older=60)
    state = slots.refresh()
    assert state['slots'][3] == C and state['unslotted'] == [D]
    assert (tmp_path / (D.replace('-', '_') + '.zip')).exists()          # never deleted


def test_a_slot_whose_squid_is_gone_is_empty_again(tmp_path):
    path = _save(tmp_path, A)
    slots = SaveSlots(tmp_path)
    assert slots.squid_in(1) == A
    path.unlink()
    assert slots.squid_in(1) is None and slots.describe()[0]['empty']


def test_the_game_starts_in_the_slot_last_played(tmp_path):
    _save(tmp_path, A, older=500)
    _save(tmp_path, B, older=10)
    slots = SaveSlots(tmp_path)
    slots.refresh()                      # B (newest) in 1, A in 2
    slots.set_active(2)
    assert slots.choose_startup_slot() == 2          # not simply the newest save
    slots.set_active(3)                              # an empty slot was last played
    assert slots.choose_startup_slot() == 1          # then the most recently saved
    with pytest.raises(ValueError):
        slots.set_active(4)


def test_an_heir_takes_its_parents_slot_and_a_new_squid_a_free_one(tmp_path):
    _save(tmp_path, A)
    _save(tmp_path, B)
    slots = SaveSlots(tmp_path)
    slots.refresh()
    playing = slots.slot_of(A)
    slots.set_active(playing)
    # A dies; its saves are deleted and its heir C is saved in the same tank
    (tmp_path / (A.replace('-', '_') + '.zip')).unlink()
    _save(tmp_path, C)
    assert slots.record_save(C) == playing
    assert slots.slot_of(B) != playing and slots.squid_in(playing) == C
    # a squid already in a slot stays there; the squid just saved is the one being played
    assert slots.record_save(B) == slots.slot_of(B) == slots.active
    slots.set_active(playing)
    # a new squid while the active slot's squid lives takes a free slot
    _save(tmp_path, D)
    free = slots.record_save(D)
    assert free not in (playing, slots.slot_of(B)) and slots.squid_in(free) == D


def test_deleting_a_slot_deletes_that_squid_only(tmp_path):
    _save(tmp_path, A)
    _save(tmp_path, A, autosave=True)
    _save(tmp_path, A, file_name='copy-of-a.zip')
    kept = _save(tmp_path, B)
    slots = SaveSlots(tmp_path)
    slot = slots.slot_of(A)
    assert slots.delete(slot) == 3
    assert slots.squid_in(slot) is None
    assert kept.exists() and slots.slot_of(B) is not None
    assert slots.delete(slot) == 0


def test_the_save_manager_speaks_for_the_slot_being_played(tmp_path):
    """"Is there a save", "the latest save" and "delete the save" used to mean
    the newest zip in the folder, whoever's it was."""
    from src.save_manager import SaveManager
    _save(tmp_path, A, older=300)
    _save(tmp_path, B, older=10)                     # the newest file in the folder
    manager = SaveManager(str(tmp_path))
    manager.slots.refresh()
    manager.slots.set_active(manager.slots.slot_of(A))
    assert manager.save_exists()
    assert squid_of(manager.get_latest_save()) == A  # not B's, though B's is newer
    manager.slots.set_active(3)                      # an empty slot: a new game there
    assert not manager.save_exists() and manager.get_latest_save() is None
    assert not manager.delete_save()                 # and nothing of anyone's is deleted
    assert len(list(tmp_path.glob('*.zip'))) == 2
    # a squid's death removes every file of that squid, whatever it is called
    _save(tmp_path, A, file_name='renamed.zip')
    assert manager.delete_saves_for(A) == 2
    assert manager.slots.slot_of(A) is None and manager.slots.slot_of(B) is not None


def test_saving_puts_the_squid_in_the_slot_being_played(tmp_path):
    from src.save_manager import SaveManager
    manager = SaveManager(str(tmp_path))
    manager.slots.set_active(2)
    data = {'game_state': {'squid': {'uuid': A, 'name': 'Pip'}}, 'brain_state': None}
    path = manager.save_game(data)
    assert os.path.basename(path) == A.replace('-', '_') + '.zip'
    assert zipfile.is_zipfile(path)
    assert manager.slots.squid_in(2) == A and manager.slots.describe()[1]['name'] == 'Pip'


def test_the_game_opens_a_slot_without_touching_the_one_it_leaves():
    import main
    source = inspect.getsource(main.MainWindow._begin_new_life)
    switching = source[source.index('if switching:'):]
    assert 'self.save_manager.slots.set_active(to_slot)' in switching
    assert switching.index('set_active(to_slot)') < switching.index('delete_saves_for')
    assert 'carried_headstones = [] if switching' in source      # each slot is its own tank
    opened = inspect.getsource(main.MainWindow.open_slot)
    assert opened.index('self.save_game()') < opened.index('_begin_new_life(to_slot=slot)')
    created = inspect.getsource(main.MainWindow.create_new_game)
    assert 'slots.delete(self.save_manager.slots.active)' in created and '.delete_save()' not in created


def test_a_game_started_from_a_save_is_autosaved():
    from src.tamagotchi_logic import TamagotchiLogic
    assert 'self.start_autosave()' in inspect.getsource(TamagotchiLogic.load_game)


def test_ids_are_spelled_one_way():
    assert normal(A.upper().replace('-', '_')) == A
    assert squid_of(A.replace('-', '_') + '_autosave.zip') == A
    assert squid_of('autosave.zip') is None


def test_renaming_the_squid_renames_its_slot_and_never_its_file(tmp_path):
    """A slot is named after its squid; the archive is named after the
    squid's uuid, always."""
    from src.save_manager import SaveManager
    manager = SaveManager(str(tmp_path))
    data = {'game_state': {'squid': {'uuid': A, 'name': 'Squid'}}, 'brain_state': None}
    first = manager.save_game(data)
    assert manager.slots.describe()[0]['name'] == 'Squid'
    data = {'game_state': {'squid': {'uuid': A, 'name': 'Captain Nemo'}}, 'brain_state': None}
    second = manager.save_game(data)
    assert second == first and os.path.basename(second) == A.replace('-', '_') + '.zip'
    assert manager.slots.describe()[0]['name'] == 'Captain Nemo'
    assert [p.name for p in tmp_path.glob('*.zip')] == [A.replace('-', '_') + '.zip']
    # the game saves as the squid is renamed, and before the slots are shown
    import main
    from src.brain_about_tab import AboutTab
    renamed = inspect.getsource(AboutTab.edit_name)
    assert renamed.index('squid.name = new_name') < renamed.index('self.tamagotchi_logic.save_game()')
    shown = inspect.getsource(main.MainWindow.open_save_slots)
    assert shown.index('self.save_game()') < shown.index('choose_slot(')
