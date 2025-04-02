# Decision engine version 1.0   April 2025

import random
from .personality import Personality

class DecisionEngine:
    def __init__(self, squid):
        self.squid = squid
    
    def make_decision(self):
        """Decision-making based primarily on neural network state with minimal hardcoding"""
        # Get current state as a complete picture
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
            "rock_throw_cooldown": getattr(self.squid, 'rock_throw_cooldown', 0)
        }
        
        # Get brain network state - this provides the emergent behavior
        brain_state = self.squid.tamagotchi_logic.squid_brain_window.brain_widget.state
        
        # Collect active memories to influence decisions
        active_memories = self.squid.memory_manager.get_active_memories_data(3)
        memory_influence = {}
        for memory in active_memories:
            if isinstance(memory.get('raw_value'), dict):
                for key, value in memory['raw_value'].items():
                    if key in memory_influence:
                        memory_influence[key] += value * 0.5  # Memory has half weight of current state
                    else:
                        memory_influence[key] = value * 0.5
        
        # Apply memory influence to current state
        for key, value in memory_influence.items():
            if key in current_state and isinstance(current_state[key], (int, float)):
                current_state[key] = min(100, max(0, current_state[key] + value))
        
        # Check for extreme conditions that should override neural decisions
        if self.squid.sleepiness >= 95:
            self.squid.go_to_sleep()
            return "sleeping"
        
        if self.squid.is_sleeping:
            return "sleeping"
        
        # Calculate decision weights for each possible action based on neural state
        decision_weights = {
            "exploring": brain_state.get("curiosity", 50) * 0.8 * (1 - (brain_state.get("anxiety", 50) / 100)),
            "eating": brain_state.get("hunger", 50) * 1.2 if self.squid.get_visible_food() else 0,
            "approaching_rock": brain_state.get("curiosity", 50) * 0.7 if not self.squid.carrying_rock else 0,
            "throwing_rock": brain_state.get("satisfaction", 50) * 0.7 if self.squid.carrying_rock else 0,
            "avoiding_threat": brain_state.get("anxiety", 50) * 0.9,
            "organizing": brain_state.get("satisfaction", 50) * 0.5
        }
        
        # Personality modifiers
        if self.squid.personality == Personality.TIMID:
            decision_weights["avoiding_threat"] *= 1.5
            decision_weights["approaching_rock"] *= 0.7
        elif self.squid.personality == Personality.ADVENTUROUS:
            decision_weights["exploring"] *= 1.3
            decision_weights["approaching_rock"] *= 1.2
        elif self.squid.personality == Personality.GREEDY:
            decision_weights["eating"] *= 1.5
        
        # Add randomness to create more unpredictable behavior
        for key in decision_weights:
            decision_weights[key] *= random.uniform(0.85, 1.15)
        
        # Choose the highest weighted decision
        best_decision = max(decision_weights, key=decision_weights.get)
        
        # Implement the chosen decision
        if best_decision == "eating" and self.squid.get_visible_food():
            closest_food = min(self.squid.get_visible_food(), 
                            key=lambda f: self.squid.distance_to(f[0], f[1]))
            self.squid.move_towards(closest_food[0], closest_food[1])
            return "moving_to_food"
        elif best_decision == "approaching_rock" and not self.squid.carrying_rock:
            nearby_rocks = [d for d in self.squid.tamagotchi_logic.get_nearby_decorations(
                self.squid.squid_x, self.squid.squid_y, 150)
                if getattr(d, 'can_be_picked_up', False)]
            if nearby_rocks:
                self.squid.current_rock_target = random.choice(nearby_rocks)
                return "approaching_rock"
        elif best_decision == "throwing_rock" and self.squid.carrying_rock:
            direction = random.choice(["left", "right"])
            if self.squid.throw_rock(direction):
                return "throwing_rock"
        elif best_decision == "organizing" and self.squid.should_organize_decorations():
            return self.squid.organize_decorations()
        elif best_decision == "avoiding_threat" and self.squid.anxiety > 70:
            # Move away from potential threats
            if len(self.squid.tamagotchi_logic.poop_items) > 0:
                self.squid.move_erratically()
            return "avoiding_threat"
            
        # Default to exploration with varying patterns
        exploration_style = random.choice(["normal", "slow", "erratic"])
        if exploration_style == "slow":
            self.squid.move_slowly()
        elif exploration_style == "erratic":
            self.squid.move_erratically()
        else:
            self.squid.move_randomly()
        
        return "exploring"