The squid utilises hebbian learning:

```python
def perform_hebbian_learning(self):
        if self.is_paused or not hasattr(self, 'brain_widget'):
            return

        # Get the current state of all neurons
        current_state = self.brain_widget.state

        # Determine which neurons are significantly active
        active_neurons = []
        for neuron, value in current_state.items():
            if isinstance(value, (int, float)) and value > 50:
                active_neurons.append(neuron)
            elif isinstance(value, bool) and value:
                active_neurons.append(neuron)
            elif isinstance(value, str):
                # Handle string values (e.g., direction) if needed
                pass 

        # If less than two neurons are active, no learning occurs
        if len(active_neurons) < 2:
            return

        # Perform learning for all pairs of active neurons
        for i in range(len(active_neurons)):
            for j in range(i + 1, len(active_neurons)):
                neuron1 = active_neurons[i]
                neuron2 = active_neurons[j]
                value1 = self.get_neuron_value(current_state[neuron1])
                value2 = self.get_neuron_value(current_state[neuron2])
                self.update_connection(neuron1, neuron2, value1, value2)
```

We can ask the network to theorise why weights changed and more..

```python
def deduce_weight_change_reason(self, pair, value1, value2):        ## Ask the network for reason why the weights changed
        neuron1, neuron2 = pair
        threshold_high = 70
        threshold_low = 30
        weight_change = new_weight - prev_weight

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
