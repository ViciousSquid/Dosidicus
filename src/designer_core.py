import json
import random
import time
import math
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
from PyQt5.QtWidgets import QMessageBox

from designer_constants import (
    NeuronType, DEFAULT_COLORS, REQUIRED_NEURONS, CORE_NEURONS,
    INPUT_SENSORS, is_core_neuron, is_required_neuron, is_input_sensor,
    is_binary_neuron, get_neuron_category, get_default_connections_for_sensor
)

@dataclass
class DesignerLayer:
    name: str
    layer_type: NeuronType
    y_position: float
    color: Tuple[int, int, int, int] = (200, 200, 220, 80)
    
    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'layer_type': self.layer_type.name.lower(),
            'y_position': self.y_position,
            'color': self.color
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'DesignerLayer':
        layer_type_str = data.get('layer_type', 'hidden').upper()
        try:
            layer_type = NeuronType[layer_type_str]
        except KeyError:
            layer_type = NeuronType.HIDDEN
        return cls(
            name=data['name'],
            layer_type=layer_type,
            y_position=data['y_position'],
            color=tuple(data.get('color', (200, 200, 220, 80)))
        )

@dataclass 
class DesignerNeuron:
    name: str
    neuron_type: NeuronType
    position: Tuple[float, float]
    layer_index: int = 0
    color: Tuple[int, int, int] = (150, 150, 220)
    description: str = ""
    is_binary: bool = False
    
    def __post_init__(self):
        if is_core_neuron(self.name):
            self.neuron_type = NeuronType.CORE
            self.color = DEFAULT_COLORS['core']
        elif self.name == 'can_see_food':
            self.neuron_type = NeuronType.SENSOR
            self.color = DEFAULT_COLORS.get('required', (100, 180, 100))
            self.is_binary = True
        elif is_input_sensor(self.name):
            self.neuron_type = NeuronType.SENSOR
            self.color = DEFAULT_COLORS['sensor']
            self.is_binary = is_binary_neuron(self.name)
    
    @property
    def is_core(self) -> bool: return is_core_neuron(self.name)
    @property
    def is_required(self) -> bool: return is_required_neuron(self.name)
    @property
    def is_sensor(self) -> bool: return is_input_sensor(self.name) or self.name == 'can_see_food'
    @property
    def is_protected(self) -> bool: return self.is_required
    @property
    def category(self) -> str: return get_neuron_category(self.name)
    
    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'neuron_type': self.neuron_type.name.lower(),
            'position': list(self.position),
            'layer_index': self.layer_index,
            'color': list(self.color),
            'description': self.description,
            'is_binary': self.is_binary,
            'category': self.category
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'DesignerNeuron':
        type_str = data.get('neuron_type', 'hidden').upper()
        try:
            neuron_type = NeuronType[type_str]
        except KeyError:
            neuron_type = NeuronType.HIDDEN
        
        # Safely handle position - might be invalid in corrupted files
        pos = data.get('position', (0, 0))
        try:
            # Ensure it's a tuple with 2 numeric values
            if isinstance(pos, (list, tuple)) and len(pos) == 2:
                x, y = pos
                if isinstance(x, (int, float)) and isinstance(y, (int, float)):
                    position = tuple(pos)
                else:
                    position = (0, 0)  # Will be fixed by add_neuron validation
            else:
                position = (0, 0)  # Will be fixed by add_neuron validation
        except (TypeError, ValueError):
            position = (0, 0)  # Will be fixed by add_neuron validation
        
        return cls(
            name=data['name'],
            neuron_type=neuron_type,
            position=position,
            layer_index=data.get('layer_index', 0),
            color=tuple(data.get('color', (150, 150, 220))),
            description=data.get('description', ''),
            is_binary=data.get('is_binary', False)
        )

@dataclass
class DesignerConnection:
    source: str
    target: str
    weight: float = 0.5
    
    def to_dict(self) -> dict:
        return {'source': self.source, 'target': self.target, 'weight': self.weight}
    
    @classmethod
    def from_dict(cls, data: dict) -> 'DesignerConnection':
        return cls(source=data['source'], target=data['target'], weight=data.get('weight', 0.5))

class BrainDesign:
    def __init__(self):
        self.neurons: Dict[str, DesignerNeuron] = {}
        self.connections: List[DesignerConnection] = []
        self.layers: List[DesignerLayer] = []
        self.output_bindings: List[Dict] = []  # Neuron output bindings for actuators
        self.metadata: Dict = {
            'name': 'Untitled', 'description': '', 'author': '',
            'version': '1.0', 'created': '', 'modified': ''
        }
        self._next_custom_neuron_x = 400  # For auto-positioning custom neurons
        self._next_custom_neuron_y = 200
    
    def _validate_and_fix_position(self, position: any) -> Tuple[float, float]:
        """Validate and fix neuron position, generating a default if invalid."""
        # Check if position is None
        if position is None:
            return self._generate_custom_position()
        
        # Check if it's a tuple/list with 2 elements
        try:
            if not isinstance(position, (tuple, list)) or len(position) != 2:
                return self._generate_custom_position()
            
            x, y = position
            
            # Validate that x and y are numbers
            if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
                return self._generate_custom_position()
            
            # Check for None or invalid values
            if x is None or y is None:
                return self._generate_custom_position()
            
            return (float(x), float(y))
            
        except (TypeError, ValueError):
            return self._generate_custom_position()
    
    def _generate_custom_position(self) -> Tuple[float, float]:
        """Generate a default position for custom neurons."""
        pos = (self._next_custom_neuron_x, self._next_custom_neuron_y)
        
        # Move position for next neuron (wrap after 3 neurons per row)
        self._next_custom_neuron_x += 120
        if self._next_custom_neuron_x > 600:
            self._next_custom_neuron_x = 400
            self._next_custom_neuron_y += 100
        
        return pos
    
    def add_neuron(self, neuron: DesignerNeuron) -> bool:
        if neuron.name in self.neurons: return False
        
        # CRITICAL FIX: Validate and fix position before adding
        neuron.position = self._validate_and_fix_position(neuron.position)
        
        self.neurons[neuron.name] = neuron
        return True
    
    def remove_neuron(self, name: str) -> Tuple[bool, str]:
        if name not in self.neurons: return False, f"Neuron '{name}' not found"
        if is_required_neuron(name):
            return False, f"Cannot delete required neuron '{name}'"
        del self.neurons[name]
        self.connections = [c for c in self.connections if c.source != name and c.target != name]
        return True, f"Removed neuron '{name}'"
    
    def rename_neuron(self, old_name: str, new_name: str) -> Tuple[bool, str]:
        if old_name not in self.neurons: return False, f"Neuron '{old_name}' not found"
        if is_required_neuron(old_name): return False, f"Cannot rename required neuron '{old_name}'"
        if new_name in self.neurons: return False, f"Neuron '{new_name}' already exists"
        neuron = self.neurons.pop(old_name)
        neuron.name = new_name
        self.neurons[new_name] = neuron
        for conn in self.connections:
            if conn.source == old_name: conn.source = new_name
            if conn.target == old_name: conn.target = new_name
        return True, f"Renamed '{old_name}' to '{new_name}'"
    
    def get_neuron(self, name: str) -> Optional[DesignerNeuron]:
        return self.neurons.get(name)
    
    def add_connection(self, source: str, target: str, weight: float = 0.5) -> bool:
        if source not in self.neurons or target not in self.neurons: return False
        for conn in self.connections:
            if conn.source == source and conn.target == target:
                conn.weight = weight
                return True
        self.connections.append(DesignerConnection(source, target, weight))
        return True
    
    def remove_connection(self, source: str, target: str) -> bool:
        for i, conn in enumerate(self.connections):
            if conn.source == source and conn.target == target:
                self.connections.pop(i)
                return True
        return False
    
    def get_connection(self, source: str, target: str) -> Optional[DesignerConnection]:
        for conn in self.connections:
            if conn.source == source and conn.target == target: return conn
        return None
    
    def add_layer(self, layer: DesignerLayer) -> bool:
        self.layers.append(layer)
        self.layers.sort(key=lambda l: l.y_position)
        return True
    
    def remove_layer(self, index: int) -> bool:
        if 0 <= index < len(self.layers):
            self.layers.pop(index)
            return True
        return False

    def get_missing_required_neurons(self) -> List[str]:
        return [name for name in REQUIRED_NEURONS if name not in self.neurons]
    
    def has_all_required_neurons(self) -> bool:
        return len(self.get_missing_required_neurons()) == 0
    
    def add_missing_required_neurons(self) -> int:
        added = 0
        for name, pos in REQUIRED_NEURONS.items():
            if name not in self.neurons:
                ntype = NeuronType.SENSOR if name == 'can_see_food' else NeuronType.CORE
                desc = "Required neuron"
                self.add_neuron(DesignerNeuron(name=name, neuron_type=ntype, position=pos, description=desc))
                added += 1
        return added

    def add_missing_core_neurons(self) -> int:
        added = 0
        for name, pos in CORE_NEURONS.items():
            if name not in self.neurons:
                self.add_neuron(DesignerNeuron(
                    name=name, neuron_type=NeuronType.CORE, position=pos, description="Core neuron"))
                added += 1
        return added
    
    def get_orphan_neurons(self) -> List[str]:
        if not self.connections:
            return [n for n in self.neurons if not is_required_neuron(n)]
        connected = set()
        for conn in self.connections:
            connected.add(conn.source)
            connected.add(conn.target)
        return [name for name in self.neurons if name not in connected and not is_required_neuron(name)]
    
    def get_island_neurons(self) -> List[Set[str]]:
        if not self.neurons: return []
        adj = {name: set() for name in self.neurons}
        for conn in self.connections:
            if conn.source in adj and conn.target in adj:
                adj[conn.source].add(conn.target)
                adj[conn.target].add(conn.source)
        
        visited = set()
        components = []
        for start in self.neurons:
            if start in visited: continue
            component = set()
            queue = [start]
            while queue:
                node = queue.pop(0)
                if node in visited: continue
                visited.add(node)
                component.add(node)
                for neighbor in adj[node]:
                    if neighbor not in visited: queue.append(neighbor)
            components.append(component)
            
        main_component = None
        for comp in components:
            if any(is_required_neuron(n) for n in comp):
                main_component = comp
                break
        return [comp for comp in components if comp != main_component and len(comp) > 0]
    
    def auto_fix_connectivity(self) -> Tuple[int, List[str]]:
        actions = []
        connections_created = 0
        
        def get_suggested_weight(source_cat: str, target_cat: str, rng: random.Random) -> float:
            tendencies = {
                ('sensor', 'core'): (0.3, 0.6), ('sensor', 'sensor'): (-0.2, 0.4),
                ('custom', 'core'): (-0.4, 0.8), ('custom', 'custom'): (-0.5, 0.5),
                ('core', 'core'): (-0.3, 0.7),
            }
            key = (source_cat, target_cat)
            if key not in tendencies: key = (target_cat, source_cat)
            if key not in tendencies: key = ('custom', 'custom')
            min_w, max_w = tendencies[key]
            return rng.uniform(min_w, max_w)
            
        def find_nearest_core(neuron_pos: Tuple[float, float]) -> Optional[str]:
            core_neurons = [n for n in self.neurons.values() if n.is_core]
            if not core_neurons: return None
            return min(core_neurons, key=lambda n: math.hypot(neuron_pos[0] - n.position[0], neuron_pos[1] - n.position[1])).name

        fix_rng = random.Random()
        fix_rng.seed(time.time() + hash(tuple(sorted(self.neurons.keys()))) % 10000)
        
        # Fix orphans
        for orphan_name in self.get_orphan_neurons():
            orphan = self.neurons[orphan_name]
            target_name = find_nearest_core(orphan.position)
            if target_name:
                w1 = get_suggested_weight(orphan.category, self.neurons[target_name].category, fix_rng)
                w2 = get_suggested_weight(self.neurons[target_name].category, orphan.category, fix_rng)
                self.add_connection(orphan_name, target_name, w1)
                self.add_connection(target_name, orphan_name, w2)
                connections_created += 2
                actions.append(f"Connected orphan '{orphan_name}' ↔ '{target_name}'")

        # Fix islands
        main_network = set()
        for conn in self.connections:
            if is_core_neuron(conn.source) or is_core_neuron(conn.target):
                main_network.add(conn.source)
                main_network.add(conn.target)
        if not main_network:
             main_network = set(self.neurons.keys()) # Fallback

        for island in self.get_island_neurons():
            island_list = list(island)
            island_center = (
                sum(self.neurons[n].position[0] for n in island_list) / len(island_list),
                sum(self.neurons[n].position[1] for n in island_list) / len(island_list)
            )
            nearest_main = find_nearest_core(island_center)
            if nearest_main:
                connect_count = min(2, len(island_list))
                for i in range(connect_count):
                    n = island_list[i % len(island_list)]
                    w = get_suggested_weight(self.neurons[n].category, self.neurons[nearest_main].category, fix_rng)
                    self.add_connection(n, nearest_main, w)
                    connections_created += 1
                    actions.append(f"Connected island node '{n}' → '{nearest_main}'")
        
        return connections_created, actions

    def add_sensor(self, name: str, create_default_connections: bool = True) -> Tuple[bool, str]:
        if name not in INPUT_SENSORS and name != 'can_see_food':
            return False, f"'{name}' is not a valid input sensor"
        if name in self.neurons:
            return False, f"Sensor '{name}' already exists"
        
        pos = REQUIRED_NEURONS[name] if name == 'can_see_food' else INPUT_SENSORS[name]
        self.add_neuron(DesignerNeuron(name=name, neuron_type=NeuronType.SENSOR, position=pos, is_binary=is_binary_neuron(name)))
        
        conns_made = []
        if create_default_connections:
            for target, weight in get_default_connections_for_sensor(name):
                if target in self.neurons:
                    self.add_connection(name, target, weight)
                    conns_made.append(f"{name}→{target}")
        return True, f"Added sensor '{name}' with connections: {', '.join(conns_made)}"

    def add_all_sensors(self) -> int:
        added = 0
        for name in INPUT_SENSORS:
            if self.add_sensor(name)[0]: added += 1
        return added
    
    def get_sensors_in_design(self) -> List[str]:
        return [n for n in self.neurons if is_input_sensor(n) or n == 'can_see_food']
    
    def validate(self, auto_fix: bool = True) -> Tuple[bool, List[str], int]:
        issues = []
        auto_added = 0
        missing_required = self.get_missing_required_neurons()
        
        if missing_required:
            if auto_fix:
                auto_added = self.add_missing_required_neurons()
                issues.append(f"Auto-added missing required: {', '.join(missing_required)}")
            else:
                issues.append(f"BLOCKING: Missing required: {', '.join(missing_required)}")
        
        orphans = self.get_orphan_neurons()
        if orphans:
            if auto_fix:
                conns, actions = self.auto_fix_connectivity()
                issues.append(f"Auto-fixed orphans with {conns} new connections")
                issues.extend(actions)
                auto_added += conns
            else:
                issues.append(f"WARNING: Orphan neurons: {', '.join(orphans)}")
        
        if 'can_see_food' not in self.neurons:
            issues.append("WARNING: Missing 'can_see_food' sensor!")
            
        return not any("BLOCKING" in i for i in issues), issues, auto_added
    
    def get_stats(self) -> Dict:
        return {
            'total_neurons': len(self.neurons),
            'connections': len(self.connections),
            'has_all_required': self.has_all_required_neurons(),
            'missing_required': self.get_missing_required_neurons(),
            'orphan_neurons': self.get_orphan_neurons(),
            'island_groups': len(self.get_island_neurons()),
            'sensors_used': self.get_sensors_in_design(),
            'required_neurons': sum(1 for n in self.neurons.values() if n.is_required),
            'sensor_neurons': sum(1 for n in self.neurons.values() if n.is_sensor and not n.is_required),
            'custom_neurons': sum(1 for n in self.neurons.values() if not n.is_required and not n.is_sensor),
            'layers': len(self.layers)
        }

    def to_dosidicus_format(self) -> dict:
        """
        Export in format compatible with custom_brain_loader.
        
        The loader expects:
        - 'neurons' dict with 'position' field
        - 'connections' dict with '->' keys
        """
        # Build neurons dict with position info (Format 1 compatible)
        neurons = {}
        for name, obj in self.neurons.items():
            neurons[name] = {
                'position': list(obj.position),
                'type': obj.neuron_type.name.lower(),
                'is_binary': obj.is_binary,
                'is_core': obj.is_core,
                'is_sensor': obj.is_sensor,
                'activation': 0.0 if obj.is_binary else (50.0 if obj.is_core else 0.0),
            }
        
        # Build connections dict with '->' keys (Format 1)
        connections = {}
        for c in self.connections:
            key = f"{c.source}->{c.target}"
            connections[key] = c.weight
        
        # Build state dict
        state = {}
        for name, obj in self.neurons.items():
            if obj.is_binary:
                state[name] = False
            elif obj.is_core:
                state[name] = 50.0
            else:
                state[name] = 0.0
        
        return {
            'version': '2.0',
            'format': 'dosidicus',
            'metadata': self.metadata.copy(),
            # Primary format (matches custom_brain_loader Format 1)
            'neurons': neurons,
            'connections': connections,
            'state': state,
            'excluded_neurons': [],
            # Output bindings for actuator neurons
            'output_bindings': self.output_bindings,
            # Legacy fields for backward compatibility
            'neuron_positions': {n: tuple(obj.position) for n, obj in self.neurons.items()},
            'weights': {f"{c.source}|{c.target}": c.weight for c in self.connections},
            'layer_structure': [l.to_dict() for l in self.layers],
            'neuron_details': {n: obj.to_dict() for n, obj in self.neurons.items()},
            'sensors_used': self.get_sensors_in_design(),
            'required_complete': self.has_all_required_neurons()
        }
    
    def to_designer_format(self) -> dict:
        """
        Export in designer format, also compatible with custom_brain_loader.
        Uses list-based connections format (Format 2 in loader).
        """
        # Build neurons dict with position info
        neurons = {}
        for n in self.neurons.values():
            neurons[n.name] = {
                'name': n.name,
                'position': list(n.position),
                'neuron_type': n.neuron_type.name.lower(),
                'layer_index': n.layer_index,
                'color': list(n.color),
                'description': n.description,
                'is_binary': n.is_binary,
                'category': n.category,
                'activation': 0.0 if n.is_binary else (50.0 if n.is_core else 0.0),
            }
        
        # Connections as list (Format 2 in loader)
        connections = [c.to_dict() for c in self.connections]
        
        return {
            'version': '2.0',
            'format': 'brain_designer',
            'metadata': self.metadata.copy(),
            'neurons': neurons,  # Dict format for loader compatibility
            'connections': connections,  # List format
            'layers': [l.to_dict() for l in self.layers],
            'excluded_neurons': [],
            'output_bindings': self.output_bindings,  # Actuator neuron bindings
        }
    
    @classmethod
    def from_designer_format(cls, data: dict) -> 'BrainDesign':
        design = cls()
        design.metadata = data.get('metadata', {})
        for l in data.get('layers', []):
            design.layers.append(DesignerLayer.from_dict(l))
        
        # Handle neurons as either dict or list
        neurons_data = data.get('neurons', [])
        if isinstance(neurons_data, dict):
            # New format: dict keyed by name
            for name, n in neurons_data.items():
                if 'name' not in n:
                    n['name'] = name
                neuron = DesignerNeuron.from_dict(n)
                design.add_neuron(neuron)  # Use add_neuron for position validation
        else:
            # Old format: list
            for n in neurons_data:
                neuron = DesignerNeuron.from_dict(n)
                design.add_neuron(neuron)  # Use add_neuron for position validation
        
        for c in data.get('connections', []):
            design.connections.append(DesignerConnection.from_dict(c))
        
        # Load output bindings
        design.output_bindings = data.get('output_bindings', [])
        
        return design
    
    @classmethod
    def from_dosidicus_format(cls, data: dict) -> 'BrainDesign':
        design = cls()
        design.metadata = data.get('metadata', {'name': 'Imported Brain'})
        for l in data.get('layer_structure', []):
            design.layers.append(DesignerLayer.from_dict(l))
        
        # Handle neurons - new format has 'neurons' dict, old format has 'neuron_positions'
        neurons_data = data.get('neurons', {})
        if neurons_data and isinstance(neurons_data, dict):
            # New format: neurons dict with full info
            for name, nd in neurons_data.items():
                pos = nd.get('position', [0, 0])
                ntype_str = nd.get('type', 'hidden').upper()
                try:
                    ntype = NeuronType[ntype_str]
                except KeyError:
                    ntype = NeuronType.CORE if is_core_neuron(name) else (
                        NeuronType.SENSOR if is_input_sensor(name) else NeuronType.HIDDEN
                    )
                neuron = DesignerNeuron(
                    name=name,
                    neuron_type=ntype,
                    position=tuple(pos) if isinstance(pos, list) else pos,
                    is_binary=nd.get('is_binary', False)
                )
                design.add_neuron(neuron)  # Use add_neuron for position validation
        else:
            # Old format: neuron_positions + neuron_details
            details = data.get('neuron_details', {})
            for name, pos in data.get('neuron_positions', {}).items():
                if name in details:
                    neuron = DesignerNeuron.from_dict(details[name])
                    design.add_neuron(neuron)  # Use add_neuron for position validation
                else:
                    ntype = NeuronType.CORE if is_core_neuron(name) else (
                        NeuronType.SENSOR if is_input_sensor(name) else NeuronType.HIDDEN
                    )
                    neuron = DesignerNeuron(name=name, neuron_type=ntype, position=tuple(pos))
                    design.add_neuron(neuron)  # Use add_neuron for position validation
        
        # Handle connections - new format has '->' keys, old format has '|' keys
        connections_data = data.get('connections', {})
        if isinstance(connections_data, dict):
            for k, w in connections_data.items():
                if '->' in k:
                    s, t = k.split('->')
                elif '|' in k:
                    s, t = k.split('|')
                else:
                    continue
                design.connections.append(DesignerConnection(s.strip(), t.strip(), w))
        elif isinstance(connections_data, list):
            # List format
            for c in connections_data:
                if c.get('source') and c.get('target'):
                    design.connections.append(DesignerConnection(
                        c['source'], c['target'], c.get('weight', 0.1)
                    ))
        
        # Also try old 'weights' field
        if not design.connections:
            for k, w in data.get('weights', {}).items():
                if '|' in k:
                    s, t = k.split('|')
                    design.connections.append(DesignerConnection(s, t, w))
        
        # Load output bindings
        design.output_bindings = data.get('output_bindings', [])
        
        return design
        
    def save(self, filepath: str, format: str = 'designer') -> Tuple[bool, str]:
        is_valid, issues, auto_added = self.validate(auto_fix=True)
        if not is_valid: 
            return False, "Save blocked by validation issues."
        
        try:
            data = self.to_dosidicus_format() if format == 'dosidicus' else self.to_designer_format()
            with open(filepath, 'w') as f: json.dump(data, f, indent=2)
            
            msg = f"Saved successfully ({len(self.neurons)} neurons)"
            if auto_added > 0: msg += f"\n(Applied {auto_added} auto-fixes)"
            return True, msg
        except Exception as e:
            return False, f"Error saving: {e}"
    
    @classmethod
    def load(cls, filepath: str) -> 'BrainDesign':
        with open(filepath, 'r') as f: data = json.load(f)
        return cls.from_dosidicus_format(data) if data.get('format') == 'dosidicus' else cls.from_designer_format(data)

    def export_dosidicus(self, filepath):
        return self.save(filepath, format='dosidicus')