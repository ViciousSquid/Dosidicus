

Neural Network Architecture
===========================

Core Structure
--------------

*   **7 Primary Neurons**:
    *   Circular (Basic Needs): `hunger`, `happiness`, `cleanliness`, `sleepiness`
    *   Square (Complex States): `satisfaction`, `anxiety`, `curiosity`

Connection System
-----------------

    # Example weight initialization
    self.weights = {
        ("hunger", "happiness"): random.uniform(-1, 1),
        ("cleanliness", "anxiety"): -0.5,  # Pre-wired negative correlation
        # ...all possible pairwise connections...
    }

Visualization Features
----------------------

![image](https://github.com/user-attachments/assets/3cc66fc2-6c0d-40dd-aee9-1b40f3a7d52f)


Key Methods
-----------

    def update_state(self, new_state):
        # Only allow certain states to be modified
        for key in ['hunger', 'happiness', 'cleanliness', 'sleepiness']:
            if key in new_state:
                self.state[key] = new_state[key]
        self.update_weights()

Weight Dynamics
---------------

*   **Random Drift**:
    
        self.weights[conn] += random.uniform(-0.1, 0.1)  # Small random changes
    
*   **Bounded Values**: Hard-limited to \[-1, 1\] range
*   **Frozen States**: Can pause learning with `freeze_weights()`



Hebbian Learning System
=======================

Core Principle
--------------

"Neurons that fire together, wire together"

Learning Algorithm
------------------

    def perform_hebbian_learning(self):
        active_neurons = [
            n for n, v in self.state.items() 
            if (isinstance(v, (int, float)) and v > 50) 
            or (isinstance(v, bool) and v)
        ]
        
        for i, j in random.sample(
            [(a,b) for a in active_neurons for b in active_neurons if a != b], 
            min(5, len(active_neurons))
        ):
            self.update_connection(i, j, self.state[i], self.state[j])

Update Rules
------------

1.  **Basic Hebbian**:
    
        weight_change = 0.01 * (value1/100) * (value2/100)
    
2.  **Personality Modifiers**:
    
        if self.personality == Personality.GREEDY:
            weight_change *= 1.5  # Faster learning for food-related connections
    

Special Cases
-------------
![image](https://github.com/user-attachments/assets/df917330-413e-4c36-965b-3bf5e6e64e13)


Memory System
=============

Two-Tiered Architecture
-----------------------
![image](https://github.com/user-attachments/assets/492df054-a203-49d2-b2ab-f0ce298b0886)



Memory Format
-------------

    {
        "category": "food",
        "value": "Ate sushi: Hunger-20, Happiness+10",
        "timestamp": 1625097600,
        "weight": 0.85
    }

Key Operations
--------------

    # Adding memory
    memory_manager.add_short_term_memory(
        category="interaction",
        key="rock_push",
        value={"satisfaction": +8, "happiness": +5}
    )
    
    # Consolidation
    if memory['weight'] > 0.7:  # Important memory
        memory_manager.transfer_to_long_term_memory(memory)

Emergent Behaviors
==================

Personality-Driven Emergence
----------------------------
![image](https://github.com/user-attachments/assets/e490e9f8-886b-4142-8d09-bb43fc88c762)



Observed Emergent Patterns
--------------------------

1.  **Decoration Preferences**:
    *   Squids develop favorite decoration spots through reinforcement
    *   Example: Timid squids form strong plant-anxiety reduction associations
2.  **Circadian Rhythms**:
    
        # Emergent sleep-wake cycle
        if (sleepiness > 90 and 
            random.random() < hunger/100):  # Hunger affects sleep resistance
            self.go_to_sleep()
    
3.  **Learned Phobias**:
    *   Negative events create lasting anxiety connections
    *   After 3+ startle events: `anxiety-cleanliness` weight <-0.5

Measurement System
------------------

    # Behavior scoring metric
    def calculate_emergence_score():
        return sum(
            abs(w) for w in self.weights.values() 
            if w not in [-1, 0, 1]  # Exclude default/min/max
        ) / len(self.weights)

Technical Limitations
=====================

1.  **Scalability**:
    *   Current O(n²) connections (49 for 7 neurons)
    *   Practical limit ~15 neurons (225 connections)
2.  **Memory Bottlenecks**:
    *   QGraphicsScene performance degrades with >1000 items
    *   Memory recall takes O(n) time
3.  **Learning Constraints**:
    *   No backpropagation (pure Hebbian)
    *   Catastrophic forgetting possible

