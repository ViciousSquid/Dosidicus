import random
from PyQt5 import QtCore
import csv
import time
import json

class HebbianLearning:
    def __init__(self, squid, brain_window, config=None):
        self.squid = squid
        self.brain_window = brain_window
        self.config = config if config else LearningConfig()
        self.learning_data = []
        self.threshold = 0.7
        self.goal_weights = {
            'organize_decorations': 0.5,
            'interact_with_rocks': 0.7,
            'move_to_plants': 0.4
        }

        self.excluded_neurons = ['is_sick', 'is_eating', 'is_sleeping', 'pursuing_food', 'direction']

        self.learning_rate = self.config.hebbian['base_learning_rate']
        self.threshold = self.config.hebbian['threshold']
        self.goal_weights = self.config.hebbian['goal_weights']
        
        # Neurogenesis tracking
        self.last_neurogenesis_time = time.time()
        self.neurogenesis_active = False


    def get_learning_data(self):
        return self.learning_data
    
    def export_learning_data(self, file_name):
        with open(file_name, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Timestamp", "Neuron 1", "Neuron 2", "Weight Change", "Goal Type"])
            writer.writerows(self.learning_data)

    def learn_from_eating(self):
        # Strong reward connections (2x boost for food)
        self.strengthen_connection('hunger', 'satisfaction', self.learning_rate * 2.0)
        self.strengthen_connection('hunger', 'happiness', self.learning_rate * 1.5)
        
        # Strengthen general reward pathways
        self.strengthen_connection('satisfaction', 'happiness', self.learning_rate * 0.8)
        
        # Log as a significant event
        self.learning_data.append((
            QtCore.QTime.currentTime().toString("hh:mm:ss"),
            'hunger', 'satisfaction',
            self.learning_rate * 2.0,
            "FOOD_REWARD",
            "NORMAL"
        ))

    def learn_from_decoration_interaction(self, decoration_category):
        if decoration_category == 'plant':
            self.strengthen_connection('curiosity', 'cleanliness', self.learning_rate)
        elif decoration_category == 'rock':
            self.strengthen_connection('curiosity', 'satisfaction', self.learning_rate * 1.5)
            self.strengthen_connection('curiosity', 'happiness', self.learning_rate)
            self.strengthen_connection('satisfaction', 'happiness', self.learning_rate * 0.5)

    def learn_from_organization(self):
        self.strengthen_connection('curiosity', 'satisfaction', self.learning_rate * 2)
        self.strengthen_connection('cleanliness', 'satisfaction', self.learning_rate)

    def learn_from_sickness(self):
        self.strengthen_connection('is_sick', 'cleanliness', self.learning_rate)
        self.strengthen_connection('is_sick', 'anxiety', self.learning_rate)

    def learn_from_curiosity(self):
        self.strengthen_connection('curiosity', 'happiness', self.learning_rate)
        self.strengthen_connection('curiosity', 'satisfaction', self.learning_rate)

    def learn_from_anxiety(self):
        self.strengthen_connection('anxiety', 'is_sick', self.learning_rate)
        self.strengthen_connection('anxiety', 'cleanliness', self.learning_rate)

    def strengthen_connection(self, neuron1, neuron2, learning_rate):
        """Enhanced version that considers neurogenesis state and goal weights"""
        # Skip if either neuron is in the excluded list
        if neuron1 in self.excluded_neurons or neuron2 in self.excluded_neurons:
            return
            
        if getattr(self.squid, neuron1) > self.threshold and getattr(self.squid, neuron2) > self.threshold:
            # Check if this is a goal-oriented connection
            is_goal = (neuron1, neuron2) in self.goal_weights or (neuron2, neuron1) in self.goal_weights
            
            # Calculate weight change
            if is_goal:
                base_change = learning_rate * self.config.combined['goal_reinforcement_factor']
            else:
                base_change = learning_rate
            
            if self.neurogenesis_active:
                base_change *= self.config.combined['neurogenesis_learning_boost']
            
            # Apply weight change
            pair = (neuron1, neuron2)
            reverse_pair = (neuron2, neuron1)
            
            prev_weight = self.brain_window.brain_widget.weights.get(pair, 0)
            new_weight = prev_weight + base_change
            
            # Apply weight bounds
            new_weight = max(self.config.hebbian['min_weight'], 
                            min(self.config.hebbian['max_weight'], new_weight))
            
            self.brain_window.brain_widget.weights[pair] = new_weight
            self.brain_window.brain_widget.weights[reverse_pair] = new_weight
            
            # Log the change
            timestamp = QtCore.QTime.currentTime().toString("hh:mm:ss")
            change_text = f"{timestamp} - Weight changed between {neuron1.upper()} and {neuron2.upper()}\n"
            change_text += f"Previous value: <font color='red'>{prev_weight:.4f}</font>\n"
            change_text += f"New value: <font color='green'>{new_weight:.4f}</font>\n\n"
            self.brain_window.weight_changes_text.append(change_text)
            
            self.learning_data.append((
                timestamp, neuron1, neuron2, 
                new_weight - prev_weight, 
                "GOAL" if is_goal else "BASIC",
                "NEUROGENESIS" if self.neurogenesis_active else "NORMAL"
            ))
            
            if self.brain_window.log_window and self.brain_window.log_window.isVisible():
                self.brain_window.log_window.update_log(change_text)

    def update_learning_rate(self, novelty_factor):
        """Update learning rate based on novelty and neurogenesis state"""
        base_rate = self.config.hebbian['base_learning_rate']
        if self.neurogenesis_active:
            self.learning_rate = base_rate * novelty_factor * self.config.combined['neurogenesis_learning_boost']
        else:
            self.learning_rate = base_rate * novelty_factor
            
        # Update goal weights with the same factor
        for goal in self.goal_weights:
            self.goal_weights[goal] = min(1.0, self.config.hebbian['goal_weights'][goal] * novelty_factor)
    

    def update_weights(self):
        # Apply goal-oriented reinforcement
        if self.squid.status == "organizing decorations":
            self.learn_from_organization()
        elif self.squid.status == "interacting with rocks":
            self.learn_from_decoration_interaction('rock')
        elif self.squid.status == "moving to plant":
            self.learn_from_decoration_interaction('plant')


    def check_neurogenesis_conditions(self, brain_state):
        """Check if conditions for neurogenesis are met"""
        current_time = time.time()
        
        # Check cooldown first
        if current_time - self.last_neurogenesis_time < self.config.neurogenesis['cooldown']:
            return False
            
        # Check triggers
        triggers = {
            'novelty': brain_state.get('novelty_exposure', 0) > self.config.neurogenesis['novelty_threshold'],
            'stress': brain_state.get('sustained_stress', 0) > self.config.neurogenesis['stress_threshold'],
            'reward': brain_state.get('recent_rewards', 0) > self.config.neurogenesis['reward_threshold']
        }
        
        return any(triggers.values())
    

    def create_new_neuron(self, neuron_type, trigger_data):
        """Create a new neuron and connect it to existing ones"""
        base_name = {
            'novelty': 'novel',
            'stress': 'defense',
            'reward': 'reward'
        }.get(neuron_type, 'new')
        
        new_name = f"{base_name}_{len(self.brain_window.brain_widget.neurogenesis_data['new_neurons'])}"
        
        # Add to brain widget
        self.brain_window.brain_widget.create_neuron(neuron_type, trigger_data)
        
        # Initialize connections with existing neurons
        for existing_neuron in self.brain_window.brain_widget.neuron_positions:
            if existing_neuron != new_name:
                # Stronger initial connection if related
                if (neuron_type == 'novelty' and existing_neuron == 'curiosity') or \
                   (neuron_type == 'stress' and existing_neuron == 'anxiety') or \
                   (neuron_type == 'reward' and existing_neuron == 'satisfaction'):
                    weight = self.config.combined['new_neuron_connection_strength'] * 1.5
                else:
                    weight = self.config.combined['new_neuron_connection_strength']
                
                self.brain_window.brain_widget.weights[(new_name, existing_neuron)] = weight
                self.brain_window.brain_widget.weights[(existing_neuron, new_name)] = weight * 0.5
        
        # Activate neurogenesis boost
        self.neurogenesis_active = True
        self.last_neurogenesis_time = time.time()
        QtCore.QTimer.singleShot(10000, self.end_neurogenesis_boost)  # 10 second boost
        
        return new_name
    
    def end_neurogenesis_boost(self):
        self.neurogenesis_active = False


class LearningConfig:
    def __init__(self):
        # Hebbian learning parameters
        self.hebbian = {
            'base_learning_rate': 0.1,
            'threshold': 0.7,
            'weight_decay': 0.01,  # Small decay to prevent weights from growing too large
            'max_weight': 1.0,
            'min_weight': -1.0,
            'learning_interval': 30000,
            'goal_weights': {
                'organize_decorations': 0.5,
                'interact_with_rocks': 0.7,
                'move_to_plants': 0.4
            }
        }
        
        # Neurogenesis parameters
        self.neurogenesis = {
            'novelty_threshold': 3,
            'stress_threshold': 0.7,
            'reward_threshold': 0.6,
            'cooldown': 300,  # 5 minutes in seconds
            'new_neuron_initial_weight': 0.5,
            'max_new_neurons': 5,
            'decay_rate': 0.95  # How quickly novelty/stress/reward counters decay
        }
        
        # Combined learning parameters
        self.combined = {
            'neurogenesis_learning_boost': 1.1,  # Multiplier for learning rate after neurogenesis
            'new_neuron_connection_strength': 0.3,
            'goal_reinforcement_factor': 2.0  # How much stronger goal-oriented learning is
        }
    
    def load_from_file(self, file_path):
        try:
            with open(file_path, 'r') as f:
                config = json.load(f)
                self.hebbian.update(config.get('hebbian', {}))
                self.neurogenesis.update(config.get('neurogenesis', {}))
                self.combined.update(config.get('combined', {}))
        except FileNotFoundError:
            print(f"Config file {file_path} not found, using defaults")
        except json.JSONDecodeError:
            print(f"Invalid config file {file_path}, using defaults")