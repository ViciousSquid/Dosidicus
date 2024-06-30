#
# A simple neural network with input, hidden, and output layers.
# Each neuron in the network is represented by an instance of the Neuron class.
#

import os
import random
import json
import numpy as np

class Neuron:
    def __init__(self, name, layer):
        # Initialize a new neuron with the given name and layer
        self.name = name
        self.layer = layer
        self.connections = {}  # Dictionary to store connections to other neurons
        self.value = 0  # Current value of the neuron

    def activate(self, input_value):
        # Apply the sigmoid activation function to the input value and update the neuron's value
        self.value = 1 / (1 + np.exp(-input_value))  # Sigmoid activation
        return self.value

class Brain:
    def __init__(self, brain_folder="neurons"):
        # Initialize a new brain with the given folder for saving and loading neuron data
        self.brain_folder = brain_folder
        self.neurons = {'input': {}, 'hidden': {}, 'output': {}}  # Dictionary to store neurons in each layer
        self.paused = False  # Flag to indicate whether the brain is paused or not

        if not os.path.exists(self.brain_folder):
            # If the brain folder does not exist, create it and create an initial brain
            os.makedirs(self.brain_folder)
            self.create_initial_brain()
        else:
            # If the brain folder exists, check if it is empty
            if not os.listdir(self.brain_folder):
                # If the brain folder is empty, create an initial brain
                self.create_initial_brain()
            else:
                # If the brain folder is not empty, load the brain data from the neuron files
                self.load_brain()

    def load_brain(self):
        # Load the brain data from the neuron files in the brain folder
        for filename in os.listdir(self.brain_folder):
            if filename.endswith(".json"):
                self.load_neuron(filename[:-5])  # Remove .json extension

    def create_initial_brain(self):
        # Create an initial brain with input, hidden, and output layers
        input_neurons = ["hunger", "tiredness", "happiness", "food_distance", "food_angle"]
        hidden_neurons = ["h1", "h2", "h3", "h4"]
        output_neurons = ["eat", "sleep", "play", "move_speed", "move_angle"]

        # Create neurons for each layer
        for name in input_neurons:
            self.neurons['input'][name] = Neuron(name, 'input')
        for name in hidden_neurons:
            self.neurons['hidden'][name] = Neuron(name, 'hidden')
        for name in output_neurons:
            self.neurons['output'][name] = Neuron(name, 'output')

        # Create random initial connections between neurons in adjacent layers
        for layer in ['input', 'hidden']:
            next_layer = 'hidden' if layer == 'input' else 'output'
            for neuron in self.neurons[layer].values():
                for target in self.neurons[next_layer].values():
                    weight = random.uniform(-1, 1)
                    neuron.connections[target.name] = weight

        # Save the initial brain data to the neuron files
        self.save_brain()

    def load_neuron(self, neuron_name):
        # Load the neuron data from the given neuron file
        file_path = os.path.join(self.brain_folder, f"{neuron_name}.json")
        if os.path.exists(file_path):
            with open(file_path, 'r') as file:
                data = json.load(file)
                layer = data['layer']
                neuron = Neuron(neuron_name, layer)
                neuron.connections = data['connections']
                neuron.value = data['value']
                self.neurons[layer][neuron_name] = neuron

    def save_brain(self):
        # Save the brain data to the neuron files in the brain folder
        for layer in self.neurons:
            for neuron in self.neurons[layer].values():
                self.save_neuron(neuron)

    def save_neuron(self, neuron):
        # Save the neuron data to the given neuron file
        file_path = os.path.join(self.brain_folder, f"{neuron.name}.json")
        data = {
            'layer': neuron.layer,
            'connections': neuron.connections,
            'value': neuron.value
        }
        with open(file_path, 'w') as file:
            json.dump(data, file)

    def get_all_neurons_info(self):
        # Get a dictionary containing information about all neurons in the brain
        return {layer: {name: {'value': neuron.value, 'connections': neuron.connections}
                        for name, neuron in neurons.items()}
                for layer, neurons in self.neurons.items()}

    def think(self, inputs):
        # Calculate the output values and movement direction vector based on the input values

        # Set input values
        for name, value in inputs.items():
            if name in self.neurons['input']:
                self.neurons['input'][name].value = value

        # Propagate through hidden layer
        for hidden_neuron in self.neurons['hidden'].values():
            # Calculate the weighted sum of inputs to the hidden neuron
            hidden_input = sum(self.neurons['input'][name].value * weight
                               for name, weight in hidden_neuron.connections.items()
                               if name in self.neurons['input'])
            # Apply the sigmoid activation function to the hidden neuron
            hidden_neuron.activate(hidden_input)

        # Propagate to output layer
        outputs = {}
        for output_neuron in self.neurons['output'].values():
            # Calculate the weighted sum of inputs to the output neuron
            output_input = sum(self.neurons['hidden'][name].value * weight
                               for name, weight in output_neuron.connections.items()
                               if name in self.neurons['hidden'])
            # Apply the sigmoid activation function to the output neuron
            outputs[output_neuron.name] = output_neuron.activate(output_input)

        # Calculate movement direction based on output values
        # In this example, I'm assuming that 'move_speed' and 'move_angle' are output neurons
        move_direction = np.array([outputs['move_speed'], outputs['move_angle']])
        return outputs, move_direction

    def edit_connection(self, from_neuron, to_neuron, new_weight):
        # Edit the weight of the connection between two neurons
        layer = 'input' if from_neuron in self.neurons['input'] else 'hidden'
        if from_neuron in self.neurons[layer] and to_neuron in self.neurons[layer]['connections']:
            self.neurons[layer][from_neuron].connections[to_neuron] = new_weight
            self.save_neuron(self.neurons[layer][from_neuron])
            return True
        return False

    def add_neuron(self, name, layer):
        # Add a new neuron to the brain
        if layer in ['input', 'hidden', 'output'] and name not in self.neurons[layer]:
            self.neurons[layer][name] = Neuron(name, layer)
            self.save_neuron(self.neurons[layer][name])
            return True
        return False

    def remove_neuron(self, name, layer):
        # Remove a neuron from the brain
        if layer in ['input', 'hidden', 'output'] and name in self.neurons[layer]:
            del self.neurons[layer][name]
            file_path = os.path.join(self.brain_folder, f"{name}.json")
            if os.path.exists(file_path):
                os.remove(file_path)
            return True
        return False
