"""
network_protocol.py - Protocol definition for pluggable brain networks

Defines the interface that any brain implementation must follow to work
with the Dosidicus-2 brain_tool, brain_widget, and neurogenesis systems.

This allows custom networks (like those from Project 1's NeuralNetwork system)
to be swapped in while maintaining full compatibility with all visualization
and learning features.
"""

from typing import Protocol, Dict, Tuple, List, Set, Any, Optional, runtime_checkable
from dataclasses import dataclass


@dataclass
class NeuronData:
    """Standard data structure for neuron information."""
    name: str
    neuron_type: str  # 'input', 'hidden', 'output', 'novelty', 'stress', 'reward'
    position: Tuple[float, float]
    attributes: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'type': self.neuron_type,
            'position': self.position,
            'attributes': self.attributes
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NeuronData':
        return cls(
            name=data['name'],
            neuron_type=data.get('type', 'hidden'),
            position=tuple(data.get('position', (0, 0))),
            attributes=data.get('attributes', {})
        )


@dataclass  
class ConnectionData:
    """Standard data structure for connection information."""
    source: str
    target: str
    weight: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'source': self.source,
            'target': self.target,
            'weight': self.weight
        }


@dataclass
class LayerDefinition:
    """Defines a layer in the network topology."""
    name: str
    neuron_names: List[str]
    layer_type: str  # 'input', 'hidden', 'output'
    y_position: float  # Base Y position for visualization
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'neuron_names': self.neuron_names,
            'layer_type': self.layer_type,
            'y_position': self.y_position
        }


@runtime_checkable
class BrainProtocol(Protocol):
    """
    Protocol defining the interface a brain must implement to work with
    the Dosidicus-2 visualization and learning systems.
    
    Implementations should provide these properties and methods to be
    fully compatible with BrainWidget, BrainWorker, and EnhancedNeurogenesis.
    """
    
    # =========================================================================
    # REQUIRED PROPERTIES - Must be Dict-like with these exact names
    # =========================================================================
    
    @property
    def state(self) -> Dict[str, float]:
        """Current activation state of each neuron (0-100 scale)."""
        ...
    
    @property
    def neuron_positions(self) -> Dict[str, Tuple[float, float]]:
        """Position of each neuron for visualization."""
        ...
    
    @property
    def weights(self) -> Dict[Tuple[str, str], float]:
        """Connection weights as (source, target) -> weight mapping."""
        ...
    
    @property
    def excluded_neurons(self) -> Set[str]:
        """Neurons excluded from Hebbian learning (status neurons, etc.)."""
        ...
    
    @property
    def config(self) -> Any:
        """Configuration object with hebbian and neurogenesis settings."""
        ...
    
    # =========================================================================
    # REQUIRED METHODS
    # =========================================================================
    
    def get_neuron(self, name: str) -> Optional[NeuronData]:
        """Get neuron data by name."""
        ...
    
    def get_all_neurons(self) -> List[NeuronData]:
        """Get list of all neurons."""
        ...
    
    def get_connections_for_neuron(self, name: str) -> List[ConnectionData]:
        """Get all connections involving a neuron (incoming and outgoing)."""
        ...
    
    def add_neuron(self, neuron: NeuronData, initial_activation: float = 50.0) -> bool:
        """Add a new neuron to the network. Returns True on success."""
        ...
    
    def add_connection(self, source: str, target: str, weight: float) -> bool:
        """Add or update a connection. Returns True on success."""
        ...
    
    def set_neuron_activation(self, name: str, value: float) -> None:
        """Set the activation value of a neuron."""
        ...
    
    def get_layer_structure(self) -> List[LayerDefinition]:
        """Get the layer structure of the network (for visualization)."""
        ...
    
    # =========================================================================
    # SERIALIZATION
    # =========================================================================
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize the entire network to a dictionary."""
        ...
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BrainProtocol':
        """Deserialize a network from a dictionary."""
        ...
    
    def save(self, filepath: str) -> bool:
        """Save the network to a file."""
        ...
    
    @classmethod
    def load(cls, filepath: str) -> Optional['BrainProtocol']:
        """Load a network from a file."""
        ...


class BrainConfig:
    """
    Configuration class compatible with Dosidicus-2's config expectations.
    
    Provides both hebbian learning and neurogenesis configuration.
    """
    
    def __init__(self):
        self.hebbian = {
            'base_learning_rate': 0.1,
            'active_threshold': 50,
            'learning_interval': 30000,  # milliseconds
            'weight_decay': 0.01,
            'min_weight': -1.0,
            'max_weight': 1.0,
        }
        
        self.neurogenesis = {
            'enabled_globally': True,
            'novelty_threshold': 3.0,
            'stress_threshold': 1.2,
            'reward_threshold': 0.6,
            'cooldown': 180,  # seconds
            'max_neurons': 50,
            'max_per_type': {
                'stress': 3,
                'novelty': 5,
                'reward': 4
            },
            'max_per_specialization': 3,
            'highlight_duration': 5.0,
            'decay_rate': 0.75,
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
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'hebbian': dict(self.hebbian),
            'neurogenesis': dict(self.neurogenesis)
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BrainConfig':
        config = cls()
        if 'hebbian' in data:
            config.hebbian.update(data['hebbian'])
        if 'neurogenesis' in data:
            config.neurogenesis.update(data['neurogenesis'])
        return config
