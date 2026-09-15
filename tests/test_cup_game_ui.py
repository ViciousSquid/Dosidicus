"""
The cup game as the player meets it: cups in the real tank, the real squid.

`test_cup_experiment.py` covers the science on the headless instrument. This
file covers the claims that are only true if the GAME path is wired correctly,
and that a headless runner cannot check:

  * a cup and the experimenter's ghost marker are scenery, not objects - the
    vision worker is never given them, so the squid cannot see either;
  * hiding the food really removes it from the world the squid perceives AND
    from the list the decision engine homes in on;
  * revealing it feeds the squid through `Squid.eat`, the same call a hand-fed
    squid gets, with no separate reward anywhere;
  * the controller never writes into brain state;
  * choosing the evaluation block really freezes plasticity in the live brain.
"""

import os
import sys
import tempfile
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5 import QtWidgets  # noqa: E402

_TMPDIR = tempfile.TemporaryDirectory(prefix="dosidicus-cup-ui-")
from src import save_manager  # noqa: E402
_orig_save_init = save_manager.SaveManager.__init__


def _tmp_save_init(self, save_directory="saves"):
    _orig_save_init(self, os.path.join(_TMPDIR.name, "saves"))


save_manager.SaveManager.__init__ = _tmp_save_init

APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
for _name in ("question", "information", "critical", "warning"):
    setattr(QtWidgets.QMessageBox, _name, staticmethod(lambda *a, **k: 0))
QtWidgets.QDialog.exec_ = lambda self: 0

import main as main_module  # noqa: E402
from src.cup_experiment import Phase  # noqa: E402
from src.cup_game_ui import CupGameController, GhostItem  # noqa: E402
from src.vision_worker import extract_scene_objects  # noqa: E402


#: Module-level so tearDownModule can reach them. A MainWindow owns background
#: threads, and Qt aborts the process when a running QThread is collected -
#: which happens after unittest has already printed OK, so a green run still
#: exits 134 and any CI watching the exit code calls it a failure. Same reason
#: and same remedy as tearDownModule in test_neural_pipeline.py.
WINDOW = None
LOGIC = None
BRAIN = None


def tearDownModule():
    for stop in (lambda: BRAIN.stop_worker(),
                 lambda: BRAIN._cleanup_render_worker()):
        try:
            if BRAIN is not None:
                stop()
        except Exception:
            pass
    try:
        worker = getattr(LOGIC, 'vision_worker', None)
        if worker is not None:
            worker.stop()
            worker.wait(2000)
    except Exception:
        pass
    for owner, names in ((BRAIN, ('neurogenesis_timer', 'animation_timer',
                                  '_render_timer', '_brain_export_timer',
                                  '_link_fade_timer')),
                         (LOGIC, ('simulation_timer', 'hebbian_timer',
                                  'autosave_timer'))):
        for name in names:
            timer = getattr(owner, name, None) if owner is not None else None
            try:
                if timer is not None:
                    timer.stop()
            except Exception:
                pass
    _TMPDIR.cleanup()


class CupGameUITests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        global WINDOW, LOGIC, BRAIN
        cls.window = WINDOW = main_module.MainWindow(specified_personality=None,
                                                     debug_mode=False)
        cls.logic = LOGIC = cls.window.tamagotchi_logic
        cls.brain = BRAIN = cls.window.brain_window.brain_widget
        cls.squid = cls.logic.squid
        # The game's own timers would step the simulation underneath the
        # assertions; this file drives everything explicitly.
        for attribute in ('simulation_timer', 'hebbian_timer', 'autosave_timer'):
            timer = getattr(cls.logic, attribute, None)
            if timer is not None and hasattr(timer, 'stop'):
                timer.stop()

    def setUp(self):
        self.controller = CupGameController(self.logic)
        self.controller.timer.stop()      # tick by hand

    def tearDown(self):
        self.controller.shutdown()
        self.brain.learning_frozen = False

    # -- scenery is not perception ---------------------------------------
    def test_cups_and_the_ghost_are_invisible_to_the_vision_worker(self):
        for item in list(self.controller.cups.values()) + [self.controller.ghost]:
            self.assertFalse(hasattr(item, 'category'),
                             f"{type(item).__name__} has a category, so "
                             "extract_scene_objects would hand it to the squid")

        objects = extract_scene_objects(self.logic.user_interface.scene,
                                        self.logic.food_items)
        categories = {obj.category for obj in objects}
        self.assertNotIn('unknown', categories)
        self.assertLessEqual(categories, {'food', 'plant', 'rock', 'poop'})

    def test_the_ghost_marker_is_drawn_for_the_player_only(self):
        ghost = self.controller.ghost
        self.assertTrue(isinstance(ghost, GhostItem))
        self.controller.set_ghost_visible(False)
        self.assertFalse(ghost.visible_to_player)
        self.controller.set_ghost_visible(True)
        self.assertTrue(ghost.visible_to_player)

    # -- hiding really hides ---------------------------------------------
    def test_hiding_removes_the_food_from_everything_the_squid_can_reach(self):
        self.controller.start_trial("train")
        self.assertIn(self.controller.food_item, self.logic.food_items)

        self.controller.shuffle()
        self.controller._hide()
        self.assertIs(self.controller.experiment.phase, Phase.HIDDEN)

        # Not among the objects the vision worker is given...
        self.assertNotIn(self.controller.food_item, self.logic.food_items)
        objects = extract_scene_objects(self.logic.user_interface.scene,
                                        self.logic.food_items)
        self.assertEqual([o for o in objects if o.category == 'food'], [])

        # ...so the sensor reads nothing, by the ordinary path.
        self.assertEqual(self.squid.get_visible_food(), [])
        self.assertEqual(self.logic.brain_hooks.calculate_can_see_food(), 0.0)

        # ...and the decision engine has nothing to steer towards either.
        self.assertEqual(self.logic.food_items, [])

    def test_the_same_food_item_comes_back_at_the_reveal(self):
        self.controller.start_trial("train")
        food = self.controller.food_item
        self.controller.shuffle()
        self.controller._hide()
        record = self.controller.experiment.current
        self.controller.experiment.open_choice()
        self.controller.experiment.force_choice(record.truth_baited_slot)
        self.controller._reveal()
        self.assertIs(self.controller.food_item, food)
        self.assertIn(food, self.logic.food_items)

    def test_a_wrong_choice_reveals_nothing(self):
        self.controller.start_trial("train")
        self.controller.shuffle()
        self.controller._hide()
        record = self.controller.experiment.current
        wrong = next(s for s in range(3) if s != record.truth_baited_slot)
        self.controller.experiment.open_choice()
        self.controller.experiment.force_choice(wrong)
        self.controller._reveal()
        self.assertFalse(record.correct)
        self.assertEqual(self.logic.food_items, [])

    # -- the reward is the ordinary one ----------------------------------
    def test_the_squid_eats_through_its_own_eat_method(self):
        """No reward path of the experiment's own: the revealed food is an
        ordinary food item and `Squid.eat` does the rest."""
        self.controller.start_trial("train")
        self.controller.shuffle()
        self.controller._hide()
        record = self.controller.experiment.current
        self.controller.experiment.open_choice()
        self.controller.experiment.force_choice(record.truth_baited_slot)
        self.controller._reveal()

        self.squid.hunger = 80.0
        before = self.squid.hunger
        self.squid.eat(self.controller.food_item)
        self.assertLess(self.squid.hunger, before,
                        "eating the revealed food did not feed the squid")
        self.assertTrue(self.squid.is_eating)

    # -- no leakage ------------------------------------------------------
    def test_the_controller_never_writes_into_brain_state(self):
        class Recording(dict):
            def __init__(self, *a, **kw):
                super().__init__(*a, **kw)
                self.writes = []

            def __setitem__(self, key, value):
                self.writes.append(key)
                super().__setitem__(key, value)

            def update(self, *a, **kw):
                self.writes.extend(dict(*a, **kw))
                super().update(*a, **kw)

        original = self.brain.state
        self.brain.state = Recording(original)
        try:
            self.controller.start_trial("train")
            self.controller.shuffle()
            self.controller._hide()
            record = self.controller.experiment.current
            self.controller.experiment.open_choice()
            self.controller.experiment.force_choice(record.truth_baited_slot)
            self.controller._reveal()
            self.controller._settle()
            self.assertEqual(self.brain.state.writes, [],
                             f"the cup game wrote into brain state: "
                             f"{self.brain.state.writes}")
        finally:
            self.brain.state = original

    def test_the_trial_record_keeps_the_answer_out_of_what_was_perceived(self):
        self.controller.start_trial("train")
        self.controller.shuffle()
        self.controller._hide()
        record = self.controller.experiment.current
        self.controller.experiment.observe(
            self.controller._squid_centre(), self.squid.status,
            dict(self.brain.state))
        sample = record.perceived(Phase.HIDDEN)
        self.assertIsNotNone(sample)
        self.assertEqual(sample.can_see_food, 0.0)
        self.assertNotIn(str(record.truth_baited_slot),
                         [sample.status])

    # -- the evaluation block really freezes ------------------------------
    def test_choosing_the_evaluation_block_freezes_the_live_brain(self):
        edge = ('can_see_food', 'act_eat')
        self.controller.set_frozen(True)
        self.assertTrue(self.brain.learning_frozen)
        before = dict(self.brain.weights)
        self.assertFalse(self.brain.apply_weight_change(edge, delta=0.2))
        self.assertEqual(dict(self.brain.weights), before)
        self.assertFalse(self.brain.state['neurogenesis_active'])

        self.controller.set_frozen(False)
        self.assertTrue(self.brain.apply_weight_change(edge, delta=0.01))
        self.assertTrue(self.brain.state['neurogenesis_active'])

    # -- reachable from the menu ------------------------------------------
    def test_the_game_is_on_the_actions_menu(self):
        """It is a thing you DO with the squid, so it sits with Feed and Clean
        rather than off in Debug."""
        ui = self.logic.user_interface
        actions = [menu for menu in ui.menu_bar.findChildren(QtWidgets.QMenu)
                   if any(a is ui.cup_game_action for a in menu.actions())]
        self.assertEqual(len(actions), 1,
                         "the cup game is not on exactly one menu")
        titles = [a.text() for a in actions[0].actions() if a.text()]
        self.assertIn(ui.feed_action.text(), titles,
                      "the cup game is not on the menu Feed is on")

    def test_triggering_the_menu_action_opens_the_game(self):
        ui = self.logic.user_interface
        existing = getattr(ui, 'cup_game_window', None)
        if existing is not None:
            existing.close()
            ui.cup_game_window = None
        try:
            ui.cup_game_action.trigger()
            window = ui.cup_game_window
            self.assertIsNotNone(window)
            self.assertEqual(sorted(c.identity for c in
                                    window.controller.cups.values()),
                             ["A", "B", "C"])
        finally:
            if getattr(ui, 'cup_game_window', None) is not None:
                ui.cup_game_window.close()
                ui.cup_game_window = None

    def test_shutdown_leaves_the_tank_as_it_found_it(self):
        scene = self.logic.user_interface.scene
        self.controller.start_trial("train")
        self.controller.shutdown()
        for item in list(self.controller.cups.values()) + [self.controller.ghost]:
            self.assertIsNot(item.scene(), scene)
        self.assertEqual(
            [f for f in self.logic.food_items
             if f is self.controller.food_item], [])
        self.assertFalse(self.brain.learning_frozen)


if __name__ == '__main__':
    unittest.main()
