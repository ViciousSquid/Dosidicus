import logging

_LOG = logging.getLogger(__name__)

import time
import random
from PyQt5 import QtCore, QtGui, QtWidgets

from .config_manager import ConfigManager
from .brain_widget import BrainWidget
from .brain_worker import BrainWorker 
from .brain_dialogs import StimulateDialog
from .brain_utils import ConsoleOutput
from .brain_network_tab import NetworkTab
from .brain_about_tab import AboutTab
from .brain_learning_tab import NeuralNetworkVisualizerTab
from .brain_memory_tab import MemoryTab
from .brain_decisions_tab import DecisionsTab
from .brain_personality_tab import PersonalityTab
from .brain_statistics_tab import StatisticsTab
from .brain_knowledge_tab import KnowledgeTab
from .task_manager import TaskManagerWindow
from .localisation import Localisation, set_language
from .brain_ui_utils import set_plain_text

# 2.6.1.0 Define _HAS_BRAIN_BRIDGE variable
_HAS_BRAIN_BRIDGE = False
try:
    from .brain_state_bridge import (
        is_game_running,  # noqa: F401
        import_brain_state_for_designer  # noqa: F401
    )
    _HAS_BRAIN_BRIDGE = True
except ImportError:
    _HAS_BRAIN_BRIDGE = False
    print("Warning: brain_state_bridge not found in brain_tool")

from .brain_tool_state import BrainStateMixin, split_connections  # noqa: F401
from .brain_tool_designer import DesignerModeMixin
from .brain_tool_export import BrainExportMixin
from .brain_tool_learning import LearningViewsMixin
from .brain_tool_memory import MemoryViewsMixin
from .brain_tool_worker import BrainWorkerSupervisionMixin


class SquidBrainWindow(
        BrainStateMixin,
        DesignerModeMixin,
        BrainExportMixin,
        LearningViewsMixin,
        MemoryViewsMixin,
        BrainWorkerSupervisionMixin,
        QtWidgets.QMainWindow,
):
    def __init__(self, tamagotchi_logic, debug_mode=False, config=None, show_decorations_callback=None):
        # Force language sync before any tabs are created
        if config and hasattr(config, 'get_language'):
            set_language(config.get_language())
        
        super().__init__()

        # Initialize font size FIRST
        from .display_scaling import DisplayScaling

        self.base_font_size = DisplayScaling.font_size(10)
        self.debug_mode = debug_mode
        self.config_manager = ConfigManager()      # real manager
        self.config        = self.config_manager   # keep old name for compat
        self.tamagotchi_logic = tamagotchi_logic
        self.initialized = False
        self.is_paused = False
        self.show_decorations_callback = show_decorations_callback

        self.setWindowTitle("Brain Tool")

        screen = QtWidgets.QApplication.primaryScreen()

        # Opening size, in absolute pixels (no DisplayScaling). Override either
        # of these in config.ini under [Display] rather than editing the source.
        display_cfg = {}
        try:
            display_cfg = self.config_manager.get_display_settings() or {}
        except Exception:
            display_cfg = {}
        final_width = int(display_cfg.get('brain_tool_width', 1300))
        final_height = int(display_cfg.get('brain_tool_height', 1100))

        # The size set here is the size the window OPENS at, and nothing else is
        # allowed to override it. Qt will not honour resize() below a window's
        # minimum size, and a QMainWindow's implicit minimum is whatever its
        # deepest child demands - so a single long, unwrapped status label was
        # enough to snap this window open ~350px wider than the value above and
        # make editing that value look like it did nothing. Declaring the
        # minimum explicitly puts the opening width back under our control.
        # It is a MINIMUM, not a fixed size: the window stays freely resizable,
        # and the user can drag it larger or smaller afterwards.
        self.setMinimumSize(DisplayScaling.scale(480), DisplayScaling.scale(360))

        # In real pixels, like every size in the game: in points on a Retina
        # Mac, where the screen reports points (DisplayScaling).
        ratio = max(1.0, screen.devicePixelRatio())
        final_width, final_height = int(final_width / ratio), int(final_height / ratio)

        # No larger than the screen allows - by the same measure on every
        # system (the screen less one fixed allowance for a taskbar or dock),
        # so the window opens the same size on all of them.
        from .desktop_style import usable_size
        usable_width, usable_height = usable_size(screen)
        final_width = min(final_width, usable_width)
        final_height = min(final_height, usable_height)

        self.resize(final_width, final_height) # Resize the window with clamped dimensions

        # Position window properly in the top-right corner of the *available* screen geometry
        # x-coordinate: right edge of available geometry minus window width, then shift left by 200 pixels
        # Top right of the area the game lays its windows out in, 100 pixels
        # in from the edge: the same spot on every system
        # (desktop_style.layout_area), not wherever this system's bars leave.
        from .desktop_style import layout_area
        area = layout_area(screen)
        x_pos = max(area.left(), area.right() - final_width - 100)
        y_pos = area.top()
        self._placed_at = (x_pos, y_pos)

        self.move(x_pos, y_pos)

        # Setup the central widget and main layout
        self.central_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.central_widget)

        self.layout = QtWidgets.QVBoxLayout()
        self.central_widget.setLayout(self.layout)

        # Create the brain widget first
        self.brain_widget = BrainWidget(self.config_manager, self.debug_mode, tamagotchi_logic=tamagotchi_logic)
        # Set parent so brain_widget can access network_tab via self.parent().network_tab
        self.brain_widget.setParent(self)

        # Initialize tab widget
        self.init_tabs()

        # On a Retina screen the opening size above is the design's share of
        # the screen, in points - but the tabs and controls are in points too
        # and do not shrink with it, so never smaller than they need.
        if ratio > 1.0:
            hint = self.sizeHint()
            width = min(max(final_width, hint.width()), usable_width)
            height = min(max(final_height, hint.height()), usable_height)
            if (width, height) != (final_width, final_height):
                self.resize(width, height)
                self._placed_at = (max(area.left(), area.right() - width - 100), area.top())
                self.move(*self._placed_at)

        # Set up timers
        self.init_timers()

        # Initialize memory update timer if needed
        if hasattr(self, 'memory_tab'):
            self.memory_update_timer = QtCore.QTimer(self)
            self.memory_update_timer.timeout.connect(self.update_memory_tab)
            self.memory_update_timer.start(5000)  # PERFORMANCE FIX: Update every 5 secs (was 2)

        
        # Set up worker thread
        self.brain_worker = BrainWorker(brain_widget=self.brain_widget)
        self.brain_worker.start()
        self._last_worker_activity = time.time()
        self._worker_healthy = True

        # Start periodic worker health monitoring
        self.health_timer = QtCore.QTimer(self)
        self.health_timer.timeout.connect(self.check_worker_health)
        self.health_timer.start(10000)  # Every 10 seconds
        
        # Connect worker signals for health monitoring
        self.brain_worker.neurogenesis_result.connect(self._on_worker_activity)
        self.brain_worker.hebbian_result.connect(self._on_worker_activity)
        self.brain_worker.state_update_result.connect(self._on_worker_activity)
        self.brain_worker.error_occurred.connect(self._on_worker_error)

        # Track pause state before entering designer
        self._was_paused_before_designer = False
        self.designer_view = None
        
        # ===== PERFORMANCE FIX: Share worker with brain_widget =====
        if hasattr(self.brain_widget, 'set_brain_worker'):
            self.brain_widget.set_brain_worker(self.brain_worker)
            print("🔗 Shared BrainWorker with brain_widget")
            
            # Immediately update cache with current state
            self.brain_widget._update_worker_cache()
            print("📦 Initial worker cache populated")
        
        # Store reference to prevent garbage collection
        self._brain_worker_ref = self.brain_worker
        
        # Ensure worker stays alive with initial work
        QtCore.QTimer.singleShot(1000, lambda: self._keep_worker_alive())
        
        # Initialize task manager AFTER worker is fully set up
        self.task_manager = TaskManagerWindow(self.brain_worker, parent=self)
        
        # Setup decorations window shortcut
        self.setup_decorations_shortcut()

        # Bridge Import Listener
        # Polls for designs pushed from the Designer window
        if _HAS_BRAIN_BRIDGE:
            self._bridge_timer = QtCore.QTimer(self)
            self._bridge_timer.timeout.connect(self._check_bridge_import)
            self._bridge_timer.start(1000)  # Check every 1 second


    def set_tamagotchi_logic(self, tamagotchi_logic):
        """Set the tamagotchi_logic reference and update all tabs"""
        print(f"SquidBrainWindow.set_tamagotchi_logic: {tamagotchi_logic is not None}")
        self.tamagotchi_logic = tamagotchi_logic
        
        # Update brain widget
        if hasattr(self, 'brain_widget'):
            self.brain_widget.tamagotchi_logic = tamagotchi_logic
            
            # 🔽 ADD THIS BLOCK: Load output bindings if they exist 🔽
            if (hasattr(self.brain_widget, 'output_bindings') and 
                self.brain_widget.output_bindings and
                hasattr(tamagotchi_logic, 'neuron_output_monitor') and
                tamagotchi_logic.neuron_output_monitor):
                
                tamagotchi_logic.neuron_output_monitor.load_bindings_from_brain({
                    'output_bindings': self.brain_widget.output_bindings
                })
                print(f"  ✓ Loaded {len(self.brain_widget.output_bindings)} output bindings into Monitor")
        
        # Update all tabs
        for tab_attr in [
            'memory_tab',
            'network_tab',
            'nn_viz_tab',
            'decisions_tab',
            'personality_tab',
            'statistics_tab',
            'about_tab',
        ]:
            if hasattr(self, tab_attr):
                tab = getattr(self, tab_attr)
                if hasattr(tab, 'set_tamagotchi_logic'):
                    tab.set_tamagotchi_logic(tamagotchi_logic)

    def setup_decorations_shortcut(self):
        """Setup keyboard shortcut for decorations window (D key)"""
        if self.show_decorations_callback:
            self.decorations_shortcut = QtWidgets.QShortcut(
                QtGui.QKeySequence(QtCore.Qt.Key_D), 
                self
            )
            self.decorations_shortcut.activated.connect(self.show_decorations_callback)

    def show_decorations_window(self):
        # Always show and activate the decorations window when D is pressed
        self.decoration_window.show()
        self.decoration_window.activateWindow()

    def set_debug_mode(self, enabled):
        """Properly set debug mode for brain window and all tabs"""
        self.debug_mode = enabled
        
        # Update brain widget's debug mode
        if hasattr(self, 'brain_widget'):
            self.brain_widget.debug_mode = enabled
        
        # Update all tabs
        for tab_name in ['network_tab', 'nn_viz_tab', 'memory_tab', 'decisions_tab', 'about_tab']:
            if hasattr(self, tab_name):
                tab = getattr(self, tab_name)
                if hasattr(tab, 'debug_mode'):
                    tab.debug_mode = enabled
        
        print(f"Brain window debug mode set to: {enabled}")

    def closeEvent(self, event):
        """Stop worker and timers when window closes"""
        if hasattr(self, 'health_timer') and self.health_timer.isActive():
            self.health_timer.stop()

        if hasattr(self, 'brain_worker') and self.brain_worker:
            self.brain_worker.stop()
            if self.brain_worker.isRunning():
                self.brain_worker.wait(5000)
        event.accept()

    def on_hebbian_countdown_finished(self):
        """Called when the Hebbian learning countdown reaches zero"""
        pass

    def init_inspector(self):
        self.inspector_action = QtWidgets.QAction("Neuron Inspector", self)
        self.inspector_action.triggered.connect(self.show_inspector)
        self.debug_menu.addAction(self.inspector_action)

    def show_inspector(self):
        if not hasattr(self, '_inspector') or not self._inspector or not self._inspector.isVisible(): # Check if visible
            # Pass the SquidBrainWindow instance (self) to NeuronInspector
            self._inspector = NeuronInspector(self, self.brain_widget)
        self._inspector.show()
        self._inspector.raise_()
        self._inspector.activateWindow() # Ensure it gets focus

    def debug_print(self, message):
        if self.debug_mode:
            print(f"DEBUG: {message}")

    def toggle_debug_mode(self, enabled):
        self.debug_mode = enabled
        self.debug_print(f"Debug mode {'enabled' if enabled else 'disabled'}")
        # Update stimulate button state
        if hasattr(self, 'stimulate_button'):
            self.stimulate_button.setEnabled(enabled)

    def init_tabs(self):
        # Get localisation instance
        loc = Localisation.instance()

        # Create tab widget
        self.tabs = QtWidgets.QTabWidget()
        self.layout.addWidget(self.tabs)

        # Set base font for all tab content
        base_font = QtGui.QFont()
        base_font.setPointSize(self.base_font_size)
        self.tabs.setFont(base_font)

        # Create and add existing tabs with Localized Titles
        self.network_tab = NetworkTab(self, self.tamagotchi_logic, self.brain_widget, self.config_manager, self.debug_mode)
        self.tabs.addTab(self.network_tab, loc.get("brain_network", "Network"))

        # Add our Neural Network Visualizer tab as the Learning tab
        self.nn_viz_tab = NeuralNetworkVisualizerTab(self, self.tamagotchi_logic, self.brain_widget, self.config, self.debug_mode)
        self.tabs.addTab(self.nn_viz_tab, loc.get("tab_learning", "Learning"))

        # Knowledge reads the brain's own provenance ledger - the same record
        # the organism writes as it learns. It is deliberately NOT a second
        # interpretation of the network.
        self.knowledge_tab = KnowledgeTab(self, self.tamagotchi_logic, self.brain_widget, self.config, self.debug_mode)
        self.tabs.addTab(self.knowledge_tab, loc.get("tab_knowledge", "Knowledge"))

        self.memory_tab = MemoryTab(self, self.tamagotchi_logic, self.brain_widget, self.config, self.debug_mode)
        self.tabs.addTab(self.memory_tab, loc.get("memory", "Memory"))

        self.decisions_tab = DecisionsTab(self, self.tamagotchi_logic, self.brain_widget, self.config, self.debug_mode)
        self.tabs.addTab(self.decisions_tab, loc.get("tab_decisions", "Decisions"))

        self.personality_tab = PersonalityTab(self, self.tamagotchi_logic, self.brain_widget, self.config, self.debug_mode)
        self.tabs.addTab(self.personality_tab, loc.get("tab_personality", "Personality"))

        # ADD THE NEW STATISTICS TAB HERE
        self.statistics_tab = StatisticsTab(self, self.tamagotchi_logic, self.brain_widget, self.config, self.debug_mode)
        self.tabs.addTab(self.statistics_tab, loc.get("statistics", "Statistics"))

        self.about_tab = AboutTab(self, self.tamagotchi_logic, self.brain_widget, self.config, self.debug_mode)
        self.tabs.addTab(self.about_tab, loc.get("tab_about", "About"))

        # Make sure all tabs have correct tamagotchi_logic reference
        for tab_name in ['memory_tab', 'network_tab', 'nn_viz_tab', 'knowledge_tab', 'decisions_tab', 'personality_tab', 'statistics_tab', 'about_tab']:
            if hasattr(self, tab_name):
                tab = getattr(self, tab_name)
                if hasattr(tab, 'set_tamagotchi_logic') and self.tamagotchi_logic:
                    tab.set_tamagotchi_logic(self.tamagotchi_logic)
                print(f"Set tamagotchi_logic for {tab_name}")

        # Pre-load the learning tab to make it responsive on first click
        if hasattr(self, 'nn_viz_tab'):
            if hasattr(self.nn_viz_tab, 'pre_load_data'):
                QtCore.QTimer.singleShot(700, self.nn_viz_tab.pre_load_data)

    def showEvent(self, event):
        """When the window is shown, put it where it was meant to go once
        more. A window placed before the system has given it a frame can end
        up a few pixels off (7 on Windows); placed again once it has one, and
        checked, it is where every other system has it."""
        super().showEvent(event)
        # Each time it is shown, until a player has moved it: the game shows
        # this window once while it starts, hidden again at once, and a
        # correction left to that showing never got to run.
        place = getattr(self, '_placed_at', None)
        if place is not None and not getattr(self, '_moved_by_player', False):
            near = (abs(self.pos().x() - place[0]) <= 64 and abs(self.pos().y() - place[1]) <= 64)
            if near:
                from .desktop_style import place_exactly
                place_exactly(self, *place)
            else:
                self._moved_by_player = True        # somewhere else: leave it there

    def init_timers(self):
        # Hebbian learning timer
        self.hebbian_timer = QtCore.QTimer()
        self.hebbian_timer.timeout.connect(self.brain_widget.perform_hebbian_learning)
        self.hebbian_timer.start(self.config.hebbian.get('learning_interval', 30000))
        
        # Hebbian countdown
        self.hebbian_countdown_seconds = int(self.config.hebbian.get('learning_interval', 30000) / 1000)

        # Add countdown timer
        self.countdown_timer = QtCore.QTimer()
        self.countdown_timer.timeout.connect(self.update_countdown)
        self.countdown_timer.start(1000)  # Update every second

        # Associations timer
        self.update_timer = QtCore.QTimer()
        self.update_timer.timeout.connect(self.update_associations)
        self.update_timer.start(10000)  # Update every 10 seconds
        self.last_update_time = time.time()
        self.update_threshold = 5  # Minimum seconds between updates


    def update_randomness_factors(self, randomness):
        """Update the randomness factors table"""
        self.random_factors_table.setRowCount(len(randomness))
        
        for i, (action, factor) in enumerate(randomness.items()):
            # Action name
            action_item = QtWidgets.QTableWidgetItem(action)
            self.random_factors_table.setItem(i, 0, action_item)
            
            # Random factor
            value_item = QtWidgets.QTableWidgetItem(f"{factor:.2f}")
            color = QtGui.QColor("darkgreen") if factor > 1.0 else QtGui.QColor("darkred")
            value_item.setForeground(color)
            self.random_factors_table.setItem(i, 1, value_item)


    def create_thought_node(self, text):
        node = QtWidgets.QGraphicsRectItem(0, 0, 250, 150)  # Increase node size
        node.setBrush(QtGui.QBrush(QtGui.QColor(240, 248, 255)))

        # Use QTextDocument for better text handling
        text_document = QtGui.QTextDocument()
        text_document.setPlainText(text)
        text_document.setTextWidth(230)  # Set text width to fit within the node

        # Create a QGraphicsTextItem with an empty string
        text_item = QtWidgets.QGraphicsTextItem()
        text_item.setDocument(text_document)
        text_item.setPos(10, 10)

        group = QtWidgets.QGraphicsItemGroup()
        group.addToGroup(node)
        group.addToGroup(text_item)
        return group

    def draw_connection(self, start, end, label):
        line = QtWidgets.QGraphicsLineItem(start[0]+200, start[1]+50, end[0], end[1]+50)
        line.setPen(QtGui.QPen(QtCore.Qt.darkGray, 2, QtCore.Qt.DashLine))
        self.decision_scene.addItem(line)

        arrow = QtWidgets.QGraphicsPolygonItem(
            QtGui.QPolygonF([QtCore.QPointF(0, -5), QtCore.QPointF(10, 0), QtCore.QPointF(0, 5)]))
        arrow.setPos(end[0], end[1]+50)
        arrow.setRotation(180 if start[0] > end[0] else 0)
        self.decision_scene.addItem(arrow)

        label_item = QtWidgets.QGraphicsTextItem(label)
        label_item.setPos((start[0]+end[0])/2, (start[1]+end[1])/2)
        self.decision_scene.addItem(label_item)

    
    def _clear_layout(self, layout):
        """Clear all widgets from the given layout"""
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def set_pause_state(self, is_paused):
        """Set pause state for the brain window and worker thread"""
        self.is_paused = is_paused
        
        # Set brain widget pause state
        if hasattr(self, 'brain_widget'):
            self.brain_widget.is_paused = is_paused
        
        # Control worker thread - CRITICAL for freezing everything
        if hasattr(self, 'brain_worker') and self.brain_worker:
            if is_paused:
                self.brain_worker.pause()
                self._pause_start_time = time.time() # Capture time when paused
                print("⏸️ BrainWorker paused")
            else:
                self.brain_worker.resume()
                
                # Adjust timestamps to account for pause duration
                if hasattr(self, '_pause_start_time'):
                    pause_duration = time.time() - self._pause_start_time
                    
                    # 1. Adjust Hebbian timer reference
                    if hasattr(self.brain_widget, 'last_hebbian_time'):
                        self.brain_widget.last_hebbian_time += pause_duration
                        
                    # 2. Adjust Neurogenesis timer reference
                    if hasattr(self.brain_widget, 'neurogenesis_data'):
                        self.brain_widget.neurogenesis_data['last_neuron_time'] += pause_duration
                        
                    # 3. Adjust Animation timer references in brain_widget to prevent jumps
                    if hasattr(self.brain_widget, '_last_animation_time'):
                        self.brain_widget._last_animation_time += pause_duration
                    
                    # 4. Adjust running weight animations
                    if hasattr(self.brain_widget, 'weight_animations'):
                        for anim in self.brain_widget.weight_animations:
                            anim['start_time'] += pause_duration
                            
                    # 5. Adjust reveal animations
                    if hasattr(self.brain_widget, 'neuron_reveal_animations'):
                        for anim in self.brain_widget.neuron_reveal_animations.values():
                            anim['start_time'] += pause_duration
                            
                    # 6. Adjust neurogenesis highlight
                    if hasattr(self.brain_widget, 'neurogenesis_highlight'):
                        self.brain_widget.neurogenesis_highlight['start_time'] += pause_duration

                print("▶️ BrainWorker resumed")

        # Manage timers based on pause state
        if is_paused:
            if hasattr(self, 'hebbian_timer'):
                self.hebbian_timer.stop()
        else:
            if hasattr(self, 'hebbian_timer'):
                self.hebbian_timer.start(self.config.hebbian['learning_interval'])

    def add_thought(self, thought):
        """Bridge method to forward thoughts to the decisions tab"""
        if hasattr(self, 'decisions_tab') and self.decisions_tab:
            # If we have a decisions tab, forward to its thought log
            if hasattr(self.decisions_tab, 'thought_log_text'):
                self.decisions_tab.thought_log_text.append(thought)
                # Auto-scroll to bottom
                scrollbar = self.decisions_tab.thought_log_text.verticalScrollBar()
                scrollbar.setValue(scrollbar.maximum())
            elif hasattr(self.decisions_tab, 'add_thought'):
                # Alternative: if the tab has its own add_thought method
                self.decisions_tab.add_thought(thought)
        else:
            # Fallback: print to console if no UI element available
            print(f"Thought: {thought}")

    def clear_thoughts(self):
        self.thoughts_text.clear()

    def init_decisions_tab(self):
        font = QtGui.QFont()
        font.setPointSize(self.base_font_size)
        # Add a label for decision history
        decision_history_label = QtWidgets.QLabel("Decision History:")
        self.decisions_tab_layout.addWidget(decision_history_label)

        # Add a text area to display decision history
        self.decision_history_text = QtWidgets.QTextEdit()
        self.decision_history_text.setReadOnly(True)
        self.decisions_tab_layout.addWidget(self.decision_history_text)

        # Add a label for decision inputs
        decision_inputs_label = QtWidgets.QLabel("Decision Inputs:")
        self.decisions_tab_layout.addWidget(decision_inputs_label)

        # Add a text area to display decision inputs
        self.decision_inputs_text = QtWidgets.QTextEdit()
        self.decision_inputs_text.setReadOnly(True)
        self.decisions_tab_layout.addWidget(self.decision_inputs_text)

    def update_decisions_tab(self, decision, decision_inputs):
        # Append the decision to the decision history
        self.decision_history_text.append(f"Decision: {decision}")

        # Display the decision inputs
        self.decision_inputs_text.clear()
        for key, value in decision_inputs.items():
            self.decision_inputs_text.append(f"{key}: {value}")

    def get_neuron_display_name(self, neuron):
        display_names = {
            "cleanliness": "Being clean",
            "sleepiness": "Being sleepy",
            "happiness": "Being happy",
            "hunger": "Being hungry",
            "satisfaction": "Satisfaction",
            "anxiety": "Being anxious",
            "curiosity": "Curiosity",
            "direction": "Direction"
        }
        return display_names.get(neuron, f"{neuron}")



    def get_neuron_value(self, value):
        # bool must be checked before int/float: bool is a subclass of int, so
        # an ordinary (int, float) test would catch True/False first and return
        # 1.0/0.0 instead of the intended 100.0/0.0.
        if isinstance(value, bool):
            return 100.0 if value else 0.0
        elif isinstance(value, (int, float)):
            return float(value)
        elif isinstance(value, str):
            # For string values (like 'direction'), return a default value
            return 75.0
        else:
            return 0.0

    def update_personality_effects(self, personality, weights, adjusted_weights):
        """Update the personality modifier display in the thinking tab"""
        # Convert enum to string if needed
        personality_str = getattr(personality, 'value', str(personality))
        
        self.personality_label.setText(f"Personality: {personality_str.capitalize()}")
        
        # Generate effect text based on weight differences
        effects_text = []
        for action, weight in weights.items():
            adjusted = adjusted_weights.get(action, weight)
            if abs(adjusted - weight) > 0.01:  # If there's a significant difference
                direction = "increases" if adjusted > weight else "decreases"
                effect = f"{action}: {direction} by {abs(adjusted - weight):.2f}"
                effects_text.append(effect)
        
        if effects_text:
            set_plain_text(self.personality_effects, "\n".join(effects_text))
        else:
            set_plain_text(self.personality_effects, "No significant personality effects")

    def update_brain(self, state):
        """Main update method to distribute state changes to all tabs"""
        if not self.initialized:
            self.initialized = True
            return  # Skip first update

        # Update the brain widget first
        self.brain_widget.update_state(state)

        # Forward updates to each tab that has an update method
        tabs_to_update = ['network_tab', 'nn_viz_tab', 'knowledge_tab', 'memory_tab', 'decisions_tab', 'personality_tab', 'about_tab']
        for tab_name in tabs_to_update:
            if hasattr(self, tab_name):
                tab = getattr(self, tab_name)
                if hasattr(tab, 'update_from_brain_state'):
                    tab.update_from_brain_state(state)


    def toggle_overview(self, state):
        if state == QtCore.Qt.Checked:
            self.overview_label.show()
        else:
            self.overview_label.hide()

    def init_console(self):
        self.console_output = QtWidgets.QTextEdit()
        self.console_output.setReadOnly(True)
        self.console_tab_layout.addWidget(self.console_output)
        self.console = ConsoleOutput(self.console_output)

    def create_button(self, text, callback, color):
        button = QtWidgets.QPushButton(text)
        button.clicked.connect(callback)
        button.setStyleSheet(f"background-color: {color}; border: 1px solid black; padding: 5px;")
        button.setFixedSize(200, 50)
        return button

    def stimulate_brain(self):
        dialog = StimulateDialog(self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            stimulation_values = dialog.get_stimulation_values()
            if stimulation_values is not None:
                self.brain_widget.update_state(stimulation_values)
                if self.tamagotchi_logic:
                    self.tamagotchi_logic.update_from_brain(stimulation_values)
                else:
                    print("Warning: tamagotchi_logic is not set. Brain stimulation will not affect the squid.")


    def update_neural_visualization(self, inputs):
        """Update the neural network visualization with current input values"""
        if not hasattr(self, 'neuron_items') or not self.neuron_items:
            self.setup_neural_visualization()
            return
        
        # Update neuron colors based on activation values
        for neuron, value in inputs.items():
            if neuron in self.neuron_items:
                # Only update numerical values
                if isinstance(value, (int, float)):
                    # Update stored value
                    self.neuron_items[neuron]["value"] = value
                    
                    # Calculate color based on value (0-100)
                    intensity = int(value * 2.55)  # Scale 0-100 to 0-255
                    
                    if neuron in ["hunger", "sleepiness", "anxiety"]:
                        # Red-based for "negative" neurons (more red = higher activation)
                        color = QtGui.QColor(255, 255 - intensity, 255 - intensity)
                    else:
                        # Blue/green-based for "positive" neurons (more color = higher activation)
                        color = QtGui.QColor(100, intensity, 255)
                    
                    # Update neuron ellipse color
                    self.neuron_items[neuron]["shape"].setBrush(QtGui.QBrush(color))
                    
                    # Make neurons pulse slightly based on value
                    scale = 1.0 + (value / 200)  # 1.0 to 1.5
                    rect = self.neuron_items[neuron]["shape"].rect()
                    center_x = rect.x() + rect.width()/2
                    center_y = rect.y() + rect.height()/2
                    new_width = 40 * scale
                    new_height = 40 * scale
                    self.neuron_items[neuron]["shape"].setRect(
                        center_x - new_width/2,
                        center_y - new_height/2,
                        new_width,
                        new_height
                    )
        
        # Update connection line widths and colors based on neuron activations
        for connection, items in self.connection_items.items():
            source, target = connection
            source_value = self.neuron_items.get(source, {}).get("value", 50)
            target_value = self.neuron_items.get(target, {}).get("value", 50)
            
            # Calculate connection strength based on both neuron activations
            # Higher when both neurons are highly activated
            connection_strength = (source_value * target_value) / 10000  # Scale to 0-1
            
            # Update line width and color
            pen_width = 1 + 3 * connection_strength
            
            # Get current brain connection weight if available
            weight = items.get("weight", 0)
            
            # Color based on weight (green for positive, red for negative)
            if weight > 0:
                pen_color = QtGui.QColor(0, 150, 0, 50 + int(200 * connection_strength))
            else:
                pen_color = QtGui.QColor(150, 0, 0, 50 + int(200 * connection_strength))
            
            items["line"].setPen(QtGui.QPen(pen_color, pen_width))
            
            # Update the weight display
            items["text"].setPlainText(f"{weight:.1f}")


    def update_brain_weights(self, weights_data):
        """Update the brain connection weights based on current neural network weights"""
        if not hasattr(self, 'connection_items'):
            return
            
        # Update connection weights
        for (src, dst), weight in weights_data.items():
            # Look for the connection in either direction
            connection = (src, dst)
            if connection in self.connection_items:
                self.connection_items[connection]["weight"] = weight
            else:
                # Try the reverse connection
                connection = (dst, src)
                if connection in self.connection_items:
                    self.connection_items[connection]["weight"] = weight
                    

    def animate_decision_process(self, decision_data):
        """Animate the decision-making process with visual effects"""
        if not hasattr(self, 'processing_animation'):
            return
            
        # Get the decision information
        decision = decision_data.get('final_decision', 'unknown')
        processing_time = decision_data.get('processing_time', 1000)
        
        # Display processing text
        self.processing_text.setText(f"Processing decision ({processing_time}ms)...")
        
        # Start the animation with a brief delay to show processing
        QtCore.QTimer.singleShot(300, lambda: self.highlight_decision_in_ui(decision))


    def highlight_decision_in_ui(self, decision):
        """Highlight the chosen decision in the UI"""
        # Update decision output with animation effect
        self.decision_output.setText(decision.capitalize())
        
        # Flash the decision with a highlight animation
        original_style = self.decision_output.styleSheet()
        self.decision_output.setStyleSheet("font-size: 18px; font-weight: bold; color: white; background-color: green; padding: 5px; border-radius: 5px;")
        
        # Reset after brief highlight
        QtCore.QTimer.singleShot(500, lambda: self.decision_output.setStyleSheet(original_style))
        
        # Update processing text
        self.processing_text.setText(f"Decision made: {decision.capitalize()}")

    def get_center_position(self):
        """Calculate center position for new debug neurons"""
        x = sum(p[0] for p in self.neuron_positions.values()) // len(self.neuron_positions)
        y = sum(p[1] for p in self.neuron_positions.values()) // len(self.neuron_positions)
        return (x + random.randint(-50, 50), y + random.randint(-50, 50))
    
    def update_paused_overlay(self):
        """Update the paused state"""
        # Maintain pause state but don't show visual overlay
        if hasattr(self, 'paused_overlay_label'):
            self.paused_overlay_label.setVisible(False)  # Always keep it invisible
            self.paused_overlay_label.deleteLater()
            delattr(self, 'paused_overlay_label')
    
# brain_tool.py

# ... (other imports at the top of brain_tool.py, ensure these are present)
# from PyQt5 import QtCore, QtGui, QtWidgets
# from PyQt5.QtWidgets import QSplitter, QTabWidget, QTableWidget, QTableWidgetItem, QFormLayout, QGroupBox # Explicitly ensure these
# import time # For time.time() in neurogenesis details
# from datetime import datetime # For formatting timestamps

# ... (SquidBrainWindow class and other preceding code) ...

class NeuronInspector(QtWidgets.QDialog):
    def __init__(self, brain_tool_window, brain_widget_ref, parent=None): # brain_tool_window is the SquidBrainWindow instance
        super().__init__(brain_tool_window) # Set parent to brain_tool_window
        self.brain_tool_window = brain_tool_window 
        self.brain_widget = brain_widget_ref 

        self.setWindowTitle("Neuron Inspector")
        # Portrait orientation, larger size
        self.setFixedSize(450, 700) # Width, Height

        self.main_layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.main_layout)

        # Neuron selector
        self.neuron_combo = QtWidgets.QComboBox()
        self.neuron_combo.setToolTip("Select a neuron to inspect or click one in the visualizer.")
        self.main_layout.addWidget(self.neuron_combo)

        # Tab widget
        self.tabs = QtWidgets.QTabWidget() #
        self.main_layout.addWidget(self.tabs)

        # --- Tab 1: Overview ---
        self.overview_tab = QtWidgets.QWidget()
        self.overview_layout = QtWidgets.QFormLayout(self.overview_tab) 
        self.overview_tab.setLayout(self.overview_layout)
        self.tabs.addTab(self.overview_tab, "Overview")

        self.name_label = QtWidgets.QLabel()
        self.value_label = QtWidgets.QLabel()
        self.position_label = QtWidgets.QLabel()
        self.type_label = QtWidgets.QLabel() # Core or Neurogenesis

        self.overview_layout.addRow("<b>Name:</b>", self.name_label)
        self.overview_layout.addRow("<b>Current Value:</b>", self.value_label)
        self.overview_layout.addRow("<b>Position (X,Y):</b>", self.position_label)
        self.overview_layout.addRow("<b>Type:</b>", self.type_label)

        # Placeholder for neurogenesis info
        self.neurogenesis_group = QtWidgets.QGroupBox("Neurogenesis Details") 
        self.neurogenesis_layout = QtWidgets.QFormLayout() 
        self.neurogenesis_group.setLayout(self.neurogenesis_layout)
        self.neurogenesis_group.setVisible(False) # Hidden by default

        self.created_at_label = QtWidgets.QLabel()
        self.trigger_type_label = QtWidgets.QLabel()
        self.trigger_value_label = QtWidgets.QLabel()
        self.associated_state_label = QtWidgets.QLabel()
        self.associated_state_label.setWordWrap(True)

        self.neurogenesis_layout.addRow("<b>Created At:</b>", self.created_at_label)
        self.neurogenesis_layout.addRow("<b>Trigger Type:</b>", self.trigger_type_label)
        self.neurogenesis_layout.addRow("<b>Trigger Value:</b>", self.trigger_value_label)
        self.neurogenesis_layout.addRow("<b>Associated State:</b>", self.associated_state_label)
        self.overview_layout.addWidget(self.neurogenesis_group)


        # --- Tab 2: Connections ---
        self.connections_tab = QtWidgets.QWidget()
        self.connections_layout = QtWidgets.QVBoxLayout(self.connections_tab)
        self.tabs.addTab(self.connections_tab, "Connections")

        self.connections_table = QtWidgets.QTableWidget() 
        self.connections_table.setColumnCount(3)
        self.connections_table.setHorizontalHeaderLabels(["Connected To", "Weight", "Direction"])
        self.connections_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.connections_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.connections_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.connections_layout.addWidget(self.connections_table)

        # --- Tab 3: Activity (Placeholder) ---
        self.activity_tab = QtWidgets.QWidget()
        self.activity_layout = QtWidgets.QVBoxLayout(self.activity_tab)
        self.activity_info_label = QtWidgets.QLabel("Detailed activity logging and graphing coming soon.")
        self.activity_info_label.setAlignment(QtCore.Qt.AlignCenter)
        self.activity_layout.addWidget(self.activity_info_label)
        self.tabs.addTab(self.activity_tab, "Activity")

        # --- Refresh Button (optional, as it updates on click) ---
        self.refresh_btn = QtWidgets.QPushButton("Refresh Data")
        self.refresh_btn.clicked.connect(self.update_info)
        self.main_layout.addWidget(self.refresh_btn)

        # Connect to brain widget's neuronClicked signal
        if hasattr(self.brain_widget, 'neuronClicked'):
            self.brain_widget.neuronClicked.connect(self.inspect_neuron_by_name) #

        self.neuron_combo.currentIndexChanged.connect(self.update_info_from_combo)

        self.update_neuron_list()
        if self.neuron_combo.count() > 0:
            self.update_info() # Initial update

    def update_neuron_list(self):
        if not self.brain_widget: return
        current_selection = self.neuron_combo.currentText()
        self.neuron_combo.clear()
        # Sort neuron names for consistent order
        neuron_names = sorted(self.brain_widget.neuron_positions.keys())
        self.neuron_combo.addItems(neuron_names)
        if current_selection in neuron_names:
            self.neuron_combo.setCurrentText(current_selection)
        elif neuron_names:
            self.neuron_combo.setCurrentIndex(0)


    def inspect_neuron_by_name(self, neuron_name):
        """Slot to handle neuronClicked signal from BrainWidget."""
        index = self.neuron_combo.findText(neuron_name)
        if index >= 0:
            # Block signals temporarily to prevent double update if setCurrentIndex triggers update_info
            self.neuron_combo.blockSignals(True)
            self.neuron_combo.setCurrentIndex(index)
            self.neuron_combo.blockSignals(False)
            self.update_info() # Explicitly update after setting index
        self.show()
        self.raise_()
        self.activateWindow()


    def update_info_from_combo(self):
        # This is called when combobox selection changes
        self.update_info()

    def update_info(self):
        """Update all display elements for the currently selected neuron."""
        if not self.brain_widget:
            self.name_label.setText("<N/A>")
            # Clear other fields
            self.value_label.setText("")
            self.position_label.setText("")
            self.type_label.setText("")
            self.neurogenesis_group.setVisible(False)
            if hasattr(self, 'connections_table'): self.connections_table.setRowCount(0)
            return

        neuron_name = self.neuron_combo.currentText()
        if not neuron_name or neuron_name not in self.brain_widget.neuron_positions:
            # Clear all fields if no valid neuron is selected
            self.name_label.setText("<No Neuron Selected>")
            self.value_label.setText("")
            self.position_label.setText("")
            self.type_label.setText("")
            self.neurogenesis_group.setVisible(False)
            if hasattr(self, 'connections_table'): self.connections_table.setRowCount(0)
            return

        # --- Overview Tab Data ---
        self.name_label.setText(f"<b>{neuron_name}</b>")

        value = self.brain_widget.state.get(neuron_name, "N/A")
        self.value_label.setText(str(round(value, 2) if isinstance(value, (float, int)) else value))

        pos = self.brain_widget.neuron_positions.get(neuron_name, ("N/A", "N/A"))
        self.position_label.setText(f"({pos[0]:.1f}, {pos[1]:.1f})" if isinstance(pos, tuple) and len(pos) == 2 and all(isinstance(p, (int,float)) for p in pos) else "N/A")


        # Check if new_neurons_details exists and then if neuron_name is in it
        is_neurogenesis = False
        if hasattr(self.brain_widget, 'neurogenesis_data') and \
           'new_neurons_details' in self.brain_widget.neurogenesis_data and \
           neuron_name in self.brain_widget.neurogenesis_data.get('new_neurons_details', {}):
            is_neurogenesis = True

        neuron_kind = "Neurogenesis" if is_neurogenesis else "Core"
        if neuron_name in self.brain_widget.excluded_neurons: 
            neuron_kind = "System Status"
        self.type_label.setText(neuron_kind)

        if is_neurogenesis:
            details = self.brain_widget.neurogenesis_data['new_neurons_details'].get(neuron_name, {})
            created_timestamp = details.get('created_at')
            if created_timestamp:
                # Ensure datetime is imported if not already: from datetime import datetime
                from datetime import datetime # Local import for safety
                self.created_at_label.setText(datetime.fromtimestamp(created_timestamp).strftime('%Y-%m-%d %H:%M:%S'))
            else:
                self.created_at_label.setText("Unknown")
            self.trigger_type_label.setText(str(details.get('trigger_type', "N/A")).capitalize())
            
            trigger_val = details.get('trigger_value_at_creation', "N/A")
            self.trigger_value_label.setText(f"{trigger_val:.2f}" if isinstance(trigger_val, float) else str(trigger_val))


            snapshot = details.get('associated_state_snapshot', {})
            snapshot_text = ", ".join([f"{k.capitalize()}: {v}" for k, v in snapshot.items() if v is not None])
            self.associated_state_label.setText(snapshot_text if snapshot_text else "No specific state captured.")
            self.neurogenesis_group.setVisible(True)
        else:
            self.neurogenesis_group.setVisible(False)

        # --- Connections Tab Data ---
        self.connections_table.setRowCount(0) # Clear previous
        connections_data = []
        # Ensure brain_widget.weights exists and is a dictionary
        if hasattr(self.brain_widget, 'weights') and isinstance(self.brain_widget.weights, dict):
            for conn_key, weight_val in self.brain_widget.weights.items():
                # Ensure conn_key is a tuple of two strings (neuron names)
                if isinstance(conn_key, tuple) and len(conn_key) == 2:
                    src, dst = conn_key
                    if src == neuron_name:
                        connections_data.append({'target': dst, 'weight': weight_val, 'direction': "Outgoing"})
                    elif dst == neuron_name:
                        connections_data.append({'target': src, 'weight': weight_val, 'direction': "Incoming"})
                # else:
                    # print(f"Skipping malformed weight key: {conn_key}")


        self.connections_table.setRowCount(len(connections_data))
        for row, conn_info in enumerate(connections_data):
            self.connections_table.setItem(row, 0, QtWidgets.QTableWidgetItem(conn_info['target'])) #
            item_weight = QtWidgets.QTableWidgetItem(f"{conn_info['weight']:.3f}") #
            item_weight.setForeground(QtGui.QColor("green") if conn_info['weight'] > 0 else QtGui.QColor("red"))
            self.connections_table.setItem(row, 1, item_weight)
            self.connections_table.setItem(row, 2, QtWidgets.QTableWidgetItem(conn_info['direction'])) #


        # Refresh neuron list only if necessary (e.g., if current neuron disappeared)
        # This check was simplified; if it causes issues, it might need refinement.
        # The primary update path is now through the combobox or direct neuron click.
        if self.neuron_combo.findText(neuron_name) == -1 and neuron_name in self.brain_widget.neuron_positions :
             self.update_neuron_list()


