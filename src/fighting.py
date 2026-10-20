# File: fighting.py
"""A fight between two squid: whether one starts, and who wins it.

Two different things, kept apart on purpose. A squid that is quick to start
fights is not thereby good at them: an aggressive squid can fight often and
lose often, and a timid one that rarely fights can be formidable when it is
attacked.

  PREDISPOSITION (fight_predisposition) - the squid's own `aggression`
  neuron, which neurogenesis grows the first time its network goes at
  another squid while alarmed. It reads 0 when the squid is placid and
  relaxed and 100 when it is fully aggro. A squid that has never grown one
  can be attacked but cannot start a fight; one that has starts a fight when
  it is in contact with another squid and is more aggro than not. Personality only
  shows here through how the squid's network has been wired and has learned.

  ABILITY (fighting_ability) - worked out when the fight happens, from things
  aggression does not touch: the squid's body (health, hunger, tiredness,
  sickness), its experience (fights fought and won), and how hard its
  network commits to this fight - an attacker with its aggression, a
  defender with its alarm (or its social_fight neuron, once it knows how to
  fight), which is how a cornered timid squid can win.

  RESOLUTION (resolve_fight) - the better squid usually wins; there is a
  little luck in it, as in any scuffle, but it is not a coin flip.

Every function returns its reasons with its number, so a fight can always
say why it started and why it ended as it did. Qt-free: the desktop host and
the mobile game use the same rules.
"""

import random
from typing import Any, Callable, Dict, Optional, Tuple

#: Aggression at which a squid in contact with another starts a fight: more
#: aggro than placid.
AGGRESSION_THRESHOLD = 50.0

#: How sharply ability decides the outcome: 1 would make a squid twice as able
#: win two times in three; 2 makes it four times in five.
ABILITY_SHARPNESS = 2.0


def _level(value, default: float = 0.0) -> float:
    try:
        return max(0.0, min(100.0, float(value)))
    except (TypeError, ValueError):
        return default


def _above_rest(value, rest: float = 50.0) -> float:
    """How far above its resting midpoint a neuron is, on 0-100."""
    return max(0.0, min(100.0, (_level(value, rest) - rest) * 100.0 / (100.0 - rest)))


def fight_predisposition(state: Dict[str, Any]) -> Tuple[float, Dict[str, float]]:
    """How strongly this squid's network drives it to attack, 0-100, and why.

    Its grown `aggression` neuron: 0 placid and relaxed, 100 fully aggro -
    and 0 if it has never grown one. A squid that swims up to another out of
    curiosity is playing, and an alarmed squid with no aggression neuron is
    frightened, not fighting.
    """
    grown = 'aggression' in state
    value = _level(state['aggression']) if grown else 0.0
    return round(value, 1), {'aggression': round(value, 1), 'grown': grown,
                             'alarm': round(_above_rest(state.get('anxiety', 50.0)), 1)}


def fitness(*, health=100.0, hunger=0.0, sleepiness=0.0, sick=False,
            fights_won=0, fights_lost=0) -> Tuple[float, Dict[str, float]]:
    """Body and experience: what a squid brings to a fight before it starts.

    1.0 is a healthy, fed, rested squid that has never fought. Hunger and
    tiredness past the midpoint cost up to half each, sickness costs 40%;
    every fight fought (up to ten) teaches a little, every one won a little
    more.
    """
    body = (_level(health, 100.0) / 100.0
            * (1.0 - 0.5 * max(0.0, _level(hunger) - 50.0) / 50.0)
            * (1.0 - 0.5 * max(0.0, _level(sleepiness) - 50.0) / 50.0)
            * (0.6 if sick else 1.0))
    fought = min(10, int(fights_won or 0) + int(fights_lost or 0))
    experience = 1.0 + 0.06 * fought + 0.04 * min(10, int(fights_won or 0))
    return round(body * experience, 3), {'body': round(body, 3),
                                         'experience': round(experience, 3)}


def commitment(state: Dict[str, Any], attacking: bool) -> Tuple[float, str]:
    """How hard this squid's network throws itself into this fight, 0-100."""
    if attacking:
        return fight_predisposition(state)[0], 'aggression'
    alarm = _above_rest(state.get('anxiety', 50.0))
    startled = 100.0 if _level(state.get('is_startled', 0.0)) > 50.0 else 0.0
    knows_how = _above_rest(state['social_fight']) if 'social_fight' in state else 0.0
    if knows_how > max(alarm, startled):
        return knows_how, 'social_fight'
    return max(alarm, startled), 'alarm'


def fighting_ability(fit: float, commit: float) -> float:
    """Fitness, multiplied by commitment (half as able uncommitted, half as
    able again fully committed)."""
    return round(100.0 * max(0.0, float(fit)) * (0.5 + _level(commit) / 100.0), 1)


def squid_fitness(squid, statistics=None) -> Tuple[float, Dict[str, float]]:
    """fitness() for a squid object (desktop or mobile)."""
    stats = statistics if statistics is not None else getattr(squid, 'statistics', None)
    return fitness(health=getattr(squid, 'health', 100.0),
                   hunger=getattr(squid, 'hunger', 0.0),
                   sleepiness=getattr(squid, 'sleepiness', 0.0),
                   sick=bool(getattr(squid, 'is_sick', False)),
                   fights_won=getattr(stats, 'fights_won', 0),
                   fights_lost=getattr(stats, 'fights_lost', 0))


def side(state: Dict[str, Any], fit: float, fit_reasons: Dict[str, float],
         attacking: bool) -> Dict[str, Any]:
    """One squid's side of a fight: its ability, and everything behind it."""
    commit, kind = commitment(state, attacking)
    return {'role': 'attacker' if attacking else 'defender',
            'fitness': fit, **fit_reasons,
            'commitment': round(commit, 1), 'committed_by': kind,
            'ability': fighting_ability(fit, commit)}


def resolve_fight(first: Dict[str, Any], second: Dict[str, Any],
                  rng: Optional[Callable[[], float]] = None) -> Dict[str, Any]:
    """Who wins, from the two sides' abilities. The record keeps both sides."""
    a = max(0.1, float(first['ability'])) ** ABILITY_SHARPNESS
    b = max(0.1, float(second['ability'])) ** ABILITY_SHARPNESS
    chance = a / (a + b)
    roll = (rng or random.random)()
    return {'first_won': roll < chance, 'first_chance': round(chance, 3),
            'first': dict(first), 'second': dict(second)}


#: How far one fight raises a squid's resting aggression - for good - by
#: outcome, and the highest it can ever be raised that way. A beaten squid is
#: marked more than a winner; neither is ever quite as placid again.
AGGRESSION_SCAR = {True: 2.0, False: 4.0}
AGGRESSION_SCAR_CEILING = 60.0


def scar(brain, won: bool, cause: str) -> float:
    """A fight leaves its mark on the squid's aggression neuron, if it has one.

    Returns how far its resting level rose (EnhancedNeurogenesis.
    raise_resting_level, which records the cause on the neuron).
    """
    growth = getattr(brain, 'enhanced_neurogenesis', None)
    if growth is None or not hasattr(growth, 'raise_resting_level'):
        return 0.0
    return growth.raise_resting_level('aggression', AGGRESSION_SCAR[bool(won)], cause,
                                      ceiling=AGGRESSION_SCAR_CEILING)


#: What a fight does to each squid's body and drives, by outcome. Applied by
#: whichever machine the squid lives on; the deltas are part of the record.
CONSEQUENCES = {
    True: {'health': -3.0, 'satisfaction': 15.0, 'happiness': 8.0, 'anxiety': -5.0},
    False: {'health': -8.0, 'happiness': -10.0, 'anxiety': 15.0, 'satisfaction': -5.0},
}


def apply_consequences(squid, won: bool) -> Dict[str, float]:
    """Apply CONSEQUENCES to a squid's stats; returns what changed."""
    applied = {}
    for stat, delta in CONSEQUENCES[bool(won)].items():
        if not isinstance(getattr(squid, stat, None), (int, float)):
            continue
        before = float(getattr(squid, stat))
        after = max(0.0, min(100.0, before + delta))
        setattr(squid, stat, after)
        applied[stat] = round(after - before, 2)
    return applied


def describe(record: Dict[str, Any], me: str = 'first') -> str:
    """One readable line: who started it, why, and why it ended as it did."""
    mine = record.get(me) or {}
    theirs = record.get('second' if me == 'first' else 'first') or {}
    won = record.get('first_won') == (me == 'first')
    why = record.get('why') or {}
    if mine.get('role') == 'attacker':
        how = f"a fight it started (aggression {why.get('aggression', 0):.0f})"
    else:
        how = "a fight when it was attacked"
    return (f"{'Won' if won else 'Lost'} {how}: ability "
            f"{mine.get('ability', 0):.0f} against {theirs.get('ability', 0):.0f}, "
            f"so it had a {100 * (record.get('first_chance', .5) if me == 'first' else 1 - record.get('first_chance', .5)):.0f}% chance.")


__all__ = ['AGGRESSION_THRESHOLD', 'ABILITY_SHARPNESS', 'CONSEQUENCES',
           'AGGRESSION_SCAR', 'AGGRESSION_SCAR_CEILING', 'scar',
           'fight_predisposition', 'fitness', 'squid_fitness', 'commitment',
           'fighting_ability', 'side', 'resolve_fight', 'apply_consequences',
           'describe']
