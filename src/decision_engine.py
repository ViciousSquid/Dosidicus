# Decision engine version 3.12 - Enhanced with decision tracking for visualization
# December 2025

import random
from .personality import Personality
import math

class DecisionEngine:
    def __init__(self, squid):
        self.squid = squid
        # Track decision data for visualization
        self.last_decision_data = {}

    def get_decision_data(self):
        """Return the last decision data for visualization"""
        return self.last_decision_data.copy()

    def make_decision(self):
        """
        Decision-making process designed for emergent behavior.
        Actions are not chosen from a simple weighted list but emerge from the interplay
        of physiological needs, memories, personality, and environmental context.
        """
        # Initialize decision tracking
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
            'personality': str(self.squid.personality).split('.')[-1],
            'randomness_applied': True
        }
        
        # =================================================================
        # 1. GATHER SENSORY AND INTERNAL STATE DATA
        # =================================================================
        # This creates a complete snapshot of the squid's current condition.

        # Gather all relevant world objects to check for visibility
        all_world_objects = []
        if hasattr(self.squid.tamagotchi_logic, 'food_items'):
            all_world_objects.extend(self.squid.tamagotchi_logic.food_items)
        if hasattr(self.squid.tamagotchi_logic, 'poop_items'):
            all_world_objects.extend(self.squid.tamagotchi_logic.poop_items)
        if hasattr(self.squid.tamagotchi_logic, 'user_interface') and hasattr(self.squid.tamagotchi_logic.user_interface, 'scene'):
            all_decorations = [item for item in self.squid.tamagotchi_logic.user_interface.scene.items() if hasattr(item, 'category')]
            all_world_objects.extend(all_decorations)

        # Use the squid's vision to get what it can actually see
        visible_objects = self.squid.get_visible_objects(all_world_objects)

        visible_rocks = [obj for obj in visible_objects if getattr(obj, 'category', '') == 'rock']
        visible_poops = [obj for obj in visible_objects if getattr(obj, 'category', '') == 'poop']
        visible_food = [obj for obj in visible_objects if getattr(obj, 'category', None) == 'food']
        visible_plants = [obj for obj in visible_objects if getattr(obj, 'category', '') == 'plant']

        current_state = {
            "hunger": self.squid.hunger,
            "happiness": self.squid.happiness,
            "cleanliness": self.squid.cleanliness,
            "sleepiness": self.squid.sleepiness,
            "satisfaction": self.squid.satisfaction,
            "anxiety": self.squid.anxiety,
            "curiosity": self.squid.curiosity,
            "is_sick": self.squid.is_sick,
            "is_sleeping": self.squid.is_sleeping,
            "has_food_visible": bool(visible_food),
            "has_rock_visible": bool(visible_rocks),
            "has_poop_visible": bool(visible_poops),
            "has_plant_visible": bool(visible_plants),
            "carrying_rock": self.squid.carrying_rock,
            "carrying_poop": self.squid.carrying_poop,
            "rock_throw_cooldown": getattr(self.squid, 'rock_throw_cooldown', 0),
            "poop_throw_cooldown": getattr(self.squid, 'poop_throw_cooldown', 0)
        }
        
        # Store inputs for visualization
        decision_data['inputs'] = current_state.copy()
        
        # The brain's neural network state provides the foundation for desires.
        brain_state = self.squid.tamagotchi_logic.squid_brain_window.brain_widget.state
        decision_data['brain_state'] = brain_state.copy()
        
        # =================================================================
        # 2. APPLY MEMORY INFLUENCE
        # =================================================================
        # Past experiences dynamically alter the squid's current motivations.
        # This makes the squid learn and adapt based on what has happened to it.
        active_memories = self.squid.memory_manager.get_active_memories_data(5)
        memory_influence_weights = {
            "exploring": 1.0,
            "eating": 1.0,
            "approaching_rock": 1.0,
            "playing": 1.0,
            "organizing": 1.0,
            "social": 1.0,
            "approaching_plant": 1.0
        }

        for memory in active_memories:
            # Determine if the memory was positive, negative, or neutral
            total_effect = 0
            if isinstance(memory.get('raw_value'), dict):
                # Sum the numerical effects in the memory's raw value
                total_effect = sum(float(val) for val in memory['raw_value'].values() if isinstance(val, (int, float)))
            
            # Apply influence based on memory category
            if memory['category'] == 'food' and total_effect > 0:
                memory_influence_weights['eating'] *= 1.2
            elif memory['category'] == 'interaction' and 'pickup' in memory['key'] and total_effect > 0:
                memory_influence_weights['approaching_rock'] *= 1.1
                memory_influence_weights['playing'] *= 1.15
            elif memory['category'] == 'play' and total_effect > 0:
                memory_influence_weights['playing'] *= 1.3
            elif memory['category'] == 'mental_state' and 'startled' in memory['key']:
                memory_influence_weights['exploring'] *= 0.8
                memory_influence_weights['approaching_plant'] *= 1.2  # Seek comfort when startled
            elif memory['category'] == 'interaction' and 'plant' in memory['key'] and total_effect > 0:
                memory_influence_weights['approaching_plant'] *= 1.2

        # Store memory influences for visualization
        decision_data['memory_influences'] = memory_influence_weights.copy()

        # =================================================================
        # 3. CALCULATE PHYSIOLOGICAL URGENCY
        # =================================================================
        # Instead of a linear influence, critical needs create a powerful, non-linear urge to act.
        urgency_multipliers = {
            "eating": math.pow(1.5, current_state['hunger'] / 25),
            "sleeping": math.pow(1.5, current_state['sleepiness'] / 25)
        }
        
        # Store urgency multipliers for visualization
        decision_data['urgency_multipliers'] = urgency_multipliers.copy()

        # Check for extreme conditions that should result in an immediate, overriding action.
        if self.squid.sleepiness >= 95:
            decision_data['final_decision'] = "exhausted"
            decision_data['confidence'] = 1.0
            self.last_decision_data = decision_data
            self.squid.go_to_sleep()
            return "exhausted"
        
        if self.squid.is_sleeping:
            decision_data['final_decision'] = "sleeping peacefully"
            decision_data['confidence'] = 1.0
            self.last_decision_data = decision_data
            return "sleeping peacefully"
        
        # Emotional states can also override standard decision-making
        if self.squid.curiosity > 80:
            decision_data['final_decision'] = "extremely curious"
            decision_data['confidence'] = 1.0
            self.last_decision_data = decision_data
            return "extremely curious"
        if self.squid.happiness < 20 and self.squid.anxiety > 50:
            decision_data['final_decision'] = "distressed"
            decision_data['confidence'] = 1.0
            self.last_decision_data = decision_data
            return "distressed"
            
        # =================================================================
        # 4. CALCULATE BASE DECISION WEIGHTS
        # =================================================================
        # These are the initial "desires" based on the brain's neural state.
        
        # Check if there are playable objects (rocks, poop when not carrying)
        has_playable_objects = (
            current_state['has_rock_visible'] or 
            current_state['has_poop_visible'] or
            self.squid.carrying_rock or 
            self.squid.carrying_poop
        )
        
        decision_weights = {
            "exploring": brain_state.get("curiosity", 50) * (1 - (brain_state.get("anxiety", 50) / 120)),
            "eating": brain_state.get("hunger", 50) if current_state['has_food_visible'] else 0,
            "approaching_rock": brain_state.get("curiosity", 50) * 0.7 if current_state['has_rock_visible'] and not self.squid.carrying_rock else 0,
            "throwing_rock": brain_state.get("satisfaction", 50) * 0.7 if self.squid.carrying_rock else 0,
            "approaching_poop": brain_state.get("curiosity", 50) * 0.5 if current_state['has_poop_visible'] and not self.squid.carrying_poop and len(self.squid.tamagotchi_logic.poop_items) > 0 else 0,
            "throwing_poop": brain_state.get("satisfaction", 50) * 0.6 if self.squid.carrying_poop else 0,
            "approaching_plant": brain_state.get("curiosity", 20) * 0.8 if current_state['has_plant_visible'] else 0,
            "playing": brain_state.get("satisfaction", 50) * brain_state.get("happiness", 50) / 100 if has_playable_objects else 0,
            "organizing": brain_state.get("satisfaction", 50) * 0.5,
            "sleeping": brain_state.get("sleepiness", 50)
        }
        
        # Store base weights for visualization
        decision_data['base_weights'] = decision_weights.copy()

        # =================================================================
        # 5. DYNAMICALLY MODIFY WEIGHTS FOR EMERGENT BEHAVIOR
        # =================================================================
        
        # Apply Physiological Urgency
        decision_weights["eating"] *= urgency_multipliers.get("eating", 1.0)
        decision_weights["sleeping"] *= urgency_multipliers.get("sleeping", 1.0)

        # Apply Memory Influence
        for action, weight in memory_influence_weights.items():
            if action in decision_weights:
                decision_weights[action] *= weight

        # Apply Personality and State Modifiers
        personality_modifiers = {action: 1.0 for action in decision_weights.keys()}
        
        if self.squid.personality == Personality.TIMID:
            personality_modifiers["exploring"] = 0.7
            personality_modifiers["approaching_plant"] = 2.2  # Timid squids strongly prefer hiding in plants
            personality_modifiers["playing"] = personality_modifiers.get("playing", 1.0) * 0.7  # Less playful when timid
        elif self.squid.personality == Personality.ADVENTUROUS:
            personality_modifiers["exploring"] = 1.3
            personality_modifiers["approaching_rock"] = 1.2
            personality_modifiers["playing"] = 1.2
        elif self.squid.personality == Personality.GREEDY:
            personality_modifiers["eating"] = 1.5
        elif self.squid.personality == Personality.ENERGETIC:
            personality_modifiers["playing"] = 1.4
            personality_modifiers["exploring"] = 1.2
        elif self.squid.personality == Personality.LAZY:
            personality_modifiers["playing"] = 0.6
            personality_modifiers["exploring"] = 0.8
        
        # Anxiety makes plants more attractive (comfort seeking)
        if self.squid.anxiety > 50:
            anxiety_multiplier = 1.6 + (self.squid.anxiety - 50) / 100  # Scales from 1.6 to 2.1
            if self.squid.personality == Personality.TIMID:
                anxiety_multiplier *= 1.3  # Timid squids seek shelter even more strongly
            personality_modifiers["approaching_plant"] = personality_modifiers.get("approaching_plant", 1.0) * anxiety_multiplier
            personality_modifiers["exploring"] = personality_modifiers.get("exploring", 1.0) * 0.7
            personality_modifiers["playing"] = personality_modifiers.get("playing", 1.0) * 0.8

        # Apply personality modifiers to weights
        for action, modifier in personality_modifiers.items():
            if action in decision_weights:
                decision_weights[action] *= modifier
        
        # Store personality modifiers for visualization
        decision_data['personality_modifiers'] = personality_modifiers

        # Add randomness to prevent deterministic behavior
        for key in decision_weights:
            decision_weights[key] *= random.uniform(0.9, 1.1)
        
        # Store final adjusted weights
        decision_data['adjusted_weights'] = decision_weights.copy()
        
        # =================================================================
        # 6. MAKE AND EXECUTE THE FINAL DECISION
        # =================================================================
        if not any(decision_weights.values()):
            best_decision = "exploring"
        else:
            best_decision = max(decision_weights, key=decision_weights.get)
        
        # Calculate confidence (how much better is the top choice than the second best)
        sorted_weights = sorted(decision_weights.values(), reverse=True)
        if len(sorted_weights) > 1 and sorted_weights[0] > 0:
            confidence = (sorted_weights[0] - sorted_weights[1]) / sorted_weights[0]
        else:
            confidence = 1.0
        
        decision_data['final_decision'] = best_decision
        decision_data['confidence'] = confidence
        
        # Store decision data for visualization
        self.last_decision_data = decision_data
        
        # Execute the chosen action
        result = self._execute_decision(best_decision, visible_food, visible_rocks, visible_plants)
        
        # Update final decision with the actual result
        self.last_decision_data['final_decision'] = result
        
        return result

    def _execute_decision(self, decision, visible_food, visible_rocks, visible_plants):
        """Execute the chosen decision and return the status string"""
        # --- Behavioral Chaining Example: EATING ---
        if decision == "eating" and visible_food:
            closest_food = min(visible_food, 
                            key=lambda f: self.squid.distance_to(f.pos().x(), f.pos().y()))
            self.squid.move_towards(closest_food.pos().x(), closest_food.pos().y())
            
            food_distance = self.squid.distance_to(closest_food.pos().x(), closest_food.pos().y())
            if food_distance > 100:
                return "eyeing food"
            elif food_distance > 50:
                return "approaching food eagerly" if self.squid.hunger > 70 else "cautiously approaching food"
            else:
                return "moving toward food"

        # --- SLEEPING DECISION ---
        elif decision == "sleeping" and self.squid.sleepiness > 70:
            self.squid.go_to_sleep()
            return "feeling drowsy"

        # --- PLAYING BEHAVIOR ---
        elif decision == "playing":
            # If carrying something, throw it playfully
            if self.squid.carrying_rock:
                if self.squid.throw_rock(random.choice(["left", "right"])):
                    return "playfully tossing rock"
            elif self.squid.carrying_poop:
                if self.squid.throw_poop(random.choice(["left", "right"])):
                    return "playfully flinging poop"
            # Otherwise, approach nearest playable object
            elif visible_rocks:
                closest_rock = min(visible_rocks, key=lambda r: self.squid.distance_to(r.pos().x(), r.pos().y()))
                self.squid.move_towards(closest_rock.pos().x(), closest_rock.pos().y())
                return "seeking toy to play with"
            else:
                return "looking for something to play with"

        # --- PLANT APPROACH (Comfort Seeking) ---
        elif decision == "approaching_plant" and visible_plants:
            closest_plant = min(visible_plants, key=lambda p: self.squid.distance_to(p.pos().x(), p.pos().y()))
            self.squid.move_towards(closest_plant.pos().x(), closest_plant.pos().y())
            
            plant_distance = self.squid.distance_to(closest_plant.pos().x(), closest_plant.pos().y())
            is_timid = self.squid.personality == Personality.TIMID
            
            if plant_distance > 100:
                return "noticing plant"
            elif plant_distance > 50:
                if self.squid.anxiety > 50:
                    return "seeking shelter in plant"
                elif is_timid:
                    return "cautiously approaching safe spot"
                else:
                    return "curiously approaching plant"
            elif plant_distance < 30:
                if is_timid or self.squid.anxiety > 40:
                    return "hiding behind plant"
                else:
                    return "resting near plant"
            else:
                return "moving toward plant"

        # --- ROCK APPROACH ---
        elif decision == "approaching_rock" and visible_rocks:
            closest_rock = min(visible_rocks, key=lambda r: self.squid.distance_to(r.pos().x(), r.pos().y()))
            self.squid.move_towards(closest_rock.pos().x(), closest_rock.pos().y())
            
            rock_distance = self.squid.distance_to(closest_rock.pos().x(), closest_rock.pos().y())
            if rock_distance > 100:
                return "eyeing rock"
            elif rock_distance > 50:
                return "curiously approaching rock"
            else:
                return "moving toward rock"
        
        elif decision == "throwing_rock" and self.squid.carrying_rock:
            if self.squid.throw_rock(random.choice(["left", "right"])):
                return "playfully throwing rock"

        # --- DEFAULT EXPLORATION BEHAVIOR ---
        exploration_options = {
            Personality.TIMID: ["cautiously exploring", "nervously watching"],
            Personality.ADVENTUROUS: ["boldly exploring", "seeking adventure"],
            Personality.GREEDY: ["searching for treasures", "scouting for food"],
            Personality.STUBBORN: ["stubbornly patrolling", "surveying domain"],
            Personality.LAZY: ["resting comfortably", "lounging lazily"],
            Personality.ENERGETIC: ["zooming around", "buzzing with energy"]
        }.get(self.squid.personality, ["exploring surroundings", "wandering aimlessly"])
        
        exploration_style = random.choice(exploration_options)
        
        if exploration_style in ["resting comfortably", "lounging lazily"]:
            self.squid.move_slowly()
        elif exploration_style in ["zooming around", "buzzing with energy"]:
            self.squid.move_erratically()
        else:
            self.squid.move_randomly()
        
        return exploration_style
