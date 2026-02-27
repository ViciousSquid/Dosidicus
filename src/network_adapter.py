"""
network_adapter.py - Adapter bridging Project 1's Network to Project 2's brain systems

This adapter wraps a Network object and exposes it through the
BrainProtocol interface, allowing custom networks with different topologies
to plug into the brain visualization and learning systems.

Usage:
    from NeuralNetwork.core import Network
    from network_adapter import NetworkAdapter
    
    # Create or load a custom network
    custom_network = Network()
    custom_network.add_neuron("input1", 50.0, (100, 100), 'input')
    ...
    
    # Wrap it for use with Dosidicus
    adapted_brain = NetworkAdapter(custom_network)
    
    # Now it can be used with BrainWidget, BrainWorker, etc.
"""

import json
import random
import time
from typing import Dict, List, Tuple, Set, Any, Optional, TYPE_CHECKING
from dataclasses import dataclass, field

from network_protocol import (
    BrainProtocol, BrainConfig, NeuronData, ConnectionData, LayerDefinition
)

if TYPE_CHECKING:
    # Import Project 1's classes for type hints only
    from core import Network, Neuron, Connection, Config


class NetworkAdapter:
    """
    Adapter that wraps a Project 1 Network to implement the BrainProtocol
    interface required by Project 2's brain systems.
    
    Features:
    - Exposes network data in the format expected by BrainWidget
    - Supports dynamic neurogenesis (adding neurons at runtime)
    - Maintains layer structure for visualization
    - Handles serialization compatible with Dosidicus-2 save system
    
    Args:
        network: A Project 1 Network instance (or None to create fresh)
        layer_structure: Optional layer definitions for visualization
        config: Optional BrainConfig (created with defaults if not provided)
    """
    
    def __init__(self, 
                 network: Optional['Network'] = None,
                 layer_structure: Optional[List[LayerDefinition]] = None,
                 config: Optional[BrainConfig] = None):
        
        # Import Project 1's Network if we need to create a new one
        if network is None:
            from core import Network as P1Network
            network = P1Network()
        
        self._network = network
        self._layer_structure = layer_structure or []
        self._config = config or BrainConfig()
        
        # Project 2 compatibility: excluded neurons (status indicators)
        self._excluded_neurons: Set[str] = {
            'is_sick', 'is_eating', 'pursuing_food', 'direction', 'is_sleeping'
        }
        
        # Track neurogenesis data (matches BrainWidget.neurogenesis_data structure)
        self._neurogenesis_data = {
            'new_neurons': [],
            'last_neuron_time': time.time(),
            'new_neurons_details': {}
        }
        
        # Sync config with underlying network
        self._sync_config_to_network()
    
    # =========================================================================
    # BRAINPROTOCOL REQUIRED PROPERTIES
    # =========================================================================
    
    @property
    def state(self) -> Dict[str, float]:
        """Current activation state of each neuron (0-100 scale)."""
        return self._network.state
    
    @state.setter
    def state(self, value: Dict[str, float]):
        """Allow direct state assignment for compatibility."""
        self._network.state = value
    
    @property
    def neuron_positions(self) -> Dict[str, Tuple[float, float]]:
        """Position of each neuron for visualization."""
        return {
            name: neuron.get_position() 
            for name, neuron in self._network.neurons.items()
        }
    
    @neuron_positions.setter  
    def neuron_positions(self, value: Dict[str, Tuple[float, float]]):
        """Allow position updates for drag-and-drop support."""
        for name, pos in value.items():
            if name in self._network.neurons:
                self._network.neurons[name].set_position(*pos)
    
    @property
    def weights(self) -> Dict[Tuple[str, str], float]:
        """Connection weights as (source, target) -> weight mapping."""
        return {
            (conn.source, conn.target): conn.get_weight()
            for conn in self._network.connections.values()
        }
    
    @weights.setter
    def weights(self, value: Dict[Tuple[str, str], float]):
        """Allow weight updates for Hebbian learning."""
        for (source, target), weight in value.items():
            key = (source, target)
            if key in self._network.connections:
                self._network.connections[key].set_weight(weight)
            elif source in self._network.neurons and target in self._network.neurons:
                # Create new connection
                self._network.connect(source, target, weight)
    
    @property
    def excluded_neurons(self) -> Set[str]:
        """Neurons excluded from Hebbian learning."""
        return self._excluded_neurons
    
    @excluded_neurons.setter
    def excluded_neurons(self, value: Set[str]):
        """Allow updating excluded neurons."""
        self._excluded_neurons = set(value)
    
    @property
    def config(self) -> BrainConfig:
        """Configuration object with hebbian and neurogenesis settings."""
        return self._config
    
    @property
    def neurogenesis_data(self) -> Dict[str, Any]:
        """Neurogenesis tracking data (BrainWidget compatibility)."""
        return self._neurogenesis_data
    
    @neurogenesis_data.setter
    def neurogenesis_data(self, value: Dict[str, Any]):
        """Allow neurogenesis data updates."""
        self._neurogenesis_data = value
    
    # =========================================================================
    # BRAINPROTOCOL REQUIRED METHODS
    # =========================================================================
    
    def get_neuron(self, name: str) -> Optional[NeuronData]:
        """Get neuron data by name."""
        if name not in self._network.neurons:
            return None
        
        neuron = self._network.neurons[name]
        return NeuronData(
            name=neuron.name,
            neuron_type=neuron.type,
            position=neuron.get_position(),
            attributes=neuron.attributes or {}
        )
    
    def get_all_neurons(self) -> List[NeuronData]:
        """Get list of all neurons."""
        return [
            NeuronData(
                name=n.name,
                neuron_type=n.type,
                position=n.get_position(),
                attributes=n.attributes or {}
            )
            for n in self._network.neurons.values()
        ]
    
    def get_connections_for_neuron(self, name: str) -> List[ConnectionData]:
        """Get all connections involving a neuron (incoming and outgoing)."""
        connections = []
        for (source, target), conn in self._network.connections.items():
            if source == name or target == name:
                connections.append(ConnectionData(
                    source=source,
                    target=target,
                    weight=conn.get_weight()
                ))
        return connections
    
    def add_neuron(self, neuron: NeuronData, initial_activation: float = 50.0) -> bool:
        """Add a new neuron to the network."""
        success = self._network.add_neuron(
            name=neuron.name,
            value=initial_activation,
            position=neuron.position,
            n_type=neuron.neuron_type,
            attributes=neuron.attributes
        )
        
        if success:
            # Track for neurogenesis data
            self._neurogenesis_data['new_neurons'].append(neuron.name)
            self._neurogenesis_data['last_neuron_time'] = time.time()
            
        return success
    
    def add_connection(self, source: str, target: str, weight: float) -> bool:
        """Add or update a connection."""
        # Update existing connection
        if (source, target) in self._network.connections:
            self._network.connections[(source, target)].set_weight(weight)
            return True
        
        # Create new connection
        return self._network.connect(source, target, weight)
    
    def set_neuron_activation(self, name: str, value: float) -> None:
        """Set the activation value of a neuron."""
        if name in self._network.state:
            self._network.state[name] = max(0.0, min(100.0, value))
    
    def get_layer_structure(self) -> List[LayerDefinition]:
        """Get the layer structure of the network."""
        return self._layer_structure
    
    # =========================================================================
    # ADDITIONAL COMPATIBILITY METHODS (for BrainWidget)
    # =========================================================================
    
    def initialize_connections(self) -> List[Tuple[str, str]]:
        """Return list of connection pairs (BrainWidget compatibility)."""
        return list(self._network.connections.keys())
    
    def initialize_weights(self) -> None:
        """Initialize weights (no-op, weights already exist in network)."""
        pass
    
    @property
    def connections(self) -> List[Tuple[str, str]]:
        """Connection list for BrainWidget compatibility."""
        return list(self._network.connections.keys())
    
    @connections.setter
    def connections(self, value: List[Tuple[str, str]]):
        """Allow setting connections list."""
        # This is typically read-only, but some code might try to set it
        pass
    
    @property
    def original_neuron_positions(self) -> Dict[str, Tuple[float, float]]:
        """Original positions for reset functionality."""
        return {
            name: neuron.get_position()
            for name, neuron in self._network.neurons.items()
        }
    
    @property
    def original_neurons(self) -> List[str]:
        """List of original neuron names (non-neurogenesis)."""
        new_neurons = set(self._neurogenesis_data.get('new_neurons', []))
        return [n for n in self._network.neurons.keys() if n not in new_neurons]
    
    @property
    def visible_neurons(self) -> Set[str]:
        """All neurons are visible by default."""
        return set(self._network.neurons.keys())
    
    @visible_neurons.setter
    def visible_neurons(self, value: Set[str]):
        """Visibility is typically managed elsewhere, but allow setting."""
        pass
    
    @property
    def neuron_shapes(self) -> Dict[str, str]:
        """Get neuron shapes from attributes."""
        shapes = {}
        for name, neuron in self._network.neurons.items():
            if neuron.attributes and 'shape' in neuron.attributes:
                shapes[name] = neuron.attributes['shape']
            else:
                # Default shape based on type
                shape_map = self._config.neurogenesis['appearance']['shapes']
                shapes[name] = shape_map.get(neuron.type, 'circle')
        return shapes
    
    # =========================================================================
    # SERIALIZATION
    # =========================================================================
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize the entire network to a dictionary."""
        return {
            'version': '2.0',
            'adapter_type': 'NetworkAdapter',
            'neurons': {
                name: {
                    'type': n.type,
                    'position': n.get_position(),
                    'attributes': n.attributes
                }
                for name, n in self._network.neurons.items()
            },
            'connections': {
                f"{s}->{t}": c.get_weight()
                for (s, t), c in self._network.connections.items()
            },
            'state': dict(self._network.state),
            'config': self._config.to_dict(),
            'layer_structure': [l.to_dict() for l in self._layer_structure],
            'excluded_neurons': list(self._excluded_neurons),
            'neurogenesis_data': {
                'new_neurons': self._neurogenesis_data.get('new_neurons', []),
                'last_neuron_time': self._neurogenesis_data.get('last_neuron_time', 0),
                'new_neurons_details': self._neurogenesis_data.get('new_neurons_details', {})
            }
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NetworkAdapter':
        """Deserialize a network from a dictionary."""
        from core import Network as P1Network
        
        network = P1Network()
        
        # Load neurons
        for name, n_data in data.get('neurons', {}).items():
            network.add_neuron(
                name=name,
                value=data.get('state', {}).get(name, 50.0),
                position=tuple(n_data.get('position', (0, 0))),
                n_type=n_data.get('type', 'hidden'),
                attributes=n_data.get('attributes', {})
            )
        
        # Load connections
        for key, weight in data.get('connections', {}).items():
            source, target = key.split('->')
            network.connect(source, target, weight)
        
        # Load state
        network.state = data.get('state', {n: 50.0 for n in network.neurons})
        
        # Load config
        config = BrainConfig.from_dict(data.get('config', {}))
        
        # Load layer structure
        layers = [
            LayerDefinition(
                name=l['name'],
                neuron_names=l['neuron_names'],
                layer_type=l['layer_type'],
                y_position=l['y_position']
            )
            for l in data.get('layer_structure', [])
        ]
        
        # Create adapter
        adapter = cls(network, layers, config)
        
        # Load excluded neurons
        adapter._excluded_neurons = set(data.get('excluded_neurons', []))
        
        # Load neurogenesis data
        adapter._neurogenesis_data = data.get('neurogenesis_data', {
            'new_neurons': [],
            'last_neuron_time': time.time(),
            'new_neurons_details': {}
        })
        
        return adapter
    
    def save(self, filepath: str) -> bool:
        """Save the network to a file."""
        try:
            with open(filepath, 'w') as f:
                json.dump(self.to_dict(), f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving network: {e}")
            return False
    
    @classmethod
    def load(cls, filepath: str) -> Optional['NetworkAdapter']:
        """Load a network from a file."""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            return cls.from_dict(data)
        except Exception as e:
            print(f"Error loading network: {e}")
            return None
    
    # =========================================================================
    # INTERNAL HELPERS
    # =========================================================================
    
    def _sync_config_to_network(self):
        """Sync adapter config with underlying network config."""
        if hasattr(self._network, 'config'):
            # Copy relevant settings to network's config
            self._network.config.hebbian.update(self._config.hebbian)
            self._network.config.neurogenesis.update(self._config.neurogenesis)
    
    def set_layer_structure(self, layers: List[LayerDefinition]):
        """Update the layer structure (and optionally reposition neurons)."""
        self._layer_structure = layers
    
    def get_underlying_network(self) -> 'Network':
        """Get the underlying Project 1 Network (for advanced access)."""
        return self._network


class DosidictusDefaultBrain(NetworkAdapter):
    """
    Pre-configured brain matching the default Dosidicus-2 structure.
    
    Creates the 7 core neurons (hunger, happiness, cleanliness, sleepiness,
    satisfaction, anxiety, curiosity) with standard positions and connections.
    
    Use this as a reference for custom brain designs.
    """
    
    def __init__(self):
        from core import Network as P1Network
        
        network = P1Network()
        
        # Core neurons with standard positions
        core_neurons = {
            "hunger": ((127, 81), 'input'),
            "happiness": ((361, 81), 'hidden'),
            "cleanliness": ((627, 81), 'input'),
            "sleepiness": ((840, 81), 'input'),
            "satisfaction": ((271, 380), 'output'),
            "anxiety": ((491, 389), 'output'),
            "curiosity": ((701, 386), 'output'),
        }
        
        # Add neurons
        for name, (pos, n_type) in core_neurons.items():
            network.add_neuron(name, 50.0, pos, n_type)
        
        # Standard connections (simplified - customize as needed)
        connections = [
            ("hunger", "satisfaction", -0.5),
            ("hunger", "anxiety", 0.3),
            ("happiness", "satisfaction", 0.6),
            ("happiness", "anxiety", -0.4),
            ("cleanliness", "happiness", 0.3),
            ("cleanliness", "anxiety", -0.2),
            ("sleepiness", "curiosity", -0.3),
            ("satisfaction", "happiness", 0.4),
            ("anxiety", "curiosity", -0.2),
            ("anxiety", "happiness", -0.3),
            ("curiosity", "satisfaction", 0.2),
        ]
        
        for source, target, weight in connections:
            network.connect(source, target, weight)
        
        # Define layer structure
        layers = [
            LayerDefinition("Inputs", ["hunger", "cleanliness", "sleepiness"], "input", 81),
            LayerDefinition("Processing", ["happiness"], "hidden", 200),
            LayerDefinition("Outputs", ["satisfaction", "anxiety", "curiosity"], "output", 385),
        ]
        
        super().__init__(network, layers)
        
        # Add status neurons as excluded
        self._excluded_neurons = {
            'is_sick', 'is_eating', 'pursuing_food', 'direction', 'is_sleeping'
        }
