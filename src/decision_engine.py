# Decision engine version 221_1000   May 2025

import random
# Make sure to import the Personality enum from the correct location.
# This allows access to the different personality types for the squid.
from .personality import Personality

class DecisionEngine:
    """
    The DecisionEngine uses a multi-layered approach to decision-making.
    It considers the squid's physical needs, emotional state, memories, 
    and personality, with the core logic being driven by the state of the neural network.
    """
    def __init__(self, squid):

        self.squid = squid
        
    
    def make_decision(self):
        """
        This is the core method of the DecisionEngine. It's called on a regular
        basis by the main game loop. It synthesizes all available data to determine
        the squid's next action and returns a descriptive status string.
        """
        # --- 1. State Gathering ---
        # A comprehensive snapshot of the squid's current condition is taken.
        # This includes basic needs, emotional states, and environmental factors.
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
        
        # The state of the neural network is retrieved. This is the core driver
        # for emergent, less predictable behaviors.
        brain_state = self.squid.tamagotchi_logic.squid_brain_window.brain_widget.state
        
        # --- 2. Memory Influence ---
        # Recent memories are retrieved to influence the current decision. This gives
        # the squid a sense of continuity and allows past events to affect its mood.
        active_memories = self.squid.memory_manager.get_active_memories_data(3)
        memory_influence = {}
        for memory in active_memories:
            # Check if the memory's value is a dictionary of stat changes.
            if isinstance(memory.get('raw_value'), dict):
                for key, value in memory['raw_value'].items():
                    # The influence of memory is weighted to be less impactful than the
                    # immediate, current state.
                    if key in memory_influence:
                        memory_influence[key] += value * 0.5
                    else:
                        memory_influence[key] = value * 0.5
        
        # The calculated memory influence is applied to the current state.
        for key, value in memory_influence.items():
            if key in current_state and isinstance(current_state[key], (int, float)):
                # Ensure stats remain within the valid 0-100 range.
                current_state[key] = min(100, max(0, current_state[key] + value))
        
        # --- 3. Overrides and High-Priority States ---
        # Before consulting the neural network, check for critical conditions that
        # require an immediate, hardcoded response. This ensures the squid's survival
        # and well-being.
        if self.squid.sleepiness >= 95:
            self.squid.go_to_sleep()
            return "exhausted"
        
        if self.squid.is_sleeping:
            # Provide different statuses based on how deeply the squid is sleeping.
            if self.squid.sleepiness > 90:
                return "sleeping deeply"
            else:
                return "sleeping peacefully"
        
        # Emotional state overrides provide more nuanced and immediate reactions.
        # This makes the squid's mood more transparent to the user.
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
            
        # Combinations of states can lead to more complex emotional expressions.
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
        
        # --- 4. Neural Network-Driven Decision Weighting ---
        # This is where the emergent behavior comes from. A dictionary of possible actions
        # is created, and each action is assigned a "weight" or "desirability" based
        # on the current state of the neural network (brain_state).
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
        
        # --- 5. Personality Modifiers ---
        # The squid's inherent personality applies a final layer of modification to the
        # decision weights, making certain behaviors more or less likely.
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
        
        # A touch of randomness is added to prevent behavior from becoming too
        # predictable and to create more lifelike unpredictability.
        for key in decision_weights:
            decision_weights[key] *= random.uniform(0.85, 1.15)
        
        # The action with the highest final weight is chosen as the winner.
        best_decision = max(decision_weights, key=decision_weights.get)
        
        # --- 6. Action Implementation and Status Generation ---
        # The chosen action is now implemented, and a highly descriptive, context-aware
        # status message is generated for the user.
        if best_decision == "eating" and self.squid.get_visible_food():
            closest_food = min(self.squid.get_visible_food(), 
                               key=lambda f: self.squid.distance_to(f[0], f[1]))
            self.squid.move_towards(closest_food[0], closest_food[1])
            
            # The status message changes based on distance and hunger level.
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
            # The status reflects the underlying personality driving the organization.
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
            if len(self.squid.tamagotchi_logic.poop_items) > 0:
                self.squid.move_erratically()
                return "feeling uncomfortable"
            if self.squid.personality == Personality.TIMID:
                if self.squid.is_near_plant():
                    return "hiding behind plant"
                else:
                    return "nervously watching"
            return "hiding"
        
        # --- 7. Default Behavior: Dynamic Exploration ---
        # If no other action takes precedence, the squid will explore. This is no longer
        # a single action but a dynamic selection from a list of possibilities,
        # heavily influenced by personality.
        exploration_options = []
        
        # Personality-specific exploration styles are added to the list.
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
        
        # A list of general exploration options ensures there's always something to do.
        exploration_options.extend([
            "exploring surroundings", 
            "wandering aimlessly", 
            "patrolling territory", 
            "swimming lazily", 
            "investigating"
        ])
        
        # A random style is chosen from the populated list.
        exploration_style = random.choice(exploration_options)
        
        # The chosen exploration style determines the squid's movement pattern.
        if exploration_style in ["resting comfortably", "conserving energy", "lounging"]:
            self.squid.move_slowly()
        elif exploration_style in ["zooming around", "buzzing with energy", "restlessly swimming"]:
            self.squid.move_erratically()
        else:
            self.squid.move_randomly()
        
        # The final, descriptive exploration status is returned.
        return exploration_style
    
    def get_status_text(self, decision):
        """
        Returns a descriptive status text based on the decision and personality.
        """
        personality_adverbs = {
            "adventurous": "boldly",
            "cautious": "cautiously",
            "playful": "playfully",
            "timid": "timidly",
        }
        
        personality_str = self.squid.personality.name.lower()
        adverb = personality_adverbs.get(personality_str, "")

        decision_text = decision.replace("_", " ")

        if adverb:
            return f"{adverb.capitalize()} {decision_text}"
        else:
            return decision_text.capitalize()
    