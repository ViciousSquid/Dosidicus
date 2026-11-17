"""Switching the Brain Tool between the running game and the Brain Designer.
"""
import logging
from PyQt5 import QtCore, QtWidgets

_LOG = logging.getLogger(__name__)

# 2.6.1.0 Robust import for Designer
_DESIGNER_AVAILABLE = False
try:
    from .designer_window import BrainDesignerWindow
    _DESIGNER_AVAILABLE = True
except Exception as e:
    _LOG.warning('Handled exception', exc_info=True)
    print(f"Warning: BrainDesignerWindow could not be imported: {type(e).__name__}: {e}")
    try:
        from src.designer_window import BrainDesignerWindow
        _DESIGNER_AVAILABLE = True
    except Exception as e2:
        _LOG.warning('Handled exception', exc_info=True)
        print(f"Warning: src fallback also failed: {type(e2).__name__}: {e2}")


class DesignerModeMixin:
    """Part of SquidBrainWindow (see brain_tool.py); not used on its own."""

    def _check_bridge_import(self):
        """Check if an external designer has pushed a new brain state."""
        # Don't import if we are currently IN the embedded designer mode
        if self.designer_view:
            return

        try:
            from .brain_state_bridge import consume_pending_import
            data = consume_pending_import()
            
            if data:
                print(">> 📥 Received external brain import from Designer")
                
                # Use the existing apply logic which handles neurons, connections, and bindings
                self.apply_designer_state(data)
                
                # Visual feedback
                if hasattr(self, 'status_bar'):
                    self.status_bar.showMessage("✨ Brain updated from external Designer", 5000)
                else:
                    print("✨ Brain updated successfully")
                    
        except ImportError:
            pass
        except Exception as e:
            _LOG.warning('Handled exception', exc_info=True)
            print(f"Error applying external import: {e}")

    def switch_to_designer_mode(self):
        """
        Replaces the main tab view with the Brain Designer embedded window.
        Includes extensive fixes for blank canvas and missing connection issues.
        """
        if not _DESIGNER_AVAILABLE:
            QtWidgets.QMessageBox.warning(self, "Error", "Brain Designer module not found.")
            return

        if not hasattr(self, 'brain_widget'): 
            return

        print(">> Switching to Designer Mode...")

        # 1. Pause simulation
        self._was_paused_before_designer = self.is_paused
        
        # Pause game logic via UI to ensure "SIMULATION PAUSED" overlay appears
        if self.tamagotchi_logic:
            # Check if we can route through UI for visual feedback
            if hasattr(self.tamagotchi_logic, 'user_interface') and \
               hasattr(self.tamagotchi_logic.user_interface, 'set_simulation_speed'):
                self.tamagotchi_logic.user_interface.set_simulation_speed(0)
            else:
                # Fallback to logic-only pause (no overlay)
                self.tamagotchi_logic.set_simulation_speed(0)
        else:
            self.set_pause_state(True)
        
        # 2. Capture state
        current_state = self.get_brain_state()
        
        # The designer needs a rich 'neurons' dictionary with types and positions
        if 'neurons' not in current_state:
            current_state['neurons'] = {}
            
            # Helper sets for identifying neuron types
            core_neurons = {'hunger', 'happiness', 'cleanliness', 'sleepiness', 
                           'satisfaction', 'anxiety', 'curiosity'}
            
            for name, pos in self.brain_widget.neuron_positions.items():
                # Determine type
                if name in core_neurons:
                    ntype = 'core'
                elif name == 'can_see_food' or name in getattr(self.brain_widget, 'input_sensors', []):
                    ntype = 'sensor'
                elif name.startswith('connector') or self.brain_widget.is_connector_neuron(name):
                    ntype = 'connector'
                else:
                    ntype = 'hidden' 
                
                # Get existing color
                color = self.brain_widget.state_colors.get(name, (200, 200, 200))
                
                # Build the rich object
                current_state['neurons'][name] = {
                    'name': name,
                    'position': pos,
                    'neuron_type': ntype, # Critical for Designer validation
                    'type': ntype,
                    'is_binary': self.brain_widget.is_binary_neuron(name),
                    'color': color,
                    'activation': self.brain_widget.state.get(name, 0.0)
                }
            print(f"   [Fix] Constructed {len(current_state['neurons'])} neuron records")

        # The designer prefers a 'connections' list of dicts.
        # We build this explicitly from the brain_widget weights to ensure links appear.
        
        connections_list = []
        
        # Source: Direct from brain_widget weights
        # We bypass 'weights_list' to ensure we get the most up-to-date dict structure
        if hasattr(self.brain_widget, 'weights'):
            for (src, dst), weight in self.brain_widget.weights.items():
                connections_list.append({
                    'source': str(src),
                    'target': str(dst),
                    'weight': float(weight)
                })

        # Inject into state
        current_state['connections'] = connections_list
        print(f"   [Fix] Constructed {len(connections_list)} connection records")

        # 3. Hide game tabs
        self.tabs.hide()
        
        # 4. Initialize Designer
        self.designer_view = BrainDesignerWindow(self, embedded_mode=True)
        self.designer_view.setWindowFlags(QtCore.Qt.Widget)
        
        # 5. Load State
        loaded = False
        if hasattr(self.designer_view, 'load_from_brain_widget_state'):
            try:
                # This calls converter which now sees our nice 'neurons' and 'connections' keys
                loaded = self.designer_view.load_from_brain_widget_state(current_state)
            except Exception as e:
                _LOG.warning('Handled exception', exc_info=True)
                print(f"Standard load failed: {e}")
        
        if not loaded:
            # Fallback manual loading
            try:
                from designer_core import BrainDesign
                design = BrainDesign.from_dosidicus_format(current_state)
                self.designer_view.design = design
                self.designer_view.refresh_all()
                loaded = True
            except Exception as e:
                _LOG.warning('Handled exception', exc_info=True)
                print(f"Critical: Failed to load brain state into designer: {e}")

        # 6. Setup Return Signal & Layout
        self.designer_view.exitRequested.connect(self.switch_to_game_mode)
        self.layout.addWidget(self.designer_view)
        
        # [FIX] Force layout update and delayed refresh to ensure canvas draws
        self.central_widget.updateGeometry()
        
        # Force an immediate refresh cycle
        if self.designer_view:
            self.designer_view.refresh_all()
            
        # Schedule refreshes to catch layout settling
        QtCore.QTimer.singleShot(50, self._force_designer_refresh)
        QtCore.QTimer.singleShot(200, self._force_designer_refresh)

        # 6. Setup Return Signal & Layout
        self.designer_view.exitRequested.connect(self.switch_to_game_mode)
        self.layout.addWidget(self.designer_view)
        
        # [FIX] Force layout update and delayed refresh to ensure canvas draws
        self.central_widget.updateGeometry()
        
        # Force an immediate refresh
        if self.designer_view:
            self.designer_view.refresh_all()
            
        # Schedule a second refresh to catch layout settling
        QtCore.QTimer.singleShot(100, self._force_designer_refresh)

    def _force_designer_refresh(self):
        """Helper to center and refresh designer after layout settles."""
        if self.designer_view and hasattr(self.designer_view, 'canvas'):
            # Force scene rect update based on items
            if hasattr(self.designer_view.canvas, 'scene') and self.designer_view.canvas.scene:
                items_rect = self.designer_view.canvas.scene.itemsBoundingRect()
                if not items_rect.isEmpty():
                    self.designer_view.canvas.scene.setSceneRect(
                        items_rect.adjusted(-200, -200, 200, 200)
                    )
            
            # Recalculate view center
            self.designer_view.canvas.center_on_neurons()
            self.designer_view.canvas.viewport().update()

    def switch_to_game_mode(self):
        """
        Restores the game view.
        Includes fixes for blank brain widget issues.
        """
        if not self.designer_view:
            return

        print(">> Switching back to Game Mode...")

        # 1. Get Data from Designer
        new_design_data = self.designer_view.get_current_design_state()
        
        # 2. Cleanup Designer
        self.layout.removeWidget(self.designer_view)
        self.designer_view.deleteLater()
        self.designer_view = None
        
        # 3. Restore Tabs
        self.tabs.show()
        
        # 4. Apply State
        if new_design_data:
            self.apply_designer_state(new_design_data)
        
        # 5. Restore Pause State
        if not self._was_paused_before_designer:
            if self.tamagotchi_logic:
                # Route through UI to remove "SIMULATION PAUSED" overlay and update menu
                if hasattr(self.tamagotchi_logic, 'user_interface') and \
                   hasattr(self.tamagotchi_logic.user_interface, 'set_simulation_speed'):
                    self.tamagotchi_logic.user_interface.set_simulation_speed(1)
                else:
                    self.tamagotchi_logic.set_simulation_speed(1) # Resume logic only
            else:
                self.set_pause_state(False)
            
        # Mark dirty immediately
        self.brain_widget.mark_render_dirty()
        
        # Explicitly invoke the offscreen render request logic
        if hasattr(self.brain_widget, '_request_render'):
            # Reset throttling to ensure request goes through
            self.brain_widget._last_render_request = 0 
            self.brain_widget._request_render()
            
        # Force Qt Repaint
        self.brain_widget.update()
        self.brain_widget.repaint()
        
        print(">> Game Mode Restored")

    def apply_designer_state(self, data):
        """
        Applies state from Designer to BrainWidget.
        Robustly handles weights/connections in list or dict format.
        """
        # 1. Update Weights
        new_weights = {}
        
        # Check for 'connections' (List of dicts OR Dict of key->val)
        connections = data.get('connections')
        
        # If connections is missing, check 'weights' (Legacy dict)
        if not connections:
            connections = data.get('weights', {})

        if isinstance(connections, dict):
            for key, weight in connections.items():
                # Handle 'src->dst' (Designer) or 'src|dst' (Legacy)
                if '->' in key:
                    s, t = key.split('->')
                    new_weights[(s, t)] = float(weight)
                elif '|' in key:
                    s, t = key.split('|')
                    new_weights[(s, t)] = float(weight)
                    
        elif isinstance(connections, list):
            # List of dicts: [{'source': 'A', 'target': 'B', 'weight': 0.5}, ...]
            for conn in connections:
                if 'source' in conn and 'target' in conn:
                    new_weights[(conn['source'], conn['target'])] = float(conn.get('weight', 0.5))

        if new_weights:
            self.brain_widget.weights = new_weights
            print(f"   [Fix] Applied {len(new_weights)} connections from designer")

        # 2. Update Positions
        if 'neurons' in data:
            new_positions = {}
            for name, info in data['neurons'].items():
                if 'position' in info:
                    new_positions[name] = tuple(info['position'])

                # Initialize new neurons if missing
                if name not in self.brain_widget.state:
                    self.brain_widget.state[name] = 50.0
                    # Apply color if present
                    if 'color' in info:
                        self.brain_widget.state_colors[name] = tuple(info['color'])
                    elif name not in self.brain_widget.state_colors:
                        self.brain_widget.state_colors[name] = (200, 200, 200)

            self.brain_widget.neuron_positions = new_positions

            # Everything derived from the neuron set has to follow, or the
            # widget ends up with weights for neurons it will not draw and
            # state entries for neurons the design deleted.
            removed = [n for n in list(self.brain_widget.state.keys())
                       if n not in new_positions
                       and n not in self.brain_widget.excluded_neurons
                       and n not in ('direction', 'position', 'neurogenesis_active')]
            for name in removed:
                self.brain_widget.state.pop(name, None)

            if hasattr(self.brain_widget, 'visible_neurons'):
                # A neuron the Designer just created was never added here, and
                # visible_neurons is the gate the renderer uses - so it existed
                # in the network but was invisible on screen.
                self.brain_widget.visible_neurons = set(new_positions.keys())

            if isinstance(getattr(self.brain_widget, 'neurons', None), dict):
                for name in list(self.brain_widget.neurons):
                    if name not in new_positions:
                        self.brain_widget.neurons.pop(name, None)

            self.brain_widget.weights = {
                (src, dst): w for (src, dst), w in self.brain_widget.weights.items()
                if src in new_positions and dst in new_positions
            }

            if hasattr(self.brain_widget, '_update_worker_cache'):
                self.brain_widget._update_worker_cache()

        # 3. Update Bindings
        if 'output_bindings' in data and hasattr(self.tamagotchi_logic, 'neuron_output_monitor'):
            self.brain_widget.output_bindings = data['output_bindings']
            self.tamagotchi_logic.neuron_output_monitor.load_bindings_from_brain(data)

        # 4. Trigger Updates
        self.brain_widget.mark_render_dirty()
        self.brain_widget.update()
        
        # Refresh Network Tab Stats
        if hasattr(self, 'network_tab'):
            self.network_tab.update_metrics_display()
