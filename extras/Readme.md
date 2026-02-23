#### Spike-Timing-Dependent Plasticity (STDP)
https://en.wikipedia.org/wiki/Spike-timing-dependent_plasticity

Adds *temporal causality* to learning, enabling the squid to learn cause-and-effect relationships rather than just correlations.

```
NOTE: As of v2.6.1.2 STDP is NOT currently implemented due to being beyond the (current) needs for this project
Here's a guide for forkers/cloners/contributors anyway x
```

Everything needed to implement can be found in [STDP.zip](https://github.com/ViciousSquid/Dosidicus/blob/v2.6.1.0__b1218_LatestVersion/extras/STDP.zip) IN THIS FOLDER

-----------------------------------

## What is STDP?

In biological neurons, the timing of action potentials (spikes) relative to each other determines whether synaptic connections strengthen or weaken:

```
Pre-synaptic neuron fires BEFORE post-synaptic neuron
→ Connection STRENGTHENS (Long-Term Potentiation / LTP)
→ "This input helped cause the output"

Post-synaptic neuron fires BEFORE pre-synaptic neuron  
→ Connection WEAKENS (Long-Term Depression / LTD)
→ "Correlation without causation"
```

This is fundamentally different from classical Hebbian learning (current implementation), which only considers whether neurons are simultaneously active.

### Why STDP Matters for Dosidicus-2

Your squid simulation involves **behavioral sequences**:

1. See food → Pursue food → Eat food → Feel satisfied
2. Feel anxious → Flee → Reach safety → Calm down
3. Get dirty → Feel uncomfortable → Get cleaned → Feel happy

With pure Hebbian learning, all neurons active during these sequences get connected bidirectionally. With STDP, the connections encode **direction**:

- `can_see_food` → `pursuing_food` (seeing food *causes* pursuit)
- `pursuing_food` → `satisfaction` (pursuit *leads to* satisfaction)

This creates a predictive network where early signals can anticipate later outcomes.

## Implementation Components

### 1. SpikeTracker

Monitors neuron activations and detects "spikes" - moments when activation crosses a threshold.

```python
# A spike is detected when:
# 1. Activation crosses above spike_threshold (default: 60)
# 2. Activation was rising (not just staying high)  
# 3. Sufficient time since last spike (refractory period)

spike_tracker.record_activation("hunger", 75.0)
```

**Key Parameters:**
- `spike_threshold`: Activation level to trigger spike (default: 60)
- `spike_rising_threshold`: Minimum activation increase (default: 8)
- `refractory_period`: Minimum time between spikes (default: 0.08s)

### 2. STDPLearner

Computes weight changes based on spike timing.

```python
# If "hunger" spiked 100ms before "pursuing_food":
delta = stdp_learner.compute_stdp_delta("hunger", "pursuing_food")
# Returns positive value (LTP) - strengthen this connection

# If "satisfaction" spiked before "hunger":
delta = stdp_learner.compute_stdp_delta("satisfaction", "hunger")  
# Returns negative value (LTD) - weaken this connection
```

**The STDP Curve:**

```
Weight Change (Δw)
      ^
  LTP |    ****
      |   *    *
      |  *      *
------+--*--------*----------------→ Time Difference (Δt)
      | *          *
  LTD |*            *****
      |
      
      Pre fires    Post fires
      first        first
```

### 3. Combined Learning

STDP is integrated with existing Hebbian learning via a weighted combination:

```python
combined_delta = (1 - stdp_weight) * hebbian_delta + stdp_weight * stdp_delta
```

Default `stdp_weight = 0.4` means:
- 60% contribution from rate-based Hebbian
- 40% contribution from timing-based STDP

### 4. Eligibility Traces

For delayed reward learning (three-factor learning):

```python
# Squid sees food, pursues it, eats it...
# Connection spike timing is tracked as "eligibility"

# Later, when satisfaction increases:
brain_widget.apply_reward_signal(0.5)
# All recently-active connections with eligibility traces are modulated
```

This allows the squid to learn from outcomes that happen slightly after the causal actions.

## Files Structure

```
├── stdp.py                         # Core STDP module
│   ├── STDPConfig                  # Configuration dataclass
│   ├── SpikeEvent                  # Single spike record
│   ├── SpikeTracker               # Tracks neuron spikes  
│   └── STDPLearner                # Main learning engine
│
├── brain_worker_stdp.py           # Updated BrainWorker with STDP
│   └── BrainWorker                # Background thread with STDP integration
│
└── brain_widget_stdp_integration.py # Integration guide for brain_widget.py
```

## Configuration Guide

### STDPConfig Parameters

| Parameter | Default | Description | Tuning Notes |
|-----------|---------|-------------|--------------|
| `tau_plus` | 0.15 | LTP time constant (seconds) | Larger = wider learning window |
| `tau_minus` | 0.15 | LTD time constant (seconds) | Usually same as tau_plus |
| `A_plus` | 0.08 | LTP amplitude | Larger = stronger potentiation |
| `A_minus` | 0.05 | LTD amplitude | Usually smaller than A_plus for stability |
| `time_window` | 0.5 | Max timing difference (seconds) | Game timescale, not biological |
| `spike_threshold` | 60.0 | Activation to trigger spike | Lower = more spikes, more learning |
| `stdp_weight` | 0.4 | STDP vs Hebbian balance | 0 = pure Hebbian, 1 = pure STDP |
| `burst_bonus` | 1.5 | Multiplier for burst activity | Rewards sustained activation |

### Recommended Starting Configuration

For Dosidicus-2's game timescale:

```python
config = STDPConfig(
    # Time constants scaled for game speed (not milliseconds)
    tau_plus=0.15,      # 150ms
    tau_minus=0.15,
    
    # Conservative learning amplitudes
    A_plus=0.08,
    A_minus=0.05,       # Asymmetric for stability
    
    # Wide window for game-speed events  
    time_window=0.5,    # 500ms
    
    # Spike detection
    spike_threshold=60.0,
    refractory_period=0.08,
    
    # Balanced with Hebbian
    stdp_weight=0.4,    # 40% STDP, 60% Hebbian
)
```

### Tuning for Different Behaviors

**For faster learning (more responsive squid):**
```python
config.A_plus = 0.12
config.A_minus = 0.08
config.stdp_weight = 0.6
```

**For more stable learning (less volatile weights):**
```python
config.A_plus = 0.05
config.A_minus = 0.03
config.stdp_weight = 0.3
```

**For longer causal chains:**
```python
config.time_window = 1.0       # 1 second window
config.tau_plus = 0.3
config.tau_minus = 0.3
config.eligibility_window = 3.0  # 3 second trace
```

## Integration Points

### 1. State Updates (High Frequency)

Every time neuron state changes, spikes should be recorded:

```python
# In brain_widget.update_state():
self._update_worker_cache()  # This triggers spike recording
```

### 2. Learning Cycles (Every 30 seconds)

The existing Hebbian learning cycle now computes combined STDP+Hebbian:

```python
# In BrainWorker._perform_hebbian_learning():
combined_delta, metadata = self.stdp_learner.compute_combined_learning(
    n1, n2, v1, v2,
    base_learning_rate=lr
)
```

### 3. Behavioral Outcomes (Event-Driven)

When significant events happen, apply reward signals:

```python
# Positive outcomes
brain_widget.apply_reward_signal(0.5)   # Ate food successfully
brain_widget.apply_reward_signal(0.3)   # Escaped danger
brain_widget.apply_reward_signal(0.2)   # Environment cleaned

# Negative outcomes  
brain_widget.apply_reward_signal(-0.3)  # Got sick
brain_widget.apply_reward_signal(-0.2)  # Hunger critical
```

## Expected Behaviors

### Before STDP

With pure Hebbian learning:
- Neurons active together form bidirectional connections
- Network learns correlations, not causation
- Prediction is limited

### After STDP

With STDP enabled:
- Connections encode temporal order (A→B vs B→A)
- Causal chains emerge (see food → pursue → eat → satisfy)
- Earlier neurons can "predict" later outcomes
- Stress neurons connect to anxiety in the right direction
- Reward neurons strengthen successful behavior sequences

### Observable Changes

1. **Asymmetric weight development**: `hunger → pursuing_food` becomes stronger than `pursuing_food → hunger`

2. **Predictive activation**: Neurons earlier in behavioral chains will activate neurons later in the chain

3. **Directional animations**: Visual pulses travel in the learned direction during Hebbian learning cycles

4. **LTP/LTD balance**: Stats will show both potentiation and depression events

## Debugging

### Check STDP Statistics

```python
stats = brain_widget.get_stdp_stats()
print(f"LTP events: {stats['ltp_events']}")
print(f"LTD events: {stats['ltd_events']}")  
print(f"Active spikes: {stats['spike_stats']['total_spikes']}")
```

### Visualize Spike Activity

The `stdp_event` signal emits spike detections:

```python
def debug_spikes(event):
    if event['type'] == 'spike':
        print(f"🔥 {event['neuron']} spiked at {event['activation']:.1f}")

brain_worker.stdp_event.connect(debug_spikes)
```

### Common Issues

**No STDP learning happening:**
- Check `stdp_enabled` is True
- Verify neurons are crossing `spike_threshold`
- Ensure `spike_rising_threshold` isn't too high

**Too much LTD (weights decreasing):**
- Lower `A_minus` 
- Increase `spike_threshold` (fewer spurious spikes)
- Check for reversed causal relationships in game logic

**Unstable weights:**
- Lower both `A_plus` and `A_minus`
- Increase weight decay
- Reduce `stdp_weight` (more Hebbian stabilization)

## Future Enhancements

Potential additions to the STDP system:

1. **Triplet STDP**: Consider triplets of spikes for more biological accuracy
2. **Homeostatic plasticity**: Automatic threshold adjustment to maintain activity levels
3. **Metaplasticity**: Learning rate that depends on recent activity history
4. **Dendritic compartments**: Different learning rules for different "parts" of a neuron
5. **Dopamine modulation**: More sophisticated reward signal integration

## References

- Bi, G. Q., & Poo, M. M. (1998). Synaptic modifications in cultured hippocampal neurons.
- Song, S., Miller, K. D., & Abbott, L. F. (2000). Competitive Hebbian learning through spike-timing-dependent synaptic plasticity.
- Izhikevich, E. M. (2007). Solving the distal reward problem through linkage of STDP and dopamine signaling.


