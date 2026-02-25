# DECISION ENGINE
# exploration of emergent behavioral complexity via dynamic, biologically-inspired neural architecture rather than a static state machine. 
# Version 4.0 — Fully Neural-Driven Decision Making | December 2025

import random
import math
from .personality import Personality


class DecisionEngine:
    """
    Neural-first decision engine.
    All perception flows through BrainNeuronHooks → no manual vision checks.
    Behavior emerges purely from the current brain state + memory + personality.
    """

    def __init__(self, squid):
        self.squid = squid
        self.last_decision_data = {}

    def get_decision_data(self):
        """Return last decision trace for visualization in Brain Tool → Decisions tab"""
        return self.last_decision_data.copy()

    def make_decision(self):
        logic = self.squid.tamagotchi_logic

        # =================================================================
        # 1. BUILD FULL BRAIN STATE FROM HOOKS
        # =================================================================
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
            'personality': self.squid.personality.value if isinstance(self.squid.personality, Personality) else str(self.squid.personality),
            'timestamp': time.time()
        }

        # --- Get dynamic perceptual inputs via hooks ---
        if not hasattr(logic, 'brain_hooks'):
            perceptual_inputs = {}
        else:
            try:
                perceptual_inputs = logic.brain_hooks.get_input_neuron_values()
                logic.brain_hooks.update_decay()  # Critical: decay temporal sensors
            except Exception as e:
                print(f"[DecisionEngine] Hook error: {e}")
                perceptual_inputs = {}

        decision_data['inputs'] = perceptual_inputs

        # --- Get full current brain state (core + learned + input neurons) ---
        try:
            brain_state = logic.brain_window.brain_widget.state.copy()
        except:
            brain_state = {}

        # Ensure perceptual inputs are present even if brain_widget hasn't updated yet
        brain_state.update(perceptual_inputs)
        decision_data['brain_state'] = brain_state

        # =================================================================
        # 2. MEMORY INFLUENCE
        # =================================================================
        active_memories = self.squid.memory_manager.get_active_memories_data(6)
        memory_mod = {
            "eating": 1.0,
            "playing": 1.0,
            "exploring": 1.0,
            "approaching_plant": 1.0,
            "throwing": 1.0,
        }

        for mem in active_memories:
            effect = sum(v for v in mem.get('raw_value', {}).values() if isinstance(v, (int, float))) if isinstance(mem.get('raw_value'), dict) else 0

            if mem['category'] == 'food' and effect > 0:
                memory_mod['eating'] *= 1.25
            if 'rock' in mem['key'] and effect > 0:
                memory_mod['playing'] *= 1.2
                memory_mod['throwing'] *= 1.15
            if 'poop' in mem['key'] and effect > 0:
                memory_mod['playing'] *= 1.1
            if 'plant' in mem['key'] and effect > 0:
                memory_mod['approaching_plant'] *= 1.3
            if 'startled' in mem['key']:
                memory_mod['exploring'] *= 0.7
                memory_mod['approaching_plant'] *= 1.4

        decision_data['memory_influences'] = memory_mod

        # =================================================================
        # 3. URGENCY (NON-LINEAR PHYSIOLOGICAL DRIVE)
        # =================================================================
        hunger_level = brain_state.get('hunger', 50)
        sleepiness = brain_state.get('sleepiness', 50)

        urgency = {
            "eating": math.pow(1.6, hunger_level / 25),
            "sleeping": math.pow(1.7, sleepiness / 25),
        }
        decision_data['urgency_multipliers'] = urgency

        # Immediate overrides
        if sleepiness >= 95:
            self.squid.go_to_sleep()
            decision_data['final_decision'] = "exhausted"
            decision_data['confidence'] = 1.0
            self.last_decision_data = decision_data
            return "exhausted"

        if self.squid.is_sleeping:
            decision_data['final_decision'] = "sleeping peacefully"
            decision_data['confidence'] = 1.0
            self.last_decision_data = decision_data
            return "sleeping peacefully"

        if brain_state.get('external_stimulus', 0) > 90:
            decision_data['final_decision'] = "startled!"
            decision_data['confidence'] = 1.0
            self.last_decision_data = decision_data
            return "startled!"

        # =================================================================
        # 4. BUILD DECISION WEIGHTS FROM BRAIN STATE
        # =================================================================
        weights = {}

        # Exploration
        threat = brain_state.get('threat_level', brain_state.get('anxiety', 50))
        external = brain_state.get('external_stimulus', 0)
        weights["exploring"] = (
            brain_state.get("curiosity", 50) *
            max(0.1, 1.0 - threat / 140) *
            (0.2 if external > 80 else 1.0)
        )

        # Eating
        can_see_food = brain_state.get('can_see_food', 0)
        weights["eating"] = (
            hunger_level *
            (3.0 if can_see_food > 80 else 0.3) *
            urgency["eating"]
        )

        # Plant seeking (comfort)
        near_plant = brain_state.get('plant_proximity', 0) > 40
        weights["approaching_plant"] = (
            (brain_state.get("anxiety", 50) / 40) *
            (3.0 if near_plant else 0.5) *
            (4.0 if self.squid.personality == Personality.TIMID else 1.8)
        )

        # Play / Object interaction
        carrying = self.squid.carrying_rock or self.squid.carrying_poop
        weights["playing"] = (
            brain_state.get("satisfaction", 50) *
            brain_state.get("curiosity", 50) / 50 *
            (2.2 if carrying else 1.0) *
            (0.4 if brain_state.get('is_sick', 0) > 50 else 1.0)
        )

        # Throwing (only if carrying)
        weights["throwing"] = (
            brain_state.get("satisfaction", 50) * 1.3
            if carrying else 0
        )

        # Sleeping (non-exhausted)
        weights["sleeping"] = sleepiness * urgency["sleeping"] * 0.6

        # Fleeing from threat
        if threat > 75 or external > 85:
            weights["fleeing"] = threat * 1.8

        decision_data['base_weights'] = weights.copy()

        # =================================================================
        # 5. APPLY MEMORY + PERSONALITY MODIFIERS
        # =================================================================
        for action, mod in memory_mod.items():
            if action in weights:
                weights[action] *= mod

        # Apply personality
        if self.squid.personality == Personality.ADVENTUROUS:
            weights["exploring"] *= 1.4
            weights["playing"] *= 1.3
        elif self.squid.personality == Personality.TIMID:
            weights["exploring"] *= 0.6
            weights["approaching_plant"] *= 1.5
        elif self.squid.personality == Personality.GREEDY:
            weights["eating"] *= 1.6
        elif self.squid.personality == Personality.LAZY:
            weights["playing"] *= 0.5
            weights["exploring"] *= 0.7
        elif self.squid.personality == Personality.ENERGETIC:
            weights["playing"] *= 1.5
            weights["exploring"] *= 1.2

        # Anxiety amplifies comfort-seeking
        if brain_state.get("anxiety", 50) > 60:
            weights["approaching_plant"] *= 1.8 + (brain_state.get("anxiety", 0) - 60) / 80

        decision_data['personality_modifiers'] = {k: v/weights.get(k,1) for k,v in weights.items() if k in weights}

        # Add randomness
        for k in weights:
            weights[k] *= random.uniform(0.88, 1.12)

        decision_data['adjusted_weights'] = weights.copy()

        # =================================================================
        # 6. SELECT AND EXECUTE DECISION
        # =================================================================
        if not any(weights.values()):
            final = "exploring"
        else:
            final = max(weights, key=weights.get)

        # Confidence calculation
        sorted_w = sorted(weights.values(), reverse=True)
        confidence = 1.0 if len(sorted_w) < 2 else (sorted_w[0] - sorted_w[1]) / sorted_w[0]

        decision_data['final_decision'] = final
        decision_data['confidence'] = confidence
        self.last_decision_data = decision_data

        result = self._execute_neural_decision(final, brain_state)
        self.last_decision_data['final_decision'] = result  # actual outcome
        return result

    def _execute_neural_decision(self, decision: str, brain_state: dict):
        """Execute decision based purely on neural signals — no redundant scanning"""
        s = self.squid

        if decision == "eating" and brain_state.get('can_see_food', 0) > 70:
            # Find closest food using existing logic method
            food = s.tamagotchi_logic.food_items
            if food:
                closest = min(food, key=lambda f: s.distance_to(f.pos().x(), f.pos().y()))
                s.move_towards(closest.pos().x(), closest.pos().y())
                dist = s.distance_to(closest.pos().x(), closest.pos().y())
                if dist < 60:
                    return "eating"
                elif dist < 120:
                    return "approaching food"
                else:
                    return "eyeing food"

        elif decision == "approaching_plant" and brain_state.get('plant_proximity', 0) > 30:
            # Use decoration cache or scene scan fallback
            plants = [item for item in s.tamagotchi_logic.user_interface.scene.items()
                      if getattr(item, 'category', '') == 'plant']
            if plants:
                closest = min(plants, key=lambda p: s.distance_to(p.sceneBoundingRect().center().x(),
                                                                 p.sceneBoundingRect().center().y()))
                s.move_towards(closest.sceneBoundingRect().center().x(),
                               closest.sceneBoundingRect().center().y())
                return "seeking comfort in plant"

        elif decision in ("playing", "throwing"):
            if s.carrying_rock:
                if s.throw_rock(random.choice(["left", "right"])):
                    return "playfully tossing rock"
            elif s.carrying_poop:
                if s.throw_poop(random.choice(["left", "right"])):
                    return "flinging poop playfully"
            # Approach nearest rock/poop if visible via brain
            elif brain_state.get('can_see_food', 0) == 0:  # crude proxy, but better than nothing
                targets = [item for item in s.tamagotchi_logic.user_interface.scene.items()
                          if getattr(item, 'category', '') in ('rock', 'poop')]
                if targets:
                    closest = min(targets, key=lambda t: s.distance_to(t.sceneBoundingRect().center().x(),
                                                                     t.sceneBoundingRect().center().y()))
                    s.move_towards(closest.sceneBoundingRect().center().x(),
                                   closest.sceneBoundingRect().center().y())
                    return "seeking toy"

        elif decision == "sleeping":
            s.go_to_sleep()
            return "settling down to sleep"

        elif decision == "fleeing" or brain_state.get('external_stimulus', 0) > 85:
            s.flee_from_center()
            return "fleeing!"

        # Default: explore with personality flavor
        flavors = {
            Personality.TIMID: ["cautiously peeking", "nervously watching"],
            Personality.ADVENTUROUS: ["boldly exploring", "seeking adventure"],
            Personality.GREEDY: ["hunting for food", "scouting"],
            Personality.LAZY: ["lounging", "drifting lazily"],
            Personality.ENERGETIC: ["zooming around", "bouncing energetically"],
            Personality.STUBBORN: ["patrolling territory", "standing ground"],
        }.get(s.personality, ["wandering", "exploring curiously"])

        style = random.choice(flavors)
        if "zoom" in style or "bounc" in style:
            s.move_erratically()
        elif "loung" in style or "drift" in style:
            s.move_slowly()
        else:
            s.move_randomly()

        return style
