"""A squid's life as one journey, and the two things it must never get wrong:

  * an offline squid's life is complete, and is never pointed online;
  * breeding is rare, kills the parent and cannot be undone, so it is shown
    and warned about and never offered as something to aim for.
"""
import contextlib
import io
import unittest
from types import SimpleNamespace

from src import life_journey as journey
from src.brain_constants import PLANT_SENSOR
from src.lifecycle import DEFAULT_CONFIG
from src.portable_brain import HeadlessBrain, TrainingConfig


def quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


def newborn_facts(**overrides):
    facts = journey.gather_facts(brain=quiet(HeadlessBrain, TrainingConfig(seed=1)))
    facts.update(overrides)
    return facts


GROWN = dict(age_seconds=4000.0, meals=9, learned_about_world=3,
             knows_consequences=2, sees_plants=True,
             learned_actions=['approaching_plant'], hides_when_frightened=True,
             combinations=['anxiety_high_and_sees_plant'])


def reached(facts):
    return {m.key for c in journey.build_journey(facts)
            for m in c.milestones if m.reached}


class ItIsReadFromTheSquid(unittest.TestCase):

    def test_a_newborn_has_only_hatched(self):
        facts = newborn_facts()
        self.assertEqual(reached(facts), {'hatched'})
        self.assertEqual(journey.stage_name(journey.build_journey(facts)), 'Hatchling')
        self.assertFalse(journey.is_mature(facts))

    def test_the_brains_own_state_is_what_is_judged(self):
        b = quiet(HeadlessBrain, TrainingConfig(seed=1))
        b.perceive('plant_in_view', 100.0)
        quiet(b.propagate)
        b.apply_weight_change((PLANT_SENSOR, 'act_shelter'), value=0.9,
                              mechanism='causal_motor_discovery', create=True)
        facts = journey.gather_facts(brain=b)
        self.assertTrue(facts['sees_plants'])
        self.assertEqual(facts['learned_actions'], ['approaching_plant'])
        self.assertTrue(facts['hides_when_frightened'])
        self.assertTrue({'plant_sense', 'learned_action', 'hides'} <= reached(facts))

    def test_an_instinct_is_not_counted_as_something_learned(self):
        facts = newborn_facts()
        self.assertEqual(facts['learned_actions'], [])
        self.assertEqual(facts['learned_about_world'], 0)

    def test_it_reads_a_running_game(self):
        squid = SimpleNamespace(
            health=80.0, is_sick=False, inherited_from=None,
            statistics=SimpleNamespace(get_total_age_seconds=lambda: 120.0,
                                       sushi_consumed=2, cheese_consumed=1,
                                       fights_won=3, fights_lost=1),
            lifecycle=SimpleNamespace(stage='living', reproduction=None, egg=None))
        logic = SimpleNamespace(
            squid=squid,
            plugin_manager=SimpleNamespace(enabled_plugins={'Multiplayer'}),
            brain_window=SimpleNamespace(
                brain_widget=quiet(HeadlessBrain, TrainingConfig(seed=1))))
        facts = journey.gather_facts(logic)
        self.assertEqual(facts['meals'], 3)
        self.assertEqual((facts['fights_won'], facts['fights_lost']), (3, 1))
        self.assertTrue(facts['multiplayer_on'])
        self.assertEqual(facts['age_seconds'], 120.0)

    def test_every_milestone_says_what_it_takes_and_what_it_was_judged_on(self):
        for chapter in journey.build_journey(newborn_facts()):
            self.assertTrue(chapter.about)
            for milestone in chapter.milestones:
                with self.subTest(milestone=milestone.key):
                    self.assertTrue(milestone.how.strip())
                    self.assertTrue(milestone.reached_because.strip())


class GrowingUp(unittest.TestCase):

    def test_age_alone_is_not_maturity_and_neither_is_learning_alone(self):
        self.assertFalse(journey.is_mature(newborn_facts(age_seconds=99999.0)))
        self.assertFalse(journey.is_mature(newborn_facts(
            **dict(GROWN, age_seconds=60.0))))
        self.assertTrue(journey.is_mature(newborn_facts(**GROWN)))

    def test_the_age_it_takes_is_a_setting(self):
        self.assertEqual(DEFAULT_CONFIG['maturity_seconds'],
                         journey.DEFAULT_MATURITY_SECONDS)
        early = newborn_facts(**dict(GROWN, age_seconds=600.0, maturity_seconds=300.0))
        self.assertTrue(journey.is_mature(early))

    def test_a_grown_squid_offline_has_nothing_left_to_do(self):
        """An offline life is a whole life: it is never pointed online."""
        facts = newborn_facts(**GROWN)
        chapters = journey.build_journey(facts)
        self.assertEqual(journey.stage_name(chapters), 'Grown up')
        self.assertIsNone(journey.next_step(chapters))
        self.assertIn('nothing left', journey.describe(facts))
        self.assertTrue(all(c.complete for c in chapters if not c.optional))

    def test_the_squid_itself_answers_whether_it_is_grown(self):
        from src.squid import Squid
        fake = SimpleNamespace(tamagotchi_logic=None, health=100.0, is_sick=False)
        self.assertFalse(Squid.is_mature(fake))


class TheOnlineChapterIsAChoice(unittest.TestCase):

    def test_it_opens_with_what_it_can_cost(self):
        chapters = {c.key: c for c in journey.build_journey(newborn_facts())}
        wider = chapters['wider_water']
        self.assertTrue(wider.optional)
        for phrase in ('for good', 'fight', 'die', 'safe'):
            self.assertIn(phrase, wider.warning)
        self.assertTrue(wider.milestones[0].players_part)
        self.assertIn('Plugin Manager', wider.milestones[0].how)

    def test_fighting_is_what_the_chapter_is_about(self):
        facts = newborn_facts(**dict(GROWN, multiplayer_on=True, hears_aquarium=True,
                                     met_a_squid=True, fights_won=7, fights_lost=4,
                                     aggression_scar=34.0))
        got = reached(facts)
        self.assertTrue({'fought', 'won', 'veteran'} <= got)
        chapters = journey.build_journey(facts)
        self.assertEqual(journey.stage_name(chapters), 'Veteran')
        text = journey.describe(facts)
        self.assertIn('won 7, lost 4', text)
        self.assertIn('rests at 34', text)

    def test_once_online_the_next_step_is_about_meeting_and_fighting(self):
        facts = newborn_facts(**dict(GROWN, multiplayer_on=True))
        step = journey.next_step(journey.build_journey(facts))
        self.assertEqual(step.key, 'hears')


class BreedingIsRareFinalAndNeverAGoal(unittest.TestCase):

    def setUp(self):
        self.facts = newborn_facts(**dict(GROWN, multiplayer_on=True,
                                          hears_aquarium=True, met_a_squid=True,
                                          fights_won=12, fights_lost=3))
        self.chapters = journey.build_journey(self.facts)
        self.heir = {c.key: c for c in self.chapters}['heir']

    def test_it_is_never_what_comes_next(self):
        self.assertIsNone(journey.next_step(self.chapters))
        for milestone in self.heir.milestones:
            self.assertTrue(milestone.by_chance)
        self.assertNotIn('Next:', journey.describe(self.facts))

    def test_it_says_plainly_that_it_is_rare_fatal_and_irreversible(self):
        warning = self.heir.warning
        self.assertIn('1 in 50', warning)
        self.assertIn('STOPS EATING', warning)
        self.assertIn('dies', warning)
        self.assertIn('cannot be undone', warning)
        self.assertIn('cannot be arranged', warning)
        self.assertIn('not a stage to reach', self.heir.about.lower())
        self.assertEqual(self.heir.milestones[0].how,
                         "Nothing you do brings this about.")

    def test_the_odds_shown_are_the_odds_configured(self):
        facts = dict(self.facts, mating_chance=0.1, mating_contact_seconds=5.0)
        heir = {c.key: c for c in journey.build_journey(facts)}['heir']
        self.assertIn('1 in 10', heir.warning)
        self.assertIn('5 seconds', heir.warning)

    def test_going_online_is_not_breeding(self):
        self.assertNotIn('breeds', reached(self.facts))
        self.assertTrue(journey.can_breed(self.facts))      # possible...
        self.assertNotEqual(journey.stage_name(self.chapters), 'Parent')   # ...not so

    def test_only_a_grown_squid_can_breed(self):
        young = dict(self.facts, age_seconds=30.0)
        self.assertFalse(journey.can_breed(young))
        self.assertFalse(journey.can_breed(dict(self.facts, multiplayer_on=False)))
        self.assertFalse(journey.can_breed(dict(self.facts, sick=True)))
        self.assertFalse(journey.can_breed(dict(self.facts, is_parent=True)))

    def test_the_host_does_not_mate_a_squid_that_is_not_grown(self):
        from plugins.multiplayer.host_body import HostBody
        lifecycle = SimpleNamespace(can_reproduce=True)
        grown = SimpleNamespace(lifecycle=lifecycle, is_transitioning=False,
                                can_move=True, is_mature=lambda: True)
        young = SimpleNamespace(lifecycle=lifecycle, is_transitioning=False,
                                can_move=True, is_mature=lambda: False)
        untold = SimpleNamespace(lifecycle=lifecycle, is_transitioning=False,
                                 can_move=True)
        self.assertTrue(HostBody._resident_can_mate(grown))
        self.assertFalse(HostBody._resident_can_mate(young))
        self.assertTrue(HostBody._resident_can_mate(untold))   # older builds, doubles

    def test_a_parent_and_an_heir_are_recognised_when_it_has_happened(self):
        parent = dict(self.facts, is_parent=True, has_egg=True)
        self.assertEqual(journey.stage_name(journey.build_journey(parent)), 'Parent')
        self.assertIn('heir', reached(newborn_facts(is_heir=True)))


class NoticingAMilestone(unittest.TestCase):

    def test_what_was_already_true_at_start_up_is_not_announced(self):
        tracker = journey.JourneyTracker()
        self.assertEqual(tracker.update(newborn_facts(**GROWN)), [])

    def test_a_new_one_is_announced_once(self):
        tracker = journey.JourneyTracker()
        tracker.update(newborn_facts())
        fresh = tracker.update(newborn_facts(meals=1))
        self.assertEqual([m.key for m in fresh], ['first_meal'])
        self.assertEqual(tracker.update(newborn_facts(meals=2)), [])

    def test_the_window_text_is_built_from_the_same_reading(self):
        html = journey.render_html(newborn_facts(**GROWN))
        self.assertIn('Grown up', html)
        self.assertIn('Before you start', html)
        self.assertNotIn('<script', html)


if __name__ == '__main__':
    unittest.main()
