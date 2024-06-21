import os
import random
import json

class Neuron:
    def __init__(self, name):
        self.name = name
        self.connections = {}
        self.value = 0

    def activate(self, input_value):
        self.value = input_value
        return max(0, min(1, self.value))  # Simple ReLU-like activation

class Brain:
    def __init__(self, brain_folder="neurons"):
        self.brain_folder = brain_folder
        self.neurons = {}
        self.load_brain()
        self.paused = False

    def load_brain(self):
        if not os.path.exists(self.brain_folder):
            os.makedirs(self.brain_folder)
            self.create_initial_brain()
        else:
            for filename in os.listdir(self.brain_folder):
                if filename.endswith(".json"):
                    neuron_name = filename[:-5]  # Remove .json extension
                    self.load_neuron(neuron_name)

    def create_initial_brain(self):
        initial_neurons = ["hunger", "tiredness", "happiness", "eat", "sleep", "play", 
                           "neuron1", "neuron2", "neuron3", "neuron4"]  # Additional 4 new neurons with no defined purpose
        for neuron_name in initial_neurons:
            neuron = Neuron(neuron_name)
            self.neurons[neuron_name] = neuron
            self.save_neuron(neuron)

        # Create random initial connections
        for neuron in self.neurons.values():
            for target in self.neurons.values():
                if neuron != target:
                    weight = random.uniform(-1, 1)
                    neuron.connections[target.name] = weight
            self.save_neuron(neuron)

    def load_neuron(self, neuron_name):
        filepath = os.path.join(self.brain_folder, f"{neuron_name}.json")
        with open(filepath, "r") as f:
            data = json.load(f)
        neuron = Neuron(neuron_name)
        neuron.connections = data["connections"]
        neuron.value = data["value"]
        self.neurons[neuron_name] = neuron

    def save_neuron(self, neuron):
        filepath = os.path.join(self.brain_folder, f"{neuron.name}.json")
        data = {
            "connections": neuron.connections,
            "value": neuron.value
        }
        with open(filepath, "w") as f:
            json.dump(data, f)

    def think(self, inputs):
        if self.paused:
            return {}

        # Set input values
        for input_name, value in inputs.items():
            if input_name in self.neurons:
                self.neurons[input_name].value = value

        # Propagate signals
        for neuron in self.neurons.values():
            activation = neuron.activate(neuron.value)
            for target_name, weight in neuron.connections.items():
                if target_name in self.neurons:
                    self.neurons[target_name].value += activation * weight

        # Get output values
        outputs = {}
        for neuron_name in ["eat", "sleep", "play"]:
            outputs[neuron_name] = self.neurons[neuron_name].value

        # Normalize outputs
        total = sum(outputs.values())
        if total > 0:
            outputs = {k: v / total for k, v in outputs.items()}

        return outputs

    def update_connections(self, reward):
        if self.paused:
            return

        learning_rate = 0.1
        for neuron in self.neurons.values():
            for target_name in neuron.connections:
                neuron.connections[target_name] += learning_rate * reward * random.uniform(-1, 1)
            self.save_neuron(neuron)

    def get_neuron_info(self, neuron_name):
        if neuron_name in self.neurons:
            neuron = self.neurons[neuron_name]
            return {
                "name": neuron.name,
                "value": neuron.value,
                "connections": neuron.connections
            }
        return None

    def set_neuron_value(self, neuron_name, value):
        if neuron_name in self.neurons:
            self.neurons[neuron_name].value = value
            self.save_neuron(self.neurons[neuron_name])

    def set_connection_weight(self, source_name, target_name, weight):
        if source_name in self.neurons and target_name in self.neurons:
            self.neurons[source_name].connections[target_name] = weight
            self.save_neuron(self.neurons[source_name])

    def toggle_pause(self):
        self.paused = not self.paused
        return self.paused

    def get_all_neurons_info(self):
        return {name: self.get_neuron_info(name) for name in self.neurons}