"""
brain_factory.py - Factory for creating custom brain networks

Provides utilities for easily creating custom neural networks with
different topologies that can plug into the Dosidicus-2 brain systems.

Usage:
    from brain_factory import BrainFactory
    
    # Create a simple 3-layer network
    brain = BrainFactory.create_layered_network(
        layers=[
            ('input', ['hunger', 'happiness', 'energy']),
            ('hidden', ['processor_1', 'processor_2']),
            ('output', ['action', 'emotion'])
        ],
        fully_connected=True
    )
    
    # Create from a template
    brain = BrainFactory.from_template('simple_emotions')
    
    # Create from JSON definition
    brain = BrainFactory.from_json_definition('my_brain.json')
"""

import json
import random
import math
from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass

from network_protocol import BrainConfig, LayerDefinition, NeuronData
from network_adapter import NetworkAdapter


class BrainFactory:
    """
    Factory class for creating custom neural network brains.
    
    Provides static methods for various brain creation patterns:
    - Layered networks (feedforward, with variable layer counts)
    - Template-based creation
    - JSON-defined custom architectures
    """
    
    # Default canvas dimensions for positioning
    CANVAS_WIDTH = 1000
    CANVAS_HEIGHT = 600
    MARGIN_X = 80
    MARGIN_Y = 60
    
    @classmethod
    def create_layered_network(
        cls,
        layers: List[Tuple[str, List[str]]],
        fully_connected: bool = True,
        initial_weight_range: Tuple[float, float] = (-0.3, 0.3),
        config: Optional[BrainConfig] = None
    ) -> NetworkAdapter:
        """
        Create a layered feedforward network.
        
        Args:
            layers: List of (layer_type, neuron_names) tuples
                    layer_type: 'input', 'hidden', or 'output'
                    neuron_names: List of neuron name strings
            fully_connected: If True, connect all neurons between adjacent layers
            initial_weight_range: (min, max) for random weight initialization
            config: Optional BrainConfig instance
            
        Returns:
            NetworkAdapter ready for use with Dosidicus-2
            
        Example:
            brain = BrainFactory.create_layered_network([
                ('input', ['sight', 'sound', 'touch']),
                ('hidden', ['h1', 'h2', 'h3', 'h4']),
                ('output', ['approach', 'avoid', 'wait'])
            ])
        """
        from core import Network as P1Network
        
        network = P1Network()
        layer_definitions = []
        
        # Calculate Y positions for each layer
        num_layers = len(layers)
        available_height = cls.CANVAS_HEIGHT - (2 * cls.MARGIN_Y)
        layer_spacing = available_height / max(1, num_layers - 1) if num_layers > 1 else 0
        
        all_neurons_by_layer = []
        
        for layer_idx, (layer_type, neuron_names) in enumerate(layers):
            # Calculate Y position for this layer
            y_pos = cls.MARGIN_Y + (layer_idx * layer_spacing)
            
            # Calculate X positions for neurons in this layer
            num_neurons = len(neuron_names)
            available_width = cls.CANVAS_WIDTH - (2 * cls.MARGIN_X)
            neuron_spacing = available_width / max(1, num_neurons + 1)
            
            layer_neurons = []
            
            for neuron_idx, name in enumerate(neuron_names):
                x_pos = cls.MARGIN_X + ((neuron_idx + 1) * neuron_spacing)
                
                # Add neuron
                network.add_neuron(
                    name=name,
                    value=50.0,
                    position=(x_pos, y_pos),
                    n_type=layer_type
                )
                layer_neurons.append(name)
            
            all_neurons_by_layer.append(layer_neurons)
            
            # Create layer definition
            layer_definitions.append(LayerDefinition(
                name=f"Layer_{layer_idx}_{layer_type}",
                neuron_names=layer_neurons,
                layer_type=layer_type,
                y_position=y_pos
            ))
        
        # Create connections between adjacent layers
        if fully_connected and len(all_neurons_by_layer) > 1:
            for i in range(len(all_neurons_by_layer) - 1):
                source_layer = all_neurons_by_layer[i]
                target_layer = all_neurons_by_layer[i + 1]
                
                for source in source_layer:
                    for target in target_layer:
                        weight = random.uniform(*initial_weight_range)
                        network.connect(source, target, weight)
        
        return NetworkAdapter(network, layer_definitions, config or BrainConfig())
    
    @classmethod
    def create_recurrent_network(
        cls,
        layers: List[Tuple[str, List[str]]],
        recurrent_connections: Optional[List[Tuple[str, str, float]]] = None,
        config: Optional[BrainConfig] = None
    ) -> NetworkAdapter:
        """
        Create a network with recurrent (feedback) connections.
        
        Args:
            layers: Same as create_layered_network
            recurrent_connections: List of (source, target, weight) for feedback connections
            config: Optional BrainConfig
            
        Returns:
            NetworkAdapter with recurrent connections
        """
        # Start with a feedforward base
        adapter = cls.create_layered_network(layers, True, (-0.3, 0.3), config)
        
        # Add recurrent connections
        if recurrent_connections:
            for source, target, weight in recurrent_connections:
                adapter.add_connection(source, target, weight)
        
        return adapter
    
    @classmethod
    def create_from_template(cls, template_name: str) -> NetworkAdapter:
        """
        Create a brain from a predefined template.
        
        Available templates:
        - 'dosidicus_default': Standard 7-neuron Dosidicus brain
        - 'simple_emotions': Basic emotion processing network
        - 'deep_processor': 4-layer deep network
        - 'wide_hidden': Wide single hidden layer
        - 'dual_pathway': Parallel processing paths
        
        Args:
            template_name: Name of the template to use
            
        Returns:
            NetworkAdapter configured according to template
        """
        templates = {
            'dosidicus_default': cls._template_dosidicus_default,
            'simple_emotions': cls._template_simple_emotions,
            'deep_processor': cls._template_deep_processor,
            'wide_hidden': cls._template_wide_hidden,
            'dual_pathway': cls._template_dual_pathway,
            'minimal': cls._template_minimal,
        }
        
        if template_name not in templates:
            available = ', '.join(templates.keys())
            raise ValueError(f"Unknown template: {template_name}. Available: {available}")
        
        return templates[template_name]()
    
    @classmethod
    def create_from_json(cls, json_path: str) -> NetworkAdapter:
        """
        Create a brain from a JSON definition file.
        
        JSON format:
        {
            "layers": [
                {"type": "input", "neurons": ["n1", "n2"]},
                {"type": "hidden", "neurons": ["h1", "h2", "h3"]},
                {"type": "output", "neurons": ["o1"]}
            ],
            "custom_connections": [
                {"source": "n1", "target": "o1", "weight": 0.5}
            ],
            "config": {
                "hebbian": {...},
                "neurogenesis": {...}
            }
        }
        """
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        return cls.create_from_dict(data)
    
    @classmethod
    def create_from_dict(cls, data: Dict[str, Any]) -> NetworkAdapter:
        """
        Create a brain from a dictionary definition.
        
        Useful for programmatic brain creation or loading from various sources.
        """
        # Parse layers
        layers = []
        for layer_data in data.get('layers', []):
            layer_type = layer_data.get('type', 'hidden')
            neurons = layer_data.get('neurons', [])
            layers.append((layer_type, neurons))
        
        # Parse config
        config = BrainConfig.from_dict(data.get('config', {}))
        
        # Create base network
        adapter = cls.create_layered_network(layers, True, (-0.3, 0.3), config)
        
        # Add custom connections (override defaults)
        for conn in data.get('custom_connections', []):
            source = conn['source']
            target = conn['target']
            weight = conn.get('weight', 0.1)
            adapter.add_connection(source, target, weight)
        
        # Set custom positions if provided
        for pos_data in data.get('custom_positions', []):
            name = pos_data['neuron']
            position = tuple(pos_data['position'])
            if name in adapter.neuron_positions:
                adapter._network.neurons[name].set_position(*position)
        
        return adapter
    
    # =========================================================================
    # TEMPLATE IMPLEMENTATIONS
    # =========================================================================
    
    @classmethod
    def _template_dosidicus_default(cls) -> NetworkAdapter:
        """Standard Dosidicus-2 brain structure."""
        from network_adapter import DosidictusDefaultBrain
        return DosidictusDefaultBrain()
    
    @classmethod
    def _template_simple_emotions(cls) -> NetworkAdapter:
        """Simple emotion processing network."""
        return cls.create_layered_network([
            ('input', ['stimulus_positive', 'stimulus_negative', 'stimulus_neutral']),
            ('hidden', ['emotion_processor']),
            ('output', ['happy', 'sad', 'calm'])
        ])
    
    @classmethod
    def _template_deep_processor(cls) -> NetworkAdapter:
        """4-layer deep processing network."""
        return cls.create_layered_network([
            ('input', ['sense_1', 'sense_2', 'sense_3', 'sense_4']),
            ('hidden', ['process_a1', 'process_a2']),
            ('hidden', ['process_b1', 'process_b2', 'process_b3']),
            ('output', ['action_1', 'action_2'])
        ])
    
    @classmethod
    def _template_wide_hidden(cls) -> NetworkAdapter:
        """Network with wide hidden layer for complex processing."""
        return cls.create_layered_network([
            ('input', ['in_1', 'in_2', 'in_3']),
            ('hidden', ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'h7', 'h8']),
            ('output', ['out_1', 'out_2'])
        ])
    
    @classmethod
    def _template_dual_pathway(cls) -> NetworkAdapter:
        """Network with parallel processing pathways."""
        from core import Network as P1Network
        
        network = P1Network()
        
        # Input layer
        inputs = ['visual', 'auditory']
        for i, name in enumerate(inputs):
            network.add_neuron(name, 50.0, (200 + i*400, 60), 'input')
        
        # Parallel hidden layers (visual and auditory paths)
        visual_hidden = ['v_process_1', 'v_process_2']
        for i, name in enumerate(visual_hidden):
            network.add_neuron(name, 50.0, (100 + i*100, 200), 'hidden')
            network.connect('visual', name, random.uniform(-0.3, 0.3))
        
        auditory_hidden = ['a_process_1', 'a_process_2']
        for i, name in enumerate(auditory_hidden):
            network.add_neuron(name, 50.0, (500 + i*100, 200), 'hidden')
            network.connect('auditory', name, random.uniform(-0.3, 0.3))
        
        # Integration layer
        integration = ['integrate']
        network.add_neuron('integrate', 50.0, (400, 350), 'hidden')
        for h in visual_hidden + auditory_hidden:
            network.connect(h, 'integrate', random.uniform(-0.3, 0.3))
        
        # Output
        network.add_neuron('response', 50.0, (400, 500), 'output')
        network.connect('integrate', 'response', 0.5)
        
        # Define layers
        layers = [
            LayerDefinition("Input", inputs, "input", 60),
            LayerDefinition("Visual_Processing", visual_hidden, "hidden", 200),
            LayerDefinition("Auditory_Processing", auditory_hidden, "hidden", 200),
            LayerDefinition("Integration", integration, "hidden", 350),
            LayerDefinition("Output", ['response'], "output", 500),
        ]
        
        return NetworkAdapter(network, layers)
    
    @classmethod
    def _template_minimal(cls) -> NetworkAdapter:
        """Minimal 2-neuron test network."""
        return cls.create_layered_network([
            ('input', ['input']),
            ('output', ['output'])
        ])
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    @classmethod
    def list_templates(cls) -> List[str]:
        """Return list of available template names."""
        return [
            'dosidicus_default',
            'simple_emotions', 
            'deep_processor',
            'wide_hidden',
            'dual_pathway',
            'minimal'
        ]
    
    @classmethod
    def get_template_info(cls, template_name: str) -> Dict[str, Any]:
        """Get information about a template."""
        info = {
            'dosidicus_default': {
                'description': 'Standard Dosidicus-2 brain with 7 core neurons',
                'layers': 3,
                'total_neurons': 7
            },
            'simple_emotions': {
                'description': 'Basic emotion processing network',
                'layers': 3,
                'total_neurons': 7
            },
            'deep_processor': {
                'description': '4-layer deep network for complex processing',
                'layers': 4,
                'total_neurons': 11
            },
            'wide_hidden': {
                'description': 'Wide hidden layer for parallel processing',
                'layers': 3,
                'total_neurons': 13
            },
            'dual_pathway': {
                'description': 'Parallel visual/auditory processing paths',
                'layers': 5,
                'total_neurons': 8
            },
            'minimal': {
                'description': 'Minimal 2-neuron test network',
                'layers': 2,
                'total_neurons': 2
            }
        }
        return info.get(template_name, {'description': 'Unknown template'})


# =========================================================================
# CONVENIENCE FUNCTIONS
# =========================================================================

def create_custom_brain(layers: List[Tuple[str, List[str]]]) -> NetworkAdapter:
    """Quick function to create a custom layered brain."""
    return BrainFactory.create_layered_network(layers)


def load_brain(filepath: str) -> NetworkAdapter:
    """Quick function to load a brain from file."""
    return NetworkAdapter.load(filepath)


def save_brain(brain: NetworkAdapter, filepath: str) -> bool:
    """Quick function to save a brain to file."""
    return brain.save(filepath)
