"""
brain_widget_modified_methods.py

Complete replacement methods for brain_widget.py that add mark_render_dirty() calls.
Copy each method and replace the corresponding method in your brain_widget.py.

The key change: Add self.mark_render_dirty() before any self.update() call,
or add both if neither exists.
"""

# =============================================================================
# METHOD 1: update_state (around line 2138)
# Change: Add mark_render_dirty() before update() calls
# =============================================================================

def update_state(self, new_state=None):
    """
    Update neuron activations based on connections and random noise,
    but also accept an external `new_state` dict to overwrite widget state.

    If `new_state` is provided, it will be merged into self.state with
    strict handling for binary neurons (keeps them 0 or 100). If None,
    the original neuron activation update logic runs (preserved below).
    """
    import time
    import random

    # If an external state is supplied, merge it and update bookkeeping
    if new_state is not None:
        # Merge incoming state into internal state with binary handling
        for k, v in (new_state.items() if isinstance(new_state, dict) else []):
            if k in self.neuron_positions and self.is_binary_neuron(k):
                # Binary neurons must be exactly 0 or 100
                if isinstance(v, bool):
                    self.state[k] = 100.0 if v else 0.0
                elif isinstance(v, (int, float)):
                    self.state[k] = 100.0 if float(v) > 50.0 else 0.0
                else:
                    # Preserve non-numeric values (fallback)
                    self.state[k] = v
            else:
                # Non-binary neurons: store as-is (numeric/bool converted)
                if isinstance(v, bool):
                    self.state[k] = 100.0 if v else 0.0
                elif isinstance(v, (int, float)):
                    self.state[k] = float(v)
                else:
                    self.state[k] = v

        # Update communication events (for glows/highlights)
        current_time = time.time()
        for neuron in list(self.state.keys()):
            if neuron not in self.communication_events:
                self.communication_events[neuron] = 0
            neuron_value = self.get_neuron_value(self.state[neuron])
            if abs(neuron_value - 50) > 20:
                self.communication_events[neuron] = current_time

        # Update functional neurons if neurogenesis system is present
        if hasattr(self, 'enhanced_neurogenesis') and getattr(self.enhanced_neurogenesis, 'functional_neurons', None):
            try:
                self.enhanced_neurogenesis.update_neuron_activations(self.state)
            except Exception:
                pass

        # CRITICAL: After updating internal state, refresh worker cache
        if hasattr(self, 'brain_worker') and self.brain_worker:
            self._update_worker_cache()

        # >>> ADDED: Mark render dirty before update <<<
        self.mark_render_dirty()
        self.update()
        return

    # -----------------------
    # Original internal logic
    # -----------------------
    BINARY_NEURONS = {"can_see_food"}
    updated = {}

    # First pass: calculate raw new activations
    for neuron, props in self.neurons.items():
        value = props.get('activation', 0.0)

        if neuron in BINARY_NEURONS:
            updated[neuron] = value
            continue

        decay = props.get('decay', 1.0)
        noise = props.get('noise', 0.0)
        value *= decay
        value += random.uniform(-noise, noise)
        updated[neuron] = value

    # Second pass: apply connection effects
    for conn in self.connections:
        src = conn.get("from")
        dst = conn.get("to")
        weight = conn.get("weight", 0)

        if src not in updated or dst not in updated:
            continue
        if dst in BINARY_NEURONS:
            continue

        try:
            updated[dst] += updated[src] * weight
        except Exception:
            continue

    # Final pass: clamp values and write back
    for neuron, val in updated.items():
        if neuron in BINARY_NEURONS:
            snap = 100.0 if val > 50 else 0.0
            try:
                self.neurons[neuron]["activation"] = snap
            except Exception:
                if neuron in self.state:
                    self.state[neuron] = snap
                else:
                    self.neurons.setdefault(neuron, {})['activation'] = snap
            continue

        clamped = max(min(val, 100), -100)
        if isinstance(self.neurons.get(neuron, {}).get('activation', None), (int, float)):
            self.neurons[neuron]['activation'] = clamped
        else:
            self.state[neuron] = clamped

    # Cache update at the end if state changed
    state_changed = bool(updated)
    if state_changed and hasattr(self, 'brain_worker') and self.brain_worker:
        self._update_worker_cache()
    
    # >>> ADDED: Mark render dirty if state changed <<<
    if state_changed:
        self.mark_render_dirty()


# =============================================================================
# METHOD 2: strengthen_connection (around line 2554)
# Change: Add mark_render_dirty() before update()
# =============================================================================

def strengthen_connection(self, neuron1, neuron2, amount):
    pair = (neuron1, neuron2)
    reverse_pair = (neuron2, neuron1)
    if pair not in self.weights and reverse_pair not in self.weights:
        self.weights[pair] = 0.0
    use_pair = pair if pair in self.weights else reverse_pair
    self.weights[use_pair] += amount
    self.weights[use_pair] = max(-1, min(1, self.weights[use_pair]))
    
    # >>> ADDED: Mark render dirty before update <<<
    self.mark_render_dirty()
    self.update()


# =============================================================================
# METHOD 3: update_connection (around line 1660)
# Change: Add mark_render_dirty() before update()
# =============================================================================

def update_connection(self, neuron1, neuron2, value1, value2):
    """Update connection weight and trigger animations"""
    import time
    
    current_time = time.time()
    pair = (neuron1, neuron2)
    reverse_pair = (neuron2, neuron1)

    # Check if the pair or its reverse exists in weights, if not, initialize it
    if pair not in self.weights and reverse_pair not in self.weights:
        if neuron1 in self.neuron_positions and neuron2 in self.neuron_positions:
            self.weights[pair] = 0.0
            print(f"      🆕 Created new connection: {neuron1} ↔ {neuron2}")
        else:
            print(f"      ⚠️  Cannot create connection: {neuron1} or {neuron2} doesn't exist in neuron_positions")
            return

    use_pair = pair if pair in self.weights else reverse_pair
    
    if use_pair not in self.weights:
        print(f"      ⚠️  Connection was pruned, skipping update for {neuron1} ↔ {neuron2}")
        return

    prev_weight = self.weights[use_pair]

    # Learning Rate Calculation
    base_lr = self.learning_rate
    newness_boost = 2.0
    effective_lr = base_lr

    is_n1_new = self.is_new_neuron(neuron1)
    is_n2_new = self.is_new_neuron(neuron2)

    if is_n1_new or is_n2_new:
        effective_lr = base_lr * newness_boost

    # Calculate weight change (basic Hebbian)
    weight_change = effective_lr * (value1 / 100.0) * (value2 / 100.0)
    
    # Add weight decay
    decay_rate = self.config.hebbian.get('weight_decay', 0.01) * 0.1
    new_weight = prev_weight + weight_change - (prev_weight * decay_rate)
    
    # Clamp weight to [-1, 1] range
    new_weight = min(max(new_weight, -1.0), 1.0)
    self.weights[use_pair] = new_weight

    # Add animation using helper method
    self.add_weight_animation(neuron1, neuron2, prev_weight, new_weight)

    # Record weight change time for both neurons
    if abs(new_weight - prev_weight) > 0.001:
        self.weight_change_events[neuron1] = current_time
        self.weight_change_events[neuron2] = current_time
        
        if (neuron1, neuron2) not in self.recently_updated_neuron_pairs and \
           (neuron2, neuron1) not in self.recently_updated_neuron_pairs:
            self.recently_updated_neuron_pairs.append((neuron1, neuron2))
        
        # >>> ADDED: Mark render dirty before update <<<
        self.mark_render_dirty()
        self.update()

    # Record communication time for both neurons
    self.communication_events[neuron1] = current_time
    self.communication_events[neuron2] = current_time

    # Debug output
    lr_indicator = " (\x1b[35mBOOSTED\x1b[0m)" if effective_lr > base_lr else ""
    direction = "\x1b[32m↑\x1b[0m" if new_weight > prev_weight else "\x1b[31m↓\x1b[0m"
    print(f"      \x1b[42mUpdated\x1b[0m {direction} {neuron1} ↔ {neuron2}: "
          f"\x1b[31m{prev_weight:.3f}\x1b[0m → \x1b[32m{new_weight:.3f}\x1b[0m "
          f"(Δ={weight_change:.3f}, LR={effective_lr:.3f}{lr_indicator})")


# =============================================================================
# METHOD 4: prune_weak_connections (around line 1736)
# Change: Add mark_render_dirty() before update()
# =============================================================================

def prune_weak_connections(self, threshold=0.05, min_age_sec=600):
    """Removes connections with absolute weight below the threshold, ignoring new neurons."""
    if not self.pruning_enabled:
        return 0

    import time
    current_time = time.time()
    to_delete = []

    for pair, weight in list(self.weights.items()):
        if not (isinstance(pair, tuple) and len(pair) == 2):
            continue

        neuron1, neuron2 = pair

        if self.is_new_neuron(neuron1, min_age_sec) or self.is_new_neuron(neuron2, min_age_sec):
            continue

        if abs(weight) < threshold:
            to_delete.append(pair)

    for pair in to_delete:
        if pair in self.weights:
            del self.weights[pair]

    if len(to_delete) > 0:
        print(f"\x1b[33mPruned {len(to_delete)} weak connections (Threshold: {threshold}).\x1b[0m")
        # >>> ADDED: Mark render dirty before update <<<
        self.mark_render_dirty()
        self.update()
    
    return len(to_delete)


# =============================================================================
# METHOD 5: prune_weak_neurons (around line 2444)
# Change: Add mark_render_dirty() and update() at the end
# =============================================================================

def prune_weak_neurons(self):
    """Remove weakly connected or inactive neurons to maintain network stability"""
    min_neurons = len(self.original_neuron_positions)
    current_count = len(self.neuron_positions) - len(self.excluded_neurons)
    if current_count <= min_neurons:
        return False

    candidates = []
    for neuron in list(self.neuron_positions.keys()):
        if neuron in self.original_neuron_positions or neuron in self.excluded_neurons:
            continue
        connections = [abs(w) for (a, b), w in self.weights.items() if (a == neuron or b == neuron)]
        activity = self.state.get(neuron, 0)
        activity_score = 0 if isinstance(activity, bool) else abs(activity - 50)
        if not connections or sum(connections) / len(connections) < 0.2:
            candidates.append((neuron, 1))
        elif activity_score < 10:
            candidates.append((neuron, 2))
    candidates.sort(key=lambda x: x[1])

    if candidates:
        neuron_to_remove = candidates[0][0]
        if neuron_to_remove in self.neuron_positions:
            del self.neuron_positions[neuron_to_remove]
        if neuron_to_remove in self.state:
            del self.state[neuron_to_remove]
        for conn in list(self.weights.keys()):
            if isinstance(conn, tuple) and (conn[0] == neuron_to_remove or conn[1] == neuron_to_remove):
                del self.weights[conn]
        if neuron_to_remove in self.neurogenesis_data.get('new_neurons', []):
            self.neurogenesis_data['new_neurons'].remove(neuron_to_remove)
        reason = "weak connections/activity"
        self.log_neurogenesis_event(neuron_to_remove, "pruned", reason)
        
        # >>> ADDED: Mark render dirty and trigger update <<<
        self.mark_render_dirty()
        self.update()
        return True
    return False


# =============================================================================
# METHOD 6: load_brain_state (around line 1949)
# Change: Add mark_render_dirty() and update() at the end
# =============================================================================

def load_brain_state(self, state):
    """Load the brain state from a saved state dictionary"""
    self.weights = state['weights']
    self.neuron_positions = state['neuron_positions']
    self.state = state.get('neuron_states', {})
    
    # Load layer structure if present (from custom brain designs)
    self.layers = state.get('layer_structure', [])

    # Ensure all neurons in neuron_positions exist in state
    for neuron in self.neuron_positions:
        if neuron not in self.state:
            self.state[neuron] = 50

    # Explicitly update excluded neurons if they exist in positions
    for neuron in self.excluded_neurons:
        if neuron in self.neuron_positions and neuron not in self.state:
            self.state[neuron] = False

    # Ensure visible_neurons is complete
    if not self.is_tutorial_mode:
        self.visible_neurons = set(self.original_neurons)
        for neuron in self.neuron_positions:
            if neuron not in self.excluded_neurons and neuron not in self.original_neurons:
                self.visible_neurons.add(neuron)
        print(f"📊 Loaded {len(self.neuron_positions)} neurons, {len(self.visible_neurons)} visible")
    
    # >>> ADDED: Mark render dirty and trigger update <<<
    self.mark_render_dirty()
    self.update()


# =============================================================================
# METHOD 7: reveal_neuron (around line 1344)
# Change: Add mark_render_dirty() at the end
# =============================================================================

def reveal_neuron(self, neuron_name):
    """Reveal a neuron with an expand animation – forces links OFF during reveal."""
    import time
    
    if neuron_name not in self.original_neurons:
        return
    if neuron_name in self.visible_neurons:
        return
    if neuron_name not in self.neuron_positions:
        print(f"❌ ERROR: Neuron {neuron_name} has no position defined!")
        return

    # First reveal → force links OFF
    if not self.visible_neurons:
        self.show_links = False
        if hasattr(self, 'parent') and hasattr(self.parent(), 'network_tab'):
            nt = self.parent().network_tab
            nt.checkbox_links.setChecked(False)
            nt.checkbox_links.setEnabled(False)

    # Staggered start
    stagger = 0.4
    delay = len(self.visible_neurons) * stagger

    self.visible_neurons.add(neuron_name)

    # Track this neuron as revealed for count display (tutorial only)
    if self.is_tutorial_mode:
        self.revealed_neurons.add(neuron_name)
        self._reveal_connections_for_neuron(neuron_name)

    # Trigger immediate metrics update
    self._update_network_metrics()

    self.neuron_reveal_animations[neuron_name] = {
        'start_time': time.time() + delay,
        'progress': 0.0
    }

    pos = self.neuron_positions[neuron_name]
    
    # >>> ADDED: Mark render dirty <<<
    self.mark_render_dirty()


# =============================================================================
# METHOD 8: reveal_all_core_neurons (around line 1411)
# Change: Add mark_render_dirty() and update() at the end
# =============================================================================

def reveal_all_core_neurons(self):
    """Make all core neurons visible immediately (for loaded games)"""
    for neuron_name in self.original_neurons:
        self.visible_neurons.add(neuron_name)
    # For loaded games, remove tracking attributes immediately
    if hasattr(self, 'revealed_neurons'):
        delattr(self, 'revealed_neurons')
    if hasattr(self, 'revealed_connections'):
        delattr(self, 'revealed_connections')
    # Ensure tutorial mode is disabled for loaded games
    self.is_tutorial_mode = False
    
    # >>> ADDED: Mark render dirty and trigger update <<<
    self.mark_render_dirty()
    self.update()


# =============================================================================
# METHOD 9: _fast_apply_external_state (around line 2275)
# Change: Add mark_render_dirty() at the end
# =============================================================================

def _fast_apply_external_state(self, new_state):
    """Quickly apply externally provided state (plugin updates, etc.)"""
    for k, v in new_state.items():
        if k in self.neuron_positions:
            if self.is_binary_neuron(k):
                self.state[k] = 100.0 if (v if isinstance(v, bool) else float(v) > 50) else 0.0
            else:
                self.state[k] = float(v) if isinstance(v, (int, float)) else v
    
    # >>> ADDED: Mark render dirty <<<
    self.mark_render_dirty()


# =============================================================================
# METHOD 10: _enable_links_after_reveal (around line 1387)
# Change: Add mark_render_dirty() at the end
# =============================================================================

def _enable_links_after_reveal(self):
    """Re-enable checkbox, tick it, and kick off the existing link-fade engine."""
    self.show_links = True
    
    # Populate link targets for all weights
    for key in self.weights.keys():
        self._link_targets[key] = 1.0
        if key not in self._link_opacities:
            self._link_opacities[key] = 0.0
    
    # Set fade speed
    self._link_fade_speed = 3.0
    
    # Re-enable and check the checkbox
    if hasattr(self, 'parent') and hasattr(self.parent(), 'network_tab'):
        nt = self.parent().network_tab
        nt.checkbox_links.setEnabled(True)
        nt.checkbox_links.setChecked(True)

    # Start the fade timer
    if not self._link_fade_timer.isActive():
        self._link_fade_timer.start()
    
    # >>> ADDED: Mark render dirty <<<
    self.mark_render_dirty()


# =============================================================================
# METHOD 11: toggle_links (around line 3281)
# Change: Add mark_render_dirty() at the end
# =============================================================================

def toggle_links(self, state):
    """
    Public slot connected to the checkbox.
    """
    from PyQt5 import QtCore
    import time
    import random
    
    want_visible = (state == QtCore.Qt.Checked)
    now = time.time()
    
    for key in self.weights.keys():
        self._link_targets[key] = 1.0 if want_visible else 0.0
        self._link_start_times[key] = now + random.uniform(0.0, 0.8)
        self._link_fade_speeds[key] = random.uniform(2.0, 4.5)
        if key not in self._link_opacities:
            self._link_opacities[key] = 1.0 if not want_visible else 0.0
    
    # >>> ADDED: Mark render dirty <<<
    self.mark_render_dirty()
