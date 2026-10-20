# File: social_knowledge.py
"""What a squid knows about other squid, kept apart from what it knows of its tank.

Everything here is read from the squid itself - nothing is decided:

  * its grown social network: which social senses and neurons it has, what
    each stands for, and why it grew (the neuron's own birth record);
  * its aggression, in words (placid .. fully aggro), where it rests and
    every event that raised that resting level for good;
  * how it meets strangers: the synapses leaving can_see_squid, pulling
    towards other squid or away from them, and how much of that its life
    (mechanism 'encounter') rather than its birth put there;
  * the individuals it remembers, and its fights - who started each and
    why, and why it ended as it did - from its own social memories.

Social memories are those in category 'social' (encounters 'peer:<uuid>',
fights 'fight:<id>', rock strikes 'rock:<throw_id>'); everything else the
squid remembers is about its environment. `think` is how social events
reach the Decisions tab as the squid's own thoughts, with their reasons.

Qt-free: desktop and mobile share it.
"""

import time
from collections import deque
from html import escape
from typing import Any, Dict, Iterable, List, Optional

from .brain_constants import (AGGRESSION_NEURON, SOCIAL_NEURONS, SOCIAL_SENSOR,
                              SOCIAL_SENSORS)

SOCIAL_CATEGORY = 'social'

#: Aggression in words. A squid at or past fighting.AGGRESSION_THRESHOLD (50)
#: is predisposed to start a fight.
AGGRESSION_WORDS = ((90.0, 'fully aggro'), (70.0, 'aggressive'),
                    (50.0, 'spoiling for a fight'), (30.0, 'edgy'),
                    (10.0, 'calm'), (0.0, 'placid and relaxed'))

#: How many recent social thoughts a brain keeps for the Decisions tab.
THOUGHTS_KEPT = 30


def is_social_memory(memory: Dict[str, Any]) -> bool:
    return isinstance(memory, dict) and memory.get('category') == SOCIAL_CATEGORY


def split_memories(memories: Iterable[Dict[str, Any]]):
    """(social, environment): what it knows of other squid, and the rest."""
    social, environment = [], []
    for memory in memories or ():
        (social if is_social_memory(memory) else environment).append(memory)
    return social, environment


def aggression_in_words(level: float) -> str:
    level = float(level or 0.0)
    for floor, words in AGGRESSION_WORDS:
        if level >= floor:
            return words
    return AGGRESSION_WORDS[-1][1]


def _engine(brain):
    return getattr(brain, 'enhanced_neurogenesis', None)


def _functional(brain, name):
    return (getattr(_engine(brain), 'functional_neurons', {}) or {}).get(name)


def _level(state, name) -> float:
    try:
        return float((state or {}).get(name, 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _born_because(brain, name) -> str:
    """Why this neuron exists, from its own birth record."""
    fn = _functional(brain, name)
    deficit = getattr(fn, 'origin_deficit', None) or {}
    if deficit.get('summary'):
        return str(deficit['summary'])
    for row in reversed(list(getattr(_engine(brain), 'growth_log', []) or [])):
        if row.get('neuron') == name and row.get('because'):
            return str(row['because'])
    return ''


def aggression(brain) -> Dict[str, Any]:
    """The squid's aggression: now, at rest, and what raised it for good."""
    from .fighting import AGGRESSION_THRESHOLD
    positions = getattr(brain, 'neuron_positions', None) or {}
    if AGGRESSION_NEURON not in positions:
        return {'grown': False, 'level': 0.0, 'words': aggression_in_words(0.0),
                'resting': 0.0, 'resting_words': aggression_in_words(0.0),
                'starts_fights': False, 'threshold': AGGRESSION_THRESHOLD,
                'rises': [], 'born': ''}
    level = _level(getattr(brain, 'state', {}), AGGRESSION_NEURON)
    fn = _functional(brain, AGGRESSION_NEURON)
    resting = getattr(fn, 'resting_level', None)
    resting = float(resting) if resting is not None else 0.0
    return {'grown': True, 'level': round(level, 1), 'words': aggression_in_words(level),
            'resting': round(resting, 1), 'resting_words': aggression_in_words(resting),
            'starts_fights': level >= AGGRESSION_THRESHOLD,
            'threshold': AGGRESSION_THRESHOLD,
            'rises': [dict(r) for r in getattr(fn, 'resting_history', []) or []],
            'born': _born_because(brain, AGGRESSION_NEURON)}


def towards_strangers(brain) -> Dict[str, Any]:
    """How the squid meets any squid: can_see_squid's pull towards and away."""
    from .social_learning import AWAY, TOWARDS
    positions = getattr(brain, 'neuron_positions', None) or {}
    if SOCIAL_SENSOR not in positions:
        return {'grown': False, 'towards': 0.0, 'away': 0.0, 'net': 0.0,
                'words': 'has never seen another squid', 'synapses': [],
                'learned': 0.0}
    weights = getattr(brain, 'weights', {}) or {}
    ledger = getattr(brain, 'ledger', None)
    synapses, learned = [], 0.0
    pull = {'towards': 0.0, 'away': 0.0}
    for targets, side in ((TOWARDS, 'towards'), (AWAY, 'away')):
        for target in targets:
            weight = weights.get((SOCIAL_SENSOR, target))
            if weight is None:
                continue
            pull[side] += max(0.0, float(weight))
            from_life = 0.0
            if ledger is not None and hasattr(ledger, 'edge_totals'):
                from_life = float((ledger.edge_totals((SOCIAL_SENSOR, target)) or {})
                                  .get('encounter', 0.0))
            learned += from_life if side == 'towards' else -from_life   # as net
            synapses.append({'to': target, 'weight': round(float(weight), 3),
                             'side': side, 'from_encounters': round(from_life, 3)})
    net = pull['towards'] - pull['away']
    if net >= 0.6:
        words = 'drawn to other squid'
    elif net >= 0.15:
        words = 'inclined to approach other squid'
    elif net > -0.15:
        words = 'undecided about other squid'
    elif net > -0.6:
        words = 'wary of other squid'
    else:
        words = 'afraid of other squid'
    synapses.sort(key=lambda s: -abs(s['weight']))
    return {'grown': True, 'towards': round(pull['towards'], 3),
            'away': round(pull['away'], 3), 'net': round(net, 3), 'words': words,
            'synapses': synapses, 'learned': round(learned, 3)}


def grown_network(brain) -> List[Dict[str, Any]]:
    """The social senses and neurons this squid grew, in order of growth."""
    from .neurogenesis import SOCIAL_CONCEPTS
    positions = getattr(brain, 'neuron_positions', None) or {}
    state = getattr(brain, 'state', {}) or {}
    rows = []
    for name in list(SOCIAL_SENSORS) + list(SOCIAL_NEURONS):
        if name not in positions:
            continue
        fn = _functional(brain, name)
        rows.append({'name': name,
                     'kind': 'sense' if name in SOCIAL_SENSORS else 'neuron',
                     'concept': SOCIAL_CONCEPTS.get(name, name.replace('_', ' ')),
                     'level': round(_level(state, name), 1),
                     'born': _born_because(brain, name),
                     'at': float(getattr(getattr(fn, 'creation_context', None),
                                         'timestamp', 0.0) or 0.0)})
    return rows


def _payload(memory: Dict[str, Any]) -> Dict[str, Any]:
    """The memory's facts: desktop keeps them in 'value', mobile in 'raw_value'."""
    for field in ('value', 'raw_value'):
        if isinstance(memory.get(field), dict):
            return memory[field]
    return {}


def fights(memories: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Every fight it remembers, newest first, with why it started and ended."""
    from .fighting import AGGRESSION_THRESHOLD
    rows, seen = [], set()
    for memory in memories or ():
        key = str(memory.get('key') or '')
        if not is_social_memory(memory) or not key.startswith('fight:') or key in seen:
            continue
        seen.add(key)
        value = _payload(memory)
        detail = value.get('detail') if isinstance(value.get('detail'), dict) else {}
        why = detail.get('why_started') or {}
        started = bool(detail.get('started_it'))
        if started:
            how = (f"it started it - its aggression was {float(why.get('aggression', 0)):.0f}, "
                   f"past the {AGGRESSION_THRESHOLD:.0f} it takes")
        else:
            mine = detail.get('mine') or {}
            how = (f"it was attacked, and fought back with its "
                   f"{mine.get('committed_by', 'alarm')} at {float(mine.get('commitment', 0)):.0f}")
        rows.append({'key': key, 'opponent': value.get('opponent', 'another squid'),
                     'opponent_uuid': value.get('opponent_uuid', ''),
                     'won': value.get('outcome') == 'won', 'started_it': started,
                     'how_it_started': how, 'summary': value.get('summary', ''),
                     'chance': detail.get('chance'),
                     'timestamp': memory.get('timestamp', 0)})
    rows.sort(key=lambda r: -float(r['timestamp'] or 0))
    return rows


def acquaintances(memories: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The individual squid it remembers, and what it remembers of each."""
    people: Dict[str, Dict[str, Any]] = {}

    def person(uuid, name=''):
        row = people.setdefault(uuid, {'uuid': uuid, 'name': name or 'a squid',
                                       'personality': '', 'encounters': 0,
                                       'good': 0.0, 'bad': 0.0, 'fights_won': 0,
                                       'fights_lost': 0, 'hits_taken': 0,
                                       'hits_given': 0, 'matings': 0,
                                       'last_outcome': '', 'last_seen': 0.0})
        if name and row['name'] == 'a squid':
            row['name'] = name
        return row

    for memory in memories or ():
        if not is_social_memory(memory):
            continue
        key = str(memory.get('key') or '')
        value = _payload(memory)
        detail = value.get('detail') if isinstance(value.get('detail'), dict) else {}
        when = memory.get('timestamp', 0)
        if key.startswith('peer:'):
            row = person(key[5:].split(':', 1)[0], value.get('peer_name', ''))
            row['encounters'] += max(1, int(detail.get('encounters', 1) or 1))
            valence = float(value.get('valence', 0.0) or 0.0)
            row['good' if valence >= 0 else 'bad'] += abs(valence)
            row['personality'] = value.get('peer_personality') or row['personality']
            row['last_outcome'] = value.get('outcome') or row['last_outcome']
            row['fights_won'] += int(detail.get('fights_won', 0) or 0)
            row['fights_lost'] += int(detail.get('fights_lost', 0) or 0)
            row['hits_taken'] += int(detail.get('hits_taken', 0) or 0)
            row['hits_given'] += int(detail.get('hits_given', 0) or 0)
            row['matings'] += 1 if detail.get('mating_id') else 0
        elif key.startswith('rock:') and value.get('peer_uuid'):
            row = person(str(value['peer_uuid']))
            row['hits_taken'] += int(value.get('hits_taken', 0) or 0)
            row['hits_given'] += int(value.get('hits_given', 0) or 0)
        else:
            continue
        if isinstance(when, (int, float)):
            row['last_seen'] = max(row['last_seen'], float(when))
    for row in people.values():
        row['feeling'] = _feeling(row)
    return sorted(people.values(), key=lambda r: -r['last_seen'])


def _feeling(row) -> str:
    good, bad = row['good'], row['bad']
    if row['fights_lost'] > row['fights_won'] or bad > good * 1.5 + 2:
        return 'remembers it badly'
    if good > bad * 1.5 + 2:
        return 'remembers it fondly'
    if good or bad:
        return 'has mixed memories of it'
    return 'barely remembers it'


def describe_memory(memory: Dict[str, Any]):
    """(title, text, sign) of one social memory, for its card: sign is +1
    for one it remembers well, -1 badly, 0 neither."""
    key = str(memory.get('key') or '')
    value = _payload(memory)
    detail = value.get('detail') if isinstance(value.get('detail'), dict) else {}
    if key.startswith('fight:'):
        won = value.get('outcome') == 'won'
        return (f"{'Won' if won else 'Lost'} a fight with {value.get('opponent', 'a squid')}",
                str(value.get('summary', '')), 1 if won else -1)
    if key.startswith('rock:'):
        if value.get('hits_given'):
            return ('Struck a squid with a rock', 'A rock it threw hit another squid.', 0)
        return ('Struck by a rock', 'A rock hit it. It cannot know whether the '
                'thrower was playing or attacking.', -1)
    if key.startswith('peer:'):
        name = value.get('peer_name') or 'a squid'
        valence = float(value.get('valence', 0.0) or 0.0)
        facts = []
        if detail.get('first_meeting'):
            facts.append('their first meeting')
        if detail.get('mating_id'):
            facts.append('they mated')
        for field, words in (('fights_won', 'fights won'), ('fights_lost', 'fights lost'),
                             ('hits_taken', 'struck by rocks'), ('hits_given', 'struck it'),
                             ('items_taken', 'took'), ('items_lost', 'lost')):
            if detail.get(field):
                facts.append(f"{words} {detail[field]}")
        if detail.get('duration'):
            facts.append(f"{float(detail['duration']):.0f}s")
        outcome = str(value.get('outcome') or 'an').capitalize()
        return (f"{outcome} encounter with {name}",
                f"It felt {valence:+.1f}" + (f" - {', '.join(facts)}" if facts else ''),
                (valence > 0) - (valence < 0))
    return ('Social', str(value.get('summary') or value or memory.get('value', '')), 0)


def knowledge(brain, memories: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    memories = list(memories or ())
    return {'network': grown_network(brain), 'aggression': aggression(brain),
            'strangers': towards_strangers(brain), 'fights': fights(memories),
            'acquaintances': acquaintances(memories),
            'memories': [m for m in memories if is_social_memory(m)]}


def _when(stamp) -> str:
    if not isinstance(stamp, (int, float)) or stamp <= 0:
        return ''
    return time.strftime('%d %b %H:%M', time.localtime(stamp))


def to_html(known: Dict[str, Any]) -> str:
    """The Memory tab's Social page: what the squid knows of other squid."""
    e = lambda text: escape(str(text))           # noqa: E731
    parts = []
    network = known['network']
    if not network:
        return ("<h3>Social knowledge</h3><p>It has never met another squid. "
                "Nothing in its brain stands for other squid: those senses and "
                "neurons only grow from an encounter.</p>")

    agg = known['aggression']
    if agg['grown']:
        lines = [f"<b>Aggression</b>: {agg['level']:.0f} - {e(agg['words'])} right now. "
                 f"It rests at {agg['resting']:.0f} ({e(agg['resting_words'])})."]
        lines.append("At this level it would start a fight."
                     if agg['starts_fights'] else
                     f"It would not start a fight now (that takes {agg['threshold']:.0f}).")
        if agg['rises']:
            rises = ''.join(f"<li>{_when(r.get('at'))}: {float(r.get('from', 0)):.0f} &rarr; "
                            f"{float(r.get('to', 0)):.0f}, because it {e(r.get('cause', ''))}</li>"
                            for r in agg['rises'][-6:])
            lines.append(f"Raised for good by:<ul>{rises}</ul>")
        else:
            lines.append("Nothing has raised its resting aggression yet.")
        parts.append('<br>'.join(lines))
    else:
        parts.append("<b>Aggression</b>: it has no aggression neuron - it has never "
                     "gone at another squid while alarmed. It is placid and relaxed.")

    strangers = known['strangers']
    if strangers['grown']:
        line = (f"<b>Towards squid it does not know</b>: {e(strangers['words'])} "
                f"(pull towards {strangers['towards']:+.2f}, away {strangers['away']:+.2f}).")
        if abs(strangers['learned']) >= 0.005:
            line += (f" Its encounters have moved this by {strangers['learned']:+.2f} "
                     f"in all - its life, not its birth.")
        parts.append(line)

    rows = ''.join(f"<li><b>{e(n['name'])}</b> ({n['kind']}, now {n['level']:.0f}) - "
                   f"{e(n['concept'])}"
                   + (f"<br><i>grew because: {e(n['born'])}</i>" if n['born'] else '')
                   + "</li>" for n in network)
    parts.append(f"<b>Its social network</b> - grown from its own encounters:<ul>{rows}</ul>")

    people = known['acquaintances']
    if people:
        rows = []
        for p in people:
            facts = [f"{p['encounters']} encounter(s)"] if p['encounters'] else []
            if p['fights_won'] or p['fights_lost']:
                facts.append(f"fights won {p['fights_won']}, lost {p['fights_lost']}")
            if p['hits_taken']:
                facts.append(f"hit by its rocks {p['hits_taken']}")
            if p['hits_given']:
                facts.append(f"hit it with rocks {p['hits_given']}")
            if p['matings']:
                facts.append('mated')
            who = e(p['name']) + (f" ({e(p['personality'])})" if p['personality'] else '')
            rows.append(f"<li><b>{who}</b>: it {e(p['feeling'])} - {', '.join(facts)}</li>")
        parts.append(f"<b>Squid it would recognise</b>:<ul>{''.join(rows)}</ul>")
    else:
        parts.append("<b>Squid it would recognise</b>: none. Mild encounters are forgotten.")

    fought = known['fights']
    if fought:
        rows = ''.join(f"<li><b>{'Won' if f['won'] else 'Lost'}</b> against {e(f['opponent'])}"
                       f" {_when(f['timestamp'])}: {e(f['how_it_started'])}."
                       + (f"<br><i>{e(f['summary'])}</i>" if f['summary'] else '') + "</li>"
                       for f in fought[:10])
        parts.append(f"<b>Fights</b> - why each started and how it ended:<ul>{rows}</ul>")
    return "<h3>Social knowledge</h3>" + "<br><br>".join(parts)


# -- thoughts --------------------------------------------------------------

def think(owner, text: str) -> str:
    """A social thought, with its reason, for the Decisions tab.

    `owner` is a brain widget or the game logic. Kept on the brain (the most
    recent THOUGHTS_KEPT, as `social_thoughts`) and passed to the brain
    window's thought log when there is one.
    """
    text = str(text)
    logic = getattr(owner, 'tamagotchi_logic', None) or owner
    window = getattr(logic, 'brain_window', None)
    brain = getattr(window, 'brain_widget', None) or owner
    kept = getattr(brain, 'social_thoughts', None)
    if not isinstance(kept, deque):
        try:
            kept = deque(maxlen=THOUGHTS_KEPT)
            brain.social_thoughts = kept
        except AttributeError:
            kept = None
    if kept is not None:
        kept.append((time.time(), text))
    if window is not None and hasattr(window, 'add_thought'):
        try:
            window.add_thought(text)
        except Exception:
            pass
    return text


def fight_thoughts(record: Dict[str, Any], me: str = 'first') -> List[str]:
    """The squid's own account of a fight: why it started and why it ended
    so. A mark it leaves is told by EnhancedNeurogenesis.raise_resting_level."""
    from .fighting import AGGRESSION_THRESHOLD
    mine = record.get(me) or {}
    theirs = record.get('second' if me == 'first' else 'first') or {}
    opponent = record.get('opponent', 'the other squid')
    won = bool(record.get('first_won')) == (me == 'first')
    chance = float(record.get('first_chance', .5) if me == 'first'
                   else 1.0 - float(record.get('first_chance', .5)))
    if mine.get('role') == 'attacker':
        why = (record.get('why') or {}).get('aggression', mine.get('commitment', 0))
        lines = [f"I went for {opponent}: my aggression was {float(why or 0):.0f}, "
                 f"past the {AGGRESSION_THRESHOLD:.0f} it takes to start a fight."]
    else:
        lines = [f"{opponent} came at me. I fought back with my "
                 f"{mine.get('committed_by', 'alarm')} at {float(mine.get('commitment', 0) or 0):.0f}."]
    lines.append(f"I {'won' if won else 'lost'}: my ability {float(mine.get('ability', 0) or 0):.0f} "
                 f"against their {float(theirs.get('ability', 0) or 0):.0f} gave me a "
                 f"{chance:.0%} chance.")
    return lines


__all__ = ['SOCIAL_CATEGORY', 'AGGRESSION_WORDS', 'is_social_memory', 'split_memories',
           'aggression_in_words', 'aggression', 'towards_strangers', 'grown_network',
           'fights', 'acquaintances', 'describe_memory', 'knowledge', 'to_html', 'think',
           'fight_thoughts']
