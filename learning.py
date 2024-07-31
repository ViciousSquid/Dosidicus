import numpy as np

class AutonomousLearning:
    def __init__(self, num_neurons):
        self.num_neurons = num_neurons
        self.connection_strengths = np.zeros((num_neurons, num_neurons))
        self.neuron_activations = np.zeros(num_neurons)
        self.learning_rate = 0.01
        self.decay_factor = 0.99
        self.is_enabled = True  # Learning is enabled by default

    def enable_learning(self):
        self.is_enabled = True

    def disable_learning(self):
        self.is_enabled = False

    def set_neuron_activation(self, neuron_index, activation):
        self.neuron_activations[neuron_index] = activation

    def update_learning(self):
        if not self.is_enabled:
            return

        for i in range(self.num_neurons):
            for j in range(self.num_neurons):
                if i != j:
                    # Hebbian learning: neurons that fire together, wire together
                    delta = self.learning_rate * self.neuron_activations[i] * self.neuron_activations[j]
                    self.connection_strengths[i, j] += delta

                    # Apply decay to all connections
                    self.connection_strengths[i, j] *= self.decay_factor

        # Normalize connection strengths to prevent runaway values
        self.connection_strengths = np.clip(self.connection_strengths, -1, 1)

    def get_connection_strength(self, neuron1, neuron2):
        return self.connection_strengths[neuron1, neuron2]

    def get_weighted_input(self, neuron_index):
        return np.sum(self.connection_strengths[neuron_index] * self.neuron_activations)

class SquidBrain:
    def __init__(self):
        self.neurons = {
            "hunger": 0,
            "happiness": 1,
            "cleanliness": 2,
            "sleepiness": 3,
            "satisfaction": 4,
            "anxiety": 5,
            "curiosity": 6
        }
        self.learning = AutonomousLearning(len(self.neurons))

    def update_neuron(self, name, value):
        if name in self.neurons:
            self.learning.set_neuron_activation(self.neurons[name], value / 100.0)  # Normalize to 0-1 range

    def process_learning(self):
        self.learning.update_learning()

    def get_neuron_influence(self, name):
        if name in self.neurons:
            return self.learning.get_weighted_input(self.neurons[name])
        return 0

    def enable_learning(self):
        self.learning.enable_learning()

    def disable_learning(self):
        self.learning.disable_learning()

# Example usage
if __name__ == "__main__":
    brain = SquidBrain()
    brain.enable_learning()

    # Simulate some updates
    for _ in range(100):
        brain.update_neuron("hunger", np.random.randint(0, 100))
        brain.update_neuron("happiness", np.random.randint(0, 100))
        brain.process_learning()

    # Check the influence of hunger on happiness
    hunger_influence = brain.get_neuron_influence("hunger")
    print(f"Hunger's influence on other neurons: {hunger_influence}")