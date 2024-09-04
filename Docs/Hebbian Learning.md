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
        if self.is_paused or not hasattr(self, 'brain_widget') or not self.tamagotchi_logic or not self.tamagotchi_logic.squid:
            return

        # Get the current state of all neurons
        current_state = self.brain_widget.state

        # Determine which neurons are significantly active
        active_neurons = []
        for neuron, value in current_state.items():
            if neuron == 'position':
                # Skip the position tuple
                continue
            if isinstance(value, (int, float)) and value > 50:
                active_neurons.append(neuron)
            elif isinstance(value, bool) and value:
                active_neurons.append(neuron)
            elif isinstance(value, str):
                # For string values (like 'direction'), we consider them active
                active_neurons.append(neuron)

        # Include decoration effects in learning
        decoration_memories = self.tamagotchi_logic.squid.memory_manager.get_all_short_term_memories('decorations')
        
        if isinstance(decoration_memories, dict):
            for decoration, effects in decoration_memories.items():
                for stat, boost in effects.items():
                    if isinstance(boost, (int, float)) and boost > 0:
                        if stat not in active_neurons:
                            active_neurons.append(stat)
        elif isinstance(decoration_memories, list):
            for memory in decoration_memories:
                for stat, boost in memory.get('effects', {}).items():
                    if isinstance(boost, (int, float)) and boost > 0:
                        if stat not in active_neurons:
                            active_neurons.append(stat)

        # If less than two neurons are active, no learning occurs
        if len(active_neurons) < 2:
            return

        # Perform learning for a random subset of active neuron pairs
        sample_size = min(5, len(active_neurons) * (len(active_neurons) - 1) // 2)
        sampled_pairs = random.sample([(i, j) for i in range(len(active_neurons)) for j in range(i+1, len(active_neurons))], sample_size)

        for i, j in sampled_pairs:
            neuron1 = active_neurons[i]
            neuron2 = active_neurons[j]
            value1 = self.get_neuron_value(current_state.get(neuron1, 50))  # Default to 50 if not in current_state
            value2 = self.get_neuron_value(current_state.get(neuron2, 50))
            self.update_connection(neuron1, neuron2, value1, value2)

        # Update the brain visualization
        self.brain_widget.update()
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
