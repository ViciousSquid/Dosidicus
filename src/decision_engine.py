# DECISION ENGINE - https://github.com/ViciousSquid/Dosidicus
# exploration of emergent behavioural complexity via dynamic, biologically-inspired neural architecture rather than a static state machine.
# Version 5.0 — Behaviour read from the network | 2026

import random
import time

from .brain_constants import (
    ACTION_NEURONS, ACTION_BEHAVIOURS, LEARNED_ACTIONS, INNATE_ACTION_WIRING,
    ACTION_THRESHOLDS, REFLEX_ACTIONS, FALLBACK_ACTION,
)


def action_activations(brain_state):
    """The squid's behaviour, as the network currently computes it."""
    return {
        ACTION_BEHAVIOURS[name]: max(0.0, _activation_of(brain_state, name))
        for name in ACTION_NEURONS
    }


def _activation_of(brain_state, name):
    raw = brain_state.get(name, 0.0)
    if isinstance(raw, bool):
        return 100.0 if raw else 0.0
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def wants(name, activation):
    """Is this urge strong enough to act on?

    The threshold is the one the action's own output binding fires at
    (ACTION_THRESHOLDS), not a number invented here, so an urge can never be
    "chosen" at a level too weak to reach the body.
    """
    return activation >= ACTION_THRESHOLDS.get(name, 50.0)


def rank_actions(activations):
    """How far past its OWN threshold each urge is, as a fraction of the room
    it had left.

    Comparing raw activations would be unfair between actions whose thresholds
    differ - a 50 is a strong wish to flee and a weak wish to eat.

    Two kinds of action sit out the contest. FALLBACK_ACTION (swimming) is what
    the squid does when nothing else is worth doing, so it is a fallback rather
    than a competitor a mild but genuine urge would have to outrank.
    REFLEX_ACTIONS (inking) are never chosen at all - they fire through their
    own binding while the squid gets on with whatever it decided.
    """
    urgency = {}
    skip = set(REFLEX_ACTIONS) | {FALLBACK_ACTION}
    for name in ACTION_NEURONS:
        if name in skip:
            continue
        behaviour = ACTION_BEHAVIOURS[name]
        value = activations.get(behaviour, 0.0)
        if not wants(name, value):
            continue
        threshold = ACTION_THRESHOLDS.get(name, 50.0)
        headroom = max(1.0, 100.0 - threshold)
        urgency[behaviour] = (value - threshold) / headroom
    return urgency


def select_action(brain_state, jitter=True):
    """Which behaviour this brain state wants, and how sure it is.

    THE one definition of the rule. It is a module-level function rather than
    a method because a squid VISITING ANOTHER TANK has to be able to use it:
    its body is on the host machine but its brain is still here, and the whole
    point of the remote-mind round trip is that the visiting squid's action is
    chosen by exactly the arithmetic that would have chosen it at home. A
    second copy of this rule living in the multiplayer plugin would be a
    second squid, and the two would drift.

    Returns (behaviour, confidence, urgency). `behaviour` is None when nothing
    clears its own threshold, which is the caller's cue to fall back to
    locomotion - or, for a sleeping squid whose act_move is held down by the
    sleep gating, to nothing at all.
    """
    activations = action_activations(brain_state)
    if jitter:
        # A small amount of noise, so a squid whose two strongest urges are
        # neck and neck does not lock onto one of them forever. This is the
        # only number in this file that is not a synapse.
        activations = {k: v * random.uniform(0.94, 1.06)
                       for k, v in activations.items()}
    urgency = rank_actions(activations)
    if not urgency:
        return None, 0.0, activations
    winner = max(urgency, key=urgency.get)
    ordered = sorted(urgency.values(), reverse=True)
    confidence = 1.0 if len(ordered) < 2 else (ordered[0] - ordered[1]) / ordered[0]
    return winner, confidence, urgency


class DecisionEngine:
    """Reads the squid's behaviour off its own network.

    WHAT IT DOES
    --------------------
    The network has action neurons (brain_constants.ACTION_NEURONS), one per
    thing the squid can do. Forward propagation drives them like any other
    network-driven neuron, and THEY INHIBIT ONE ANOTHER - a strongly driven
    action suppresses its rivals, so the winner is whatever survives that
    competition rather than the result of a comparison made out here. This
    engine reads the outcome and carries it out. Every number behind a
    behaviour is a synapse, and every synapse is something Hebbian learning,
    STDP, sleep consolidation or neurogenesis can move.

    What the squid is born with is not a rule anywhere; it is structure
    (brain_constants.INNATE_ACTION_WIRING), of four kinds:

      sensorimotor priors  seeing food drives the neuron that swims to food
      reflex pathways      startle drives flight, and in parallel the ink
                           reflex, which fires with a probability rather than
                           a certainty
      homeostatic drives   hunger sharpens the food prior; sleepiness past
                           the top of its range drives an involuntary collapse
      tonic bias           locomotion idles above zero, so a squid that wants
                           nothing still swims and goes on meeting things

    All of it is ordinary synapses written through the recorded path, so an
    instinct is a starting point rather than a law: experience can strengthen,
    weaken or invert any of it.

    Playing, sheltering by a plant, and choosing to rest before exhaustion
    have no innate wiring at all. Those neurons sit at zero until something the
    squid experiences builds a path to them.

    There is no "if asleep" branch here and no "if exhausted" branch. Being
    asleep inhibits the voluntary action neurons (sleep gating), and an
    imminent collapse silences them, so in both cases the network itself
    produces nothing to do.
    """

    def __init__(self, squid):
        self.squid = squid
        self.last_decision_data = {}

    def get_decision_data(self):
        """Return last decision trace for visualization in Brain Tool → Decisions tab"""
        return self.last_decision_data.copy()

    # ------------------------------------------------------------------
    # Reading the network
    # ------------------------------------------------------------------
    @staticmethod
    def _activation(brain_state, name):
        raw = brain_state.get(name, 0.0)
        if isinstance(raw, bool):
            return 100.0 if raw else 0.0
        try:
            return float(raw)
        except (TypeError, ValueError):
            return 0.0

    def _action_weights(self, brain_state):
        """The squid's behaviour, as the network currently computes it."""
        return {
            ACTION_BEHAVIOURS[name]: max(0.0, self._activation(brain_state, name))
            for name in ACTION_NEURONS
        }

    @staticmethod
    def _wants(name, activation):
        """Is this urge strong enough to act on?

        The threshold is the one the action's own output binding fires at
        (ACTION_THRESHOLDS), not a number invented here, so an urge can never
        be "chosen" at a level too weak to reach the body. Without it the
        argmax would pick whatever was fractionally above zero - a squid with
        an ink neuron at 1.7 out of 100, and nothing else happening, would ink.
        """
        return activation >= ACTION_THRESHOLDS.get(name, 50.0)

    def _innate_drivers(self, brain_state):
        """Which innate reflex is contributing what, for the Decisions tab.

        This is a read-only explanation of the network's own arithmetic, not
        an input to the decision - the decision has already been made by
        propagation before this engine is called.
        """
        drivers = {}
        widget = self._brain_widget()
        weights = getattr(widget, 'weights', {}) if widget is not None else {}
        for source, target, _innate in INNATE_ACTION_WIRING:
            weight = float(weights.get((source, target), 0.0))
            contribution = self._activation(brain_state, source) * weight / 100.0
            if abs(contribution) < 0.01:
                continue
            drivers.setdefault(ACTION_BEHAVIOURS[target], {})[source] = round(contribution, 3)
        return drivers

    def _brain_widget(self):
        logic = getattr(self.squid, 'tamagotchi_logic', None)
        window = getattr(logic, 'brain_window', None)
        return getattr(window, 'brain_widget', None)

    # ------------------------------------------------------------------
    # Deciding
    # ------------------------------------------------------------------
    def make_decision(self):
        logic = self.squid.tamagotchi_logic

        decision_data = {
            'inputs': {},
            'brain_state': {},
            'base_weights': {},
            'memory_influences': {},
            'urgency_multipliers': {},
            'personality_modifiers': {},
            'adjusted_weights': {},
            'final_decision': '',
            'confidence': 0.0,
            'personality': getattr(self.squid.personality, 'value',
                                   str(self.squid.personality)),
            'timestamp': time.time(),
        }

        # --- Perception. Every input reaches the brain through the hooks;
        #     there is no manual scanning of the scene here. ---
        perceptual_inputs = {}
        if hasattr(logic, 'brain_hooks'):
            try:
                perceptual_inputs = logic.brain_hooks.get_input_neuron_values()
                logic.brain_hooks.update_decay()  # Critical: decay temporal sensors
            except Exception as e:
                print(f"[DecisionEngine] Hook error: {e}")
                perceptual_inputs = {}
        decision_data['inputs'] = perceptual_inputs

        widget = self._brain_widget()
        brain_state = dict(getattr(widget, 'state', {}) or {})
        brain_state.update(perceptual_inputs)
        decision_data['brain_state'] = brain_state

        # There is no "if asleep" branch and no "if exhausted" branch here.
        # Both used to be written as stimulus-to-action rules - `if
        # sleepiness >= 95: go_to_sleep()` - and both are pathways in the
        # network now: sleepiness drives act_collapse (a homeostatic drive),
        # and is_sleeping inhibits every voluntary action neuron (sleep
        # gating). A sleeping squid's actions sit below their thresholds
        # because something in its brain is holding them there, which is what
        # being asleep is.

        # --- The decision itself: whatever the network wants most. ---
        weights = self._action_weights(brain_state)
        decision_data['base_weights'] = dict(weights)
        # Which innate reflex is contributing what, per behaviour. Reported
        # under its own key: 'memory_influences' is consumed by the Decisions
        # tab as a flat {action: multiplier} and there are no such multipliers
        # any more - a synapse is not a multiplier applied after the fact.
        decision_data['innate_drivers'] = self._innate_drivers(brain_state)

        # The rule itself lives at module level (select_action), because a
        # squid visiting another tank chooses its action with the same
        # arithmetic while its body is on someone else's machine.
        winner, confidence, urgency = select_action(brain_state)
        decision_data['adjusted_weights'] = action_activations(brain_state)

        if winner is None:
            # Nothing is driving any action hard enough to act on. Locomotion
            # is the fallback, but it has to clear its own threshold like
            # anything else - which is how a sleeping squid, whose act_move is
            # held down by the sleep gating, ends up doing nothing at all
            # rather than drifting around the tank in its sleep.
            locomotion = self._activation(brain_state, FALLBACK_ACTION)
            if wants(FALLBACK_ACTION, locomotion):
                return self._record(decision_data, self._drift(), 0.0)
            return self._record(decision_data, self._resting_status(), 0.0)

        decision_data['confidence'] = confidence
        decision_data['urgency_multipliers'] = {k: round(v, 3) for k, v in urgency.items()}

        result = self._execute(winner, brain_state)
        return self._record(decision_data, result, confidence)

    def _record(self, decision_data, result, confidence):
        decision_data['final_decision'] = result
        decision_data['confidence'] = confidence
        self.last_decision_data = decision_data
        return result

    # ------------------------------------------------------------------
    # Carrying it out
    # ------------------------------------------------------------------
    def _execute(self, decision, brain_state):
        """Turn the winning action into a drive.

        Movement is always expressed as a DRIVE_DECISION drive rather than by
        writing squid_direction: move_squid() is the only thing that moves the
        squid, so routing through the drive keeps one movement channel and lets
        an output binding's urge outrank a decision.

        Note what is NOT here: no thresholds on sensors deciding whether the
        action is allowed, no personality flavour table, no fallbacks that
        substitute a different behaviour. If the network chose it, the squid
        does it; if it cannot be done right now (nothing to eat, no rock in
        reach) the squid drifts, and the disappointment is itself experience.
        """
        s = self.squid

        if decision == "eating":
            target = self._nearest_food()
            if target is not None:
                s.set_neural_drive('seek_food', duration=4.0, target=target,
                                   priority=s.DRIVE_DECISION)
                dist = s.distance_to(*target)
                if dist < 60:
                    return "eating"
                return "approaching food" if dist < 120 else "eyeing food"
            return self._drift()

        if decision == "fleeing":
            s.flee_from_center()
            return "fleeing!"

        if decision == "inking":
            logic = getattr(s, 'tamagotchi_logic', None)
            if logic is not None and hasattr(logic, 'create_ink_cloud'):
                logic.create_ink_cloud()
                return "inking!"
            return self._drift()

        if decision == "approaching_plant":
            plant = self._nearest_of('plant')
            if plant is not None:
                s.set_neural_drive('seek_plant', duration=5.0, target=plant,
                                   priority=s.DRIVE_DECISION)
                return "seeking comfort in plant"
            return self._drift()

        if decision == "playing":
            if s.carrying_rock:
                if s.throw_rock(random.choice(["left", "right"])):
                    return "playfully tossing rock"
            elif s.carrying_poop:
                if s.throw_poop(random.choice(["left", "right"])):
                    return "flinging poop playfully"
            toy = self._nearest_of('rock', 'poop')
            if toy is not None:
                s.set_neural_drive('approach_rock', duration=6.0, target=toy,
                                   priority=s.DRIVE_DECISION)
                return "seeking toy"
            return self._drift()

        if decision == "sleeping":
            s.go_to_sleep()
            return "settling down to sleep"

        if decision == "exhausted":
            s.go_to_sleep()
            return "exhausted"

        return self._drift()

    def _resting_status(self):
        """Nothing in the network wants anything. Usually: it is asleep."""
        return ("sleeping peacefully" if getattr(self.squid, 'is_sleeping', False)
                else "resting")

    def _drift(self):
        """Move, without having chosen anywhere in particular to go."""
        s = self.squid
        s.current_speed = s.base_speed
        s.set_neural_drive('wander', duration=3.0, priority=s.DRIVE_DECISION)
        return "exploring"

    # ------------------------------------------------------------------
    # Finding things in the world
    # ------------------------------------------------------------------
    def _nearest_food(self):
        s = self.squid
        food = getattr(getattr(s, 'tamagotchi_logic', None), 'food_items', None)
        if not food:
            return None
        closest = min(food, key=lambda f: s.distance_to(f.pos().x(), f.pos().y()))
        return (closest.pos().x(), closest.pos().y())

    def _nearest_of(self, *categories):
        s = self.squid
        logic = getattr(s, 'tamagotchi_logic', None)
        ui = getattr(logic, 'user_interface', None)
        scene = getattr(ui, 'scene', None)
        if scene is None:
            return None
        items = [i for i in scene.items()
                 if getattr(i, 'category', '') in categories]
        if not items:
            return None
        return min(items, key=lambda i: s.distance_to(
            i.sceneBoundingRect().center().x(),
            i.sceneBoundingRect().center().y()))

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def unlearned_actions(self):
        """Actions the squid still has no path to - what it cannot do yet."""
        widget = self._brain_widget()
        weights = getattr(widget, 'weights', {}) if widget is not None else {}
        unlearned = []
        for name in LEARNED_ACTIONS:
            drivers = [k for k in weights if k[1] == name and abs(weights[k]) > 0.05]
            if not drivers:
                unlearned.append(ACTION_BEHAVIOURS[name])
        return unlearned
