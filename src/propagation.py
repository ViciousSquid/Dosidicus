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


# ---------------------------------------------------------------------------
# Neurons the world writes, rather than the synapses
# ---------------------------------------------------------------------------
# A sensor is written by the environment. An action-representation neuron -
# grown when the brain turns out to have no way of telling one of its own
# actions from another - is written by what the squid is currently doing.
# Neither is computed by the forward pass, and `propagate` must not be given
# them as targets: two writers on one neuron is exactly the class of bug this
# module exists to remove.
#
# Kept here, next to the transfer function, because "who writes what, each
# tick" is one question and it should have one answer.

ACTION_ACTIVE = 100.0
ACTION_RESTING = BASELINE


class ExternallyDriven:
    """Mixed into any brain that can grow action representations.

    Both the game's BrainWidget and the headless trainer inherit this, so an
    action the squid can represent in one is representable in the other.
    """

    #: action name -> the neuron that stands for it
    action_representations: Dict[str, str]
    #: every neuron written from outside the forward pass
    externally_driven: set

    def _external_maps(self):
        if not hasattr(self, 'action_representations') or \
                self.action_representations is None:
            self.action_representations = {}
        if not hasattr(self, 'externally_driven') or \
                self.externally_driven is None:
            self.externally_driven = set()
        return self.action_representations, self.externally_driven

    def represent_action(self, action: str, neuron: str) -> None:
        """Bind a neuron to one of the squid's own actions.

        The neuron now says "I am doing this" and nothing else. It asserts
        nothing about what the action causes - that is for plasticity to
        discover from what follows.
        """
        actions, external = self._external_maps()
        existing = actions.get(str(action))
        if existing and existing != str(neuron) and \
                existing in (getattr(self, 'neuron_positions', None) or {}):
            # This action already has a living representation. Rebinding it
            # would leave the old neuron in the network with nothing driving
            # it - an orphan the brain would then have to rescue.
            return
        actions[str(action)] = str(neuron)
        external.add(str(neuron))

    def forget_action_representation(self, neuron: str) -> None:
        """Drop a binding, e.g. when the neuron is pruned."""
        actions, external = self._external_maps()
        for action, name in list(actions.items()):
            if name == neuron:
                del actions[action]
        external.discard(neuron)

    def action_for_neuron(self, neuron: str) -> str:
        actions, _ = self._external_maps()
        for action, name in actions.items():
            if name == neuron:
                return action
        return ""

    def drive_external_neurons(self, smoothing: float = DEFAULT_SMOOTHING
                               ) -> Dict[str, float]:
        """Write the action neurons from what the squid is actually doing.

        Called once per tick, immediately before propagation, so the rest of
        the network sees the action the same way it sees a sensor: as a fact
        about the world it can learn from. Rising and falling through the same
        smoothing as everything else means the representation leaves a short
        trace after the action ends, which is what gives spike timing and the
        eligibility traces something to work with.
        """
        actions, _external = self._external_maps()
        if not actions:
            return {}
        causal = getattr(self, 'causal_learning', None)
        current = getattr(causal, 'current_action', "") if causal is not None else ""
        state = getattr(self, 'state', None)
        if state is None:
            return {}

        changed: Dict[str, float] = {}
        for action, neuron in actions.items():
            if neuron not in state:
                continue
            target = ACTION_ACTIVE if action == current else ACTION_RESTING
            old = activation_of(state.get(neuron, BASELINE))
            if old is None:
                old = BASELINE
            new = old + (target - old) * smoothing
            new = max(0.0, min(100.0, new))
            if abs(new - old) > 1e-9:
                changed[neuron] = new
            state[neuron] = new
        return changed
