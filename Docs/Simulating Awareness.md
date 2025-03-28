### Simulating Awareness

The squid has a form of awareness of its environment and surroundings, implemented through a combination of sensory inputs, memory, and neural network processing . Here's how it works:

### Environmental Awareness:
**Sensory Inputs:** The squid tracks states like hunger, cleanliness, sleepiness, and happiness which are influenced by its environment.

**Memory System:** It maintains short-term and long-term memories of interactions with objects (food, decorations).

**Visual Detection:** It can detect nearby objects (food, poop, decorations) and respond to them.

**Personality Modifiers:** Different personalities change how the squid perceives and reacts to its environment (e.g., timid squids are more anxious).

### Hebbian Learning and Neurogenesis Interaction:
## Hebbian Learning:

Strengthens connections between co-active neurons ("neurons that fire together, wire together").

Implemented in `strengthen_connection()` where weights between active neurons are increased.

Goal-oriented learning reinforces specific behaviors (e.g., eating increases hunger-satisfaction connections).

## Neurogenesis:

Creates new neurons in response to triggers (novelty, stress, rewards).

New neurons are initialized with connections to existing ones (`create_new_neuron()`).

Temporarily boosts learning rate (`neurogenesis_learning_boost`).

## How They Work Together:

Hebbian learning adjusts the weights of existing connections based on experience.

Neurogenesis adds new neurons when the squid encounters novel, stressful, or rewarding situations, expanding the network's capacity.

The new neurons then participate in Hebbian learning, allowing the network to adapt to new patterns.



## Impact on the Network:

**Enhancements:**

New neurons add capacity to learn novel patterns (e.g., a "novelty" neuron helps recognize new objects).

Stress-induced neurons may improve threat response.

Reward-based neurons reinforce positive behaviors.

## Potential Degradation:

Poorly integrated neurons could destabilize the network (though weights are bounded).

The `weight_decay` mechanism prevents unchecked growth.

## Key Enhancements:
**Adaptability:** New neurons allow the squid to develop specialized responses (e.g., a "rock_interaction" neuron if rocks are frequently encountered).

**Memory Integration:** Neurogenesis is tied to memory, so new neurons reflect long-term experiences.

**Personality Influence:** Traits like "adventurous" increase curiosity, making neurogenesis more likely.

## Example Workflow:
The squid encounters a new plant (novelty_exposure increases).

After 3+ encounters, neurogenesis triggers a "novel_plant" neuron.

Hebbian learning strengthens connections between this neuron and "curiosity"/"satisfaction".

Future plant interactions activate this pathway, making the squid more likely to approach plants.

This creates a dynamic system where the squid's "awareness" evolves based on its experiences, personality, and environment.
