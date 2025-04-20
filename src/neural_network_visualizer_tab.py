# neural_network_visualizer_tab.py
import math
import random
from PyQt5 import QtCore, QtGui, QtWidgets
from .brain_base_tab import BrainBaseTab

class NeuralNetworkVisualizerTab(BrainBaseTab):
    def __init__(self, parent=None, tamagotchi_logic=None, brain_widget=None, config=None, debug_mode=False):
        super().__init__(parent, tamagotchi_logic, brain_widget, config, debug_mode)
        
        # Animation state tracking
        self.animations = {}
        self.learning_in_progress = False
        self.highlighted_neurons = set()
        self.current_state = {}
        self.popup_items = []  # Track popup items
        
        # Neurons to hide
        self.hidden_neurons = ['is_eating', 'pursuing_food', 'is_fleeing']
        
        # Setup the UI
        self.setup_ui()
        
    def setup_ui(self):
        # Clear any existing widgets from the parent's layout
        layout = self.layout  # Get the layout that was set in BrainBaseTab
        
        # Clear existing widgets
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Title and description
        title_label = QtWidgets.QLabel("Neural Network Learning Visualization")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title_label)
        
        description = (
            "This visualization shows how the squid's neural network learns and adapts. "
            "Neurons (circles) represent different aspects of the squid's state, and "
            "connections (lines) show how they influence each other."
        )
        desc_label = QtWidgets.QLabel(description)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        # Learning status indicator
        status_layout = QtWidgets.QHBoxLayout()
        self.countdown_label = QtWidgets.QLabel("30 seconds")
        self.countdown_label.setStyleSheet("font-weight: bold; color: #3498db;")
        status_layout.addWidget(QtWidgets.QLabel("Next learning cycle in:"))
        status_layout.addWidget(self.countdown_label)
        status_layout.addStretch()
        layout.addLayout(status_layout)
        
        # Create visualization area
        self.viz_scene = QtWidgets.QGraphicsScene()
        self.viz_view = QtWidgets.QGraphicsView(self.viz_scene)
        self.viz_view.setRenderHint(QtGui.QPainter.Antialiasing)
        self.viz_view.setMinimumHeight(300)
        layout.addWidget(self.viz_view)
        
        # Control panel
        control_panel = QtWidgets.QWidget()
        control_layout = QtWidgets.QHBoxLayout(control_panel)
        
        # Zoom slider
        zoom_label = QtWidgets.QLabel("Zoom:")
        control_layout.addWidget(zoom_label)
        
        self.zoom_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.zoom_slider.setMinimum(50)
        self.zoom_slider.setMaximum(150)
        self.zoom_slider.setValue(100)
        self.zoom_slider.valueChanged.connect(self.update_zoom)
        control_layout.addWidget(self.zoom_slider)
        
        # View mode selector
        self.mode_selector = QtWidgets.QComboBox()
        self.mode_selector.addItems(["Standard View", "Simplified View", "Detailed View"])
        self.mode_selector.currentIndexChanged.connect(self.update_visualization_mode)
        control_layout.addWidget(self.mode_selector)
        
        # Add manual learning trigger button (only in debug mode)
        if self.debug_mode:
            self.trigger_button = QtWidgets.QPushButton("Trigger Learning Cycle")
            self.trigger_button.clicked.connect(self.trigger_learning_cycle)
            control_layout.addWidget(self.trigger_button)
        
        layout.addWidget(control_panel)
        
        # Educational panel with tabs
        self.edu_tabs = QtWidgets.QTabWidget()
        
        # How Learning Works tab
        learning_widget = QtWidgets.QWidget()
        learning_layout = QtWidgets.QVBoxLayout(learning_widget)
        learning_content = QtWidgets.QTextEdit()
        learning_content.setReadOnly(True)
        learning_content.setHtml(self._get_learning_explanation_html())
        learning_layout.addWidget(learning_content)
        self.edu_tabs.addTab(learning_widget, "How Learning Works")
        
        # Key Concepts tab
        concepts_widget = QtWidgets.QWidget()
        concepts_layout = QtWidgets.QVBoxLayout(concepts_widget)
        concepts_content = QtWidgets.QTextEdit()
        concepts_content.setReadOnly(True)
        concepts_content.setHtml(self._get_key_concepts_html())
        concepts_layout.addWidget(concepts_content)
        self.edu_tabs.addTab(concepts_widget, "Key Concepts")
        
        # Add activity log tab
        log_widget = QtWidgets.QWidget()
        log_layout = QtWidgets.QVBoxLayout(log_widget)
        self.activity_log = QtWidgets.QTextEdit()
        self.activity_log.setReadOnly(True)
        self.activity_log.setHtml("<h3>Learning Activity Log</h3><p>Recent learning events will appear here.</p>")
        log_layout.addWidget(self.activity_log)
        clear_button = QtWidgets.QPushButton("Clear Log")
        clear_button.clicked.connect(self.clear_log)
        log_layout.addWidget(clear_button, alignment=QtCore.Qt.AlignRight)
        self.edu_tabs.addTab(log_widget, "Activity Log")
        
        # Add educational panel to layout
        layout.addWidget(self.edu_tabs)
        
        # Initialize visualization
        self.update_visualization()
    
    def trigger_learning_cycle(self):
        """Trigger an immediate learning cycle"""
        if hasattr(self.parent, 'trigger_learning_cycle'):
            self.parent.trigger_learning_cycle()
            self.add_log_entry("Manual learning cycle triggered")
            
    def clear_log(self):
        """Clear the activity log"""
        self.activity_log.setHtml("<h3>Learning Activity Log</h3><p>Recent learning events will appear here.</p>")
    
    def add_log_entry(self, message):
        """Add an entry to the activity log"""
        timestamp = QtCore.QTime.currentTime().toString("hh:mm:ss")
        self.activity_log.append(f"<p><b>[{timestamp}]</b> {message}</p>")
        
        # Auto-scroll to bottom
        scrollbar = self.activity_log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def update_zoom(self, value):
        """Handle zoom slider changes"""
        scale = value / 100.0
        transform = QtGui.QTransform()
        transform.scale(scale, scale)
        self.viz_view.setTransform(transform)
    
    def update_visualization_mode(self, index):
        """Update visualization based on selected mode"""
        self.update_visualization()
    
    def update_from_brain_state(self, state):
        """Update visualization based on current brain state"""
        self.current_state = state
        self.update_visualization()
        
        # Check if learning is happening
        if hasattr(self.brain_widget, 'hebbian_countdown_seconds'):
            countdown = self.brain_widget.hebbian_countdown_seconds
            if countdown <= 5 and not self.learning_in_progress:  # Learning is about to happen
                self.show_learning_animation()
    
    def update_visualization(self):
        """Update the network visualization"""
        if not hasattr(self.brain_widget, 'neuron_positions') or not self.brain_widget.neuron_positions:
            return
            
        # Clear scene
        self.viz_scene.clear()
        self.popup_items = []  # Clear popup items tracking
        
        # Get neuron data
        neuron_positions = self.brain_widget.neuron_positions
        weights = getattr(self.brain_widget, 'weights', {})
        
        # Filter out hidden neurons
        filtered_positions = {k: v for k, v in neuron_positions.items() 
                             if k not in self.hidden_neurons}
        
        # Scale positions to fit view
        positions = {}
        values = {}
        
        if not filtered_positions:
            # No neurons to display
            return
        
        # Determine bounds
        min_x = min(pos[0] for pos in filtered_positions.values())
        max_x = max(pos[0] for pos in filtered_positions.values())
        min_y = min(pos[1] for pos in filtered_positions.values())
        max_y = max(pos[1] for pos in filtered_positions.values())
        
        width = max(1, max_x - min_x)
        height = max(1, max_y - min_y)
        
        # Calculate scaling factor
        scale_x = 500 / width
        scale_y = 300 / height
        scale = min(scale_x, scale_y)
        
        # Create scaled positions and get values
        for name, pos in filtered_positions.items():
            positions[name] = (
                (pos[0] - min_x) * scale + 50,  # Add margin
                (pos[1] - min_y) * scale + 50   # Add margin
            )
            
            # Get current value (activation)
            if hasattr(self.brain_widget, 'state') and name in self.brain_widget.state:
                values[name] = self.brain_widget.state[name]
            else:
                values[name] = 50  # Default activation
        
        # Draw connections first (so they're behind neurons)
        self._draw_connections(positions, weights)
        
        # Draw neurons
        self._draw_neurons(positions, values)
        
        # Set scene size
        self.viz_scene.setSceneRect(0, 0, 600, 400)
    
    def _draw_connections(self, positions, weights):
        """Draw the neural connections with appropriate styling"""
        # Get view mode
        mode = self.mode_selector.currentText()
        show_all = mode == "Detailed View"
        
        try:
            # Process connection weights
            weight_items = []
            
            # Try iterating as (src,dst):weight pairs first
            if isinstance(weights, dict):
                for key, weight in weights.items():
                    if isinstance(key, tuple) and len(key) == 2:
                        # Standard format: {(src,dst): weight}
                        src, dst = key
                        if src not in self.hidden_neurons and dst not in self.hidden_neurons:
                            weight_items.append((src, dst, weight))
                    elif isinstance(key, str) and '_' in key:
                        # Alternative format: {f"{src}_{dst}": weight}
                        src, dst = key.split('_', 1)
                        if src not in self.hidden_neurons and dst not in self.hidden_neurons:
                            weight_items.append((src, dst, weight))
            
            # Draw all connections
            for src, dst, weight in weight_items:
                # Skip weak connections in simplified view
                if abs(weight) < 0.3 and mode == "Simplified View":
                    continue
                    
                # Ensure both neurons exist in positions
                if src not in positions or dst not in positions:
                    continue
                    
                # Get positions
                start_x, start_y = positions[src]
                end_x, end_y = positions[dst]
                
                # Calculate line parameters
                if weight > 0:
                    color = QtGui.QColor(0, 0, 255)  # Blue for excitatory
                    tooltip = f"Excitatory connection: {src} encourages {dst}"
                else:
                    color = QtGui.QColor(255, 0, 0)  # Red for inhibitory
                    tooltip = f"Inhibitory connection: {src} inhibits {dst}"
                
                # Line width based on strength
                width = abs(weight) * 3
                
                # Create the line
                line = QtWidgets.QGraphicsLineItem(start_x, start_y, end_x, end_y)
                line.setPen(QtGui.QPen(color, width))
                line.setZValue(1)  # Ensure connections are behind neurons
                line.setToolTip(tooltip)
                
                # Add to scene
                self.viz_scene.addItem(line)
                
                # If learning is highlighted, add animation if this connection is changing
                connection_pair = (src, dst)
                if self.learning_in_progress and (
                    connection_pair in self.highlighted_neurons or
                    (dst, src) in self.highlighted_neurons
                ):
                    self._add_connection_animation(line)
                
                # Draw direction arrows (only in detailed mode)
                if show_all:
                    self._draw_direction_arrow(start_x, start_y, end_x, end_y, color)
                    
                    # Add weight label
                    mid_x = (start_x + end_x) / 2
                    mid_y = (start_y + end_y) / 2
                    
                    weight_text = QtWidgets.QGraphicsTextItem(f"{weight:.2f}")
                    weight_text.setPos(mid_x, mid_y)
                    weight_text.setDefaultTextColor(QtGui.QColor(0, 0, 0))
                    self.viz_scene.addItem(weight_text)
                    
        except Exception as e:
            print(f"Error drawing connections: {str(e)}")
            # Add error message to visualization
            error_text = QtWidgets.QGraphicsTextItem("Error: Could not draw connections")
            error_text.setDefaultTextColor(QtGui.QColor(255, 0, 0))
            error_text.setPos(50, 50)
            self.viz_scene.addItem(error_text)
    
    def _draw_direction_arrow(self, x1, y1, x2, y2, color):
        """Draw an arrow indicating connection direction"""
        # Calculate angle
        angle = math.atan2(y2 - y1, x2 - x1)
        
        # Create arrow head
        arrow_size = 10
        arrow_head = QtGui.QPolygonF([
            QtCore.QPointF(0, 0),
            QtCore.QPointF(-arrow_size, arrow_size/2),
            QtCore.QPointF(-arrow_size, -arrow_size/2)
        ])
        
        # Create arrow item
        arrow = QtWidgets.QGraphicsPolygonItem(arrow_head)
        arrow.setBrush(QtGui.QBrush(color))
        arrow.setPen(QtGui.QPen(color))
        
        # Position at 3/4 of the way along the line
        pos_x = x1 + (x2 - x1) * 0.75
        pos_y = y1 + (y2 - y1) * 0.75
        
        # Set position and rotation
        arrow.setPos(pos_x, pos_y)
        arrow.setRotation(angle * 180 / math.pi)
        
        # Add to scene
        self.viz_scene.addItem(arrow)
    
    def _draw_neurons(self, positions, values):
        """Draw the neurons with appropriate styling"""
        # For each neuron
        for name, (x, y) in positions.items():
            # Get value and determine color
            value = values.get(name, 50)
            
            # Calculate color based on neuron type and value
            if name.startswith("novel_") or name.startswith("reward_") or name.startswith("defense_"):
                # Special neurons from neurogenesis
                if name.startswith("novel_"):
                    base_color = QtGui.QColor(255, 255, 150)  # Yellow
                elif name.startswith("reward_"):
                    base_color = QtGui.QColor(150, 255, 150)  # Green
                else:
                    base_color = QtGui.QColor(255, 150, 150)  # Red
            else:
                # Regular neurons
                r = int(max(0, min(255, 255 - value * 2.55)))
                g = int(max(0, min(255, value * 2.55)))
                b = int(max(0, min(255, 255 - abs(value - 50) * 5.1)))
                base_color = QtGui.QColor(r, g, b)
            
            # Create ellipse for neuron
            radius = 20
            if name in self.highlighted_neurons:
                # Larger, highlighted radius for neurons being learned about
                radius = 30
                ellipse = QtWidgets.QGraphicsEllipseItem(x - radius, y - radius, radius * 2, radius * 2)
                ellipse.setPen(QtGui.QPen(QtGui.QColor(255, 255, 0), 3))  # Yellow highlight
            else:
                ellipse = QtWidgets.QGraphicsEllipseItem(x - radius, y - radius, radius * 2, radius * 2)
                ellipse.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0)))
            
            ellipse.setBrush(QtGui.QBrush(base_color))
            ellipse.setZValue(2)  # Ensure neurons are on top of connections
            
            # Add tooltip
            tooltip_text = self._create_neuron_tooltip(name, value)
            ellipse.setToolTip(tooltip_text)
            
            # Add to scene
            self.viz_scene.addItem(ellipse)
            
            # Add neuron name
            text = QtWidgets.QGraphicsTextItem(name)
            text.setPos(x - radius, y + radius + 5)
            text.setZValue(3)
            self.viz_scene.addItem(text)
            
            # Add activity value
            value_text = QtWidgets.QGraphicsTextItem(f"{value:.1f}")
            value_text.setPos(x - 15, y - 10)
            value_text.setDefaultTextColor(QtGui.QColor(0, 0, 0))
            value_text.setZValue(4)
            self.viz_scene.addItem(value_text)
    
    def _create_neuron_tooltip(self, neuron_name, value):
        """Create an educational tooltip for a neuron"""
        descriptions = {
            "happiness": "Represents how happy the squid is. High happiness can lead to increased curiosity.",
            "hunger": "Represents how hungry the squid is. High hunger can decrease happiness.",
            "sleepiness": "Represents how tired the squid is. High sleepiness eventually leads to sleep.",
            "cleanliness": "Represents how clean the environment is. Low cleanliness can lead to sickness.",
            "curiosity": "Represents how interested the squid is in exploring. Affects exploration behavior.",
            "anxiety": "Represents how anxious the squid is. High anxiety can trigger defensive behaviors.",
            "satisfaction": "Represents how content the squid is with recent experiences."
        }
        
        if neuron_name.startswith("novel_"):
            description = "A specialized neuron created from a novel experience. Helps the squid adapt to new situations."
        elif neuron_name.startswith("reward_"):
            description = "A specialized neuron created from positive experiences. Helps the squid seek beneficial activities."
        elif neuron_name.startswith("defense_") or neuron_name.startswith("stress_"):
            description = "A specialized neuron created during stressful situations. Helps the squid respond to threats."
        else:
            description = descriptions.get(neuron_name, f"Represents {neuron_name}")
        
        tooltip = f"<b>{neuron_name}</b><br>Current value: {value:.1f}<br><br>{description}"
        return tooltip
    
    def _add_connection_animation(self, line_item):
        """Add a pulsing animation to a connection line to show learning"""
        # Create animation to pulse the line width
        anim = QtCore.QVariantAnimation()
        anim.setStartValue(1.0)
        anim.setEndValue(4.0)
        anim.setDuration(1000)
        anim.setLoopCount(3)
        
        # Update pen width when animation value changes
        def update_pen(value):
            try:
                if line_item.scene() == self.viz_scene:
                    current_pen = line_item.pen()
                    new_pen = QtGui.QPen(current_pen.color(), value)
                    line_item.setPen(new_pen)
            except:
                pass  # Handle case where item might have been removed
        
        anim.valueChanged.connect(update_pen)
        anim.start()
        
        # Store animation to prevent garbage collection
        self.animations[line_item] = anim
    
    def show_learning_animation(self):
        """Display animations when Hebbian learning occurs"""
        if self.learning_in_progress:
            return
            
        self.learning_in_progress = True
        
        # Select random neurons to highlight for learning
        active_neurons = []
        for name, value in self.current_state.items():
            if (isinstance(value, (int, float)) and 
                value > 60 and 
                name not in self.hidden_neurons):
                active_neurons.append(name)
        
        # If we have at least 2 active neurons, highlight a connection
        if len(active_neurons) >= 2:
            # Choose 2 random neurons
            learning_pair = random.sample(active_neurons, 2)
            self.highlighted_neurons = set(learning_pair)
            
            # Show a popup about learning
            self._show_learning_popup(learning_pair[0], learning_pair[1])
            
            # Add to activity log
            self.add_log_entry(f"Learning connection between <b>{learning_pair[0]}</b> and <b>{learning_pair[1]}</b>")
            
            # Refresh visualization to show highlights
            self.update_visualization()
            
            # Clear highlights after 3 seconds
            QtCore.QTimer.singleShot(3000, self._clear_highlights)
    
    def _show_learning_popup(self, neuron1, neuron2):
        """Show an educational popup about learning"""
        # Clear any existing popup first
        self._clear_popup()
        
        # Create a semi-transparent info box
        self.popup_box = QtWidgets.QGraphicsRectItem(50, 150, 500, 100)
        self.popup_box.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 220, 220)))
        self.popup_box.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0), 2))
        self.popup_box.setZValue(100)
        self.viz_scene.addItem(self.popup_box)
        self.popup_items.append(self.popup_box)
        
        # Add text explaining what's happening
        self.popup_text = QtWidgets.QGraphicsTextItem()
        self.popup_text.setHtml(
            f"<b>Learning in progress!</b><br>"
            f"The connection between <b>{neuron1}</b> and <b>{neuron2}</b> is being strengthened "
            f"because both neurons are active at the same time.<br>"
            f"This is Hebbian learning: \"Neurons that fire together, wire together.\""
        )
        self.popup_text.setTextWidth(480)
        self.popup_text.setPos(60, 160)
        self.popup_text.setZValue(101)
        self.viz_scene.addItem(self.popup_text)
        self.popup_items.append(self.popup_text)
        
        # Create animation to fade out the popup
        self.fade_anim = QtCore.QVariantAnimation()
        self.fade_anim.setStartValue(1.0)
        self.fade_anim.setEndValue(0.0)
        self.fade_anim.setDuration(3000)
        
        def update_opacity(value):
            for item in self.popup_items:
                if item.scene() == self.viz_scene:
                    item.setOpacity(value)
                
        def cleanup():
            self._clear_popup()
            
        self.fade_anim.valueChanged.connect(update_opacity)
        self.fade_anim.finished.connect(cleanup)
        self.fade_anim.start()
        
        # Store animation
        self.animations['popup'] = self.fade_anim
    
    def _clear_popup(self):
        """Clean up popup items safely"""
        for item in self.popup_items:
            if item.scene() == self.viz_scene:
                self.viz_scene.removeItem(item)
        
        self.popup_items = []
                
        if hasattr(self, 'fade_anim') and self.fade_anim:
            try:
                self.fade_anim.stop()
            except:
                pass
    
    def _clear_highlights(self):
        """Clear highlighted neurons and refresh"""
        self.highlighted_neurons = set()
        self.learning_in_progress = False
        self.update_visualization()
        
    def _get_learning_explanation_html(self):
        """Return HTML content explaining neural learning"""
        return """
        <h2>How Neural Learning Works</h2>
        
        <p>The squid's brain uses a simplified form of neural learning called <b>Hebbian learning</b>. 
        The core principle is: <i>"Neurons that fire together, wire together."</i></p>
        
        <h3>The Learning Process:</h3>
        
        <ol>
            <li><b>Activation:</b> Neurons activate based on the squid's experiences and internal state.</li>
            <li><b>Connection Strengthening:</b> When two neurons are active at the same time, the connection between them gets stronger.</li>
            <li><b>Adaptation:</b> Over time, this changes the network structure, allowing the squid to learn from experiences.</li>
        </ol>
        
        <h3>Example:</h3>
        <p>If the squid feels hungry (hunger neuron activates) and then eats food (satisfaction neuron activates), 
        the connection between hunger and satisfaction strengthens. This helps the squid learn that eating reduces hunger.</p>
        
        <p>Similarly, if being dirty (low cleanliness) often leads to being sick, the network will strengthen this connection, 
        helping the squid learn to avoid being dirty.</p>
        
        <h3>Connection Types:</h3>
        <ul>
            <li><span style="color:blue;font-weight:bold;">Blue connections (positive):</span> When one neuron activates, it encourages the other to activate too.</li>
            <li><span style="color:red;font-weight:bold;">Red connections (negative):</span> When one neuron activates, it inhibits or reduces the other.</li>
        </ul>
        
        <p>Watch for <span style="color:yellow;background-color:#333;padding:2px;">highlighted connections</span> in the visualization - 
        these show learning in progress!</p>
        """
    
    def _get_key_concepts_html(self):
        """Return HTML content explaining key neural network concepts"""
        return """
        <h2>Key Neural Network Concepts</h2>
        
        <h3>Neurons</h3>
        <p>Neurons are the basic building blocks of the network. Each neuron represents a different aspect of the squid's state or behavior:</p>
        <ul>
            <li><b>Core Neurons:</b> Basic states like hunger, happiness, and cleanliness.</li>
            <li><b>Secondary Neurons:</b> More complex states like curiosity, anxiety, and satisfaction.</li>
            <li><b>Specialized Neurons:</b> Created through neurogenesis to help the squid adapt to new situations.</li>
        </ul>
        
        <h3>Neurogenesis</h3>
        <p>When the squid has new or significant experiences, the network can create entirely new neurons through <b>neurogenesis</b>:</p>
        <ul>
            <li><b>Novel Neurons:</b> Created from new experiences to help the squid adapt.</li>
            <li><b>Reward Neurons:</b> Created from positive experiences to encourage beneficial behaviors.</li>
            <li><b>Defense/Stress Neurons:</b> Created from stressful experiences to help the squid respond to threats.</li>
        </ul>
        
        <h3>Connection Weights</h3>
        <p>The strength of connections between neurons determines how much they influence each other:</p>
        <ul>
            <li><b>Strong Positive:</b> Strong encouraging effect (value near +1.0)</li>
            <li><b>Weak Positive:</b> Mild encouraging effect (value near +0.3)</li>
            <li><b>Weak Negative:</b> Mild inhibiting effect (value near -0.3)</li>
            <li><b>Strong Negative:</b> Strong inhibiting effect (value near -1.0)</li>
        </ul>
        
        <h3>Network Adaptation</h3>
        <p>The network continuously adapts based on the squid's experiences, forming a simple learning system that allows the squid to:</p>
        <ul>
            <li>Remember cause-and-effect relationships</li>
            <li>Anticipate consequences of actions</li>
            <li>Develop preferences and aversions</li>
            <li>Optimize behavior for survival and well-being</li>
        </ul>
        """