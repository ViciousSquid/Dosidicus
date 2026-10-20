# Social learning: how encounters change a squid

Two squid can start with the same personality and end up nothing alike.

> An adventurous youngster constantly visits other aquariums, gets into fights
> and develops negative memories. Over time it becomes less willing to
> approach unfamiliar squid. Another with the same initial personality has
> consistently positive experiences and becomes increasingly sociable. Their
> personalities began similarly, but their life histories made their
> behaviour diverge.

That divergence is not scripted anywhere. It comes from four things a squid
does with every encounter, each recorded so the player can always see why its
squid is the way it is.

## 1. It grows what it needs - from what happened

The first time it sees another squid, comes close to one, recognises one,
plays with one, flees from one, fights or attacks, it grows the sense or
social neuron for that, wired to what was happening in it at that moment. Two
squid with different lives grow different social networks, wired differently.
See [the social network](social-network.md).

## 2. It remembers individuals - the ones that mattered

Every encounter is measured while it happens (`EncounterSession`): what this
squid did, what the other was seen doing, how close they came, objects that
changed hands, fights and who won them, a mating. When it ends - the other
squid out of sight for 6 s, or 3 minutes have passed - it is closed into a
record of what happened and **how it went**:

- **valence** = the change in happiness + satisfaction + ¼ curiosity −
  anxiety over the encounter, − 6 per object lost, + 4 per object taken,
  − 8 per fight lost, + 5 per fight won. Measured, not judged: two squid can do
  the same things and have it go differently.
- **outcome**, a label for the Memory tab: mated, beaten, won a fight, robbed,
  took, bad, good, quiet. Nothing reads it to decide anything.

The record is filed as an ordinary memory of **that individual**, key
`peer:<its uuid>`, in the squid's own `MemoryManager`
(`PeerLedger.record`). Whether it lasts is the memory system's ordinary rule:
importance = 3 + 0.22 × |valence|, + 2 if an object changed hands, + 2.5 per
fight, + 3 for a mating, + 1 for a first meeting; at 7 or more it goes to
long-term memory at once and survives the session. **A mild, boring encounter
does not reach 7: it stays in short-term memory and is forgotten.** A fight
always matters; each fight is also filed on its own, in long-term memory, with
everything behind it ([fights](fights.md)).

Brief glimpses (under 2 s, with nothing happening) leave no record at all.

## 3. It recognises them later - from its own memory

When a squid has a squid in its view cone, what it remembers of **that**
individual reaches its brain as percepts (`perceive_recognition`):

| Percept | From memory |
|---|---|
| `squid_familiar` | how many times it has met this one (100 after six) |
| `squid_recalled_bad` | how badly those meetings went, summed |
| `squid_recalled_good` | how well they went, summed |

The first time any of these reads something, the squid grows the sense for it
(`recognises_squid`, `remembers_bad_encounter`, `remembers_good_encounter`),
wired to what it felt then - a squid recognised in fear is wired to fear.
A stranger reads zero everywhere. A memory of one individual never colours a
meeting with another: recall is by the individual's identity, and only what
this squid itself remembers counts - nothing the other squid, or its host,
says. A forgotten encounter is not recalled: that squid is a stranger again.

## 4. It generalises - to every squid, strangers included

When an encounter is filed, how it went moves the synapses leaving
`can_see_squid` - the sense for **any** squid - so the lesson applies to squid
it has never met (`src/social_learning.py`):

- a **bad** encounter (beaten, robbed, frightened) weakens the pull towards
  other squid - `can_see_squid` → `act_play`, `curiosity`, `social_play` - and
  strengthens alarm at them - → `anxiety`, `act_flee`, `social_flee`, creating
  that synapse if it has none;
- a **good** one does the opposite.

Each encounter moves each synapse by 0.004 per point of valence, at most 0.15.
Encounters below ±2 valence teach nothing. Six bad encounters (valence −25
each) take an adventurous squid's pull to play from 0.8 to 0.2 and grow an
alarm synapse to 0.6: met by a stranger, it no longer approaches. Six good ones
(+20 each) take the pull to 1.0: it approaches straight away. The rule is the same for every squid;
the lives are not.

Every change goes through the brain's `apply_weight_change` with mechanism
`encounter` and the encounter that caused it - its outcome, its valence, the
squid it was with - so the Laboratory can show synapse by synapse how a life
changed how this squid meets others ("...because an encounter with another
squid went well or badly").

## 5. Some changes never go back

- A fight raises `aggression`'s resting level for good - by 4 when lost, 2
  when won, up to 60 - so a much-fought squid is never again fully placid. The
  neuron keeps every rise and its cause.
- A fight costs health; a lost one costs more.
- Statistics count every fight won and lost, every encounter, every mating.
- The save holds all of it. Nothing in multiplayer is undone by leaving it.

## 6. And the ordinary learning keeps going

Everything above sits on top of the plasticity every neuron in the network
already has - Hebbian co-activation, spike timing, causal reward ("an action
it took led to a result worth repeating"), sleep consolidation. Social neurons
and senses are ordinary neurons to all of it, so a squid can also learn, with
no rule saying so, that attacking calms it, that a familiar squid is safe, or
that fleeing from one particular squid helps.

## Reading a squid's social mind

| Question | Where |
|---|---|
| Why does this social neuron/sense exist? | Neuron Laboratory: what it represents, when and why it grew, its birth wiring |
| Why did this synapse change? | Neuron Laboratory / synapse history: mechanism (`encounter`, `hebbian`, ...) and cause |
| What does it remember of a squid? | Memory tab: `peer:` memories (who, how it went, what happened) |
| Why did a fight start, and why did it end that way? | Memory tab: `fight:` memories |
| How aggro is it, and is that for good? | `aggression` neuron: its reading, and its resting level with every rise and cause |

A dedicated Social Knowledge view in the Memory tab, an `aggression` card in
the Laboratory, and social thoughts in the Decisions tab are planned (see
`docs/HANDOFF-peer-to-peer-evolution.md`).

## Code

| What | Where |
|---|---|
| Encounter measurement | `plugins/multiplayer/encounter.py`: `EncounterSession`, `EncounterRecord`, `OUTCOME_DRIVES` |
| Memory of individuals, recall | `plugins/multiplayer/peer_ledger.py`; `encounter.perceive_recognition` |
| Generalising to strangers | `src/social_learning.py`: `learn_from_encounter` |
| Permanent marks | `src/fighting.py`: `scar`; `src/neurogenesis.py`: `raise_resting_level` |
| Provenance | `src/neural_provenance.py`: `MECHANISMS` |
| Specification | `tests/test_social_consequences_stage2a.py`, `tests/test_fighting.py` |
