"""
Brain State Bridge - Communication layer between running game and Brain Designer

This module provides a mechanism for the Brain Designer to detect when
the main Dosidicus game is running and import the exact brain state
being displayed in the game's brain widget.

The game writes its current brain state to a shared file, and the designer
reads from it on startup.
"""

import json
import os
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass


# Shared state file location - in user's home directory
def get_bridge_directory() -> Path:
    """Get the directory for bridge files."""
    # Use a hidden directory in the user's home folder
    bridge_dir = Path.home() / ".dosidicus" / "bridge"
    bridge_dir.mkdir(parents=True, exist_ok=True)
    return bridge_dir


def get_state_file_path() -> Path:
    """Get the path to the shared brain state file."""
    return get_bridge_directory() / "active_brain_state.json"


def get_lock_file_path() -> Path:
    """Get the path to the game running lock file."""
    return get_bridge_directory() / "game_running.lock"


# ============================================================================
# GAME-SIDE FUNCTIONS (called by brain_widget / brain_tool)
# ============================================================================

def export_brain_state(
    neuron_positions: Dict[str, Tuple[float, float]],
    weights: Dict[Tuple[str, str], float],
    state: Dict[str, Any],
    visible_neurons: set = None,
    excluded_neurons: list = None,
    layers: list = None,
    output_bindings: list = None
) -> bool:
    """
    Export the current brain state from the game to the shared file.
    
    This should be called by the game periodically or on state changes.
    
    Args:
        neuron_positions: Dict mapping neuron name to (x, y) position
        weights: Dict mapping (source, target) tuple to weight value
        state: Dict mapping neuron name to current activation value
        visible_neurons: Set of currently visible neuron names
        excluded_neurons: List of neurons excluded from display
        layers: Optional layer structure
        output_bindings: Optional output bindings list
        
    Returns:
        True if export was successful, False otherwise
    """
    try:
        # Convert weights dict with tuple keys to serializable format
        serializable_weights = {}
        for (src, dst), weight in weights.items():
            key = f"{src}->{dst}"
            serializable_weights[key] = weight
        
        export_data = {
            "version": "1.0",
            "format": "live_brain_state",
            "timestamp": time.time(),
            "pid": os.getpid(),
            "neurons": {},
            "connections": serializable_weights,
            "state": {},
            "excluded_neurons": list(excluded_neurons) if excluded_neurons else [],
            "layers": layers or [],
            "output_bindings": output_bindings or []
        }
        
        # Build neurons dict with position and state info
        for name, pos in neuron_positions.items():
            if visible_neurons is not None and name not in visible_neurons:
                continue  # Skip non-visible neurons
            
            export_data["neurons"][name] = {
                "position": list(pos) if isinstance(pos, tuple) else pos,
                "activation": state.get(name, 0)
            }
        
        # Copy state values
        export_data["state"] = dict(state)
        
        # Write to file atomically (write to temp then rename)
        state_file = get_state_file_path()
        temp_file = state_file.with_suffix('.tmp')
        
        with open(temp_file, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        # Atomic rename
        temp_file.replace(state_file)
        
        return True
        
    except Exception as e:
        print(f"[BrainBridge] Error exporting brain state: {e}")
        return False


def set_game_running(running: bool = True) -> None:
    """
    Set/clear the game running flag.
    
    Call with running=True when game starts, running=False when game closes.
    """
    lock_file = get_lock_file_path()
    
    if running:
        # Create lock file with PID and timestamp
        lock_data = {
            "pid": os.getpid(),
            "timestamp": time.time()
        }
        with open(lock_file, 'w') as f:
            json.dump(lock_data, f)
    else:
        # Remove lock file
        try:
            lock_file.unlink(missing_ok=True)
        except Exception:
            pass
        
        # Also remove state file
        try:
            get_state_file_path().unlink(missing_ok=True)
        except Exception:
            pass


def update_brain_state_from_widget(brain_widget) -> bool:
    """
    Convenience function to export brain state directly from a BrainWidget instance.
    
    Args:
        brain_widget: BrainWidget instance from the game
        
    Returns:
        True if export successful
    """
    try:
        return export_brain_state(
            neuron_positions=brain_widget.neuron_positions,
            weights=brain_widget.weights,
            state=brain_widget.state,
            visible_neurons=getattr(brain_widget, 'visible_neurons', None),
            excluded_neurons=getattr(brain_widget, 'excluded_neurons', []),
            layers=getattr(brain_widget, 'layers', []),
            output_bindings=[]
        )
    except Exception as e:
        print(f"[BrainBridge] Error updating from widget: {e}")
        return False


# ============================================================================
# DESIGNER-SIDE FUNCTIONS (called by brain_designer / designer_window)
# ============================================================================

def is_game_running() -> bool:
    """
    Check if the main Dosidicus game is currently running.
    
    Returns:
        True if game appears to be running and has exported brain state
    """
    lock_file = get_lock_file_path()
    state_file = get_state_file_path()
    
    if not lock_file.exists():
        return False
    
    if not state_file.exists():
        return False
    
    try:
        # Check if lock file is recent (within last 60 seconds)
        with open(lock_file, 'r') as f:
            lock_data = json.load(f)
        
        lock_time = lock_data.get('timestamp', 0)
        if time.time() - lock_time > 60:
            # Lock file is stale, game probably crashed
            return False
        
        # Check if state file is recent
        state_mtime = state_file.stat().st_mtime
        if time.time() - state_mtime > 30:
            # State file is stale
            return False
        
        return True
        
    except Exception:
        return False


def import_brain_state_for_designer() -> Optional[Dict]:
    """
    Import brain state from the running game for use in the designer.
    
    Returns:
        Dict with brain state data if game is running, None otherwise
    """
    if not is_game_running():
        return None
    
    try:
        state_file = get_state_file_path()
        
        with open(state_file, 'r') as f:
            data = json.load(f)
        
        # Verify format
        if data.get('format') != 'live_brain_state':
            return None
        
        return data
        
    except Exception as e:
        print(f"[BrainBridge] Error importing brain state: {e}")
        return None


def convert_to_brain_design(live_state: Dict) -> Optional['BrainDesign']:
    """
    Convert imported live brain state to a BrainDesign object.
    
    This creates a BrainDesign that mirrors the exact state of the running game.
    
    Args:
        live_state: Dict from import_brain_state_for_designer()
        
    Returns:
        BrainDesign instance or None if conversion fails
    """
    # Import here to avoid circular imports
    try:
        from designer_core import BrainDesign, DesignerNeuron, DesignerConnection
        from designer_constants import (
            NeuronType, is_core_neuron, is_input_sensor, is_binary_neuron,
            DEFAULT_COLORS
        )
    except ImportError:
        print("[BrainBridge] Could not import designer modules")
        return None
    
    try:
        design = BrainDesign()
        
        # Set metadata
        design.metadata = {
            'name': 'Imported from Running Game',
            'description': 'Brain state imported from active Dosidicus game',
            'author': 'Live Import',
            'version': '1.0',
            'created': '',
            'modified': ''
        }
        
        neurons_data = live_state.get('neurons', {})
        connections_data = live_state.get('connections', {})
        state_data = live_state.get('state', {})
        
        # Create neurons
        for name, neuron_info in neurons_data.items():
            pos = neuron_info.get('position', [0, 0])
            
            # Determine neuron type
            if is_core_neuron(name):
                ntype = NeuronType.CORE
                color = DEFAULT_COLORS.get('core', (150, 150, 220))
            elif is_input_sensor(name) or name == 'can_see_food':
                ntype = NeuronType.SENSOR
                color = DEFAULT_COLORS.get('sensor', (150, 200, 220))
            else:
                ntype = NeuronType.HIDDEN
                color = DEFAULT_COLORS.get('hidden', (180, 180, 200))
            
            neuron = DesignerNeuron(
                name=name,
                neuron_type=ntype,
                position=tuple(pos) if isinstance(pos, list) else pos,
                color=color,
                is_binary=is_binary_neuron(name)
            )
            design.add_neuron(neuron)
        
        # Create connections
        for conn_key, weight in connections_data.items():
            if '->' in conn_key:
                source, target = conn_key.split('->')
            elif '|' in conn_key:
                source, target = conn_key.split('|')
            else:
                continue
            
            source = source.strip()
            target = target.strip()
            
            # Only add if both neurons exist
            if source in design.neurons and target in design.neurons:
                conn = DesignerConnection(source=source, target=target, weight=weight)
                design.connections.append(conn)
        
        # Load layers if present
        for layer_data in live_state.get('layers', []):
            from designer_core import DesignerLayer
            design.layers.append(DesignerLayer.from_dict(layer_data))
        
        # Load output bindings if present
        design.output_bindings = live_state.get('output_bindings', [])
        
        return design
        
    except Exception as e:
        print(f"[BrainBridge] Error converting to BrainDesign: {e}")
        import traceback
        traceback.print_exc()
        return None


# ============================================================================
# CLEANUP
# ============================================================================

def cleanup_bridge_files() -> None:
    """Remove all bridge files. Called when game exits cleanly."""
    set_game_running(False)
