"""A squid's life as one journey: what it has become, and what comes next.

The game has many parts - feeding and cleaning, the brain that learns, the
neurons it grows, decorations, sleep, and (if the player turns it on) other
people's squid, fights, mating and an heir. This module is where they are one
thing. It reads the squid and says, in plain words, which stages of a life it
has reached and what the next one takes.

Three rules:

  * NOTHING IS AWARDED. A stage is reached because of something true about
    this squid that can be checked - a synapse it learned, a neuron it grew, a
    record in its lifecycle - never because a timer ran out or a button was
    pressed. Every milestone says what it was judged on.

  * AN OFFLINE LIFE IS A WHOLE LIFE. The first four chapters end with a grown
    squid that looks after itself, and nothing in them needs another squid.
    The last chapter is separate, optional, and plainly marked: it exists only
    for a player who chooses to turn Multiplayer on, and it says before
    anything else what that can cost.

  * NO QT. This is facts and words. The window that shows it is
    src/journey_window.py; the trainer and the tests use this directly.

GOING ONLINE IS NOT BREEDING. Stated once so nobody has to guess:

    Turning Multiplayer on lets your squid meet other squid. What it mostly
    does then is what squid do: size each other up, play, steal each other's
    rocks, and FIGHT. A fight has a winner and a loser, decided by the two
    squids' condition, experience and how hard each one's own network commits
    to it; it is recorded on both sides, remembered against that individual,
    and leaves a mark on both that does not fade.

    Breeding is something else: rare, and final. On any visit in which two
    squid stay within reach of each other for a couple of seconds there is a
    small chance (1 in 50 by default) that it is a mating - and only if the
    squid whose tank it is, is grown up (chapter 4), well, and not already a
    parent. That squid then lays an egg, STOPS EATING, and dies. It cannot be
    undone. The egg hatches into a new squid that inherits half of each
    parent's inborn synapses, some mutated; nothing either parent LEARNED or
    GREW is inherited. Nobody can make it happen and nobody should be told to
    try: it is the end of one squid's story, when it comes, not a goal.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

#: Seconds of play before a squid can count as grown up. Overridden by
#: config.ini [Lifecycle] maturity_seconds.
DEFAULT_MATURITY_SECONDS = 3600.0

#: A learned synapse this strong counts as something the squid has learned.
_LEARNED = 0.3


# ---------------------------------------------------------------------------
# Facts: everything a milestone may be judged on, gathered in one place
# ---------------------------------------------------------------------------
def gather_facts(logic=None, brain=None, squid=None) -> Dict[str, Any]:
    """Read a running game (or just a brain) into plain values.

    Every key is something that is simply true or false about this squid, or
    a number that can be read off it. Anything that cannot be read - no
    lifecycle, no plugins, a headless brain - comes back as its neutral value,
    so the journey can be told for a brain file as readily as for a live game.
    """
    from .brain_constants import (ACTION_BEHAVIOURS, ACTION_NEURONS, AQUARIUM_SENSE,
                                  CORE_STAT_NEURONS, INNATE_CONNECTIONS,
                                  LEARNED_ACTIONS, PLANT_SENSOR, SOCIAL_NEURONS,
                                  SOCIAL_SENSOR)
    if squid is None:
        squid = getattr(logic, 'squid', None)
    if brain is None:
        brain = getattr(getattr(logic, 'brain_window', None), 'brain_widget', None)

    facts: Dict[str, Any] = {
        'age_seconds': 0.0, 'alive': True, 'health': 100.0, 'sick': False,
        'meals': 0, 'learned_about_world': 0, 'knows_consequences': 0,
        'sees_plants': False, 'learned_actions': [], 'combinations': [],
        'hides_when_frightened': False,
        'multiplayer_on': False, 'hears_aquarium': False, 'met_a_squid': False,
        'social_neurons': [], 'fights_won': 0, 'fights_lost': 0,
        'aggression_scar': 0.0, 'is_parent': False, 'has_egg': False,
        'is_heir': False, 'maturity_seconds': DEFAULT_MATURITY_SECONDS,
        'mating_chance': 0.02, 'mating_contact_seconds': 2.0,
    }

    # ---- the body --------------------------------------------------------
    if squid is not None:
        statistics = getattr(squid, 'statistics', None)
        if statistics is not None:
            try:
                facts['age_seconds'] = float(statistics.get_total_age_seconds())
            except Exception:
                pass
            facts['meals'] = int(getattr(statistics, 'sushi_consumed', 0)
                                 + getattr(statistics, 'cheese_consumed', 0))
            facts['fights_won'] = int(getattr(statistics, 'fights_won', 0) or 0)
            facts['fights_lost'] = int(getattr(statistics, 'fights_lost', 0) or 0)
        facts['health'] = float(getattr(squid, 'health', 100.0) or 0.0)
        facts['sick'] = bool(getattr(squid, 'is_sick', False))
        facts['is_heir'] = bool(getattr(squid, 'inherited_from', None))
        lifecycle = getattr(squid, 'lifecycle', None)
        if lifecycle is not None:
            stage = getattr(lifecycle, 'stage', 'living')
            facts['alive'] = stage != 'dead'
            facts['is_parent'] = stage == 'parent' or bool(
                getattr(lifecycle, 'reproduction', None))
            facts['has_egg'] = getattr(lifecycle, 'egg', None) is not None

    # ---- the settings ------------------------------------------------------
    manager = getattr(logic, 'plugin_manager', None)
    enabled = getattr(manager, 'enabled_plugins', None) or ()
    facts['multiplayer_on'] = 'multiplayer' in {str(name).lower() for name in enabled}
    config = getattr(logic, 'config_manager', None) or getattr(brain, 'config', None)
    reader = getattr(config, 'get_lifecycle_config', None)
    if callable(reader):
        try:
            lifecycle_config = reader()
            for key in ('maturity_seconds', 'mating_chance', 'mating_contact_seconds'):
                if key in lifecycle_config:
                    facts[key] = float(lifecycle_config[key])
        except Exception:
            pass

    # ---- the brain ---------------------------------------------------------
    if brain is None:
        return facts
    weights = getattr(brain, 'weights', None) or {}
    positions = getattr(brain, 'neuron_positions', None) or {}
    innate = {(src, dst) for src, dst, _w in INNATE_CONNECTIONS}

    # Something about the world it was not born knowing: a synapse into one of
    # its drives that experience put there.
    facts['learned_about_world'] = sum(
        1 for edge, weight in weights.items()
        if edge[1] in CORE_STAT_NEURONS and edge not in innate
        and abs(weight) >= 0.1)

    causal = getattr(brain, 'causal_learning', None)
    if causal is not None:
        try:
            facts['knows_consequences'] = len(causal.known_contingencies())
        except Exception:
            pass

    facts['sees_plants'] = PLANT_SENSOR in positions
    facts['hears_aquarium'] = AQUARIUM_SENSE in positions
    facts['met_a_squid'] = SOCIAL_SENSOR in positions
    facts['social_neurons'] = [name for name in SOCIAL_NEURONS if name in positions]

    # An action it was not born able to do, that its own synapses now drive.
    learned = []
    for motor in LEARNED_ACTIONS:
        if any(dst == motor and src not in ACTION_NEURONS and weight >= _LEARNED
               for (src, dst), weight in weights.items()):
            learned.append(ACTION_BEHAVIOURS.get(motor, motor))
    facts['learned_actions'] = learned
    facts['hides_when_frightened'] = 'approaching_plant' in learned

    growth = getattr(brain, 'enhanced_neurogenesis', None)
    neurons = getattr(growth, 'functional_neurons', None) or {}
    facts['combinations'] = [name for name, neuron in neurons.items()
                             if getattr(neuron, 'combination', None)
                             and getattr(neuron, 'established', False)]
    # What its fights have left on it for good: how far its aggression now
    # rests above the zero it was grown at (src/fighting.scar).
    aggression = neurons.get('aggression')
    rest = getattr(aggression, 'resting_level', None)
    facts['aggression_scar'] = float(rest) if isinstance(rest, (int, float)) else 0.0
    return facts


# ---------------------------------------------------------------------------
# The journey
# ---------------------------------------------------------------------------
@dataclass
class Milestone:
    key: str
    title: str
    #: Shown before it is reached: what it takes.
    how: str
    #: Shown once it is: what it was judged on.
    reached_because: str
    test: Callable[[Dict[str, Any]], bool]
    #: A thing the PLAYER has to do, as opposed to something the squid does.
    players_part: bool = False
    #: Something that may or may not ever happen, and is not to be aimed for.
    #: It is shown, and never offered as "what comes next".
    by_chance: bool = False
    reached: bool = False


@dataclass
class Chapter:
    key: str
    title: str
    about: str
    milestones: List[Milestone] = field(default_factory=list)
    optional: bool = False
    #: Shown at the head of an optional chapter, before anything else.
    warning: str = ""

    @property
    def complete(self) -> bool:
        return all(m.reached for m in self.milestones)

    @property
    def started(self) -> bool:
        return any(m.reached for m in self.milestones)


def is_mature(facts: Dict[str, Any]) -> bool:
    """Grown up: old enough, and having learned from its own life.

    Both halves matter. Age alone would make maturity a timer; learning alone
    would let a squid a few minutes old breed. It has to have found out at
    least one thing about what its actions lead to, and come to do at least
    one thing it was not born able to do.
    """
    return bool(facts.get('alive', True)
                and facts.get('age_seconds', 0.0) >= facts.get(
                    'maturity_seconds', DEFAULT_MATURITY_SECONDS)
                and facts.get('knows_consequences', 0) >= 1
                and facts.get('learned_actions'))


def can_breed(facts: Dict[str, Any]) -> bool:
    """Whether a mating is POSSIBLE for this squid at all - everything on its
    own side. Whether one ever happens is another squid, and a small chance."""
    return bool(is_mature(facts) and facts.get('multiplayer_on')
                and not facts.get('is_parent') and not facts.get('sick')
                and facts.get('health', 0.0) > 0.0)


def _minutes(seconds: float) -> str:
    minutes = int(round(seconds / 60.0))
    if minutes >= 120:
        return f"{minutes / 60.0:.0f} hours"
    if minutes >= 60:
        return "an hour" if minutes < 90 else f"{minutes / 60.0:.1f} hours"
    return f"{max(1, minutes)} minutes"


def build_journey(facts: Dict[str, Any]) -> List[Chapter]:
    """The chapters of this squid's life, with what has been reached."""
    maturity = float(facts.get('maturity_seconds', DEFAULT_MATURITY_SECONDS))
    chance = float(facts.get('mating_chance', 0.02))
    odds = f"1 in {round(1 / chance)}" if chance > 0 else "none"
    contact = float(facts.get('mating_contact_seconds', 2.0))
    won = int(facts.get('fights_won', 0))
    lost = int(facts.get('fights_lost', 0))
    fought = won + lost
    learned = facts.get('learned_actions') or []
    learned_words = ', '.join(a.replace('_', ' ') for a in learned) or 'nothing yet'

    chapters = [
        Chapter('hatchling', "1. Hatchling",
                "It is born able to swim, eat and flee, and knows nothing else. "
                "Your part is to keep it alive while it finds its way.", [
            Milestone('hatched', "Hatched",
                      "It hatches.", "It is alive.",
                      lambda f: f.get('alive', True)),
            Milestone('first_meal', "Its first meal",
                      "Feed it. It swims to food it can see when it is hungry.",
                      f"It has eaten {facts.get('meals', 0)} time(s).",
                      lambda f: f.get('meals', 0) >= 1, players_part=True),
        ]),
        Chapter('learning', "2. Finding out",
                "Its brain starts to change. What goes together in its world "
                "becomes a synapse; what its own actions lead to, it starts to "
                "notice.", [
            Milestone('world', "It has learned something about its world",
                      "Give it a life with things happening in it: food, "
                      "sleep, a clean tank and a dirty one.",
                      f"{facts.get('learned_about_world', 0)} synapse(s) into "
                      f"its drives were not there when it hatched.",
                      lambda f: f.get('learned_about_world', 0) >= 1),
            Milestone('consequences', "It knows what one of its actions leads to",
                      "It has to do something often enough, with the same "
                      "result, to be sure of it. Eating is usually the first.",
                      f"It is confident of {facts.get('knows_consequences', 0)} "
                      f"consequence(s) of its own actions.",
                      lambda f: f.get('knows_consequences', 0) >= 1),
            Milestone('plant_sense', "It has seen a plant, and grown a sense for one",
                      "Put a plant in the tank (View > Decorations). The first "
                      "time one is in its view cone it grows a neuron for "
                      "seeing plants - it is not born with one.",
                      "It has a can_see_plant neuron, grown the first time it "
                      "saw one.",
                      lambda f: f.get('sees_plants', False), players_part=True),
        ]),
        Chapter('coping', "3. Looking after itself",
                "Rest, shelter and play are not instincts. Now and then it "
                "tries one for no reason, more often when it is curious or in "
                "trouble, and keeps what turns out to help.", [
            Milestone('learned_action', "It does something it was not born able to do",
                      "Let it be tired, frightened or bored sometimes: an "
                      "action only proves itself to a squid that needed it.",
                      f"Its own synapses now drive: {learned_words}.",
                      lambda f: bool(f.get('learned_actions'))),
            Milestone('hides', "It hides in a plant when it is frightened",
                      "This is how a squid brings its own anxiety down - no "
                      "neuron does it for it. It needs a plant it can see, and "
                      "enough frights to find out that hiding helps.",
                      "A learned path now drives it to shelter.",
                      lambda f: f.get('hides_when_frightened', False)),
            Milestone('combination', "It grew a neuron for something only it found out",
                      "When an action pays off only if two things are true "
                      "together, no synapse can say so, and it grows a neuron "
                      "for the pair. Look for one named for what it means.",
                      "Grown from its own trials: "
                      + (', '.join(n.replace('_', ' ')
                                   for n in facts.get('combinations') or [])
                         or 'a combination neuron') + ".",
                      lambda f: bool(f.get('combinations'))),
        ]),
        Chapter('grown', "4. Grown up",
                "A squid that has lived long enough and learned from it. This "
                "is a whole life: nothing beyond here is needed, and a squid "
                "kept at home is safe.", [
            Milestone('mature', "It is grown up",
                      f"It needs {_minutes(maturity)} of life, to know at least "
                      f"one consequence of its actions, and to have learned at "
                      f"least one action it was not born with.",
                      f"It is {_minutes(facts.get('age_seconds', 0.0))} old and "
                      f"has learned from its own life.",
                      is_mature),
        ]),
        Chapter('wider_water', "5. The wider water (optional)",
                "Other people's squid. This chapter only exists if you turn the "
                "Multiplayer plugin on, and everything in it is your choice. "
                "What squid mostly do when they meet is size each other up, "
                "play, take each other's rocks - and fight.",
                optional=True,
                warning=("Meeting other squid changes yours for good. It will "
                         "fight, and can be hurt badly enough to die. What it "
                         "wins and loses stays with it. None of this can be "
                         "undone, and none of it can happen while Multiplayer "
                         "is off: a squid kept at home is safe."),
                milestones=[
            Milestone('online', "You have opened the tank to other squid",
                      "Plugins > Plugin Manager > enable Multiplayer, and "
                      "accept its warning. It is never on unless you do this.",
                      "Multiplayer is on.",
                      lambda f: f.get('multiplayer_on', False) or f.get('met_a_squid', False),
                      players_part=True),
            Milestone('hears', "It knows another aquarium is out there",
                      "Another player's tank has to be reachable: on your own "
                      "network they find each other; for a friend elsewhere, "
                      "swap friend codes in Plugins > Multiplayer > Friends. "
                      "The first time a tank is heard, your squid grows a "
                      "sense for it; whether that draws it out or keeps it "
                      "home is its temperament, and then its experience.",
                      "It has grown aquarium_nearby.",
                      lambda f: f.get('hears_aquarium', False) or f.get('met_a_squid', False)),
            Milestone('meets', "It has met another squid",
                      "One of them has to visit the other. Your squid leaves "
                      "by itself, when its own network takes it out.",
                      "It has grown can_see_squid, the first time it saw one.",
                      lambda f: f.get('met_a_squid', False)),
            Milestone('fought', "It has been in a fight",
                      "A fight starts when two squid are face to face and one "
                      "of them is more aggressive than not - which a squid "
                      "becomes by going at another while its anxiety is high, and more so "
                      "with every fight after.",
                      f"It has fought {fought} time(s): won {won}, lost {lost}.",
                      lambda f: f.get('fights_won', 0) + f.get('fights_lost', 0) >= 1),
            Milestone('won', "It has won a fight",
                      "The better squid usually wins: the healthier, better "
                      "fed and more rested one, the one that has fought "
                      "before, and the one whose network commits harder. "
                      "Look after it and it fights better.",
                      f"It has won {won} of its {fought} fight(s).",
                      lambda f: f.get('fights_won', 0) >= 1),
            Milestone('veteran', "It is a veteran",
                      "Ten fights. Every one it has been in is remembered - "
                      "who, who started it, and why it went as it did - and "
                      "none of them has left it as placid as it was.",
                      f"{fought} fights, and its aggression now rests at "
                      f"{facts.get('aggression_scar', 0.0):.0f} where it began at 0.",
                      lambda f: f.get('fights_won', 0) + f.get('fights_lost', 0) >= 10),
        ]),
        Chapter('heir', "An heir (rare, and the end of this squid)",
                "This is not a stage to reach. It is something that can "
                "happen to a squid that meets others, and it happens seldom.",
                optional=True,
                warning=(f"On a visit in which two squid stay within reach of "
                         f"each other for {contact:g} seconds there is a "
                         f"{odds} chance of a mating, if the squid whose tank "
                         f"it is, is grown up, well and not already a parent. "
                         f"That squid lays an egg, STOPS EATING, and dies. It "
                         f"cannot be undone and cannot be arranged. The egg "
                         f"hatches into a new squid with half of each parent's "
                         f"inborn synapses, some mutated, and nothing either "
                         f"parent learned or grew; your saves and memories "
                         f"begin again with it."),
                milestones=[
            Milestone('breeds', "It has mated, and there is an egg",
                      "Nothing you do brings this about.",
                      "It is a parent. It has stopped eating, and its egg is "
                      "in the tank.",
                      lambda f: f.get('is_parent', False) or f.get('has_egg', False),
                      by_chance=True),
            Milestone('heir', "This squid is an heir",
                      "A squid hatched from a parent's egg.",
                      "It hatched from an egg and carries its parents' "
                      "inborn synapses.",
                      lambda f: f.get('is_heir', False), by_chance=True),
        ]),
    ]
    for chapter in chapters:
        for milestone in chapter.milestones:
            try:
                milestone.reached = bool(milestone.test(facts))
            except Exception:
                milestone.reached = False
    return chapters


def next_step(chapters: List[Chapter]) -> Optional[Milestone]:
    """The first thing not yet reached, in order - never one in a chapter the
    player has not chosen to start."""
    for chapter in chapters:
        if chapter.optional and not chapter.started:
            continue
        for milestone in chapter.milestones:
            if not milestone.reached and not milestone.by_chance:
                return milestone
    return None


def stage_name(chapters: List[Chapter]) -> str:
    """One word for where this squid is in its life."""
    reached = {m.key for c in chapters for m in c.milestones if m.reached}
    if 'breeds' in reached:
        return "Parent"
    if 'veteran' in reached:
        return "Veteran"
    if 'mature' in reached:
        return "Grown up"
    if 'learned_action' in reached:
        return "Juvenile"
    if 'consequences' in reached or 'world' in reached:
        return "Learner"
    return "Hatchling"


# ---------------------------------------------------------------------------
# Noticing a milestone the moment it is reached
# ---------------------------------------------------------------------------
class JourneyTracker:
    """Remembers what had been reached, so a new milestone can be announced
    once. The first reading after the game starts announces nothing: those
    were reached before."""

    def __init__(self):
        self._reached: Optional[set] = None

    def update(self, facts: Dict[str, Any]) -> List[Milestone]:
        chapters = build_journey(facts)
        now = {m.key: m for c in chapters for m in c.milestones if m.reached}
        if self._reached is None:
            self._reached = set(now)
            return []
        fresh = [m for key, m in now.items() if key not in self._reached]
        self._reached |= set(now)
        return fresh

    def reset(self) -> None:
        self._reached = None


# ---------------------------------------------------------------------------
# Words
# ---------------------------------------------------------------------------
def describe(facts: Dict[str, Any]) -> str:
    """The journey as plain text - for a terminal, a log or a test."""
    chapters = build_journey(facts)
    lines = [f"Stage: {stage_name(chapters)}", ""]
    for chapter in chapters:
        lines.append(chapter.title + ("  (complete)" if chapter.complete else ""))
        lines.append("  " + chapter.about)
        if chapter.warning:
            lines.append("  WARNING: " + chapter.warning)
        for m in chapter.milestones:
            mark = "[x]" if m.reached else "[ ]"
            lines.append(f"  {mark} {m.title}")
            lines.append("      " + (m.reached_because if m.reached else m.how))
        lines.append("")
    upcoming = next_step(chapters)
    if upcoming is not None:
        who = "Your part" if upcoming.players_part else "Next"
        lines.append(f"{who}: {upcoming.title} - {upcoming.how}")
    else:
        lines.append("There is nothing left that it has not done.")
    return "\n".join(lines)


def render_html(facts: Dict[str, Any]) -> str:
    """The journey as the small HTML the game's window shows."""
    from html import escape
    chapters = build_journey(facts)
    out = [f"<h2>{escape(stage_name(chapters))}</h2>"]
    upcoming = next_step(chapters)
    if upcoming is not None:
        who = "Your part" if upcoming.players_part else "What comes next"
        out.append(f"<p><b>{who}:</b> {escape(upcoming.title)}.<br>"
                   f"{escape(upcoming.how)}</p>")
    for chapter in chapters:
        done = " &#10003;" if chapter.complete else ""
        out.append(f"<h3>{escape(chapter.title)}{done}</h3>")
        out.append(f"<p><i>{escape(chapter.about)}</i></p>")
        if chapter.warning:
            out.append(f"<p><b>Before you start:</b> {escape(chapter.warning)}</p>")
        out.append("<ul>")
        for m in chapter.milestones:
            mark = "&#9745;" if m.reached else "&#9744;"
            text = m.reached_because if m.reached else m.how
            weight = "b" if m.reached else "span"
            out.append(f"<li>{mark} <{weight}>{escape(m.title)}</{weight}><br>"
                       f"<small>{escape(text)}</small></li>")
        out.append("</ul>")
    return "\n".join(out)
