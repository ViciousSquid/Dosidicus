"""New Game and hatching, against the real main window.

An egg hatching IS a new game - the same sequence as starting with no save -
so the two are tested together, through MainWindow itself:

  * the starter egg still hatches the way it always has;
  * New Game deletes BOTH of the squid's save files, clears the squid's own
    memory folder (and nothing outside the game), takes the plugins down so no
    network session is left pointing at the old squid, and gives the new squid
    a newborn brain rather than the old one's learned network;
  * a parent's egg hatches through that same path, once, with no way to
    cancel it, into a squid with a new identity, a newborn brain and no
    memories - and with its own two messages.

The game runs from a temporary working directory (images and plugins linked
in), so no test touches a real squid's saves or memories.
"""

import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from PyQt5 import QtWidgets                                    # noqa: E402

APP = None
WINDOW = None
MAIN = None
_TMPDIR = None
_PREV_CWD = None

VISITOR_UUID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


class YesBox:
    """TimedMessageBox, answered Yes."""

    def __init__(self, *args, **kwargs):
        pass

    def exec_(self):
        return 0

    def get_result(self):
        return QtWidgets.QMessageBox.Yes


def setUpModule():
    global APP, WINDOW, MAIN, _TMPDIR, _PREV_CWD
    _PREV_CWD = os.getcwd()
    _TMPDIR = tempfile.TemporaryDirectory(prefix="dosidicus-newgame-")
    for name in ("images", "plugins"):
        os.symlink(os.path.join(_REPO_ROOT, name), os.path.join(_TMPDIR.name, name))
    os.chdir(_TMPDIR.name)

    APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    for name in ("question", "information", "critical", "warning"):
        setattr(QtWidgets.QMessageBox, name, staticmethod(lambda *a, **k: 0))
    QtWidgets.QDialog.exec_ = lambda self: 0

    import main as main_module
    MAIN = main_module
    main_module.TimedMessageBox = YesBox
    WINDOW = main_module.MainWindow(specified_personality=None, debug_mode=False)
    if hasattr(WINDOW.brain_window, "hebbian_timer"):
        WINDOW.brain_window.hebbian_timer.stop()


def tearDownModule():
    brain = getattr(getattr(WINDOW, 'brain_window', None), 'brain_widget', None)
    try:
        if WINDOW is not None and WINDOW.tamagotchi_logic is not None:
            WINDOW.tamagotchi_logic.stop()
        if brain is not None:
            brain.stop_worker()
            brain._cleanup_render_worker()
    except Exception:
        pass
    for timer_name in ('neurogenesis_timer', 'animation_timer', '_render_timer',
                       '_brain_export_timer', '_link_fade_timer'):
        timer = getattr(brain, timer_name, None) if brain is not None else None
        if timer is not None:
            try:
                timer.stop()
            except Exception:
                pass
    os.chdir(_PREV_CWD)
    _TMPDIR.cleanup()


# ---------------------------------------------------------------------------
def save_files_for(squid_uuid):
    """Where the live SaveManager keeps this squid's manual save and autosave.

    Asked of the manager rather than assumed: another test module may have
    pointed SaveManager somewhere else for the whole run.
    """
    manager = WINDOW.tamagotchi_logic.save_manager
    return [manager._get_save_path_for_uuid(str(squid_uuid), is_autosave=False),
            manager._get_save_path_for_uuid(str(squid_uuid), is_autosave=True)]


def give_the_squid_a_past():
    """A squid that has lived: saved twice, remembered things, learned and grown."""
    logic = WINDOW.tamagotchi_logic
    squid = WINDOW.squid
    brain = WINDOW.brain_window.brain_widget
    squid.memory_manager.add_short_term_memory('food', 'parent_meal', 'Ate well')
    innate_pair = next(iter(brain.weights))
    innate_value = brain.weights[innate_pair]
    brain.weights[innate_pair] = 0.987 if innate_value != 0.987 else 0.5
    brain.neuron_positions['parent_grown_neuron'] = (900, 900)
    brain.state['parent_grown_neuron'] = 42.0
    brain.weights[('hunger', 'parent_grown_neuron')] = 0.6
    logic.save_game()
    logic.save_game(is_autosave=True)
    for path in save_files_for(squid.uuid):
        assert os.path.exists(path), path
    return innate_pair, innate_value


class Recorder:
    def __init__(self):
        self.messages = []

    def __call__(self, message):
        self.messages.append(message)


def assert_newborn(test, parent_uuid, innate_pair, innate_value):
    squid = WINDOW.squid
    brain = WINDOW.brain_window.brain_widget
    test.assertIs(WINDOW.tamagotchi_logic.squid, squid)
    test.assertNotEqual(str(squid.uuid), str(parent_uuid))
    test.assertEqual(squid.lifecycle.stage, 'living')
    test.assertIsNone(squid.lifecycle.egg)
    # A newborn brain: the innate value back, the grown neuron and its learned
    # synapse gone - nothing of the previous squid's network.
    test.assertEqual(brain.weights[innate_pair], innate_value)
    test.assertNotIn('parent_grown_neuron', brain.neuron_positions)
    test.assertNotIn('parent_grown_neuron', brain.state)
    test.assertNotIn(('hunger', 'parent_grown_neuron'), brain.weights)
    test.assertFalse(any('parent_grown_neuron' in key for key in brain.weights))
    # No memories carried over, in the squid or on disk.
    test.assertEqual(squid.memory_manager.short_term_memory, [])
    test.assertEqual(squid.memory_manager.long_term_memory, [])
    for path in save_files_for(parent_uuid):
        test.assertFalse(os.path.exists(path), path)


# ===========================================================================
class StarterEggTests(unittest.TestCase):
    """Runs first: the window was booted with no save."""

    def test_1_the_starter_egg_hatches_as_it_always_has(self):
        self.assertIsNotNone(WINDOW.squid)
        self.assertEqual(WINDOW.squid.lifecycle.stage, 'living')
        recorder = Recorder()
        with mock.patch.object(WINDOW.user_interface, 'show_message', recorder):
            WINDOW.splash.second_frame.emit()
        self.assertEqual(recorder.messages, ["Squid is hatching!"])


class NewGameTests(unittest.TestCase):

    def test_2_new_game_starts_a_newborn_and_leaves_nothing_behind(self):
        parent_uuid = WINDOW.squid.uuid
        innate_pair, innate_value = give_the_squid_a_past()

        class FakeNetworkPlugin:
            shut_down = 0

            def shutdown(self):
                FakeNetworkPlugin.shut_down += 1

        WINDOW.plugin_manager.plugins['fakenet'] = {'instance': FakeNetworkPlugin()}
        removed = []
        real_rmtree = shutil.rmtree

        def recording_rmtree(path, *args, **kwargs):
            removed.append(os.path.abspath(path))
            return real_rmtree(path, *args, **kwargs)

        recorder = Recorder()
        with mock.patch.object(shutil, 'rmtree', recording_rmtree):
            WINDOW.start_new_game()
        with mock.patch.object(WINDOW.user_interface, 'show_message', recorder):
            WINDOW.splash.second_frame.emit()

        assert_newborn(self, parent_uuid, innate_pair, innate_value)
        # The plugins came down - for multiplayer, that is the network reset.
        self.assertEqual(FakeNetworkPlugin.shut_down, 1)
        self.assertNotIn('fakenet', WINDOW.plugin_manager.plugins)
        # Only the game's own memory folder was cleared - never the folder
        # above the game, which is where the old path pointed.
        self.assertEqual(removed, [os.path.abspath('_memory')])
        above_the_game = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(MAIN.__file__))), '_memory')
        self.assertNotIn(os.path.abspath(above_the_game), removed)
        # A starter egg, so its own message.
        self.assertEqual(recorder.messages, ["Squid is hatching!"])


class HatchTests(unittest.TestCase):

    def test_3_a_parents_egg_hatches_once_into_a_new_squid(self):
        logic = WINDOW.tamagotchi_logic
        parent = WINDOW.squid
        parent_uuid = parent.uuid
        innate_pair, innate_value = give_the_squid_a_past()

        self.assertTrue(logic.record_reproduction("visit1-mate", VISITOR_UUID, "Mate"))
        eggs = [i for i in WINDOW.user_interface.scene.items()
                if getattr(i, 'category', '') == 'egg']
        self.assertEqual(len(eggs), 1)

        # Starvation's last tick: the parent dies through the ordinary update.
        parent.is_sleeping = False
        parent.hunger, parent.health = 100.0, 0.05
        logic.update_statistics()
        self.assertTrue(parent.lifecycle.is_dead)

        recorder = Recorder()
        with mock.patch.object(WINDOW.user_interface, 'show_message', recorder):
            # What the death's timer calls. No dialog can intervene: the
            # TimedMessageBox is never constructed on this path.
            with mock.patch.object(MAIN, 'TimedMessageBox',
                                   side_effect=AssertionError("no dialogs")):
                self.assertTrue(logic.begin_egg_hatching())
            WINDOW.splash.second_frame.emit()
            WINDOW.splash.finished.emit()

        self.assertIsNot(WINDOW.squid, parent)
        assert_newborn(self, parent_uuid, innate_pair, innate_value)
        self.assertIn("An egg is hatching!", recorder.messages)
        self.assertIn("A squid has hatched and you must look after him.",
                      recorder.messages)
        self.assertNotIn("Squid is hatching!", recorder.messages)
        # The egg completed: gone from the tank, and the hatchling - not the
        # parent - is what is saved now.
        self.assertEqual([i for i in WINDOW.user_interface.scene.items()
                          if getattr(i, 'category', '') == 'egg'], [])
        self.assertTrue(os.path.exists(save_files_for(WINDOW.squid.uuid)[0]))

        # It cannot hatch again: not from the old logic's timer, not by id.
        hatchling = WINDOW.squid
        self.assertFalse(logic.begin_egg_hatching())
        self.assertFalse(WINDOW.hatch_egg("visit1-mate"))
        self.assertIs(WINDOW.squid, hatchling)

        # And a restart loads the hatchling, with no egg anywhere.
        latest = WINDOW.save_manager.get_latest_save()
        self.assertIn(str(hatchling.uuid).replace('-', '_'), latest)
        loaded = WINDOW.save_manager.load_game()
        self.assertEqual(loaded['game_state']['lifecycle']['stage'], 'living')
        self.assertIsNone(loaded['game_state']['lifecycle']['egg'])


if __name__ == '__main__':
    unittest.main()
