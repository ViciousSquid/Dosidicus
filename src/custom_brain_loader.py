import os
import json
import shutil
import time
from pathlib import Path
from typing import Optional, Dict
from PyQt5 import QtWidgets, QtCore, QtGui
from .brain_neuron_outputs import NeuronOutputBinding, OutputTriggerMode


# Global tracker for the currently loaded custom brain
_current_custom_brain: Optional[Dict] = None
_current_custom_brain_name: Optional[str] = None
_current_custom_brain_file: Optional[str] = None


def add_load_brain_button(network_tab, checkbox_layout):
    """
    Add a Load Brain button to the NetworkTab.
    
    Args:
        network_tab: The NetworkTab instance (self)
        checkbox_layout: The checkbox layout to add the button to
    """
    # Add some spacing
    checkbox_layout.addSpacing(20)
    
    # Create the button
    load_btn = QtWidgets.QPushButton("Load Brain...")
    load_btn.setToolTip("Load a custom brain architecture")
    load_btn.setStyleSheet("""
        QPushButton {
            background-color: #5c6bc0;
            color: white;
            border: none;
            border-radius: 3px;
            padding: 4px 12px;
            font-weight: bold;
            font-size: 9pt;
        }
        QPushButton:hover {
            background-color: #7986cb;
        }
        QPushButton:pressed {
            background-color: #3f51b5;
        }
    """)
    
    # Create loader and connect
    loader = BrainLoader(network_tab)
    network_tab._brain_loader = loader
    load_btn.clicked.connect(loader.show_dialog)
    
    checkbox_layout.addWidget(load_btn)
    
    # --- RESET BUTTON (with “Are you sure?” guard) ---
    reset_btn = QtWidgets.QPushButton("↺")
    reset_btn.setToolTip("Reset to default brain")
    reset_btn.setFixedSize(50, 50)
    reset_btn.setStyleSheet("""
        QPushButton {
            background-color: #78909c;
            color: white;
            border: none;
            border-radius: 3px;
            font-weight: bold;
        }
        QPushButton:hover { background-color: #90a4ae; }
    """)

    def _confirm_reset():
        ans = QtWidgets.QMessageBox.question(
            network_tab,           # parent widget
            "Confirm Reset",
            "Reset all neuron positions to their default locations?\n\n"
            "Network structure (connections and weights) will be preserved.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        if ans == QtWidgets.QMessageBox.Yes:
            try:
                loader.reset_positions_to_default()
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    network_tab, "Error", f"Failed to reset positions:\n{e}"
                )
    
    reset_btn.clicked.connect(_confirm_reset)
    checkbox_layout.addWidget(reset_btn)


# =============================================================================
# SAVE/LOAD INTEGRATION API
# =============================================================================

def get_custom_brain_save_data() -> Optional[Dict]:
    """
    Get custom brain data for saving with game state.
    Returns None if using default brain.
    
    Call this from tamagotchi_logic.save_game() to include in save_data.
    """
    global _current_custom_brain, _current_custom_brain_name
    
    if _current_custom_brain is None:
        return None
    
    return {
        'is_custom_brain': True,
        'brain_name': _current_custom_brain_name,
        'brain_definition': _current_custom_brain,
        'source_file': _current_custom_brain_file,
    }


def has_custom_brain() -> bool:
    """Check if a custom brain is currently loaded."""
    return _current_custom_brain is not None


def get_custom_brain_name() -> Optional[str]:
    """Get the name of the currently loaded custom brain."""
    return _current_custom_brain_name


def validate_custom_brain_save(save_data: Dict) -> tuple[bool, str]:
    """
    Validate that a save file's custom brain can be restored.
    
    Returns:
        (is_valid, message) - is_valid=True if loadable, message explains any issues
    """
    custom_brain_data = save_data.get('custom_brain')
    
    if not custom_brain_data:
        return True, "Default brain (no custom brain)"
    
    if not custom_brain_data.get('is_custom_brain'):
        return True, "Default brain"
    
    brain_def = custom_brain_data.get('brain_definition')
    if not brain_def:
        return False, "Save contains custom brain flag but no brain definition!"
    
    # Check if brain definition looks valid
    if 'positions' not in brain_def and 'neurons' not in brain_def:
        return False, "Custom brain definition is corrupted (no neurons)"
    
    brain_name = custom_brain_data.get('brain_name', 'Unknown')
    return True, f"Custom brain: {brain_name}"


def restore_custom_brain_from_save(save_data: Dict, brain_widget) -> tuple[bool, str]:
    """
    Restore a custom brain from save data.
    
    Args:
        save_data: The loaded save data dict
        brain_widget: The BrainWidget to apply the brain to
        
    Returns:
        (success, message)
    """
    global _current_custom_brain, _current_custom_brain_name, _current_custom_brain_file
    
    custom_brain_data = save_data.get('custom_brain')
    
    if not custom_brain_data or not custom_brain_data.get('is_custom_brain'):
        # No custom brain - reset to default
        _current_custom_brain = None
        _current_custom_brain_name = None
        _current_custom_brain_file = None
        return True, "Using default brain"
    
    brain_def = custom_brain_data.get('brain_definition')
    brain_name = custom_brain_data.get('brain_name', 'Unknown')
    
    if not brain_def:
        return False, "Custom brain definition missing from save!"
    
    try:
        # Create a temporary loader to apply the brain
        loader = BrainLoader.__new__(BrainLoader)
        loader.brain_widget = brain_widget
        loader.network_tab = None
        
        # Parse and apply
        parsed = loader._parse(brain_def)
        if not parsed:
            return False, f"Could not parse custom brain '{brain_name}'"
        
        loader._apply(parsed)
        
        # Update global tracking
        _current_custom_brain = brain_def
        _current_custom_brain_name = brain_name
        _current_custom_brain_file = custom_brain_data.get('source_file')
        
        return True, f"Restored custom brain: {brain_name}"
        
    except Exception as e:
        return False, f"Error restoring custom brain: {e}"


def show_custom_brain_load_warning(parent, save_data: Dict) -> bool:
    """
    Show warning dialog when loading a save with custom brain.
    
    Returns True if user wants to proceed, False to cancel.
    """
    # VALIDATION FIX: Ensure parent is a QWidget or None
    if parent and not isinstance(parent, QtWidgets.QWidget):
        if hasattr(parent, 'mainwindow'):
            parent = parent.mainwindow
        elif hasattr(parent, 'central_widget'):
            parent = parent.central_widget
        else:
            # Fallback to None (desktop parent) to prevent crash
            parent = None

    custom_brain_data = save_data.get('custom_brain')
    
    if not custom_brain_data or not custom_brain_data.get('is_custom_brain'):
        return True  # No custom brain, no warning needed
    
    brain_name = custom_brain_data.get('brain_name', 'Unknown')
    source_file = custom_brain_data.get('source_file', 'Unknown')
    
    # Validate the brain can be restored
    is_valid, message = validate_custom_brain_save(save_data)
    
    if not is_valid:
        QtWidgets.QMessageBox.critical(
            parent,
            "Cannot Load Save",
            f"This save uses a custom brain that cannot be restored:\n\n"
            f"Brain: {brain_name}\n"
            f"Error: {message}\n\n"
            f"The save file may be corrupted."
        )
        return False
    
    # Show info dialog
    reply = QtWidgets.QMessageBox.question(
        parent,
        "Custom Brain Save",
        f"This save uses a custom brain architecture:\n\n"
        f"🧠 Brain: {brain_name}\n"
        f"📁 Original file: {source_file}\n\n"
        f"The brain definition is embedded in the save and will be restored.\n\n"
        f"Continue loading?",
        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        QtWidgets.QMessageBox.Yes
    )
    
    return reply == QtWidgets.QMessageBox.Yes


# =============================================================================
# BRAIN LOADER CLASS
# =============================================================================

class BrainLoader:
    """Handles brain file loading."""
    
    def __init__(self, network_tab):
        self.network_tab = network_tab
        self.brain_widget = network_tab.brain_widget
        self.brains_folder = self._find_brains_folder()
    
    def _find_brains_folder(self) -> Path:
        """Find or create custom_brains folder (one level up from Brain/)."""
        candidates = [
            Path(__file__).parent.parent / "custom_brains",  # Up from Brain/ to project root
            Path.cwd() / "custom_brains",
            Path(__file__).parent / "custom_brains",  # Fallback to Brain/custom_brains
        ]
        for p in candidates:
            if p.exists():
                return p
        
        # Create at project root level (one up from Brain/)
        default = candidates[0]
        default.mkdir(parents=True, exist_ok=True)
        return default
    
    def show_dialog(self):
        """Show the brain selection dialog."""
        dialog = BrainSelectDialog(self.brains_folder, self.network_tab)
        if dialog.exec_() == QtWidgets.QDialog.Accepted and dialog.selected_file:
            self.load_file(dialog.selected_file)
    
    def load_file(self, filepath: str) -> bool:
        """Load and apply a brain file."""
        global _current_custom_brain, _current_custom_brain_name, _current_custom_brain_file
        
        try:
            print(f"🧠 Loading brain: {filepath}")
            
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            brain = self._parse(data)
            if not brain:
                raise ValueError("Could not parse brain format")
            
            self._apply(brain)
            
            # 1. Send bindings to the live game logic
            if hasattr(self.network_tab, 'tamagotchi_logic'):
                logic = self.network_tab.tamagotchi_logic
                if hasattr(logic, 'neuron_output_monitor') and logic.neuron_output_monitor:
                    logic.neuron_output_monitor.load_bindings_from_brain(brain)
                    print(f"  ✓ Loaded {len(brain.get('output_bindings', []))} output bindings into Monitor")

                # --- FIX: Force-sync live sensor values immediately ---
                # This prevents the saved "0" value from overwriting the real sensor input
                # in the first frame after loading.
                if hasattr(logic, 'brain_hooks'):
                    print("  -> Syncing live sensor inputs...")
                    input_values = logic.brain_hooks.get_input_neuron_values()
                    
                    # Update widget state directly
                    bw = self.brain_widget
                    if hasattr(bw, 'state'):
                        bw.state.update(input_values)
                    
                    # Update internal simulation neurons if present
                    if hasattr(bw, 'neurons'):
                        for k, v in input_values.items():
                            if k in bw.neurons:
                                bw.neurons[k]['activation'] = v
                # --- END FIX ---

            # 2. UI OVERLAY SETUP
            # Check if the stats area exists. If not, create it manually.
            if hasattr(self.network_tab, '_create_functional_stats_area'):
                if not hasattr(self.network_tab, 'functional_stats_area') or self.network_tab.functional_stats_area is None:
                    print("  -> Creating functional stats area for overlay...")
                    self.network_tab._create_functional_stats_area()
            
            # Ensure the label has text so the widget has non-zero height!
            if hasattr(self.network_tab, 'functional_stats_label') and not self.network_tab.functional_stats_label.text():
                self.network_tab.functional_stats_label.setText("<b>🧠 Custom Brain Loaded</b><br>External Bindings Active")
                self.network_tab.functional_stats_label.show()

            # Initialize overlay if missing
            if hasattr(self.network_tab, 'functional_stats_area'):
                if not hasattr(self.network_tab, 'binding_overlay') or self.network_tab.binding_overlay is None:
                    try:
                        from .brain_network_tab_banners import BindingOverlay
                        self.network_tab.binding_overlay = BindingOverlay(self.network_tab, self.network_tab.functional_stats_area)
                        print("  -> BindingOverlay initialized")
                    except ImportError as e:
                        print(f"  ! Could not import BindingOverlay: {e}")

            # Update the overlay with data
            if hasattr(self.network_tab, 'binding_overlay') and self.network_tab.binding_overlay:
                bindings = brain.get('output_bindings', [])
                if bindings:
                    print(f"  -> Sending {len(bindings)} bindings to overlay")
                    self.network_tab.binding_overlay.update_bindings(bindings)

            # 3. Finalize
            _current_custom_brain = data
            _current_custom_brain_name = Path(filepath).stem
            _current_custom_brain_file = filepath
            
            self._update_worker()
            
            if hasattr(self.network_tab, 'update_metrics_display'):
                self.network_tab.update_metrics_display()
            
            if self.brain_widget:
                self.brain_widget.update()
            
            name = Path(filepath).stem
            QtWidgets.QMessageBox.information(
                self.network_tab, "Loaded",
                f"✅ {name}\n\nNeurons: {len(brain['positions'])}\nConnections: {len(brain['weights'])}\n\n"
                f"This brain will be saved with your game."
            )
            return True
            
        except Exception as e:
            import traceback
            print(f"❌ Failed to load brain: {e}")
            traceback.print_exc()
            QtWidgets.QMessageBox.critical(self.network_tab, "Error", f"Failed to load:\n{e}")
            return False
    
    def reset_to_default(self):
        """Reset to the default brain."""
        global _current_custom_brain, _current_custom_brain_name, _current_custom_brain_file
        
        bw = self.brain_widget
        if not bw or not hasattr(bw, '_orig_backup'):
            QtWidgets.QMessageBox.warning(
                self.network_tab, "Cannot Reset",
                "No original brain backup available."
            )
            return
        
        backup = bw._orig_backup
        
        # Restore from backup
        if hasattr(bw, 'neuron_positions'):
            bw.neuron_positions.clear()
            bw.neuron_positions.update(backup['positions'])
        
        if hasattr(bw, 'weights'):
            bw.weights.clear()
            bw.weights.update(backup['weights'])
        
        if hasattr(bw, 'state'):
            # Only restore non-status neurons
            status = {'is_sick', 'is_eating', 'is_sleeping', 'pursuing_food', 'direction'}
            saved_status = {k: v for k, v in bw.state.items() if k in status}
            bw.state.clear()
            bw.state.update(backup['state'])
            bw.state.update(saved_status)
        
        if hasattr(bw, 'connections'):
            bw.connections = list(bw.weights.keys())
        
        # Clear custom brain tracking
        _current_custom_brain = None
        _current_custom_brain_name = None
        _current_custom_brain_file = None
        
        self._update_worker()
        
        if hasattr(self.network_tab, 'update_metrics_display'):
            self.network_tab.update_metrics_display()
        
        bw.update()
        
        QtWidgets.QMessageBox.information(
            self.network_tab, "Reset",
            "Brain reset to default configuration."
        )
    
    def _parse(self, data: Dict) -> Optional[Dict]:
        """Parse brain file to standard format."""
        result = {'positions': {}, 'weights': {}, 'state': {}, 'excluded': set(), 'output_bindings': []}
        
        # Format 1: Dosidicus format (connections as dict with "->")
        if 'neurons' in data and isinstance(data.get('connections'), dict):
            for name, nd in data['neurons'].items():
                pos = nd.get('position', [0, 0])
                result['positions'][name] = tuple(pos) if isinstance(pos, list) else pos
            for key, w in data.get('connections', {}).items():
                if '->' in str(key):
                    s, t = str(key).split('->')
                    result['weights'][(s, t)] = w
            result['state'] = data.get('state', {})
            result['excluded'] = set(data.get('excluded_neurons', []))
        
        # Format 2: Designer format (connections as list)
        elif 'neurons' in data and isinstance(data.get('connections'), list):
            for name, nd in data['neurons'].items():
                pos = nd.get('position', [0, 0])
                result['positions'][name] = tuple(pos) if isinstance(pos, list) else pos
                result['state'][name] = nd.get('activation', 50.0)
            for c in data.get('connections', []):
                if c.get('source') and c.get('target'):
                    result['weights'][(c['source'], c['target'])] = c.get('weight', 0.1)
            result['excluded'] = set(data.get('excluded_neurons', []))
        
        # Format 3: Layer format
        elif 'layers' in data:
            for i, layer in enumerate(data['layers']):
                neurons = layer.get('neurons', [])
                y = 80 + i * 150
                for j, name in enumerate(neurons):
                    x = 100 + (j + 1) * (700 // (len(neurons) + 1))
                    result['positions'][name] = (x, y)
                    result['state'][name] = 50.0
            for c in data.get('custom_connections', []):
                if c.get('source') and c.get('target'):
                    result['weights'][(c['source'], c['target'])] = c.get('weight', 0.1)
        else:
            return None
        
        # Parse output bindings
        result['output_bindings'] = data.get('output_bindings', [])
        
        # Defaults
        for n in result['positions']:
            if n not in result['state']:
                result['state'][n] = 50.0
        
        status = {'is_sick', 'is_eating', 'is_sleeping', 'pursuing_food', 'direction'}
        result['excluded'].update(status)
        
        return result if result['positions'] else None
    
    def _apply(self, brain: dict):
        """Apply parsed brain data to the current brain widget."""
        bw = self.brain_widget
        
        # Apply positions
        if 'positions' in brain:
            if hasattr(bw, 'neuron_positions'):
                bw.neuron_positions.clear()
                bw.neuron_positions.update(brain['positions'])
                
        # --- FIX: Ensure mandatory sensors are present ---
        # If the custom brain deleted core sensors, the game logic will break.
        # We restore them using original positions (or default) so inputs still work.
        MANDATORY_SENSORS = {
            'can_see_food', 'external_stimulus', 'plant_proximity', 
            'is_eating', 'is_sleeping', 'is_sick', 'is_fleeing', 'is_startled', 
            'pursuing_food'
        }
        
        restored_sensors = 0
        if hasattr(bw, 'original_neuron_positions'):
            for sensor in MANDATORY_SENSORS:
                if sensor not in bw.neuron_positions:
                    if sensor in bw.original_neuron_positions:
                        bw.neuron_positions[sensor] = bw.original_neuron_positions[sensor]
                        # Also ensure it has a state entry
                        if hasattr(bw, 'state') and sensor not in bw.state:
                            bw.state[sensor] = 0.0
                        restored_sensors += 1
        
        if restored_sensors > 0:
            print(f"🔧 Restored {restored_sensors} mandatory sensor neurons missing from custom brain")
        
        # Apply weights/connections
        if 'weights' in brain:
            if hasattr(bw, 'weights'):
                bw.weights.clear()
                bw.weights.update(brain['weights'])
        
        # Apply state if present (neuron activations)
        if 'state' in brain:
            if hasattr(bw, 'state'):
                bw.state.clear()
                bw.state.update(brain['state'])

        # Populate bw.neurons for synchronous simulation fallback
        if hasattr(bw, 'neurons'):
            bw.neurons = {}
            for name in bw.neuron_positions:
                # Check if this is a binary/sensor neuron
                is_sensor = hasattr(bw, 'is_binary_neuron') and bw.is_binary_neuron(name)
                
                # FIX: Sensors get 1.0 decay so they persist. 0.0 decay zeroes them out instantly.
                bw.neurons[name] = {
                    'activation': bw.state.get(name, 50.0),
                    'decay': 1.0 if is_sensor else 0.9, 
                    'noise': 0.0
                }
        
        # Apply excluded neurons
        if 'excluded' in brain:
            if hasattr(bw, 'excluded_neurons'):
                bw.excluded_neurons = list(brain['excluded'])
        
        # === OUTPUT BINDINGS (Neuron → Behavior) ===
        output_bindings_data = brain.get('output_bindings', [])
        
        if output_bindings_data:
            # Find the NeuronOutputMonitor
            monitor = None
            logic = getattr(bw, 'tamagotchi_logic', None)
            if logic and hasattr(logic, 'neuron_output_monitor'):
                monitor = logic.neuron_output_monitor
            # Fallback if attached differently
            elif hasattr(bw, 'parent') and hasattr(bw.parent(), 'tamagotchi_logic'):
                monitor = bw.parent().tamagotchi_logic.neuron_output_monitor
            
            if monitor:
                # Load the bindings
                monitor.bindings = []  # Clear old ones
                loaded_count = 0
                for bind_data in output_bindings_data:
                    try:
                        binding = NeuronOutputBinding.from_dict(bind_data)
                        monitor.bindings.append(binding)
                        loaded_count += 1
                    except Exception as e:
                        print(f"[BrainLoader] Failed to load binding: {e}")
                
                print(f"[NeuronOutputMonitor] Loaded {loaded_count} neuron output bindings")
                
                # Use the actual monitor() method to trigger initial thresholds
                if hasattr(bw, 'state') and bw.state:
                    # Convert state values to float where needed
                    activations = {}
                    for name, value in bw.state.items():
                        try:
                            activations[name] = float(value)
                        except (TypeError, ValueError):
                            activations[name] = 100.0 if value else 0.0
                    
                    # Trigger the monitor with current activations
                    monitor.monitor(activations)
                    print("[NeuronOutputMonitor] Initial neuron activations processed via monitor()")
                else:
                    print("[NeuronOutputMonitor] ⚠️ No state data available for initial trigger")
            else:
                print("[NeuronOutputMonitor] ⚠️ Monitor not found — bindings saved but not activated")
        
        # Keep a copy on the widget for saving/exporting later
        bw.output_bindings = output_bindings_data
        
        # Update related attributes safely
        if hasattr(bw, 'connections'):
            bw.connections = list(brain['weights'].keys())
        if hasattr(bw, 'visible_neurons'):
            bw.visible_neurons = set(bw.neuron_positions.keys()) if hasattr(bw, 'neuron_positions') else set()
        if hasattr(bw, 'original_neuron_positions') and hasattr(bw, 'neuron_positions'):
            bw.original_neuron_positions = dict(bw.neuron_positions)
        if hasattr(bw, 'original_neurons') and hasattr(bw, 'neuron_positions'):
            status = {'is_sick', 'is_eating', 'is_sleeping', 'pursuing_food', 'direction'}
            bw.original_neurons = [n for n in bw.neuron_positions if n not in status]
        if hasattr(bw, 'communication_events') and hasattr(bw, 'neuron_positions'):
            bw.communication_events = {n: 0 for n in bw.neuron_positions}
    
    def _update_worker(self):
        """Update BrainWorker cache if available."""
        try:
            worker = None
            parent = self.network_tab.parent() if self.network_tab else None
            while parent:
                if hasattr(parent, 'brain_worker'):
                    worker = parent.brain_worker
                    break
                parent = parent.parent()
            
            if not worker:
                print("⚠️ BrainWorker not found - skipping cache update")
                return
            
            # Try to update worker cache - different versions may have different APIs
            bw = self.brain_widget
            
            if hasattr(worker, 'update_cache') and callable(getattr(worker, 'update_cache')):
                worker.update_cache(
                    state=bw.state,
                    weights=bw.weights,
                    neuron_positions=bw.neuron_positions,
                    config=getattr(bw, 'config', None),
                    excluded_neurons=getattr(bw, 'excluded_neurons', []),
                    learning_rate=getattr(bw, 'learning_rate', 0.1),
                    new_neurons=bw.neurogenesis_data.get('new_neurons', []) if hasattr(bw, 'neurogenesis_data') else []
                )
                print("✅ BrainWorker cache updated")
            elif hasattr(worker, 'set_brain_data') and callable(getattr(worker, 'set_brain_data')):
                worker.set_brain_data(bw.state, bw.weights, bw.neuron_positions)
                print("✅ BrainWorker data updated")
            else:
                # Just update the worker's direct references if it has them
                if hasattr(worker, 'state'):
                    worker.state = bw.state
                if hasattr(worker, 'weights'):
                    worker.weights = bw.weights
                if hasattr(worker, 'neuron_positions'):
                    worker.neuron_positions = bw.neuron_positions
                print("✅ BrainWorker references updated")
                
        except Exception as e:
            print(f"⚠️ Could not update BrainWorker: {e}")
            # Non-fatal - brain still loads, just learning might need restart

    def reset_positions_to_default(self):
        """Reset only neuron positions to defaults, preserving network structure"""
        bw = self.brain_widget
        if not bw or not hasattr(bw, '_orig_backup'):
            raise ValueError("No original brain backup available")
        
        # Reset positions only
        for neuron in list(bw.neuron_positions.keys()):
            if neuron in bw._orig_backup['positions']:
                bw.neuron_positions[neuron] = bw._orig_backup['positions'][neuron]
        
        # Update displays
        if hasattr(self.network_tab, 'update_metrics_display'):
            self.network_tab.update_metrics_display()
        
        # Repaint
        bw.update()
        
        print("✅ Neuron positions reset to defaults")


# =============================================================================
# BRAIN SELECTION DIALOG
# =============================================================================

class BrainSelectDialog(QtWidgets.QDialog):
    """Simple dialog to select a brain file."""
    
    def __init__(self, brains_folder: Path, parent=None):
        super().__init__(parent)
        self.brains_folder = brains_folder
        self.selected_file = None
        self.setWindowTitle("Load Custom Brain")
        self.setMinimumSize(450, 350)
        self._setup_ui()
        self._refresh()
    
    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        # List
        self.list = QtWidgets.QListWidget()
        self.list.setStyleSheet("font-size: 11pt;")
        self.list.itemDoubleClicked.connect(self.accept)
        self.list.currentRowChanged.connect(self._on_select)
        layout.addWidget(self.list)
        
        # Info
        self.info = QtWidgets.QLabel("Select a brain file")
        self.info.setStyleSheet("background: #f0f0f0; padding: 8px; border-radius: 4px;")
        self.info.setWordWrap(True)
        layout.addWidget(self.info)
        
        # Buttons
        btns = QtWidgets.QHBoxLayout()
        
        browse = QtWidgets.QPushButton("Browse...")
        browse.clicked.connect(self._browse)
        btns.addWidget(browse)
        
        folder = QtWidgets.QPushButton("Open Folder")
        folder.clicked.connect(self._open_folder)
        btns.addWidget(folder)
        
        btns.addStretch()
        
        cancel = QtWidgets.QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)
        
        load = QtWidgets.QPushButton("Load")
        load.setStyleSheet("background: #5c6bc0; color: white; font-weight: bold;")
        load.clicked.connect(self.accept)
        btns.addWidget(load)
        
        layout.addLayout(btns)
        
        # Hint
        hint = QtWidgets.QLabel(f"Folder: {self.brains_folder}")
        hint.setStyleSheet("color: #888; font-size: 9pt;")
        layout.addWidget(hint)
    
    def _refresh(self):
        self.list.clear()
        files = list(self.brains_folder.glob("*.json")) if self.brains_folder.exists() else []
        
        if not files:
            item = QtWidgets.QListWidgetItem("(No brain files - click Browse)")
            item.setFlags(item.flags() & ~QtCore.Qt.ItemIsSelectable)
            self.list.addItem(item)
            return
        
        for f in sorted(files):
            item = QtWidgets.QListWidgetItem(f"🧠 {f.stem}")
            item.setData(QtCore.Qt.UserRole, str(f))
            self.list.addItem(item)
    
    def _on_select(self, row):
        item = self.list.item(row)
        if not item:
            return
        path = item.data(QtCore.Qt.UserRole)
        if not path:
            return
        
        try:
            with open(path) as f:
                data = json.load(f)
            neurons = len(data.get('neurons', {}))
            conns = data.get('connections', {})
            conn_count = len(conns) if isinstance(conns, (dict, list)) else 0
            meta = data.get('metadata', {})
            name = meta.get('name', Path(path).stem)
            desc = meta.get('description', '')
            self.info.setText(f"<b>{name}</b><br>Neurons: {neurons} | Connections: {conn_count}<br>{desc}")
        except:
            self.info.setText("Could not read file")
    
    def _browse(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select Brain", str(self.brains_folder), "JSON (*.json)"
        )
        if path:
            self.selected_file = path
            self.accept()
    
    def _open_folder(self):
        import subprocess, sys
        folder = str(self.brains_folder)
        if sys.platform == 'win32':
            subprocess.run(['explorer', folder])
        elif sys.platform == 'darwin':
            subprocess.run(['open', folder])
        else:
            subprocess.run(['xdg-open', folder])
    
    def accept(self):
        if not self.selected_file:
            item = self.list.currentItem()
            if item:
                self.selected_file = item.data(QtCore.Qt.UserRole)
        if self.selected_file:
            super().accept()