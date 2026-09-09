"""Stage 2A: social consequences, and whether they change anything.

The question this file exists to answer:

    Can what happened with ONE individual change what this squid does the
    next time it meets THAT individual, and only that individual?

Three things have to hold for the answer to be yes, and each is a section
below:

  1. an interaction leaves an objective record, filed against the individual;
  2. that record reaches the brain as ordinary perception on a later meeting;
  3. with a pathway the squid has actually learned, it changes what the squid
     does - while a squid it has never met is unaffected.

The control condition matters as much as the result: with no relevant prior
memory, identical perception must produce identical behaviour. If that fails,
any difference seen elsewhere is noise rather than learning.

Nothing here adds a social behaviour, a social neuron or a rule about what an
encounter means. The only new thing in Stage 2A is that the visiting squid
writes down what happened.
"""

import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _path in (_REPO_ROOT, os.path.join(_REPO_ROOT, "headless")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from PyQt5 import QtWidgets                                # noqa: E402

from src import brain_constants as bc                      # noqa: E402
from src.config_manager import ConfigManager               # noqa: E402
from src.decision_engine import select_action              # noqa: E402

from plugins.multiplayer.identity import SquidIdentity     # noqa: E402
from plugins.multiplayer.peer_ledger import PeerLedger     # noqa: E402
from plugins.multiplayer.encounter import (                # noqa: E402
    EncounterSession, drive_snapshot,
)
from plugins.multiplayer.encounter_sensors import (        # noqa: E402
    ConspecificView, EncounterSensors, SENSOR_SPECS, SENSOR_NAMES,
)
from plugins.multiplayer.remote_protocol import (          # noqa: E402
    Consequence, PerceptionFrame, ProtocolError,
    CONSEQUENCE_ATE, CONSEQUENCE_BLOCKED, CONSEQUENCE_CONTEST,
    PRIVATE_SENSORS, FORBIDDEN_KEYS,
)

from test_remote_mind_stage1 import (                      # noqa: E402
    Encounter, FakeItem, FakeSquid, Clock, quiet_brain,
    HOST_UUID, VISITOR_UUID, OTHER_UUID,
)

_APP = None
_TMPDIR = None
_PREV_CWD = None
_BRAINS = []


def setUpModule():
    global _APP, _TMPDIR, _PREV_CWD
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    _PREV_CWD = os.getcwd()
    _TMPDIR = tempfile.TemporaryDirectory(prefix="dosidicus-stage2a-")
    os.chdir(_TMPDIR.name)
    for name, binary, position, _description in SENSOR_SPECS:
        bc.register_input_sensor(name, binary=binary, position=position,
                                 owner='stage2a-test')


def tearDownModule():
    for brain in _BRAINS:
        try:
            brain._cleanup_render_worker()
        except Exception:
            pass
    _BRAINS.clear()
    os.chdir(_PREV_CWD)
    _TMPDIR.cleanup()
    EncounterSensors.release_classification(bc)


# ===========================================================================
# 1. An interaction leaves an objective record, filed against the individual
# ===========================================================================
class TheVisitorRecordsWhatHappenedTests(unittest.TestCase):
    """Before Stage 2A a visiting squid recorded nothing at all.

    It could read what it remembered about a resident, but never wrote
    anything new - so the loop that is supposed to make a second encounter
    differ from a first was open at exactly the point that matters.
    """

    def setUp(self):
        self.meeting = Encounter(items=[FakeItem(560.0, 400.0)])
        self.meeting.admit(x=500.0, y=400.0)
        self.meeting.host_sends_frame()
        self.meeting.visitor_receives()

    def test_a_visit_opens_an_encounter_against_the_resident(self):
        session = self.meeting.visitor_mind.session
        self.assertIsNotNone(session, "a visit has to be an experience")
        self.assertEqual(session.peer.uuid, HOST_UUID)
        self.assertTrue(session.first_meeting)

    def test_the_session_cannot_open_before_the_resident_is_named(self):
        """An experience has to be filed against somebody."""
        alone = Encounter()
        alone.visitor_mind.begin_visit(None)
        self.assertIsNone(alone.visitor_mind.session)

    def test_winning_a_contest_is_recorded_as_an_object_gained(self):
        self.meeting.set_brain(**quiet_brain(act_play=95.0))
        self.meeting.visitor_decides()
        self.meeting.host_receives()
        self.meeting.host_reports()
        self.meeting.visitor_receives()
        self.assertEqual(self.meeting.visitor_mind.session.items_taken, 1)

    def test_the_visit_becomes_a_memory_of_that_individual(self):
        self.meeting.set_brain(**quiet_brain(act_play=95.0))
        for _ in range(3):
            self.meeting.cycle()
            self.meeting.clock.advance(0.5)
        self.meeting.visitor_mind.end_visit(notify=False)

        memories = (self.meeting.visitor_squid.memory_manager.short_term_memory
                    + self.meeting.visitor_squid.memory_manager.long_term_memory)
        social = [m for m in memories if m.get('category') == 'social']
        self.assertEqual([m['key'] for m in social], [f"peer:{HOST_UUID}"])
        self.assertEqual(social[0]['value']['peer_uuid'], HOST_UUID)

    def test_the_record_says_what_happened_not_what_it_meant(self):
        """Objective facts only: an object moved, food was eaten.

        No verdict about the resident is stored anywhere, because a verdict is
        the squid's own business and would be a conclusion this layer had no
        standing to draw.
        """
        self.meeting.set_brain(**quiet_brain(act_play=95.0))
        for _ in range(3):
            self.meeting.cycle()
            self.meeting.clock.advance(0.5)
        record = self.meeting.visitor_mind.close_session()
        self.assertIsNotNone(record)
        detail = record.to_memory_value()['detail']
        self.assertEqual(detail['items_taken'], 1)
        self.assertIn('drive_deltas', detail)
        for banned in ('trust', 'friend', 'enemy', 'aggressive', 'hostile',
                       'liked', 'verdict', 'opinion'):
            self.assertNotIn(banned, str(record.to_memory_value()).lower())

    def test_a_glimpse_is_not_recorded(self):
        """A visit where nothing happened leaves nothing behind."""
        brief = Encounter()
        brief.admit()
        brief.host_sends_frame()
        brief.visitor_receives()
        brief.clock.advance(0.2)
        self.assertIsNone(brief.visitor_mind.close_session())
        self.assertEqual(brief.visitor_squid.memory_manager.short_term_memory, [])

    def test_ending_the_visit_for_any_reason_still_files_it(self):
        for reason in ('departed', 'ejected', 'link_lost'):
            with self.subTest(reason=reason):
                meeting = Encounter(items=[FakeItem(560.0, 400.0)])
                meeting.admit(x=500.0, y=400.0)
                meeting.host_sends_frame()
                meeting.visitor_receives()
                meeting.set_brain(**quiet_brain(act_play=95.0))
                for _ in range(3):
                    meeting.cycle()
                    meeting.clock.advance(0.5)
                meeting.visitor_mind.end_visit(reason=reason, notify=False)
                self.assertGreater(meeting.visitor_ledger.familiarity(HOST_UUID), 0.0,
                                   "an interrupted visit still happened")


class TheResidentRecordsItFromItsOwnSideTests(unittest.TestCase):
    """Both squid are in the encounter, so both keep their own account."""

    def test_being_robbed_is_recorded_as_a_loss_not_a_gain(self):
        """The bug this covers: one flag meant opposite things.

        note_contest(taken=True) is written by the actuator when THIS squid
        takes an object, and by the host when a VISITOR does. The resident's
        session recorded both as a gain, so a squid that had just been robbed
        filed it as a good day.
        """
        view = ConspecificView(clock=Clock(500.0))
        peer = SquidIdentity(uuid=VISITOR_UUID, name="Traveller")
        view.observe_peer(peer, x=100.0, y=0.0, observer_x=0.0, observer_y=0.0,
                          now=500.0)

        view.note_contest(view.presences[VISITOR_UUID], None, taken=True, by='peer')
        taken_by_peer = view.drain_contests()
        self.assertEqual(taken_by_peer[0]['by'], 'peer')

        view.note_contest(view.presences[VISITOR_UUID], None, taken=True, by='local')
        taken_by_us = view.drain_contests()
        self.assertEqual(taken_by_us[0]['by'], 'local')

    def test_a_loss_makes_the_encounter_negative_for_the_loser(self):
        peer = SquidIdentity(uuid=VISITOR_UUID, name="Traveller")
        robbed = EncounterSession(peer, {'happiness': 50.0}, now=0.0)
        robbed.note_item_lost()
        gained = EncounterSession(peer, {'happiness': 50.0}, now=0.0)
        gained.note_item_taken()

        losing = robbed.close(drives={'happiness': 50.0}, now=5.0)
        winning = gained.close(drives={'happiness': 50.0}, now=5.0)
        self.assertLess(losing.valence, 0.0)
        self.assertGreater(winning.valence, 0.0)
        self.assertEqual(losing.outcome, 'robbed')


# ===========================================================================
# 2. The record reaches the brain as ordinary perception
# ===========================================================================
class MemoryReachesPerceptionTests(unittest.TestCase):

    def _bad_visit(self, meeting):
        """A visit that goes badly for the visitor, recorded properly."""
        meeting.host_sends_frame()
        meeting.visitor_receives()
        meeting.visitor_squid.anxiety = 90.0
        meeting.visitor_squid.happiness = 20.0
        meeting.clock.advance(4.0)
        meeting.visitor_mind.session.observe(
            drives=drive_snapshot(meeting.visitor_squid), action='fleeing',
            now=meeting.clock())
        return meeting.visitor_mind.close_session()

    def test_a_second_meeting_carries_the_first_into_the_sensors(self):
        first = Encounter()
        first.admit()
        record = self._bad_visit(first)
        self.assertIsNotNone(record)
        self.assertLess(record.valence, 0.0)

        again = Encounter(host_squid=first.host_squid,
                          visitor_squid=first.visitor_squid)
        again.visitor_ledger.refresh()
        again.admit()
        again.host_sends_frame()
        again.visitor_receives()

        self.assertGreater(again.visitor_sensors.recalled_bad(), 0.0)
        self.assertGreater(again.visitor_sensors.familiarity(), 0.0)
        self.assertEqual(again.visitor_sensors.recalled_good(), 0.0)

    def test_the_recall_is_available_before_the_squid_acts(self):
        """Order matters: perception, then decision. Not the other way round."""
        first = Encounter()
        first.admit()
        self._bad_visit(first)

        again = Encounter(host_squid=first.host_squid,
                          visitor_squid=first.visitor_squid)
        again.visitor_ledger.refresh()
        again.admit()
        again.host_sends_frame()
        again.visitor_receives()
        self.assertEqual(again.visitor_mind.intents_sent, 0)
        self.assertGreater(again.visitor_sensors.recalled_bad(), 0.0)

    def test_a_good_visit_recalls_as_good(self):
        meeting = Encounter(items=[FakeItem(560.0, 400.0)])
        meeting.admit(x=500.0, y=400.0)
        meeting.host_sends_frame()
        meeting.visitor_receives()
        meeting.visitor_squid.happiness = 85.0
        meeting.visitor_squid.satisfaction = 80.0
        meeting.clock.advance(4.0)
        meeting.visitor_mind.session.observe(
            drives=drive_snapshot(meeting.visitor_squid), action='exploring',
            now=meeting.clock())
        record = meeting.visitor_mind.close_session()

        self.assertGreater(record.valence, 0.0)
        self.assertGreater(meeting.visitor_ledger.recalled_good(HOST_UUID), 0.0)
        self.assertEqual(meeting.visitor_ledger.recalled_bad(HOST_UUID), 0.0)


# ===========================================================================
# Isolation: what happened with B must not colour C
# ===========================================================================
class MemoriesDoNotBleedBetweenIndividualsTests(unittest.TestCase):

    def setUp(self):
        self.visitor = FakeSquid(VISITOR_UUID, "Traveller", 0.0, 0.0)
        self.ledger = PeerLedger(self.visitor.memory_manager)

    def _record(self, peer_uuid, drives):
        session = EncounterSession(SquidIdentity(uuid=peer_uuid, name="Peer"),
                                   {'happiness': 50.0, 'anxiety': 50.0}, now=0.0)
        session.observe(action='exploring', now=3.0)
        self.ledger.record(session.close(drives=drives, now=5.0))

    def test_a_bad_memory_of_one_squid_leaves_another_untouched(self):
        self._record(HOST_UUID, {'happiness': 15.0, 'anxiety': 95.0})
        self.assertGreater(self.ledger.recalled_bad(HOST_UUID), 0.0)
        self.assertEqual(self.ledger.recalled_bad(OTHER_UUID), 0.0)
        self.assertEqual(self.ledger.familiarity(OTHER_UUID), 0.0)

    def test_opposite_histories_are_held_separately(self):
        self._record(HOST_UUID, {'happiness': 15.0, 'anxiety': 95.0})
        self._record(OTHER_UUID, {'happiness': 90.0, 'anxiety': 15.0})

        self.assertGreater(self.ledger.recalled_bad(HOST_UUID), 0.0)
        self.assertEqual(self.ledger.recalled_good(HOST_UUID), 0.0)
        self.assertGreater(self.ledger.recalled_good(OTHER_UUID), 0.0)
        self.assertEqual(self.ledger.recalled_bad(OTHER_UUID), 0.0)

    def test_the_sensors_report_whoever_is_actually_present(self):
        """The same squid, the same tank, a different individual in front of it."""
        self._record(HOST_UUID, {'happiness': 15.0, 'anxiety': 95.0})

        remembered = Encounter(visitor_squid=self.visitor)
        remembered.visitor_ledger.refresh()
        remembered.admit()
        remembered.host_sends_frame()
        remembered.visitor_receives()

        stranger_squid = FakeSquid(OTHER_UUID, "Nobody", 600.0, 400.0)
        stranger = Encounter(host_squid=stranger_squid, visitor_squid=self.visitor)
        stranger.visitor_ledger.refresh()
        stranger.admit()
        stranger.host_sends_frame()
        stranger.visitor_receives()

        self.assertGreater(remembered.visitor_sensors.recalled_bad(), 0.0)
        self.assertEqual(stranger.visitor_sensors.recalled_bad(), 0.0)

    def test_a_hundred_memories_of_others_do_not_make_a_stranger_familiar(self):
        for index in range(20):
            self._record(f"dddddddd-dddd-4ddd-8ddd-{index:012d}",
                         {'happiness': 20.0, 'anxiety': 90.0})
        self.assertEqual(self.ledger.familiarity(OTHER_UUID), 0.0)
        self.assertEqual(self.ledger.recalled_bad(OTHER_UUID), 0.0)


# ===========================================================================
# The control condition
# ===========================================================================
class NoMemoryMeansNoDifferenceTests(unittest.TestCase):
    """If this fails, every result above is noise."""

    def test_two_strangers_produce_identical_perception(self):
        visitor = FakeSquid(VISITOR_UUID, "Traveller", 0.0, 0.0)
        readings = []
        for host_uuid in (HOST_UUID, OTHER_UUID):
            meeting = Encounter(
                host_squid=FakeSquid(host_uuid, "Resident", 600.0, 400.0),
                visitor_squid=visitor)
            meeting.visitor_ledger.refresh()
            meeting.admit(x=300.0, y=400.0)
            meeting.host_sends_frame()
            meeting.visitor_receives()
            readings.append({name: handler() for name, handler
                             in meeting.visitor_sensors.handlers().items()})
        self.assertEqual(readings[0], readings[1])

    def test_two_strangers_produce_an_identical_decision(self):
        visitor = FakeSquid(VISITOR_UUID, "Traveller", 0.0, 0.0)
        actions = []
        for host_uuid in (HOST_UUID, OTHER_UUID):
            meeting = Encounter(
                host_squid=FakeSquid(host_uuid, "Resident", 600.0, 400.0),
                visitor_squid=visitor)
            meeting.visitor_ledger.refresh()
            meeting.admit(x=300.0, y=400.0)
            meeting.host_sends_frame()
            meeting.visitor_receives()
            meeting.set_brain(**quiet_brain(act_flee=90.0))
            actions.append(meeting.visitor_decides().action)
        self.assertEqual(actions[0], actions[1])

    def test_a_squid_with_no_history_reads_zero_on_every_recall_sensor(self):
        meeting = Encounter()
        meeting.admit(x=300.0, y=400.0)
        meeting.host_sends_frame()
        meeting.visitor_receives()
        for name in ('conspecific_familiarity', 'conspecific_recalled_good',
                     'conspecific_recalled_bad'):
            with self.subTest(sensor=name):
                self.assertEqual(
                    meeting.visitor_mind.recalled_sensors()[name], 0.0)


# ===========================================================================
# Interpretation stays local
# ===========================================================================
class InterpretationStaysAtHomeTests(unittest.TestCase):

    def test_the_host_sends_no_recalled_or_familiarity_value(self):
        meeting = Encounter(items=[FakeItem(560.0, 400.0)])
        meeting.admit(x=500.0, y=400.0)
        meeting.set_brain(**quiet_brain(act_play=95.0))
        for _ in range(3):
            meeting.cycle()
            meeting.clock.advance(0.5)

        self.assertTrue(meeting.link.sent_by_host)
        for kind, payload in meeting.link.sent_by_host:
            sensors = payload.get('sensors', {}) if kind == 'perception_frame' else {}
            for name in PRIVATE_SENSORS:
                with self.subTest(message=kind, sensor=name):
                    self.assertNotIn(name, sensors)
            for key in payload:
                self.assertNotIn(str(key).lower(), FORBIDDEN_KEYS)

    def test_a_host_asserting_a_memory_is_rejected(self):
        for name in PRIVATE_SENSORS:
            with self.subTest(sensor=name):
                payload = PerceptionFrame('v1').to_payload()
                payload['sensors'][name] = 100.0
                with self.assertRaises(ProtocolError):
                    PerceptionFrame.from_payload(payload)

    def test_a_consequence_states_a_fact_not_a_conclusion(self):
        """'You did not get it', never 'that squid was hostile'."""
        meeting = Encounter(items=[FakeItem(560.0, 400.0)])
        meeting.admit(x=500.0, y=400.0)
        meeting.set_brain(**quiet_brain(act_play=95.0))
        meeting.cycle()
        for _kind, payload in meeting.link.sent_by_host:
            detail = payload.get('detail', {})
            for value in detail.values():
                self.assertNotIsInstance(value, dict)
            for key in detail:
                self.assertIn(key, ('won', 'ok', 'what', 'reason'))

    def test_the_recall_values_are_computed_from_the_local_ledger(self):
        """Structural: unplug the ledger and the recall goes to zero."""
        meeting = Encounter()
        meeting.admit()
        meeting.host_sends_frame()
        meeting.visitor_receives()
        meeting.visitor_mind.peer_ledger = None
        self.assertEqual(meeting.visitor_mind.recalled_sensors(),
                         {'conspecific_familiarity': 0.0,
                          'conspecific_recalled_good': 0.0,
                          'conspecific_recalled_bad': 0.0})


# ===========================================================================
# 3. THE EXPERIMENT: does a memory of one individual change behaviour?
# ===========================================================================
class IndividualSpecificLearningTests(unittest.TestCase):
    """The whole point of Stage 2A, on a real brain.

    A real BrainWidget, real propagation, real Hebbian learning, the real
    modulation path. Nothing is injected: the pathway that makes the memory
    matter is one the squid learns from co-activation, exactly as it would
    learn anything else.

    The shape of the experiment:

      * repeated encounters with ONE individual are frightening;
      * plasticity finds conspecific_recalled_bad and anxiety co-varying and
        wires them, because that is what Hebbian learning does;
      * afterwards, the SAME current perception produces a different
        physiological response depending only on which individual it is.

    Note what is not claimed: that the squid should be afraid of it, or that
    recalled_bad means danger. The synapse exists because the squid's own life
    put those two things together.
    """

    ALONE = {name: 0.0 for name in SENSOR_NAMES}

    @classmethod
    def setUpClass(cls):
        cls.brain = cls._trained_brain()

    @staticmethod
    def _trained_brain():
        from src.brain_widget import BrainWidget
        brain = BrainWidget(config=ConfigManager())
        _BRAINS.append(brain)
        brain.config.neurogenesis['enabled'] = False
        for name, _binary, position, _description in SENSOR_SPECS:
            brain.neuron_positions[name] = position
            brain.state[name] = 0.0

        candidates = list(brain.neuron_positions)

        def live(sensors, drives):
            brain.state.update({**IndividualSpecificLearningTests.ALONE,
                                **sensors, **drives})
            brain.propagate_activations(smoothing=0.5)
            brain.plasticity.observe(brain.state, candidates)

        # A life in which meeting THIS individual goes badly, alternating with
        # ordinary time alone. The alternation is the point: the learning rule
        # converges on the CORRELATION between two neurons, so two signals
        # held constant teach nothing at all.
        for _cycle in range(30):
            for _ in range(12):
                live({'conspecific_visible': 100.0, 'conspecific_proximity': 85.0,
                      'conspecific_recalled_bad': 90.0}, {'anxiety': 85.0})
            for _ in range(12):
                live({}, {'anxiety': 30.0})
            brain.perform_hebbian_learning()
        return brain

    def _modulation(self, recalled_bad):
        """The squid's physiological response to what is in front of it."""
        self.brain.state.update({**self.ALONE,
                                 'conspecific_visible': 100.0,
                                 'conspecific_proximity': 85.0,
                                 'conspecific_recalled_bad': recalled_bad,
                                 'conspecific_recalled_good': 0.0,
                                 'anxiety': 50.0})
        return self.brain.compute_neural_modulation()

    def test_experience_wires_the_recall_sensor_to_something(self):
        """The squid learned it. Nothing put this synapse there."""
        weight = self.brain.weights.get(('conspecific_recalled_bad', 'anxiety'))
        self.assertIsNotNone(weight,
                             "repeated bad encounters must leave a pathway")
        self.assertGreater(weight, 0.2)

    def test_the_synapse_is_the_squids_own_and_carries_its_provenance(self):
        explanation = self.brain.explain_weight(
            ('conspecific_recalled_bad', 'anxiety'))
        self.assertTrue(explanation,
                        "a learned synapse has to be able to say where it came from")

    def test_identical_perception_but_a_remembered_individual_differs(self):
        """THE result.

        The current sensory situation is byte-identical in the two cases. The
        only difference is what this squid remembers about the individual in
        front of it - and its physiology responds differently because of it.
        """
        remembered = self._modulation(90.0).get('anxiety', 0.0)
        stranger = self._modulation(0.0).get('anxiety', 0.0)
        self.assertGreater(remembered, stranger)

    def test_a_stranger_still_gets_the_generic_response(self):
        """The individual-specific part is a difference, not the whole thing.

        Seeing any squid at all became mildly stressful too, because
        conspecific_visible was co-active with anxiety in the same life. That
        general lesson is not the finding; the gap between the two is.
        """
        stranger = self._modulation(0.0).get('anxiety', 0.0)
        self.assertGreater(stranger, 0.0)
        remembered = self._modulation(90.0).get('anxiety', 0.0)
        self.assertGreater(remembered - stranger, 0.05,
                           "an individual has to be worth more than a category")

    def test_the_difference_disappears_if_the_memory_does(self):
        """A causal check: remove the recall and the two become identical."""
        with_memory = self._modulation(90.0).get('anxiety', 0.0)
        without = self._modulation(0.0).get('anxiety', 0.0)
        self.assertNotAlmostEqual(with_memory, without, places=3)

        saved = self.brain.weights.pop(('conspecific_recalled_bad', 'anxiety'))
        try:
            self.assertAlmostEqual(self._modulation(90.0).get('anxiety', 0.0),
                                   self._modulation(0.0).get('anxiety', 0.0),
                                   places=6)
        finally:
            self.brain.weights[('conspecific_recalled_bad', 'anxiety')] = saved

    def test_a_good_history_does_not_borrow_the_bad_pathway(self):
        """recalled_good is a different sensor and this life never used it."""
        self.brain.state.update({**self.ALONE,
                                 'conspecific_visible': 100.0,
                                 'conspecific_proximity': 85.0,
                                 'conspecific_recalled_good': 90.0,
                                 'anxiety': 50.0})
        good = self.brain.compute_neural_modulation().get('anxiety', 0.0)
        bad = self._modulation(90.0).get('anxiety', 0.0)
        self.assertLess(good, bad)

    def test_no_module_maps_a_remembered_peer_to_a_behaviour(self):
        """Nothing decided that a remembered-bad squid should do anything.

        Perception and memory must not name an action at all - if either did,
        the pathway found above would be a rule someone wrote rather than
        something this squid learned.
        """
        import inspect
        from plugins.multiplayer import encounter_sensors, peer_ledger
        for module in (encounter_sensors, peer_ledger):
            source = inspect.getsource(module)
            with self.subTest(module=module.__name__):
                for action in bc.ACTION_NEURONS:
                    self.assertNotIn(action, source)

    def test_a_consequence_is_applied_from_what_happened_not_from_who_it_was(self):
        """The drive change is keyed on the EVENT, never on the individual.

        on_consequence is where an outcome reaches the squid's physiology. If
        it consulted the ledger, the squid's response would be coloured by its
        opinion before its network ever got a say - which is the shape of
        thing this whole design exists to avoid.
        """
        import inspect
        from plugins.multiplayer.visitor_mind import VisitorMind
        source = inspect.getsource(VisitorMind.on_consequence)
        for forbidden in ('peer_ledger', 'recalled', 'familiarity',
                          'personality', 'resident_uuid'):
            with self.subTest(term=forbidden):
                self.assertNotIn(forbidden, source)

    def test_the_same_consequence_lands_the_same_way_whoever_sent_it(self):
        """Two residents, one identical outcome, one identical drive change."""
        deltas = []
        for host_uuid in (HOST_UUID, OTHER_UUID):
            meeting = Encounter(
                host_squid=FakeSquid(host_uuid, "Resident", 600.0, 400.0))
            meeting.admit()
            meeting.host_sends_frame()
            meeting.visitor_receives()
            before = meeting.visitor_squid.anxiety
            meeting.visitor_mind.on_consequence(
                Consequence(meeting.visitor_mind.visit_id, CONSEQUENCE_CONTEST,
                            detail={'won': False}).to_payload())
            deltas.append(meeting.visitor_squid.anxiety - before)
        self.assertEqual(deltas[0], deltas[1])
        self.assertGreater(deltas[0], 0.0)


if __name__ == "__main__":
    unittest.main()
