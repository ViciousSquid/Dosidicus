# File: life_timeline.py
"""A squid's life in order: every event that shaped it, and the brain it had
at each one.

Everything here is already recorded by the game as it happens - when each
neuron grew and why (neural_provenance origins), when each synapse first
formed and by what means (provenance totals), every memory with its time,
the life-cycle record. Nothing is inferred and nothing is narrated that the
squid's own records do not say. This module only puts it in order.

    build(save)  ->  {
        'born_at', 'ended_at', 'squid': {...},
        'eras':        the stages of the life, with when each began
        'events':      every life event, oldest first
        'neurons':     every neuron, and when it came to be
        'connections': every synapse, when it first formed, and how
        'lineage':     the parents and what was inherited, for a hatchling
        'journey':     the chapters of life_journey, if they were supplied
        'counts':      totals, for a table of many squid
    }

`save` is the dict the game writes (game_state, brain_state, statistics,
ShortTerm, LongTerm) - a live game's or one read back from a save file. The
result is written into the save as timeline.json, so anything outside the
game (the Laboratory pages in extras/) shows the same life in the same words
without a second copy of this logic.

With `events` and `neurons`/`connections` a viewer can stand at any moment of
the life and draw the brain as it was then: the neurons born by that moment,
the synapses formed by it.

Qt-free. Never raises on a save it does not fully understand: a part that
cannot be read is left out.
"""
import time
from typing import Any, Dict, Iterable, List, Optional

VERSION = 1

#: How a synapse came to be or was changed, in plain words
#: (neural_provenance mechanisms).
MECHANISMS = {
    'innate': 'born with it',
    'inheritance': 'inherited from a parent',
    'hebbian': 'two neurons that fire together',
    'stdp': 'one neuron firing just before another',
    'reflex': 'an inborn reflex',
    'causal_reward': 'what an action led to',
    'causal': 'what an action led to',
    'consolidation': 'replayed in sleep',
    'neurogenesis': 'wired when a neuron grew',
    'encounter': 'an encounter with another squid',
    'social': 'an encounter with another squid',
    'discovery': 'trying an action it had never used',
    'designer': 'set by hand in the Brain Designer',
    'manual': 'set by hand',
}

ERAS = (
    ('hatchling', 'Hatchling',
     'As it hatched: the neurons and wiring every squid is born with.'),
    ('learning', 'Learning',
     'It has started to change its own wiring from what it lives through.'),
    ('growing', 'Growing',
     'It has grown neurons of its own, each for something it could not otherwise represent.'),
    ('social', 'Among other squid',
     'It knows there are other squid and other tanks, and has grown senses for them.'),
    ('parent', 'Parent',
     'It has mated and laid an egg. It no longer eats.'),
    ('dead', 'Ended',
     'It has died. Its headstone stays in the tank.'),
)


def _number(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number == number and abs(number) != float('inf') else default


def _words(name: str) -> str:
    return str(name).replace('_', ' ')


def _kind_of(name: str) -> str:
    try:
        from .brain_constants import (ACTION_NEURONS, CORE_STAT_NEURONS, SOCIAL_NEURONS,
                                      SOCIAL_SENSORS, DEFAULT_INPUT_SENSORS)
    except Exception:                                  # noqa: BLE001
        return 'neuron'
    if name in CORE_STAT_NEURONS:
        return 'drive'
    if name in ACTION_NEURONS:
        return 'action'
    if name in SOCIAL_SENSORS:
        return 'social sense'
    if name in SOCIAL_NEURONS:
        return 'social'
    if name in DEFAULT_INPUT_SENSORS:
        return 'sense'
    return 'grown'


def _memories(save: Dict[str, Any]) -> List[Dict[str, Any]]:
    seen, found = set(), []
    for store, lasting in (('LongTerm', True), ('ShortTerm', False)):
        for memory in save.get(store) or []:
            if not isinstance(memory, dict):
                continue
            stamp = (str(memory.get('key')), memory.get('timestamp'))
            if stamp in seen:
                continue
            seen.add(stamp)
            found.append(dict(memory, _lasting=lasting))
    return found


def _memory_event(memory: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """One memory as a life event, or None for one that is not an event of
    its own (a neuron's birth is taken from the brain's own record of it)."""
    key = str(memory.get('key') or '')
    category = str(memory.get('category') or '')
    value = memory.get('value')
    when = _number(memory.get('timestamp'), 0.0)
    if not when or category == 'neurogenesis':
        return None
    record = value if isinstance(value, dict) else {}
    detail = record.get('detail') if isinstance(record.get('detail'), dict) else {}
    event = {'t': when, 'lasting': bool(memory.get('_lasting'))}
    if key.startswith('fight:'):
        won = record.get('outcome') == 'won'
        event.update(kind='fight', title=f"{'Won' if won else 'Lost'} a fight with "
                                         f"{record.get('opponent', 'another squid')}",
                     text=str(record.get('summary', '')),
                     who=str(record.get('opponent', '')),
                     detail={'started_it': bool(detail.get('started_it')),
                             'chance': detail.get('chance'),
                             'why': detail.get('why_started') or {},
                             'cost': detail.get('consequences') or {}})
    elif key.startswith('peer:'):
        outcome = str(record.get('outcome') or 'an')
        name = record.get('peer_name') or 'another squid'
        bits = []
        if detail.get('first_meeting'):
            bits.append('their first meeting')
        if detail.get('fights_won'):
            bits.append(f"fights won {detail['fights_won']}")
        if detail.get('fights_lost'):
            bits.append(f"fights lost {detail['fights_lost']}")
        if detail.get('mating_id'):
            bits.append('they mated')
        if detail.get('duration'):
            bits.append(f"{round(_number(detail['duration']))}s together")
        kind = 'mating' if detail.get('mating_id') else 'encounter'
        event.update(kind=kind, who=str(name),
                     title=f"{outcome[:1].upper()}{outcome[1:]} encounter with {name}",
                     text=(f"It felt {_number(record.get('valence')):+.1f}"
                           + (': ' + ', '.join(bits) if bits else '') + '.'),
                     detail={'valence': _number(record.get('valence')),
                             'first_meeting': bool(detail.get('first_meeting'))})
    elif category == 'belief':
        gave_up = bool(record.get('changed_mind')) or key.startswith('revised:')
        statement = str(record.get('statement') or record.get('summary') or _words(key))
        event.update(kind='belief_dropped' if gave_up else 'belief',
                     title=('Stopped believing: ' if gave_up else 'Came to believe: ') + statement,
                     text=str(record.get('summary') or ''),
                     detail={'occasions': record.get('occasions')})
    else:
        text = (record.get('summary') or record.get('description')
                or (value if isinstance(value, str) else ''))
        if not text:
            return None
        event.update(kind='memory', title=_words(key)[:80] or category, text=str(text),
                     detail={'category': category})
    return event


def build(save: Dict[str, Any], journey: Any = None,
          now: Optional[float] = None) -> Dict[str, Any]:
    """The life in `save`, in order. See the module's own description."""
    save = save if isinstance(save, dict) else {}
    game = save.get('game_state') if isinstance(save.get('game_state'), dict) else {}
    brain = save.get('brain_state') if isinstance(save.get('brain_state'), dict) else {}
    stats = save.get('statistics') if isinstance(save.get('statistics'), dict) else {}
    squid = game.get('squid') if isinstance(game.get('squid'), dict) else {}
    life = game.get('lifecycle') if isinstance(game.get('lifecycle'), dict) else {}
    provenance = brain.get('provenance') if isinstance(brain.get('provenance'), dict) else {}
    origins = provenance.get('origins') if isinstance(provenance.get('origins'), dict) else {}
    totals = provenance.get('totals') if isinstance(provenance.get('totals'), list) else []
    positions = brain.get('neuron_positions') if isinstance(brain.get('neuron_positions'), dict) else {}

    memories = _memories(save)
    stamps = [_number(m.get('timestamp')) for m in memories if m.get('timestamp')]
    stamps += [_number(o.get('created_at')) for o in origins.values() if isinstance(o, dict)]
    stamps += [_number(t.get('first_seen')) for t in totals if isinstance(t, dict)]
    stamps = [s for s in stamps if s > 0]
    age = _number(stats.get('total_age_seconds'))
    ended_at = _number(now, 0.0) or (max(stamps) if stamps else time.time())
    death = life.get('death') if isinstance(life.get('death'), dict) else None
    if death and _number(death.get('at')):
        ended_at = max(ended_at, _number(death.get('at')))
    # It hatched its age ago; never after the first thing recorded of it.
    born_at = ended_at - age if age > 0 else (min(stamps) if stamps else ended_at)
    if stamps:
        born_at = min(born_at, min(stamps))

    # ---- the brain, with when each part came to be ------------------------
    neurons = []
    for name, position in positions.items():
        origin = origins.get(name) if isinstance(origins.get(name), dict) else None
        try:
            x, y = float(position[0]), float(position[1])
        except (TypeError, ValueError, IndexError):
            x = y = 0.0
        neurons.append({
            'name': str(name), 'x': round(x, 1), 'y': round(y, 1), 'kind': _kind_of(str(name)),
            'born': _number(origin.get('created_at')) if origin else None,
            'why': str(origin.get('deficit_summary') or '') if origin else '',
            'for': str(origin.get('remedy') or '') if origin else '',
        })
    born_of = {n['name']: n['born'] for n in neurons}

    weights = {}
    for row in brain.get('weights_list') or []:
        if isinstance(row, (list, tuple)) and len(row) == 3:
            weights[(str(row[0]), str(row[1]))] = _number(row[2])
    how = {}
    for entry in totals:
        if isinstance(entry, dict) and isinstance(entry.get('edge'), (list, tuple)) \
                and len(entry['edge']) == 2:
            how[(str(entry['edge'][0]), str(entry['edge'][1]))] = entry
    connections = []
    for (source, target), weight in sorted(weights.items()):
        entry = how.get((source, target), {})
        counted = entry.get('counts') if isinstance(entry.get('counts'), dict) else {}
        moved = entry.get('totals') if isinstance(entry.get('totals'), dict) else {}
        innate = 'innate' in counted or 'inheritance' in counted
        since = _number(entry.get('first_seen'), 0.0) or None
        # A synapse cannot be older than either neuron it joins.
        for end in (source, target):
            if born_of.get(end) and (since is None or since < born_of[end]):
                since = born_of[end]
        connections.append({
            'source': source, 'target': target, 'weight': round(weight, 4),
            'since': None if (innate and not any(born_of.get(e) for e in (source, target))) else since,
            'innate': innate,
            'by': {str(k): round(_number(v), 4) for k, v in moved.items()},
            'times': {str(k): int(_number(v)) for k, v in counted.items()},
        })

    # ---- events -------------------------------------------------------------
    events: List[Dict[str, Any]] = []
    personality = str(squid.get('personality') or '')
    lineage = squid.get('lineage') if isinstance(squid.get('lineage'), dict) else {}
    parents = [str(p) for p in (lineage.get('parents') or [])][:2]
    events.append({
        't': born_at, 'kind': 'hatched',
        'title': f"Hatched{', a ' + personality + ' squid' if personality else ''}",
        'text': (f"From the egg of {' and '.join(parents)}: half of each parent's inborn "
                 f"wiring, {sum(1 for g in lineage.get('inherited') or [] if g.get('mutated'))} "
                 f"synapses mutated." if parents else
                 'From a fresh egg, with the neurons and wiring every squid is born with.'),
        'detail': {'neurons': sum(1 for n in neurons if not n['born'])}})

    for neuron in neurons:
        if neuron['born']:
            wired = [c for c in connections
                     if neuron['name'] in (c['source'], c['target'])]
            events.append({
                't': neuron['born'], 'kind': 'neuron', 'neuron': neuron['name'],
                'title': f"Grew a neuron: {_words(neuron['name'])}",
                'text': neuron['why'] or 'It grew a new neuron.',
                'detail': {'for': neuron['for'], 'kind': neuron['kind'],
                           'connections': len(wired)}})
    for gone in provenance.get('pruned') or []:
        if isinstance(gone, dict) and _number(gone.get('at') or gone.get('pruned_at')):
            events.append({
                't': _number(gone.get('at') or gone.get('pruned_at')), 'kind': 'pruned',
                'title': f"Lost a neuron: {_words(gone.get('name', 'a neuron'))}",
                'text': str(gone.get('reason') or 'It was not being used.'), 'detail': {}})

    # A synapse it was not born with, the first time it formed - unless it
    # came with a neuron that grew, which is that neuron's event.
    for connection in connections:
        if connection['innate'] or not connection['since']:
            continue
        ends = (connection['source'], connection['target'])
        if any(born_of.get(end) and abs(born_of[end] - connection['since']) < 2.0 for end in ends):
            continue
        means = max(connection['times'] or {'': 0}, key=lambda k: connection['times'].get(k, 0))
        events.append({
            't': connection['since'], 'kind': 'association',
            'edge': [connection['source'], connection['target']],
            'title': f"Linked {_words(connection['source'])} to {_words(connection['target'])}",
            'text': (f"Formed through {MECHANISMS.get(means, _words(means) or 'learning')}; "
                     f"it stands at {connection['weight']:+.2f} now."),
            'detail': {'by': connection['times']}})

    for memory in memories:
        event = _memory_event(memory)
        if event:
            events.append(event)

    mated = life.get('reproduction') if isinstance(life.get('reproduction'), dict) else None
    if mated and _number(mated.get('at')):
        events.append({'t': _number(mated['at']), 'kind': 'egg', 'who': str(mated.get('mate_name', '')),
                       'title': f"Mated with {mated.get('mate_name', 'another squid')} and laid an egg",
                       'text': 'It is a parent now: it stops eating, and its egg hatches when it dies.',
                       'detail': {'mating': mated.get('mating_id')}})
    if death and _number(death.get('at')):
        events.append({'t': _number(death['at']), 'kind': 'death',
                       'title': f"Died: {_words(death.get('cause', 'unknown'))}",
                       'text': 'A headstone is laid where it died.', 'detail': {}})

    events = [e for e in events if e.get('t')]
    events.sort(key=lambda e: (e['t'], e['kind'] != 'hatched'))
    for index, event in enumerate(events):
        event['age'] = round(max(0.0, event['t'] - born_at), 1)
        event['n'] = index

    # ---- eras ---------------------------------------------------------------
    def first(test) -> Optional[float]:
        return next((e['t'] for e in events if test(e)), None)

    starts = {
        'hatchling': born_at,
        'learning': first(lambda e: e['kind'] == 'association'),
        'growing': first(lambda e: e['kind'] == 'neuron'),
        'social': first(lambda e: e['kind'] in ('encounter', 'fight', 'mating')
                        or (e['kind'] == 'neuron' and e['detail'].get('kind', '').startswith('social'))),
        'parent': first(lambda e: e['kind'] == 'egg'),
        'dead': first(lambda e: e['kind'] == 'death'),
    }
    eras, latest = [], born_at
    for key, title, about in ERAS:
        began = starts.get(key)
        if began is None:
            continue
        began = max(began, latest)          # an era never begins before the one before it
        latest = began
        eras.append({'key': key, 'title': title, 'about': about, 'from': began,
                     'age': round(began - born_at, 1)})
    # A stage that began at the same moment as the next (a squid whose first
    # grown neuron was a sense for another tank) was never a stage of its own.
    eras = [era for era, following in zip(eras, eras[1:] + [None])
            if following is None or following['from'] > era['from']]
    for era, following in zip(eras, eras[1:] + [None]):
        era['to'] = following['from'] if following else ended_at
    for event in events:
        event['era'] = next((era['key'] for era in reversed(eras) if event['t'] >= era['from']),
                            eras[0]['key'] if eras else '')

    counts: Dict[str, int] = {}
    for event in events:
        counts[event['kind']] = counts.get(event['kind'], 0) + 1
    result = {
        'version': VERSION,
        'born_at': born_at, 'ended_at': ended_at, 'age_seconds': round(ended_at - born_at, 1),
        'squid': {'name': str(squid.get('name') or 'Squid'), 'personality': personality,
                  'uuid': str(squid.get('uuid') or ''), 'stage': str(life.get('stage') or 'living'),
                  'colour': squid.get('tint_color') if isinstance(squid.get('tint_color'), list) else None},
        'eras': eras, 'events': events, 'neurons': neurons, 'connections': connections,
        'lineage': {'parents': parents,
                    'inherited': [g for g in (lineage.get('inherited') or []) if isinstance(g, dict)],
                    'bred_by': str(lineage.get('bred_by') or '')},
        'counts': dict(counts, neurons_at_birth=sum(1 for n in neurons if not n['born']),
                       neurons_grown=sum(1 for n in neurons if n['born']),
                       connections=len(connections),
                       connections_learned=sum(1 for c in connections if not c['innate'])),
    }
    if journey is not None:
        try:
            result['journey'] = _journey(journey)
        except Exception:                               # noqa: BLE001
            pass
    return result


def _journey(chapters: Iterable[Any]) -> List[Dict[str, Any]]:
    """life_journey's chapters as plain data: which stages of a life this
    squid has reached, and what each was judged on."""
    told = []
    for chapter in chapters:
        told.append({
            'title': chapter.title, 'about': chapter.about,
            'optional': bool(getattr(chapter, 'optional', False)),
            'complete': bool(chapter.complete), 'started': bool(chapter.started),
            'milestones': [{'title': m.title, 'reached': bool(m.reached),
                            'text': m.reached_because if m.reached else m.how,
                            'by_chance': bool(getattr(m, 'by_chance', False))}
                           for m in chapter.milestones]})
    return told


__all__ = ['build', 'VERSION', 'ERAS', 'MECHANISMS']
