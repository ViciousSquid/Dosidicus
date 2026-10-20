# Handoff: Dosidicus peer-to-peer evolution (branch `CANARY`)

This document is a complete brief for continuing the work: what was asked,
what is done, what is left, and the decisions already made about how. Read it
end to end before changing anything. Develop on `CANARY`, commit and push
there; do not open a pull request unless asked.

---

## 1. The brief

### The vision (owner's spec, in substance)

Transform Dosidicus multiplayer into a decentralised artificial-life ecosystem
where independently learning squid can encounter one another, interact, fight,
reproduce and evolve.

- Players participate simply by enabling multiplayer. **The squid retain
  complete autonomy**: their own neural networks decide whether to leave
  home, visit another aquarium, interact peacefully, compete or fight.
  Personality influences behaviour and aggression; memories and learned
  experiences shape future decisions.
- Fights are short, comical encounters shown by the existing animated cartoon
  fight cloud. Outcomes depend on the squid's neural responses, personality,
  experience and physical condition - **not a simple random roll**. Victories
  and defeats are permanently recorded and feed back into learning and
  behaviour.
- **All encounters have persistent, irreversible consequences.** Save games
  are permanently modified; experiences may alter neural development,
  relationships, reproduction, survival and future generations through
  inherited mutations.
- Enabling multiplayer presents a clear warning (exact text in section 4).
- **Core principle: players enable the possibility of encounters. Squid make
  their own decisions. Evolution emerges from the consequences.**

### Gameplay loop

1. Player enables multiplayer. Their aquarium becomes part of the peer-to-peer
   ecosystem, subject to connection and consent rules.
2. Squid becomes aware of nearby peers. Its personality, curiosity, learned
   responses and needs can influence whether it decides to venture out.
3. Squid voluntarily visits another aquarium. The host provides the
   environment; the visitor's brain remains on its own device.
4. An encounter unfolds: ignore one another, interact peacefully, compete over
   food or objects, fight, or potentially reproduce.
5. Consequences persist: changed memories, statistics or physiological states.
   Some events are irreversible.

### Emergent individuality (owner's example - the goal)

An adventurous youngster constantly visits, gets into fights, develops
negative memories, and over time becomes less willing to approach unfamiliar
squid. Another with the same starting personality has positive experiences and
becomes increasingly sociable. Same start, diverging lives.

### Standing rules from the owner (apply to everything)

- **No decision trees or pre-scripted behaviour rules.** Squid experience
  encounters through their own senses; their brains decide, based on
  personality and the configuration of their social neurons and sensors.
- **No new core neurons.** Nothing for other squid is innate. Neurogenesis
  grows what is needed, only when a squid actually encounters another.
- **Transparency and provenance always.** The player must always be able to
  read the squid's mind: why a neuron exists, why a synapse moved, why a fight
  started and why it ended as it did. Thoughts may go in the Decisions tab.
- **Personality acts through wiring**, never through `if personality == ...`.
- Predisposition to start a fight and ability to win one are **separate**.
- `act_ink` firing **always** produces ink (no dice, no cooldown).
- The simulation runs at **1 FPS deliberately**; design timings in whole
  seconds. Do not "fix" the frame rate.
- Performance: don't do unnecessary Python work; batch/vectorise with numpy
  where it pays; for small N, plain Python scalars are fine.
- Do the **big code changes first**, small ones after.
- Mild/boring encounters **should be forgotten**; ones that matter go to
  long-term memory.

---

## 2. Done (committed and pushed to `CANARY`)

| Commit | What |
|---|---|
| `13ccfd6` | Achievements CIRCLE OF LIFE, Fisticuffs!/Scuffle/Tussle/Slugfest; first multiplayer risk notice |
| `d3d4da8` | Beating pixel heart over a pair that has just mated |
| `69cf68f` | Every dead squid becomes a headstone (random from a sheet of 10; cannot be deleted, picked up or thrown; can be pushed; tooltip "RIP name"; at most 80% of the DPI-scaled squid). Death by neglect and by untreated sickness |
| `50f786a` | Other squid are sensed through vision, and grown senses/social neurons replace all `conspecific_*` neurons (details in section 3) |
| `a7cff7f` | "Enable peer-to-peer evolution?" Yes/No confirmation (desktop) / Enable-Cancel (mobile); mobile play goes at a squid in view |
| `3b6d87e` | Fights: grown `aggression` neuron, ability-based outcome, provenance, permanent aggression scar, encounter-driven learning, `act_ink` always inks, ink clouds and messages fade properly |

Earlier on the branch (before this work): release workflows for all platforms
(`e1f47c3`), shared brain interchange, the real two-instance gallery
(`docs/canary-gallery`, now stale - see section 5).

Test suite at the last commit: **683 passed**
(`QT_QPA_PLATFORM=offscreen python -m pytest tests android/tests -q -p no:cacheprovider`, ~50 s).

---

## 3. Decisions made (and why)

### Seeing other squid

- **Vision only.** A visitor is drawn in the tank as a scene item with
  `category == 'squid'`; `src/vision_worker.py` sees it through the view cone.
  The cone geometry is shared, Qt-free, in `src/vision_cone.py` (72 degrees),
  used by desktop vision, the multiplayer host (for the visitor's view) and
  mobile. `vision_cone.proximity()` gives closeness (0-100 over 400 px),
  felt whichever way the squid looks.
- **Percepts, not neurons.** The world reports `squid_in_view`,
  `squid_proximity`, `in_fight`, and from the squid's OWN memory (never the
  host's) `squid_familiar`, `squid_recalled_good`, `squid_recalled_bad`, via
  `brain.perceive(name, value)` (`src/propagation.py`). A percept reaches the
  network only through a sense organ neurogenesis has grown for it.
- A visitor admitted to the tank swings the resident's view cone onto it
  (`Squid.notice`, held ~4 s); on mobile the resident turns to face it.
- Heartbeats no longer draw a grey placeholder squid in the tank for every
  online peer (that was a bug: peers who never visited appeared and were
  "seen").
- All nine old `conspecific_*` neurons are retired: dropped with their
  synapses when an old save loads (`brain_constants.RETIRED_NEURONS`,
  `brain_io.normalise_brain`). No migration of `social`/`encounter` neurons is
  needed (owner: none exist in the wild).

### The social network inside the main network

Grown only from encounters; a squid that never meets another has none of it.

- **Sense organs** (`brain_constants.SOCIAL_SENSORS`), each grown the first
  time its percept reports something the network cannot represent
  (`neurogenesis.SOCIAL_SENSOR_GROWTH`), written by the world each tick like
  `can_see_food`, never by a synapse (registered as input sensors at growth
  and on load via `ensure_grown_sensor`):
  - `can_see_squid` (binary, tick box) - first sighting;
  - `squid_nearby` (analogue) - first time a squid comes within half range;
  - `recognises_squid` (binary) - first time it meets one it remembers;
  - `remembers_bad_encounter` / `remembers_good_encounter` (analogue).
- **Social neurons** (`brain_constants.SOCIAL_NEURONS`), hexagons, named for
  their purpose, one of each, grown from *experience* - the first time the
  squid's own network does the thing with another squid in view
  (`neurogenesis.SOCIAL_EXPERIENCE`):
  - `social_play` (its `act_play` fired), `social_flee` (`act_flee` fired),
    `social_fight` (it was in a fight - `in_fight` percept),
    `aggression` (it went at another squid - `act_play` - while alarmed,
    anxiety >= 60).
- `aggression` reads **0 = placid and relaxed, 100 = fully aggro**; it rests
  at zero (`brain_constants.AGGRESSION_NEURON`, added to propagation's
  rest-at-zero set).
- **Personality** enters only as `can_see_squid`'s birth wiring
  (`neurogenesis.SOCIAL_SENSOR_WIRING['can_see_squid']`, a table per
  personality - e.g. timid: anxiety and act_flee; adventurous: curiosity and
  act_play), so what a squid first does on seeing another is its network's
  response.
- Every growth carries its cause (`Deficit` evidence in the ledger); the
  Neuron Laboratory says "This neuron was created to represent the binary
  concept of "I see another squid"" (`neurogenesis.SOCIAL_CONCEPTS`), and
  calls a grown sensor "A sense organ the squid grew for itself".
- Social hexagons are NOT connectors: `is_connector_neuron` excludes them in
  `brain_widget`, `portable_brain`, `designer_canvas`; the renderer and the
  fallback painter draw them as named hexagons (pink `SOCIAL_COLOUR`). Mobile
  draws them as hexagons too (`ui/brainview.py`).
- Desktop `act_play` at a squid in view goes at it if it is nearer than any
  rock (`brain_neuron_outputs._go_at_squid_in_view`); the host does the same
  for a visitor's play intent; mobile likewise (`Simulation._squid_to_play_at`).
- **OPEN DECISION (owner's latest instruction, not yet implemented):** the
  fixed birth-wiring tables (`SOCIAL_WIRING`, `SOCIAL_INPUTS`, and the
  non-`can_see_squid` entries of `SOCIAL_SENSOR_WIRING`) are "hard rules" and
  must go. Replace with wiring taken from the experience that grew the neuron:
  inputs from the senses and drives that were active at that moment, outputs
  to what the network was doing/feeling then (sign by deviation from rest).
  Any further wiring (e.g. `aggression` lowering anxiety) must come only from
  learning, with provenance. Keep the per-personality `can_see_squid` table.
  Re-check the behaviour tests in `tests/test_social_concept.py` and
  `tests/test_fighting.py` afterwards (bold squid still approaches, timid
  still flees).

### Fights (`src/fighting.py`, Qt-free, shared by host and mobile)

- **Predisposition** = the squid's grown `aggression` neuron
  (`fight_predisposition`). A fight starts when two squid are in contact and
  one is more aggro than placid (`AGGRESSION_THRESHOLD = 50`); the more aggro
  one is the attacker. A squid that never grew `aggression` can be attacked
  but never starts a fight. The old `can_initiate_fight` personality gate is
  deleted; mobile's personality "fight bonus" table is deleted.
- **Ability** (`fitness`, `commitment`, `fighting_ability`, `side`) = body
  (health, hunger, sleepiness, sickness) x experience (fights fought/won) x
  commitment (attacker: aggression; defender: alarm/startle, or
  `social_fight` once it knows how to fight). So an attacked timid squid can
  be formidable. `resolve_fight` - the abler squid usually wins
  (`ABILITY_SHARPNESS = 2`), a little luck remains.
- The **visitor computes its own** `aggression`, `defence` and `fitness` at
  home and sends them with every action intent (encounter protocol **3**;
  `remote_protocol.ActionIntent`); the host combines with its resident's.
- **Consequences** (`CONSEQUENCES`): health/drives by outcome, applied where
  each squid lives. **Permanent mark**: `scar()` raises `aggression`'s
  resting level (+4 lost, +2 won, ceiling 60) via
  `EnhancedNeurogenesis.raise_resting_level` - only ever rises, history with
  causes on `FunctionalNeuron.resting_history`, kept in the save; propagation
  takes per-neuron `resting` levels.
- **Record**: every fight filed in long-term memory (`encounter.remember_fight`,
  key `fight:<id>`, category `social`) with who started it and why, both
  abilities, the chance and the consequences; `src/fighting.describe` gives
  the one-line summary ("Won a fight it started (aggression 80): ability 90
  against 70, so it had a 62% chance."). Fights also count in the encounter
  record with that individual (`EncounterSession.note_fight`) and in
  `PeerLedger` (fights won/lost per individual).
- Ink: `act_ink` binding probability 1.0, cooldown 0 (fires once per threshold
  crossing); mobile visitor ink is edge-triggered, no dice.

### Learning from encounters (`src/social_learning.py`)

- When an encounter is filed, its valence moves `can_see_squid`'s synapses -
  the sense for ANY squid, so lessons generalise to strangers: bad encounters
  weaken approach (act_play, curiosity, social_play) and strengthen alarm
  (anxiety, act_flee, social_flee); good ones the reverse. Mechanism
  `'encounter'` in `neural_provenance.MECHANISMS`, with the encounter's
  outcome and peer in the detail. Mild encounters (|valence| < 2) teach
  nothing.
- Encounter memories: the existing importance rule promotes ones that matter
  to long-term memory; mild ones stay short-term and fade (owner confirmed).

### Mating, eggs, death

- Mating only during a visit, decided by the **host**: 2% chance, rolled
  once per visit, after **2 s** of sustained contact (`config.ini`
  `[Lifecycle] mating_contact_seconds = 2.0`). Never happens without
  multiplayer.
- Parent stops eating, starves, dies; egg hatches into a **New Game** (the
  normal New Game egg animation, pixel-identical handoff - already tested in
  `tests/test_new_game_and_hatch.py`).
- Dead squid always become headstones; New Game keeps headstones.
- "Neglect" death: interpreted as hunger at its **maximum (100)** for too long
  (the owner said "hunger stays at zero"; hunger is 100 when starving in this
  engine). Flag this to the owner if not yet confirmed.

### Warning (exact text, `src/lifecycle.py`)

Title: **Enable peer-to-peer evolution?**

> Enabling multiplayer introduces new experiences that may permanently alter
> your squid's behaviour, neural development and life.
>
> Encounters may result in fights, reproduction or even death.
>
> Changes to your squid and its saved state cannot be undone.

Desktop: Yes/No (default No), asked until accepted, then remembered in
`config.ini`; declining leaves multiplayer off. Mobile: Enable/Cancel before
Nearby opens, remembered by a flag file in `user_data_dir`.

### Inheritance (in progress - see section 4)

- The hatchling inherits **half its weights from each parent**: each parent
  contributes a random half of its synapses between newborn neurons only
  (`src/inheritance.gamete`) - no grown neuron is inherited. The resident's
  half is taken at mating; the mate's half is made on the mate's own machine
  and sent as a new `gamete` message (the only time weights cross the wire;
  strictly validated by `remote_protocol.Gamete` / `inheritance.clean_gamete`).
  Both are kept on the egg (`Lifecycle.add_genes`, `egg['genes']`, saved).
- At hatch: newborn wiring overlaid with both halves (shared synapse: one
  parent chosen at random), 10% of inherited weights mutate by up to +/-0.1;
  every inherited synapse recorded with mechanism `'inheritance'`, parent and
  whether it mutated.

---

## 4. In progress: inheritance

Desktop inheritance is committed (the commit after this document's first
version): `src/inheritance.py` (`gamete`, `clean_gamete`, `inherit`);
`src/lifecycle.py` (`egg['genes']`, `add_genes`, `egg_genes`, validated on
load); `src/tamagotchi_logic.py` (resident's half taken in
`record_reproduction` - never blocks laying the egg - and `add_mate_genes`);
`remote_protocol.Gamete` / `MSG_GAMETE` and `packet_validator` allowing
`'gamete'`; `VisitorMind._send_gamete` (sent each time it hears of the mating,
cached per mating); `MultiplayerPlugin.handle_gamete` (kept only for its own
egg, from that mating, from that mate); `main.py` `_begin_new_life` applies
`inherit()` to the hatchling; `inheritance` is in the APK's `SHARED_MODULES`.
`tests/test_new_game_and_hatch.py` asserts the hatchling inherits with
provenance and that nothing grown or remembered carries over.

Remaining for this task:

1. Dedicated tests (`tests/test_inheritance.py`): a gamete is half, and only
   synapses between newborn neurons; `clean_gamete` rejects bad input;
   `add_genes` once per parent, only for its own egg/mating, survives
   save/load; the host keeps a visitor's gamete only from the mate, through
   `handle_gamete`; hatch combines both halves with provenance and mutation.
2. Mobile inheritance (with mobile mating, section 5).

## 5. Left to do

Priority order agreed with the owner: big code changes first.

### Big

- **Experience-derived birth wiring for social neurons/sensors** (section 3,
  "OPEN DECISION") - remove the hard-rule tables.
- **Rocks: conscious aim and velocity** (task "Conscious aim and velocity").
  Throwing exists already. Aim = what the squid is attending to (the target
  in its view cone - another squid if one is there, else where it looks);
  velocity = from the network (activation of what drives the throw); both
  recorded with provenance. Whether to throw stays the network's existing
  decision; no scripted targeting or intent. A squid hit by a rock (or seeing
  one land close) only *feels* it (percepts) and its own network reacts -
  intent is never transmitted. Resident<->visitor via the host. Hits recorded
  in the encounter memory. Desktop + mobile. (Mobile throws are currently a
  random direction and speed: `Simulation._update_rock_play`.)
- **Social knowledge in Laboratory, Memory tab and Decisions tab**: Memory tab
  gets a Social Knowledge view separate from environmental memories (known
  individuals: name, personality, encounters, fights won/lost, matings, how
  it went; each fight with who started it and why, abilities, chance,
  consequences). Laboratory: social overview (grown social senses/neurons and
  why they grew), `aggression` described in words (placid .. fully aggro) with
  its resting level and every permanent rise and its cause, encounter-driven
  synapse changes. Decisions tab: social thoughts as they happen ("I see
  another squid", "I remember that one - it beat me", "I'm getting aggro",
  "I attacked", "I fought back", "I fled", "I played"), each with its reason.
- **Squid senses nearby aquariums and decides itself to venture out**
  (gameplay loop 2-3): peers discovered -> a percept -> a sense organ grown the
  first time; exit through an edge only when its own network is driving it
  there (exploring/moving, not fleeing, chasing food or fallback wandering).
  Currently any edge contact with multiplayer on exits (`Squid.check_boundary_exit`).
- **Mobile parity**: mating (host-decided, 2%, 2 s contact) with egg,
  starvation and hatch, inheritance; neglect/sickness deaths; headstones;
  recognition percepts from mobile memory (mobile has no `PeerLedger`);
  `src/lifecycle.py` is already shipped to mobile.

### Smaller

- **SOCIAL band** in the brain layout - created only when the first social
  sense/neuron is grown (never at birth). Plan: `SOCIAL_ROW` at the bottom of
  the growth zone (y ~682, band ~646-716); other grown neurons use the rows
  above (`GROWTH_ROW_YS_BESIDE_SOCIAL`); `growth_positions` places social
  members in canonical order (senses then neurons); `neuron_row` returns
  `'social'` (`ROW_COLORS`/`ROW_BAND_COLORS['social']`); renderer
  (`brain_render_worker._draw_row_bands/_draw_row_labels`) and mobile
  `ui/brainview.py` draw it only when a member exists; HeadlessBrain needs a
  `relayout_grown_neurons`.
- **Pruning**: social neurons/sensors prunable by the normal pruning when not
  useful; `can_see_squid` protected (`neurogenesis.intelligent_pruning`
  currently skips anything with `represents_concept`).
- **Host and guest always use both swim frames, never in sync** (desktop
  `remote_entity_manager` visuals vs `Squid` frames; mobile `tankview`).
- **Headstone tooltip**: name, age at death, fights won and lost (stored with
  the headstone).
- **Contested object flashes dark red**: when a fight arises from a contest
  over an object, tint it dark red and flash it from 2 s before the scuffle
  (a lead-in after the fight is decided) until 2 s after. Desktop + mobile.
- **Docs**: `plugins/multiplayer/docs/` describing social behaviours (senses,
  social neurons and how the social network grows inside the main network,
  personality-as-wiring, memory/recognition, fights, consequences, ink,
  mating, inheritance). Also describe this to the owner in chat.
- **README** (`plugins/multiplayer/README`) - keep in step with the above.

### Verification and release

- **Real two-instance test**: run two game instances with multiplayer
  enabled, like a user would; verify discovery, consent, a visit with both
  squid in one tank, personality-dependent interaction (approach/flee,
  fights with cloud, mating heart, headstones). `tools/capture_multiplayer.py`
  exists from an earlier approach; regenerate `docs/canary-gallery` (its JSON
  captures still show the retired `conspecific_*`/`encounter` design).
- **Release APK** for distribution (`.github/workflows/android-release.yml`;
  signing via repository secrets). Note: the README once mentioned a release
  key at `/workspace/dosidicus-release-signing` - a key custody concern raised
  in the original audit; prefer CI secrets.

---

## 6. Where things are

| Area | Files |
|---|---|
| Vision | `src/vision_worker.py`, `src/vision_cone.py`, `src/squid.py` (`notice`) |
| Percepts, propagation | `src/propagation.py` (`perceive`, `CONCEPT_PERCEPTS`, `resting`) |
| Social growth | `src/neurogenesis.py` (`SOCIAL_*` tables, `observe_social`, `raise_resting_level`), `src/brain_constants.py` (`SOCIAL_SENSORS`, `SOCIAL_NEURONS`, `AGGRESSION_NEURON`, `ensure_grown_sensor`, `RETIRED_NEURONS`) |
| Fights | `src/fighting.py`; host: `plugins/multiplayer/mp_plugin_logic.py` (`_who_starts_a_fight`, `resolve_fight`), `host_body.py`; visitor: `visitor_mind.py` (`_live_through_fight`); mobile: `android/dosidicus_mobile/engine/simulation.py` (`_update_fight`) |
| Learning from encounters | `src/social_learning.py`; called from `mp_plugin_logic.close_encounter` and `VisitorMind._learn_from` |
| Memory of individuals | `plugins/multiplayer/peer_ledger.py`, `encounter.py` (`remember_fight`, `perceive_recognition`, `active_social_neurons`) |
| Provenance | `src/neural_provenance.py` (`MECHANISMS` incl. `encounter`, `inheritance`) |
| Laboratory | `src/laboratory.py` (`_card_identity`, `_role`) |
| Lifecycle, warning | `src/lifecycle.py` |
| Inheritance | `src/inheritance.py`, `main.py` (`_begin_new_life`) |
| Protocol | `plugins/multiplayer/remote_protocol.py`, `identity.py` (`ENCOUNTER_PROTOCOL_VERSION = 3`), `packet_validator.py` |
| Mobile | `android/dosidicus_mobile/engine/{simulation,squid,constants}.py`, `ui/{brainview,nearby_screen,tankview}.py`; shared modules list in `android/prepare_apk.py` |
| Specs as tests | `tests/test_social_concept.py`, `tests/test_fighting.py`, `tests/test_reproduction_lifecycle.py`, `tests/test_remote_mind_stage1.py`, `tests/test_social_consequences_stage2a.py`, `tests/test_ink_cloud_fades.py` |

Commit messages end with the attribution lines the session supplies. Run the
full suite before every push.
