# File: throwing.py
"""A thrown rock goes where the squid is looking, as hard as its network throws it.

Whether to throw at all is the squid's network's: its play neuron firing
(throw_or_drop). How:

  AIM - at what the squid is attending to: the nearest other squid in its
  view cone, if there is one, leading for the drop the rock will take; else
  straight along its gaze.

  SPEED - from the strength of what drives the throw: its play neuron, or its
  grown aggression neuron if that is the stronger. A half-hearted toss lobs;
  a fully aggro squid hurls.

Nothing about why goes with the rock. A squid struck by one, or one that sees
one land beside it, only feels it - a startle, a knock - and its own network
decides what that means: the thrower might have been playing, or attacking,
and it cannot know which.

Every throw returns its reasons (aimed at whom, how hard, driven by what), so
it can be remembered and shown. Qt-free: desktop and mobile share it; speeds
are in the caller's units (desktop: pixels per 50 ms step).
"""

import math
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple


def _level(value) -> float:
    try:
        return max(0.0, min(100.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def throw_or_drop(state: Dict[str, Any]) -> bool:
    """Throw if the squid's play neuron is firing; otherwise put the rock down."""
    from .decision_engine import wants
    return bool(wants('act_play', _level(state.get('act_play', 0.0))))


def throw_drive(state: Dict[str, Any]) -> Tuple[float, str]:
    """How hard the network is throwing, 0-100, and which neuron drives it."""
    play = _level(state.get('act_play', 0.0))
    aggro = _level(state['aggression']) if 'aggression' in state else 0.0
    return (aggro, 'aggression') if aggro > play else (play, 'act_play')


def throw_speed(state: Dict[str, Any], slowest: float, fastest: float) -> Tuple[float, Dict[str, Any]]:
    drive, by = throw_drive(state)
    speed = slowest + (fastest - slowest) * drive / 100.0
    return speed, {'drive': round(drive, 1), 'driven_by': by, 'speed': round(speed, 2)}


def flight_steps(distance: float, speed: float, drag: float = 0.0) -> float:
    """Steps for a rock thrown at `speed` to cover `distance`, slowed by
    `drag` per step. Out of reach, as long as it flies before it stalls."""
    if drag <= 0.0:
        return distance / speed
    keep = 1.0 - drag
    reach = distance * drag / speed
    if reach >= 0.95:
        return math.log(0.05) / math.log(keep)
    return math.log(1.0 - reach) / math.log(keep)


def aim(origin: Sequence[float], gaze: float,
        targets: Iterable[Tuple[str, float, float]], speed: float,
        gravity: float, drag: float = 0.0) -> Tuple[float, Optional[str], Dict[str, Any]]:
    """The angle to throw at (screen coordinates, y down), the target, and why.

    `targets` are (name, x, y) of the squid in this squid's view cone. With
    one, it aims at the nearest, raised by the drop the rock will take on the
    way (steps to get there, slowed by drag; drop = gravity t^2 / 2).
    """
    ox, oy = origin
    seen = sorted(targets, key=lambda t: math.hypot(t[1] - ox, t[2] - oy))
    if not seen or speed <= 0:
        return gaze, None, {'aimed_at': None, 'along': 'its gaze'}
    name, tx, ty = seen[0]
    distance = math.hypot(tx - ox, ty - oy)
    steps = flight_steps(distance, speed, drag)
    drop = 0.5 * gravity * steps * steps
    angle = math.atan2((ty - drop) - oy, tx - ox)
    return angle, name, {'aimed_at': name, 'distance': round(distance, 1),
                         'lead_for_drop': round(drop, 1)}


def plan_throw(state: Dict[str, Any], origin: Sequence[float], gaze: float,
               targets: Iterable[Tuple[str, float, float]], *, slowest: float,
               fastest: float, gravity: float, drag: float = 0.0) -> Dict[str, Any]:
    """Everything about one throw: velocity, and the reasons for it."""
    speed, why_speed = throw_speed(state, slowest, fastest)
    angle, target, why_aim = aim(origin, gaze, targets, speed, gravity, drag)
    return {'vx': speed * math.cos(angle), 'vy': speed * math.sin(angle),
            'angle': round(math.degrees(angle), 1), 'target': target,
            **why_speed, **why_aim}


def describe(plan: Dict[str, Any]) -> str:
    """One line: at whom, how hard, and why that hard."""
    at = f"at {plan['aimed_at']}" if plan.get('aimed_at') else 'where it was looking'
    return (f"Threw a rock {at}, {('hard' if plan.get('drive', 0) >= 70 else 'gently')} - "
            f"{plan.get('driven_by', 'act_play')} at {plan.get('drive', 0):.0f}")


__all__ = ['throw_or_drop', 'throw_drive', 'throw_speed', 'flight_steps', 'aim',
           'plan_throw', 'describe']
