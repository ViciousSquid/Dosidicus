# File: social_learning.py
"""What an encounter teaches a squid about other squid - strangers included.

When an encounter with another squid is filed as a memory, how it went moves
the synapses leaving the squid's can_see_squid sense. That is the sense for
ANY squid, so the lesson generalises to squid it has never met:

  * a bad encounter - beaten in a fight, robbed, frightened - weakens the
    pull towards other squid (act_play, curiosity, social_play) and
    strengthens alarm at them (anxiety, act_flee, social_flee);
  * a good one does the opposite.

So two squid born alike drift apart with what happens to them: the one that
keeps getting hurt grows wary of every squid, the one whose meetings go well
grows sociable. The same lesson reaches its aquarium_nearby sense, if it has
grown one: hurt, it is less drawn to explore other aquariums (and so to
venture out, src/venturing.py); welcomed, more. What it remembers of a particular individual is separate,
and is its recognition senses' (remembers_bad_encounter and the rest).

Mild encounters teach nothing, and are forgotten anyway. Every change goes
through the brain's apply_weight_change with the encounter that caused it,
so the Laboratory shows, synapse by synapse, how the squid's life changed
how it meets others. Qt-free: desktop and mobile share it.
"""

from typing import Any, List, Tuple

from .brain_constants import AQUARIUM_SENSE, SOCIAL_SENSOR

#: Weight change per point of encounter valence, and the most one encounter
#: can move a synapse.
LEARNING_RATE = 0.004
MAX_STEP = 0.15

#: Valence below this, either way, is an encounter that taught nothing.
MIN_VALENCE = 2.0

#: Where can_see_squid's synapses point when the squid is drawn to other squid,
#: and when it is wary of them.
TOWARDS = ('act_play', 'curiosity', 'social_play')
AWAY = ('anxiety', 'act_flee', 'social_flee')

#: Where aquarium_nearby's synapses point when another aquarium draws the
#: squid out, and when it unsettles it.
VENTURE_TOWARDS = ('act_move', 'curiosity')
VENTURE_AWAY = ('anxiety',)

#: Each sense an encounter teaches, with the targets it moves.
LESSONS = ((SOCIAL_SENSOR, TOWARDS, AWAY),
           (AQUARIUM_SENSE, VENTURE_TOWARDS, VENTURE_AWAY))


def learn_from_encounter(brain, valence: float, outcome: str = '',
                         peer: str = '') -> List[Tuple[Tuple[str, str], float, float]]:
    """Move can_see_squid's (and aquarium_nearby's) synapses by how an
    encounter went.

    Returns [(synapse, before, after)]. A synapse the lesson would only
    weaken is never created; one it strengthens may be.
    """
    positions = getattr(brain, 'neuron_positions', None) or {}
    if abs(float(valence)) < MIN_VALENCE:
        return []
    step = max(-MAX_STEP, min(MAX_STEP, float(valence) * LEARNING_RATE))
    detail = {'outcome': outcome, 'valence': round(float(valence), 2),
              'peer': peer,
              'note': f"{outcome or 'an'} encounter{' with ' + peer if peer else ''}"}
    changes = []
    for sense, towards, away in LESSONS:
        if sense not in positions:
            continue
        for targets, sign in ((towards, 1.0), (away, -1.0)):
            for target in targets:
                if target not in positions:
                    continue
                edge = (sense, target)
                before = brain.weights.get(edge)
                move = sign * step
                if before is None and move <= 0:
                    continue
                after = max(-1.0, min(1.0, (before or 0.0) + move))
                if brain.apply_weight_change(edge, value=after, mechanism='encounter',
                                             detail=detail, create=before is None):
                    changes.append((edge, before, after))
    if changes:
        from .social_knowledge import think
        lesson = 'more drawn to squid' if step > 0 else 'warier of squid'
        tanks = any(edge[0] == AQUARIUM_SENSE for edge, _, _ in changes)
        think(brain, f"That {outcome + ' ' if outcome else ''}encounter"
                     f"{' with ' + peer if peer else ''} went "
                     f"{'well' if step > 0 else 'badly'} (felt {float(valence):+.1f}): "
                     f"I am {lesson}, even ones I do not know"
                     + (" - and of other aquariums." if tanks else "."))
    return changes


__all__ = ['learn_from_encounter', 'LEARNING_RATE', 'MAX_STEP', 'MIN_VALENCE',
           'TOWARDS', 'AWAY', 'VENTURE_TOWARDS', 'VENTURE_AWAY', 'LESSONS']
