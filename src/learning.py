import random
from PyQt5 import QtCore
import csv
import time
import json
from datetime import datetime
from .personality import Personality

class HebbianLearning:
    def __init__(self, squid, brain_window, config=None):
        self.squid = squid
        self.brain_window = brain_window
        self.config = config if config else LearningConfig()

        
        # Learning data and tracking
        self.squid_personality = squid.personality if squid else None
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

        # Learning event logging
        self.learning_event_log = []
        self.learning_log_file = 'learning_events.json'

        # Network state history
        self.network_state_history = []
        self.max_history_length = 100

        # Personality-specific learning modifiers
        self.personality_learning_modifiers = {
            Personality.TIMID: {
                'learning_rate_reduction': 0.5,
                'novelty_sensitivity': 0.3,
                'connection_stability': 0.8
            },
            Personality.ADVENTUROUS: {
                'learning_rate_boost': 1.5,
                'novelty_sensitivity': 1.2,
                'connection_plasticity': 1.2
            },
            Personality.GREEDY: {
                'reward_learning_boost': 1.3,
                'exploration_penalty': 0.7,
                'connection_prioritization': ['satisfaction', 'hunger']
            },
            Personality.STUBBORN: {
                'unlearning_resistance': 0.9,
                'new_connection_threshold': 0.6,
                'preference_reinforcement': 1.2
            }
        }

    def get_learning_data(self):
        return self.learning_data
    
    def export_learning_data(self, file_name):
        with open(file_name, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Timestamp", "Neuron 1", "Neuron 2", "Weight Change", "Goal Type"])
            writer.writerows(self.learning_data)

    def learn_from_eating(self):
        """
        Modify eating-related learning based on personality
        """
        # Base learning connections
        self.strengthen_connection('hunger', 'satisfaction', self.learning_rate * 2.0)
        self.strengthen_connection('hunger', 'happiness', self.learning_rate * 1.5)
        
        # Personality-specific modifications
        personality = self.squid_personality or Personality.ADVENTUROUS
        
        if personality == Personality.GREEDY:
            # Greedy squids form stronger connections related to food and satisfaction
            self.strengthen_connection('hunger', 'satisfaction', self.learning_rate * 3.0)
            self.strengthen_connection('satisfaction', 'happiness', self.learning_rate * 2.0)
        
        elif personality == Personality.STUBBORN:
            # Stubborn squids only strengthen connections for favorite food (sushi)
            if getattr(self.squid, 'last_food_type', None) == 'sushi':
                self.strengthen_connection('hunger', 'satisfaction', self.learning_rate * 2.5)
        
        elif personality == Personality.TIMID:
            # Timid squids form weaker, more cautious connections
            self.strengthen_connection('hunger', 'satisfaction', self.learning_rate * 1.5)
            self.strengthen_connection('hunger', 'anxiety', self.learning_rate * 0.5)
        
        elif personality == Personality.ADVENTUROUS:
            # Adventurous squids form more varied and dynamic connections
            self.strengthen_connection('hunger', 'curiosity', self.learning_rate * 1.8)
            self.strengthen_connection('satisfaction', 'happiness', self.learning_rate * 2.0)

    def learn_from_decoration_interaction(self, decoration_category):
        """
        Modify decoration interaction learning based on personality
        """
        # Base learning connections
        if decoration_category == 'plant':
            self.strengthen_connection('curiosity', 'cleanliness', self.learning_rate)
        elif decoration_category == 'rock':
            self.strengthen_connection('curiosity', 'satisfaction', self.learning_rate * 1.5)
            self.strengthen_connection('curiosity', 'happiness', self.learning_rate)
        
        # Personality-specific modifications
        personality = self.squid_personality or Personality.ADVENTUROUS
        
        if personality == Personality.ADVENTUROUS:
            # Adventurous squids learn more from new decorations
            if decoration_category == 'rock':
                self.strengthen_connection('curiosity', 'satisfaction', self.learning_rate * 2.5)
                self.strengthen_connection('curiosity', 'happiness', self.learning_rate * 2.0)
        
        elif personality == Personality.TIMID:
            # Timid squids are more cautious about new decorations
            if decoration_category == 'rock':
                self.strengthen_connection('curiosity', 'anxiety', self.learning_rate * 0.5)
        
        elif personality == Personality.GREEDY:
            # Greedy squids focus on decorations that might provide rewards
            if decoration_category == 'rock':
                self.strengthen_connection('satisfaction', 'happiness', self.learning_rate * 2.0)
        
        elif personality == Personality.STUBBORN:
            # Stubborn squids resist learning from new decorations
            if decoration_category == 'rock':
                self.strengthen_connection('curiosity', 'satisfaction', self.learning_rate * 0.5)

    def learn_from_organization(self):
        """
        Modify organization-related learning based on personality
        """
        # Base learning connections
        self.strengthen_connection('curiosity', 'satisfaction', self.learning_rate * 2)
        self.strengthen_connection('cleanliness', 'satisfaction', self.learning_rate)
        
        # Personality-specific modifications
        personality = self.squid_personality or Personality.ADVENTUROUS
        
        if personality == Personality.ADVENTUROUS:
            # Adventurous squids learn more from organizing
            self.strengthen_connection('curiosity', 'happiness', self.learning_rate * 2.5)
        
        elif personality == Personality.TIMID:
            # Timid squids have a more cautious approach to organization
            self.strengthen_connection('curiosity', 'anxiety', self.learning_rate * 0.5)
        
        elif personality == Personality.GREEDY:
            # Greedy squids organize for potential rewards
            self.strengthen_connection('satisfaction', 'happiness', self.learning_rate * 2.0)
        
        elif personality == Personality.STUBBORN:
            # Stubborn squids resist changing their environment
            self.strengthen_connection('curiosity', 'satisfaction', self.learning_rate * 0.5)

    def learn_from_sickness(self):
        """
        Modify sickness-related learning based on personality
        """
        # Base learning connections
        self.strengthen_connection('is_sick', 'cleanliness', self.learning_rate)
        self.strengthen_connection('is_sick', 'anxiety', self.learning_rate)
        
        # Personality-specific modifications
        personality = self.squid_personality or Personality.ADVENTUROUS
        
        if personality == Personality.TIMID:
            # Timid squids become more anxious when sick
            self.strengthen_connection('is_sick', 'anxiety', self.learning_rate * 2.0)
        
        elif personality == Personality.ADVENTUROUS:
            # Adventurous squids learn to overcome sickness
            self.strengthen_connection('is_sick', 'happiness', self.learning_rate * 1.5)
        
        elif personality == Personality.GREEDY:
            # Greedy squids focus on recovering quickly
            self.strengthen_connection('is_sick', 'satisfaction', self.learning_rate * 1.8)
        
        elif personality == Personality.STUBBORN:
            # Stubborn squids resist the impact of sickness
            self.strengthen_connection('is_sick', 'anxiety', self.learning_rate * 0.5)

    def update_personality(self, new_personality):
        """
        Update the personality dynamically during learning
        
        Args:
            new_personality (Personality): New personality type
        """
        self.squid_personality = new_personality
        
        # Optional: Log personality change
        self.log_learning_event({
            'event_type': 'personality_change',
            'old_personality': self.squid_personality,
            'new_personality': new_personality
        })

    def learn_from_curiosity(self):
        """
        Modify curiosity-related learning based on personality
        """
        # Base learning connections
        self.strengthen_connection('curiosity', 'happiness', self.learning_rate)
        self.strengthen_connection('curiosity', 'satisfaction', self.learning_rate)
        
        # Personality-specific modifications
        personality = self.squid_personality or Personality.ADVENTUROUS
        
        if personality == Personality.ADVENTUROUS:
            # Adventurous squids learn more from curiosity
            self.strengthen_connection('curiosity', 'happiness', self.learning_rate * 2.5)
            self.strengthen_connection('curiosity', 'satisfaction', self.learning_rate * 2.0)
        
        elif personality == Personality.TIMID:
            # Timid squids have a more reserved curiosity
            self.strengthen_connection('curiosity', 'anxiety', self.learning_rate * 0.5)
        
        elif personality == Personality.GREEDY:
            # Greedy squids are curious about potential rewards
            self.strengthen_connection('curiosity', 'satisfaction', self.learning_rate * 2.0)
        
        elif personality == Personality.STUBBORN:
            # Stubborn squids resist learning from curiosity
            self.strengthen_connection('curiosity', 'satisfaction', self.learning_rate * 0.5)

    def learn_from_anxiety(self):
        """
        Modify anxiety-related learning based on personality
        """
        # Base learning connections
        self.strengthen_connection('anxiety', 'is_sick', self.learning_rate)
        self.strengthen_connection('anxiety', 'cleanliness', self.learning_rate)
        
        # Personality-specific modifications
        personality = self.squid_personality or Personality.ADVENTUROUS
        
        if personality == Personality.TIMID:
            # Timid squids are more affected by anxiety
            self.strengthen_connection('anxiety', 'is_sick', self.learning_rate * 2.0)
            self.strengthen_connection('anxiety', 'happiness', self.learning_rate * 0.5)
        
        elif personality == Personality.ADVENTUROUS:
            # Adventurous squids learn to overcome anxiety
            self.strengthen_connection('anxiety', 'happiness', self.learning_rate * 1.5)
        
        elif personality == Personality.GREEDY:
            # Greedy squids link anxiety to potential loss
            self.strengthen_connection('anxiety', 'satisfaction', self.learning_rate * 1.8)
        
        elif personality == Personality.STUBBORN:
            # Stubborn squids resist the impact of anxiety
            self.strengthen_connection('anxiety', 'is_sick', self.learning_rate * 0.5)

    def strengthen_connection(self, neuron1, neuron2, base_learning_rate):
        """Enhanced version that considers neurogenesis state and goal weights"""
        # Skip if either neuron is in the excluded list
        if neuron1 in self.excluded_neurons or neuron2 in self.excluded_neurons:
            return
        
        # Determine personality (with a default)
        personality = self.squid_personality or Personality.ADVENTUROUS
        
        # Apply personality modifiers
        learning_rate = self.apply_personality_learning_modifiers(neuron1, neuron2, base_learning_rate)
        
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
            
            # Prepare learning event details
            learning_event = {
                'neuron1': neuron1,
                'neuron2': neuron2,
                'learning_rate': learning_rate,
                'weight_change': new_weight - prev_weight,
                'previous_weight': prev_weight,
                'new_weight': new_weight,
                'personality': personality.value,
                'is_goal_oriented': is_goal,
                'neurogenesis_active': self.neurogenesis_active,
                'explanation': self.generate_learning_explanation(neuron1, neuron2, learning_rate)
            }
            
            # Log the learning event
            self.log_learning_event(learning_event)
            
            # Periodically capture network state
            if len(self.learning_event_log) % 10 == 0:
                self.capture_network_state()

    def apply_personality_learning_modifiers(self, neuron1, neuron2, learning_rate):
        """
        Apply personality-specific modifiers to learning process
        """
        personality = self.squid_personality or Personality.ADVENTUROUS
        modifiers = self.personality_learning_modifiers.get(personality, {})
        
        # Base learning rate modification
        if personality == Personality.TIMID:
            learning_rate *= modifiers.get('learning_rate_reduction', 1.0)
        elif personality == Personality.ADVENTUROUS:
            learning_rate *= modifiers.get('learning_rate_boost', 1.0)
        
        # Connection prioritization for greedy personality
        if personality == Personality.GREEDY:
            priority_neurons = modifiers.get('connection_prioritization', [])
            if any(n in priority_neurons for n in [neuron1, neuron2]):
                learning_rate *= 1.3
        
        # Stubborn personality resistance to change
        if personality == Personality.STUBBORN:
            learning_rate *= modifiers.get('unlearning_resistance', 1.0)
        
        return learning_rate
    
    def generate_learning_explanation(self, neuron1, neuron2, learning_rate):
        """
        Generate a human-readable explanation of learning process
        """
        personality = self.squid_personality or Personality.ADVENTUROUS
        explanations = {
            Personality.TIMID: f"Cautiously adjusting connection between {neuron1} and {neuron2}",
            Personality.ADVENTUROUS: f"Rapidly strengthening connection between {neuron1} and {neuron2}",
            Personality.GREEDY: f"Prioritizing connection between {neuron1} and {neuron2} for potential reward",
            Personality.STUBBORN: f"Maintaining existing connection pattern between {neuron1} and {neuron2}"
        }
        
        return explanations.get(personality, "Neutral learning process")

    def log_learning_event(self, event_details):
        """
        Log a detailed learning event with comprehensive details
        
        Args:
            event_details (dict): Dictionary containing learning event information
        """
        try:
            # Ensure timestamp is added
            event_details['timestamp'] = datetime.now().isoformat()
            
            # Add context information if not present
            if 'personality' not in event_details and self.squid_personality:
                event_details['personality'] = self.squid_personality.value
            
            # Validate and sanitize event details
            sanitized_event = {
                k: v for k, v in event_details.items() 
                if v is not None and v != ''
            }
            
            # Add to in-memory log
            self.learning_event_log.append(sanitized_event)
            
            # Optionally save to file (every 10 events or based on a condition)
            if len(self.learning_event_log) % 10 == 0:
                self.save_learning_log()
            
            # Optional: print event for debugging (can be removed in production)
            if self.debug_mode:
                print(f"Learning Event: {sanitized_event}")
            
        except Exception as e:
            print(f"Error logging learning event: {e}")
            # Optionally log to a separate error log
    
    def save_learning_log(self):
        """Save learning events to a JSON file"""
        try:
            with open(self.learning_log_file, 'w') as f:
                json.dump(self.learning_event_log, f, indent=2)
        except Exception as e:
            print(f"Error saving learning log: {e}")
    
    def export_learning_log(self, filename=None):
        """
        Export learning log to CSV or specified format
        """
        if not filename:
            filename = f"learning_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        try:
            with open(filename, 'w', newline='') as csvfile:
                # Determine fieldnames dynamically based on first event
                if self.learning_event_log:
                    fieldnames = list(self.learning_event_log[0].keys())
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    
                    writer.writeheader()
                    for event in self.learning_event_log:
                        writer.writerow(event)
            
            print(f"Learning log exported to {filename}")
        except Exception as e:
            print(f"Error exporting learning log: {e}")

    def capture_network_state(self):
        """
        Capture the current state of the neural network
        """
        current_state = {
            'timestamp': datetime.now().isoformat(),
            'neurons': list(self.brain_window.brain_widget.neuron_positions.keys()),
            'weights': {str(k): v for k, v in self.brain_window.brain_widget.weights.items()},
            'neuron_positions': {
                str(name): list(pos) 
                for name, pos in self.brain_window.brain_widget.neuron_positions.items()
            },
            'personality': self.squid.personality.value,
            'learning_rate': self.learning_rate
        }
        
        # Add to history
        self.network_state_history.append(current_state)
        
        # Trim history if it exceeds max length
        if len(self.network_state_history) > self.max_history_length:
            self.network_state_history.pop(0)
        
        return current_state
    
    def analyze_network_evolution(self):
        """
        Analyze how the network has evolved over time
        """
        if len(self.network_state_history) < 2:
            return {"error": "Not enough history to analyze"}
        
        analysis = {
            'total_neurons_added': 0,
            'total_weight_changes': 0,
            'personality_impact': {},
            'learning_rate_trend': []
        }
        
        # Analyze changes between consecutive states
        for i in range(1, len(self.network_state_history)):
            prev_state = self.network_state_history[i-1]
            current_state = self.network_state_history[i]
            
            # Count new neurons
            new_neurons = set(current_state['neurons']) - set(prev_state['neurons'])
            analysis['total_neurons_added'] += len(new_neurons)
            
            # Track weight changes
            weight_changes = 0
            for (k, v) in current_state['weights'].items():
                if k in prev_state['weights']:
                    if abs(v - prev_state['weights'][k]) > 0.01:
                        weight_changes += 1
            
            analysis['total_weight_changes'] += weight_changes
            
            # Personality impact tracking
            personality = current_state['personality']
            analysis['personality_impact'][personality] = analysis['personality_impact'].get(personality, 0) + 1
            
            # Learning rate trend
            analysis['learning_rate_trend'].append(current_state['learning_rate'])
        
        return analysis
    
    def export_network_evolution(self, filename=None):
        """
        Export network evolution history
        """
        if not filename:
            filename = f"network_evolution_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            with open(filename, 'w') as f:
                json.dump(self.network_state_history, f, indent=2)
            
            print(f"Network evolution history exported to {filename}")
        except Exception as e:
            print(f"Error exporting network evolution: {e}")

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
            'cooldown': 200,  # Changed from 300 to 200 seconds
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