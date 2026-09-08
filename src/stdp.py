"""
STDP (Spike-Timing-Dependent Plasticity) Module for Dosidicus-2

This module implements biologically-inspired STDP learning rules that complement
the existing Hebbian learning system. STDP adds temporal causality to learning:
connections strengthen when the pre-synaptic neuron fires BEFORE the post-synaptic
neuron (causal relationship), and weaken when the order is reversed.

Key Features:
- Asymmetric learning window with configurable time constants
- Thread-safe spike recording for use with BrainWorker
- Burst detection for handling rapid activations
- Integration mode for combining with rate-based Hebbian learning
- Eligibility traces for handling delayed rewards

Biological Basis:
- Pre → Post (Δt > 0): Long-Term Potentiation (LTP) - strengthening
- Post → Pre (Δt < 0): Long-Term Depression (LTD) - weakening
- Learning magnitude decreases exponentially with time difference

Adapted for Dosidicus-2's timescales:
- Real neurons: ~10-50ms learning windows
- Dosidicus-2: ~100-500ms learning windows (game runs slower than biology)
"""

import time
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Set
from PyQt5.QtCore import QMutex, QMutexLocker


@dataclass
class SpikeEvent:
    """Records a single spike event for a neuron."""
    timestamp: float
    activation_level: float  # How strongly it fired (0-100)
    was_rising: bool = True  # True if activation was increasing when threshold crossed
    
    
@dataclass 
class STDPConfig:
    """Configuration for STDP learning parameters."""
    
    # Time constants (in seconds) - controls how fast learning decays with time difference
    tau_plus: float = 0.15       # LTP time constant (pre before post)
    tau_minus: float = 0.15      # LTD time constant (post before pre)
    
    # Learning amplitudes
    A_plus: float = 0.08         # Maximum LTP amplitude
    A_minus: float = 0.05        # Maximum LTD amplitude (often smaller for stability)
    
    # Timing window
    time_window: float = 0.5     # Maximum time difference to consider (seconds)
    
    # Spike detection
    spike_threshold: float = 60.0       # Activation level to consider a "spike"
    spike_rising_threshold: float = 8.0  # Minimum increase to detect rising edge
    refractory_period: float = 0.08     # Minimum time between spikes (seconds)
    
    # Burst handling
    burst_window: float = 0.3           # Time window to detect bursts
    burst_threshold: int = 3            # Number of spikes to consider a burst
    burst_bonus: float = 1.5            # Multiplier for burst-associated learning
    
    # Integration with Hebbian
    stdp_weight: float = 0.4            # How much STDP contributes vs rate-based (0-1)
    
    # Eligibility traces (for delayed reward learning)
    eligibility_decay: float = 0.95     # How fast eligibility traces decay
    eligibility_window: float = 2.0     # How long eligibility persists (seconds)
    
    # Connection-specific learning rate modulation
    new_connection_boost: float = 2.0   # Boost for newly formed connections
    custom_neuron_boost: float = 1.3    # Boost for custom (user-created) neurons


class SpikeTracker:
    """
    Thread-safe tracker for neuron activation spikes.
    
    Records when neurons cross activation thresholds, enabling STDP
    to compute timing-dependent weight changes.
    """
    
    def __init__(self, config: Optional[STDPConfig] = None):
        self.config = config or STDPConfig()
        self._mutex = QMutex()
        
        # Spike history: neuron_name -> deque of SpikeEvent
        self._spike_history: Dict[str, deque] = {}
        self._max_history_per_neuron = 20
        
        # Previous activation values for edge detection
        self._previous_activations: Dict[str, float] = {}
        
        # Burst tracking
        self._burst_counts: Dict[str, int] = {}  # Recent spike counts
        self._last_burst_check: float = 0.0
        
    def record_activation(self, neuron_name: str, activation: float, 
                          timestamp: Optional[float] = None) -> Optional[SpikeEvent]:
        """
        Record a neuron's activation level and detect spikes.
        
        A spike is detected when:
        1. Activation crosses above the threshold
        2. Activation was rising (not just staying high)
        3. Sufficient time has passed since last spike (refractory period)
        
        Args:
            neuron_name: Name of the neuron
            activation: Current activation level (0-100)
            timestamp: Optional timestamp (uses current time if not provided)
            
        Returns:
            SpikeEvent if a spike was detected, None otherwise
        """
        if timestamp is None:
            timestamp = time.time()
            
        with QMutexLocker(self._mutex):
            # Get previous activation
            prev_activation = self._previous_activations.get(neuron_name, 50.0)
            self._previous_activations[neuron_name] = activation
            
            # Check if this is a spike (threshold crossing with rising edge)
            is_above_threshold = activation >= self.config.spike_threshold
            was_below_threshold = prev_activation < self.config.spike_threshold
            is_rising = (activation - prev_activation) >= self.config.spike_rising_threshold
            
            # Alternative: strong activation even if not crossing threshold
            is_strong_activation = activation >= 80 and is_rising
            
            if not ((is_above_threshold and (was_below_threshold or is_rising)) or is_strong_activation):
                return None
            
            # Check refractory period
            if neuron_name in self._spike_history and len(self._spike_history[neuron_name]) > 0:
                last_spike = self._spike_history[neuron_name][-1]
                if (timestamp - last_spike.timestamp) < self.config.refractory_period:
                    return None
            
            # Create and record spike event
            spike = SpikeEvent(
                timestamp=timestamp,
                activation_level=activation,
                was_rising=is_rising
            )
            
            # Initialize history deque if needed
            if neuron_name not in self._spike_history:
                self._spike_history[neuron_name] = deque(maxlen=self._max_history_per_neuron)
            
            self._spike_history[neuron_name].append(spike)
            
            # Update burst count
            self._burst_counts[neuron_name] = self._burst_counts.get(neuron_name, 0) + 1
            
            return spike
    
    def record_batch(self, state: Dict[str, float], timestamp: Optional[float] = None) -> List[Tuple[str, SpikeEvent]]:
        """
        Record activations for multiple neurons at once.
        
        Args:
            state: Dictionary of neuron_name -> activation_level
            timestamp: Optional shared timestamp for all recordings
            
        Returns:
            List of (neuron_name, SpikeEvent) tuples for detected spikes
        """
        if timestamp is None:
            timestamp = time.time()
            
        spikes = []
        for neuron_name, activation in state.items():
            if isinstance(activation, (int, float)):
                spike = self.record_activation(neuron_name, float(activation), timestamp)
                if spike:
                    spikes.append((neuron_name, spike))
        
        return spikes
    
    def get_last_spike_time(self, neuron_name: str) -> Optional[float]:
        """Get the timestamp of the most recent spike for a neuron."""
        with QMutexLocker(self._mutex):
            if neuron_name in self._spike_history and len(self._spike_history[neuron_name]) > 0:
                return self._spike_history[neuron_name][-1].timestamp
            return None
    
    def get_recent_spikes(self, neuron_name: str, window: Optional[float] = None) -> List[SpikeEvent]:
        """Get all spikes within a time window for a neuron."""
        if window is None:
            window = self.config.time_window
        with QMutexLocker(self._mutex):
            return self._get_recent_spikes_nolock(neuron_name, window)

    def _get_recent_spikes_nolock(self, neuron_name: str, window: float) -> List[SpikeEvent]:
        """Lock-free version — caller must already hold _mutex."""
        cutoff = time.time() - window
        if neuron_name not in self._spike_history:
            return []
        return [s for s in self._spike_history[neuron_name] if s.timestamp >= cutoff]

    def is_bursting(self, neuron_name: str) -> bool:
        """Check if a neuron is currently in a burst state."""
        with QMutexLocker(self._mutex):
            return self._is_bursting_nolock(neuron_name)

    def _is_bursting_nolock(self, neuron_name: str) -> bool:
        """Lock-free version — caller must already hold _mutex."""
        recent = self._get_recent_spikes_nolock(neuron_name, self.config.burst_window)
        return len(recent) >= self.config.burst_threshold
    
    def cleanup_old_spikes(self, max_age: Optional[float] = None):
        """Remove spike records older than max_age seconds."""
        if max_age is None:
            max_age = self.config.time_window * 3
            
        current_time = time.time()
        cutoff = current_time - max_age
        
        with QMutexLocker(self._mutex):
            for neuron_name in list(self._spike_history.keys()):
                # Filter to keep only recent spikes
                self._spike_history[neuron_name] = deque(
                    (s for s in self._spike_history[neuron_name] if s.timestamp >= cutoff),
                    maxlen=self._max_history_per_neuron
                )
                
                # Remove empty histories
                if len(self._spike_history[neuron_name]) == 0:
                    del self._spike_history[neuron_name]
            
            # Decay burst counts periodically
            current_time = time.time()
            if current_time - self._last_burst_check > self.config.burst_window:
                self._burst_counts = {k: max(0, v - 1) for k, v in self._burst_counts.items()}
                self._last_burst_check = current_time
    
    def get_spike_stats(self) -> Dict:
        """Get statistics about spike activity."""
        with QMutexLocker(self._mutex):
            return {
                'tracked_neurons': len(self._spike_history),
                'total_spikes': sum(len(h) for h in self._spike_history.values()),
                'bursting_neurons': sum(
                    1 for n in self._spike_history.keys()
                    if self._is_bursting_nolock(n)          # no re-lock
                ),
                'recent_spikes_by_neuron': {
                    k: len(self._get_recent_spikes_nolock(k, self.config.time_window))  # no re-lock
                    for k in self._spike_history.keys()
                }
            }
    
    def to_dict(self) -> Dict:
        """Serialize spike tracker state for saving."""
        with QMutexLocker(self._mutex):
            return {
                'spike_history': {
                    name: [
                        {'timestamp': s.timestamp, 'activation': s.activation_level, 'rising': s.was_rising}
                        for s in spikes
                    ]
                    for name, spikes in self._spike_history.items()
                },
                'previous_activations': dict(self._previous_activations),
                'burst_counts': dict(self._burst_counts)
            }
    
    def from_dict(self, data: Dict):
        """Restore spike tracker state from saved data."""
        with QMutexLocker(self._mutex):
            self._spike_history.clear()
            for name, spikes in data.get('spike_history', {}).items():
                self._spike_history[name] = deque(
                    (SpikeEvent(s['timestamp'], s['activation'], s.get('rising', True)) for s in spikes),
                    maxlen=self._max_history_per_neuron
                )
            self._previous_activations = dict(data.get('previous_activations', {}))
            self._burst_counts = dict(data.get('burst_counts', {}))


class STDPLearner:
    """
    Implements STDP learning rules for weight updates.
    
    Computes weight changes based on the relative timing of pre-synaptic
    and post-synaptic neuron spikes.
    """
    
    def __init__(self, config: Optional[STDPConfig] = None):
        self.config = config or STDPConfig()
        self.spike_tracker = SpikeTracker(self.config)
        self._mutex = QMutex()
        
        # Eligibility traces: (pre, post) -> (trace_value, last_update_time)
        self._eligibility_traces: Dict[Tuple[str, str], Tuple[float, float]] = {}
        
        # Statistics tracking
        self._ltp_count = 0  # Long-term potentiation events
        self._ltd_count = 0  # Long-term depression events
        self._total_delta = 0.0
        
    def record_activation(self, neuron_name: str, activation: float, 
                          timestamp: Optional[float] = None) -> Optional[SpikeEvent]:
        """Record activation and detect spikes. Delegates to spike tracker."""
        return self.spike_tracker.record_activation(neuron_name, activation, timestamp)
    
    def record_state(self, state: Dict[str, float], timestamp: Optional[float] = None):
        """Record full brain state for spike detection."""
        return self.spike_tracker.record_batch(state, timestamp)
    
    def compute_stdp_delta(self, pre_neuron: str, post_neuron: str,
                           connection_age: float = 1.0,
                           is_custom_neuron: bool = False) -> float:
        """
        Compute the STDP weight change for a directed connection pre → post.
        
        The classic STDP rule:
        - If pre fires before post (Δt > 0): LTP (positive change)
        - If post fires before pre (Δt < 0): LTD (negative change)
        - Magnitude decreases exponentially with |Δt|
        
        Args:
            pre_neuron: Name of pre-synaptic neuron
            post_neuron: Name of post-synaptic neuron
            connection_age: Age multiplier (newer connections learn faster)
            is_custom_neuron: Whether either neuron is user-created
            
        Returns:
            Weight change (positive for LTP, negative for LTD, 0 if no timing data)
        """
        pre_time = self.spike_tracker.get_last_spike_time(pre_neuron)
        post_time = self.spike_tracker.get_last_spike_time(post_neuron)
        
        # Need both neurons to have spiked recently
        if pre_time is None or post_time is None:
            return 0.0
        
        # Compute time difference: positive means pre fired first
        dt = post_time - pre_time
        
        # Check if within learning window
        if abs(dt) > self.config.time_window:
            return 0.0
        
        # Compute STDP delta using exponential decay
        if dt > 0:
            # Pre before post: LTP (causal, strengthen)
            delta = self.config.A_plus * math.exp(-dt / self.config.tau_plus)
            self._ltp_count += 1
        elif dt < 0:
            # Post before pre: LTD (acausal, weaken)
            delta = -self.config.A_minus * math.exp(dt / self.config.tau_minus)
            self._ltd_count += 1
        else:
            # Simultaneous (very rare): small potentiation
            delta = self.config.A_plus * 0.5
        
        # Apply modifiers
        # 1. New connection boost
        if connection_age < 1.0:
            delta *= self.config.new_connection_boost * (1.0 - connection_age * 0.5)
        
        # 2. Custom neuron boost
        if is_custom_neuron:
            delta *= self.config.custom_neuron_boost
        
        # 3. Burst bonus (if either neuron is bursting)
        if self.spike_tracker.is_bursting(pre_neuron) or self.spike_tracker.is_bursting(post_neuron):
            delta *= self.config.burst_bonus
        
        self._total_delta += abs(delta)
        return delta
    
    def compute_symmetric_stdp(self, neuron1: str, neuron2: str,
                                connection_age: float = 1.0,
                                is_custom: bool = False) -> Tuple[float, str]:
        """
        Compute STDP for an undirected connection (checks both directions).
        
        For networks with bidirectional or undirected connections, this computes
        the stronger of the two possible STDP signals.
        
        Args:
            neuron1, neuron2: The two neurons
            connection_age: Age multiplier
            is_custom: Whether either is a custom neuron
            
        Returns:
            Tuple of (delta, direction) where direction is 'n1_to_n2', 'n2_to_n1', or 'none'
        """
        delta_1_to_2 = self.compute_stdp_delta(neuron1, neuron2, connection_age, is_custom)
        delta_2_to_1 = self.compute_stdp_delta(neuron2, neuron1, connection_age, is_custom)
        
        # Return the stronger signal
        if abs(delta_1_to_2) >= abs(delta_2_to_1):
            if delta_1_to_2 != 0:
                return delta_1_to_2, 'n1_to_n2'
        else:
            if delta_2_to_1 != 0:
                return delta_2_to_1, 'n2_to_n1'
        
        return 0.0, 'none'
    
    def update_eligibility_trace(self, pre_neuron: str, post_neuron: str, 
                                  stdp_delta: float, current_time: Optional[float] = None):
        """
        Update eligibility trace for a connection.
        
        Eligibility traces allow STDP effects to be modulated by delayed rewards,
        implementing a form of three-factor learning rule.
        
        Args:
            pre_neuron, post_neuron: Connection endpoints
            stdp_delta: The STDP delta computed for this pair
            current_time: Optional timestamp
        """
        if current_time is None:
            current_time = time.time()
            
        key = (pre_neuron, post_neuron)
        
        with QMutexLocker(self._mutex):
            # Get existing trace, decayed to current time
            if key in self._eligibility_traces:
                old_trace, old_time = self._eligibility_traces[key]
                elapsed = current_time - old_time
                
                # Exponential decay
                decay_factor = self.config.eligibility_decay ** (elapsed / 0.1)
                decayed_trace = old_trace * decay_factor
            else:
                decayed_trace = 0.0
            
            # Add new STDP signal to trace
            new_trace = decayed_trace + stdp_delta
            
            # Clamp trace magnitude
            new_trace = max(-1.0, min(1.0, new_trace))
            
            self._eligibility_traces[key] = (new_trace, current_time)
    
    def get_eligibility_trace(self, pre_neuron: str, post_neuron: str,
                               current_time: Optional[float] = None) -> float:
        """Get the current eligibility trace for a connection."""
        if current_time is None:
            current_time = time.time()
            
        key = (pre_neuron, post_neuron)
        
        with QMutexLocker(self._mutex):
            if key not in self._eligibility_traces:
                return 0.0
            
            trace, last_time = self._eligibility_traces[key]
            elapsed = current_time - last_time
            
            # Expired trace
            if elapsed > self.config.eligibility_window:
                return 0.0
            
            # Apply decay
            decay_factor = self.config.eligibility_decay ** (elapsed / 0.1)
            return trace * decay_factor
    
    def apply_reward_modulation(self, reward_signal: float) -> Dict[Tuple[str, str], float]:
        """
        Apply reward modulation to all active eligibility traces.
        
        This implements the third factor in three-factor learning rules:
        connections with positive eligibility traces are strengthened by
        positive rewards and weakened by negative rewards (and vice versa).
        
        Args:
            reward_signal: Reward value (positive = good outcome, negative = bad)
            
        Returns:
            Dictionary of (pre, post) -> weight_delta for all affected connections
        """
        current_time = time.time()
        weight_deltas = {}
        
        with QMutexLocker(self._mutex):
            for (pre, post), (trace, last_time) in list(self._eligibility_traces.items()):
                # Skip expired traces
                if current_time - last_time > self.config.eligibility_window:
                    continue
                
                # Apply decay
                elapsed = current_time - last_time
                decay_factor = self.config.eligibility_decay ** (elapsed / 0.1)
                current_trace = trace * decay_factor
                
                if abs(current_trace) < 0.01:
                    continue
                
                # Weight delta = eligibility * reward
                delta = current_trace * reward_signal * 0.1
                weight_deltas[(pre, post)] = delta
                
                # Clear the trace after applying
                self._eligibility_traces[(pre, post)] = (0.0, current_time)
        
        return weight_deltas
    
    def compute_combined_learning(self, neuron1: str, neuron2: str,
                                   v1: float, v2: float,
                                   base_learning_rate: float = 0.1,
                                   connection_age: float = 1.0,
                                   is_custom: bool = False) -> Tuple[float, Dict]:
        """
        Compute combined Hebbian + STDP learning signal.
        
        This integrates rate-based Hebbian learning with timing-based STDP,
        weighted by config.stdp_weight.
        
        Args:
            neuron1, neuron2: The two neurons in the connection
            v1, v2: Current activation values (0-100)
            base_learning_rate: Base learning rate for Hebbian component
            connection_age: Age of connection (0-1, where 0 is new)
            is_custom: Whether either neuron is custom
            
        Returns:
            Tuple of (combined_delta, metadata_dict)
        """
        # 1. Rate-based Hebbian component
        hebbian_delta = base_learning_rate * (v1 / 100.0) * (v2 / 100.0)
        
        # 2. STDP component
        stdp_delta, direction = self.compute_symmetric_stdp(
            neuron1, neuron2, connection_age, is_custom
        )
        
        # 3. Combine with weighting
        stdp_w = self.config.stdp_weight
        combined_delta = (1 - stdp_w) * hebbian_delta + stdp_w * stdp_delta
        
        # 4. Apply connection age boost to combined signal
        if connection_age < 0.5:
            combined_delta *= self.config.new_connection_boost
        
        metadata = {
            'hebbian_delta': hebbian_delta,
            'stdp_delta': stdp_delta,
            'stdp_direction': direction,
            'combined_delta': combined_delta,
            'is_ltp': stdp_delta > 0,
            'is_ltd': stdp_delta < 0
        }
        
        # Update eligibility trace
        if stdp_delta != 0:
            self.update_eligibility_trace(neuron1, neuron2, stdp_delta)
        
        return combined_delta, metadata
    
    def cleanup(self):
        """Periodic cleanup of old data."""
        self.spike_tracker.cleanup_old_spikes()
        
        # Cleanup old eligibility traces
        current_time = time.time()
        cutoff = current_time - self.config.eligibility_window * 2
        
        with QMutexLocker(self._mutex):
            self._eligibility_traces = {
                k: v for k, v in self._eligibility_traces.items()
                if v[1] > cutoff
            }
    
    def get_stats(self) -> Dict:
        """Get learning statistics."""
        spike_stats = self.spike_tracker.get_spike_stats()
        
        with QMutexLocker(self._mutex):
            return {
                'ltp_events': self._ltp_count,
                'ltd_events': self._ltd_count,
                'total_delta_magnitude': self._total_delta,
                'active_eligibility_traces': len(self._eligibility_traces),
                'spike_stats': spike_stats
            }
    
    def reset_stats(self):
        """Reset learning statistics."""
        with QMutexLocker(self._mutex):
            self._ltp_count = 0
            self._ltd_count = 0
            self._total_delta = 0.0
    
    def to_dict(self) -> Dict:
        """Serialize STDP learner state."""
        with QMutexLocker(self._mutex):
            return {
                'spike_tracker': self.spike_tracker.to_dict(),
                'eligibility_traces': {
                    f"{k[0]}|{k[1]}": {'trace': v[0], 'time': v[1]}
                    for k, v in self._eligibility_traces.items()
                },
                'stats': {
                    'ltp_count': self._ltp_count,
                    'ltd_count': self._ltd_count,
                    'total_delta': self._total_delta
                }
            }
    
    def from_dict(self, data: Dict):
        """Restore STDP learner state."""
        if 'spike_tracker' in data:
            self.spike_tracker.from_dict(data['spike_tracker'])
        
        with QMutexLocker(self._mutex):
            self._eligibility_traces.clear()
            for key_str, val in data.get('eligibility_traces', {}).items():
                parts = key_str.split('|')
                if len(parts) == 2:
                    self._eligibility_traces[(parts[0], parts[1])] = (val['trace'], val['time'])
            
            stats = data.get('stats', {})
            self._ltp_count = stats.get('ltp_count', 0)
            self._ltd_count = stats.get('ltd_count', 0)
            self._total_delta = stats.get('total_delta', 0.0)


# Convenience function for creating a configured STDP system
def create_stdp_learner(
    time_window_ms: float = 500,
    stdp_weight: float = 0.4,
    spike_threshold: float = 60.0
) -> STDPLearner:
    """
    Create an STDP learner with common configuration.
    
    Args:
        time_window_ms: Learning time window in milliseconds
        stdp_weight: Weight of STDP vs Hebbian (0-1)
        spike_threshold: Activation level to consider a spike
        
    Returns:
        Configured STDPLearner instance
    """
    config = STDPConfig(
        time_window=time_window_ms / 1000.0,
        tau_plus=time_window_ms / 3000.0,
        tau_minus=time_window_ms / 3000.0,
        stdp_weight=stdp_weight,
        spike_threshold=spike_threshold
    )
    return STDPLearner(config)
