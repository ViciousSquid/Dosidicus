# The social network inside the squid's network

A newborn squid has nothing in its brain about other squid. Not a sensor, not
a neuron, not a synapse. Everything it ever has for them grows, from its own
experience of meeting them, inside its ordinary network - a small network
within the network, which encodes what this one squid has come to know about
other squid and how it behaves around them.

A squid whose owner never enables multiplayer never meets another squid, and
never grows any of it.

## 1. How another squid reaches the brain

Through the senses the squid already has, and nothing else.

| What the squid perceives | Where it comes from |
|---|---|
| `squid_in_view` | Its own vision: a visitor is drawn in the tank as a scene item of category `squid`, and the view cone (72°, `src/vision_cone.py`) decides whether it is seen - exactly as for food. While visiting, the host reports what the visitor's eyes would see from its body, by the same cone. |
| `squid_proximity` | How close the nearest other squid is, 0-100 over 400 px (`vision_cone.proximity`) - felt whichever way it is looking. |
| `in_fight` | Its body is in a scuffle. |
| `squid_familiar`, `squid_recalled_good`, `squid_recalled_bad` | Its **own memory** of the individual in its view cone (`PeerLedger`, section 4 of [social learning](social-learning.md)). Never something the other squid or its host says. |
| `aquarium_heard` | Another aquarium is nearby: a peer's heartbeat heard on the network in the last 30 s (`venturing.peer_heard`). Not about a squid in view - how a squid comes to know there is somewhere to go. |

These are **percepts**, not neurons (`brain.perceive(name, value)`). A percept
does nothing to the network until the squid has grown a sense organ for it.

When a visitor is admitted to a tank, the resident's view cone swings onto it
and follows it for a few seconds (`Squid.notice`) - the orienting response -
then scanning resumes. Whether it is seen is still vision's call. On mobile,
where a squid sees the way it faces, the resident turns to face it.

## 2. What grows, and when

Neurogenesis grows each piece the first time it matters
(`EnhancedNeurogenesis.observe_social`, checked every tick, at no cost when no
squid is in view). There is no growth cooldown for these - the encounter is the
evidence - and at most one grows per tick.

### Sense organs - written by the world, like `can_see_food`

| Sense | Grows the first time... | Reads |
|---|---|---|
| `can_see_squid` | it sees another squid | tick box: 100 while one is in view, else 0 |
| `squid_nearby` | one comes within half the range (proximity > 50) | how close, 0-100 |
| `recognises_squid` | the squid in view is one it remembers | tick box |
| `remembers_bad_encounter` | it meets one it remembers badly | how badly, 0-100 |
| `remembers_good_encounter` | it meets one it remembers well | how well, 0-100 |
| `aquarium_nearby` | it hears another aquarium (no squid in view needed) | tick box |

Each is classified as a sensor only once grown (`ensure_grown_sensor`), so no
synapse can ever point at it; the world writes it every tick from its percept.
Binary ones are drawn as tick boxes, as `can_see_food` is.

`can_see_squid` and `aquarium_nearby` are the only ones grown whatever the
brain's size limit: without them a squid cannot know another squid, or another
aquarium, exists. The others respect the limit.

### Social neurons - grown from what the squid did

Hexagons, named for their purpose, one of each.

| Neuron | Grows the first time, with another squid in view... |
|---|---|
| `social_play` | its own `act_play` fires - it went to play with one |
| `social_flee` | its own `act_flee` fires - it fled from one |
| `social_fight` | it is in a fight |
| `aggression` | it goes at one (`act_play`) **while alarmed** (anxiety 60 or more) - a hostile approach |

Nothing chooses which of these a squid grows: it grows the ones its own network
has actually lived. A squid that only ever watches grows none; a timid squid
that flees grows `social_flee`; a bold one that approaches grows
`social_play`, and if it once approached in a temper, `aggression`.

`aggression` is different from the rest in one way: it reads **0 when the
squid is placid and relaxed, 100 when it is fully aggro**, and rests at zero.
A squid with no `aggression` neuron can be attacked but can never start a fight
([fights](fights.md)).

## 3. How it is wired - from the moment it grew

No table says what other squid, a memory or a fight means. Every new piece is
wired to what was happening in the squid when it grew
(`EnhancedNeurogenesis._social_birth_wiring`):

- **A new social neuron** takes input from every social sense reporting at
  that moment (weight 0.6 × reading) and from every drive away from rest by 10
  or more (weight up to ±0.5, by how far), and drives the actions the network
  was doing at that moment (weight 1.0). So `social_flee` grown while fleeing
  in alarm is fed by the sight of the squid and by alarm, and drives flight.
- **A new sense** feeds every social neuron active at that moment, and every
  drive stirred at that moment. A bad memory recognised while anxious is wired
  to anxiety; recognised calmly, it is not.
- **The first sighting** is the one exception, and it is personality:
  `can_see_squid` is wired by temperament (`SIGHTING_TEMPERAMENT`) - a timid
  squid's to anxiety and flight, an adventurous one's to curiosity and play, a
  stubborn one's to play and a little anxiety - the same way personality tilts
  the innate pathways (`INNATE_PERSONALITY_BIAS`). That is how different
  personalities react differently to the same first sight: some approach, some
  flee, some only watch. `aquarium_nearby` is wired the same way
  (`VENTURING_TEMPERAMENT`): an adventurous squid's excites its exploring
  (`act_move`) and curiosity, a timid one's inhibits exploring and stirs a
  little anxiety. That decides who ventures out (section 8).

Anything beyond birth - `aggression` coming to calm anxiety, a bad memory
coming to feed flight, a sense that turns out to matter more than another - is
**learned**, by the same plasticity as everything else in the network
(Hebbian co-activation, STDP, causal reward, sleep consolidation) plus one rule
for encounters ([social learning](social-learning.md)). Every change is
recorded.

## 4. How it is driven

The social senses are written by the world each tick. The social neurons are
ordinary network neurons: propagation computes them from their synapses, and
they push on the squid's own action neurons and drives. The decision engine
reads the winning action as it always does. Nothing in the plugin maps
"another squid" to an action.

`act_play` aimed at a squid in view sends the squid swimming at it, if it is
nearer than any rock (`brain_neuron_outputs._go_at_squid_in_view`; the host
does the same for a visitor's play, mobile likewise). Face to face, that is
contact - where play, competition, mating and fights happen.

## 5. What can change for good

- **Resting level.** Life can raise where a social neuron settles. A fight
  raises `aggression`'s resting level - by 4 for a fight lost, 2 for a fight
  won, up to 60 - and nothing ever lowers it
  (`EnhancedNeurogenesis.raise_resting_level`). Every rise is recorded on the
  neuron with its cause and kept in the save. A squid marked this way is
  never again as placid as it was.
- **Synapses.** Every encounter's outcome moves the sight sense's synapses
  ([social learning](social-learning.md)), and all the ordinary plasticity
  keeps working.
- **Pruning.** A social sense or neuron that is not useful is pruned like any
  other grown neuron when the brain is at its size limit - recorded, with the
  reason - and grows again the next time it matters. Two never are:
  `can_see_squid`, the squid's knowing that other squid exist at all, and a
  neuron life has marked for good (a raised resting level), so pruning cannot
  undo what a fight did.

## Where it sits

The social network has a band of its own in the brain view, **SOCIAL**, in
rose, below the rows of grown neurons - drawn only once its first member has
grown, so a squid that has never met another has no such band. Its members
sit in a fixed order, senses first (`can_see_squid`, `squid_nearby`, ...,
`aquarium_nearby`), then the social neurons; the other grown neurons use the
two rows above it (`brain_constants.SOCIAL_ROW`, `growth_positions`). The
same on Android.

## 6. Reading it

Every grown piece says why it exists. The Neuron Laboratory shows, for each:

- what it was created to represent ("This neuron was created to represent the
  binary concept of "I see another squid""; "...the concept of "attacking
  another squid"");
- the moment it grew and the evidence (`Deficit` evidence: what it sensed,
  what it did, how anxious it was);
- every synapse it was born with, and every change since, with the mechanism
  and cause;
- for a grown sensor, "A sense organ the squid grew for itself".

## 7. Across generations

No grown neuron is inherited. A hatchling inherits half its weights from each
parent - but only synapses between the neurons every newborn has
([reproduction](reproduction.md)) - so each generation grows its own social
network from its own encounters, on a slightly different innate wiring.

## 8. Venturing out

Enabling multiplayer only makes visiting possible (`src/venturing.py`). A
squid leaves its tank while, at once:

- its `aquarium_nearby` sense reports another aquarium,
- its exploring neuron, `act_move`, is firing, and
- that sense is pushing its exploring **up**: its synapse onto `act_move` is
  excitatory, so the other aquarium is part of why it explores.

Then exploring takes it to the nearest side of the tank (left or right, never
the surface or the sand), and there it asks the other tank's host to come in.
Not while fleeing, chasing food or merely drifting; and the edges stop it
otherwise, as they do with multiplayer off. A timid squid, born with the sense
inhibiting its exploring, stays home. Encounters move these synapses as they
move `can_see_squid`'s ([social learning](social-learning.md)): an
adventurous squid that keeps getting hurt comes to stay home too. The squid's
thoughts say when it leaves and why ("Another aquarium is nearby and I want to
explore it"); `Squid.why_not_venturing()` says why it has not.

### Coming home

Fear or tiredness, decided by the visitor's own network at home
(`VisitorMind.decide`):

- its flight winning the competition: it swims home ("I was frightened, so I
  swam home");
- its rest winning, or exhaustion (the collapse reflex, which nothing
  resists): it goes home to sleep. **A squid away from home always comes home
  to sleep** - one that is asleep while visiting, however it fell asleep, is
  home on the next tick.

A stubborn squid can hold off sleep while another need is stronger (hunger, or
curiosity x0.8, or anxiety x0.6, above 55%) - "Was tired but resisted sleep
due to stubbornness" - and does the next thing its network wants instead. Not
indefinitely: never once its sleepiness reaches 90, never when exhausted, and
at 100 it falls asleep where it is - and so comes home. The same rule holds
at home (`personality.resists_sleep`, used by the decision engine). Coming
home ends the visit as the squid's own choice (`departed`), so the encounter
is filed and its lessons learned. Otherwise it stays as long as its network
keeps it engaged.

## Code

| What | Where |
|---|---|
| Names and classification | `src/brain_constants.py`: `SOCIAL_SENSORS`, `SOCIAL_NEURONS`, `AGGRESSION_NEURON`, `ensure_grown_sensor` |
| Growth and birth wiring | `src/neurogenesis.py`: `SOCIAL_CONCEPTS`, `SOCIAL_SENSOR_GROWTH`, `SOCIAL_EXPERIENCE`, `SIGHTING_TEMPERAMENT`, `BIRTH_*`, `observe_social`, `_social_birth_wiring`, `raise_resting_level` |
| Percepts and resting levels | `src/propagation.py`: `perceive`, `CONCEPT_PERCEPTS`, `drive_external_neurons`, `propagate(resting=...)` |
| Vision | `src/vision_worker.py`, `src/vision_cone.py`, `Squid.notice` |
| Recognition | `plugins/multiplayer/encounter.py`: `perceive_recognition` |
| Venturing out | `src/venturing.py`; `Squid.is_venturing`, `check_boundary_exit`; `MultiplayerPlugin._perceive_aquariums`, `address_exit` |
| Coming home | `plugins/multiplayer/visitor_mind.py`: `HOMEWARD`, `go_home`, `tick`; `src/personality.py`: `resists_sleep` |
| Specification | `tests/test_social_concept.py`, `tests/test_venturing.py`, `tests/test_coming_home.py`; two real processes: `tools/test_venture_multiplayer.py` |
