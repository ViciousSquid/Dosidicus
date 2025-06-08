# Decision engine version 3.0 - June 2025 - Emergent Behavior Revamp

import random
from .personality import Personality
import math # Import math for more complex calculations

class DecisionEngine:
    def __init__(self, squid):
        self.squid = squid
    
    def make_decision(self):
        """
        Decision-making process designed for emergent behavior.
        Actions are not chosen from a simple weighted list but emerge from the interplay
        of physiological needs, memories, personality, and environmental context.
        """
        # =================================================================
        # 1. GATHER SENSORY AND INTERNAL STATE DATA
        # =================================================================
        # This creates a complete snapshot of the squid's current condition.
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
            "has_food_visible": bool(self.squid.get_visible_food()),
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
            "social": 1.0 # A new weight for potential social interactions
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
            "approaching_rock": brain_state.get("curiosity", 50) * 0.7 if not self.squid.carrying_rock else 0,
            "throwing_rock": brain_state.get("satisfaction", 50) * 0.7 if self.squid.carrying_rock else 0,
            "approaching_poop": brain_state.get("curiosity", 50) * 0.5 if not self.squid.carrying_poop and len(self.squid.tamagotchi_logic.poop_items) > 0 else 0,
            "throwing_poop": brain_state.get("satisfaction", 50) * 0.6 if self.squid.carrying_poop else 0,
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

        # Apply Personality Modifiers: Innate traits provide a behavioral baseline.
        if self.squid.personality == Personality.TIMID:
            decision_weights["avoiding_threat"] *= 1.5
            decision_weights["exploring"] *= 0.7
        elif self.squid.personality == Personality.ADVENTUROUS:
            decision_weights["exploring"] *= 1.3
            decision_weights["approaching_rock"] *= 1.2
        elif self.squid.personality == Personality.GREEDY:
            decision_weights["eating"] *= 1.5
        
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
        if best_decision == "eating" and self.squid.get_visible_food():
            closest_food = min(self.squid.get_visible_food(), 
                            key=lambda f: self.squid.distance_to(f[0], f[1]))
            self.squid.move_towards(closest_food[0], closest_food[1])
            
            food_distance = self.squid.distance_to(closest_food[0], closest_food[1])
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

        # (The rest of the action implementations follow a similar logic)
        elif best_decision == "approaching_rock" and not self.squid.carrying_rock:
            # Implementation for approaching a rock...
            nearby_rocks = [d for d in self.squid.tamagotchi_logic.get_nearby_decorations(
                self.squid.squid_x, self.squid.squid_y, 150)
                if getattr(d, 'can_be_picked_up', False)]
            if nearby_rocks:
                self.squid.current_rock_target = random.choice(nearby_rocks)
                return "interested in rock"
        
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