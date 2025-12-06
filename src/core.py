# NeuralNetwork/core.py
import random
import time
import json
import math

class Config:
    """Holds configuration for the network, learning, and neurogenesis."""
    def __init__(self):
        self.hebbian = {
            'base_learning_rate': 0.1,
            'active_threshold': 50,
            'learning_interval': 30000,
            'weight_decay': 0.01,
        }
        self.neurogenesis = {
            'enabled_globally': True,
            'novelty_threshold': 3.0,
            'stress_threshold': 1.2,
            'reward_threshold': 0.6,
            'cooldown': 180,
            'max_neurons': 32,
            'appearance': {
                'colors': {
                    'default': (200, 200, 200),
                    'input': (150, 220, 150),
                    'hidden': (150, 150, 220),
                    'output': (220, 150, 150),
                    'novelty': (255, 255, 150),
                    'stress': (255, 150, 150),
                    'reward': (173, 216, 230),
                },
                'shapes': {
                    'default': 'circle',
                    'input': 'square',
                    'hidden': 'circle',
                    'output': 'diamond',
                    'novelty': 'diamond',
                    'stress': 'square',
                    'reward': 'triangle',
                }
            }
        }

class Neuron:
    """Represents a single neuron in the network."""
    def __init__(self, name, n_type='default', position=(0,0), attributes=None):
        self.name = name
        self.type = n_type
        self.position = position
        self.attributes = attributes or {}

    def get_position(self):
        return self.position

    def set_position(self, x, y):
        self.position = (x, y)

class Connection:
    """Represents a connection between two neurons."""
    def __init__(self, source_name, target_name, weight=0.0):
        self.source = source_name
        self.target = target_name
        self.weight = weight

    def get_weight(self):
        return self.weight

    def set_weight(self, new_weight):
        self.weight = max(-1.0, min(1.0, new_weight))

class Network:
    """Manages all neurons, connections, and network-level operations."""
    def __init__(self):
        self.neurons = {}
        self.connections = {}
        self.state = {}
        self.config = Config()
        self.last_hebbian_time = 0
        self.neurogenesis_enabled = True
        self.neurogenesis_data = {
            'novelty_counter': 0, 'stress_counter': 0, 'reward_counter': 0,
            'last_neuron_time': 0, 'new_neurons_details': {}
        }

    def add_neuron(self, name, value, position, n_type='default', attributes=None):
        if name not in self.neurons:
            self.neurons[name] = Neuron(name, n_type, position, attributes)
            self.state[name] = value
            return True
        return False

    def connect(self, source, target, weight):
        if source in self.neurons and target in self.neurons:
            self.connections[(source, target)] = Connection(source, target, weight)
            return True
        return False

    def perform_learning(self):
        if time.time() - self.last_hebbian_time < (self.config.hebbian['learning_interval'] / 1000.0):
            return None

        self.last_hebbian_time = time.time()
        active_neurons = [n for n, v in self.state.items() if v > self.config.hebbian['active_threshold']]
        updated_pairs = set()

        if len(active_neurons) < 2:
            return []

        for i in range(len(active_neurons)):
            for j in range(i + 1, len(active_neurons)):
                n1, n2 = active_neurons[i], active_neurons[j]
                v1, v2 = self.state[n1], self.state[n2]
                lr = self.config.hebbian['base_learning_rate']
                
                # Strengthen connection (or create if non-existent)
                key = tuple(sorted((n1, n2)))
                if key not in self.connections:
                    self.connect(key[0], key[1], 0)
                
                # Apply Hebbian rule
                weight_change = lr * (v1 / 100.0) * (v2 / 100.0)
                conn = self.connections.get(key) or self.connections.get(key[::-1])
                if conn:
                    new_weight = conn.get_weight() + weight_change
                    conn.set_weight(new_weight)
                    updated_pairs.add(key)
        
        # Apply weight decay
        decay = self.config.hebbian['weight_decay']
        for conn in self.connections.values():
            conn.set_weight(conn.get_weight() * (1.0 - decay))
            
        return list(updated_pairs)

    def propagate_activation(self):
        next_state = self.state.copy()
        for target_name, target_neuron in self.neurons.items():
            incoming_activation = 0
            for (source_name, t_name), conn in self.connections.items():
                if t_name == target_name:
                    incoming_activation += self.state.get(source_name, 0) * conn.get_weight()
            
            # Simple activation function (e.g., tanh) scaled to 0-100
            activation = math.tanh(incoming_activation / 100.0) # Scale input
            next_state[target_name] = (activation + 1) * 50 # Map from [-1, 1] to [0, 100]

        self.state = next_state

    def check_neurogenesis(self, sim_state):
        if not self.neurogenesis_enabled or time.time() - self.neurogenesis_data['last_neuron_time'] < self.config.neurogenesis['cooldown']:
            return None
            
        # Update counters from simulated state
        self.neurogenesis_data['novelty_counter'] += sim_state.get('SIM_novelty_exposure', 0)
        self.neurogenesis_data['stress_counter'] += sim_state.get('SIM_sustained_stress', 0)
        
        # Check triggers
        triggers = {
            'novelty': self.neurogenesis_data['novelty_counter'] > self.config.neurogenesis['novelty_threshold'],
            'stress': self.neurogenesis_data['stress_counter'] > self.config.neurogenesis['stress_threshold']
        }
        
        for n_type, is_triggered in triggers.items():
            if is_triggered:
                new_neuron_name = self._create_neuron_internal(n_type, sim_state)
                if new_neuron_name:
                    self.neurogenesis_data['last_neuron_time'] = time.time()
                    self.neurogenesis_data[f'{n_type}_counter'] = 0 # Reset counter
                    return new_neuron_name
        return None

    def _create_neuron_internal(self, n_type, creation_context_state):
        # Find a suitable position (e.g., near center)
        x_vals = [n.get_position()[0] for n in self.neurons.values()]
        y_vals = [n.get_position()[1] for n in self.neurons.values()]
        center_x = sum(x_vals) / len(x_vals) if x_vals else 300
        center_y = sum(y_vals) / len(y_vals) if y_vals else 300
        new_pos = (center_x + random.uniform(-80, 80), center_y + random.uniform(-80, 80))

        # Create a unique name
        base_name = f"{n_type}_N"
        idx = 0
        while f"{base_name}{idx}" in self.neurons:
            idx += 1
        new_name = f"{base_name}{idx}"
        
        attrs = {
            'shape': self.config.neurogenesis['appearance']['shapes'].get(n_type, 'circle'),
            'color': self.config.neurogenesis['appearance']['colors'].get(n_type, (200,200,200))
        }

        self.add_neuron(new_name, 50.0, new_pos, n_type, attrs)
        self.neurogenesis_data['new_neurons_details'][new_name] = {
            'created_at': time.time(),
            'trigger_type': n_type,
            'associated_state_snapshot': {k:v for k,v in creation_context_state.items() if k.startswith("SIM_")}
        }
        return new_name

    def set_neurogenesis_enabled(self, enabled):
        self.neurogenesis_enabled = enabled

    def save(self, filepath):
        data = {
            'neurons': {name: {'type': n.type, 'position': n.position, 'attributes': n.attributes} for name, n in self.neurons.items()},
            'connections': {f"{s}->{t}": c.get_weight() for (s, t), c in self.connections.items()},
            'state': self.state,
            'config': {
                'hebbian': self.config.hebbian,
                'neurogenesis': self.config.neurogenesis,
            }
        }
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving network: {e}")
            return False

    @staticmethod
    def load(filepath):
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            net = Network()
            # Load config first
            if 'config' in data:
                net.config.hebbian.update(data['config'].get('hebbian', {}))
                net.config.neurogenesis.update(data['config'].get('neurogenesis', {}))
            
            # Load neurons
            for name, n_data in data['neurons'].items():
                net.add_neuron(name, 0, n_data['position'], n_data['type'], n_data.get('attributes'))
            
            # Load connections
            for key, weight in data['connections'].items():
                source, target = key.split('->')
                net.connect(source, target, weight)
            
            # Load state
            net.state = data.get('state', {n: 50.0 for n in net.neurons})

            return net
        except Exception as e:
            print(f"Error loading network: {e}")
            return None