# Mating, eggs and inheritance

Reproduction only ever happens during a visit, so a squid whose owner never
enables multiplayer never mates and never lays an egg.

## Mating

There is no mating action, in either brain. Each squid's own network moves its
own body; the **host** works out what that means in its tank, as it does a
contest (`HostBody._resolve_contact`):

- if the visitor stays within reach of the resident for **2 seconds**, the
  host makes **one roll for the whole visit**, at **2%** (`config.ini`
  `[Lifecycle] mating_chance`, `mating_contact_seconds`);
- only a resident that is at home, alive and has never reproduced can mate.

On success the resident becomes a parent and lays its egg in its own tank, in
one record and one save (`src/lifecycle.py`); a pixel heart beats over the
pair; the visitor is told (and remembers the mating against that individual).

## The parent and the egg

A parent stops eating. Its hunger rises as anyone's does; once starving, it
loses health until it dies (`CIRCLE OF LIFE` achievement). Then its egg hatches - into a New
Game, shown by the ordinary New Game egg animation, handed over from the egg
pixel for pixel. The parent's headstone stays in the tank.

## Death, and what comes after

Any squid can die, not only a parent (`src/lifecycle.py`): of **neglect**
(left at its hungriest for 5 minutes of play), of **sickness** left 10
minutes without medicine, of its **injuries** once rocks and fights have left
it no health, or - a
parent - **starved**. A headstone is laid where it died, and its epitaph keeps
its name, how long it lived and its fights won and lost (hover on desktop,
tap on Android). A few seconds later a new squid hatches in the same tank:
from the parent's egg if there is one, otherwise from a fresh egg. Headstones
are never removed.

## Android

The Android game lives the same life through the same code: `HostBody`
resolves a mating on an Android host with the same chance and contact time,
the egg carries both gametes over the Nearby link, a parent does not eat or
go visiting, and the hatchling inherits as below
(`android/dosidicus_mobile/engine/simulation.py`: `record_reproduction`,
`on_squid_died`, `continue_after_death`).

## Inheritance

A hatchling inherits **half its weights from each parent**
(`src/inheritance.py`):

- At mating, each parent contributes a **gamete**: a random half of its
  synapses between the neurons every newborn has. No grown neuron is
  inherited - no social neuron, no aggression - so each generation grows its
  own social network from its own life.
- The resident's half is taken from its brain as the mating is recorded. The
  mate's half is made on the mate's own machine and sent to the host as a
  `gamete` message - **the one time any of a squid's weights cross the
  wire**, reduced on arrival to exactly that and kept only for the host's own
  egg, from that mating, from that mate. Both halves travel with the egg in
  the save.
- At hatch, the newborn's wiring is overlaid with both halves - a synapse both
  parents passed on comes from one of them, at random - and a tenth of the
  inherited weights mutate by up to ±0.1. Each inherited synapse is recorded
  with mechanism `inheritance`, the parent it came from and whether it
  mutated.

So a lineage drifts: what each parent's life did to its innate wiring is half
passed on, with a little variation, and selection is whatever the squid's
lives make of it.

## Code

| What | Where |
|---|---|
| Mating | `plugins/multiplayer/host_body.py`: `_resolve_contact`; `mp_plugin_logic.record_mating` |
| Parent, egg, death | `src/lifecycle.py`; `src/tamagotchi_logic.py`: `record_reproduction`, `begin_egg_hatching` |
| Inheritance | `src/inheritance.py`; `Lifecycle.add_genes`; `remote_protocol.Gamete`; `VisitorMind._send_gamete`; `MultiplayerPlugin.handle_gamete`; `main.py` `_begin_new_life` |
| Android | `android/dosidicus_mobile/engine/simulation.py`, `peer_visit.py` (`_on_mating`, `_keep_gamete`) |
| Specification | `tests/test_reproduction_lifecycle.py`, `tests/test_new_game_and_hatch.py`, `android/tests/test_mobile_lifecycle.py` |
