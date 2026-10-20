# Fights

Short, comical scuffles under one cartoon cloud - with real, lasting
consequences, and a reason for everything.

Two questions are kept apart on purpose:

- **Does a squid start a fight?** Its predisposition - read from its network.
- **Does it win?** Its ability - worked out when the fight happens.

An aggressive squid can fight often and lose often. A timid squid that rarely
fights can be formidable when it is attacked. Neither is decided by its
personality label or by dice (`src/fighting.py`, shared by the desktop host
and the mobile game).

## Starting a fight - predisposition

A fight starts only when two squid are **in contact** and one of them is
**more aggro than placid**: its `aggression` neuron reads 50 or more
(`fight_predisposition`, `AGGRESSION_THRESHOLD`). The more aggro one is the
attacker. If neither is, they are just in contact - playing, competing over
something, perhaps mating.

`aggression` is a social neuron the squid grows the first time its own network
goes at another squid while alarmed ([the social network](social-network.md)).
It reads 0 when the squid is placid and relaxed and 100 when it is fully
aggro, rests at zero, and is driven by whatever fed it at birth and since -
the sight of a squid, closeness, bad memories, alarm. **A squid that never grew
one can be attacked, but never starts a fight.** Personality only shows
through how the squid's network was wired and what it has lived through.

On the host, the resident's aggression is read from its brain; the visitor's
comes with each of its intents, worked out on its own machine.

## Winning a fight - ability

When the scuffle ends, each side's ability (`side`, `fighting_ability`) is:

**fitness × commitment**

- **Fitness** (`fitness`) = body × experience.
  - Body: health; hunger past the midpoint costs up to half; tiredness past
    the midpoint costs up to half; sickness costs 40%.
  - Experience: +6% per fight ever fought (up to ten), +4% more per fight won
    (up to ten).
- **Commitment** - how hard the network throws itself in (0-100; ability runs
  from half, uncommitted, to one and a half times, fully committed):
  - the **attacker** commits with its aggression;
  - the **defender** commits with its alarm (anxiety above rest, or being
    startled) - or with its `social_fight` neuron once it has learned how to
    fight, if that is stronger.

So an attacked timid squid, fit and frightened, commits fully and can beat a
hungry, hurt, fully aggro attacker.

The winner is drawn from the two abilities (`resolve_fight`): chance =
a² / (a² + b²). Twice as able wins four times in five. A little luck remains,
as in any scuffle - but it is not a coin flip.

A visitor works out its own aggression, defence (what it would commit if
attacked) and fitness at home and sends them with every intent (encounter
protocol 4); the host combines them with its resident's and resolves the
fight in the tank that owns both bodies.

## What a fight does

To each squid, applied on the machine it lives on (`CONSEQUENCES`):

| | Health | Happiness | Satisfaction | Anxiety |
|---|---|---|---|---|
| Won | −3 | +8 | +15 | −5 |
| Lost | −8 | −10 | −5 | +15 |

And, permanently:

- its `aggression` resting level rises - 4 for a loss, 2 for a win, up to 60 -
  and never falls (`scar`); the neuron records every rise and its cause;
- its fights won/lost statistics, and the Fisticuffs!/Scuffle/Tussle/Slugfest
  achievements;
- its memory of that individual counts the fight, and the encounter's valence
  moves how it meets every squid ([social learning](social-learning.md));
- being in the fight is itself an experience: the first one grows
  `social_fight`.

## The record

Every fight is filed in the squid's long-term memory (category `social`, key
`fight:<id>`, `encounter.remember_fight`) with:

- who started it, and why (the attacker's aggression);
- both sides' role, fitness, body, experience, commitment and ability;
- the chance this squid had, and the result;
- the consequences applied to it.

and a one-line summary, e.g. *"Won a fight it started (aggression 80):
ability 90 against 70, so it had a 62% chance."* The same line is shown as
the fight ends.

## Ink

Whether a squid inks is entirely its network's. `act_ink` firing - crossing
its threshold - **always** produces ink, once per firing: no chance, no
cooldown, on desktop and mobile alike. A fight can make a squid ink only by
what it does to it (alarm, startle) and how its network responds; no fight
code ever inks.

## Code

| What | Where |
|---|---|
| The model | `src/fighting.py` |
| Host: who starts it, resolution, record | `plugins/multiplayer/mp_plugin_logic.py`: `_who_starts_a_fight`, `show_fight_cloud`, `resolve_fight` |
| Visitor's side | `plugins/multiplayer/visitor_mind.py`: `decide` (sends aggression/defence/fitness), `_live_through_fight` |
| Mobile | `android/dosidicus_mobile/engine/simulation.py`: `_update_fight`, `_resolve_fight` |
| Specification | `tests/test_fighting.py`, `tests/test_reproduction_lifecycle.py` (FightCloudTests), `tests/test_fight_statistics.py` |
