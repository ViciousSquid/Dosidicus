## Hebbian Learning

Hebbian learning is a fundamental principle in neuroscience that states, "Neurons that fire together, wire together." In the context of the Brain Tool, this principle is used to strengthen the connections between neurons that are frequently active together. This implementation of Hebbian learning is designed to adapt the neural network of the squid based on its experiences and interactions.

### Key Concepts

1. **Neuron States**: Each neuron in the brain has a state that represents its level of activity. For example, neurons can represent states like hunger, happiness, cleanliness, sleepiness, etc.
2. **Connections**: Neurons are connected to each other with weights that represent the strength of the connection. Positive weights indicate excitatory connections, while negative weights indicate inhibitory connections.
3. **Weight Updates**: The weights of the connections are updated based on the co-activation of neurons. If two neurons are active together, their connection is strengthened.

### Implementation Details

#### Initialization

- **Neuron Positions**: The positions of the neurons are initialized in a dictionary called `neuron_positions`.
- **Connections**: The connections between neurons are initialized in a list called `connections`.
- **Weights**: The weights of the connections are initialized in a dictionary called `weights`. Initially, the weights are set to random values between -1 and 1.

#### Performing Hebbian Learning

The `perform_hebbian_learning` method is the core of the Hebbian learning implementation:

```python
def perform_hebbian_learning(self):
    """Enhanced Hebbian learning with neurogenesis support"""
    if self.is_paused:
        return
        
    print("Starting Hebbian training...")
    
    # Get all neurons including new ones
    all_neurons = list(self.brain_widget.neuron_positions.keys())
    current_state = self.brain_widget.state
    
    # Get personality modifier
    personality = getattr(self.tamagotchi_logic.squid, 'personality', 'ADVENTUROUS')
    personality_mod = self._get_personality_modifier(personality)
    
    # Include neurons that are either:
    # - Above activation threshold (50) 
    # OR
    # - Newly created (less than 2 minutes old)
    active_neurons = []
    for neuron in all_neurons:
        value = current_state.get(neuron, 0)
        
        # Check if neuron is active
        is_active = (isinstance(value, (int, float)) and (value > 50)
        
        # Check if neuron is new (give them priority)
        is_new = (neuron in getattr(self.tamagotchi_logic.squid.hebbian_learning, 'new_neurons', []))
        
        if is_active or is_new:
            active_neurons.append(neuron)
    
    if len(active_neurons) < 2:
        return

    # Calculate dynamic learning rate based on squid's state
    base_rate = 0.1
    learning_rate = base_rate * personality_mod
    
    # Boost learning when squid is curious or satisfied
    if current_state.get('curiosity', 0) > 70:
        learning_rate *= 1.5
    if current_state.get('satisfaction', 0) > 65:
        learning_rate *= 1.3
        
    # Perform learning for neuron pairs
    sample_size = min(8, len(active_neurons) * (len(active_neurons) - 1) // 2)
    sampled_pairs = random.sample(
        [(i, j) for i in range(len(active_neurons)) for j in range(i+1, len(active_neurons))],
        sample_size
    )

    for i, j in sampled_pairs:
        neuron1 = active_neurons[i]
        neuron2 = active_neurons[j]
        
        # Get neuron values (handle boolean states)
        val1 = self.get_neuron_value(current_state.get(neuron1, 50))
        val2 = self.get_neuron_value(current_state.get(neuron2, 50))
        
        # Apply learning
        self.update_connection(neuron1, neuron2, val1, val2, learning_rate)
        
        # Special handling for new neurons - form additional connections
        is_new1 = neuron1 in getattr(self.tamagotchi_logic.squid.hebbian_learning, 'new_neurons', [])
        is_new2 = neuron2 in getattr(self.tamagotchi_logic.squid.hebbian_learning, 'new_neurons', [])
        
        if is_new1 or is_new2:
            # New neurons get extra connections to core emotions
            for core_neuron in ['happiness', 'satisfaction', 'curiosity']:
                if core_neuron not in [neuron1, neuron2]:
                    core_val = self.get_neuron_value(current_state.get(core_neuron, 50))
                    self.update_connection(neuron1, core_neuron, val1, core_val, learning_rate * 1.3)
                    self.update_connection(neuron2, core_neuron, val2, core_val, learning_rate * 1.3)

    # Update visualization and associations
    self.brain_widget.update()
    self.update_associations()
    
    # Debug output
    if self.debug_mode:
        print(f"Hebbian learning complete. Processed {len(sampled_pairs)} pairs.")
        print(f"Learning rate: {learning_rate:.2f} (Personality mod: {personality_mod:.1f})")
        if any(n in getattr(self.tamagotchi_logic.squid.hebbian_learning, 'new_neurons', []) for n in active_neurons):
            print("New neurons participated in learning")

def _get_personality_modifier(self, personality):
    """Get learning rate modifier based on personality"""
    modifiers = {
        'TIMID': 0.8,    # Learns more slowly
        'ADVENTUROUS': 1.5, # Learns faster
        'LAZY': 0.7,
        'ENERGETIC': 1.2,
        'INTROVERT': 0.9,
        'GREEDY': 1.3,   # Learns quickly about food
        'STUBBORN': 0.6  # Resists learning
    }
    if isinstance(personality, str):
        return modifiers.get(personality, 1.0)
    return modifiers.get(personality.name, 1.0)

def update_connection(self, neuron1, neuron2, value1, value2, learning_rate):
    """Enhanced connection update with neurogenesis support"""
    # Ensure connection exists
    if (neuron1, neuron2) not in self.brain_widget.weights:
        self.brain_widget.weights[(neuron1, neuron2)] = 0.0
        if (neuron1, neuron2) not in self.brain_widget.connections:
            self.brain_widget.connections.append((neuron1, neuron2))
    
    # Calculate weight change with novelty boost
    is_new_neuron = (neuron1 in getattr(self.tamagotchi_logic.squid.hebbian_learning, 'new_neurons', []) or
                    neuron2 in getattr(self.tamagotchi_logic.squid.hebbian_learning, 'new_neurons', []))
    
    novelty_boost = 1.5 if is_new_neuron else 1.0
    weight_change = learning_rate * novelty_boost * (value1/100) * (value2/100)
    
    # Apply weight change
    prev_weight = self.brain_widget.weights[(neuron1, neuron2)]
    new_weight = max(-1.0, min(1.0, prev_weight + weight_change))
    self.brain_widget.weights[(neuron1, neuron2)] = new_weight
    
    # Log the change
    self._log_weight_change(neuron1, neuron2, prev_weight, new_weight, is_new_neuron)

def _log_weight_change(self, neuron1, neuron2, prev, new, is_new):
    """Enhanced logging with neurogenesis awareness"""
    timestamp = QtCore.QTime.currentTime().toString("hh:mm:ss")
    change = new - prev
    
    # Format message with color coding
    msg = f"{timestamp} - {neuron1} ↔ {neuron2}: "
    msg += f"<font color='red'>{prev:.3f}</font> → " 
    msg += f"<font color='green'>{new:.3f}</font> "
    msg += f"(Δ: {change:+.3f})"
    
    if is_new:
        msg += " <font color='blue'>[NEW NEURON]</font>"
    
    self.weight_changes_text.append(msg)
    self.learning_data.append((timestamp, neuron1, neuron2, change, is_new))
```

 Here's a detailed breakdown of how it works:

1. **Get Current State**: The current state of all neurons is retrieved. This state includes the levels of hunger, happiness, cleanliness, sleepiness, etc.

2. **Determine Active Neurons**: The method identifies which neurons are significantly active. A neuron is considered active if its state value is above a certain threshold (e.g., 50 for continuous values or `True` for boolean values).

3. **Include Decoration Effects**: The method also considers the effects of decorations in the squid's environment. Decorations can have short-term memory effects that influence the states of the neurons.

4. **Sample Active Neuron Pairs**: If less than two neurons are active, no learning occurs. Otherwise, a random subset of active neuron pairs is sampled for learning.

5. **Update Weights**: For each sampled pair of active neurons, the weight of their connection is updated using the Hebbian learning rule. The weight change is calculated as follows:

   ```python
   weight_change = 0.01 * (value1 / 100) * (value2 / 100)
   new_weight = min(max(prev_weight + weight_change, -1), 1)
   ```

   - `value1` and `value2` are the states of the two neurons, normalized to the range [0, 1].
   - `prev_weight` is the previous weight of the connection.
   - `new_weight` is the updated weight, clamped to the range [-1, 1].

6. **Deduce Weight Change Reason**: The method deduces the reason for the weight change based on the activity levels of the neurons and the magnitude of the weight change:

```python
def deduce_weight_change_reason(self, pair, value1, value2, prev_weight, new_weight, weight_change):
        neuron1, neuron2 = pair
        threshold_high = 70
        threshold_low = 30

        reasons = []

        # Analyze neuron activity levels
        if value1 > threshold_high and value2 > threshold_high:
            reasons.append(f"Both {neuron1.upper()} and {neuron2.upper()} were highly active")
        elif value1 < threshold_low and value2 < threshold_low:
            reasons.append(f"Both {neuron1.upper()} and {neuron2.upper()} had low activity")
        elif value1 > threshold_high:
            reasons.append(f"{neuron1.upper()} was highly active")
        elif value2 > threshold_high:
            reasons.append(f"{neuron2.upper()} was highly active")

        # Analyze weight change
        if abs(weight_change) > 0.1:
            if weight_change > 0:
                reasons.append("Strong positive reinforcement")
            else:
                reasons.append("Strong negative reinforcement")
        elif abs(weight_change) > 0.01:
            if weight_change > 0:
                reasons.append("Moderate positive reinforcement")
            else:
                reasons.append("Moderate negative reinforcement")
        else:
            reasons.append("Weak reinforcement")

        # Analyze the relationship between neurons
        if "hunger" in pair and "satisfaction" in pair:
            reasons.append("Potential hunger-satisfaction relationship")
        elif "cleanliness" in pair and "happiness" in pair:
            reasons.append("Potential cleanliness-happiness relationship")

        # Analyze the current weight
        if abs(new_weight) > 0.8:
            reasons.append("Strong connection formed")
        elif abs(new_weight) < 0.2:
            reasons.append("Weak connection")

        # Analyze learning progress
        if abs(prev_weight) < 0.1 and abs(new_weight) > 0.1:
            reasons.append("New significant connection emerging")
        elif abs(prev_weight) > 0.8 and abs(new_weight) < 0.8:
            reasons.append("Previously strong connection weakening")

        # Combine reasons
        if len(reasons) > 1:
            return " | ".join(reasons)
        elif len(reasons) == 1:
            return reasons[0]
        else:
            return "Complex interaction with no clear single reason"
```

7. **Update Visualization**: The brain visualization is updated to reflect the changes in the weights of the connections.

8. **Update Learning Data**: The learning data is updated with the new weight change and the direction of the change (increased or decreased).

9. **Update Log Window**: If the log window is open, it is updated with the new learning data.

#### Updating Associations

The `update_associations` method is used to update the associations between neural states based on the learned weights. The method calculates the association strength between each pair of neurons and updates the associations text area in the Associations tab.

### Example Scenario

Consider a scenario where the squid is hungry and happy. The hunger and happiness neurons are both active. The Hebbian learning rule will strengthen the connection between these two neurons because they are active together. Over time, this strengthened connection will influence the squid's behavior, making it more likely to be happy when it is hungry.

### Conclusion

The implementation of Hebbian learning in the Brain Tool is designed to adapt the neural network of the squid based on its experiences and interactions. By strengthening the connections between neurons that are frequently active together, the squid's brain can learn and adapt to its environment. This implementation provides a powerful tool for simulating and visualizing the learning process in a digital pet.
