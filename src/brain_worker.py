"""
brain_worker.py - Background thread worker for heavy brain computations

Offloads heavy neurogenesis checks, Hebbian learning, and state updates
to a separate thread to prevent UI stalling.

"""

import time
import math
import random
from heapq import nlargest
from typing import Dict, List, Tuple, Optional, Any
from collections import deque
from dataclasses import dataclass
from PyQt5.QtCore import QThread, pyqtSignal, QMutex, QMutexLocker, QWaitCondition


@dataclass
class WorkItem:
    """Represents a unit of work to be processed by the worker thread"""
    work_type: str  # 'neurogenesis', 'hebbian', 'state_update'
    data: Dict[str, Any]
    timestamp: float


class BrainWorker(QThread):
    """
    Background worker thread for heavy brain computations.
    
    Signals:
        neurogenesis_result: Emitted when neurogenesis check completes
            - Dict containing 'created' (bool) and 'neuron_name' (str or None)
        hebbian_result: Emitted when Hebbian learning completes
            - Dict containing 'updated_pairs' list and 'weights' dict updates
        state_update_result: Emitted when state update completes
            - Dict containing the processed state changes
        error_occurred: Emitted when an error occurs
            - str containing the error message
    """
    
    # Signals for communicating results back to main thread
    neurogenesis_result = pyqtSignal(dict)
    hebbian_result = pyqtSignal(dict)
    state_update_result = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, brain_widget, parent=None):
        super().__init__(parent)
        
        # Store reference to brain widget for accessing data
        # NOTE: We only READ from brain_widget in the worker thread
        # All WRITES happen via signals back to the main thread
        self.brain_widget = brain_widget
        
        # Thread control
        self._running = True
        self._paused = False
        
        # Work queue with mutex protection
        self._work_queue = deque()
        self._queue_mutex = QMutex()
        self._work_available = QWaitCondition()
        
        # Cached copies of data for thread-safe access
        self._cached_state = {}
        self._cached_weights = {}
        self._cached_neuron_positions = {}
        self._cached_config = None
        self._cache_mutex = QMutex()
        
        # Timing controls
        self._last_neurogenesis_time = 0
        self._last_hebbian_time = 0
        self._neurogenesis_interval = 2.0  # seconds
        self._hebbian_interval = 30.0  # seconds (will be updated from config)
        
    def stop(self):
        """Stop the worker thread gracefully"""
        self._running = False
        # Wake up the thread if it's waiting
        self._queue_mutex.lock()
        self._work_available.wakeAll()
        self._queue_mutex.unlock()
        
    def pause(self):
        """Pause processing (for simulation pause)"""
        self._paused = True
        
    def resume(self):
        """Resume processing"""
        self._paused = False
        # Wake up the thread
        self._queue_mutex.lock()
        self._work_available.wakeAll()
        self._queue_mutex.unlock()
        
    def update_cache(self, state: Dict, weights: Dict, neuron_positions: Dict, config):
        """
        Update the cached copies of brain data.
        Called from the main thread to provide fresh data for processing.
        Thread-safe via mutex.
        """
        with QMutexLocker(self._cache_mutex):
            self._cached_state = state.copy() if state else {}
            self._cached_weights = weights.copy() if weights else {}
            self._cached_neuron_positions = neuron_positions.copy() if neuron_positions else {}
            self._cached_config = config
            
    def queue_neurogenesis_check(self, state_with_context: Dict):
        """Queue a neurogenesis check for background processing"""
        work_item = WorkItem(
            work_type='neurogenesis',
            data=state_with_context.copy(),
            timestamp=time.time()
        )
        self._enqueue_work(work_item)
        
    def queue_hebbian_learning(self):
        """Queue Hebbian learning for background processing"""
        work_item = WorkItem(
            work_type='hebbian',
            data={},
            timestamp=time.time()
        )
        self._enqueue_work(work_item)
        
    def queue_state_update(self, new_state: Dict):
        """Queue a state update for background processing"""
        work_item = WorkItem(
            work_type='state_update',
            data=new_state.copy(),
            timestamp=time.time()
        )
        self._enqueue_work(work_item)
        
    def _enqueue_work(self, work_item: WorkItem):
        """Add work item to the queue in a thread-safe manner"""
        self._queue_mutex.lock()
        try:
            self._work_queue.append(work_item)
            self._work_available.wakeOne()
        finally:
            self._queue_mutex.unlock()
            
    def run(self):
        """Main worker thread loop"""
        print("🧠 BrainWorker thread started")
        
        while self._running:
            work_item = None
            
            # Wait for work with timeout
            self._queue_mutex.lock()
            try:
                if not self._work_queue and self._running:
                    # Wait up to 100ms for new work
                    self._work_available.wait(self._queue_mutex, 100)
                    
                if self._work_queue and not self._paused:
                    work_item = self._work_queue.popleft()
            finally:
                self._queue_mutex.unlock()
                
            # Process the work item
            if work_item and not self._paused:
                try:
                    self._process_work_item(work_item)
                except Exception as e:
                    error_msg = f"BrainWorker error processing {work_item.work_type}: {str(e)}"
                    print(f"⚠️ {error_msg}")
                    import traceback
                    traceback.print_exc()
                    self.error_occurred.emit(error_msg)
                    
        print("🧠 BrainWorker thread stopped")
        
    def _process_work_item(self, work_item: WorkItem):
        """Process a single work item based on its type"""
        if work_item.work_type == 'neurogenesis':
            self._process_neurogenesis(work_item.data)
        elif work_item.work_type == 'hebbian':
            self._process_hebbian_learning()
        elif work_item.work_type == 'state_update':
            self._process_state_update(work_item.data)
            
    def _process_neurogenesis(self, state_with_context: Dict):
        """
        Process neurogenesis check in background thread.
        This is the heavy computation that was stalling the UI.
        """
        result = {
            'created': False,
            'neuron_name': None,
            'neuron_type': None,
            'trigger_value': 0,
            'position': None,
            'connections': {}
        }
        
        # Get cached data for thread-safe access
        with QMutexLocker(self._cache_mutex):
            cached_state = self._cached_state.copy()
            cached_weights = self._cached_weights.copy()
            cached_positions = self._cached_neuron_positions.copy()
            config = self._cached_config
            
        if not config:
            self.neurogenesis_result.emit(result)
            return
            
        try:
            # Check if neurogenesis should trigger
            neurogenesis_config = getattr(config, 'neurogenesis', {})
            if isinstance(neurogenesis_config, dict):
                novelty_threshold = neurogenesis_config.get('novelty_threshold', 3.0)
                stress_threshold = neurogenesis_config.get('stress_threshold', 1.2)
                reward_threshold = neurogenesis_config.get('reward_threshold', 3.5)
                cooldown = neurogenesis_config.get('cooldown', 180)
            else:
                novelty_threshold = 3.0
                stress_threshold = 1.2
                reward_threshold = 3.5
                cooldown = 180
                
            current_time = time.time()
            
            # Check cooldown
            if current_time - self._last_neurogenesis_time < cooldown:
                self.neurogenesis_result.emit(result)
                return
                
            # Calculate neurogenesis counters from state
            novelty_counter = state_with_context.get('novelty_exposure', 0)
            stress_counter = state_with_context.get('sustained_stress', 0)
            reward_counter = state_with_context.get('recent_rewards', 0)
            
            # Determine which type of neuron to create (if any)
            neuron_type = None
            trigger_value = 0
            
            if novelty_counter >= novelty_threshold:
                neuron_type = 'novelty'
                trigger_value = novelty_counter
            elif stress_counter >= stress_threshold:
                neuron_type = 'stress'
                trigger_value = stress_counter
            elif reward_counter >= reward_threshold:
                neuron_type = 'reward'
                trigger_value = reward_counter
                
            if neuron_type:
                # Generate unique neuron name
                base_name = f"{neuron_type}_{int(current_time) % 10000}"
                counter = 1
                neuron_name = base_name
                while neuron_name in cached_positions:
                    neuron_name = f"{base_name}_{counter}"
                    counter += 1
                    
                # Calculate position for new neuron (avoid overlaps)
                position = self._calculate_neuron_position(cached_positions)
                
                # Determine connections based on current state
                connections = self._calculate_initial_connections(
                    neuron_type, 
                    cached_state, 
                    cached_positions
                )
                
                result = {
                    'created': True,
                    'neuron_name': neuron_name,
                    'neuron_type': neuron_type,
                    'trigger_value': trigger_value,
                    'position': position,
                    'connections': connections
                }
                
                self._last_neurogenesis_time = current_time
                print(f"✨ Worker: Neurogenesis triggered! Creating {neuron_type} neuron: {neuron_name}")
                
        except Exception as e:
            print(f"⚠️ Worker neurogenesis error: {e}")
            import traceback
            traceback.print_exc()
            
        self.neurogenesis_result.emit(result)
        
    def _calculate_neuron_position(self, existing_positions: Dict) -> Tuple[int, int]:
        """Calculate a position for a new neuron that doesn't overlap with existing ones"""
        # Define bounds for neuron placement
        min_x, max_x = 100, 900
        min_y, max_y = 150, 450
        min_distance = 80  # Minimum distance from other neurons
        
        # Try random positions until we find one that doesn't overlap
        max_attempts = 50
        for _ in range(max_attempts):
            x = random.randint(min_x, max_x)
            y = random.randint(min_y, max_y)
            
            # Check distance from all existing neurons
            too_close = False
            for pos in existing_positions.values():
                if isinstance(pos, (tuple, list)) and len(pos) >= 2:
                    dist = math.sqrt((x - pos[0])**2 + (y - pos[1])**2)
                    if dist < min_distance:
                        too_close = True
                        break
                        
            if not too_close:
                return (x, y)
                
        # Fallback: return a position in unused area
        return (random.randint(min_x, max_x), random.randint(min_y, max_y))
        
    def _calculate_initial_connections(
        self, 
        neuron_type: str, 
        state: Dict, 
        positions: Dict
    ) -> Dict[str, float]:
        """Calculate initial connection weights for a new neuron"""
        connections = {}
        
        # Core neurons to potentially connect to
        core_neurons = ['hunger', 'happiness', 'cleanliness', 'sleepiness', 
                       'satisfaction', 'anxiety', 'curiosity']
        
        for neuron in core_neurons:
            if neuron not in positions:
                continue
                
            neuron_value = state.get(neuron, 50)
            deviation = abs(neuron_value - 50)
            
            # Only connect if there's significant activation
            if deviation > 20:
                # Weight based on deviation, with sign based on neuron type
                base_weight = (deviation / 50) * 0.6
                
                if neuron_type == 'stress':
                    # Stress neurons inhibit anxiety
                    if neuron == 'anxiety':
                        connections[neuron] = -base_weight
                    elif neuron in ['happiness', 'satisfaction']:
                        connections[neuron] = base_weight * 0.3
                elif neuron_type == 'reward':
                    # Reward neurons enhance positive emotions
                    if neuron in ['happiness', 'satisfaction']:
                        connections[neuron] = base_weight
                    elif neuron == 'anxiety':
                        connections[neuron] = -base_weight * 0.5
                elif neuron_type == 'novelty':
                    # Novelty neurons connect to curiosity
                    if neuron == 'curiosity':
                        connections[neuron] = base_weight
                    elif neuron == 'anxiety':
                        connections[neuron] = -base_weight * 0.3
                        
        return connections
        
    def _process_hebbian_learning(self):
        """
        Process Hebbian learning in background thread.
        This performs the weight updates between neuron pairs.
        """
        result = {
            'updated_pairs': [],
            'weight_updates': {},
            'timestamp': time.time()
        }
        
        # Get cached data
        with QMutexLocker(self._cache_mutex):
            cached_state = self._cached_state.copy()
            cached_weights = self._cached_weights.copy()
            cached_positions = self._cached_neuron_positions.copy()
            config = self._cached_config
            
        if not config or not cached_weights:
            self.hebbian_result.emit(result)
            return
            
        try:
            # Get config values
            hebbian_config = getattr(config, 'hebbian', {})
            if isinstance(hebbian_config, dict):
                learning_rate = hebbian_config.get('learning_rate', 0.1)
                weight_decay = hebbian_config.get('weight_decay', 0.01)
                max_weight = hebbian_config.get('max_weight', 1.0)
                min_weight = hebbian_config.get('min_weight', -1.0)
            else:
                learning_rate = 0.1
                weight_decay = 0.01
                max_weight = 1.0
                min_weight = -1.0
                
            neurogenesis_config = getattr(config, 'neurogenesis', {})
            if isinstance(neurogenesis_config, dict):
                max_hebbian_pairs = neurogenesis_config.get('max_hebbian_pairs', 2)
            else:
                max_hebbian_pairs = 2
                
            # Excluded neurons (binary states, not real values)
            excluded_neurons = ['is_sick', 'is_eating', 'pursuing_food', 
                               'direction', 'is_sleeping', 'position']
            
            # Collect real neurons only
            neurons = [n for n in cached_positions.keys() if n not in excluded_neurons]
            
            # Score every possible pair by summed activation
            scored_pairs = []
            for i, n1 in enumerate(neurons):
                for n2 in neurons[i + 1:]:
                    v1 = self._get_neuron_value(cached_state.get(n1, 50))
                    v2 = self._get_neuron_value(cached_state.get(n2, 50))
                    score = v1 + v2
                    scored_pairs.append((score, n1, n2, v1, v2))
                    
            # Get top pairs
            top_pairs = nlargest(max_hebbian_pairs, scored_pairs)
            
            # Process each pair
            updated_pairs = []
            weight_updates = {}
            
            for _, n1, n2, v1, v2 in top_pairs:
                # Calculate weight change
                delta = learning_rate * (v1 / 100.0) * (v2 / 100.0)
                
                # Find the pair in weights (check both orderings)
                pair = (n1, n2)
                reverse_pair = (n2, n1)
                use_pair = pair if pair in cached_weights else reverse_pair
                
                if use_pair not in cached_weights:
                    continue
                    
                old_weight = cached_weights[use_pair]
                new_weight = old_weight + delta - (old_weight * weight_decay)
                new_weight = max(min_weight, min(max_weight, new_weight))
                
                weight_updates[use_pair] = {
                    'old_weight': old_weight,
                    'new_weight': new_weight,
                    'delta': delta
                }
                updated_pairs.append((n1, n2))
                
            result = {
                'updated_pairs': updated_pairs,
                'weight_updates': weight_updates,
                'timestamp': time.time()
            }
            
            if updated_pairs:
                print(f"📊 Worker: Hebbian learning processed {len(updated_pairs)} pairs")
                
        except Exception as e:
            print(f"⚠️ Worker Hebbian error: {e}")
            import traceback
            traceback.print_exc()
            
        self.hebbian_result.emit(result)
        
    def _process_state_update(self, new_state: Dict):
        """
        Process state update in background thread.
        Handles clamping, decay calculations, etc.
        """
        result = {
            'processed_state': {},
            'changes': {},
            'timestamp': time.time()
        }
        
        # Get cached current state
        with QMutexLocker(self._cache_mutex):
            current_state = self._cached_state.copy()
            cached_positions = self._cached_neuron_positions.copy()
            
        try:
            processed_state = {}
            changes = {}
            
            for neuron, value in new_state.items():
                # Skip neurons that don't exist
                if neuron not in cached_positions:
                    continue
                    
                # Handle boolean values
                if isinstance(value, bool):
                    processed_state[neuron] = value
                    if current_state.get(neuron) != value:
                        changes[neuron] = {'old': current_state.get(neuron), 'new': value}
                    continue
                    
                # Handle non-numeric values
                if not isinstance(value, (int, float)):
                    processed_state[neuron] = value
                    continue
                    
                # Clamp to valid range
                clamped_value = max(0, min(100, value))
                
                # Apply gentle decay if stuck at extremes
                current_value = current_state.get(neuron, 50)
                if isinstance(current_value, (int, float)) and abs(current_value - 50) > 30:
                    decay_rate = 0.02
                    if current_value > 50:
                        clamped_value = min(clamped_value, current_value - (current_value - 50) * decay_rate)
                    else:
                        clamped_value = max(clamped_value, current_value + (50 - current_value) * decay_rate)
                        
                processed_state[neuron] = clamped_value
                
                # Track significant changes
                if abs(clamped_value - current_state.get(neuron, 50)) > 0.1:
                    changes[neuron] = {
                        'old': current_state.get(neuron, 50), 
                        'new': clamped_value
                    }
                    
            result = {
                'processed_state': processed_state,
                'changes': changes,
                'timestamp': time.time()
            }
            
        except Exception as e:
            print(f"⚠️ Worker state update error: {e}")
            import traceback
            traceback.print_exc()
            
        self.state_update_result.emit(result)
        
    def _get_neuron_value(self, value) -> float:
        """Convert a neuron value to a numerical format"""
        if isinstance(value, (int, float)):
            return float(value)
        elif isinstance(value, bool):
            return 100.0 if value else 0.0
        elif isinstance(value, str):
            return 75.0
        else:
            return 50.0