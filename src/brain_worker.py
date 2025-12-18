import sys
import time
import random
import traceback
import math
from queue import Queue, Empty
from heapq import nlargest

from PyQt5.QtCore import QThread, pyqtSignal, QMutex, QMutexLocker, QWaitCondition


# PURE_INPUTS: These neurons receive external input and should NOT be modified by learning
# They are read-only sensors that reflect game state
PURE_INPUTS = {
    "can_see_food", "is_eating", "is_sleeping", "is_sick", 
    "pursuing_food", "is_fleeing", "is_startled", "external_stimulus", 
    "plant_proximity"
}


class BrainWorker(QThread):
    """
    Background worker for handling expensive brain logic operations:
    - Neurogenesis checks
    - Hebbian learning calculations
    - State decay and update processing
    
    Custom neurons (user-created neurons) ARE included in Hebbian learning
    and can form new connections through this system.
    """
    
    # Signals for results (emitted to main thread)
    neurogenesis_result = pyqtSignal(dict)
    hebbian_result = pyqtSignal(dict)
    state_update_result = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, brain_widget=None):
        super().__init__()
        self.brain_widget = brain_widget
        self._running = True
        self._paused = False
        
        # Thread-safe queues for tasks
        self.task_queue = Queue()
        
        # Cache for thread-safe access to brain state
        self._cache_mutex = QMutex()
        self.cache = {
            'state': {},
            'weights': {},
            'positions': {},
            'config': None,
            'excluded_neurons': set(),
            'connector_neurons': set(),
            'custom_neurons': set(),  # NEW: Track custom neurons
            'learning_rate': 0.1,
            'new_neurons': set()
        }

        # History tracking to prevent Hebbian loops
        self._last_hebbian_pairs = []
        
        self.wait_condition = QWaitCondition()
        self.queue_mutex = QMutex()

    def update_cache(self, state, weights, positions, config, excluded_neurons=None, 
                     connector_neurons=None, learning_rate=0.1, new_neurons=None,
                     custom_neurons=None):
        """
        Update the local cache of brain state.
        Called from main thread before triggering heavy tasks.
        
        Args:
            state: Current neuron activation values
            weights: Current connection weights
            positions: Neuron positions
            config: Learning configuration
            excluded_neurons: Neurons to exclude from learning (system neurons)
            connector_neurons: Connector neurons from neurogenesis
            learning_rate: Base learning rate for Hebbian updates
            new_neurons: Recently created neurons (get learning boost)
            custom_neurons: User-created custom neurons (participate in learning)
        """
        with QMutexLocker(self._cache_mutex):
            # Deep copy or safe copy important structures
            self.cache['state'] = state.copy()
            self.cache['weights'] = weights.copy()
            self.cache['positions'] = positions.copy()
            self.cache['config'] = config
            self.cache['excluded_neurons'] = excluded_neurons if excluded_neurons else set()
            self.cache['connector_neurons'] = connector_neurons if connector_neurons else set()
            self.cache['custom_neurons'] = custom_neurons if custom_neurons else set()
            self.cache['learning_rate'] = learning_rate
            self.cache['new_neurons'] = new_neurons if new_neurons else set()

    def queue_neurogenesis_check(self, state_context):
        self._add_task('neurogenesis', {'state': state_context})

    def queue_hebbian_learning(self):
        self._add_task('hebbian', {})

    def queue_state_update(self, update_data):
        self._add_task('state_update', update_data)

    def _add_task(self, task_type, data):
        with QMutexLocker(self.queue_mutex):
            self.task_queue.put((task_type, data))
            self.wait_condition.wakeOne()

    def stop(self):
        self._running = False
        with QMutexLocker(self.queue_mutex):
            self.wait_condition.wakeAll()

    def pause(self):
        """Pause the worker thread."""
        with QMutexLocker(self.queue_mutex):
            self._paused = True
    
    def resume(self):
        """Resume the worker thread."""
        with QMutexLocker(self.queue_mutex):
            self._paused = False
            self.wait_condition.wakeAll()

    def run(self):
        print("🧵 BrainWorker thread started")
        
        while self._running:
            task = None
            
            # Wait for task
            with QMutexLocker(self.queue_mutex):
                # Check pause state first
                while self._paused and self._running:
                    self.wait_condition.wait(self.queue_mutex)

                if not self._running:
                    break

                if self.task_queue.empty():
                    self.wait_condition.wait(self.queue_mutex, 200)
                    if self._paused: 
                        continue
                    if self.task_queue.empty():
                        continue
                
                try:
                    task = self.task_queue.get_nowait()
                except Empty:
                    continue

            if not task:
                continue

            task_type, data = task
            
            try:
                if task_type == 'neurogenesis':
                    self._perform_neurogenesis_check(data)
                elif task_type == 'hebbian':
                    self._perform_hebbian_learning()
                elif task_type == 'state_update':
                    self._process_state_update(data)
            except Exception as e:
                error_msg = f"Error in {task_type}: {str(e)}\n{traceback.format_exc()}"
                print(error_msg)
                self.error_occurred.emit(error_msg)
                
        print("🧵 BrainWorker thread stopped")

    def _perform_neurogenesis_check(self, data):
        """Check if neurogenesis conditions are met based on cached config."""
        state = data.get('state', {})
        
        with QMutexLocker(self._cache_mutex):
            config = self.cache['config']
        
        if not config:
            return

        neuro_config = getattr(config, 'neurogenesis', {})
        
        triggers = {
            'novelty': state.get('novelty_exposure', 0) > neuro_config.get('novelty_threshold', 3.0),
            'stress': state.get('sustained_stress', 0) > neuro_config.get('stress_threshold', 1.2) or state.get('anxiety', 0) > 75,
            'reward': state.get('recent_rewards', 0) > neuro_config.get('reward_threshold', 3.5)
        }
        
        # Priority logic
        trigger_type = None
        trigger_val = 0
        
        if triggers['stress']:
            trigger_type = 'stress'
            trigger_val = state.get('sustained_stress', 0)
        elif triggers['novelty']:
            trigger_type = 'novelty'
            trigger_val = state.get('novelty_exposure', 0)
        elif triggers['reward']:
            trigger_type = 'reward'
            trigger_val = state.get('recent_rewards', 0)
            
        if trigger_type:
            self.neurogenesis_result.emit({
                'should_create': True,
                'neuron_type': trigger_type,
                'trigger_value': trigger_val,
                'state_context': state,
                'is_emergency': (trigger_type == 'stress' and state.get('anxiety', 0) > 90)
            })
        else:
            self.neurogenesis_result.emit({'should_create': False})

    def _perform_hebbian_learning(self):
        """Hebbian learning with bug fix for weight lookup and custom neuron boost."""
        with QMutexLocker(self._cache_mutex):
            state = self.cache['state']
            weights = self.cache['weights']
            neuron_list = list(self.cache['positions'].keys())
            excluded = self.cache['excluded_neurons']
            connector_neurons = self.cache['connector_neurons']
            custom_neurons = self.cache['custom_neurons']
            config = self.cache['config']
            base_learning_rate = self.cache['learning_rate']
            new_neurons = self.cache['new_neurons']

        if not config or not neuron_list:
            return

        learning_candidates = [
            n for n in neuron_list 
            if n not in excluded and n not in connector_neurons and n not in PURE_INPUTS
        ]
        
        if len(learning_candidates) < 2:
            self.hebbian_result.emit({'updated_pairs': []})
            return

        scored_pairs = []
        for i, n1 in enumerate(learning_candidates):
            for n2 in learning_candidates[i + 1:]:
                v1 = self._get_neuron_value(state.get(n1, 50))
                v2 = self._get_neuron_value(state.get(n2, 50))
                score = v1 + v2 + random.uniform(0, 40)

                pair_key = tuple(sorted((n1, n2)))
                if pair_key in self._last_hebbian_pairs:
                    score -= 500
                
                if n1 in custom_neurons or n2 in custom_neurons:
                    score += 15

                scored_pairs.append((score, n1, n2, v1, v2))

        top_k = config.neurogenesis.get('max_hebbian_pairs', 2) if hasattr(config, 'neurogenesis') else 2
        top_pairs = nlargest(top_k, scored_pairs)
        self._last_hebbian_pairs = [tuple(sorted((n1, n2))) for _, n1, n2, _, _ in top_pairs]
        
        weight_updates = {}
        updated_pairs_list = []
        hebbian_config = getattr(config, 'hebbian', {})
        decay_rate = hebbian_config.get('weight_decay', 0.01)
        
        for _, n1, n2, v1, v2 in top_pairs:
            pair = (n1, n2)
            reverse_pair = (n2, n1)
            
            # --- ROBUST WEIGHT LOOKUP (Fixes KeyError: ('neuron', None)) ---
            use_pair = None
            if pair in weights:
                use_pair = pair
            elif reverse_pair in weights:
                use_pair = reverse_pair
            
            is_new = False
            if use_pair is None:
                # If connection doesn't exist, we will create a new one using (n1, n2)
                use_pair = pair
                old_w = 0.0
                is_new = True
            else:
                old_w = weights[use_pair]
            
            # Calculate learning rate with boosts
            lr = base_learning_rate
            if n1 in new_neurons or n2 in new_neurons:
                lr *= 2.0
            if n1 in custom_neurons or n2 in custom_neurons:
                lr *= 1.5 # 1.5x boost for custom purple circles
                
            delta = lr * (v1 / 100.0) * (v2 / 100.0)
            new_w = max(-1.0, min(1.0, old_w + delta - (old_w * decay_rate)))
            
            weight_updates[use_pair] = {
                'old_weight': old_w,
                'new_weight': new_w,
                'is_new_connection': is_new
            }
            updated_pairs_list.append(use_pair)

        self.hebbian_result.emit({
            'updated_pairs': updated_pairs_list,
            'weight_updates': weight_updates
        })

    def _process_state_update(self, data):
        """Process state decay and noise logic."""
        if data.get('health_check'):
            self.state_update_result.emit({'health_check': True})
            return

        with QMutexLocker(self._cache_mutex):
            current_state = self.cache['state']
            weights = self.cache['weights']
            excluded = self.cache['excluded_neurons']
            custom_neurons = self.cache['custom_neurons']

        updated_state = {}

        # 1. Decay and Noise
        for neuron, val in current_state.items():
            if neuron in excluded or neuron in PURE_INPUTS:
                continue
            
            # Simple decay towards baseline
            if isinstance(val, (int, float)):
                # Decay factor
                decay = 0.95 
                noise = random.uniform(-0.5, 0.5)
                
                # Custom neurons may have slightly different dynamics
                # They decay a bit slower to maintain their learned state
                if neuron in custom_neurons:
                    decay = 0.97  # Slower decay for custom neurons
                
                new_val = val * decay + noise
                updated_state[neuron] = new_val

        # 2. Connection effects (Simplified delta calculation)
        connection_deltas = {}
        
        for (src, dst), w in weights.items():
            if src in current_state and dst in current_state:
                if dst in PURE_INPUTS: 
                    continue
                
                src_val = current_state[src]
                if isinstance(src_val, (int, float)):
                    effect = src_val * w * 0.1
                    connection_deltas[dst] = connection_deltas.get(dst, 0) + effect
                    
        # Apply deltas
        for neuron, delta in connection_deltas.items():
            if neuron in updated_state:
                updated_state[neuron] += delta
            elif neuron in current_state and neuron not in PURE_INPUTS:
                updated_state[neuron] = current_state[neuron] + delta

        # Clamp
        final_state = {}
        for k, v in updated_state.items():
            final_state[k] = max(-100, min(100, v))

        self.state_update_result.emit({'processed_state': final_state})

    def _get_neuron_value(self, val):
        """Convert various value types to float for calculations."""
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, bool):
            return 100.0 if val else 0.0
        return 0.0
