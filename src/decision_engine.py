# DECISION ENGINE - https://github.com/ViciousSquid/Dosidicus
# exploration of emergent behavioural complexity via dynamic, biologically-inspired neural architecture rather than a static state machine.
# Version 5.0 — Behaviour read from the network | 2026

import random
import time

from .brain_constants import (
    ACTION_NEURONS, ACTION_BEHAVIOURS, LEARNED_ACTIONS, INNATE_ACTION_WIRING,
    ACTION_THRESHOLDS, REFLEX_ACTIONS, FALLBACK_ACTION,
)


class DecisionEngine:
    """Reads the squid's behaviour off its own network.

    WHAT THIS NO LONGER DOES
    ------------------------
    Earlier versions computed behaviour from hand-written formulas:

        weights["eating"] = hunger * (3.0 if can_see_food > 80 else 0.3) \
                            * 1.6 ** (hunger / 25)
        weights["approaching_plant"] = (anxiety / 40) * (3.0 if near_plant else 0.5) \
                                       * (4.0 if personality is TIMID else 1.8)

    ...and a dozen more like them, followed by a memory-influence table and a
    per-personality multiplier table. Those numbers were the squid's real
    behaviour policy. The network could rewire itself completely - grow
    neurons, invert synapses, consolidate a lifetime of experience - and the
    squid would still do exactly what that arithmetic said, because nothing
    the squid learned was ever consulted when it chose what to do.

    WHAT IT DOES INSTEAD
    --------------------
    The network has action neurons (brain_constants.ACTION_NEURONS), one per
    thing the squid can do. Forward propagation drives them like any other
    network-driven neuron. This engine reads their activations and reports the
    strongest as the squid's choice. That is the whole policy - so every number
    behind a behaviour is now a synapse, and every synapse is something
    Hebbian learning, STDP, sleep consolidation or neurogenesis can move.

    The squid is born able to MOVE, EAT and FLEE (with a chance of inking when
    startled), because a newborn that does nothing never generates the
    experience it would need in order to learn. Playing, sheltering by a plant
    and choosing to rest have no innate wiring at all: those action neurons sit
    at zero until something the squid experiences builds a path to them.

    Two things here are still unconditional, and both are physiology rather
    than choice: a squid that is asleep is asleep, and a squid at the top of
    the sleepiness scale collapses. Learning to rest BEFORE collapsing is one
    of the things a squid can acquire - that is what act_rest is for.
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

        # --- Physiology. Not decisions: a squid does not choose to be asleep,
        #     and past a certain exhaustion it does not choose to stay awake. ---
        if self.squid.is_sleeping:
            return self._record(decision_data, "sleeping peacefully", 1.0)

        if self._activation(brain_state, 'sleepiness') >= 95:
            self.squid.go_to_sleep()
            return self._record(decision_data, "exhausted", 1.0)

        # --- The decision itself: whatever the network wants most. ---
        weights = self._action_weights(brain_state)
        decision_data['base_weights'] = dict(weights)
        # Which innate reflex is contributing what, per behaviour. Reported
        # under its own key: 'memory_influences' is consumed by the Decisions
        # tab as a flat {action: multiplier} and there are no such multipliers
        # any more - a synapse is not a multiplier applied after the fact.
        decision_data['innate_drivers'] = self._innate_drivers(brain_state)

        # A small amount of noise, so a squid whose two strongest urges are
        # neck and neck does not lock onto one of them forever. This is the
        # only number in this file that is not a synapse.
        jittered = {k: v * random.uniform(0.94, 1.06) for k, v in weights.items()}
        decision_data['adjusted_weights'] = jittered

        # Rank each urge by how far past its OWN threshold it is, as a fraction
        # of the room it had left. Comparing raw activations would be unfair
        # between actions whose thresholds differ - a 50 is a strong wish to
        # flee and a weak wish to eat.
        #
        # Two kinds of action sit out the contest. FALLBACK_ACTION (swimming) is
        # what the squid does when nothing else is worth doing, so it is the
        # fallback below rather than a competitor a mild but genuine urge would
        # have to outrank. REFLEX_ACTIONS (inking) are never chosen at all -
        # they fire through their own binding while the squid gets on with
        # whatever it decided, which for a frightened squid is escaping.
        urgency = {}
        skip = set(REFLEX_ACTIONS) | {FALLBACK_ACTION}
        for name in ACTION_NEURONS:
            if name in skip:
                continue
            behaviour = ACTION_BEHAVIOURS[name]
            value = jittered[behaviour]
            if not self._wants(name, value):
                continue
            threshold = ACTION_THRESHOLDS.get(name, 50.0)
            headroom = max(1.0, 100.0 - threshold)
            urgency[behaviour] = (value - threshold) / headroom

        if not urgency:
            # Nothing in the network is driving any action hard enough to act
            # on. The squid swims - which is the floor act_move rests at, and
            # is how it goes on meeting things it can learn from.
            return self._record(decision_data, self._drift(), 0.0)

        winner = max(urgency, key=urgency.get)
        ordered = sorted(urgency.values(), reverse=True)
        confidence = 1.0 if len(ordered) < 2 else (ordered[0] - ordered[1]) / ordered[0]
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

        return self._drift()

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
