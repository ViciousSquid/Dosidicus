
🧠 Neurogenesis
================

Neurogenesis is the mechanism by which new neurons are created and integrated into the existing neural network, allowing the squid's brain to adapt and grow based on its experiences.

* * *

1\. Overview
------------

Neurogenesis in this system is designed to simulate brain plasticity. New neurons can be generated in response to specific triggers: **novelty**, **stress**, and **reward**. Once created, these neurons form connections with existing ones and participate in Hebbian learning. To maintain network stability and prevent uncontrolled growth (unless desired), a **pruning** mechanism can remove weak or inactive neurons. The entire process is configurable, allowing for different brain development scenarios.

* * *

2\. Configuration
-----------------

Neurogenesis parameters are primarily managed within the `BrainWidget` class, drawing from the `LearningConfig` and its own defaults.

### Default Configuration (`BrainWidget.__init__`)

If no specific configuration is provided, `BrainWidget` establishes a default set of neurogenesis parameters:

    
    # From brain_widget.py
    self.config.neurogenesis = {
        'decay_rate': 0.95,
        'novelty_threshold': 3,
        'stress_threshold': 0.7,
        'reward_threshold': 0.6,
        'cooldown': 300, # 5 minutes
        'highlight_duration': 5.0, # 5 seconds
        'max_neurons': 15 # Default limit
    }
            

### Appearance Configuration (`BrainWidget._create_neuron_internal`)

The visual appearance (color and shape) of new neurons is also configurable, allowing for easy identification of their type:

    
    # From brain_widget.py
    cfg_appearance = self.config.neurogenesis.get('appearance', {})
    cfg_colors = cfg_appearance.get('colors', {})
    cfg_shapes = cfg_appearance.get('shapes', {})
    
    default_colors = {'novelty': (255, 255, 150), 'stress': (255, 150, 150), 'reward': (150, 255, 150)}
    self.state_colors[new_name] = tuple(cfg_colors.get(neuron_type, default_colors.get(neuron_type, (200,200,200))))
    
    default_shapes = {'novelty': 'diamond', 'stress': 'square', 'reward': 'circle'}
    self.neuron_shapes[new_name] = cfg_shapes.get(neuron_type, default_shapes.get(neuron_type, 'circle'))
            

* * *

3\. Triggering Mechanisms
-------------------------

Neurogenesis is initiated when certain internal counters exceed their respective thresholds. These counters are updated within `BrainWidget.update_state`, primarily driven by the squid's emotional and sensory states.

### Counters & Updates (`BrainWidget.update_state`)

Counters increase based on squid states (like curiosity, anxiety) and can also receive direct boosts (`novelty_exposure`, `sustained_stress`, `recent_rewards`). They decay over time.

    
    # From brain_widget.py
    # Increment novelty counter when curiosity is high
    if 'curiosity' in self.state and self.state['curiosity'] > 75:
        self.neurogenesis_data['novelty_counter'] += 0.1
    
    # Increment stress counter when anxiety is high or cleanliness is low
    if ('anxiety' in self.state and self.state['anxiety'] > 80) or \
    ('cleanliness' in self.state and self.state['cleanliness'] < 20):
        self.neurogenesis_data['stress_counter'] += 0.25
    
    # Increment reward counter when happiness or satisfaction is high
    if ('happiness' in self.state and self.state['happiness'] > 85) or \
    ('satisfaction' in self.state and self.state['satisfaction'] > 85):
        self.neurogenesis_data['reward_counter'] += 0.2
    
    # Handle direct state triggers
    if new_state.get('novelty_exposure', 0) > 0:
        self.neurogenesis_data['novelty_counter'] += new_state.get('novelty_exposure', 0)
    
    # Decay
    self.neurogenesis_data['novelty_counter'] *= self.neurogenesis_config.get('decay_rate', 0.95)
    # ... (similar for stress and reward)
            

### Threshold Checking (`BrainWidget.update_state` & `BrainWidget.check_neurogenesis`)

The core check happens in `update_state`. It compares the counters against **adjusted thresholds** (if pruning is enabled) or base thresholds. It also verifies the neuron limit and cooldown period before attempting to create a neuron.

    
    # From brain_widget.py (update_state)
    novelty_threshold = self.get_adjusted_threshold(novelty_threshold_base, 'novelty')
    # ...
    if (self.neurogenesis_data['novelty_counter'] > novelty_threshold or ...):
        max_neurons = self.neurogenesis_config.get('max_neurons', 15)
        current_neuron_count = len(self.neuron_positions) - len(self.excluded_neurons)
        cooldown_ok = current_time - self.neurogenesis_data['last_neuron_time'] > self.neurogenesis_config.get('cooldown', 300)
    
        if (not self.pruning_enabled or current_neuron_count < max_neurons) and cooldown_ok:
            # ... determine type and call _create_neuron_internal
            

### Adjusted Thresholds (`BrainWidget.get_adjusted_threshold`)

To control neuron population when pruning is active, thresholds increase as the number of new neurons grows. This makes it progressively harder to create new neurons, promoting stability.

    
    # From brain_widget.py
    def get_adjusted_threshold(self, base_threshold, trigger_type):
        # ... calculates new_neuron_count ...
        scaling_factors = {
            'novelty': 0.25,
            'stress': 0.1,
            'reward': 0.08
        }
        scaling_factor = scaling_factors.get(trigger_type, 0.15)
        multiplier = 1.0 + (scaling_factor * (new_neuron_count - baseline + 1))
        return base_threshold * multiplier
            

* * *

4\. Neuron Creation (`_create_neuron_internal`)
-----------------------------------------------

This is the core function responsible for adding a new neuron to the network. It handles naming, positioning, visual setup, connection weighting, and logging.

### Key Steps:

1.  **Limit Check:** Verifies against `max_neurons` if pruning is enabled.
2.  **Naming:** Creates a unique name (e.g., `novel_0`, `stress_1`).
3.  **Positioning:** Places the new neuron near the most active existing neuron or a central point.
4.  **Appearance:** Sets the color and shape based on the trigger type and configuration.
5.  **State Init:** Sets the initial activation state (usually 50).
6.  **Weight Init:** Establishes initial connections and weights to core neurons (e.g., 'novelty' connects to 'curiosity' and 'anxiety'). These weights can be influenced by the squid's personality.
7.  **Data Storage:** Records detailed information about the new neuron (creation time, trigger type/value, associated state) in `neurogenesis_data['new_neurons_details']`. This is used by the Neuron Inspector.
8.  **Highlighting:** Sets up a visual highlight for the new neuron in the `BrainWidget`.
9.  **Logging:** Calls `log_neurogenesis_event` to record the creation.

    ```
    # From brain_widget.py (_create_neuron_internal - Snippets)
    # Naming
    base_name = {'novelty': 'novel', 'stress': 'stress', 'reward': 'reward'}[neuron_type]
    # ... loop to find unique index ...
    
    # Positioning
    # ... finds base_x, base_y ...
    self.neuron_positions[new_name] = (base_x + random.randint(-50, 50), base_y + random.randint(-50, 50))
    
    # Weight Init
    default_weights = { ... }
    personality_weight_modifier = { ... }.get(personality_str, 1.0)
    for target, weight in default_weights.get(neuron_type, {}).items():
        self.weights[(new_name, target)] = weight * personality_weight_modifier
        self.weights[(target, new_name)] = (weight * personality_weight_modifier) * 0.5
    
    # Data Storage
    self.neurogenesis_data['new_neurons_details'][new_name] = { ... }
    
    # Logging
    self.log_neurogenesis_event(new_name, "created", details=log_creation_details)
    return new_name
      ```      

* * *

5\. Neuron Pruning (`prune_weak_neurons`)
-----------------------------------------

Pruning is an optional mechanism (controlled via the UI) to remove less useful neurons, typically when the network approaches its maximum size. It targets newly generated neurons that are either weakly connected or show low activity.

### Key Steps:

1.  **Check Conditions:** Only runs if pruning is enabled and there are enough neurons to prune.
2.  **Identify Candidates:** Iterates through non-original, non-system neurons. It calculates their average connection strength and activity score. Neurons with weak connections or low activity are marked as candidates.
3.  **Select & Remove:** If candidates exist, the weakest one is selected and removed from:
    *   `neuron_positions`
    *   `state`
    *   `weights` (all associated connections)
    *   `neurogenesis_data['new_neurons']`
4.  **Logging:** Calls `log_neurogenesis_event` to record the pruning event.
```
    
    # From brain_widget.py
    def prune_weak_neurons(self):
        # ... (skip checks) ...
        for neuron in list(self.neuron_positions.keys()):
            # ... (skip original/system) ...
            connections = [abs(w) for (a, b), w in self.weights.items() if (a == neuron or b == neuron)]
            activity = self.state.get(neuron, 0)
            activity_score = 0 if isinstance(activity, bool) else abs(activity - 50)
            if not connections or sum(connections) / len(connections) < 0.2:
                candidates.append((neuron, 1))
            elif activity_score < 10:
                candidates.append((neuron, 2))
    
        if candidates:
            neuron_to_remove = candidates[0][0]
            # ... (delete from dicts/lists) ...
            self.log_neurogenesis_event(neuron_to_remove, "pruned", reason)
            return True
        return False
            
```
* * *

6\. Visualization
-----------------

New neurons are drawn alongside core neurons in `BrainWidget.paintEvent`, which calls `draw_neurons`. Newly created neurons can be temporarily highlighted.

### Drawing (`draw_neurons`)

This method iterates through `neuron_positions` and draws each neuron based on its configured shape (circle, square, diamond, etc.) and color.

### Highlighting (`draw_neurogenesis_highlights`)

If a neuron is currently marked for highlight (in `neurogenesis_highlight`), this method draws a temporary yellow circle around it.

    ```
    # From brain_widget.py
    def draw_neurogenesis_highlights(self, painter, scale):
        if (self.neurogenesis_highlight['neuron'] and
            time.time() - self.neurogenesis_highlight['start_time'] < self.neurogenesis_highlight['duration']):
            pos = self.neuron_positions.get(self.neurogenesis_highlight['neuron'])
            if pos:
                painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 0), int(3 * scale)))
                painter.setBrush(QtCore.Qt.NoBrush)
                radius = int(40 * scale)
                painter.drawEllipse(int(pos[0] - radius), int(pos[1] - radius), int(radius * 2), int(radius * 2))
      ```      

### Neuron Inspector

The `NeuronInspector` class provides a detailed view of individual neurons. For neurons created via neurogenesis, it displays specific details like creation time, trigger type, and the squid's state at the time of creation, drawing data from `brain_widget.neurogenesis_data['new_neurons_details']`.

* * *

7\. Logging (`log_neurogenesis_event`)
--------------------------------------

This method writes neurogenesis events (creation and pruning) to a text file named `neurogenesis_log.txt`. This provides a persistent record of the brain's structural changes.
```
    
    # From brain_widget.py
    def log_neurogenesis_event(self, neuron_name, event_type, reason=None, details=None):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = ""
        if event_type == "created":
            # ... (formats creation details and connections) ...
            log_entry = f"{timestamp} Neuron created: {neuron_name} ... "
        elif event_type == "pruned":
            log_entry = f"{timestamp} PRUNED: {neuron_name} due to {reason if reason else 'Unknown reason'}"
        
        with open('neurogenesis_log.txt', 'a', encoding='utf-8') as f:
            f.write(log_entry + "\\n\\n")
            
```
* * *

8\. UI Integration (`NetworkTab`)
---------------------------------

The `NetworkTab` provides a user interface element to control a key aspect of neurogenesis: **pruning**.

### Pruning Checkbox

A checkbox allows the user to enable or disable the pruning mechanism in real-time.
```
    
    # From brain_network_tab.py
    self.checkbox_pruning = QtWidgets.QCheckBox("Enable pruning")
    self.checkbox_pruning.setChecked(True)  # Enabled by default
    self.checkbox_pruning.stateChanged.connect(self.toggle_pruning)
    checkbox_layout.addWidget(self.checkbox_pruning)
    
    def toggle_pruning(self, state):
        if hasattr(self, 'brain_widget') and self.brain_widget:
            enabled = state == QtCore.Qt.Checked
            self.brain_widget.toggle_pruning(enabled)
            # ... (shows warning if disabled) ...
            
```
**Warning:** Disabling pruning allows for unconstrained neurogenesis, which can potentially lead to network instability or performance issues if the neuron count grows very large.
