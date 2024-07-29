# Squid Brain Technical Overview

## 1. Brain Structure and State

The squid's brain is represented by a set of neurons, each corresponding to a specific attribute or state. The main components are:

- Basic needs: `hunger`, `happiness`, `cleanliness`, `sleepiness`
- Advanced states: `satisfaction`, `anxiety`, `curiosity`

These neurons are interconnected, and their states influence each other based on weighted connections.

## 2. Neural Network Implementation

The brain is implemented as a simple neural network:

- Neurons are represented as nodes with activation values (`0-100` for most states).
- Connections between neurons have weights (`-1 to 1`) that determine how much one neuron's state influences another.
- The network is updated periodically (every second in game time) to recalculate neuron states based on internal and external factors.

## 3. Autonomy and Decision Making

The squid has a moderate level of autonomy:

- Movement: The squid moves autonomously based on its current state and environmental factors.
- Sleep cycles: The squid will autonomously go to sleep when its sleepiness reaches 100, and wake up when it reaches 0.
- Eating: The squid will pursue and eat food items when they're available and it's hungry.
- Pooping: The squid will autonomously create poop items based on its digestive cycle.

However, the squid cannot autonomously feed itself or clean its environment, requiring player intervention for these actions.

## 4. State Updates and Interactions

The squid's brain state is updated regularly:

- Basic needs (`hunger`, `sleepiness`, `happiness`, `cleanliness`) change over time.
- Health decreases if the squid is sick or if happiness and cleanliness are very low.
- Advanced states (`satisfaction`, `anxiety`, `curiosity`) are calculated based on the basic needs and environmental factors.
- Binary states are updated based on specific conditions or player actions.

## 5. Player Interaction and Care

The player needs to care for the squid in several ways:

1. Feeding: Player must spawn food items for the squid to eat, managing its hunger.
2. Cleaning: Player must clean the environment to maintain cleanliness and prevent sickness.
3. Medicine: If the squid becomes sick, the player must administer medicine.
4. Entertainment: Player can play Rock Paper Scissors with the squid and can place decorations which affect mood/behaviours

## 6. Environmental Factors

The squid's brain also responds to environmental factors:

- Presence of food items influences the `pursuing_food` state.
- Cleanliness of the environment affects the squid's `cleanliness` state.

## 7. Learning and Adaptation

The current implementation has limited learning capabilities:

- The weights between neurons can change slightly over time, potentially allowing for some adaptation.
- A Hebbian learning mechanism is implemented, allowing for strengthening of associations between frequently co-activated neurons.

## 8. Visualization and Debugging

The game includes a brain visualization window:

- Displays the current state of all neurons.
- Shows connections between neurons and their weights.
- Allows for real-time monitoring of the squid's internal state.

## 9. Save and Load Functionality

The brain state can be saved and loaded:

- All neuron states and connection weights are stored.
- This allows for persistence of the squid's "personality" across game sessions.

## 10. Future Expansion Possibilities

The current brain implementation allows for potential expansions:

- More complex decision-making algorithms.
- Introduction of memory or long-term learning.
- More sophisticated environmental interactions.
- Implementation of mood or personality traits that influence behavior.

In conclusion, the squid's brain provides a balance between autonomy and the need for player care. It simulates a simple but effective AI that responds to both its internal state and external stimuli, creating a dynamic and engaging pet care experience.
