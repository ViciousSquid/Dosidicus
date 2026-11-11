"""The slot chooser (src/slot_chooser.py): drawn in the family of the
language splash and the tutorial question."""
import json
import os
import zipfile

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
QtWidgets = pytest.importorskip('PyQt5.QtWidgets')
from PyQt5 import QtCore, QtGui, QtTest  # noqa: E402

from src import language_splash  # noqa: E402
from src.save_slots import SaveSlots  # noqa: E402
from src.slot_chooser import (PASTEL_GREEN, PASTEL_ORANGE, SlotChooser, age_text)  # noqa: E402

A = 'aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa'
B = 'bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb'


@pytest.fixture(scope='module')
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _save(folder, squid, name):
    with zipfile.ZipFile(folder / (squid.replace('-', '_') + '.zip'), 'w') as archive:
        archive.writestr('game_state.json', json.dumps({'squid': {'name': name, 'personality': 'timid', 'uuid': squid}}))
        archive.writestr('statistics.json', json.dumps({'total_age_seconds': 4000}))


def _slots(tmp_path):
    _save(tmp_path, A, 'Inky')
    slots = SaveSlots(tmp_path)
    slots.refresh()
    return slots


def test_a_used_slot_carries_its_squids_name_and_an_empty_one_says_new_game(app, tmp_path):
    dialog = SlotChooser(_slots(tmp_path))
    assert [row.title() for row in dialog.rows] == ['Inky', 'New game', 'New game']
    assert 'Timid' in dialog.rows[0].detail() and '1h 06m' in dialog.rows[0].detail()
    assert dialog.bar.text() == 'Choose a slot'


def test_empty_is_pastel_green_and_used_is_pastel_orange(app, tmp_path):
    dialog = SlotChooser(_slots(tmp_path))
    assert dialog.rows[0].colours() == PASTEL_ORANGE and dialog.rows[1].colours() == PASTEL_GREEN
    dialog.show()
    app.processEvents()
    image = dialog.grab().toImage()

    def colour_of(row):
        point = row.mapTo(dialog, QtCore.QPoint(row.width() - 30, 12))
        return QtGui.QColor(image.pixel(point)).name()
    dialog.rows[2].setFocus()            # the focused row is drawn a shade darker
    app.processEvents()
    image = dialog.grab().toImage()
    assert colour_of(dialog.rows[0]) == PASTEL_ORANGE[0]
    assert colour_of(dialog.rows[1]) == PASTEL_GREEN[0]


def test_it_is_drawn_like_the_language_and_tutorial_popups(app, tmp_path):
    """The same grey bar, the same heavy monospace, the same buttons."""
    dialog = SlotChooser(_slots(tmp_path))
    assert dialog.windowFlags() & QtCore.Qt.FramelessWindowHint
    assert language_splash.BAR_GREY in dialog.bar.styleSheet()
    assert dialog.bar.font().family() == language_splash.splash_font(10).family()
    assert language_splash.RED[0] in dialog.delete_button.styleSheet()        # dark red destroys
    assert language_splash.GREEN[0] in dialog.back_button.styleSheet()


def test_choosing_a_slot(app, tmp_path):
    dialog = SlotChooser(_slots(tmp_path))
    dialog.pick(2)
    assert dialog.chosen == 2 and dialog.result() == QtWidgets.QDialog.Accepted
    dialog = SlotChooser(_slots(tmp_path))
    dialog.show()
    QtTest.QTest.keyClick(dialog, QtCore.Qt.Key_3)
    assert dialog.chosen == 3


def test_deleting_asks_twice_and_never_the_squid_being_played(app, tmp_path):
    slots = _slots(tmp_path)
    _save(tmp_path, B, 'Ziggy')
    slots.refresh()
    playing = slots.slot_of(A)
    other = slots.slot_of(B)
    dialog = SlotChooser(slots, playing=playing)
    dialog.begin_deleting()
    assert dialog.bar.text() == 'Delete which?'
    assert not dialog.rows[playing - 1].isEnabled() and dialog.rows[other - 1].isEnabled()
    dialog.pick(playing)                                 # refused
    assert dialog.doomed is None
    dialog.pick(other)
    assert dialog.bar.text() == 'Delete Ziggy?' and slots.slot_of(B) == other      # not yet
    dialog.stop_deleting()                               # No
    assert slots.slot_of(B) == other
    dialog.begin_deleting()
    dialog.pick(other)
    dialog.delete_confirmed()                            # Yes
    assert slots.slot_of(B) is None and slots.slot_of(A) == playing
    assert dialog.rows[other - 1].title() == 'New game'
    assert dialog.chosen is None                         # deleting chooses nothing


def test_at_the_start_a_slot_must_be_chosen(app, tmp_path):
    dialog = SlotChooser(_slots(tmp_path))                # no game running
    dialog.show()
    assert not dialog.back_button.isVisible()
    QtTest.QTest.keyClick(dialog, QtCore.Qt.Key_Escape)
    assert dialog.isVisible()
    playing = SlotChooser(_slots(tmp_path), playing=1)
    playing.show()
    assert playing.back_button.isVisible()


def test_every_language_has_the_choosers_words():
    import importlib
    keys = ('save_slots', 'slot_choose', 'slot_new_game', 'slot_delete', 'slot_delete_which',
            'slot_delete_confirm', 'slot_back', 'slot_playing', 'slot_unnamed',
            'slot_stage_dead', 'slot_stage_parent')
    for code in ('en', 'de', 'es', 'fr', 'ja', 'zh', 'ml'):
        table = importlib.import_module(f'translations.{code}').translations
        for key in keys:
            assert table.get(key), (code, key)
        assert '{name}' in table['slot_delete_confirm'], code


def test_ages_are_short():
    assert (age_text(59), age_text(3725), age_text(90000)) == ('0m', '1h 02m', '1d 1h')
