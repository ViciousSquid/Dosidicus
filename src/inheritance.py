# File: inheritance.py
"""A hatchling inherits half its weights from each parent.

At mating, each parent contributes a gamete: a random half of its synapses
between the neurons every newborn has (brain_constants.newborn_neurons) -
none that it grew, because no grown neuron is inherited; a hatchling grows
its own. The resident's gamete is taken where it lives; the mate's is made on
the mate's own machine and sent to the host (plugins/multiplayer), the one
time a squid's weights ever cross the wire. Both are kept with the egg.

At hatch the newborn's innate wiring is overlaid with both halves. Where both
parents passed on the same synapse, one of them is chosen at random. A few
inherited weights mutate a little, which is how a lineage can drift. Every
inherited synapse goes through the brain's apply_weight_change with the
parent it came from and whether it mutated, so the Laboratory can say of any
synapse in a hatchling's brain: inherited from this parent, like this.

Qt-free: desktop and mobile share it.
"""

import math
import random
from typing import Any, Dict, List, Mapping, Optional, Tuple

from .brain_constants import newborn_neurons

#: The share of inherited weights that mutate, and how far each can move.
MUTATION_RATE = 0.1
MUTATION_SIZE = 0.1

#: No gamete may carry more than this many synapses - more than a newborn
#: brain can have between its own neurons.
MAX_GENES = 600

_SEP = '->'


def _key(src: str, dst: str) -> str:
    return f"{src}{_SEP}{dst}"


def _edge(key: str) -> Optional[Tuple[str, str]]:
    parts = str(key).split(_SEP)
    return (parts[0], parts[1]) if len(parts) == 2 else None


def gamete(weights: Mapping, rng: Optional[random.Random] = None) -> Dict[str, float]:
    """A random half of a brain's synapses between newborn neurons.

    {'src->dst': weight}, ready to be kept with an egg or sent to a host.
    """
    rng = rng or random
    innate = set(newborn_neurons())
    edges = sorted(edge for edge in weights
                   if isinstance(edge, tuple) and len(edge) == 2
                   and edge[0] in innate and edge[1] in innate)
    chosen = rng.sample(edges, len(edges) // 2) if edges else []
    return {_key(*edge): round(float(weights[edge]), 4) for edge in sorted(chosen)}


def clean_gamete(genes: Any) -> Dict[str, float]:
    """A gamete as anyone may send it, reduced to what it is allowed to be.

    Only synapses between newborn neurons, each weight within [-1, 1], at most
    MAX_GENES of them; anything else is dropped.
    """
    if not isinstance(genes, dict):
        return {}
    innate = set(newborn_neurons())
    clean = {}
    for key, value in list(genes.items())[:MAX_GENES]:
        edge = _edge(key)
        if (edge is None or edge[0] == edge[1] or edge[0] not in innate
                or edge[1] not in innate or isinstance(value, bool)
                or not isinstance(value, (int, float)) or not math.isfinite(value)):
            continue                 # NaN would otherwise clamp to +1
        clean[_key(*edge)] = max(-1.0, min(1.0, float(value)))
    return clean


def inherit(brain, gametes: Mapping[str, Mapping[str, float]],
            rng: Optional[random.Random] = None) -> List[Dict[str, Any]]:
    """Overlay a newborn brain with its parents' gametes.

    `gametes` is {parent's name: gamete}. Returns one record per inherited
    synapse: {'synapse', 'parent', 'weight', 'mutated'}.
    """
    rng = rng or random
    positions = getattr(brain, 'neuron_positions', None) or {}
    offered: Dict[str, List[Tuple[str, float]]] = {}
    for parent, genes in gametes.items():
        for key, weight in clean_gamete(genes).items():
            offered.setdefault(key, []).append((str(parent), weight))
    inherited = []
    for key in sorted(offered):
        src, dst = _edge(key)
        if src not in positions or dst not in positions:
            continue
        parent, weight = rng.choice(offered[key])
        mutated = rng.random() < MUTATION_RATE
        if mutated:
            weight = max(-1.0, min(1.0, weight + rng.uniform(-MUTATION_SIZE, MUTATION_SIZE)))
        detail = {'parent': parent, 'mutated': mutated,
                  'note': f"inherited from {parent}" + (", a little mutated" if mutated else "")}
        brain.apply_weight_change((src, dst), value=round(weight, 4),
                                  mechanism='inheritance', detail=detail, create=True)
        inherited.append({'synapse': (src, dst), 'parent': parent,
                          'weight': round(weight, 4), 'mutated': mutated})
    return inherited


__all__ = ['gamete', 'clean_gamete', 'inherit', 'MUTATION_RATE', 'MUTATION_SIZE',
           'MAX_GENES']
