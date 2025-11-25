import sys
import csv
import os
import time
import math
import random
import numpy as np
import json
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QSplitter
from PyQt5.QtGui import QPixmap, QFont
from datetime import datetime
from .neurogenesis import EnhancedNeurogenesis, ExperienceBuffer
from .enhanced_brain_tooltips import EnhancedBrainTooltips
from .personality import Personality
from .learning import LearningConfig
from .neuro_debug import NeuronLaboratory
from typing import Dict

class BrainWidget(QtWidgets.QWidget):
    neuronClicked = QtCore.pyqtSignal(str)

    def __init__(self, config=None, debug_mode=False, tamagotchi_logic=None):
        self.resolution_scale = 1.0  # Default resolution scale
        self.config = config if config else LearningConfig() #
        self._laboratory = None
        if not hasattr(self.config, 'hebbian'): #
            self.config.hebbian = { #
                'learning_interval': 30000, #
                'weight_decay': 0.01, #
                'active_threshold': 50 #
            }
        super().__init__() #

        # Tutorial glow effect properties
        self.tutorial_glow_active = False
        self.tutorial_glow_timer = None
        self.tutorial_glow_animation = None
        self._tutorial_glow_opacity = 0.0
        self._link_fade_speeds = {}        # (src,dst) → fade speed per link
        self._link_start_times = {}        # (src,dst) → when this link should start

        from .neurogenesis_show import ShowmanNeurogenesis
        real_engine                 = EnhancedNeurogenesis(self, config)
        self.enhanced_neurogenesis  = ShowmanNeurogenesis(real_engine)
        self.excluded_neurons = ['is_sick', 'is_eating', 'pursuing_food', 'direction', 'is_sleeping'] #
        self.hebbian_countdown_seconds = 30  # Default duration
        self.learning_active = True #
        self.pruning_enabled = True #
        self.debug_mode = debug_mode  # Initialize debug_mode
        self.is_paused = False #
        self.last_hebbian_time = time.time() #
        self.last_neurogenesis_type = None
        self.tamagotchi_logic = tamagotchi_logic #
        self.recently_updated_neuron_pairs = [] #
        self.neuron_shapes = {} #
        

        # Neural communication tracking system
        self.communication_events = {} #
        self.communication_highlight_duration = 0.5 #
        self.weight_change_events = {} #
        self.activity_duration = 0.5 #

        # ADDED IN 2.4.5.0: Replace simple neurogenesis_data with enhanced system
        self.enhanced_neurogenesis = EnhancedNeurogenesis(self, self.config)
        self.experience_buffer = self.enhanced_neurogenesis.experience_buffer

        # Ensure neurogenesis config exists
        if not hasattr(self.config, 'neurogenesis'): #
            self.config.neurogenesis = {
                'decay_rate': 0.75,  # Default decay rate if not specified
                'novelty_threshold': 3.0, #
                'stress_threshold': 1.2, #
                'reward_threshold': 3.5, #
                'cooldown': 180, #
                'highlight_duration': 5.0, #
                'max_neurons': 50
            }

        self.neurogenesis_config = self.config.neurogenesis 
        self.neurogenesis_data = {
            'novelty_counter': 0,
            'stress_counter': 0,
            'reward_counter': 0,
            'new_neurons': [],
            'last_neuron_time': time.time(),
            'new_neurons_details': {}   # used by inspector / logging
        }

        # <<< MAX NEURO COUNTER VALUES >>>
        self.max_novelty_counter = 100
        self.max_stress_counter = 100
        self.max_reward_counter = 100

        # Neural state initialization
        self.state = { #
            "hunger": 50, #
            "happiness": 50, #
            "cleanliness": 50, #
            "sleepiness": 50, #
            "satisfaction": 50, #
            "anxiety": 50, #
            "curiosity": 50, #
            "is_sick": False, #
            "is_eating": False, #
            "is_sleeping": False, #
            "pursuing_food": False, #
            "direction": "up", #
            "position": (0, 0), #
            "is_startled": False, #
            "is_fleeing": False, #
            'neurogenesis_active': True
        }

        # Neuron position configuration
        self.original_neuron_positions = { #
            "hunger": (127, 81), #
            "happiness": (361, 81), #
            "cleanliness": (627, 81), #
            "sleepiness": (840, 81), #
            "satisfaction": (271, 380), #
            "anxiety": (491, 389), #
            "curiosity": (701, 386) #
        }
        self.neuron_positions = self.original_neuron_positions.copy() #

        

        # Track which neurons are visible (for animated reveal on new game)
        self.visible_neurons = set()
        # List of core neurons in reveal order
        self.original_neurons = ["hunger", "happiness", "cleanliness", "sleepiness", 
                                 "satisfaction", "anxiety", "curiosity"]
        # Animation state for neuron reveals
        self.neuron_reveal_animations = {}  # {neuron_name: {'start_time': float, 'progress': float}}
        # --- link fade animation ---
        self._link_opacities = {}          # (src,dst) → current opacity 0.0-1.0
        self._link_targets   = {}          # (src,dst) → target opacity  0 or 1
        self._link_fade_timer = QtCore.QTimer(self)
        self._link_fade_timer.setInterval(16)          # ~60 FPS
        self._link_fade_timer.timeout.connect(self._advance_link_fades)
        self._auto_fade_links_pending = False 
        
        # Tutorial mode flag
        self.is_tutorial_mode = False
        
        # Track revealed neurons and connections for synced count display during animation
        # NOTE: These should ONLY be used when is_tutorial_mode is True
        self.revealed_neurons = set()
        self.revealed_connections = set()

        # Initialize communication events for all neurons
        for neuron in self.neuron_positions.keys(): #
            self.communication_events[neuron] = 0 #

        # Animation control variables
        self.animation_timer = QtCore.QTimer(self)
        self.animation_timer.timeout.connect(self.update_animations)
        # NEUROGENESIS FIX: Start monitoring timer
        self.neurogenesis_timer = QtCore.QTimer(self)
        self.neurogenesis_timer.timeout.connect(self._periodic_neurogenesis_check)
        self.neurogenesis_timer.start(2000)  # Check every 2 seconds
        print("🧬 Neurogenesis monitoring timer started")
        self.animation_timer.start(50)  # 20 FPS
        self.neuron_sizes = {}  # For smooth size transitions
        self.weight_animations = []  # Track multiple weight changes
        self.neurogenesis_highlight = {
            'neuron': None,
            'start_time': 0,
            'duration': 5.0,
            'pulse_phase': 0
        }

        # Add neurogenesis visualization tracking
        self.neurogenesis_highlight = { #
            'neuron': None, #
            'start_time': 0, #
            'duration': 5.0  # seconds
        }

        # Connection and weight initialization
        self.connections = self.initialize_connections() #
        self.weights = {}  # Initialize empty dictionary for weights
        self.initialize_weights()  # Populate weights
        self.show_links = True #
        self.frozen_weights = None #
        self.history = [] #
        self.training_data = [] #
        self.associations = np.zeros((len(self.neuron_positions), len(self.neuron_positions))) #
        self.learning_rate = 0.1 #
        self.capture_training_data_enabled = False #
        self.dragging = False #
        self.dragged_neuron = None #
        self.drag_start_pos = None #
        self.tooltip_manager = EnhancedBrainTooltips(self)
        self.setMouseTracking(True)
        self.show_weights = False #
        _link_fade_speed = 3.0   # opacity units per second (tweak for faster/slower)

        # Visual state colors
        self.state_colors = { #
            'is_sick': (255, 204, 204),  # Pastel red
            'is_eating': (204, 255, 204),  # Pastel green
            'is_sleeping': (204, 229, 255),  # Pastel blue
            'pursuing_food': (255, 229, 204),  # Pastel orange
            'direction': (229, 204, 255)  # Pastel purple
        }



    def set_debug_mode(self, enabled):
        """Set debug mode without causing circular callbacks"""
        # Only proceed if there's an actual change
        if self.debug_mode == enabled:
            return

        # Update our own state
        self.debug_mode = enabled

        # Update brain widget
        if hasattr(self, 'brain_widget'):
            self.brain_widget.debug_mode = enabled

        # Update tabs
        for tab_name in ['network_tab', 'nn_viz_tab', 'memory_tab', 'decisions_tab', 'about_tab']:
            if hasattr(self, tab_name):
                tab = getattr(self, tab_name)
                if hasattr(tab, 'debug_mode'):
                    tab.debug_mode = enabled

        # Enable/disable debug-specific UI elements
        if hasattr(self, 'stimulate_button'):
            self.stimulate_button.setEnabled(enabled)

        print(f"Brain window debug mode set to: {enabled}")

        
    def is_neuron_revealed(self, name):
        """Return True if the neuron has finished its reveal animation.
        Only checks revealed tracking during tutorial mode."""
        # In normal gameplay (not tutorial), all neurons are considered revealed
        if not self.is_tutorial_mode:
            return True
            
        # During tutorial, check if neuron has completed its animation
        if name not in self.neuron_reveal_animations:
            return name in self.visible_neurons  # never animated = already visible
        anim = self.neuron_reveal_animations[name]
        elapsed = time.time() - anim['start_time']
        return elapsed >= 0.4  # same duration used in draw_neurons
    

    def _advance_link_fades(self):
        """Called every 16 ms while any line is still moving."""
        dt = 0.016
        still_animating = False
        now = time.time()

        for key, target in list(self._link_targets.items()):
            # Check if this link's delay has passed
            start_time = self._link_start_times.get(key, 0)
            if now < start_time:
                still_animating = True
                continue
                
            current = self._link_opacities.get(key, 0.0)
            # Use per-link speed for individual animation timing
            speed = self._link_fade_speeds.get(key, 3.0)
            step = speed * dt
            
            if abs(target - current) <= step:        # arrived
                self._link_opacities[key] = target
                del self._link_targets[key]          # stop tracking this one
                if key in self._link_start_times:
                    del self._link_start_times[key]
                if key in self._link_fade_speeds:
                    del self._link_fade_speeds[key]
            else:                                    # move one step
                self._link_opacities[key] = current + step * (1 if target > current else -1)
                still_animating = True

        self.update()                                # repaint with new alphas

        if not still_animating:                      # all lines finished
            self._link_fade_timer.stop()

    def update_animations(self):
        """Update all animation states"""
        current_time = time.time()

        # 1. update neurogenesis pulse
        if self.neurogenesis_highlight['neuron']:
            elapsed = current_time - self.neurogenesis_highlight['start_time']
            if elapsed < self.neurogenesis_highlight['duration']:
                self.neurogenesis_highlight['pulse_phase'] = elapsed * 15
            else:
                self.neurogenesis_highlight['neuron'] = None

        # 2. update neuron reveal animations
        completed_reveals = []
        for neuron_name, anim_data in self.neuron_reveal_animations.items():
            elapsed = current_time - anim_data['start_time']
            duration = 0.4
            if elapsed >= duration:
                anim_data['progress'] = 1.0
                completed_reveals.append(neuron_name)
            else:
                progress = elapsed / duration
                anim_data['progress'] = 1 - (1 - progress) ** 3

        for neuron_name in completed_reveals:
            del self.neuron_reveal_animations[neuron_name]

        # NEW: when the LAST neuron animation completes, immediately enable links
        if (len(self.visible_neurons) == len(self.original_neurons) and
            not self.neuron_reveal_animations and
            not self.show_links):                    # only once
            self._enable_links_after_reveal()

        # 3. weight animations (unchanged)
        self.weight_animations = [
            anim for anim in self.weight_animations
            if current_time - anim['start_time'] < anim['duration']
        ]
        self.update()

    def reveal_neuron(self, neuron_name):
        """Reveal a neuron with an expand animation – forces links OFF during reveal."""
        if neuron_name not in self.original_neurons:
            return
        if neuron_name in self.visible_neurons:
            return
        if neuron_name not in self.neuron_positions:
            print(f"❌ ERROR: Neuron {neuron_name} has no position defined!")
            return

        # ┌----------------------------------------------------------┐
        # │ 1.  FIRST REVEAL → force links OFF  (any game mode)      │
        # └----------------------------------------------------------┘
        if not self.visible_neurons:                       # very first neuron
            self.show_links = False
            if hasattr(self, 'parent') and hasattr(self.parent(), 'network_tab'):
                nt = self.parent().network_tab
                nt.checkbox_links.setChecked(False)
                nt.checkbox_links.setEnabled(False)      # user can’t turn it on

        # ---------- staggered start ----------
        stagger = 0.4
        delay = len(self.visible_neurons) * stagger

        self.visible_neurons.add(neuron_name)

        # Track this neuron as revealed for count display (tutorial only)
        if self.is_tutorial_mode:
            self.revealed_neurons.add(neuron_name)
            # Reveal connections between already-revealed neurons
            self._reveal_connections_for_neuron(neuron_name)

        # Trigger immediate metrics update to show new counts
        self._update_network_metrics()

        self.neuron_reveal_animations[neuron_name] = {
            'start_time': time.time() + delay,
            'progress': 0.0
        }

        pos = self.neuron_positions[neuron_name]
        # (any existing logging / diagnostics you had can stay here)

    def _enable_links_after_reveal(self):
        """Re-enable checkbox, tick it, and kick off the existing link-fade engine."""
        self.show_links = True
        
        # Populate link targets for all weights (like toggle_links does)
        for key in self.weights.keys():
            self._link_targets[key] = 1.0  # Target full opacity
            # Initialize opacity if not already set
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
        #print("🧠 All core neurons revealed")
    
    def _reveal_connections_for_neuron(self, neuron_name):
        """Reveal connections between this neuron and other revealed neurons
        NOTE: This should only be called during tutorial mode"""
        if not self.is_tutorial_mode:
            return
        if not hasattr(self, 'weights'):
            return
        if not hasattr(self, 'revealed_neurons') or not hasattr(self, 'revealed_connections'):
            return
            
        # Check all weights to find connections involving this neuron
        for (source, target), weight in self.weights.items():
            # If both ends of the connection are revealed, track it
            if source in self.revealed_neurons and target in self.revealed_neurons:
                edge_key = f"{source}->{target}"
                if edge_key not in self.revealed_connections:
                    self.revealed_connections.add(edge_key)
    
    def _update_network_metrics(self):
        """Update the network tab metrics display"""
        try:
            # Try to get the parent window (SquidBrainWindow)
            parent = self.parent()
            if parent and hasattr(parent, 'network_tab'):
                parent.network_tab.update_metrics_display()
        except Exception as e:
            pass  # Silently fail if we can't update - not critical
    
    def finish_reveal_animation(self):
        """Called when the reveal animation completes - cleanup tracking attributes"""
        # Remove reveal tracking so normal counting resumes
        if hasattr(self, 'revealed_neurons'):
            delattr(self, 'revealed_neurons')
        if hasattr(self, 'revealed_connections'):
            delattr(self, 'revealed_connections')

        # Exit tutorial mode
        self.is_tutorial_mode = False

        # AUTO-ENABLE links now that all neurons are revealed
        self.show_links = True
        if hasattr(self, 'parent') and hasattr(self.parent(), 'network_tab'):
            nt = self.parent().network_tab
            nt.checkbox_links.setEnabled(True)
            nt.checkbox_links.setChecked(True)      # tick the box

        # Fade-in the links smoothly
        if self.show_links and self._link_targets:
            self._auto_fade_links_pending = True
            if not self._link_fade_timer.isActive():
                self._advance_link_fades()

    def add_weight_animation(self, neuron1, neuron2, old_weight, new_weight):
        """Add animation for a weight change without modifying the weight itself"""
        current_time = time.time()
        pair = (neuron1, neuron2)
        
        # Add to animations list
        self.weight_animations.append({
            'pair': pair,
            'start_time': current_time,
            'duration': 2.0,
            'start_weight': old_weight,
            'end_weight': new_weight,
            'neuron1': neuron1,
            'neuron2': neuron2,
            'color': (0, 255, 0) if new_weight > old_weight else (255, 0, 0),
            'pulse_speed': 0.5
        })
        
        # Record communication events
        self.weight_change_events[neuron1] = current_time
        self.weight_change_events[neuron2] = current_time
        
        # Add to recently updated pairs
        if (neuron1, neuron2) not in self.recently_updated_neuron_pairs and \
        (neuron2, neuron1) not in self.recently_updated_neuron_pairs:
            self.recently_updated_neuron_pairs.append((neuron1, neuron2))

    def is_neurogenesis_neuron(self, neuron_name: str) -> bool:
        """
        Check if a neuron was created through neurogenesis (and can be dragged).
        TO BE REMOVED IN FUTURE VERSION - depreceted
        """
        
        if not neuron_name:
            return False
        
        # Core neurons that should NOT be draggable
        if neuron_name in self.original_neurons:
            return False
        
        # ANY neuron not in original_neurons is draggable (including circular ones)
        return True

    def _periodic_neurogenesis_check(self):
        """
        Periodic check for neurogenesis triggers.
        This method is called every 2 seconds by self.neurogenesis_timer.
        """
        if not hasattr(self, 'check_neurogenesis_triggers'):
            return
        
        # Build state with context
        state_with_context = self.state.copy()
        
        # Add environmental data if available
        if hasattr(self, 'parent') and hasattr(self.parent, 'tamagotchi_logic'):
            logic = self.parent.tamagotchi_logic
            if hasattr(logic, 'food_items'):
                state_with_context['food_count'] = len(logic.food_items)
            if hasattr(logic, 'poop_items'):
                state_with_context['poop_count'] = len(logic.poop_items)
            if hasattr(logic, 'squid'):
                state_with_context['carrying_rock'] = logic.squid.carrying_rock
        
        # Add empty recent_actions if not present
        if 'recent_actions' not in state_with_context:
            state_with_context['recent_actions'] = []
        
        try:
            created = self.check_neurogenesis_triggers(state_with_context)
            if created:
                print(f"✨ Neurogenesis triggered! New neuron created.")
        except Exception as e:
            print(f"⚠️ Neurogenesis check error: {e}")
            import traceback
            traceback.print_exc()

    def toggle_pruning(self, enabled):
        """Enable or disable the pruning mechanisms for neurogenesis"""
        previous = self.pruning_enabled
        self.pruning_enabled = enabled

        if previous != enabled:
            print(f"\x1b[{'42' if enabled else '41'}mPruning {'enabled' if enabled else 'disabled'}\x1b[0m - Neurogenesis {'constrained' if enabled else 'unconstrained'}")

            if not enabled:
                print("\x1b[31mWARNING: Disabling pruning may lead to network instability\x1b[0m")

        return self.pruning_enabled
    
    def get_stress_neuron_count(self):
        """Counts the number of neurons that start with the name 'stress'."""
        return len([name for name in self.neuron_positions if name.startswith('stress')])

    def stop_hebbian_learning(self):
        """Stop Hebbian learning immediately"""
        self.learning_active = False
        self.hebbian_countdown_seconds = 0
        print("++ Hebbian learning stopped")

    def start_hebbian_learning(self, duration_seconds=30):
        """Start Hebbian learning with a specified duration"""
        self.hebbian_countdown_seconds = duration_seconds
        self.learning_active = True
        self.is_paused = False
        print(f"++ Hebbian learning started for {duration_seconds} seconds")

    def _update_communication_events(self):
        """Clean up old communication events that have expired"""
        current_time = time.time()
        # Remove events older than the highlight duration
        expired_neurons = [
            neuron for neuron, event_time in self.communication_events.items()
            if current_time - event_time > self.communication_highlight_duration
        ]
        for neuron in expired_neurons:
            del self.communication_events[neuron]

    def get_neuron_value(self, value):
        """
        Convert a neuron value to a numerical format for Hebbian learning.

        Args:
            value: The value of the neuron, which can be int, float, bool, or str.

        Returns:
            float: The numerical value of the neuron.
        """
        if isinstance(value, (int, float)):
            return float(value)
        elif isinstance(value, bool):
            return 100.0 if value else 0.0
        elif isinstance(value, str):
            # For string values (like 'direction'), return a default value
            return 75.0
        else:
            return 0.0
        
    def is_new_neuron(self, neuron_name, newness_duration_sec=300): # 300s = 5 minutes
        """Check if a neuron was created within the newness duration."""
        # Check if it's in the primary neurogenesis data
        if neuron_name in self.neurogenesis_data.get('new_neurons', []):
            details = self.neurogenesis_data.get('new_neurons_details', {}).get(neuron_name)
            if details:
                created_at = details.get('created_at')
                if created_at and (time.time() - created_at) < newness_duration_sec:
                    return True # It's new based on details
            else:
                 # If no details but in list, assume it might be new (fallback)
                 # You might want to refine this based on how 'new_neurons' is managed.
                 # For now, if it's in the list and < 5 mins, assume new.
                 # A better check is needed if 'new_neurons' isn't pruned.
                 # Let's rely *only* on details for a stricter check.
                 pass
        return False


    def update_connection(self, neuron1, neuron2, value1, value2):
        """Update connection weight and trigger animations"""
        current_time = time.time()
        pair = (neuron1, neuron2)
        reverse_pair = (neuron2, neuron1)

        # Check if the pair or its reverse exists in weights, if not, initialize it
        if pair not in self.weights and reverse_pair not in self.weights:
            # Only add if both neurons exist
            if neuron1 in self.neuron_positions and neuron2 in self.neuron_positions:
                self.weights[pair] = 0.0  # Start with 0 weight
                print(f"      🆕 Created new connection: {neuron1} ↔ {neuron2}")
            else:
                print(f"      ⚠️  Cannot create connection: {neuron1} or {neuron2} doesn't exist in neuron_positions")
                return  # Don't create connection if a neuron doesn't exist

        # Use the correct pair order
        use_pair = pair if pair in self.weights else reverse_pair
        
        # Ensure the pair still exists before proceeding (might be pruned)
        if use_pair not in self.weights:
            print(f"      ⚠️  Connection was pruned, skipping update for {neuron1} ↔ {neuron2}")
            return

        prev_weight = self.weights[use_pair]

        # --- Learning Rate Calculation ---
        base_lr = self.learning_rate
        newness_boost = 2.0  # New neurons learn 2x faster
        effective_lr = base_lr

        is_n1_new = self.is_new_neuron(neuron1)
        is_n2_new = self.is_new_neuron(neuron2)

        if is_n1_new or is_n2_new:
            effective_lr = base_lr * newness_boost
        # --- End Learning Rate ---

        # Calculate weight change (basic Hebbian)
        weight_change = effective_lr * (value1 / 100.0) * (value2 / 100.0)
        
        # Add weight decay (optional but good for stability)
        decay_rate = self.config.hebbian.get('weight_decay', 0.01) * 0.1  # Slow decay during learning
        new_weight = prev_weight + weight_change - (prev_weight * decay_rate)
        
        # Clamp weight to [-1, 1] range
        new_weight = min(max(new_weight, -1.0), 1.0)
        self.weights[use_pair] = new_weight

        # Add animation using helper method
        self.add_weight_animation(neuron1, neuron2, prev_weight, new_weight)

        # Record weight change time for both neurons
        if abs(new_weight - prev_weight) > 0.001:  # Only if significant change
            self.weight_change_events[neuron1] = current_time
            self.weight_change_events[neuron2] = current_time
            
            # Add to recently updated for visualization/logging
            if (neuron1, neuron2) not in self.recently_updated_neuron_pairs and \
            (neuron2, neuron1) not in self.recently_updated_neuron_pairs:
                self.recently_updated_neuron_pairs.append((neuron1, neuron2))
            
            # Trigger visual update
            self.update()

        # Record communication time for both neurons
        self.communication_events[neuron1] = current_time
        self.communication_events[neuron2] = current_time

        # Debug output with color coding
        lr_indicator = " (\x1b[35mBOOSTED\x1b[0m)" if effective_lr > base_lr else ""
        direction = "\x1b[32m↑\x1b[0m" if new_weight > prev_weight else "\x1b[31m↓\x1b[0m"
        print(f"      \x1b[42mUpdated\x1b[0m {direction} {neuron1} ↔ {neuron2}: "
            f"\x1b[31m{prev_weight:.3f}\x1b[0m → \x1b[32m{new_weight:.3f}\x1b[0m "
            f"(Δ={weight_change:.3f}, LR={effective_lr:.3f}{lr_indicator})")

    def prune_weak_connections(self, threshold=0.05, min_age_sec=600): # Prune if < 0.05 abs weight & > 10 mins old
        """Removes connections with absolute weight below the threshold, ignoring new neurons."""
        if not self.pruning_enabled: # Respect the global pruning flag
            return 0

        current_time = time.time()
        to_delete = []

        # Iterate over a copy of keys to allow deletion during iteration
        for pair, weight in list(self.weights.items()):
            # Ensure pair is a valid tuple
            if not (isinstance(pair, tuple) and len(pair) == 2):
                # print(f"Skipping invalid weight key during pruning: {pair}") # Optional Debug
                continue

            neuron1, neuron2 = pair

            # Don't prune if either neuron is "new" (gives them time to establish)
            if self.is_new_neuron(neuron1, min_age_sec) or self.is_new_neuron(neuron2, min_age_sec):
                continue
            
            # Don't prune connections involving core/original neurons (optional, but safer)
            # if neuron1 in self.original_neuron_positions or neuron2 in self.original_neuron_positions:
            #    continue

            # Check if absolute weight is below the threshold
            if abs(weight) < threshold:
                to_delete.append(pair)

        for pair in to_delete:
            if pair in self.weights:
                del self.weights[pair]

        if len(to_delete) > 0:
            print(f"\x1b[33mPruned {len(to_delete)} weak connections (Threshold: {threshold}).\x1b[0m")
            self.update() # Update visualization if connections changed
        
        return len(to_delete) # Return how many were pruned


    def perform_hebbian_learning(self):
        """
        One full Hebbian update cycle.
        The number of neuron pairs updated is read from config.ini
        (key max_hebbian_pairs in the [Neurogenesis] section).
        """
        from heapq import nlargest

        # --- COLOR SETUP ---
        COLORS = [
            "\033[96m",  # CYAN
            "\033[93m",  # YELLOW/ORANGE
            "\033[95m",  # MAGENTA
            "\033[92m",  # GREEN
            "\033[94m",  # BLUE
        ]
        RESET = "\033[0m"
        # --------------------

        if not hasattr(self, 'weights'):
            self.weights = {}
        self.recently_updated_neuron_pairs.clear()

        # 1. collect real neurons only
        neurons = [n for n in self.neuron_positions.keys() if n not in self.excluded_neurons]

        # 2. score every possible pair by summed activation
        scored_pairs = []
        for i, n1 in enumerate(neurons):
            for n2 in neurons[i + 1:]:
                v1 = self.get_neuron_value(self.state[n1])
                v2 = self.get_neuron_value(self.state[n2])
                score = v1 + v2
                scored_pairs.append((score, n1, n2, v1, v2))

        # 3. grab the configurable number of top pairs
        top_k = self.config.neurogenesis.get('max_hebbian_pairs', 2)
        top_pairs = nlargest(top_k, scored_pairs)

        # 4. classic Hebbian update on those pairs with animations
        updated_pairs = []
        current_time = time.time()

        for _, n1, n2, v1, v2 in top_pairs:
            base_lr = self.learning_rate
            decay_rate = self.config.hebbian.get('weight_decay', 0.01)

            is_n1_new = self.is_new_neuron(n1)
            is_n2_new = self.is_new_neuron(n2)
            if is_n1_new or is_n2_new:
                base_lr *= 2.0

            delta = base_lr * (v1 / 100.0) * (v2 / 100.0)

            pair = (n1, n2)
            reverse_pair = (n2, n1)
            use_pair = pair if pair in self.weights else reverse_pair

            if use_pair not in self.weights:
                continue

            old_w = self.weights[use_pair]
            new_w = old_w + delta - (old_w * decay_rate)
            new_w = max(self.config.hebbian['min_weight'],
                        min(self.config.hebbian['max_weight'], new_w))

            self.weights[use_pair] = new_w
            self.add_weight_animation(n1, n2, old_w, new_w)
            updated_pairs.append((n1, n2))

        # 5. console & UI feed
        if updated_pairs:
            colored = []
            for i, (a, b) in enumerate(updated_pairs):
                color = COLORS[i % len(COLORS)]
                colored.append(f"{color}{a} ↔ {b}{RESET}")

            print("     Hebbian learning chosen pairs: " + "  ".join(colored))

        self.recently_updated_neuron_pairs = updated_pairs
        self.last_hebbian_time = time.time()

        # trigger visual update
        self.update()


    def get_recently_updated_neurons(self):
        """Return the list of neuron pairs updated in the last learning cycle"""
        return self.recently_updated_neuron_pairs


    def resizeEvent(self, event):
        """Handle window resize events - startles squid and enforces minimum size"""
        super().resizeEvent(event)

        # Only trigger startle if we're actually resizing (not just moving)
        old_size = event.oldSize()
        if (old_size.isValid() and
            hasattr(self, 'tamagotchi_logic') and
            self.tamagotchi_logic):

            new_size = event.size()
            width_change = abs(new_size.width() - old_size.width())
            height_change = abs(new_size.height() - old_size.height())

            # Only startle if change is significant (>50px)
            if width_change > 50 or height_change > 50:
                # Check if first resize
                if not hasattr(self, '_has_resized_before'):
                    source = "first_resize"
                    self._has_resized_before = True
                else:
                    source = "window_resize"

                #self.tamagotchi_logic.startle_squid(source=source) #STARTLE WHEN WINDOW RESIZE

                if self.debug_mode:
                    print(f"Squid startled by {source}")

        # Enforce minimum window size (1280x900)
        min_width, min_height = 1280, 900
        if event.size().width() < min_width or event.size().height() < min_height:
            self.resize(
                max(event.size().width(), min_width),
                max(event.size().height(), min_height)
            )

    def closeEvent(self, event):
        """Handle window close event - save state and clean up resources"""
        if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic:
            # Save current brain state
            try:
                brain_state = self.save_brain_state()
                with open('last_brain_state.json', 'w') as f:
                    json.dump(brain_state, f)
            except Exception as e:
                print(f"Error saving brain state: {e}")

            # Clean up timers
            if hasattr(self, 'hebbian_timer'):
                self.hebbian_timer.stop()
            if hasattr(self, 'countdown_timer'):
                self.countdown_timer.stop()
            if hasattr(self, 'memory_update_timer'):
                self.memory_update_timer.stop()

        # Close any child windows
        if hasattr(self, '_inspector') and self._inspector: 
            self._inspector.close()
            
        if hasattr(self, '_laboratory') and self._laboratory:
            self._laboratory.close()
        
        # Accept the close event 
        event.accept()

    def save_brain_state(self):
        return {
            'weights': self.weights,
            'neuron_positions': self.neuron_positions,
            'neuron_states': self.state
        }

    def load_brain_state(self, state):
        """Load the brain state from a saved state dictionary"""
        self.weights = state['weights']
        self.neuron_positions = state['neuron_positions']
        # Load neuron states, defaulting to empty dict if not present
        self.state = state.get('neuron_states', {})

        # Ensure all neurons in neuron_positions exist in state
        for neuron in self.neuron_positions:
            if neuron not in self.state:
                # Initialize missing neurons with default value
                self.state[neuron] = 50  # Default activation value

        # Explicitly update excluded neurons if they exist in positions
        for neuron in self.excluded_neurons:
            if neuron in self.neuron_positions and neuron not in self.state:
                self.state[neuron] = False  # Default boolean state

        # Ensure visible_neurons is complete if not in tutorial mode
        if not self.is_tutorial_mode and len(self.visible_neurons) < len(self.original_neurons):
            print(f"⚠️  Loaded state had incomplete visible_neurons. Resetting to all core neurons.")
            self.visible_neurons = set(self.original_neurons)

    def create_initial_state(self):
        """
        Create and return the initial brain state for a new game.
        Returns a dictionary with all core neurons set to their default values.
        Also resets animation tracking attributes.
        """
        # Reset animation tracking attributes
        self.reset_animation_state()
        
        initial_state = {
            "hunger": 50,
            "happiness": 50,
            "cleanliness": 50,
            "sleepiness": 50,
            "satisfaction": 50,
            "anxiety": 50,
            "curiosity": 50,
            "is_sick": False,
            "is_eating": False,
            "is_sleeping": False,
            "pursuing_food": False,
            "direction": "up",
            "position": (0, 0),
            "is_startled": False,
            "is_fleeing": False,
            'neurogenesis_active': True
        }
        return initial_state
    
    def reset_animation_state(self):
        """
        Reset all animation and reveal tracking attributes for a new game.
        This ensures the neuron reveal animation can run properly.
        """
        # Enable tutorial mode for new game reveal animation
        self.is_tutorial_mode = True
        
        # Reset visible neurons
        self.visible_neurons = set()
        
        # Reset reveal tracking (recreate if deleted)
        self.revealed_neurons = set()
        self.revealed_connections = set()
        
        # Clear reveal animations
        self.neuron_reveal_animations = {}
        
        print("🔄 Animation state reset for new game (tutorial mode enabled)")

    def initialize_connections(self):
        connections = []
        neurons = list(self.neuron_positions.keys())
        for i in range(len(neurons)):
            for j in range(i+1, len(neurons)):
                connections.append((neurons[i], neurons[j]))
        return connections

    def initialize_weights(self):
        neurons = list(self.neuron_positions.keys())
        for i in range(len(neurons)):
            for j in range(i+1, len(neurons)):
                self.weights[(neurons[i], neurons[j])] = random.uniform(-1, 1)

    def get_neuron_count(self):
        """Returns the actual count of neurons in the network positions."""
        return len(self.neuron_positions)

    def get_edge_count(self):
        """Returns the actual count of connections (weights) in the network."""
        return len(self.weights) # MODIFIED: Use self.weights

    def get_weakest_connections(self, n=3):
        """Return the n weakest connections by absolute weight"""
        if not hasattr(self, 'weights') or not self.weights:
            return []

        sorted_weights = sorted(self.weights.items(), key=lambda x: abs(x[1]))
        return sorted_weights[:n]  # Returns list of ((source, target), weight) tuples

    def get_extreme_neurons(self, n=3):
        """Return neurons deviating most from baseline (50)"""
        neurons = [(k, v) for k, v in self.state.items()
                if isinstance(v, (int, float)) and k in self.neuron_positions]
        most_positive = sorted(neurons, key=lambda x: -x[1])[:n]
        most_negative = sorted(neurons, key=lambda x: x[1])[:n]
        return {'overactive': most_positive, 'underactive': most_negative}

    def get_unbalanced_connections(self, n=3):
        """Return connections with largest weight disparities"""
        unbalanced = []
        for (a, b), w1 in self.weights.items():
            w2 = self.weights.get((b, a), 0)
            if abs(w1 - w2) > 0.3:  # Only consider significant differences
                unbalanced.append(((a, b), (w1, w2), abs(w1 - w2)))
        return sorted(unbalanced, key=lambda x: -x[2])[:n]

    def calculate_network_health(self):
        """Calculate network health based on connection weights and neuron activity"""
        total_weight = sum(abs(w) for w in self.weights.values())
        avg_weight = total_weight / len(self.weights) if self.weights else 0
        health = min(100, max(0, avg_weight * 100))
        return health

    def calculate_network_efficiency(self):
        """Calculate network efficiency based on connection distribution"""
        if not self.connections:
            return 0
        reciprocal_count = 0
        for conn in self.connections:
            reverse_conn = (conn[1], conn[0])
            if reverse_conn in self.connections:
                reciprocal_count += 1
        efficiency = (reciprocal_count / len(self.connections)) * 100
        return efficiency

    def log_neurogenesis_event(self, neuron_name, event_type, reason=None, details=None):
        """Log neurogenesis events in a human-readable paragraph format."""
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = ""

        if event_type == "created" and details:
            neuron_type = details.get("trigger_type")
            trigger_value = details.get("trigger_value", 0.0)

            if not neuron_type:
                return # Cannot log without a neuron type

            # General creation message
            log_entry += f"{timestamp} - a {neuron_type.upper()} neuron ({neuron_name}) was created because {neuron_type} counter was {trigger_value:.2f}\n"

            # Specific details for stress neurons
            if neuron_type == "stress":
                log_entry += "An inhibitory connection was made to ANXIETY\n"
                log_entry += "Maximum anxiety value has been permanently reduced by 10\n"

        elif event_type == "pruned":
            # A more consistent format for pruned events
            timestamp_full = datetime.now().strftime("%H:%M:%S")
            log_entry = f"{timestamp_full} - a neuron ({neuron_name}) was PRUNED due to {reason if reason else 'unknown reason'}\n"

        if log_entry:
            try:
                with open('neurogenesis_log.txt', 'a', encoding='utf-8') as f:
                    f.write(log_entry)
                    # Always add the separator after an entry
                    f.write("\n-------------------------------\n\n")
            except Exception as e:
                print(f"\x1b[31mNeurogenesis logging failed: {str(e)}\x1b[0m")

    def update_state(self, new_state: Dict[str, float]):
        """
        COMPLETE: Update brain state with clamping, decay, and state change detection.
        Prevents stagnation at extreme values.
        
        NOTE: Neurogenesis checks are handled by _periodic_neurogenesis_check(), 
        not here, to avoid redundancy.
        """
        # Track if any meaningful state changes occurred
        state_changed = False
        old_state = self.state.copy()
        current_time = time.time()  # Define once for timestamp updates
        
        # ===== PREVENT STAGNATION WITH NORMALIZATION =====
        for neuron, value in new_state.items():
            # Validate neuron exists
            if neuron not in self.neuron_positions:
                continue
                
            # 1. Clamp to valid range (0-100)
            value = max(0, min(100, value))
            
            # 2. Apply gentle decay if stuck at extremes
            current_value = self.state.get(neuron, 50)
            if abs(current_value - 50) > 30:  # If far from baseline
                decay_rate = 0.02  # 2% per update
                if current_value > 50:
                    value = current_value - (decay_rate * (current_value - 50))
                else:
                    value = current_value + (decay_rate * (50 - current_value))
            
            # 3. Add slight random noise to prevent perfect stability
            noise = random.uniform(-0.5, 0.5)
            value += noise
            
            # 4. Re-clamp after modifications
            value = max(0, min(100, value))
            
            # Store the updated value
            self.state[neuron] = value
            
            # Check if this was a meaningful change
            if abs(value - old_state.get(neuron, 50)) > 2.0:  # Threshold: must change >2 points
                state_changed = True
        # =========================================================
        
        # Update communication events for visual feedback
        for neuron in self.state.keys():
            if neuron not in self.communication_events:
                self.communication_events[neuron] = 0
            
            neuron_value = self.get_neuron_value(self.state[neuron])
            if abs(neuron_value - 50) > 20:  # If significantly active
                self.communication_events[neuron] = current_time
        
        # ===== REMOVED: Redundant neurogenesis triggering =====
        # Neurogenesis is now handled solely by _periodic_neurogenesis_check()
        # which runs every 2 seconds via self.neurogenesis_timer
        # This eliminates duplicate experience capture and potential conflicts
        # ======================================================
        
        # ===== UPDATE FUNCTIONAL NEURONS =====
        # Let existing functional neurons calculate their activation
        if hasattr(self, 'enhanced_neurogenesis') and self.enhanced_neurogenesis.functional_neurons:
            self.enhanced_neurogenesis.update_neuron_activations(self.state)
        
        # ===== SCHEDULE VISUAL UPDATE =====
        # Trigger redraw of brain visualization
        self.update()
        
        # ===== LOG MAJOR STATE CHANGES =====
        if self.debug_mode and state_changed:
            active_neurons = {k: v for k, v in self.state.items() if abs(v - 50) > 25}
            if active_neurons:
                print(f"🧠 State update: {len(active_neurons)} neurons active")
                for neuron, value in active_neurons.items():
                    print(f"   {neuron}: {value:.1f}")

    def provide_outcome_feedback(self, outcome_value: float):
        """
        Provide feedback to recently activated neurons.
        outcome_value: 1.0 = very positive, 0.0 = neutral, -1.0 = very negative
        """
        if not hasattr(self, 'enhanced_neurogenesis'):
            return
        
        current_time = time.time()
        
        # Update utility scores for recently active neurons
        for name, func_neuron in self.enhanced_neurogenesis.functional_neurons.items():
            # Was this neuron recently active?
            # Check if func_neuron has the last_activated attribute (for FunctionalNeuron objects)
            if hasattr(func_neuron, 'last_activated') and current_time - func_neuron.last_activated < 30:  # 30 seconds
                if hasattr(func_neuron, 'update_utility_score'):
                    func_neuron.update_utility_score(outcome_value)


    
    
    def check_neurogenesis_triggers(self, state):
        """Enhanced neurogenesis check with proper trigger priority"""
        if not state.get('neurogenesis_active', True):
            return False
        
        # Build experience context
        recent_actions = state.get('recent_actions', [])
        environment = {
            'food_count': state.get('food_count', 0),
            'poop_count': state.get('poop_count', 0),
            'has_rock': state.get('carrying_rock', False)
        }
        
        # ===== FIX: PROPER TRIGGER PRIORITY WITH EMERGENCY OVERRIDE =====
        trigger_type = None
        
        # 🚨 HIGHEST PRIORITY: Emergency stress (overrides everything)
        if state.get('anxiety', 50) >= 95:
            trigger_type = 'stress'
            print(f"🚨 EMERGENCY: Critical anxiety level ({state.get('anxiety', 50):.1f})!")
        
        # HIGH PRIORITY: Stress (anxiety or sustained stress)
        elif state.get('anxiety', 50) > 75 or state.get('sustained_stress', 0) > 1:
            trigger_type = 'stress'
        
        # MEDIUM PRIORITY: Novelty (curiosity or new objects)
        elif state.get('curiosity', 50) > 70 or state.get('novelty_exposure', 0) > 2:
            trigger_type = 'novelty'
        
        # LOW PRIORITY: Reward (satisfaction or positive outcomes)
        elif state.get('satisfaction', 50) > 70 or state.get('recent_rewards', 0) > 2:
            trigger_type = 'reward'
        # ================================================================
        
        if trigger_type:
            # Capture full experience context
            context = self.enhanced_neurogenesis.capture_experience_context(
                trigger_type=trigger_type,
                brain_state=self.state,
                recent_actions=recent_actions,
                environment=environment
            )
            
            # Add to experience buffer
            self.experience_buffer.add_experience(context)
            
            # Check if we should create a neuron
            if self.enhanced_neurogenesis.should_create_neuron(context):
                neuron_name = self.enhanced_neurogenesis.create_functional_neuron(context)
                
                if neuron_name and self.pruning_enabled:
                    # Check if we need to prune
                    current_count = len(self.neuron_positions) - len(self.excluded_neurons)
                    max_neurons = self.neurogenesis_config.get('max_neurons', 32)
                    
                    if current_count > max_neurons * 0.85:
                        self.enhanced_neurogenesis.intelligent_pruning()
                
                return neuron_name is not None
        
        return False

    def get_neurogenesis_threshold(self, trigger_type):
        """Safely get threshold for a trigger type with fallback defaults"""
        try:
            return self.neurogenesis_config['triggers'][trigger_type]['threshold']
        except KeyError:
            defaults = {'novelty': 0.7, 'stress': 0.8, 'reward': 0.6}
            return defaults.get(trigger_type, 1.0)

    def stimulate_brain(self, stimulation_values):
        """Handle brain stimulation with validation"""
        if not isinstance(stimulation_values, dict):
            return
        filtered_update = {}
        for key in self.state.keys():
            if key in stimulation_values:
                filtered_update[key] = stimulation_values[key]
        self.update_state(filtered_update)

    def get_adjusted_threshold(self, base_threshold, trigger_type):
        """Scale threshold based on network size to prevent runaway neurogenesis"""
        original_count = len(self.original_neuron_positions)
        current_count = len(self.neuron_positions) - len(self.excluded_neurons)
        new_neuron_count = current_count - original_count
        baseline = original_count + 3
        if new_neuron_count <= 0 or current_count <= baseline:
            return base_threshold
        scaling_factors = {'novelty': 0.25, 'stress': 0.1, 'reward': 0.08}
        scaling_factor = scaling_factors.get(trigger_type, 0.15)
        multiplier = 1.0 + (scaling_factor * (new_neuron_count - baseline + 1))
        adjusted = base_threshold * multiplier
        return adjusted

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
            if neuron_to_remove in self.neuron_positions: del self.neuron_positions[neuron_to_remove]
            if neuron_to_remove in self.state: del self.state[neuron_to_remove]
            for conn in list(self.weights.keys()):
                if isinstance(conn, tuple) and (conn[0] == neuron_to_remove or conn[1] == neuron_to_remove):
                    del self.weights[conn]
            if neuron_to_remove in self.neurogenesis_data.get('new_neurons', []):
                self.neurogenesis_data['new_neurons'].remove(neuron_to_remove)
            reason = "weak connections/activity"
            self.log_neurogenesis_event(neuron_to_remove, "pruned", reason)
            return True
        return False

    def _create_neuron_internal(self, neuron_type, state, trigger_value_for_log=None):
        """Create a new neuron with strong defaults + weak exploratory wires."""
        current_neuron_count = len(self.neuron_positions) - len(self.excluded_neurons)
        max_neurons_config   = self.neurogenesis_config.get('max_neurons', 32)
        if self.pruning_enabled and current_neuron_count >= max_neurons_config:
            print(f"\x1b[33mNeurogenesis blocked: Max neuron limit ({max_neurons_config}) reached.\x1b[0m")
            return None

        # --- name & position ---
        base_name  = {'novelty': 'novelty', 'stress': 'stress', 'reward': 'reward'}[neuron_type]
        new_index  = len([n for n in self.neuron_positions if n.startswith(base_name)])
        new_name   = f"{base_name}_{new_index}"

        active_neurons_pos = sorted(
            [(k, v, self.neuron_positions[k]) for k, v in self.state.items()
            if isinstance(v, (int, float)) and k in self.neuron_positions
            and k not in self.excluded_neurons],
            key=lambda x: x[1], reverse=True
        )
        base_x, base_y = active_neurons_pos[0][2] if active_neurons_pos else (600, 300)
        self.neuron_positions[new_name] = (
            base_x + random.randint(-50, 50),
            base_y + random.randint(-50, 50)
        )

        # --- state & appearance ---
        self.state[new_name] = 50
        cfg_appearance = self.config.neurogenesis.get('appearance', {})
        cfg_colors     = cfg_appearance.get('colors', {})
        cfg_shapes     = cfg_appearance.get('shapes', {})

        # Stress neurons are **always** pure red (override config)
        if neuron_type == 'stress':
            self.state_colors[new_name] = (255, 0, 0)
        else:
            default_colors = {
                'novelty': (255, 255, 150),
                'reward':  (173, 216, 230)
            }
            self.state_colors[new_name] = tuple(
                cfg_colors.get(neuron_type, default_colors.get(neuron_type, (200, 200, 200)))
            )

        default_shapes = {
            'novelty': 'diamond',
            'stress':  'square',
            'reward':  'triangle'
        }
        self.neuron_shapes[new_name] = cfg_shapes.get(
            neuron_type, default_shapes.get(neuron_type, 'circle')
        )
        self.communication_events[new_name] = time.time()

        # --- strong default connections (kept exactly as before) ---
        default_weights = {
            'novelty': {'curiosity': 0.6, 'anxiety': -0.4},
            'stress':  {'anxiety': -0.7, 'happiness': 0.3},
            'reward':  {'satisfaction': 0.8, 'happiness': 0.5}
        }
        for target, weight in default_weights[neuron_type].items():
            if target in self.neuron_positions:
                self.weights[(new_name, target)] = weight
                self.weights[(target, new_name)] = weight * 0.5
                self.communication_events[target] = time.time()

        # --- NEW: weak exploratory connections to every other neuron ---
        for target in list(self.neuron_positions.keys()):
            if target == new_name or target in self.excluded_neurons:
                continue
            # skip if already wired by defaults
            if (new_name, target) in self.weights or (target, new_name) in self.weights:
                continue
            seed_w = random.uniform(-0.08, 0.08)   # weak exploratory weight
            self.weights[(new_name, target)] = seed_w
            self.weights[(target, new_name)] = seed_w * 0.5

        # --- logging & repulsion ---
        trigger_reason_value = (
            trigger_value_for_log
            if trigger_value_for_log is not None
            else state.get(
                {'novelty': 'novelty_exposure', 'stress': 'sustained_stress', 'reward': 'recent_rewards'}[neuron_type], 0
            )
        )
        log_creation_details = {
            "trigger_type": neuron_type,
            "trigger_value": round(trigger_reason_value, 2),
            "context": ""
        }
        self.log_neurogenesis_event(new_name, "created", details=log_creation_details)
        self.apply_repulsion_force()

        # --- statistics hook ---
        if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic:
            self.tamagotchi_logic.track_neuron_creation(neuron_type)

        return new_name

    def apply_repulsion_force(self, iterations=15, strength=0.6, threshold=120.0):
        """Applies a repulsion force between nearby neurons to spread them out."""

        neuron_list = [name for name in self.neuron_positions.keys() if name not in self.excluded_neurons]

        for _ in range(iterations):
            displacements = {name: [0.0, 0.0] for name in neuron_list}

            for i in range(len(neuron_list)):
                for j in range(i + 1, len(neuron_list)):
                    neuron1 = neuron_list[i]
                    neuron2 = neuron_list[j]

                    pos1 = self.neuron_positions[neuron1]
                    pos2 = self.neuron_positions[neuron2]

                    dx = pos1[0] - pos2[0]
                    dy = pos1[1] - pos2[1]

                    distance_sq = dx*dx + dy*dy

                    if 0 < distance_sq < threshold*threshold:
                        distance = math.sqrt(distance_sq)
                        force = strength * (threshold - distance) / distance
                        move_x = (dx / distance) * force
                        move_y = (dy / distance) * force
                        displacements[neuron1][0] += move_x
                        displacements[neuron1][1] += move_y
                        displacements[neuron2][0] -= move_x
                        displacements[neuron2][1] -= move_y

            damping = 0.5
            moved = False
            for name in neuron_list:
                if name in self.original_neuron_positions:
                   continue

                pos = self.neuron_positions[name]
                disp = displacements[name]

                if abs(disp[0]) > 0.1 or abs(disp[1]) > 0.1:
                    new_x = pos[0] + disp[0] * damping
                    new_y = pos[1] + disp[1] * damping
                    new_x = max(50, min(974, new_x))
                    new_y = max(50, min(668, new_y))
                    self.neuron_positions[name] = (new_x, new_y)
                    moved = True

            if not moved:
                break
        if moved:
           self.update()

    def update_weights(self):
        """
        Update weights by adding small random noise. 
        WARNING: This adds noise and might counteract Hebbian learning.
        """
        if self.frozen_weights is not None:
            return

        # --- MODIFIED: Iterate over a copy of the actual weight keys ---
        for conn in list(self.weights.keys()):
            # Check if the connection still exists (it might be pruned concurrently)
            if conn in self.weights:
                # Add a very small amount of noise/drift
                self.weights[conn] += random.uniform(-0.01, 0.01) # Reduced noise
                # Clamp the weight to stay within [-1, 1]
                self.weights[conn] = max(-1, min(1, self.weights[conn]))

    def freeze_weights(self):
        self.frozen_weights = self.weights.copy()

    def unfreeze_weights(self):
        self.frozen_weights = None

    def strengthen_connection(self, neuron1, neuron2, amount):
        pair = (neuron1, neuron2)
        reverse_pair = (neuron2, neuron1)
        if pair not in self.weights and reverse_pair not in self.weights:
            self.weights[pair] = 0.0
        use_pair = pair if pair in self.weights else reverse_pair
        self.weights[use_pair] += amount
        self.weights[use_pair] = max(-1, min(1, self.weights[use_pair]))
        self.update()

    def create_neuron(self, neuron_type, trigger_data):
        """Add after all other methods"""
        base_name = {'novelty': 'novel', 'stress': 'defense', 'reward': 'reward'}[neuron_type]
        new_name = f"{base_name}_{len(self.neurogenesis_data['new_neurons'])}"
        active_neurons = sorted([(k,v) for k,v in self.state.items() if isinstance(v, (int, float))], key=lambda x: x[1], reverse=True)
        base_x, base_y = self.neuron_positions[active_neurons[0][0]] if active_neurons else (600, 300)
        self.neuron_positions[new_name] = (base_x + random.randint(-50, 50), base_y + random.randint(-50, 50))
        self.neurogenesis_highlight = {'neuron': new_name, 'start_time': time.time(), 'duration': 5.0}
        self.update()
        self.state[new_name] = 50
        self.state_colors[new_name] = {'novelty': (255, 255, 150), 'stress': (255, 150, 150), 'reward': (150, 255, 150)}[neuron_type]
        default_weights = {'novelty': {'curiosity': 0.6, 'anxiety': -0.4}, 'stress': {'anxiety': -0.7, 'happiness': 0.3}, 'reward': {'satisfaction': 0.8, 'happiness': 0.5}}
        for target, weight in default_weights[neuron_type].items():
            self.weights[(new_name, target)] = weight
            self.weights[(target, new_name)] = weight * 0.5
        self.neurogenesis_data['new_neurons'].append(new_name)
        self.neurogenesis_data['last_neuron_time'] = time.time()
        return new_name

    def capture_training_data(self, state):
        training_sample = [state[neuron] for neuron in self.neuron_positions.keys()]
        self.training_data.append(training_sample)
        print("Captured training data:", training_sample)

    def train_hebbian(self):
        print("Starting Hebbian training...")
        for sample in self.training_data:
            for i in range(len(sample)):
                for j in range(i+1, len(sample)):
                    self.associations[i][j] += self.learning_rate * sample[i] * sample[j]
                    self.associations[j][i] = self.associations[i][j]
        self.training_data = []

    def get_association_strength(self, neuron1, neuron2):
        idx1 = list(self.neuron_positions.keys()).index(neuron1)
        idx2 = list(self.neuron_positions.keys()).index(neuron2)
        return self.associations[idx1][idx2]

    def draw_connections(self, painter, scale):
        """Draw connections with extended 2-second weight-change animations.
        Links are forced INVISIBLE while core neurons are still being revealed."""
        if not self.show_links:
            return

        # absolutely no connections until every core neuron is completely revealed (tutorial mode guard). 
        if self.is_tutorial_mode and len(self.visible_neurons) < len(self.original_neurons):
            return

        current_time = time.time()
        connections_drawn = 0
        connections_skipped = 0

        for key, weight in self.weights.items():
            if not isinstance(key, tuple) or len(key) != 2:
                continue
            source, target = key

            # skip tutorial-only connections when not in tutorial
            tutorial_mode = getattr(self.parent(), 'tutorial_active', False)
            is_tutorial_conn = (source.startswith('tutorial_neuron_') or
                                target.startswith('tutorial_neuron_'))
            if is_tutorial_conn and not tutorial_mode:
                continue

            # skip if either neuron is still revealing (tutorial safety)
            if self.is_tutorial_mode and (
                    not self.is_neuron_revealed(source) or
                    not self.is_neuron_revealed(target)):
                connections_skipped += 1
                continue

            if (source not in self.neuron_positions or
                target not in self.neuron_positions or
                source in self.excluded_neurons or
                target in self.excluded_neurons):
                continue

            # skip connections involving non-visible core neurons (tutorial)
            if self.is_tutorial_mode:
                if source in self.original_neurons and source not in self.visible_neurons:
                    connections_skipped += 1
                    continue
                if target in self.original_neurons and target not in self.visible_neurons:
                    connections_skipped += 1
                    continue

            start = self.neuron_positions[source]
            end   = self.neuron_positions[target]
            start_point = QtCore.QPointF(float(start[0]), float(start[1]))
            end_point   = QtCore.QPointF(float(end[0]),   float(end[1]))

            # special styling:  Stress ↔ Anxiety  (dashed red)
            is_stress_to_anxiety = (
                (source.lower().startswith('stress') and target.lower() == 'anxiety') or
                (target.lower().startswith('stress') and source.lower() == 'anxiety'))
            if is_stress_to_anxiety:
                pen = QtGui.QPen(QtGui.QColor("red"))
                pen.setWidth(3)
                pen.setStyle(QtCore.Qt.DashLine)
                painter.setPen(pen)
                painter.drawLine(start_point, end_point)
                continue   # skip default drawing for this pair

            # default appearance
            anim_weight = weight
            base_width  = 1.0 * scale
            line_width  = base_width
            pen_style   = QtCore.Qt.SolidLine
            animating   = False
            pulse_progress = 0.0

            # check for active weight-change animations (2-second window)
            for anim in self.weight_animations:
                if anim['pair'] == key:
                    elapsed = current_time - anim['start_time']
                    if elapsed < anim['duration']:
                        progress = elapsed / anim['duration']
                        anim_weight = anim['start_weight'] + progress * (
                            anim['end_weight'] - anim['start_weight'])

                        # growing / shrinking line width
                        if progress < 0.5:
                            line_width = base_width + (6.0 * scale * progress * 2)
                        else:
                            line_width = base_width + (6.0 * scale * (1 - progress) * 2)

                        pulse_progress = progress * anim['pulse_speed']
                        animating = True
                        break

            # colour & alpha
            if animating:
                r, g, b = anim['color']
                alpha = int(255 * (1 - pulse_progress ** 2))
                color = QtGui.QColor(r, g, b, alpha)
            else:
                base_alpha = int(self._link_opacities.get(key, 0.0) * 255)
                color = (QtGui.QColor(0, int(255 * abs(weight)), 0, base_alpha) if weight > 0 else
                        QtGui.QColor(int(255 * abs(weight)), 0, 0, base_alpha))

            # line style
            if is_tutorial_conn and tutorial_mode:
                color = QtGui.QColor(255, 255, 0, 180)
                line_width = 3
                pen_style = QtCore.Qt.DashLine
            else:
                pen_style = (QtCore.Qt.DashLine if weight < 0 else
                            QtCore.Qt.SolidLine)
                if abs(anim_weight) < 0.1:
                    pen_style = QtCore.Qt.DotLine

            painter.setPen(QtGui.QPen(color, line_width, pen_style))
            painter.drawLine(start_point, end_point)

            # pulse circle travelling along the wire (2-second anim)
            if animating and pulse_progress < 1.0:
                pulse_pos = pulse_progress
                pulse_x = start_point.x() + pulse_pos * (end_point.x() - start_point.x())
                pulse_y = start_point.y() + pulse_pos * (end_point.y() - start_point.y())
                pulse_size = 6 * scale * (1 - pulse_progress ** 2)

                painter.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 0, 200)))
                painter.setPen(QtCore.Qt.NoPen)
                painter.drawEllipse(QtCore.QPointF(pulse_x, pulse_y),
                                    pulse_size, pulse_size)

            # glow around the line (first 70 % of 2-second window)
            if animating and progress < 0.7:
                glow_width = line_width + 4 * scale * (1 - (progress / 0.7))
                glow_color = QtGui.QColor(255, 255, 200, 50)
                painter.setPen(QtGui.QPen(glow_color, glow_width, pen_style))
                painter.drawLine(start_point, end_point)

            # weight text (optional)
            if self.show_weights and abs(weight) > 0.1:
                midpoint = QtCore.QPointF((start_point.x() + end_point.x()) / 2,
                                        (start_point.y() + end_point.y()) / 2)
                text_area_width  = 80.0 * scale
                text_area_height = 22.0 * scale
                font = painter.font()
                font.setPointSize(max(8, int(8 * scale)))
                painter.setFont(font)
                rect = QtCore.QRectF(midpoint.x() - text_area_width / 2,
                                    midpoint.y() - text_area_height / 2,
                                    text_area_width, text_area_height)
                painter.setBrush(QtGui.QBrush(QtGui.QColor(0, 0, 0)))
                painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0)))
                painter.drawRect(rect)
                painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255)))
                painter.drawText(rect, QtCore.Qt.AlignCenter, f"{weight:.2f}")

            connections_drawn += 1

        # debug guard: warn only when something looks wrong
        if connections_drawn == 0 and len(self.weights) > 0:
            print(f"🔴 NO CONNECTIONS DRAWN! tutorial_mode={self.is_tutorial_mode}, "
                f"visible_neurons={len(self.visible_neurons)}, original_neurons={len(self.original_neurons)}, "
                f"total_weights={len(self.weights)}, skipped={connections_skipped}")

    def _get_logical_coords(self, widget_pos):
        """Maps widget QPoint/QPointF to logical neuron coordinates."""
        indicator_space = 60
        base_width_logical = 1024
        base_height_logical = 768 - indicator_space
        scale_x = self.width() / base_width_logical
        scale_y = (self.height() - indicator_space) / base_height_logical
        scale = min(scale_x, max(0.1, scale_y))
        translate_y = indicator_space
        lx = widget_pos.x() / scale
        ly = (widget_pos.y() - translate_y) / scale
        return QtCore.QPointF(lx, ly)

    def get_neuron_at_pos(self, widget_pos):
        """Finds a neuron at the given QPoint widget coordinates."""
        logical_pos = self._get_logical_coords(widget_pos)
        neuron_radius = 50  # Increased to 50 for better click detection on all neurons
        for name, pos in self.neuron_positions.items():
            dist_sq = (logical_pos.x() - pos[0])**2 + (logical_pos.y() - pos[1])**2
            if dist_sq <= neuron_radius**2:
                return name
        return None


    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        # Fill background
        painter.fillRect(self.rect(), QtGui.QColor(240, 240, 240))

        # HIDDEN: State indicator pills (functionality retained, display disabled)
        indicator_y_position = 10
        indicator_font = QtGui.QFont("Arial", 10, QtGui.QFont.Bold)
        painter.setFont(indicator_font)
        font_metrics = painter.fontMetrics()
        
        active_indicators_data = []
        # Collect state data for statistics window
        if self.state.get('is_fleeing', False): 
            active_indicators_data.append({"text": "Fleeing!", "color": QtGui.QColor(220, 20, 60)})
        if self.state.get('is_startled', False): 
            active_indicators_data.append({"text": "Startled!", "color": QtGui.QColor(255, 165, 0)})
        if self.state.get('pursuing_food', False): 
            active_indicators_data.append({"text": "Pursuing Food", "color": QtGui.QColor(60, 179, 113)})

        squid_status = self.state.get('status', '').lower()
        if self.state.get('is_eating', False) or 'eating' in squid_status:
            active_indicators_data.append({"text": "Eating", "color": QtGui.QColor(46, 204, 113)})
        if self.state.get('is_sleeping', False):
            active_indicators_data.append({"text": "Sleeping", "color": QtGui.QColor(142, 68, 173)})
        if 'rock' in squid_status or 'play' in squid_status:
            active_indicators_data.append({"text": "Playing", "color": QtGui.QColor(241, 196, 15)})
        if 'hiding' in squid_status:
            active_indicators_data.append({"text": "Hiding", "color": QtGui.QColor(22, 160, 133)})
        if self.state.get('anxiety', 0) > 70 or 'anxious' in squid_status:
            active_indicators_data.append({"text": "Anxious", "color": QtGui.QColor(231, 76, 60)})
        if self.state.get('curiosity', 0) > 80 or 'curious' in squid_status:
            active_indicators_data.append({"text": "Curious", "color": QtGui.QColor(52, 152, 219)})
        
        indicators_to_display = active_indicators_data[:3]
        
            
        painter.save()
        
        # Calculate space - no indicators displayed, so no space needed
        fixed_indicator_area_height = 0
        indicator_space_at_top = indicator_y_position + fixed_indicator_area_height
        
        base_width_logical = 1024
        base_height_logical = 768 - indicator_space_at_top
        if base_height_logical <= 0: 
            base_height_logical = 1
            
        scale_x = self.width() / base_width_logical
        
        drawable_height_for_neurons = self.height() - indicator_space_at_top
        if drawable_height_for_neurons <= 0: 
            drawable_height_for_neurons = 1
            
        scale_y = drawable_height_for_neurons / base_height_logical
        scale_y = max(0.01, scale_y)
        
        scale = max(0.01, min(scale_x, scale_y))

        painter.translate(0, indicator_space_at_top)
        painter.scale(scale, scale)
        
        self.draw_neurons(painter, 1.0)
        
        if self.dragging and self.dragged_neuron:
            pos = self.neuron_positions[self.dragged_neuron]
            painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 0), 3 / scale))
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawEllipse(QtCore.QPointF(pos[0], pos[1]), 30, 30) 
            
        self.draw_neurogenesis_highlights(painter, 1.0)
        
        if self.show_links:
            self.draw_connections(painter, 1.0)
            
        # FIX: Draw strength multipliers on top of neurons
        self.draw_strength_multiplier(painter, 1.0)
            
        painter.restore()
        
        # Draw tutorial glow as pulsing background (after restore, so it's in widget coordinates)
        if self.tutorial_glow_active:
            painter.save()
            
            # Light blue pulsing background
            glow_color = QtGui.QColor(48, 197, 255)  # Highighter blue
            
            # Calculate alpha based on pulsing opacity
            alpha = int(100 * self._tutorial_glow_opacity)  # Max 100 alpha for subtle effect
            glow_color.setAlpha(alpha)
            
            # Fill entire widget with pulsing light blue
            painter.setBrush(glow_color)
            painter.setPen(QtCore.Qt.NoPen)
            painter.drawRect(0, 0, self.width(), self.height())
            
            painter.restore()

    def draw_neurons(self, painter, scale):
        """Draw all neurons with activity-based sizing and highlights"""
        current_time = time.time()

        # Check for tutorial mode
        tutorial_mode = getattr(self.parent(), 'tutorial_active', False)
        
        for name, pos in self.neuron_positions.items():
            if name in self.excluded_neurons:
                continue

            # Skip tutorial neurons if not in tutorial mode
            if name.startswith('tutorial_neuron_') and not tutorial_mode:
                continue

            # Skip core neurons that haven't been revealed yet
            if name in self.original_neurons and name not in self.visible_neurons:
                continue

            try:
                # Calculate dynamic size based on activity
                value = self.get_neuron_value(self.state.get(name, 50))
                base_size = 25.0
                size_factor = 0.8 + 0.4 * (abs(value - 50) / 50)
                target_size = base_size * size_factor * scale

                # Smooth size transition
                if name not in self.neuron_sizes:
                    self.neuron_sizes[name] = target_size
                else:
                    current_size = self.neuron_sizes[name]
                    size_diff = target_size - current_size
                    self.neuron_sizes[name] = current_size + size_diff * 0.2

                radius = self.neuron_sizes[name]

                # Apply reveal animation if in progress
                reveal_scale = 1.0
                reveal_alpha = 255
                if name in self.neuron_reveal_animations:
                    elapsed = current_time - self.neuron_reveal_animations[name]['start_time']
                    duration = 0.4  # 0.4 seconds for reveal animation
                    if elapsed >= duration:
                        progress = 1.0
                    else:
                        # Ease-out animation curve
                        progress = elapsed / duration
                        progress = 1 - (1 - progress) ** 3
                    reveal_scale = progress
                    reveal_alpha = max(0, min(255, int(255 * progress)))  # ← safe alpha

                # Apply reveal scaling to radius
                animated_radius = radius * reveal_scale

                shape = self.neuron_shapes.get(name, 'circle')
                base_color = self.state_colors.get(name, (200, 200, 200))
                color = QtGui.QColor(*base_color)
                color.setAlpha(reveal_alpha)

                # Special handling for tutorial neurons
                if name.startswith('tutorial_neuron_') and tutorial_mode:
                    color = QtGui.QColor(255, 255, 0, 200)  # Bright yellow
                    # Make them pulse
                    pulse = 0.7 + 0.3 * math.sin(current_time * 8)
                    animated_radius = animated_radius * pulse

                # Draw activity highlight
                if name in self.communication_events:
                    elapsed = current_time - self.communication_events[name]
                    if elapsed < self.activity_duration:
                        pulse = 0.5 + 0.5 * math.sin(current_time * 10)
                        highlight_radius = animated_radius + 3 + 2 * pulse
                        highlight_color = QtGui.QColor(255, 255, 0, min(150, reveal_alpha))
                        painter.setPen(QtGui.QPen(highlight_color, 2))
                        painter.setBrush(QtCore.Qt.NoBrush)
                        painter.drawEllipse(QtCore.QPointF(pos[0], pos[1]),
                                        highlight_radius, highlight_radius)

                # Draw the neuron shape with reveal animation
                if shape == 'diamond':
                    self.draw_diamond_neuron(painter, pos[0], pos[1], animated_radius, name, scale, reveal_alpha)
                elif shape == 'triangle':
                    self.draw_triangular_neuron(painter, pos[0], pos[1], animated_radius, name, scale, reveal_alpha)
                elif shape == 'square':
                    self.draw_square_neuron(painter, pos[0], pos[1], animated_radius, name, scale, reveal_alpha)
                else:
                    painter.setBrush(QtGui.QBrush(color))
                    pen_color = QtGui.QColor(0, 0, 0)
                    pen_color.setAlpha(reveal_alpha)
                    painter.setPen(QtGui.QPen(pen_color))
                    painter.drawEllipse(QtCore.QPointF(pos[0], pos[1]), animated_radius, animated_radius)
                    self._draw_neuron_label(painter, pos[0], pos[1], name, animated_radius, scale, reveal_alpha)

                # Draw neurogenesis highlight
                if (self.neurogenesis_highlight['neuron'] == name and
                    current_time - self.neurogenesis_highlight['start_time'] <
                    self.neurogenesis_highlight['duration']):

                    progress = (current_time - self.neurogenesis_highlight['start_time']) / \
                            self.neurogenesis_highlight['duration']
                    pulse = 0.5 + 0.5 * math.sin(self.neurogenesis_highlight['pulse_phase'])
                    highlight_radius = animated_radius + 10 + 10 * pulse * (1 - progress)

                    highlight_color = QtGui.QColor(255, 215, 0, min(200, reveal_alpha))
                    painter.setPen(QtGui.QPen(highlight_color, 3))
                    painter.setBrush(QtCore.Qt.NoBrush)
                    painter.drawEllipse(QtCore.QPointF(pos[0], pos[1]),
                                    highlight_radius, highlight_radius)

            except Exception as e:
                print(f"Error drawing neuron {name}: {str(e)}")

    def draw_binary_neuron(self, painter, x, y, value, label, scale=1.0):
        color = (0, 0, 0) if value else (255, 255, 255)
        painter.setBrush(QtGui.QBrush(QtGui.QColor(*color))); painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0)))
        x_scaled, y_scaled, size = int(x * scale), int(y * scale), int(30 * scale)
        painter.drawRect(x_scaled - size//2, y_scaled - size//2, size, size)
        font = painter.font(); font.setPointSize(int(8 * scale)); painter.setFont(font)
        label_width, label_height = int(150 * scale), int(20 * scale)
        painter.drawText(x_scaled - label_width//2, y_scaled + int(30 * scale), label_width, label_height, QtCore.Qt.AlignCenter, label)

    def draw_circular_neuron(self, painter, x, y, value, label, scale=1.0):
        color = QtGui.QColor(150, 255, 150); radius = 20 * scale
        painter.setBrush(QtGui.QBrush(color)); painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0)))
        painter.drawEllipse(int(x - radius), int(y - radius), int(radius*2), int(radius*2))
        self._draw_neuron_label(painter, x, y, label, scale)

    def draw_triangular_neuron(self, painter, x, y, radius, label, scale=1.0, alpha=255):
        """Draw a triangular neuron with given radius"""
        color = QtGui.QColor(*self.state_colors.get(label, (255, 255, 150)))
        self._draw_polygon_neuron(painter, x, y, 3, radius, color, label, scale, alpha=alpha)

    def show_diagnostic_report(self):
        if hasattr(self, 'brain_widget'): self.brain_widget.show_diagnostic_report()
        else: print("Error: Brain widget not initialized")

    def _draw_polygon_neuron(self, painter, x, y, sides, radius, color, label, scale,
                            rotation=0, alpha=255):
        painter.save()
        painter.translate(x, y)
        painter.rotate(rotation)

        alpha = max(0, min(255, alpha))            # ← clamp
        colored = QtGui.QColor(color)
        colored.setAlpha(alpha)

        pen_color = QtGui.QColor(0, 0, 0)
        pen_color.setAlpha(alpha)

        painter.setBrush(QtGui.QBrush(colored))
        painter.setPen(QtGui.QPen(pen_color))

        polygon = QtGui.QPolygonF()
        angle_step = 360.0 / sides
        for i in range(sides):
            angle = math.radians(i * angle_step - 90)
            polygon.append(QtCore.QPointF(radius * math.cos(angle),
                                        radius * math.sin(angle)))
        painter.drawPolygon(polygon)
        painter.restore()
        self._draw_neuron_label(painter, x, y, label, radius, scale, alpha)

    def _draw_neuron_label(self, painter, x, y, label, radius, scale, alpha=255):
        """Draw neuron label below the neuron"""
        alpha = max(0, min(255, alpha))              # ← clamp alpha
        label_color = QtGui.QColor(0, 0, 0)
        label_color.setAlpha(alpha)
        painter.setPen(label_color)
        font = painter.font()
        font.setPointSize(int(8 * scale))
        painter.setFont(font)
        label_y = y + radius + 15 * scale

        # Calculate the width needed for the text
        font_metrics = painter.fontMetrics()
        text_width = font_metrics.horizontalAdvance(label)
        padding = 10 * scale
        rect_width = text_width + 2 * padding

        # Center the text rectangle horizontally around the neuron center (x)
        painter.drawText(
            int(x - rect_width / 2),
            int(label_y),
            int(rect_width),
            int(20 * scale),
            QtCore.Qt.AlignCenter,
            label
        )

    def draw_neurogenesis_highlights(self, painter, scale):
        if (self.neurogenesis_highlight['neuron'] and time.time() - self.neurogenesis_highlight['start_time'] < self.neurogenesis_highlight['duration']):
            pos = self.neuron_positions.get(self.neurogenesis_highlight['neuron'])
            if pos:
                painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 0), int(3 * scale))); painter.setBrush(QtCore.Qt.NoBrush); radius = int(40 * scale)
                x, y, width, height = int(pos[0] - radius), int(pos[1] - radius), int(radius * 2), int(radius * 2)
                painter.drawEllipse(x, y, width, height)

    def draw_square_neuron(self, painter, x, y, radius, label, scale=1.0, alpha=255):
        """Draw a square neuron with given radius"""
        color = QtGui.QColor(*self.state_colors.get(label, (152, 251, 152)))
        self._draw_polygon_neuron(painter, x, y, 4, radius, color, label, scale, rotation=45, alpha=alpha)

    def draw_diamond_neuron(self, painter, x, y, radius, label, scale=1.0, alpha=255):
        """Draw a diamond-shaped neuron with given radius"""
        color = QtGui.QColor(*self.state_colors.get(label, (152, 251, 152)))
        self._draw_polygon_neuron(painter, x, y, 4, radius, color, label, scale, rotation=0, alpha=alpha)

    def toggle_links(self, state):
        """
        Public slot connected to the checkbox.
        Instead of flipping a boolean immediately we only *request* the
        new target opacity; the timer will do the actual fade with
        per-link random delays and speeds for maximum chaos.
        """
        want_visible = (state == QtCore.Qt.Checked)
        now = time.time()
        
        for key in self.weights.keys():
            self._link_targets[key] = 1.0 if want_visible else 0.0
            
            # Random delay per link (0-800ms)
            self._link_start_times[key] = now + random.uniform(0.0, 0.8)
            
            # Random speed per link for individual character
            self._link_fade_speeds[key] = random.uniform(2.0, 4.5)
            
            # Initialize opacity if not already set
            if key not in self._link_opacities:
                self._link_opacities[key] = 0.0 if want_visible else 1.0

        # Kick the timer (safe to call multiple times)
        if not self._link_fade_timer.isActive():
            self._link_fade_timer.start()

    def toggle_weights(self, state):
        self.show_weights = state == QtCore.Qt.Checked
        self.update()

    def toggle_capture_training_data(self, state):
        self.capture_training_data_enabled = state

    def mousePressEvent(self, event):

        
        if event.button() != QtCore.Qt.LeftButton:
            #print(f"   Not left button: {event.button()}")
            super().mousePressEvent(event)
            return

        logical_pos = self._get_logical_coords(event.pos())
        #print(f"   Logical coords: {logical_pos}")
        
        neuron = self.get_neuron_at_pos(event.pos())
        #print(f"   Neuron detected: {neuron}")
        
        if not neuron:
            #print(f"   No neuron found at position")
            # Debug: show all neuron positions and distances
            #print(f"   Available neurons: {list(self.neuron_positions.keys())}")
            #print(f"   Distances from click point:")
            import math
            neuron_radius = 50  # Must match the radius in get_neuron_at_pos
            for name, pos in self.neuron_positions.items():
                dist = math.sqrt((logical_pos.x() - pos[0])**2 + (logical_pos.y() - pos[1])**2)
                #print(f"      {name}: pos={pos}, distance={dist:.1f}px (threshold: {neuron_radius}px)")
            self.dragged_neuron = None
            self.dragging = False
            super().mousePressEvent(event)
            return

        # --- neurogenesis-only drag rule ---
        is_neuro = self.is_neurogenesis_neuron(neuron)
        #print(f"   Is neurogenesis neuron? {is_neuro}")
        
        if is_neuro:
            # Neurogenesis neuron: allow dragging
            self.dragged_neuron = neuron
            self.dragging = True
            self.drag_start_pos = event.pos()
            #print(f"🎯 Started dragging neurogenesis neuron: {neuron}")
            
            # Debug: Check if neuron is in functional_neurons
            if hasattr(self, 'enhanced_neurogenesis'):
                print(f"")
                if neuron in self.enhanced_neurogenesis.functional_neurons:
                    print(f"")
                else:
                    print(f"")
            
            self.update()
        else:
            # Core neuron: register click but PREVENT drag
            self.dragged_neuron = neuron
            self.dragging = False
            self.drag_start_pos = event.pos()  # Store for click detection
            print(f"")
            print(f"")
            if neuron in self.neuron_shapes:
                print(f"")
            self.update()

        super().mousePressEvent(event)

    def handle_neuron_clicked(self, neuron_name):
        print(f"")

    def show_diagnostic_report(self):
        dialog = DiagnosticReportDialog(self, self.parent())
        dialog.exec_()

    def mouseMoveEvent(self, event):
        """Handle mouse movement for tooltips and dragging"""

        if hasattr(self, 'tooltip_manager'):
            self.tooltip_manager.show_tooltip_for_position(event)

        # Only allow dragging neurogenesis neurons
        if self.dragging and self.dragged_neuron:
            if self.is_neurogenesis_neuron(self.dragged_neuron):
                logical_pos = self._get_logical_coords(event.pos())
                self.neuron_positions[self.dragged_neuron] = (logical_pos.x(), logical_pos.y())
                self.update()
            else:
                # This shouldn't happen but let's log it if it does
                print(f"")

        super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self, event):
        """
        Handle double-click on a neuron to open the Neuron Laboratory instead of the Inspector.
        """
        if event.button() == QtCore.Qt.LeftButton:
            neuron_name = self.get_neuron_at_pos(event.pos())
            
            if neuron_name:
                print(f"")
                
                # Close the old Inspector if it's currently open (compatibility cleanup)
                if hasattr(self, '_inspector') and self._inspector and self._inspector.isVisible():
                    self._inspector.close()
                    self._inspector = None # Clear the old reference

                # Open or show the Neuron Laboratory
                if self._laboratory is None:
                    self._laboratory = NeuronLaboratory(self, parent=self.window() or self.parent()) 
                
                self._laboratory.show()
                self._laboratory.raise_() # Bring the window to the front

                # CALL A NEW METHOD: Pass the neuron name for selection
                if hasattr(self._laboratory, 'select_neuron_by_name'):
                    self._laboratory.select_neuron_by_name(neuron_name)
                
                self.update() # Redraw the brain visualization
                event.accept()
                return
        
        super().mouseDoubleClickEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            is_click = False
            if self.dragged_neuron and self.drag_start_pos:
                distance = (event.pos() - self.drag_start_pos).manhattanLength()
                if distance < QtWidgets.QApplication.startDragDistance():
                    is_click = True
            if is_click:
                self.neuronClicked.emit(self.dragged_neuron)
            self.dragging = False
            self.dragged_neuron = None
            self.drag_start_pos = None
            self.update()
            # Only apply repulsion to neurogenesis neurons
            #if hasattr(self, 'enhanced_neurogenesis'):
            #    self.apply_repulsion_force()
        super().mouseReleaseEvent(event)

    def draw_strength_multiplier(self, painter, scale):
        """
        Draw strength multipliers on neurons that have been strengthened.
        Displays as "2.5x" above strengthened neurons with a badge.
        """
        if not hasattr(self, 'enhanced_neurogenesis'):
            return
        
        current_time = time.time()
        
        for name, neuron in self.enhanced_neurogenesis.functional_neurons.items():
            # Only show multiplier if > 1.0 (i.e., strengthened at least once)
            # FIX: Check if neuron has strength_multiplier attribute before accessing it
            if not hasattr(neuron, 'strength_multiplier'):
                continue
                
            if neuron.strength_multiplier <= 1.0 or name not in self.neuron_positions:
                continue
            
            pos = self.neuron_positions[name]
            x, y = pos
            
            # Position ABOVE the neuron
            label_y = y - 45 * scale
            
            # Format multiplier text
            multiplier_text = f"{neuron.strength_multiplier:.1f}x"
            
            # Create font
            font = QtGui.QFont()
            font.setPointSize(int(9 * scale))
            font.setBold(True)
            painter.setFont(font)
            
            # Draw background circle/badge for visibility
            font_metrics = painter.fontMetrics()
            text_width = font_metrics.horizontalAdvance(multiplier_text)
            badge_radius = max(12 * scale, (text_width / 2) + 5 * scale)
            
            painter.setBrush(QtGui.QBrush(QtGui.QColor(255, 215, 0, 220)))  # Gold background
            painter.setPen(QtGui.QPen(QtGui.QColor(139, 105, 20), 2))  # Dark gold border
            painter.drawEllipse(QtCore.QPointF(x, label_y), badge_radius, badge_radius)
            
            # Draw text on top in black
            painter.setPen(QtGui.QColor(0, 0, 0))
            painter.drawText(
                int(x - text_width / 2),
                int(label_y - font_metrics.height() / 2),
                int(text_width),
                int(font_metrics.height()),
                QtCore.Qt.AlignCenter,
                multiplier_text
            )
            
            # Add a small star icon to indicate strengthening
            star_radius = 8 * scale
            star_x = x + 20 * scale
            star_y = y - 20 * scale
            
            painter.setBrush(QtGui.QBrush(QtGui.QColor(255, 215, 0, 200)))
            painter.setPen(QtGui.QPen(QtGui.QColor(255, 165, 0), 2))
            painter.drawEllipse(QtCore.QPointF(star_x, star_y), star_radius, star_radius)


    def _is_click_on_neuron(self, point, neuron_pos, scale):
        neuron_x, neuron_y = neuron_pos
        scaled_x = neuron_x * scale; scaled_y = neuron_y * scale
        return (abs(scaled_x - point.x()) <= 25 * scale and abs(scaled_y - point.y()) <= 25 * scale)

    def is_point_inside_neuron(self, point, neuron_pos, scale):
        neuron_x, neuron_y = neuron_pos
        scaled_x = neuron_x * scale; scaled_y = neuron_y * scale
        return ((scaled_x - 25 * scale) <= point.x() <= (scaled_x + 25 * scale) and (scaled_y - 25 * scale) <= point.y() <= (scaled_y + 25 * scale))

    def reset_positions(self):
        self.neuron_positions = self.original_neuron_positions.copy()
        self.update()
        
    def start_tutorial_glow(self, duration_ms=5000):
        """Start a glowing, pulsing border effect for tutorial purposes"""
        self.tutorial_glow_active = True
        self._tutorial_glow_opacity = 0.0
        
        # Create animation for pulsing effect
        self.tutorial_glow_animation = QtCore.QPropertyAnimation(self, b"tutorial_glow_opacity")
        self.tutorial_glow_animation.setDuration(500)  # 0.5 second pulse
        self.tutorial_glow_animation.setStartValue(0.0)
        self.tutorial_glow_animation.setEndValue(1.0)
        self.tutorial_glow_animation.setLoopCount(-1)  # Infinite loop
        self.tutorial_glow_animation.setEasingCurve(QtCore.QEasingCurve.InOutSine)
        
        # Start the animation
        self.tutorial_glow_animation.start()
        
        # Set timer to stop after duration
        self.tutorial_glow_timer = QtCore.QTimer()
        self.tutorial_glow_timer.setSingleShot(True)
        self.tutorial_glow_timer.timeout.connect(self.stop_tutorial_glow)
        self.tutorial_glow_timer.start(duration_ms)
    
    def stop_tutorial_glow(self):
        """Stop the tutorial glow effect"""
        self.tutorial_glow_active = False
        if self.tutorial_glow_animation:
            self.tutorial_glow_animation.stop()
            self.tutorial_glow_animation = None
        if self.tutorial_glow_timer:
            self.tutorial_glow_timer.stop()
            self.tutorial_glow_timer = None
        self.update()
    
    def get_tutorial_glow_opacity(self):
        """Get current glow opacity (for Qt property animation)"""
        return self._tutorial_glow_opacity
    
    def set_tutorial_glow_opacity(self, value):
        """Set glow opacity and trigger repaint (for Qt property animation)"""
        self._tutorial_glow_opacity = value
        self.update()
    
    # Qt property for animation
    tutorial_glow_opacity = QtCore.pyqtProperty(float, get_tutorial_glow_opacity, set_tutorial_glow_opacity)