import configparser
import os
import random
from PyQt5 import QtCore
from ast import literal_eval

class ConfigManager:
    def __init__(self, config_path="config.ini"):
        self.config_path = config_path
        self.config = configparser.ConfigParser()
        self.load_config()

    def load_config(self):
        if not os.path.exists(self.config_path):
            self.create_default_config()
        self.config.read(self.config_path)

    def create_default_config(self):
        # Rock Interactions
        self.config['RockInteractions'] = {
            'pickup_probability': '0.9',
            'throw_probability': '0.8',
            'min_carry_duration': '3.0',
            'max_carry_duration': '8.0',
            'cooldown_after_throw': '5.0',
            'happiness_boost': '15',
            'satisfaction_boost': '20',
            'anxiety_reduction': '10',
            'memory_decay_rate': '0.95',
            'max_rock_memories': '5'
        }

        # Neurogenesis
        self.config['Neurogenesis'] = {
            'enabled': 'True',
            'cooldown': '300.0',
            'max_neurons': '20',
            'initial_neuron_count': '7'
        }

        # Neurogenesis Triggers
        self.config['Neurogenesis.Novelty'] = {
            'enabled': 'True',
            'threshold': '0.7',
            'decay_rate': '0.95',
            'max_counter': '10.0',
            'min_curiosity': '0.3',
            'adventurous_modifier': '1.2',
            'timid_modifier': '0.8'
        }

        self.config['Neurogenesis.Stress'] = {
            'enabled': 'True',
            'threshold': '0.8',
            'decay_rate': '0.9',
            'max_counter': '10.0',
            'min_anxiety': '0.4',
            'timid_modifier': '1.5',
            'energetic_modifier': '0.7'
        }

        self.config['Neurogenesis.Reward'] = {
            'enabled': 'True',
            'threshold': '0.6',
            'decay_rate': '0.85',
            'max_counter': '10.0',
            'min_satisfaction': '0.5',
            'boost_multiplier': '1.1'
        }

        # Neuron Properties
        self.config['Neurogenesis.NeuronProperties'] = {
            'base_activation': '0.5',
            'position_variance': '50',
            'default_connections': 'True',
            'connection_strength': '0.3',
            'reciprocal_strength': '0.15'
        }

        # Appearance
        self.config['Neurogenesis.Appearance'] = {
            'novelty_color': '255,255,150',
            'stress_color': '255,150,150',
            'reward_color': '150,255,150',
            'novelty_shape': 'triangle',
            'stress_shape': 'square',
            'reward_shape': 'circle'
        }

        # Visual Effects
        self.config['Neurogenesis.VisualEffects'] = {
            'highlight_duration': '5.0',
            'highlight_radius': '40',
            'pulse_effect': 'True',
            'pulse_speed': '0.5'
        }

        with open(self.config_path, 'w') as f:
            self.config.write(f)

    def get_rock_config(self):
        return {
            'pickup_prob': float(self.config['RockInteractions']['pickup_probability']),
            'throw_prob': float(self.config['RockInteractions']['throw_probability']),
            'min_carry_duration': float(self.config['RockInteractions']['min_carry_duration']),
            'max_carry_duration': float(self.config['RockInteractions']['max_carry_duration']),
            'cooldown_after_throw': float(self.config['RockInteractions']['cooldown_after_throw']),
            'happiness_boost': int(self.config['RockInteractions']['happiness_boost']),
            'satisfaction_boost': int(self.config['RockInteractions']['satisfaction_boost']),
            'anxiety_reduction': int(self.config['RockInteractions']['anxiety_reduction']),
            'memory_decay_rate': float(self.config['RockInteractions']['memory_decay_rate']),
            'max_rock_memories': int(self.config['RockInteractions']['max_rock_memories'])
        }
    
    def get_poop_config(self):
        return {
            'min_carry_duration': 2.0,
            'max_carry_duration': 9.0,
            'pickup_prob': 0.2,
            'throw_prob': 0.3,
            'happiness_penalty': 5,
            'anxiety_increase': 10
        }

    def get_neurogenesis_config(self):
        """Returns the complete neurogenesis configuration as a dictionary"""
        return {
            'general': {
                'enabled': self.config.getboolean('Neurogenesis', 'enabled'),
                'cooldown': self.config.getfloat('Neurogenesis', 'cooldown'),
                'max_neurons': self.config.getint('Neurogenesis', 'max_neurons'),
                'initial_neuron_count': self.config.getint('Neurogenesis', 'initial_neuron_count')
            },
            'triggers': {
                'novelty': {
                    'enabled': self.config.getboolean('Neurogenesis.Novelty', 'enabled'),
                    'threshold': self.config.getfloat('Neurogenesis.Novelty', 'threshold'),
                    'decay_rate': self.config.getfloat('Neurogenesis.Novelty', 'decay_rate'),
                    'max_counter': self.config.getfloat('Neurogenesis.Novelty', 'max_counter'),
                    'min_curiosity': self.config.getfloat('Neurogenesis.Novelty', 'min_curiosity'),
                    'personality_modifiers': {
                        'adventurous': self.config.getfloat('Neurogenesis.Novelty', 'adventurous_modifier'),
                        'timid': self.config.getfloat('Neurogenesis.Novelty', 'timid_modifier')
                    }
                },
                'stress': {
                    'enabled': self.config.getboolean('Neurogenesis.Stress', 'enabled'),
                    'threshold': self.config.getfloat('Neurogenesis.Stress', 'threshold'),
                    'decay_rate': self.config.getfloat('Neurogenesis.Stress', 'decay_rate'),
                    'max_counter': self.config.getfloat('Neurogenesis.Stress', 'max_counter'),
                    'min_anxiety': self.config.getfloat('Neurogenesis.Stress', 'min_anxiety'),
                    'personality_modifiers': {
                        'timid': self.config.getfloat('Neurogenesis.Stress', 'timid_modifier'),
                        'energetic': self.config.getfloat('Neurogenesis.Stress', 'energetic_modifier')
                    }
                },
                'reward': {
                    'enabled': self.config.getboolean('Neurogenesis.Reward', 'enabled'),
                    'threshold': self.config.getfloat('Neurogenesis.Reward', 'threshold'),
                    'decay_rate': self.config.getfloat('Neurogenesis.Reward', 'decay_rate'),
                    'max_counter': self.config.getfloat('Neurogenesis.Reward', 'max_counter'),
                    'min_satisfaction': self.config.getfloat('Neurogenesis.Reward', 'min_satisfaction'),
                    'boost_multiplier': self.config.getfloat('Neurogenesis.Reward', 'boost_multiplier')
                }
            },
            'neuron_properties': {
                'base_activation': self.config.getfloat('Neurogenesis.NeuronProperties', 'base_activation'),
                'position_variance': self.config.getint('Neurogenesis.NeuronProperties', 'position_variance'),
                'default_connections': self.config.getboolean('Neurogenesis.NeuronProperties', 'default_connections'),
                'connection_strength': self.config.getfloat('Neurogenesis.NeuronProperties', 'connection_strength'),
                'reciprocal_strength': self.config.getfloat('Neurogenesis.NeuronProperties', 'reciprocal_strength')
            },
            'appearance': {
                'colors': {
                    'novelty': [int(x) for x in self.config['Neurogenesis.Appearance']['novelty_color'].split(',')],
                    'stress': [int(x) for x in self.config['Neurogenesis.Appearance']['stress_color'].split(',')],
                    'reward': [int(x) for x in self.config['Neurogenesis.Appearance']['reward_color'].split(',')]
                },
                'shapes': {
                    'novelty': self.config['Neurogenesis.Appearance']['novelty_shape'],
                    'stress': self.config['Neurogenesis.Appearance']['stress_shape'],
                    'reward': self.config['Neurogenesis.Appearance']['reward_shape']
                }
            },
            'visual_effects': {
                'highlight_duration': self.config.getfloat('Neurogenesis.VisualEffects', 'highlight_duration'),
                'highlight_radius': self.config.getint('Neurogenesis.VisualEffects', 'highlight_radius'),
                'pulse_effect': self.config.getboolean('Neurogenesis.VisualEffects', 'pulse_effect'),
                'pulse_speed': self.config.getfloat('Neurogenesis.VisualEffects', 'pulse_speed')
            }
        }

    def get_random_carry_duration(self):
        """Returns random duration between min and max carry duration"""
        config = self.get_rock_config()
        return random.uniform(config['min_carry_duration'], config['max_carry_duration'])

    def _parse_config_value(self, value):
        """Parse configuration values that might contain comments"""
        # Remove everything after comment markers
        for comment_marker in [';', '#', '//']:
            if comment_marker in value:
                value = value.split(comment_marker)[0]
        
        value = value.strip()
        
        # Try to convert to appropriate type
        if value.lower() == 'true':
            return True
        elif value.lower() == 'false':
            return False
        elif value.isdigit():
            return int(value)
        try:
            return float(value)
        except ValueError:
            return value