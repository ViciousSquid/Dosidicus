"""
propagation.py - the project's single forward-propagation implementation.

There is one transfer function in Dosidicus and this is it. Everything that
steps a network - the game's BrainWidget, the headless trainer, a test - calls
`propagate` here, so a brain trained in one place behaves identically in the
other. Previously the game, the worker thread, the neurogenesis engine and the
headless trainer each had their own version, differing in baseline, decay,
clamp range and timestep, which meant a brain exported from the trainer did not
do the same thing when the squid ran it.

The rule
--------
    target = 50 + sum((activation[src] - 50) * weight) * strength
    new    = old + (target - old) * smoothing         clamped to 0..100

50 is the neutral baseline, so a silent input contributes nothing and a
negative weight is genuinely inhibitory. `strength` is the per-neuron
multiplier a grown neuron accumulates when neurogenesis strengthens it rather
than duplicating it.

Contract
--------
* Reads   : state (activations), weights (synapses)
* Writes  : state, for the named targets only
* Never   : touches a neuron the caller did not list as a target - sensors are
            owned by the world and core drives by the squid model.
"""

from __future__ import annotations

import random
from typing import Dict, Iterable, Mapping, Optional, Tuple

Pair = Tuple[str, str]

BASELINE = 50.0
DEFAULT_SMOOTHING = 0.5


def activation_of(raw) -> Optional[float]:
    """Coerce a stored neuron value to the 0-100 activation scale."""
    if isinstance(raw, bool):
        return 100.0 if raw else 0.0
    if isinstance(raw, (int, float)):
        return float(raw)
    return None


def propagate(state: Dict[str, object],
              weights: Mapping[Pair, float],
              targets: Iterable[str],
              strengths: Optional[Mapping[str, float]] = None,
              noise: Optional[Mapping[str, float]] = None,
              smoothing: float = DEFAULT_SMOOTHING) -> Dict[str, float]:
    """Compute one timestep for every target neuron, in place.

    Returns the neurons whose activation actually changed.
    """
    targets = [t for t in targets]
    if not targets:
        return {}
    target_set = set(targets)
    strengths = strengths or {}
    noise = noise or {}

    # 1. Sum weighted input from a single consistent snapshot, so all neurons
    #    step together rather than the result depending on dict order.
    net_input = {name: 0.0 for name in targets}
    for edge, weight in weights.items():
        if not (isinstance(edge, tuple) and len(edge) == 2):
            continue
        src, dst = edge
        if dst not in target_set:
            continue
        src_val = activation_of(state.get(src))
        if src_val is None:
            continue
        net_input[dst] += (src_val - BASELINE) * float(weight)

    # 2. Transfer function + per-neuron strength multiplier.
    changed: Dict[str, float] = {}
    for name in targets:
        strength = float(strengths.get(name, 1.0) or 1.0)
        target_val = BASELINE + net_input[name] * strength

        jitter = float(noise.get(name, 0.0) or 0.0)
        if jitter:
            target_val += random.uniform(-jitter, jitter)

        old = activation_of(state.get(name, BASELINE))
        if old is None:
            old = BASELINE

        new_val = old + (target_val - old) * smoothing
        new_val = max(0.0, min(100.0, new_val))

        if abs(new_val - old) > 1e-9:
            changed[name] = new_val
        state[name] = new_val

    return changed
