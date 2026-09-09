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


# =============================================================================
# REGISTERING A SENSOR AT RUNTIME
#
# A plugin can already supply the VALUE of a new input neuron - see
# PluginManager.register_neuron_handler and BrainNeuronHooks. What it could
# not do was tell the rest of the project that the neuron is a SENSE ORGAN,
# because the four sets above were built once at import and a plugin sensor
# was in none of them. The consequences were not cosmetic:
#
#   propagation.baseline_of()      it rested at the 50 midpoint instead of 0,
#                                  so "nothing to report" read as a signal -
#                                  and forward propagation was free to
#                                  overwrite whatever the world had written
#   capability.situation_signature() the situation it defines could never be
#                                  named, so no representation deficit could
#                                  ever be raised for it
#   causal_learning._capture_cue() it could never be the antecedent of a
#                                  causal claim, so no expression deficit
#                                  either
#   is_learning_target()           plasticity was allowed to write synapses
#                                  INTO a neuron the world overwrites every
#                                  tick, which are inert by construction
#
# So the sets are mutated in place rather than rebuilt: every module that did
# `from .brain_constants import PURE_INPUT_NEURONS` holds a reference to the
# set object itself, and rebinding the name here would leave all of them
# looking at a stale copy.
#
# This is deliberately generic. Nothing here knows what a sensor is FOR.
# =============================================================================

#: Where a registered sensor asked to be drawn, if it said. Kept apart from
#: INPUT_SENSORS so that the built-in layout is exactly what it always was.
PLUGIN_INPUT_SENSORS: dict = {}

#: Which sensors arrived at runtime, and who registered them. Only these can
#: be unregistered - a plugin can never remove a built-in sense organ.
_REGISTERED_SENSORS: dict = {}

#: Anything holding a derived copy of the role sets subscribes here.
#: propagation does, because its resting-level set is one.
_SENSOR_LISTENERS: list = []


def on_input_sensor_change(callback) -> None:
    """Subscribe to sensor registration.

    `callback(name, binary, added)` runs whenever a sensor is registered or
    unregistered. Used by modules that cache a set derived from the role sets
    above and cannot see an in-place mutation of a different set.
    """
    if callback not in _SENSOR_LISTENERS:
        _SENSOR_LISTENERS.append(callback)


def _notify_sensor_change(name: str, binary: bool, added: bool) -> None:
    for callback in list(_SENSOR_LISTENERS):
        try:
            callback(name, binary, added)
        except Exception as exc:      # a bad listener must not break the brain
            print(f"[brain_constants] sensor listener failed for '{name}': {exc}")


def register_input_sensor(name: str, *, binary: bool = False,
                          position=None, owner: str = "plugin") -> bool:
    """Classify `name` as a pure input neuron for the rest of its process life.

    The caller is separately responsible for supplying the value (a neuron
    handler) and for the neuron existing in the brain. This function only
    answers the question every system above asks: "is this a sense organ?"

    Registering a name that is already a built-in sensor is a no-op, and
    returns False - a plugin may override the built-in's VALUE through the
    handler registry, but it may not reclassify the neuron.
    """
    if not isinstance(name, str) or not name:
        raise ValueError("sensor name must be a non-empty string")
    if name in CORE_STAT_NEURONS or name in ACTION_NEURONS:
        raise ValueError(
            f"'{name}' is a core stat or an action neuron and cannot be a sensor")
    if name in PURE_INPUT_NEURONS and name not in _REGISTERED_SENSORS:
        return False                  # already a built-in; leave it alone

    binary = bool(binary)
    _REGISTERED_SENSORS[name] = {'binary': binary, 'owner': owner}
    (BINARY_NEURONS if binary else ANALOGUE_SENSORS).add(name)
    PURE_INPUT_NEURONS.add(name)
    NON_PROPAGATED_NEURONS.add(name)
    if position is not None:
        PLUGIN_INPUT_SENSORS[name] = tuple(position)
    _notify_sensor_change(name, binary, True)
    return True


def unregister_input_sensor(name: str) -> bool:
    """Undo `register_input_sensor`. Built-in sensors are never removed."""
    entry = _REGISTERED_SENSORS.pop(name, None)
    if entry is None:
        return False
    (BINARY_NEURONS if entry['binary'] else ANALOGUE_SENSORS).discard(name)
    PURE_INPUT_NEURONS.discard(name)
    NON_PROPAGATED_NEURONS.discard(name)
    PLUGIN_INPUT_SENSORS.pop(name, None)
    _notify_sensor_change(name, entry['binary'], False)
    return True


def registered_input_sensors() -> dict:
    """{name: {'binary': bool, 'owner': str}} for sensors added at runtime."""
    return {name: dict(entry) for name, entry in _REGISTERED_SENSORS.items()}


def is_registered_input_sensor(name: str) -> bool:
    """True if this sensor arrived at runtime rather than being built in."""
    return name in _REGISTERED_SENSORS


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
    "act_move":     (170, 250),
    "act_eat":      (330, 250),
    "act_flee":     (470, 250),
    "act_ink":      (610, 250),
    "act_play":     (750, 250),
    "act_shelter":  (250, 160),
    "act_rest":     (620, 160),
    # Involuntary. Not the same neuron as act_rest: choosing to rest before
    # you are exhausted is a thing a squid can learn, and collapsing when you
    # are is a thing that happens to it. See the homeostatic drives below.
    "act_collapse": (440, 160),
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
    # A tonic bias, not a wish: locomotion idles at the ordinary midpoint so a
    # squid that wants nothing in particular still swims, and goes on meeting
    # things it can learn from.
    "act_move": 50.0,
}


def action_resting_level(name: str) -> float:
    """Resting activation for an action neuron."""
    return ACTION_RESTING_LEVELS.get(name, 0.0)


# What each action neuron is called when the squid is doing it. The decision
# engine reports the winning action; this is the only place the mapping lives.
ACTION_BEHAVIOURS = {
    "act_move":     "exploring",
    "act_eat":      "eating",
    "act_flee":     "fleeing",
    "act_ink":      "inking",
    "act_play":     "playing",
    "act_shelter":  "approaching_plant",
    "act_rest":     "sleeping",
    "act_collapse": "exhausted",
}


# ---------------------------------------------------------------------------
# Firing thresholds
# ---------------------------------------------------------------------------
# The activation an action neuron has to reach before it drives anything - a
# property of the neuron, in the same units as its activation, not a rule
# about behaviour. Every consumer reads these: the actuator fires on them and
# the decision engine ranks by how far past its own threshold each urge is, so
# an urge can never be "chosen" at a level too weak to reach the body.
#
# They are calibrated against what the innate pathways can actually produce,
# which is bounded: a saturated sensor contributes half its value (see
# propagation.signal_of), so is_startled at 100 through a 0.80 synapse is 40,
# not 80. A threshold above what its own pathway can reach is a behaviour that
# can never happen - the ink reflex was first set at 80, which the startle
# pathway tops out well below, so a startled squid could never have inked.
ACTION_FIRING_THRESHOLDS = {
    "act_move":     45.0,
    # Seeing food is enough on its own: a saturated can_see_food gives 42.5
    # through the innate 0.85 synapse. Set below that with room to spare, so
    # the decision noise cannot push a squid that can plainly see food back
    # under the line - "swim towards food" is the instinct it is born with,
    # not a coin flip it wins slightly more often than not.
    "act_eat":      38.0,
    "act_flee":     50.0,
    "act_ink":      45.0,
    # The learned actions sit in the same band as the innate ones, and for the
    # same reason: a threshold has to be REACHABLE by the pathways that could
    # drive it. A core drive contributes at most 50 (propagation.signal_of), so
    # thresholds of 60 and 85 meant a squid could learn "when anxious, shelter"
    # as strongly as a synapse can be learned and still never do it - the
    # behaviour would have been permanently out of reach, which is not the same
    # thing as having to be learned. One strong learned pathway from a drive
    # that is clearly signalling now makes a behaviour available; the
    # competition between actions decides whether it actually happens.
    "act_play":     38.0,
    "act_shelter":  38.0,
    "act_rest":     38.0,
    # Only at the very top of the sleepiness scale.
    "act_collapse": 45.0,
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
    # --- SENSORIMOTOR PRIORS -------------------------------------------
    # The squid is born already wired from a sense to the action that sense is
    # for. Seeing food drives the neuron that swims towards food; it does not
    # consult a rule that says so. This is the "move towards food" instinct,
    # and it is one synapse.
    ("can_see_food",   "act_eat",      0.85),

    # --- REFLEX PATHWAYS -----------------------------------------------
    # Short, strong, sensor-to-motor. Startle alone reaches the flight
    # threshold: a squid that has just been frightened should not need
    # corroborating evidence to run. Threat sustains what startle begins.
    ("is_startled",    "act_flee",     1.00),
    ("threat_level",   "act_flee",     0.55),
    # Inking runs from the same startle, in parallel with flight rather than
    # instead of it - see REFLEX_ACTIONS. The probability on its binding is
    # what makes it a CHANCE of inking rather than a certainty.
    ("is_startled",    "act_ink",      0.80),
    ("threat_level",   "act_ink",      0.35),

    # --- HOMEOSTATIC DRIVES --------------------------------------------
    # A drive away from its comfortable level pushes the action that would
    # correct it. Hunger sharpens the appetite the food prior already
    # supplies; sleepiness, at the very top of its range, drives an
    # involuntary collapse.
    #
    # act_collapse is deliberately NOT act_rest. Collapsing from exhaustion is
    # homeostasis and every squid is born with it. Choosing to rest BEFORE
    # exhaustion is a thing a squid has to learn, and act_rest is left unwired
    # so that it can.
    ("hunger",         "act_eat",      0.40),
    ("sleepiness",     "act_collapse", 0.95),
    ("anxiety",        "act_flee",     0.25),

    # --- TONIC BIAS ----------------------------------------------------
    # Locomotion has a resting level of its own (ACTION_RESTING_LEVELS), so a
    # squid that wants nothing in particular still swims. Curiosity modulates
    # it above that floor. A motionless newborn never meets anything, so it
    # never has the experience it would need to learn any of the rest.
    ("curiosity",      "act_move",     0.45),

    # --- SLEEP GATING ---------------------------------------------------
    # Being asleep inhibits the voluntary actions rather than being checked
    # for by a rule outside the network. A sleeping squid's action neurons sit
    # below their thresholds because something is holding them there, which is
    # why the decision engine needs no "if asleep" branch at all.
    ("is_sleeping",    "act_move",    -0.90),
    ("is_sleeping",    "act_eat",     -0.90),
    ("is_sleeping",    "act_flee",    -0.90),
    ("is_sleeping",    "act_collapse", -0.90),
)


# ---------------------------------------------------------------------------
# Competition between actions
# ---------------------------------------------------------------------------
# A squid cannot flee and eat at the same time, and deciding which it does is
# not arithmetic performed outside its head: the action neurons INHIBIT ONE
# ANOTHER, so a strongly driven one suppresses its rivals and the winner is
# whatever survives that. This is ordinary lateral inhibition, written as
# ordinary synapses, and it is subject to the same plasticity as everything
# else - a squid whose experience keeps pairing two actions can weaken the
# inhibition between them.
#
# Locomotion is inhibited by every other action but does not inhibit them
# back. That asymmetry is what makes swimming the thing a squid does when
# nothing else is worth doing, without anything having to declare it the
# "fallback": any real urge quietly suppresses idling, and when the urge
# passes, idling comes back on its own.
#
# Reflexes (inking, collapsing) sit outside the competition. Inking runs
# alongside flight rather than against it, and an exhausted squid does not
# get a vote.
COMPETING_ACTIONS = ("act_eat", "act_flee", "act_play", "act_shelter", "act_rest")

#: How hard a driven action suppresses its rivals, and idle swimming.
LATERAL_INHIBITION = -0.22
LOCOMOTION_INHIBITION = -0.30
#: How hard an imminent collapse silences everything else.
COLLAPSE_INHIBITION = -0.45


def action_competition_wiring():
    """Mutual inhibition between action neurons, as (source, target, weight).

    Generated rather than typed out: with five competing actions this is
    twenty synapses plus five onto locomotion, and a hand-written table of
    those would be a place for one of them to go quietly missing.
    """
    wiring = []
    for source in COMPETING_ACTIONS:
        for target in COMPETING_ACTIONS:
            if source != target:
                wiring.append((source, target, LATERAL_INHIBITION))
        wiring.append((source, "act_move", LOCOMOTION_INHIBITION))

    # Collapse takes no part in the competition - it is not chosen - but it
    # silences it. An exhausted squid stops doing things; without this it went
    # on reporting whatever it had been up to for the tick between crossing
    # the collapse threshold and the sleep gating taking hold.
    for target in COMPETING_ACTIONS + ("act_move",):
        wiring.append(("act_collapse", target, COLLAPSE_INHIBITION))
    return tuple(wiring)


REFLEX_ACTIONS = ("act_ink", "act_collapse")

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
    ("act_move",     "neuron_output_wander",         3.0, 1.00),
    ("act_eat",      "neuron_output_seek_food",      1.5, 1.00),
    ("act_flee",     "neuron_output_flee",           3.0, 1.00),
    # Reachable on a real startle, and then only about a third of the time.
    ("act_ink",      "neuron_output_ink_cloud",      8.0, 0.35),
    # The body can always do these. What it lacks is anything driving the
    # neuron, and for a learned action nothing does until experience wires it.
    ("act_play",     "neuron_output_approach_rock",  5.0, 1.00),
    ("act_shelter",  "neuron_output_seek_plant",     4.0, 1.00),
    ("act_rest",     "neuron_output_sleep",         10.0, 1.00),
    ("act_collapse", "neuron_output_sleep",         10.0, 1.00),
)


# The activation at which each action becomes something the squid will
# actually do. Read from the neuron's own firing threshold rather than written
# again here, so the threshold the decision engine tests is by construction
# the one the actuator fires on.
ACTION_THRESHOLDS = dict(ACTION_FIRING_THRESHOLDS)


def innate_bindings():
    """(neuron, hook, threshold, cooldown, probability) for each reflex."""
    return tuple(
        (neuron, hook, ACTION_FIRING_THRESHOLDS.get(neuron, 50.0),
         cooldown, probability)
        for neuron, hook, cooldown, probability in INNATE_ACTION_BINDINGS)


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

    Eight required neurons, the sensors the innate pathways read, and the
    action neurons that are the motor end of behaviour. Neurogenesis adds to
    this over the squid's life; nothing else is there at birth.
    """
    return {**REQUIRED_NEURONS, **INNATE_SENSORS, **ACTION_NEURONS}


# ---------------------------------------------------------------------------
# Personality, as a tilt on the innate pathways rather than a rule
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
