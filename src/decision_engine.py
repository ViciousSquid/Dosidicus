# Decision engine version 2.1   April 2025

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
            "carrying_poop": self.squid.carrying_poop,
            "rock_throw_cooldown": getattr(self.squid, 'rock_throw_cooldown', 0),
            "poop_throw_cooldown": getattr(self.squid, 'poop_throw_cooldown', 0)
        }
        
        # Get brain network state - this provides opportunity for emergent behavior
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
            return "exhausted"
        
        if self.squid.is_sleeping:
            if self.squid.sleepiness > 90:
                return "sleeping deeply"
            else:
                return "sleeping peacefully"
        
        # Check for emotional state overrides
        if self.squid.anxiety > 80:
            return "extremely anxious"
        elif self.squid.anxiety > 60:
            return "anxious"
        elif self.squid.anxiety > 40:
            return "nervous"
            
        if self.squid.curiosity > 80:
            return "extremely curious"
        elif self.squid.curiosity > 60:
            return "curious"
        elif self.squid.curiosity > 40:
            return "inquisitive"
            
        if self.squid.happiness > 80 and self.squid.anxiety < 30:
            return "content"
            
        if self.squid.happiness > 80 and self.squid.curiosity > 60:
            return "excited"
            
        if self.squid.happiness < 30:
            return "grumpy"
            
        if self.squid.satisfaction > 80:
            return "satisfied"
            
        if (self.squid.sleepiness > 70):
            return "drowsy"
            
        if self.squid.is_sick:
            return "feeling sick"
        
        # Calculate decision weights for each possible action based on neural state
        decision_weights = {
            "exploring": brain_state.get("curiosity", 50) * 0.8 * (1 - (brain_state.get("anxiety", 50) / 100)),
            "eating": brain_state.get("hunger", 50) * 1.2 if self.squid.get_visible_food() else 0,
            "approaching_rock": brain_state.get("curiosity", 50) * 0.7 if not self.squid.carrying_rock else 0,
            "throwing_rock": brain_state.get("satisfaction", 50) * 0.7 if self.squid.carrying_rock else 0,
            "approaching_poop": brain_state.get("curiosity", 50) * 0.7 if not self.squid.carrying_poop and len(self.squid.tamagotchi_logic.poop_items) > 0 else 0,
            "throwing_poop": brain_state.get("satisfaction", 50) * 0.7 if self.squid.carrying_poop else 0,
            "avoiding_threat": brain_state.get("anxiety", 50) * 0.9,
            "organizing": brain_state.get("satisfaction", 50) * 0.5
        }
        
        # Personality modifiers
        if self.squid.personality == Personality.TIMID:
            decision_weights["avoiding_threat"] *= 1.5
            decision_weights["approaching_rock"] *= 0.7
            decision_weights["approaching_poop"] *= 0.7
        elif self.squid.personality == Personality.ADVENTUROUS:
            decision_weights["exploring"] *= 1.3
            decision_weights["approaching_rock"] *= 1.2
            decision_weights["approaching_poop"] *= 1.2
        elif self.squid.personality == Personality.GREEDY:
            decision_weights["eating"] *= 1.5
        
        # Add randomness to create more unpredictable behavior
        for key in decision_weights:
            decision_weights[key] *= random.uniform(0.85, 1.15)
        
        # Choose the highest weighted decision
        best_decision = max(decision_weights, key=decision_weights.get)
        
        # Implement the chosen decision with expanded status descriptions
        if best_decision == "eating" and self.squid.get_visible_food():
            closest_food = min(self.squid.get_visible_food(), 
                            key=lambda f: self.squid.distance_to(f[0], f[1]))
            self.squid.move_towards(closest_food[0], closest_food[1])
            
            # Food-specific statuses depending on hunger and distance
            food_distance = self.squid.distance_to(closest_food[0], closest_food[1])
            if food_distance > 100:
                return "eyeing food"
            elif food_distance > 50:
                if self.squid.hunger > 70:
                    return "approaching food eagerly"
                else:
                    return "cautiously approaching food"
            else:
                return "moving toward food"
        
        elif best_decision == "approaching_rock" and not self.squid.carrying_rock:
            nearby_rocks = [d for d in self.squid.tamagotchi_logic.get_nearby_decorations(
                self.squid.squid_x, self.squid.squid_y, 150)
                if getattr(d, 'can_be_picked_up', False)]
            if nearby_rocks:
                self.squid.current_rock_target = random.choice(nearby_rocks)
                
                rock_distance = self.squid.distance_to(
                    self.squid.current_rock_target.pos().x(), 
                    self.squid.current_rock_target.pos().y())
                    
                if rock_distance > 70:
                    return "interested in rock"
                else:
                    return "examining rock curiously"
        
        elif best_decision == "throwing_rock" and self.squid.carrying_rock:
            direction = random.choice(["left", "right"])
            if self.squid.throw_rock(direction):
                if random.random() < 0.3:
                    return "tossing rock around"
                else:
                    return "playfully throwing rock"
        
        elif best_decision == "approaching_poop" and not self.squid.carrying_poop:
            nearby_poops = [d for d in self.squid.tamagotchi_logic.poop_items 
                            if self.squid.distance_to(d.pos().x(), d.pos().y()) < 150]
            if nearby_poops:
                self.squid.current_poop_target = random.choice(nearby_poops)
                return "approaching poop"
        
        elif best_decision == "throwing_poop" and self.squid.carrying_poop:
            direction = random.choice(["left", "right"])
            if self.squid.throw_poop(direction):
                return "throwing poop"
        
        elif best_decision == "organizing" and self.squid.should_organize_decorations():
            action = self.squid.organize_decorations()
            if action == "hoarding":
                if self.squid.personality == Personality.GREEDY:
                    return "hoarding items"
                else:
                    return "organizing decorations"
            elif action == "approaching_decoration":
                return "redecorating"
            else:
                return "arranging environment"
        
        elif best_decision == "avoiding_threat" and self.squid.anxiety > 70:
            # Move away from potential threats
            if len(self.squid.tamagotchi_logic.poop_items) > 0:
                self.squid.move_erratically()
                return "feeling uncomfortable"
            if self.squid.personality == Personality.TIMID:
                if self.squid.is_near_plant():
                    return "hiding behind plant"
                else:
                    return "nervously watching"
            return "hiding"
        
        # Default to exploration with varying patterns
        # Create more descriptive exploration states
        exploration_options = []
        
        # Add personality-specific exploration options
        if self.squid.personality == Personality.TIMID:
            exploration_options.extend(["cautiously exploring", "nervously watching"])
        elif self.squid.personality == Personality.ADVENTUROUS:
            exploration_options.extend(["boldly exploring", "seeking adventure", "investigating bravely"])
        elif self.squid.personality == Personality.GREEDY:
            exploration_options.extend(["searching for treasures", "eagerly collecting"])
        elif self.squid.personality == Personality.STUBBORN:
            exploration_options.extend(["stubbornly patrolling", "demanding attention"])
        elif self.squid.personality == Personality.LAZY:
            exploration_options.extend(["resting comfortably", "conserving energy", "lounging"])
        elif self.squid.personality == Personality.ENERGETIC:
            exploration_options.extend(["zooming around", "buzzing with energy", "restlessly swimming"])
        
        # Add general exploration options
        exploration_options.extend([
            "exploring surroundings", 
            "wandering aimlessly", 
            "patrolling territory", 
            "swimming lazily", 
            "investigating"
        ])
        
        # Select a random exploration style
        exploration_style = random.choice(exploration_options)
        
        if exploration_style in ["resting comfortably", "conserving energy", "lounging"]:
            self.squid.move_slowly()
        elif exploration_style in ["zooming around", "buzzing with energy", "restlessly swimming"]:
            self.squid.move_erratically()
        else:
            self.squid.move_randomly()
        
        return exploration_style