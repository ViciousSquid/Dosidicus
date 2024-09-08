# Technical Overview: Squid Learning System and Neuroplasticity

## 1. Hebbian Learning

The learning system is based on Hebbian learning, often summarized as "Neurons that fire together, wire together." This principle is implemented in the `HebbianLearning` class. For more details and to see the entire method, look here: https://github.com/ViciousSquid/Dosidicus/blob/main/Docs/Hebbian%20Learning.md

### Key Components:

- **Neurons**: Represented as attributes of the squid (e.g., hunger, satisfaction, anxiety).
- **Connections**: Represented as weights between neurons, stored in `self.brain_window.brain_widget.weights`.
- **Learning Rate**: Controls the speed of learning (`self.learning_rate`).
- **Threshold**: Determines when selective reinforcement occurs (`self.threshold`).

### Core Learning Process:

1. **Activation Correlation**: The product of two neurons' activation levels determines the strength of their association.
2. **Weight Update**: Connections are strengthened or weakened based on this correlation.
3. **Selective Reinforcement**: Larger weight changes occur when the activation product exceeds a threshold.

## 2. Neuroplasticity

Neuroplasticity is implemented through several mechanisms:

### a. Synaptic Plasticity

- **Weight Changes**: Synaptic strengths (weights) are continuously updated based on neural activity.
- **Bidirectional Changes**: Weights can increase (potentiation) or decrease (depression) based on correlated activity.

### b. Structural Plasticity

- **New Connections**: While not explicitly creating new connections, the system allows weak connections to strengthen significantly, effectively creating new functional pathways.

### c. Homeostatic Plasticity

- **Weight Decay**: Implemented to prevent runaway excitation and maintain overall network stability.
- **Weight Limits**: Maximum and minimum weight values (`self.max_weight`, `self.min_weight`) ensure bounded plasticity.

## 3. Temporal Dynamics

### a. Temporal Association

- Neurons active in close temporal proximity have their connections strengthened, implemented in `apply_temporal_association`.
- Uses an exponential decay function to model the temporal relationship between neural activations.

### b. Time-Dependent Plasticity

- Weight updates consider the time elapsed since the last update, allowing for time-sensitive learning.

## 4. Learning Algorithm Details

### Main Update Cycle (`update_weights`):

1. Calculate time elapsed since last update.
2. Get current activation levels of all neurons.
3. Update weights for all neuron pairs.
4. Apply temporal association.

### Weight Update Process (`update_connection_weight`):

1. Calculate Hebbian change: `learning_rate * activation_product`
2. Apply selective reinforcement based on activation threshold.
3. Calculate weight decay: `decay_rate * current_weight * time_elapsed`
4. Combine Hebbian change, reinforcement, and decay to get new weight.
5. Clamp weight within allowed range.
6. Update weight in both directions (connections are bidirectional).
7. Log significant changes for visualization.

### Temporal Association (`apply_temporal_association`):

1. For each pair of neurons, calculate temporal factor using exponential decay.
2. Adjust weights based on this temporal relationship.

## 5. Integration with Squid Behavior

- Learning occurs in response to various squid activities and states (eating, interacting with decorations, experiencing sickness, curiosity, anxiety).
- Each experience triggers specific connection strengthening, e.g., `learn_from_eating` strengthens connections between hunger and satisfaction neurons.

## 6. Adaptability and Personalization

- The learning system allows the squid's neural network to adapt to its experiences over time.
- This leads to personalized behavior patterns based on the squid's unique history of interactions and experiences.

## 7. Visualization and Debugging

- Weight changes are logged and can be visualized in the brain window.
- Significant changes are highlighted for easy tracking of learning progress.

## Conclusion

This learning system implements key principles of neuroplasticity and Hebbian learning, allowing the squid's neural network to adapt dynamically based on its experiences.
