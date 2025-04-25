`DecisionEngine` calculates decision weights for potential actions based on neural states, memories, and personality traits. The highest-weighted action is executed

### Core Components:

#### * Neural State Integration:

Utilizes real-time neural states (e.g., hunger, anxiety) to drive decision-making, reflecting the squid's internal motivations.

#### * Memory-Driven Influence:

Incorporates active memories to adjust current states, allowing past experiences to influence present actions dynamically.

#### * Personality-Based Modifiers:

Adjusts decision weights based on predefined personality traits, ensuring diverse behavioral patterns across different squid instances.

#### * Stochastic Elements:

Introduces randomness to decision weights, enhancing unpredictability and mimicking natural variability in behavior.

---------

Implemented in `decision_engine.py` :

```python    
    # Decision engine version 1.0   April 2025
    
    import random
    from .personality import Personality
    
    class DecisionEngine:
        def __init__(self, squid):
            """
            Initialize the DecisionEngine with a squid object.
    
            Parameters:
            - squid: An object representing the squid, containing attributes and methods
                     related to its state and behaviors.
            """
            self.squid = squid
    
        def make_decision(self):
            """
            Decision-making process based on the squid's neural network state and current conditions.
            This function aims to simulate decision-making with minimal hardcoding, relying on
            the squid's neural state and active memories.
            """
            # Gather the current state of the squid
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
    
            # Retrieve the brain network state, which influences emergent behavior
            brain_state = self.squid.tamagotchi_logic.squid_brain_window.brain_widget.state
    
            # Collect active memories to influence the decision-making process
            active_memories = self.squid.memory_manager.get_active_memories_data(3)
            memory_influence = {}
    
            # Process active memories to determine their influence on the current state
            for memory in active_memories:
                if isinstance(memory.get('raw_value'), dict):
                    for key, value in memory['raw_value'].items():
                        if key in memory_influence:
                            memory_influence[key] += value * 0.5  # Memory influence is half the weight of the current state
                        else:
                            memory_influence[key] = value * 0.5
    
            # Apply the influence of memories to the current state
            for key, value in memory_influence.items():
                if key in current_state and isinstance(current_state[key], (int, float)):
                    current_state[key] = min(100, max(0, current_state[key] + value))
    
            # Check for extreme conditions that should override neural decisions
            if self.squid.sleepiness >= 95:
                self.squid.go_to_sleep()
                return "sleeping"
    
            if self.squid.is_sleeping:
                return "sleeping"
    
            # Calculate decision weights for each possible action based on the neural state
            decision_weights = {
                "exploring": brain_state.get("curiosity", 50) * 0.8 * (1 - (brain_state.get("anxiety", 50) / 100)),
                "eating": brain_state.get("hunger", 50) * 1.2 if self.squid.get_visible_food() else 0,
                "approaching_rock": brain_state.get("curiosity", 50) * 0.7 if not self.squid.carrying_rock else 0,
                "throwing_rock": brain_state.get("satisfaction", 50) * 0.7 if self.squid.carrying_rock else 0,
                "avoiding_threat": brain_state.get("anxiety", 50) * 0.9,
                "organizing": brain_state.get("satisfaction", 50) * 0.5
            }
    
            # Adjust decision weights based on the squid's personality
            if self.squid.personality == Personality.TIMID:
                decision_weights["avoiding_threat"] *= 1.5
                decision_weights["approaching_rock"] *= 0.7
            elif self.squid.personality == Personality.ADVENTUROUS:
                decision_weights["exploring"] *= 1.3
                decision_weights["approaching_rock"] *= 1.2
            elif self.squid.personality == Personality.GREEDY:
                decision_weights["eating"] *= 1.5
    
            # Introduce randomness to make the behavior more unpredictable
            for key in decision_weights:
                decision_weights[key] *= random.uniform(0.85, 1.15)
    
            # Determine the best decision based on the highest weight
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
```
    

Explanation of Key Concepts:
----------------------------

*   **Neural Network State:** The decision-making process relies heavily on the squid's neural network state, which is influenced by various factors such as hunger, happiness, and curiosity. This state is represented by the `brain_state` dictionary.
*   **Memory Influence:** Active memories affect the squid's current state, with each memory having half the weight of the current state. This influence is calculated and applied to the current state.
*   **Personality Modifiers:** The squid's personality (e.g., timid, adventurous, greedy) modifies the decision weights, making certain actions more or less likely based on the personality trait.
*   **Randomness:** Randomness is introduced to make the squid's behavior more unpredictable, simulating real-life decision-making where actions are not always deterministic.
*   **Decision Weights:** Each possible action has a weight calculated based on the neural state and modified by personality and randomness. The action with the highest weight is chosen.
*   **Extreme Conditions:** Certain conditions, such as high sleepiness, override the neural decisions to ensure the squid's well-being.
