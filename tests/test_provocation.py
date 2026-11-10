"""What another squid does to this one is felt, remembered, and - if a fight
follows - named as what set it off. Nothing here tells either squid what to
do about it.
"""
import unittest
from types import SimpleNamespace

from src import fighting
from src.social_knowledge import fight_thoughts
from src.tamagotchi_logic import HEAL_BELOW_HUNGER, HEAL_PER_TICK, heal_in_sleep

import test_remote_mind_stage1 as mp


def meeting_over_food(hunger):
    food = mp.FakeItem(310.0, 400.0, category='food')
    meeting = mp.Encounter(food=[food])
    meeting.host_squid.hunger = hunger
    meeting.host_squid.anxiety = 30.0
    meeting.host_squid.happiness = 60.0
    meeting.admit(x=300.0, y=400.0)
    return meeting


def visitor_eats(meeting):
    intent = SimpleNamespace(target_id=None)
    meeting.host_body._do_eat(meeting.actor, intent)


class AVisitorEatingTheResidentsFood(unittest.TestCase):

    def test_it_is_felt_and_more_the_hungrier_the_resident_is(self):
        fed, starving = meeting_over_food(10.0), meeting_over_food(95.0)
        visitor_eats(fed)
        visitor_eats(starving)
        self.assertGreater(fed.host_squid.anxiety, 30.0)
        self.assertGreater(starving.host_squid.anxiety, fed.host_squid.anxiety + 8.0)
        self.assertLess(starving.host_squid.happiness, fed.host_squid.happiness)

    def test_it_is_remembered_against_the_squid_that_did_it(self):
        meeting = meeting_over_food(90.0)
        visitor_eats(meeting)
        memories = [m for m in meeting.host_squid.memory_manager.short_term_memory
                    if str(m.get('key', '')).startswith('theft:')]
        self.assertEqual(len(memories), 1)
        value = memories[0]['value']
        self.assertEqual(value['summary'], "Traveller ate food in my tank while I was starving.")
        self.assertEqual(value['opponent_uuid'], mp.VISITOR_UUID)
        self.assertEqual(value['outcome'], 'robbed')
        self.assertLess(value['valence'], -5.0)

    def test_the_host_does_not_decide_what_the_resident_does_about_it(self):
        """It is a confrontation, recorded with what was taken - and that is
        all. Whether a fight follows is the two squids' own aggression."""
        meeting = meeting_over_food(90.0)
        contests = []
        meeting.host_view.on_contest = contests.append
        visitor_eats(meeting)
        self.assertEqual(contests, [mp.VISITOR_UUID])
        taken = meeting.host_view.provocation(mp.VISITOR_UUID, now=meeting.clock())
        self.assertEqual(taken['what'], 'food')
        self.assertIsNone(meeting.host_view.provocation(
            mp.VISITOR_UUID, now=meeting.clock() + 31.0))
        self.assertFalse(hasattr(meeting.host_squid, 'fights_started'))

    def test_nothing_is_felt_by_a_resident_that_is_away(self):
        meeting = meeting_over_food(90.0)
        meeting.host_squid.is_transitioning = True
        visitor_eats(meeting)
        self.assertEqual(meeting.host_squid.anxiety, 30.0)


class AFightSaysWhatSetItOff(unittest.TestCase):

    def _record(self, provoked_by=None):
        mine = {'role': 'attacker', 'ability': 80.0, 'commitment': 62.0,
                'committed_by': 'aggression'}
        theirs = {'role': 'defender', 'ability': 60.0}
        record = fighting.resolve_fight(mine, theirs, rng=lambda: 0.0)
        why = {'aggression': 62.0}
        if provoked_by:
            why['provoked_by'] = provoked_by
        record.update(opponent='Guest', why=why)
        return record

    def test_in_the_one_line_account(self):
        said = fighting.describe(self._record('food'))
        self.assertIn('a fight it started after its food was eaten', said)
        self.assertIn('aggression 62', said)
        self.assertNotIn('after', fighting.describe(self._record()))

    def test_in_the_squids_own_thoughts(self):
        thoughts = fight_thoughts(self._record('food'))
        self.assertTrue(thoughts[0].startswith('It had just eaten my food. I went for Guest'))
        self.assertTrue(fight_thoughts(self._record())[0].startswith('I went for Guest'))

    def test_the_provocation_is_not_what_decides_the_fight(self):
        """Its own aggression is. A placid squid that is robbed does not fight."""
        self.assertLess(fighting.fight_predisposition({'anxiety': 95.0})[0],
                        fighting.AGGRESSION_THRESHOLD)


class WoundsHealInSleep(unittest.TestCase):

    def squid(self, **over):
        values = dict(is_sleeping=True, is_sick=False, hunger=30.0, health=60.0,
                      lifecycle=SimpleNamespace(can_eat=True))
        values.update(over)
        return SimpleNamespace(**values)

    def test_a_fed_well_sleeping_squid_mends(self):
        squid = self.squid()
        self.assertAlmostEqual(heal_in_sleep(squid), HEAL_PER_TICK)
        self.assertAlmostEqual(squid.health, 60.0 + HEAL_PER_TICK)

    def test_awake_hungry_or_ill_it_does_not(self):
        for change in (dict(is_sleeping=False), dict(is_sick=True),
                       dict(hunger=HEAL_BELOW_HUNGER), dict(health=100.0)):
            with self.subTest(**change):
                self.assertEqual(heal_in_sleep(self.squid(**change)), 0.0)

    def test_a_parent_which_no_longer_eats_does_not_mend(self):
        parent = self.squid(lifecycle=SimpleNamespace(can_eat=False))
        self.assertEqual(heal_in_sleep(parent), 0.0)

    def test_a_lost_fight_is_a_few_minutes_sleep_not_a_step_towards_death(self):
        lost = -fighting.CONSEQUENCES[False]['health']
        self.assertLess(lost / HEAL_PER_TICK, 300)


class AggressionIsAStatisticOnceItExists(unittest.TestCase):
    """Not something a squid is born with: the box appears when the neuron does."""

    @classmethod
    def setUpClass(cls):
        from PyQt5 import QtWidgets
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def _window(self, positions, state):
        from src.statistics_window import StatisticsWindow
        brain = SimpleNamespace(neuron_positions=positions, state=state)
        logic = SimpleNamespace(brain_window=SimpleNamespace(brain_widget=brain))
        squid = SimpleNamespace(tamagotchi_logic=logic, status='roaming',
                                hunger=10, happiness=50, cleanliness=50,
                                sleepiness=10, health=100, satisfaction=50,
                                curiosity=50, anxiety=20, is_sleeping=False)
        window = StatisticsWindow(squid)
        self.addCleanup(window.deleteLater)
        window.roll_timer.stop()
        return window, brain

    def test_a_squid_with_no_aggression_neuron_has_no_such_statistic(self):
        window, _brain = self._window({'hunger': (0, 0)}, {'hunger': 10})
        window._update_aggression()
        self.assertTrue(window.aggression_box.isHidden())
        self.assertNotIn('aggression', window.stat_boxes)

    def test_it_appears_when_the_neuron_is_grown_and_shows_its_activation(self):
        window, brain = self._window({'hunger': (0, 0)}, {'hunger': 10})
        window._update_aggression()
        self.assertTrue(window.aggression_box.isHidden())
        brain.neuron_positions['aggression'] = (5, 5)
        brain.state['aggression'] = 63.4
        window._update_aggression()
        self.assertFalse(window.aggression_box.isHidden())
        self.assertEqual(window.aggression_box.value_label.text(), '63')
        self.assertEqual(window.aggression_box.name_label.text(), 'Aggression')

    def test_it_is_read_from_the_brain_and_cannot_be_typed_into(self):
        window, brain = self._window({'aggression': (5, 5)}, {'aggression': 40.0})
        window.update_statistics()
        window.set_debug_mode(True)
        self.assertTrue(window.aggression_box.value_edit.isHidden())
        window.apply_changes()
        self.assertFalse(hasattr(window.squid, 'aggression'))


if __name__ == '__main__':
    unittest.main()
