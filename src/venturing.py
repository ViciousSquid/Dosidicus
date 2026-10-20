# File: venturing.py
"""When a squid leaves its tank to visit another: its own network's decision.

Enabling multiplayer only makes it possible. A squid knows another aquarium
is nearby through a sense it grows the first time one is heard on the network
(aquarium_nearby, wired by temperament - neurogenesis.VENTURING_TEMPERAMENT -
and moved by every encounter after). It ventures out while, together:

  * that sense reports another aquarium,
  * its exploring neuron (act_move) is firing, and
  * the sense is pushing that exploring up - its synapse onto act_move is
    excitatory, so news of the other aquarium is part of why it explores.

Then it swims for the nearest side of the tank and, on reaching it, leaves.
Not while fleeing, chasing food or merely drifting with nothing firing; and a
squid whose aquarium sense inhibits its exploring - born timid, or taught by
bad encounters - stays home. Otherwise the edges of the tank stop it, as they
do with multiplayer off. Qt-free.
"""

from typing import Any, Dict, Optional, Tuple

from .brain_constants import AQUARIUM_SENSE

#: The motor neuron for exploring.
EXPLORE = 'act_move'

#: How long after a peer's heartbeat its aquarium still counts as nearby.
#: Heartbeats come every few seconds; a peer silent for longer has gone.
HEARD_WITHIN = 30.0


def _level(state: Dict[str, Any], name: str) -> float:
    try:
        return float((state or {}).get(name, 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def why_not(state: Dict[str, Any], weights: Dict, *, fleeing: bool = False,
            chasing_food: bool = False, can_visit: bool = True) -> Optional[str]:
    """None if the squid's network is taking it out; else what is not."""
    from .decision_engine import wants
    if not can_visit:
        return 'it cannot visit'
    if _level(state, AQUARIUM_SENSE) <= 0.0:
        return 'it senses no other aquarium'
    if fleeing:
        return 'it is fleeing'
    if chasing_food:
        return 'it is chasing food'
    if not wants(EXPLORE, _level(state, EXPLORE)):
        return 'it is not exploring'
    if float((weights or {}).get((AQUARIUM_SENSE, EXPLORE), 0.0) or 0.0) <= 0.0:
        return 'the other aquarium does not draw it'
    return None


def venturing(state: Dict[str, Any], weights: Dict, **conditions) -> bool:
    return why_not(state, weights, **conditions) is None


def way_out(x: float, y: float, width: float, height: float,
            tank_width: float) -> Tuple[str, Tuple[float, float]]:
    """The nearest side of the tank, and a point just beyond it to swim at."""
    cy = y + height / 2.0
    if x + width / 2.0 <= tank_width / 2.0:
        return 'left', (-width, cy)
    return 'right', (tank_width + width, cy)


def peer_heard(last_heard: Dict[str, float], now: float) -> float:
    """The aquarium percept: 100 while some peer was heard within HEARD_WITHIN."""
    return 100.0 if any(now - at <= HEARD_WITHIN for at in (last_heard or {}).values()) else 0.0


__all__ = ['EXPLORE', 'HEARD_WITHIN', 'why_not', 'venturing', 'way_out', 'peer_heard']
