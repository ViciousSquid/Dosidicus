"""
brain_constants.py - Shared constants for Dosidicus-2 brain system

This file defines the canonical neuron categories used across:
- brain_widget.py
- brain_tool.py  
- brain_designer.py
- brain_neuron_hooks.py

Import from here to ensure consistency.
"""

# =============================================================================
# REQUIRED NEURONS - Mandatory for all brain designs
# These 8 neurons MUST exist in any valid Dosidicus brain.
# =============================================================================

# Core stat neurons - positions match brain_widget.py's original_neuron_positions
CORE_NEURONS = {
    "hunger": (127, 81),
    "happiness": (361, 81),
    "cleanliness": (627, 81),
    "sleepiness": (840, 81),
    "satisfaction": (271, 380),
    "anxiety": (491, 389),
    "curiosity": (701, 386),
}

# can_see_food is MANDATORY - the squid must be able to see food
# This is separate from optional sensors because it's required for basic functionality
MANDATORY_SENSOR = {
    "can_see_food": (50, 200),
}

# All required neurons combined (7 core + 1 mandatory sensor)
REQUIRED_NEURONS = {**CORE_NEURONS, **MANDATORY_SENSOR}

# Ordered list for consistent iteration
CORE_NEURON_NAMES = [
    "hunger", "happiness", "cleanliness", "sleepiness",
    "satisfaction", "anxiety", "curiosity"
]

REQUIRED_NEURON_NAMES = CORE_NEURON_NAMES + ["can_see_food"]

# =============================================================================
# INPUT SENSORS - Optional neurons that receive values from game state
# These neurons get their activation from BrainNeuronHooks, not from
# neural propagation. They represent environmental/state observations.
# NOTE: can_see_food is NOT here - it's in REQUIRED_NEURONS
# =============================================================================
INPUT_SENSORS = {
    "external_stimulus": (50, 50),      # Environmental changes (resize, interactions)
    "plant_proximity": (50, 250),       # Distance to nearest plant decoration
    "threat_level": (50, 350),          # Computed from anxiety + startle state
    "pursuing_food": (150, 50),         # Currently chasing food
    "is_sick": (150, 150),              # Sickness state
    "is_fleeing": (150, 250),           # Currently fleeing
    "is_eating": (150, 350),            # Currently eating
    "is_sleeping": (250, 50),           # Currently sleeping
    "is_startled": (250, 150),          # Startled state
}

# Tuple for compatibility with brain_neuron_hooks.py (includes can_see_food)
DEFAULT_INPUT_SENSORS = (
    'external_stimulus',
    'can_see_food',  # Listed here for hooks compatibility but it's mandatory
    'plant_proximity',
    'threat_level',
    'pursuing_food',
    'is_sick',
    'is_fleeing',
    'is_eating',
    'is_sleeping',
    'is_startled',
)

# =============================================================================
# BINARY NEURONS - Neurons that should display as on/off (0 or 100)
# These use bright green/red coloring instead of gradient heat maps.
# =============================================================================
BINARY_NEURONS = {
    'can_see_food',
    'is_eating',
    'is_sleeping',
    'is_sick',
    'pursuing_food',
    'is_fleeing',
    'is_startled',
}

# =============================================================================
# ANALOGUE SENSORS - Continuous 0-100 readings that must NOT be binarised.
# external_stimulus baselines around 5-15 and plant_proximity is a distance
# gradient; quantising either at the 50 mark discarded the whole signal.
# =============================================================================
ANALOGUE_SENSORS = {
    'external_stimulus',
    'plant_proximity',
    'threat_level',
}

# =============================================================================
# NEURON ROLE SETS - the authoritative classification for the whole project.
#
# PURE_INPUT_NEURONS  driven by the world through BrainNeuronHooks
# CORE_STAT_NEURONS   mirrored from the squid model each tick
# NON_PROPAGATED      the union: forward propagation must never write these
#
# Every other neuron (Designer customs, neurogenesis neurons, connectors) is
# network-driven and gets its activation from BrainWidget.propagate_activations.
# =============================================================================
PURE_INPUT_NEURONS = BINARY_NEURONS | ANALOGUE_SENSORS

CORE_STAT_NEURONS = set(CORE_NEURONS.keys())

NON_PROPAGATED_NEURONS = PURE_INPUT_NEURONS | CORE_STAT_NEURONS


def is_network_driven(name: str) -> bool:
    """True if this neuron's activation is computed by forward propagation."""
    return name not in NON_PROPAGATED_NEURONS


def is_learning_target(name: str) -> bool:
    """True if a learned synapse pointing AT this neuron can do anything.

    Sensors are written by the world every tick, so a synapse into one is
    inert and must never be created. Core stats are different: propagation
    does not overwrite them (the squid model owns them), but learned synapses
    into a core stat MODULATE it - see TamagotchiLogic.apply_neural_modulation.
    That is how a default eight-neuron brain, which contains nothing but
    sensors and core stats, is able to develop at all.
    """
    return name not in PURE_INPUT_NEURONS


def normalise_activation(name: str, value):
    """
    Coerce any stored neuron value into the project's 0-100 activation scale.

    Booleans always become 0.0/100.0 - previously a bool landed as 0.0/1.0
    whenever the neuron was absent from neuron_positions, so a Designer
    threshold expressed in percent could never be crossed.
    """
    if isinstance(value, bool):
        return 100.0 if value else 0.0
    if isinstance(value, (int, float)):
        v = float(value)
        if name in BINARY_NEURONS:
            return 100.0 if v > 50.0 else 0.0
        return max(0.0, min(100.0, v))
    return value

# =============================================================================
# EXCLUDED NEURONS - Status neurons that exist but aren't visualized normally
# These are tracked in brain state but not shown in the main visualization.
# =============================================================================
EXCLUDED_NEURONS = [
    'is_sick',
    'is_eating', 
    'pursuing_food',
    'direction',
    'is_sleeping'
]

# =============================================================================
# VISUAL STYLE CONSTANTS - For consistent rendering across tools
# =============================================================================

# Ring colors for neuron types
CORE_NEURON_RING_COLOR = (255, 215, 0)      # Gold
INPUT_SENSOR_RING_COLOR = (100, 149, 237)   # Cornflower blue
CUSTOM_NEURON_RING_COLOR = (180, 180, 180)  # Gray

# Ring widths
PROTECTED_RING_WIDTH = 3
NORMAL_RING_WIDTH = 2

# Default neuron colors by type
DEFAULT_COLORS = {
    'core': (150, 150, 220),      # Soft purple
    'input': (100, 200, 150),     # Soft green  
    'output': (220, 150, 150),    # Soft red
    'hidden': (180, 180, 200),    # Neutral
    'sensor': (150, 200, 220),    # Soft blue
}

# =============================================================================
# LAYER DEFAULTS
# =============================================================================
DEFAULT_LAYER_HEIGHT = 120
DEFAULT_LAYER_SPACING = 150

LAYER_COLORS = {
    'input': {
        'fill': (200, 255, 200, 80),
        'border': (150, 220, 150, 120)
    },
    'output': {
        'fill': (255, 200, 200, 80),
        'border': (220, 150, 150, 120)
    },
    'hidden': {
        'fill': (230, 230, 255, 80),
        'border': (200, 200, 240, 120)
    }
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def is_core_neuron(name: str) -> bool:
    """Check if a neuron name is a core stat neuron (7 stats)."""
    return name in CORE_NEURONS

def is_required_neuron(name: str) -> bool:
    """Check if a neuron is required (core + can_see_food)."""
    return name in REQUIRED_NEURONS

def is_input_sensor(name: str) -> bool:
    """Check if a neuron name is an optional input sensor."""
    return name in INPUT_SENSORS

def is_any_sensor(name: str) -> bool:
    """Check if a neuron receives values from hooks (including can_see_food)."""
    return name in INPUT_SENSORS or name in MANDATORY_SENSOR or name in DEFAULT_INPUT_SENSORS

def is_binary_neuron(name: str) -> bool:
    """Check if a neuron should display as binary (on/off)."""
    return name in BINARY_NEURONS

def is_protected_neuron(name: str) -> bool:
    """Check if a neuron is protected (cannot be deleted or renamed)."""
    return is_required_neuron(name)

def get_neuron_category(name: str) -> str:
    """Get the category of a neuron: 'core', 'required', 'sensor', or 'custom'."""
    if is_core_neuron(name):
        return 'core'
    elif name == 'can_see_food':
        return 'required'
    elif is_input_sensor(name):
        return 'sensor'
    else:
        return 'custom'

def get_all_standard_neurons() -> dict:
    """Get all standard neurons (required + optional sensors) with positions."""
    result = dict(REQUIRED_NEURONS)
    result.update(INPUT_SENSORS)
    return result

def get_missing_required(existing_neurons: set) -> list:
    """Get list of required neurons not in the given set."""
    return [name for name in REQUIRED_NEURONS if name not in existing_neurons]

# ---------------------------------------------------------------------------
# The brain a squid is born with
# ---------------------------------------------------------------------------
# Every Dosidicus squid hatches with the same small set of reflexes, and this
# is the only place they are written down. The game used to build a newborn
# brain out of 40% random connections at random weights in [-1, +1], while the
# headless trainer built one from a fixed innate table - so "the same squid,
# raised differently" was never a comparison anyone could actually make, two
# squids of the same species were born with different instincts, and none of
# those synapses could say where it came from because they were assigned
# straight into the weights dict.
#
# Read as (source, target, weight) and written through the recorded write path
# with mechanism 'innate', so a newborn brain can explain itself as readily as
# an old one. Every neuron a squid is born with appears at least once, so a
# newborn is never diagnosed with a connectivity deficit it was created with.
INNATE_CONNECTIONS = (
    ("hunger",       "satisfaction", -0.30),
    ("happiness",    "satisfaction",  0.40),
    ("anxiety",      "satisfaction", -0.35),
    ("cleanliness",  "happiness",     0.20),
    ("sleepiness",   "happiness",    -0.15),
    ("curiosity",    "happiness",     0.25),
    # Seeing food sharpens the appetite, and is something to look forward to.
    # These two were previously written three separate times in BrainWidget -
    # once before initialize_weights() and once after it, so the later pair
    # silently overwrote whatever the first had decided - and the happiness one
    # was behind a coin flip, which meant half of all squid were born without
    # it.
    ("can_see_food", "hunger",        0.20),
    ("can_see_food", "happiness",     0.50),
)


# ---------------------------------------------------------------------------
# What the squid can do: action neurons
# ---------------------------------------------------------------------------
# Behaviour is chosen by the NETWORK, not by a table of rules. These neurons
# are the motor end of it: each one stands for one thing the squid can do, is
# driven by ordinary forward propagation like any other network-driven neuron,
# and is bound to the actuator that carries the behaviour out (see
# INNATE_ACTION_BINDINGS and brain_neuron_outputs).
#
# The engine used to decide behaviour from hand-written formulas -
# weights["eating"] = hunger * (3.0 if can_see_food > 80 else 0.3) * 1.6 **
# (hunger/25), and a dozen more like it, plus a per-personality multiplier
# table. Those numbers were the squid's real behaviour policy, and no amount of
# learning could touch them: the network could rewire itself completely and the
# squid would still act on the same arithmetic. Now the arithmetic IS the
# network, and every one of these numbers is a synapse that learning can move.
#
# Positions sit in the band between the sensor column and the core stats, and
# inside layout_bounds() like everything else.
ACTION_NEURONS = {
    "act_move":    (170, 250),
    "act_eat":     (330, 250),
    "act_flee":    (470, 250),
    "act_ink":     (610, 250),
    "act_play":    (750, 250),
    "act_shelter": (250, 160),
    "act_rest":    (620, 160),
}

ACTION_NEURON_NAMES = tuple(ACTION_NEURONS.keys())


# What each action neuron settles to when nothing is driving it.
#
# Nearly all of them rest at ZERO: "I do not want to do this" has to be worth
# nothing, or an action the squid has never learned would sit at the midpoint
# forever and compete with the ones it has.
#
# act_move is the exception, and rests at the ordinary midpoint, because
# swimming is what a squid does when it is not doing anything else. A squid
# whose locomotion also rested at zero would be motionless from birth - and a
# motionless squid never encounters anything, so it never has the experience it
# would need in order to learn any of the rest. Movement is the floor that the
# whole "learn it by doing it" design stands on.
ACTION_RESTING_LEVELS = {
    "act_move": 50.0,
}


def action_resting_level(name: str) -> float:
    """Resting activation for an action neuron."""
    return ACTION_RESTING_LEVELS.get(name, 0.0)


# What each action neuron is called when the squid is doing it. The decision
# engine reports the winning action; this is the only place the mapping lives.
ACTION_BEHAVIOURS = {
    "act_move":    "exploring",
    "act_eat":     "eating",
    "act_flee":    "fleeing",
    "act_ink":     "inking",
    "act_play":    "playing",
    "act_shelter": "approaching_plant",
    "act_rest":    "sleeping",
}


# ---------------------------------------------------------------------------
# What the squid is born knowing
# ---------------------------------------------------------------------------
# A squid hatches able to MOVE, to EAT, and to FLEE - and nothing else. These
# are the reflexes that stop a newborn from being a blank slate that never does
# anything long enough to learn from, and they are deliberately the only ones.
#
# Everything else an adult squid does - playing with rocks, sheltering by a
# plant when it is anxious, learning that resting when tired is worth doing -
# has NO innate wiring at all. Those action neurons exist and are wired to
# their actuators, but nothing drives them at birth: the squid has to discover
# each one through investigation and experience, and Hebbian/STDP learning and
# neurogenesis have to build the path. A squid that never meets a rock never
# learns to play with one.
#
# These are ordinary synapses written through the recorded write path with
# mechanism 'innate', so they show up in the Knowledge tab like any other, and
# ordinary learning can strengthen, weaken or invert them from experience. An
# instinct here is a starting point, not a law.
INNATE_ACTION_WIRING = (
    # MOVE. Baseline locomotion, so a newborn is out in the world where things
    # can happen to it. Curiosity drives it; being startled does not stop it
    # (fleeing is movement too), but being asleep does.
    ("curiosity",      "act_move",  0.45),
    ("is_sleeping",    "act_move", -0.90),

    # EAT. Seeing food is most of it; hunger sharpens it. This is the "move
    # towards food automatically" reflex: act_eat is bound to the food-seeking
    # actuator, so a squid that can see food swims to it without being taught.
    ("can_see_food",   "act_eat",   0.85),
    ("hunger",         "act_eat",   0.40),
    ("is_sleeping",    "act_eat",  -0.90),

    # FLEE. Startle is the reflex trigger; a high threat level sustains it.
    # Startle alone is enough to reach the threshold: a squid that has just
    # been frightened should not need corroborating evidence to run.
    ("is_startled",    "act_flee",  1.00),
    ("threat_level",   "act_flee",  0.55),
    ("anxiety",        "act_flee",  0.25),

    # INK. Part of the startle reflex rather than a decision - see the
    # probability on its binding below, which is what makes it a CHANCE of
    # inking rather than a certainty.
    ("is_startled",    "act_ink",   0.80),
    ("threat_level",   "act_ink",   0.35),
)


# Actions the squid never *chooses*. They happen through their output binding
# when the network drives them past their threshold, and the decision engine
# leaves them out of the contest.
#
# Inking is the case this exists for. It is a defensive reflex that goes off
# WHILE the squid is bolting, not an alternative to bolting - and if it were
# ranked against fleeing it would sometimes win, and a frightened squid would
# stand still and release a cloud of ink instead of escaping.
REFLEX_ACTIONS = ("act_ink",)

# What the squid does when nothing else is worth doing. Not a competitor: an
# urge only has to beat its own threshold, not this.
FALLBACK_ACTION = "act_move"


# Action neurons deliberately left unwired at birth. Listed explicitly so that
# "the squid cannot do this yet" is a stated fact about the design rather than
# something you have to infer from the absence of a row above.
LEARNED_ACTIONS = tuple(
    name for name in ACTION_NEURON_NAMES
    if not any(target == name for _, target, _ in INNATE_ACTION_WIRING)
)


# ---------------------------------------------------------------------------
# How an action neuron reaches the world
# ---------------------------------------------------------------------------
# (neuron, output hook, threshold, cooldown seconds, probability).
#
# `probability` is what "a CHANCE of an ink cloud when startled" is made of:
# the reflex fires when the neuron crosses its threshold, and then only
# actually inks that fraction of the time. Keeping it here makes the chance a
# property of the reflex - visible, tunable, and the same for every squid -
# instead of a random.random() buried in a behaviour rule.
# Thresholds are calibrated against what the innate wiring can actually
# produce, which is bounded: a saturated sensor contributes half its value
# (see propagation.signal_of), so is_startled at 100 through a 0.70 synapse is
# 35, not 70. A threshold above what its own reflex can reach is a behaviour
# that can never happen - the ink cloud was originally set at 80, which the
# startle reflex tops out well below, so a startled squid could never have
# inked at all.
INNATE_ACTION_BINDINGS = (
    ("act_move",    "neuron_output_wander",      45.0, 3.0, 1.00),
    # Seeing food is enough on its own (a saturated can_see_food gives 42.5
    # through the innate 0.85 synapse): "swim towards food" is the reflex a
    # squid is born with, and hunger then makes it more or less urgent than
    # whatever else is going on.
    ("act_eat",     "neuron_output_seek_food",   40.0, 1.5, 1.00),
    ("act_flee",    "neuron_output_flee",        50.0, 3.0, 1.00),
    # Reachable on a real startle, and then only about a third of the time.
    ("act_ink",     "neuron_output_ink_cloud",   45.0, 8.0, 0.35),
    # Learned actions are bound to their actuators from birth too. The binding
    # is the squid's BODY - it can always ink, or hold a rock. What it does not
    # have is anything driving these neurons, so until experience wires one up
    # it never crosses its threshold and the behaviour never happens.
    ("act_play",    "neuron_output_approach_rock", 60.0, 5.0, 1.00),
    ("act_shelter", "neuron_output_seek_plant",    55.0, 4.0, 1.00),
    ("act_rest",    "neuron_output_sleep",         85.0, 10.0, 1.00),
)


# The sensors a squid is born able to read. can_see_food is already mandatory;
# these are the two the flee reflex needs, plus the sleep flag that gates the
# other reflexes off while the squid is asleep. Without them in the newborn
# brain the innate wiring above would be silently dropped (initialize_weights
# skips any synapse whose endpoints are not present), and a newborn would have
# no way to notice a threat at all.
INNATE_SENSORS = {
    "is_startled":  INPUT_SENSORS["is_startled"],
    "threat_level": INPUT_SENSORS["threat_level"],
    "is_sleeping":  INPUT_SENSORS["is_sleeping"],
}


def newborn_neurons() -> dict:
    """Every neuron a squid hatches with, as {name: (x, y)}.

    Eight required neurons, the sensors the innate reflexes read, and the
    action neurons that are the motor end of behaviour. Neurogenesis adds to
    this over the squid's life; nothing else is there at birth.
    """
    return {**REQUIRED_NEURONS, **INNATE_SENSORS, **ACTION_NEURONS}


# ---------------------------------------------------------------------------
# Personality, as a tilt on the instincts rather than a rule about behaviour
# ---------------------------------------------------------------------------
# A timid squid is not one that consults a rule saying "multiply fleeing by
# 1.5 when deciding". It is one born with a stronger startle reflex. The
# decision engine used to carry a per-personality multiplier table applied
# after the fact, which meant personality could never be affected by anything
# that happened to the squid; expressing it as a birth-time tilt on the innate
# synapses puts it where experience can reach it, so a timid squid that is
# never frightened can genuinely grow out of it.
#
# Read as {personality value: ((source, target, multiplier), ...)}, applied
# once, to the innate weight, when the squid's personality becomes known.
INNATE_PERSONALITY_BIAS = {
    'timid': (
        ("is_startled",  "act_flee", 1.30),
        ("threat_level", "act_flee", 1.30),
        ("is_startled",  "act_ink",  1.25),
        ("curiosity",    "act_move", 0.75),
    ),
    'adventurous': (
        ("curiosity",    "act_move", 1.30),
        ("is_startled",  "act_flee", 0.85),
    ),
    'energetic': (
        ("curiosity",    "act_move", 1.40),
    ),
    'lazy': (
        ("curiosity",    "act_move", 0.60),
    ),
    'greedy': (
        ("hunger",       "act_eat",  1.45),
        ("can_see_food", "act_eat",  1.15),
    ),
    'stubborn': (
        ("is_startled",  "act_flee", 0.75),
        ("threat_level", "act_flee", 0.80),
    ),
    'introvert': (
        ("curiosity",    "act_move", 0.85),
        ("threat_level", "act_flee", 1.15),
    ),
}


# The activation at which each action becomes something the squid will
# actually do. Derived from the bindings rather than written twice, so the
# threshold the decision engine tests is by construction the same one the
# actuator fires on - an urge is never "chosen" at a level that could not
# reach the body.
ACTION_THRESHOLDS = {
    neuron: threshold
    for neuron, _hook, threshold, _cooldown, _probability in INNATE_ACTION_BINDINGS
}


def is_action_neuron(name: str) -> bool:
    """True if this neuron is the motor end of a behaviour."""
    return name in ACTION_NEURONS


# ---------------------------------------------------------------------------
# Where a neuron is allowed to sit
# ---------------------------------------------------------------------------
# Every neuron the brain grows has to stay inside the area the Brain Tool shows
# without being resized, so the whole network is visible at the size the window
# opens at. That area is defined RELATIVE TO THE DEFAULT LAYOUT rather than to
# the logical canvas: a neuron may sit at most LAYOUT_MARGIN pixels outside the
# box the eight default neurons occupy.
#
# Placement used to run against the full 1024x768 logical canvas with a
# centering force pulling everything toward (512, 384), which put grown neurons
# in a clump in the middle of a canvas far taller than the default layout - so
# the interesting part of the network was both bunched up and partly below the
# visible area.
LAYOUT_MARGIN = 50

# Never let a neuron sit so close to the canvas edge that its circle and label
# are clipped, even if the margin above would allow it.
LAYOUT_EDGE_GUARD = 25


def layout_bounds(default_positions=None, margin=LAYOUT_MARGIN):
    """Return (min_x, min_y, max_x, max_y) that any neuron must stay inside.

    This is the bounding box of `default_positions` (the eight neurons a squid
    is born with, by default) grown by `margin` on every side, then held off
    the canvas edge by LAYOUT_EDGE_GUARD.
    """
    positions = default_positions or REQUIRED_NEURONS
    xs = [p[0] for p in positions.values()]
    ys = [p[1] for p in positions.values()]
    if not xs or not ys:
        xs, ys = [50, 840], [81, 389]
    return (
        max(LAYOUT_EDGE_GUARD, min(xs) - margin),
        max(LAYOUT_EDGE_GUARD, min(ys) - margin),
        max(xs) + margin,
        max(ys) + margin,
    )


def clamp_to_layout(x, y, default_positions=None, margin=LAYOUT_MARGIN):
    """Clamp a point into the region layout_bounds() describes."""
    min_x, min_y, max_x, max_y = layout_bounds(default_positions, margin)
    return (max(min_x, min(max_x, float(x))),
            max(min_y, min(max_y, float(y))))
