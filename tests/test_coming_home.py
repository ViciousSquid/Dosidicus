"""A visiting squid comes home by its own network's choice: fear or tiredness.

  * flight winning its action competition sends it home ("I was frightened");
  * rest (or collapse) winning sends it home to sleep;
  * a squid away from home ALWAYS comes home to sleep: one that is asleep
    while visiting, however it fell asleep, is home on the next tick;
  * a stubborn squid can hold off sleep while another need is stronger -
    "Was tired but resisted sleep due to stubbornness" - but not indefinitely:
    never past personality.STUBBORN_SLEEP_LIMIT, never when exhausted;
  * while its network keeps it engaged - playing, exploring - it stays.
Going home is its decision: the visit ends 'departed', the encounter is filed.
"""
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_remote_mind_stage1 import Encounter, quiet_brain          # noqa: E402
from plugins.multiplayer.remote_protocol import END_DEPARTED, VisitEnd  # noqa: E402
from plugins.multiplayer.visitor_mind import HOMEWARD               # noqa: E402
from src.personality import (RESISTED_SLEEP, STUBBORN_SLEEP_LIMIT,  # noqa: E402
                             resists_sleep)


class ComingHome(unittest.TestCase):

    def visiting(self, **brain):
        meeting = Encounter()
        meeting.admit()
        meeting.host_sends_frame()
        meeting.visitor_receives()
        meeting.set_brain(**quiet_brain(**brain))
        return meeting

    def assert_home(self, meeting, thought):
        mind = meeting.visitor_mind
        self.assertFalse(mind.perception.away)
        self.assertFalse(meeting.visitor_squid.is_transitioning)
        ends = [VisitEnd.from_payload(p) for kind, p in meeting.link.sent_by_visitor
                if kind == 'visit_end']
        self.assertEqual([e.reason for e in ends], [END_DEPARTED])
        thoughts = [text for _, text in
                    getattr(meeting.visitor_tank.brain_window.brain_widget,
                            'social_thoughts', [])]
        self.assertIn(thought, thoughts)

    def test_a_frightened_visitor_swims_home(self):
        meeting = self.visiting(act_flee=95.)
        self.assertIsNone(meeting.visitor_decides())
        self.assert_home(meeting, HOMEWARD['act_flee'])

    def test_a_tired_visitor_goes_home_to_sleep(self):
        meeting = self.visiting(act_rest=95.)
        self.assertIsNone(meeting.visitor_decides())
        self.assert_home(meeting, HOMEWARD['act_rest'])

    def test_a_visitor_that_has_fallen_asleep_is_always_brought_home(self):
        meeting = self.visiting()                        # nothing even winning
        meeting.visitor_squid.is_sleeping = True
        self.assertIsNone(meeting.visitor_mind.tick())
        self.assert_home(meeting, HOMEWARD['act_rest'])

    def test_an_engaged_visitor_stays(self):
        meeting = self.visiting(act_play=95.)
        intent = meeting.cycle()
        self.assertEqual(intent.action, 'act_play')
        self.assertTrue(meeting.visitor_mind.perception.away)
        self.assertFalse([kind for kind, _ in meeting.link.sent_by_visitor
                          if kind == 'visit_end'])


class StubbornAboutSleep(unittest.TestCase):

    def stubborn_visitor(self, **squid):
        meeting = Encounter()
        meeting.visitor_squid.personality = type("P", (), {"value": "stubborn"})()
        for name, value in squid.items():
            setattr(meeting.visitor_squid, name, value)
        thoughts = []
        meeting.visitor_tank.brain_window.add_thought = thoughts.append
        meeting.admit()
        meeting.host_sends_frame()
        meeting.visitor_receives()
        return meeting, thoughts

    def test_tired_but_curious_it_resists_and_stays(self):
        meeting, thoughts = self.stubborn_visitor(curiosity=90., sleepiness=70.)
        meeting.set_brain(**quiet_brain(act_rest=95., act_play=70.))
        intent = meeting.visitor_decides()
        self.assertEqual(intent.action, 'act_play')        # the next thing it wants
        self.assertTrue(meeting.visitor_mind.perception.away)
        self.assertEqual(thoughts, [RESISTED_SLEEP])
        meeting.visitor_decides()
        self.assertEqual(thoughts, [RESISTED_SLEEP])        # once, not every tick

    def test_but_not_indefinitely(self):
        meeting, thoughts = self.stubborn_visitor(curiosity=90.,
                                                  sleepiness=STUBBORN_SLEEP_LIMIT)
        meeting.set_brain(**quiet_brain(act_rest=95., act_play=70.))
        self.assertIsNone(meeting.visitor_decides())
        self.assertFalse(meeting.visitor_mind.perception.away)

    def test_exhaustion_cannot_be_resisted(self):
        meeting, _ = self.stubborn_visitor(curiosity=90., sleepiness=70.)
        meeting.set_brain(**quiet_brain(act_collapse=95.))
        self.assertIsNone(meeting.visitor_decides())
        self.assertFalse(meeting.visitor_mind.perception.away)

    def test_with_nothing_stronger_it_goes_home_to_sleep(self):
        meeting, thoughts = self.stubborn_visitor(curiosity=30., hunger=20., anxiety=10.,
                                                  sleepiness=70.)
        meeting.set_brain(**quiet_brain(act_rest=95.))
        self.assertIsNone(meeting.visitor_decides())
        self.assertFalse(meeting.visitor_mind.perception.away)
        self.assertNotIn(RESISTED_SLEEP, thoughts)
        self.assertIn(HOMEWARD['act_rest'], thoughts)

    def test_the_rule(self):
        self.assertTrue(resists_sleep('stubborn', 60., 0., 0., 70.))
        self.assertTrue(resists_sleep('stubborn', 0., 70., 0., 70.))     # 70 x 0.8 = 56
        self.assertFalse(resists_sleep('stubborn', 0., 68., 0., 70.))    # 54.4
        self.assertFalse(resists_sleep('stubborn', 60., 0., 0., STUBBORN_SLEEP_LIMIT))
        self.assertFalse(resists_sleep('adventurous', 99., 99., 99., 70.))

    def test_at_home_too_the_resistance_is_real(self):
        from types import SimpleNamespace
        from src.decision_engine import DecisionEngine
        slept, shown, thought = [], [], []
        squid = SimpleNamespace(
            personality=type("P", (), {"value": "stubborn"})(), hunger=80., curiosity=0.,
            anxiety=0., sleepiness=70., base_speed=1, current_speed=1, DRIVE_DECISION='decision',
            set_neural_drive=lambda *a, **k: None, go_to_sleep=lambda: slept.append(True),
            tamagotchi_logic=SimpleNamespace(
                show_message=shown.append,
                brain_window=SimpleNamespace(add_thought=thought.append)))
        engine = DecisionEngine.__new__(DecisionEngine)
        engine.squid = squid
        self.assertEqual(engine._execute('sleeping', {}), 'resisting sleep')
        self.assertEqual((slept, thought), ([], [RESISTED_SLEEP]))
        squid.sleepiness = STUBBORN_SLEEP_LIMIT
        self.assertEqual(engine._execute('sleeping', {}), 'settling down to sleep')
        self.assertEqual(slept, [True])


if __name__ == '__main__':
    unittest.main()
