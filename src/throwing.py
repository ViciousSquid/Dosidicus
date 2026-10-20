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
import random
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple


def _level(value) -> float:
    try:
        value = float(value)
        return max(0.0, min(100.0, value)) if math.isfinite(value) else 0.0
    except (TypeError, ValueError):
        return 0.0


def throw_or_drop(state: Dict[str, Any]) -> bool:
    """Throw if the squid's play neuron is firing; otherwise put the rock down."""
    from .decision_engine import select_action
    return select_action(state, jitter=False)[0] == 'playing'


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


def choose_target(origin: Sequence[float], targets: Iterable[Sequence[Any]]):
    """Which squid in view to go at: (name, x, y, why), or None.

    `targets` are (name, x, y) of the squid in view, or (name, x, y,
    recalled_bad) where recalled_bad (0-100) is how badly THIS squid
    remembers that one, from its own memory (PeerLedger). One it remembers
    badly is gone at before any it does not - the worst remembered first, the
    nearest among equals; with none remembered badly, simply the nearest.
    """
    ox, oy = float(origin[0]), float(origin[1])
    seen = [(t[0], float(t[1]), float(t[2]), max(0.0, float(t[3]) if len(t) > 3 else 0.0))
            for t in targets]
    if not seen:
        return None
    name, tx, ty, bad = min(seen, key=lambda t: (-t[3], math.hypot(t[1] - ox, t[2] - oy)))
    why = ({'chosen_because': 'remembered badly', 'recalled_bad': round(bad, 1)} if bad > 0
           else {'chosen_because': 'nearest'})
    return name, tx, ty, why


def aim(origin: Sequence[float], gaze: float,
        targets: Iterable[Sequence[Any]], speed: float,
        gravity: float, drag: float = 0.0) -> Tuple[float, Optional[str], Dict[str, Any]]:
    """The angle to throw at (screen coordinates, y down), the target, and why.

    `targets` are the squid in this squid's view cone (choose_target). With
    one, it aims at the one it remembers worst, or else the nearest, raised by
    the drop the rock will take on the way (steps to get there, slowed by
    drag; drop = gravity t^2 / 2).
    """
    ox, oy = origin
    chosen = choose_target(origin, targets)
    if chosen is None or speed <= 0:
        return gaze, None, {'aimed_at': None, 'along': 'its gaze'}
    name, tx, ty, why = chosen
    distance = math.hypot(tx - ox, ty - oy)
    steps = flight_steps(distance, speed, drag)
    drop = 0.5 * gravity * steps * steps
    angle = math.atan2((ty - drop) - oy, tx - ox)
    return angle, name, {'aimed_at': name, 'distance': round(distance, 1),
                         'lead_for_drop': round(drop, 1), 'target_at': (tx, ty), **why}


def recalled_bad(memory_manager, peer_uuid: str) -> float:
    """How badly a squid remembers another, 0-100, from its own memory."""
    if memory_manager is None or not peer_uuid:
        return 0.0
    try:
        from plugins.multiplayer.peer_ledger import PeerLedger
        return float(PeerLedger(memory_manager).recalled_bad(str(peer_uuid)))
    except Exception:
        return 0.0


#: A thrown thing passing this close to a squid's centre strikes it.
REACH_RADIUS = 45.0


def reaches(origin: Sequence[float], target: Sequence[float], vx: float, vy: float,
            gravity: float, bounds: Optional[Sequence[float]] = None,
            radius: float = REACH_RADIUS, steps: int = 400) -> bool:
    """Would a throw with this velocity get to the target? Flown under the
    same physics as the real throw (flight_step), landing included - how the
    squid's eyes judge how far it can throw."""
    position, velocity = (float(origin[0]), float(origin[1])), (float(vx), float(vy))
    bounds = bounds or (-1e9, 1e9, -1e9, 1e9)
    for _ in range(steps):
        end, velocity, landed = flight_step(position, velocity, bounds, gravity=gravity)
        if swept_hit(position, end, target, radius) is not None:
            return True
        if landed or velocity == (0.0, 0.0):
            return False
        position = end
    return False


#: Motor noise. A throw leaves the tentacles a little off the line the squid
#: aims along and a little off the strength its network put in - widely for a
#: novice, narrowing with practice (every rock and poop it has thrown) but
#: never to nothing, so a throw does not always land. The body's, not a
#: decision: whether and how hard to throw stay its network's.
NOVICE_ANGLE_SD, SKILLED_ANGLE_SD = 9.0, 1.5      # degrees off the line
NOVICE_SPEED_SD, SKILLED_SPEED_SD = 0.13, 0.02    # fraction of the strength
#: Throws of practice that close half the gap from novice to skilled.
PRACTICE_SCALE = 12.0


def skill(practice: float) -> float:
    """0 for a squid that has never thrown, rising towards 1 with practice."""
    practice = max(0.0, float(practice or 0.0))
    return practice / (practice + PRACTICE_SCALE)


def spread(practice: float) -> Tuple[float, float]:
    """(degrees, fraction): how far its throws stray, at this much practice."""
    rough = 1.0 - skill(practice)
    return (SKILLED_ANGLE_SD + (NOVICE_ANGLE_SD - SKILLED_ANGLE_SD) * rough,
            SKILLED_SPEED_SD + (NOVICE_SPEED_SD - SKILLED_SPEED_SD) * rough)


def practice_of(*records: Any) -> int:
    """Throws made, from a squid's own statistics (desktop: rocks and poop;
    mobile: rocks). Each record counted once, however it is reached."""
    distinct = {id(record): record for record in records if record is not None}
    return int(sum(float(getattr(record, field, 0) or 0) for record in distinct.values()
                   for field in ('total_rocks_thrown', 'total_poops_thrown', 'rocks_thrown')))


def release(plan: Dict[str, Any], practice: float, rng=None) -> Dict[str, Any]:
    """Let go: the aimed velocity, strayed by motor noise for this practice.
    Records how far it strayed ('aim_error', degrees; 'strength_error')."""
    rng = rng or random
    angle_sd, speed_sd = spread(practice)
    off = rng.gauss(0.0, angle_sd)
    strength = max(0.5, 1.0 + rng.gauss(0.0, speed_sd))
    angle = math.atan2(plan['vy'], plan['vx']) + math.radians(off)
    speed = math.hypot(plan['vx'], plan['vy']) * strength
    plan.update(vx=speed * math.cos(angle), vy=speed * math.sin(angle),
                aim_error=round(off, 1), strength_error=round(strength - 1.0, 3),
                practice=int(practice), skill=round(skill(practice), 2))
    return plan


def plan_throw(state: Dict[str, Any], origin: Sequence[float], gaze: float,
               targets: Iterable[Tuple[str, float, float]], *, slowest: float,
               fastest: float, gravity: float, drag: float = 0.0,
               bounds: Optional[Sequence[float]] = None,
               practice: Optional[float] = None, rng=None) -> Dict[str, Any]:
    """Everything about one throw: velocity, and the reasons for it.

    With a squid to aim at, also whether the throw would reach it
    ('reaches'): the network decides whether and how hard; whether that is
    far enough is what the squid sees - judged on the throw it means to make.
    With `practice`, the throw it actually makes strays from that (release):
    it does not always land, and lands more often the more it has thrown.
    """
    speed, why_speed = throw_speed(state, slowest, fastest)
    angle, target, why_aim = aim(origin, gaze, targets, speed, gravity, drag)
    plan = {'vx': speed * math.cos(angle), 'vy': speed * math.sin(angle),
            'angle': round(math.degrees(angle), 1), 'target': target,
            **why_speed, **why_aim}
    if target is not None:
        plan['reaches'] = reaches(origin, why_aim['target_at'], plan['vx'], plan['vy'],
                                  gravity, bounds)
    if practice is not None:
        release(plan, practice, rng)
    return plan


def out_of_reach(plan: Dict[str, Any]) -> bool:
    """A squid to aim at that this throw would not get to: close in first."""
    return plan.get('target') is not None and plan.get('reaches') is False


def describe(plan: Dict[str, Any]) -> str:
    """One line: what, at whom, how hard, and why that hard."""
    at = f"at {plan['aimed_at']}" if plan.get('aimed_at') else 'where it was looking'
    if plan.get('chosen_because') == 'remembered badly':
        at += ', whom it remembers badly'
    thing = 'poop' if plan.get('what') == 'poop' else 'a rock'
    return (f"Threw {thing} {at}, {('hard' if plan.get('drive', 0) >= 70 else 'gently')} - "
            f"{plan.get('driven_by', 'act_play')} at {plan.get('drive', 0):.0f}")


#: What a thrown thing does to the squid it strikes - felt, never explained:
#: the thrower's reasons never reach it. A rock knocks (health) and startles,
#: and might have been play. Poop does no harm, but it is not a rock: nobody
#: takes being splattered kindly - it is dirtied (cleanliness down), anxiety
#: up, happiness down, and it counts as the worse mark in the encounter
#: (encounter.EncounterSession._measure).
HIT_EFFECTS = {
    'rock': {'health': -2.0, 'startle': True},
    'poop': {'cleanliness': -20.0, 'anxiety': 15.0, 'happiness': -10.0},
}


def feel_hit(squid, what: str = 'rock', startle=None) -> Dict[str, float]:
    """A strike, on the struck squid's body and drives. Returns what changed.

    `startle(source)` is called for a strike that startles. Shared by the
    resident at home, a visitor at home and mobile, so a strike is the same
    thing wherever it lands.
    """
    effects = HIT_EFFECTS.get(what, HIT_EFFECTS['rock'])
    changed = {}
    for stat in ('health', 'cleanliness', 'anxiety', 'happiness'):
        if stat not in effects or not isinstance(getattr(squid, stat, None), (int, float)):
            continue
        before = float(getattr(squid, stat))
        after = max(0.0, min(100.0, before + effects[stat]))
        setattr(squid, stat, after)
        changed[stat] = round(after - before, 2)
    if effects.get('startle') and callable(startle):
        startle(f'{what}_hit')
    return changed


def swept_hit(start, end, centre, radius):
    """First contact along a segment, including overlap and tangency.

    Return a fraction of the segment or None. Checking the whole path avoids
    tunnelling at high speeds and lets callers choose the first body struck.
    """
    dx, dy = end[0] - start[0], end[1] - start[1]
    ox, oy = start[0] - centre[0], start[1] - centre[1]
    c = ox * ox + oy * oy - radius * radius
    if c <= 0:
        return 0.0
    a = dx * dx + dy * dy
    if a <= 1e-12:
        return None
    b = ox * dx + oy * dy
    disc = b * b - a * c
    if disc < 0:
        return None
    t = (-b - math.sqrt(disc)) / a
    return t if 0 <= t <= 1 else None


def flight_step(position, velocity, bounds, dt=1.0, gravity=0.3):
    """One physical step, clipped at the first tank boundary.

    Coordinates are rock centres, bounds are left/right/top/floor. Return
    (end, velocity, landed). The clipped path must be checked for hits BEFORE
    discarding a landed projectile. Speeds and dt use 50 ms units on both
    platforms; callers subdivide longer frames.
    """
    x, y = position
    vx, vy = velocity
    left, right, top, floor = bounds
    # A release near the floor starts within the physical tank.
    x, y = max(left, min(right, x)), max(top, min(floor, y))
    dx, dy = vx * dt, vy * dt
    contacts = [(1.0, '')]
    if dx < 0 and x + dx <= left:
        contacts.append(((left - x) / dx, 'wall'))
    elif dx > 0 and x + dx >= right:
        contacts.append(((right - x) / dx, 'wall'))
    if dy < 0 and y + dy <= top:
        contacts.append(((top - y) / dy, 'top'))
    elif dy >= 0 and y + dy >= floor:
        contacts.append(((floor - y) / dy if dy else 0.0, 'floor'))
    fraction, contact = min(contacts, key=lambda c: (c[0], not bool(c[1])))
    end = (x + dx * fraction, y + dy * fraction)
    vx *= 0.98 ** dt
    vy += gravity * dt
    if contact == 'floor':
        return end, (0.0, 0.0), True
    if contact == 'wall':
        vx *= -0.2
    elif contact == 'top':
        vy = abs(vy) * 0.2
    return end, (vx, vy), False


__all__ = ['throw_or_drop', 'throw_drive', 'throw_speed', 'flight_steps', 'aim',
           'plan_throw', 'describe', 'swept_hit', 'flight_step', 'HIT_EFFECTS', 'feel_hit',
           'REACH_RADIUS', 'reaches', 'out_of_reach', 'skill', 'spread', 'practice_of',
           'release']
