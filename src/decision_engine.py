# Decision engine version 3.11 - June 2025
#
# changelog: 
# 3.11 - Added vision
#

import random
from .personality import Personality
import math

class DecisionEngine:
    def __init__(self, squid):
        self.squid = squid

    def make_decision(self):
        """
        Decision-making process designed for emergent behavior.
        Actions are not chosen from a simple weighted list but emerge from the interplay
        of physiological needs, memories,personality, and environmental context.
        """
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
        visible_plants = [obj for obj in visible_objects if getattr(obj, 'category', '') == 'plant'] # New

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
            "has_plant_visible": bool(visible_plants), # New
            "carrying_rock": self.squid.carrying_rock,
            "carrying_poop": self.squid.carrying_poop,
            "rock_throw_cooldown": getattr(self.squid, 'rock_throw_cooldown', 0),
            "poop_throw_cooldown": getattr(self.squid, 'poop_throw_cooldown', 0)
        }
        
        # The brain's neural network state provides the foundation for desires.
        brain_state = self.squid.tamagotchi_logic.squid_brain_window.brain_widget.state
        
        # =================================================================
        # 2. APPLY MEMORY INFLUENCE
        # =================================================================
        # Past experiences dynamically alter the squid's current motivations.
        # This makes the squid learn and adapt based on what has happened to it.
        active_memories = self.squid.memory_manager.get_active_memories_data(5) # Get more memories for richer influence
        memory_influence_weights = {
            "exploring": 1.0,
            "eating": 1.0,
            "approaching_rock": 1.0,
            "avoiding_threat": 1.0,
            "organizing": 1.0,
            "social": 1.0,
            "approaching_plant": 1.0 # New
        }

        for memory in active_memories:
            # Determine if the memory was positive, negative, or neutral
            total_effect = 0
            if isinstance(memory.get('raw_value'), dict):
                # Sum the numerical effects in the memory's raw value
                total_effect = sum(float(val) for val in memory['raw_value'].values() if isinstance(val, (int, float)))
            
            # Apply influence based on memory category
            if memory['category'] == 'food' and total_effect > 0:
                memory_influence_weights['eating'] *= 1.2 # Positive food memory increases desire to eat
            elif memory['category'] == 'interaction' and 'pickup' in memory['key'] and total_effect > 0:
                 memory_influence_weights['approaching_rock'] *= 1.1 # Positive interaction encourages more
            elif memory['category'] == 'mental_state' and 'startled' in memory['key']:
                 memory_influence_weights['avoiding_threat'] *= 1.3 # Negative startle memory promotes caution
                 memory_influence_weights['exploring'] *= 0.8 # and discourages exploration
            elif memory['category'] == 'interaction' and 'plant' in memory['key'] and total_effect > 0: # New
                memory_influence_weights['approaching_plant'] *= 1.2 # Positive plant memory encourages more

        # =================================================================
        # 3. CALCULATE PHYSIOLOGICAL URGENCY
        # =================================================================
        # Instead of a linear influence, critical needs create a powerful, non-linear urge to act.
        # This uses an exponential function to make high needs much more influential.
        urgency_multipliers = {
            "eating": math.pow(1.5, current_state['hunger'] / 25), # Urgency for food grows exponentially
            "sleeping": math.pow(1.5, current_state['sleepiness'] / 25), # Urgency for sleep also grows exponentially
            "avoiding_threat": math.pow(1.2, current_state['anxiety'] / 30) # Anxiety creates an urgent need to be safe
        }

        # Check for extreme conditions that should result in an immediate, overriding action.
        if self.squid.sleepiness >= 95:
            self.squid.go_to_sleep()
            return "exhausted"
        
        if self.squid.is_sleeping:
            # If sleeping, the squid's behavior is simple.
            return "sleeping peacefully"
        
        # Emotional states can also override standard decision-making, leading to more expressive behavior.
        if self.squid.anxiety > 80:
            return "extremely anxious"
        if self.squid.curiosity > 80:
            return "extremely curious"
        if self.squid.happiness < 20 and self.squid.anxiety > 50:
             return "distressed"
            
        # =================================================================
        # 4. CALCULATE BASE DECISION WEIGHTS
        # =================================================================
        # These are the initial "desires" based on the brain's neural state.
        decision_weights = {
            "exploring": brain_state.get("curiosity", 50) * (1 - (brain_state.get("anxiety", 50) / 120)), # Anxiety suppresses curiosity
            "eating": brain_state.get("hunger", 50) if current_state['has_food_visible'] else 0,
            "approaching_rock": brain_state.get("curiosity", 50) * 0.7 if current_state['has_rock_visible'] and not self.squid.carrying_rock else 0,
            "throwing_rock": brain_state.get("satisfaction", 50) * 0.7 if self.squid.carrying_rock else 0,
            "approaching_poop": brain_state.get("curiosity", 50) * 0.5 if current_state['has_poop_visible'] and not self.squid.carrying_poop and len(self.squid.tamagotchi_logic.poop_items) > 0 else 0,
            "throwing_poop": brain_state.get("satisfaction", 50) * 0.6 if self.squid.carrying_poop else 0,
            "approaching_plant": brain_state.get("curiosity", 20) * 0.8 if current_state['has_plant_visible'] else 0, # New
            "avoiding_threat": brain_state.get("anxiety", 50),
            "organizing": brain_state.get("satisfaction", 50) * 0.5,
            "sleeping": brain_state.get("sleepiness", 50) # Added sleeping as a conscious decision
        }

        # =================================================================
        # 5. DYNAMICALLY MODIFY WEIGHTS FOR EMERGENT BEHAVIOR
        # =================================================================
        
        # Apply Physiological Urgency: A hungry squid MUST think about food.
        decision_weights["eating"] *= urgency_multipliers.get("eating", 1.0)
        decision_weights["sleeping"] *= urgency_multipliers.get("sleeping", 1.0)
        decision_weights["avoiding_threat"] *= urgency_multipliers.get("avoiding_threat", 1.0)

        # Apply Memory Influence: Past experiences shape current desires.
        for action, weight in memory_influence_weights.items():
            if action in decision_weights:
                decision_weights[action] *= weight

        # Apply Personality and State Modifiers: Innate traits provide a behavioral baseline.
        if self.squid.personality == Personality.TIMID:
            decision_weights["avoiding_threat"] *= 1.5
            decision_weights["exploring"] *= 0.7
            decision_weights["approaching_plant"] *= 1.8 # Timid squids like plants
        elif self.squid.personality == Personality.ADVENTUROUS:
            decision_weights["exploring"] *= 1.3
            decision_weights["approaching_rock"] *= 1.2
        elif self.squid.personality == Personality.GREEDY:
            decision_weights["eating"] *= 1.5
        
        if self.squid.anxiety > 50: # Anxious squids seek comfort in plants
            decision_weights["approaching_plant"] *= 1.6

        # Add a touch of randomness to prevent behavior from being too deterministic.
        for key in decision_weights:
            decision_weights[key] *= random.uniform(0.9, 1.1)
        
        # =================================================================
        # 6. MAKE AND EXECUTE THE FINAL DECISION
        # =================================================================
        # The chosen action is the one with the highest "desire" after all factors are considered.
        if not any(decision_weights.values()):
             best_decision = "exploring" # Default action if no weights are positive
        else:
             best_decision = max(decision_weights, key=decision_weights.get)
        
        # The rest of this function implements the chosen action, including "behavioral chaining"
        # where a single decision leads to a sequence of smaller actions and status changes.
        
        # --- Behavioral Chaining Example: EATING ---
        if best_decision == "eating" and visible_food:
            closest_food = min(visible_food, 
                            key=lambda f: self.squid.distance_to(f.pos().x(), f.pos().y()))
            self.squid.move_towards(closest_food.pos().x(), closest_food.pos().y())
            
            food_distance = self.squid.distance_to(closest_food.pos().x(), closest_food.pos().y())
            # The squid's status changes based on its progress towards the goal.
            if food_distance > 100:
                return "eyeing food" # Chain 1: Initial observation
            elif food_distance > 50:
                # Chain 2: The approach, with emotion based on hunger level.
                return "approaching food eagerly" if self.squid.hunger > 70 else "cautiously approaching food"
            else:
                return "moving toward food" # Chain 3: Final approach

        # --- SLEEPING DECISION ---
        elif best_decision == "sleeping" and self.squid.sleepiness > 70:
            self.squid.go_to_sleep()
            return "feeling drowsy"

        # --- PLANT APPROACH ---
        elif best_decision == "approaching_plant" and current_state['has_plant_visible']:
            closest_plant = min(visible_plants, key=lambda p: self.squid.distance_to(p.pos().x(), p.pos().y()))
            self.squid.move_towards(closest_plant.pos().x(), closest_plant.pos().y())
            
            plant_distance = self.squid.distance_to(closest_plant.pos().x(), closest_plant.pos().y())
            if plant_distance > 100:
                return "noticing plant"
            elif plant_distance > 50:
                return "seeking comfort from plant" if self.squid.anxiety > 50 else "curiously approaching plant"
            else:
                return "moving toward plant"

        # --- ROCK APPROACH ---
        elif best_decision == "approaching_rock" and current_state['has_rock_visible']:
            closest_rock = min(visible_rocks, key=lambda r: self.squid.distance_to(r.pos().x(), r.pos().y()))
            self.squid.move_towards(closest_rock.pos().x(), closest_rock.pos().y())
            
            rock_distance = self.squid.distance_to(closest_rock.pos().x(), closest_rock.pos().y())
            if rock_distance > 100:
                return "eyeing rock"
            elif rock_distance > 50:
                return "curiously approaching rock"
            else:
                return "moving toward rock"
        
        elif best_decision == "throwing_rock" and self.squid.carrying_rock:
            # Implementation for throwing a rock...
            if self.squid.throw_rock(random.choice(["left", "right"])):
                return "playfully throwing rock"

        # --- DEFAULT EXPLORATION BEHAVIOR ---
        # If no other urgent need or desire is present, the squid defaults to exploring.
        # The style of exploration is emergent from its personality.
        exploration_options = {
            Personality.TIMID: ["cautiously exploring", "nervously watching"],
            Personality.ADVENTUROUS: ["boldly exploring", "seeking adventure"],
            Personality.GREEDY: ["searching for treasures", "scouting for food"],
            Personality.STUBBORN: ["stubbornly patrolling", "surveying domain"],
            Personality.LAZY: ["resting comfortably", "lounging lazily"],
            Personality.ENERGETIC: ["zooming around", "buzzing with energy"]
        }.get(self.squid.personality, ["exploring surroundings", "wandering aimlessly"])
        
        exploration_style = random.choice(exploration_options)
        
        # The chosen exploration style affects its movement pattern.
        if exploration_style in ["resting comfortably", "lounging lazily"]:
            self.squid.move_slowly()
        elif exploration_style in ["zooming around", "buzzing with energy"]:
            self.squid.move_erratically()
        else:
            self.squid.move_randomly()
        
        return exploration_style