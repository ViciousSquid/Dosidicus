import sys
import time
import random
import traceback
import math
from queue import Queue, Empty
from heapq import nlargest

from PyQt5.QtCore import QThread, pyqtSignal, QMutex, QMutexLocker, QWaitCondition

class BrainWorker(QThread):
    """
    Background worker for handling expensive brain logic operations:
    - Neurogenesis checks
    - Hebbian learning calculations
    - State decay and update processing
    """
    
    # Signals for results (emitted to main thread)
    neurogenesis_result = pyqtSignal(dict)
    hebbian_result = pyqtSignal(dict)
    state_update_result = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, brain_widget=None):
        super().__init__()
        self.brain_widget = brain_widget  # Optional weak ref if needed, usually avoided for thread safety
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
            'learning_rate': 0.1,
            'new_neurons': set(),
            'custom_neurons': set()
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
        """
        with QMutexLocker(self._cache_mutex):
            # Deep copy or safe copy important structures
            self.cache['state'] = state.copy()
            self.cache['weights'] = weights.copy()
            self.cache['positions'] = positions.copy()
            self.cache['config'] = config
            self.cache['excluded_neurons'] = excluded_neurons if excluded_neurons else set()
            self.cache['connector_neurons'] = connector_neurons if connector_neurons else set()
            self.cache['learning_rate'] = learning_rate
            self.cache['new_neurons'] = new_neurons if new_neurons else set()
            self.cache['custom_neurons'] = custom_neurons if custom_neurons else set()

    def queue_neurogenesis_check(self, state_context):
        self._add_task('neurogenesis', {'state': state_context})

    def queue_hebbian_learning(self):
        # print("🧵 BrainWorker: Hebbian learning queued")  # Uncomment for verbose queuing logs
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

    # --- Pause and Resume Methods ---
    def pause(self):
        """Pause the worker thread."""
        with QMutexLocker(self.queue_mutex):
            self._paused = True
    
    def resume(self):
        """Resume the worker thread."""
        with QMutexLocker(self.queue_mutex):
            self._paused = False
            self.wait_condition.wakeAll()
    # --------------------------------

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
                    self.wait_condition.wait(self.queue_mutex, 200) # Timeout allows checking _running
                    # Re-check pause after wait
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
        
        # The stress path used to short-circuit on `anxiety > 75`, which any
        # startle satisfies instantly - so sustained_stress (which needs ~20
        # stressed ticks to reach 2.0) never mattered and stress neurons were
        # by far the easiest type to grow. Sustained stress is now the primary
        # signal and acute anxiety only counts when it is genuinely extreme.
        triggers = {
            'novelty': state.get('novelty_exposure', 0) > neuro_config.get('novelty_threshold', 2.0),
            'stress': (state.get('sustained_stress', 0) > neuro_config.get('stress_threshold', 1.2)
                       or state.get('anxiety', 0) > 90),
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
            # Emit result back to main thread to finalize creation
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
        """Retired.

        Plasticity lives in src/plasticity.py and is committed on the main
        thread by BrainWidget.perform_hebbian_learning(). This copy sampled the
        network once per cycle and could not see brief events; the STDP plugin
        used to monkey-patch it to work around that. Kept as a no-op so any
        external caller (or an old patch) fails safe instead of silently
        applying a second, divergent learning rule.
        """
        self.hebbian_result.emit({'updated_pairs': [], 'weight_updates': {}})

    def _process_state_update(self, data):
        """Worker-side health check.

        This used to carry a third, divergent copy of forward propagation
        (decay 0.95, 0.1 timestep factor). It was unreachable - the only task
        ever queued is {'health_check': True} - and propagation now lives in
        exactly one place, BrainWidget.propagate_activations(), which runs on
        the main thread where the state it reads is authoritative.
        """
        if data.get('health_check'):
            self.state_update_result.emit({'health_check': True})
            return

        self.state_update_result.emit({'health_check': True})

    def _get_neuron_value(self, val):
        # bool must be checked before int/float: bool is a subclass of int, so
        # `isinstance(True, (int, float))` is True and would return 1.0 instead
        # of the intended 100.0.
        if isinstance(val, bool):
            return 100.0 if val else 0.0
        if isinstance(val, (int, float)):
            return float(val)
        return 0.0