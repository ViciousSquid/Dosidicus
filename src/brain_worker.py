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
        self._cached_excluded_neurons = set()
        self._cached_learning_rate = 0.1
        self._cached_new_neurons = set()
        self._cache_mutex = QMutex()
        
        # Timing controls
        self._last_neurogenesis_time = 0
        self._last_hebbian_time = 0
        self._neurogenesis_interval = 2.0  # seconds
        self._hebbian_interval = 30.0  # seconds (will be updated from config)
        
        # Health monitoring
        self._last_heartbeat = time.time()
        self._last_job = "-"
        self._jobs_processed = 0
        
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
        
    def update_cache(self, state: Dict, weights: Dict, neuron_positions: Dict, config,
                     excluded_neurons=None, learning_rate=0.1, new_neurons=None):
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
            self._cached_excluded_neurons = set(excluded_neurons) if excluded_neurons else set()
            self._cached_learning_rate = learning_rate
            self._cached_new_neurons = set(new_neurons) if new_neurons else set()
            
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
        print("🧵 BrainWorker thread started and entering main loop")
        
        while self._running:
            try:
                work_item = None
                
                # Wait for work with longer timeout
                self._queue_mutex.lock()
                try:
                    if not self._work_queue and self._running:
                        # Wait up to 1 second for work
                        self._work_available.wait(self._queue_mutex, 1000)
                    
                    if self._work_queue and not self._paused:
                        work_item = self._work_queue.popleft()
                finally:
                    self._queue_mutex.unlock()
                
                if work_item:
                    self._process_work_item(work_item)
                else:
                    # No work available, do a health check
                    if self._running and not self._paused:
                        time.sleep(0.1)  # Small sleep to prevent CPU spinning
                        
                # Send heartbeat periodically
                current_time = time.time()
                if current_time - self._last_heartbeat > 5.0:  # Every 5 seconds
                    self._last_heartbeat = current_time
                        
            except Exception as e:
                print(f"🧵 BrainWorker main loop error: {e}")
                import traceback
                traceback.print_exc()
                self.error_occurred.emit(str(e))
                # Continue running despite errors
                time.sleep(1)  # Brief pause before continuing
        
        print("🧵 BrainWorker thread exiting cleanly")
        
    def _process_work_item(self, work_item: WorkItem):
        self._last_job = work_item.work_type
        self._jobs_processed += 1
        
        if work_item.work_type == 'neurogenesis':
            self._process_neurogenesis(work_item.data)
        elif work_item.work_type == 'hebbian':
            self._process_hebbian_learning()
        elif work_item.work_type == 'state_update':
            self._process_state_update(work_item.data)
            
    def _process_neurogenesis(self, state_with_context: Dict):
        """Process neurogenesis check in background thread.
        
        Performs preliminary trigger detection and signals to main thread
        whether neuron creation should proceed. Actual neuron creation
        happens on the main thread to ensure thread safety.
        """
        result = {
            'should_create': False,
            'neuron_type': None,
            'trigger_value': 0,
            'trigger_reason': None,
            'is_emergency': False,
            'state_context': {}
        }

        # Get cached config for threshold checks
        with QMutexLocker(self._cache_mutex):
            config = self._cached_config
            cached_state = self._cached_state.copy()

        if not config:
            self.neurogenesis_result.emit(result)
            return

        try:
            # Extract key values for trigger detection
            anxiety = state_with_context.get('anxiety', 50)
            curiosity = state_with_context.get('curiosity', 50)
            satisfaction = state_with_context.get('satisfaction', 50)
            happiness = state_with_context.get('happiness', 50)
            hunger = state_with_context.get('hunger', 50)
            sustained_stress = state_with_context.get('sustained_stress', 0)
            novelty_exposure = state_with_context.get('novelty_exposure', 0)
            recent_rewards = state_with_context.get('recent_rewards', 0)
            
            trigger_type = None
            trigger_value = 0
            trigger_reason = None
            is_emergency = False
            
            # ===== PRIORITY 1: EMERGENCY STRESS (critical anxiety) =====
            if anxiety >= 95:
                trigger_type = 'stress'
                trigger_value = anxiety
                trigger_reason = 'emergency_anxiety'
                is_emergency = True
                print(f"🚨 [Worker] EMERGENCY: Critical anxiety ({anxiety:.1f})")
            
            # ===== PRIORITY 2: HIGH STRESS =====
            elif anxiety > 75:
                trigger_type = 'stress'
                trigger_value = anxiety
                trigger_reason = 'high_anxiety'
            
            elif sustained_stress > 1.0:
                trigger_type = 'stress'
                trigger_value = sustained_stress * 50 + 50  # Scale to 50-100
                trigger_reason = 'sustained_stress'
            
            elif hunger > 85:
                trigger_type = 'stress'
                trigger_value = hunger
                trigger_reason = 'hunger_crisis'
            
            # ===== PRIORITY 3: NOVELTY =====
            elif curiosity > 70:
                trigger_type = 'novelty'
                trigger_value = curiosity
                trigger_reason = 'high_curiosity'
            
            elif novelty_exposure > 2:
                trigger_type = 'novelty'
                trigger_value = novelty_exposure * 20 + 50  # Scale
                trigger_reason = 'novelty_exposure'
            
            elif state_with_context.get('new_object_encountered', False):
                trigger_type = 'novelty'
                trigger_value = 75
                trigger_reason = 'new_object'
            
            # ===== PRIORITY 4: REWARD =====
            elif satisfaction > 70 and happiness > 60:
                trigger_type = 'reward'
                trigger_value = (satisfaction + happiness) / 2
                trigger_reason = 'high_satisfaction'
            
            elif recent_rewards > 2:
                trigger_type = 'reward'
                trigger_value = recent_rewards * 15 + 50  # Scale
                trigger_reason = 'recent_rewards'
            
            elif state_with_context.get('recent_positive_outcome', False):
                trigger_type = 'reward'
                trigger_value = 70
                trigger_reason = 'positive_outcome'
            
            # Build result if trigger detected
            if trigger_type:
                result = {
                    'should_create': True,
                    'neuron_type': trigger_type,
                    'trigger_value': trigger_value,
                    'trigger_reason': trigger_reason,
                    'is_emergency': is_emergency,
                    'state_context': state_with_context.copy()
                }
                #print(f"🧵 [Worker] Trigger detected: {trigger_type} ({trigger_reason}, value={trigger_value:.1f})")   # DEBUG LINE DEBUG LINE DEBUG LINE DEBUG LINE
            
            self.neurogenesis_result.emit(result)
            
        except Exception as e:
            print(f"Error in neurogenesis processing: {e}")
            self.error_occurred.emit(f"Neurogenesis error: {e}")
            self.neurogenesis_result.emit(result)

    def _process_hebbian_learning(self):
        """Process Hebbian learning in background thread"""
        result = {
            'updated_pairs': [],
            'weight_updates': {},
            'timestamp': time.time()
        }
        
        try:
            # Get cached data with mutex protection
            with QMutexLocker(self._cache_mutex):
                state = self._cached_state.copy()
                weights = self._cached_weights.copy()
                neuron_positions = self._cached_neuron_positions.copy()
                config = self._cached_config
                excluded_neurons = self._cached_excluded_neurons.copy()
                learning_rate = self._cached_learning_rate
                new_neurons = self._cached_new_neurons.copy()
            
            if not config or not weights:
                print("   [Worker] Hebbian: No config or weights cached")
                self.hebbian_result.emit(result)
                return
            
            print(f"++ [Worker] Hebbian learning cycle triggered")
            
            # Get neurons excluding the excluded ones
            neurons = [n for n in neuron_positions.keys() if n not in excluded_neurons]
            print(f"   [Worker] Neurons available: {len(neurons)}, Weights tracked: {len(weights)}")
            
            if len(neurons) < 2:
                print("   [Worker] Not enough neurons for Hebbian learning")
                self.hebbian_result.emit(result)
                return
            
            # Score all neuron pairs by their combined activation
            scored_pairs = []
            for i, n1 in enumerate(neurons):
                for n2 in neurons[i + 1:]:
                    v1 = self._get_neuron_value(state.get(n1, 50))
                    v2 = self._get_neuron_value(state.get(n2, 50))
                    score = v1 + v2
                    scored_pairs.append((score, n1, n2, v1, v2))
            
            # Get top K pairs
            top_k = config.neurogenesis.get('max_hebbian_pairs', 2) if hasattr(config, 'neurogenesis') else 2
            top_pairs = nlargest(top_k, scored_pairs)
            print(f"   [Worker] Top {top_k} pairs selected from {len(scored_pairs)} candidates")
            
            # Calculate weight updates for top pairs
            updated_pairs = []
            weight_updates = {}
            
            hebbian_config = config.hebbian if hasattr(config, 'hebbian') else {}
            decay_rate = hebbian_config.get('weight_decay', 0.01)
            min_weight = hebbian_config.get('min_weight', -1.0)
            max_weight = hebbian_config.get('max_weight', 1.0)
            
            for _, n1, n2, v1, v2 in top_pairs:
                base_lr = learning_rate
                
                # Boost learning rate for new neurons
                if n1 in new_neurons or n2 in new_neurons:
                    base_lr *= 2.0
                
                # Calculate Hebbian delta
                delta = base_lr * (v1 / 100.0) * (v2 / 100.0)
                
                # Find the pair in weights (could be either direction)
                pair = (n1, n2)
                reverse_pair = (n2, n1)
                use_pair = pair if pair in weights else reverse_pair
                
                if use_pair not in weights:
                    print(f"   [Worker] Skipping pair {n1}-{n2}: not in weights dict")
                    continue
                
                old_w = weights[use_pair]
                new_w = old_w + delta - (old_w * decay_rate)
                new_w = max(min_weight, min(max_weight, new_w))
                
                # Store update for main thread to apply
                # Use comma-separated string as key for JSON compatibility
                pair_key = f"{use_pair[0]},{use_pair[1]}"
                weight_updates[pair_key] = {
                    'old_weight': old_w,
                    'new_weight': new_w,
                    'delta': delta
                }
                updated_pairs.append(list(use_pair))
            
            if updated_pairs:
                print(f"   [Worker] Updated {len(updated_pairs)} pairs")
            else:
                print("   [Worker] No pairs were updated this cycle")
            
            result = {
                'updated_pairs': updated_pairs,
                'weight_updates': weight_updates,
                'timestamp': time.time()
            }
            
            self.hebbian_result.emit(result)
            self._last_hebbian_time = time.time()
            
        except Exception as e:
            print(f"Error in Hebbian learning: {e}")
            import traceback
            traceback.print_exc()
            self.error_occurred.emit(f"Hebbian learning error: {e}")
            self.hebbian_result.emit(result)
    
    def _get_neuron_value(self, value):
        """Convert a neuron value to numerical format for Hebbian learning."""
        if isinstance(value, (int, float)):
            return float(value)
        elif isinstance(value, bool):
            return 100.0 if value else 0.0
        elif isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return 50.0
        return 50.0

    def _process_state_update(self, new_state: Dict):
        """Process state update in background thread"""
        result = {
            'processed_state': new_state.copy(),
            'timestamp': time.time(),
            'is_health_check': new_state.get('health_check', False)
        }
        
        try:
            # Process the state update
            self.state_update_result.emit(result)
            
        except Exception as e:
            print(f"Error in state update: {e}")
            self.error_occurred.emit(f"State update error: {e}")
            self.state_update_result.emit(result)

    # Health monitoring methods
    def get_health_status(self):
        """Get comprehensive health status for monitoring"""
        current_time = time.time()
        
        return {
            'is_running': self.isRunning(),
            'last_heartbeat': self._last_heartbeat,
            'time_since_heartbeat': current_time - self._last_heartbeat,
            'jobs_processed': self._jobs_processed,
            'last_job': self._last_job,
            'queue_size': len(self._work_queue),
            'is_paused': self._paused,
            'is_running_flag': self._running
        }
    
    def is_healthy(self):
        """Quick health check for external monitoring"""
        current_time = time.time()
        
        # Multiple health indicators
        is_running_flag = self._running
        has_recent_heartbeat = (current_time - self._last_heartbeat) < 10.0
        has_queued_work = len(self._work_queue) > 0
        is_currently_processing = self._last_job != "-"
        
        # Thread is healthy if any indicator is positive
        return (
            is_running_flag or
            has_recent_heartbeat or
            has_queued_work or
            is_currently_processing
        )