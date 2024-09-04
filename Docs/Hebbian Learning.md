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

#### Stimulating the Brain

- **Update State**: The `update_state` method is used to update the state of the brain based on the input stimulation. This method updates the states of the neurons and triggers a repaint of the brain visualization.
- **Capture Training Data**: If the `capture_training_data_enabled` flag is set, the current state of the brain is captured and added to the training data.

#### Performing Hebbian Learning

The `perform_hebbian_learning` method is the core of the Hebbian learning implementation. Here's a detailed breakdown of how it works:

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

6. **Deduce Weight Change Reason**: The method deduces the reason for the weight change based on the activity levels of the neurons and the magnitude of the weight change. This information is used to generate a summary of the weight change.

7. **Update Visualization**: The brain visualization is updated to reflect the changes in the weights of the connections.

8. **Update Learning Data**: The learning data is updated with the new weight change and the direction of the change (increased or decreased).

9. **Update Log Window**: If the log window is open, it is updated with the new learning data.

#### Updating Associations

The `update_associations` method is used to update the associations between neural states based on the learned weights. The method calculates the association strength between each pair of neurons and updates the associations text area in the Associations tab.

### Example Scenario

Consider a scenario where the squid is hungry and happy. The hunger and happiness neurons are both active. The Hebbian learning rule will strengthen the connection between these two neurons because they are active together. Over time, this strengthened connection will influence the squid's behavior, making it more likely to be happy when it is hungry.

### Conclusion

The implementation of Hebbian learning in the Brain Tool is designed to adapt the neural network of the squid based on its experiences and interactions. By strengthening the connections between neurons that are frequently active together, the squid's brain can learn and adapt to its environment. This implementation provides a powerful tool for simulating and visualizing the learning process in a digital pet.
