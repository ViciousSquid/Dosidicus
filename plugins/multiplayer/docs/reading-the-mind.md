# Reading a squid's social mind

Everything a squid knows about other squid can be read, and it is kept apart
from what it knows about its tank. None of it is a summary someone wrote for
the player: it is read from the squid's own neurons, synapses, provenance and
memories (`src/social_knowledge.py`, shared by desktop and mobile).

## Memory tab: Social

Social memories (category `social`: encounters `peer:<uuid>`, fights
`fight:<id>`, rock strikes `rock:<throw_id>`) live on their own page. Short-
and long-term memory show only the tank. The page opens with what the squid
knows:

- **Aggression** in words, from *placid and relaxed* through *calm*, *edgy*,
  *spoiling for a fight* (50, enough to start one), *aggressive* to
  *fully aggro*. It shows where the level rests, and each event that raised
  the resting level for good, with when and why.
- **Towards squid it does not know**: how it meets any squid. This is the
  pull of `can_see_squid`'s synapses towards approach (play, curiosity,
  social play) against alarm (anxiety, fleeing, social flee). It also says
  how much of that pull its encounters put there (mechanism `encounter`),
  as opposed to its birth.
- **Its social network**: each social sense and neuron it has grown, what it
  stands for, and why it grew (its birth record).
- **Squid it would recognise**: each remembered individual, with
  encounters, fights won and lost, rock hits, matings, and whether it
  remembers that squid fondly or badly. Mild encounters are forgotten, so
  they never appear here.
- **Fights**: each fight says who started it and why (the attacker's
  aggression), or what the squid defended itself with, and why it ended as
  it did (both abilities and the chance).

The social memory cards follow, written as sentences and coloured by how
they went.

A squid that has grown no social sense or neuron has a blank Social page
with one line, translated into every language (`social_tab_no_neurons`):
"This squid has not grown any socialisation neurons: Enable Multiplayer".

## Neuron Laboratory

- **Deep Inspector**: any social sense or neuron gets a *What does it know of
  other squid?* card. For `aggression` it shows the level in words, the
  resting level, whether it would start a fight now, and every permanent rise
  with its cause. For `can_see_squid` it shows how the squid meets strangers
  and how much of that its life taught it.
- **Live Overview**: an *Its social network* card, shown only once something
  has grown.

## Decisions tab: Social thoughts

Social events are told as the squid's own thoughts, each with its reason
(`social_knowledge.think`):

- growing a social sense or neuron: what happened, and what it now stands for;
- starting a fight ("I went for Manuel: my aggression was 72, past the 50 it
  takes"), or being attacked ("Manuel came at me. I fought back with my alarm
  at 85");
- how a fight ended ("I lost: my ability 40 against their 70 gave me a 30%
  chance");
- a permanent rise in aggression ("my aggression rests at 8 now, not 0, and
  always will - I lost a fight with Manuel");
- what an encounter taught it about squid in general ("I am warier of squid,
  even ones I do not know").

The panel appears once the squid has had its first social thought. A
**Squid** chip joins the perception chips once it has grown the sense to see
one.
