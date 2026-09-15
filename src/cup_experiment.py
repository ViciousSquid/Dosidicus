"""
cup_experiment.py - the cup-and-food experiment, without Qt.

WHAT THIS IS
------------
A shell game, played with the squid. Three cups sit on the tank floor. The
player baits one of them where the squid can see it, shuffles the cups, and the
food ends up hidden under one. The squid swims to a cup. The player lifts it. If
the squid picked the baited cup it gets the food, and everything that normally
follows from eating follows from it here too - there is no second reward system.

That is the game. The reason it exists is the measurement underneath it: a
three-cup forced choice has a known chance rate of 1/3, so "did the squid learn
anything?" becomes a question with a numerical answer instead of an impression.

WHAT IT MAY NOT DO
------------------
The experiment adds NO neurons and NO sensors. The squid is given no concept of
a cup, no concept of a choice, and no channel of any kind that exists because
this experiment exists. Everything it knows during a trial it knows through the
senses it already had, and `can_see_food` keeps its ordinary meaning throughout:
while the food is under a cup it is not among the visible objects, so the sensor
reads 0 by the existing code path rather than by a special case.

The experimenter's knowledge of where the food is - the ghost marker the player
sees - lives in this module and in the UI. It is never written into brain state.
`CupExperiment` holds no reference through which it could: it reads the brain,
and it never writes to it. See `test_cup_experiment.py`.

The squid is not asked to "choose a cup". It swims where its own network sends
it; this layer watches its ordinary position and calls the first cup it reaches
its selection. The interpretation is ours, not the squid's.

WHAT THE ARCHITECTURE CAN AND CANNOT LEARN HERE
-----------------------------------------------
This was checked against the code before the experiment was built, and the
answer decides what the experiment is allowed to claim.

Everything the world writes into the network goes through
`BrainNeuronHooks.get_input_neuron_values()`, and every one of those values is a
SCALAR with no spatial content: `can_see_food` (is there food in the cone at
all), `plant_proximity`, `threat_level`, `external_stimulus` and the state flags.
Everything the network can do is an action neuron from
`brain_constants.ACTION_NEURONS`, and none of those is directional either -
there is `act_eat`, and no `act_go_left`. The squid's position does appear in
the dict passed to `update_brain` under `position`, but it is a tuple, so
`propagation.activation_of` returns None for it and no synapse can read it.

So:

  * The network CAN represent "there is food about" and "I want to eat", and
    plasticity can move how strongly it wants to, because those are activations
    on existing neurons.
  * The network CANNOT represent "the food is at the left cup". There is no
    input that differs between the three cups and no output that differs
    between going to one and going to another. A representation the network
    cannot form is not one experience can teach it.

Therefore this experiment predicts, in advance, that CHOICE ACCURACY STAYS AT
CHANCE, and it is built to measure that honestly rather than to avoid it. The
fix would be a positional sense and a directed action - which is exactly the
thing this experiment is forbidden to add, and exactly the finding worth
reporting.

What CAN move is the secondary measure: how hard `act_eat` is driven while the
food is hidden. That is ordinary food-seeking persistence under occlusion, it
runs on synapses the existing plasticity engine can and does change, and it is
reported alongside accuracy - separately, so neither is mistaken for the other.

What the runs found, pooled over five seeds (docs/cup_experiment.md):

    which cup   +5.0 points over the learning-disabled control, p = 0.33
                -> no. As predicted, and for the reason above.
    drive      +19   points over the same control, p < 0.001, in a block
                where learning was frozen -> yes.

The squid does not learn WHERE the food went. It does learn to go on wanting it
once it is gone.

HOW A RUN IS STRUCTURED
-----------------------
A no-information baseline (the squid is never shown the bait, so nothing it does
can beat 1/3), then training trials, then EVALUATION trials with learning frozen
(`RecordedSynapses.set_learning_frozen`), so nothing measured during evaluation
can be the product of adaptation happening during evaluation. A learning-disabled
control arm runs the same protocol with the freeze on throughout, and the
comparison that counts is evaluation against THAT rather than against 1/3 - the
apparatus gives points away, and both arms get the same gift.

One seed is one animal. `cup_experiment_runner --seeds N` pools several, and
docs/cup_experiment.md records why that matters here.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

#: Three cups. The chance rate is 1/len(CUP_IDENTITIES) and everything that
#: reports a baseline derives it from here rather than writing 0.333 down.
CUP_IDENTITIES: Tuple[str, ...] = ("A", "B", "C")

#: How close the squid's centre has to get to a cup's centre before this layer
#: reads its ordinary swimming as having arrived at that cup.
DEFAULT_SELECT_RADIUS = 90.0


def chance_rate(cups: int = len(CUP_IDENTITIES)) -> float:
    """The rate a squid choosing at random would score. 1/3 for three cups."""
    return 1.0 / max(1, int(cups))


# ---------------------------------------------------------------------------
# Phases of one trial
# ---------------------------------------------------------------------------
class Phase(Enum):
    """The seven steps of a trial, in the order the player performs them."""
    IDLE = "idle"
    BAIT = "bait"            # food placed, visible to the squid
    SHUFFLE = "shuffle"      # cups rearranged
    HIDDEN = "hidden"        # food under a cup; can_see_food must read 0
    CHOICE = "choice"        # the squid is swimming; we watch where it goes
    REVEAL = "reveal"        # the chosen cup is lifted
    OUTCOME = "outcome"      # it eats, or it does not
    SETTLED = "settled"


#: Phases during which the food is, by construction, invisible to the squid.
OCCLUDED_PHASES = (Phase.HIDDEN, Phase.CHOICE)


# ---------------------------------------------------------------------------
# What the squid actually perceived, as distinct from what we know
# ---------------------------------------------------------------------------
@dataclass
class Perception:
    """One sample of the squid's own inputs and activations.

    Deliberately named for the squid's point of view. Nothing in here is
    experimenter knowledge; the ground truth lives on TrialRecord, in fields
    whose names begin with `truth_`, and the two are never merged.
    """
    phase: str
    t: float
    can_see_food: float = 0.0
    act_eat: float = 0.0
    hunger: float = 0.0
    happiness: float = 0.0
    satisfaction: float = 0.0
    squid_x: float = 0.0
    squid_y: float = 0.0
    status: str = ""

    @classmethod
    def sample(cls, phase: Phase, brain_state: Mapping[str, Any],
               squid_pos: Tuple[float, float] = (0.0, 0.0),
               status: str = "", t: Optional[float] = None) -> "Perception":
        def num(key: str) -> float:
            raw = brain_state.get(key, 0.0)
            if isinstance(raw, bool):
                return 100.0 if raw else 0.0
            try:
                return float(raw)
            except (TypeError, ValueError):
                return 0.0
        return cls(
            phase=phase.value,
            t=time.time() if t is None else float(t),
            can_see_food=num('can_see_food'),
            act_eat=num('act_eat'),
            hunger=num('hunger'),
            happiness=num('happiness'),
            satisfaction=num('satisfaction'),
            squid_x=float(squid_pos[0]),
            squid_y=float(squid_pos[1]),
            status=str(status),
        )


@dataclass
class TrialRecord:
    """Everything one trial produced, with the two kinds of knowledge apart.

    `truth_*` is what the EXPERIMENTER knows - which cup was baited, where the
    ghost marker is. The squid never had any of it.

    `perceptions` is what the SQUID had - readings off its own sensors and
    activations off its own neurons, sampled at each phase.
    """
    index: int
    block: str = "train"

    # --- experimenter ground truth ------------------------------------
    truth_slot_of_identity: Dict[str, int] = field(default_factory=dict)
    truth_baited_identity: str = ""
    truth_baited_slot: int = -1

    # --- what the squid did -------------------------------------------
    chosen_slot: int = -1
    chosen_identity: str = ""
    correct: Optional[bool] = None
    ate: bool = False
    committed: bool = False          # did it reach a cup at all?
    choice_latency: float = 0.0
    #: Did the choice open from a fair starting place - the squid clear of
    #: every cup - or did the apparatus run out of patience and start it
    #: sitting next to one? A trial that did not start clear is still scored,
    #: and `started_clear` is what lets anyone check whether those trials are
    #: carrying the result.
    started_clear: bool = True

    # --- what the squid perceived -------------------------------------
    perceptions: List[Perception] = field(default_factory=list)

    # --- what changed inside it ---------------------------------------
    outcome_deltas: Dict[str, float] = field(default_factory=dict)
    weight_deltas: Dict[str, float] = field(default_factory=dict)
    plasticity_events: List[str] = field(default_factory=list)
    episodes: List[str] = field(default_factory=list)
    knowledge: List[str] = field(default_factory=list)
    learning_frozen: bool = False

    def perceived(self, phase: Phase) -> Optional[Perception]:
        """The last sample taken during this phase."""
        wanted = phase.value
        for p in reversed(self.perceptions):
            if p.phase == wanted:
                return p
        return None

    def _peak_act_eat(self, seeing: bool,
                      phases: Optional[Sequence[Phase]] = None
                      ) -> Optional[float]:
        """Peak act_eat over samples split by what the squid could SEE.

        Split on the sensor rather than on the phase. A trial in the
        no-information arm has a bait phase in which no bait was ever shown, so
        "act_eat during BAIT" there would be a reading of the squid wanting to
        eat nothing in particular - and dividing by it produced persistence
        figures over 100%.
        """
        wanted = None if phases is None else {ph.value for ph in phases}
        values = [p.act_eat for p in self.perceptions
                  if (p.can_see_food >= 100.0) == seeing
                  and (wanted is None or p.phase in wanted)]
        return max(values) if values else None

    def act_eat_while_visible(self) -> Optional[float]:
        """How hard the squid wanted to eat while it could see the food.

        The reference level. It is mostly innate - `can_see_food -> act_eat` is
        a synapse the squid is born with - so it says how loudly the sight of
        food speaks, and gives the number below something to be a fraction of.
        None when the squid never laid eyes on food during the trial.
        """
        return self._peak_act_eat(seeing=True)

    def act_eat_while_hidden(self) -> Optional[float]:
        """How hard the squid wanted to eat while it could NOT see the food.

        The secondary measure, and the only part of "follow the food" this
        architecture can actually learn: unlike which cup it goes to, this is
        an activation on an existing neuron, reached through synapses the
        existing plasticity engine moves. If training does anything here, it
        shows up as this number rising.
        """
        return self._peak_act_eat(seeing=False, phases=OCCLUDED_PHASES)

    def occlusion_persistence(self) -> Optional[float]:
        """Hidden drive as a fraction of visible drive: does the wish survive?

        1.0 would be a squid that wants to eat exactly as much with the food
        out of sight as with it in sight. 0.0 is a squid for which food that
        cannot be seen does not exist.
        """
        visible = self.act_eat_while_visible()
        hidden = self.act_eat_while_hidden()
        if visible is None or hidden is None or visible <= 1e-6:
            return None
        return hidden / visible

    def to_dict(self) -> dict:
        d = asdict(self)
        d['perceptions'] = [asdict(p) for p in self.perceptions]
        return d


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------
def _log_binom_coeff(n: int, k: int) -> float:
    return (math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1))


def binomial_tail(hits: int, n: int, p: float) -> float:
    """P(X >= hits) for X ~ Binomial(n, p). Exact, no scipy.

    One-sided, because the question is "better than chance?" and a squid doing
    reliably WORSE than chance is a different finding that deserves to be
    stated as such rather than folded into the same number.
    """
    if n <= 0:
        return 1.0
    hits = max(0, min(int(hits), n))
    total = 0.0
    for k in range(hits, n + 1):
        total += math.exp(_log_binom_coeff(n, k)
                          + k * math.log(p) + (n - k) * math.log1p(-p))
    return min(1.0, total)


def wilson_interval(hits: int, n: int, z: float = 1.959963985) -> Tuple[float, float]:
    """95% Wilson score interval for a proportion.

    Wilson rather than the normal approximation because these blocks are small
    and a Wald interval on 12 trials can run off the end of [0, 1].
    """
    if n <= 0:
        return (0.0, 1.0)
    phat = hits / n
    denom = 1.0 + z * z / n
    centre = (phat + z * z / (2 * n)) / denom
    half = (z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def two_proportion_p(hits_a: int, n_a: int, hits_b: int, n_b: int) -> float:
    """Two-sided p for "these two blocks scored differently".

    A pooled-proportion z test. The comparison the whole design turns on is
    eval-with-learning against eval-with-learning-frozen, and that is a
    difference between two proportions, not a distance from 1/3.
    """
    if n_a <= 0 or n_b <= 0:
        return 1.0
    p_a, p_b = hits_a / n_a, hits_b / n_b
    pooled = (hits_a + hits_b) / (n_a + n_b)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n_a + 1 / n_b))
    if se <= 0:
        return 1.0
    z = abs(p_a - p_b) / se
    # Two-sided normal tail via erfc, so there is no table and no scipy.
    return math.erfc(z / math.sqrt(2.0))


def permutation_p(a: Sequence[float], b: Sequence[float],
                  iterations: int = 5000,
                  rng: Optional[random.Random] = None) -> float:
    """Two-sided p for "these two samples have different means".

    A permutation test, because the measure it is used on - how hard the squid
    wanted to eat with the food out of sight - is a bounded activation with no
    reason to be normally distributed, and because a permutation test needs no
    table, no library and no distributional assumption. Seeded, so a run is
    reproducible like everything else here.
    """
    a, b = [float(x) for x in a], [float(x) for x in b]
    if not a or not b:
        return 1.0
    observed = abs(sum(a) / len(a) - sum(b) / len(b))
    pool = a + b
    n = len(a)
    rng = rng or random.Random(0)
    hits = 0
    for _ in range(iterations):
        rng.shuffle(pool)
        diff = abs(sum(pool[:n]) / n - sum(pool[n:]) / (len(pool) - n))
        if diff >= observed - 1e-12:
            hits += 1
    return (hits + 1) / (iterations + 1)


@dataclass
class DriveComparison:
    """Food-seeking drive under occlusion, one block against another.

    The other half of the result. Which cup the squid goes to is a spatial
    question the network cannot represent, but HOW MUCH IT STILL WANTS TO EAT
    once the food is out of sight is an activation on a neuron it already has,
    reached through synapses the existing plasticity engine moves. If training
    teaches the squid anything about food it cannot see, it shows up here.
    """
    label: str
    a_values: List[float]
    b_values: List[float]

    @staticmethod
    def _mean(values):
        return (sum(values) / len(values)) if values else None

    @property
    def a_mean(self) -> Optional[float]:
        return self._mean(self.a_values)

    @property
    def b_mean(self) -> Optional[float]:
        return self._mean(self.b_values)

    @property
    def p_value(self) -> float:
        return permutation_p(self.a_values, self.b_values)

    @property
    def significant(self) -> bool:
        return self.p_value < 0.05

    def describe(self) -> str:
        if self.a_mean is None or self.b_mean is None:
            return f"{self.label}: not enough trials"
        verdict = ("a real difference" if self.significant
                   else "no detectable difference")
        return (f"{self.label}: {self.a_mean:.0%} vs {self.b_mean:.0%} "
                f"({self.a_mean - self.b_mean:+.0%}), "
                f"p={self.p_value:.3f} - {verdict}")


def persistence_values(records: Sequence[TrialRecord]) -> List[float]:
    """Per-trial occlusion persistence, for the trials that have one."""
    return [v for v in (r.occlusion_persistence() for r in records)
            if v is not None]


@dataclass
class Comparison:
    """One block measured against another, with the verdict spelled out."""
    label: str
    a: "BlockStats"
    b: "BlockStats"

    @property
    def difference(self) -> float:
        return self.a.rate - self.b.rate

    @property
    def p_value(self) -> float:
        return two_proportion_p(self.a.hits, self.a.committed,
                                self.b.hits, self.b.committed)

    @property
    def significant(self) -> bool:
        return self.p_value < 0.05

    def describe(self) -> str:
        verdict = ("a real difference" if self.significant
                   else "no detectable difference")
        return (f"{self.label}: {self.a.rate:.1%} vs {self.b.rate:.1%} "
                f"({self.difference:+.1%}), p={self.p_value:.3f} - {verdict}")


@dataclass
class BlockStats:
    """One block of trials, scored against chance.

    Accuracy is `hits / committed`, not `hits / trials`: a trial the squid
    never played is an OMISSION, and scoring an omission as a wrong answer
    measures how often the squid felt like swimming to a cup, not how often it
    swam to the right one. A squid that plays 60% of trials and guesses would
    otherwise "score" 20% and look reliably WORSE than chance.

    Dropping omissions is only legitimate because the squid cannot know which
    cup is baited, so whether it plays is independent of which answer would
    have been right. That independence is not assumed - `omission_bias` in the
    controls measures it.

    `rate_all` keeps the undropped number in view so nothing is hidden by the
    choice of denominator.
    """
    block: str
    trials: int
    committed: int
    commit_rate: float
    hits: int
    rate: float
    rate_all: float
    chance: float
    ci_low: float
    ci_high: float
    p_above_chance: float
    mean_act_eat_visible: Optional[float]
    mean_act_eat_hidden: Optional[float]
    mean_persistence: Optional[float]
    learning_frozen: bool
    #: The same block, restricted to trials that began with the squid clear of
    #: every cup. The rest began with it standing on or beside the cup it had
    #: last seen the food at, where picking the nearest one is worth points
    #: that have nothing to do with knowing anything. Splitting them is the
    #: experiment's sharpest internal control: a squid that had LEARNED where
    #: the food was would score alike in both strata, and a squid that is
    #: merely still standing there would not.
    clear_committed: int = 0
    clear_hits: int = 0
    clear_rate: float = 0.0
    near_committed: int = 0
    near_hits: int = 0
    near_rate: float = 0.0

    @property
    def above_chance(self) -> bool:
        """Significantly better than guessing, at the conventional 5%."""
        return self.p_above_chance < 0.05

    def describe(self) -> str:
        verdict = ("above chance" if self.above_chance
                   else "not distinguishable from chance")
        frozen = " (learning frozen)" if self.learning_frozen else ""
        omitted = self.trials - self.committed
        return (f"{self.block}{frozen}: {self.hits}/{self.committed} correct "
                f"= {self.rate:.1%} "
                f"[95% CI {self.ci_low:.1%}-{self.ci_high:.1%}], "
                f"chance {self.chance:.1%}, p={self.p_above_chance:.3f} "
                f"- {verdict}"
                + (f"  ({omitted} omitted of {self.trials})" if omitted else ""))

    def describe_start(self) -> str:
        """Accuracy split by where the trial started from."""
        def part(hits, n, label):
            return (f"{label} {hits}/{n} = {hits / n:.1%}" if n
                    else f"{label} no trials")
        return (f"{self.block}: "
                + part(self.clear_hits, self.clear_committed,
                       "started clear of every cup:")
                + "; "
                + part(self.near_hits, self.near_committed,
                       "started beside one:"))

    def describe_drive(self) -> str:
        """The secondary measure, stated separately so it is never read as
        accuracy."""
        def fmt(v):
            return "n/a" if v is None else f"{v:.1f}"
        persistence = ("n/a" if self.mean_persistence is None
                       else f"{self.mean_persistence:.0%}")
        return (f"{self.block}: reached a cup on {self.commit_rate:.0%} of "
                f"trials; act_eat {fmt(self.mean_act_eat_visible)} with food in "
                f"sight, {fmt(self.mean_act_eat_hidden)} with it hidden "
                f"({persistence} persistence)")


def score_block(records: Sequence[TrialRecord], block: str = "",
                cups: int = len(CUP_IDENTITIES)) -> BlockStats:
    """Score a list of trials. The only place a hit rate is computed."""
    played = [r for r in records if r.committed and r.correct is not None]
    n = len(played)
    hits = sum(1 for r in played if r.correct)
    total = len([r for r in records if r.correct is not None])
    p = chance_rate(cups)
    low, high = wilson_interval(hits, n)

    def mean_of(getter):
        values = [v for v in (getter(r) for r in records) if v is not None]
        return (sum(values) / len(values)) if values else None

    clear = [r for r in played if r.started_clear]
    near = [r for r in played if not r.started_clear]
    clear_hits = sum(1 for r in clear if r.correct)
    near_hits = sum(1 for r in near if r.correct)

    return BlockStats(
        block=block or (records[0].block if records else ""),
        trials=total,
        committed=n,
        commit_rate=(n / total) if total else 0.0,
        hits=hits,
        rate=(hits / n) if n else 0.0,
        rate_all=(hits / total) if total else 0.0,
        chance=p,
        ci_low=low,
        ci_high=high,
        p_above_chance=binomial_tail(hits, n, p),
        mean_act_eat_visible=mean_of(TrialRecord.act_eat_while_visible),
        mean_act_eat_hidden=mean_of(TrialRecord.act_eat_while_hidden),
        mean_persistence=mean_of(TrialRecord.occlusion_persistence),
        learning_frozen=bool(records and records[-1].learning_frozen),
        clear_committed=len(clear),
        clear_hits=clear_hits,
        clear_rate=(clear_hits / len(clear)) if clear else 0.0,
        near_committed=len(near),
        near_hits=near_hits,
        near_rate=(near_hits / len(near)) if near else 0.0,
    )


# ---------------------------------------------------------------------------
# The cups
# ---------------------------------------------------------------------------
class CupLayout:
    """Three cups and the slots they can stand in.

    A SLOT is a place on the tank floor; an IDENTITY is a particular cup. A
    shuffle is a fresh random assignment of identities to slots, and the bait
    goes under a randomly chosen IDENTITY. Both are drawn independently and
    uniformly every trial, which is what makes "always go to the middle slot"
    and "always follow cup B" equally worthless - see the exploitability tests.
    """

    def __init__(self, slot_positions: Sequence[Tuple[float, float]],
                 identities: Sequence[str] = CUP_IDENTITIES,
                 rng: Optional[random.Random] = None):
        if len(slot_positions) != len(identities):
            raise ValueError("need one slot position per cup identity")
        self.slot_positions = [(float(x), float(y)) for x, y in slot_positions]
        self.identities = tuple(identities)
        self.rng = rng or random.Random()
        self.slot_of_identity: Dict[str, int] = {
            name: i for i, name in enumerate(self.identities)}

    @property
    def cups(self) -> int:
        return len(self.identities)

    def shuffle(self) -> Dict[str, int]:
        """Rearrange the cups. Returns the new identity -> slot mapping."""
        slots = list(range(self.cups))
        self.rng.shuffle(slots)
        self.slot_of_identity = {name: slot
                                 for name, slot in zip(self.identities, slots)}
        return dict(self.slot_of_identity)

    def identity_at(self, slot: int) -> str:
        for name, s in self.slot_of_identity.items():
            if s == slot:
                return name
        return ""

    def position_of_slot(self, slot: int) -> Tuple[float, float]:
        return self.slot_positions[int(slot)]

    def slot_nearest(self, x: float, y: float,
                     radius: float = DEFAULT_SELECT_RADIUS) -> int:
        """Which cup the squid has arrived at, or -1 if it has not.

        This is the whole of the "choice" mechanism: ordinary position, read
        from outside. The squid is not consulted and has no idea it is being
        interpreted.
        """
        best, best_d = -1, radius
        for slot, (cx, cy) in enumerate(self.slot_positions):
            d = math.hypot(x - cx, y - cy)
            if d <= best_d:
                best, best_d = slot, d
        return best


# ---------------------------------------------------------------------------
# The experiment
# ---------------------------------------------------------------------------
class CupExperiment:
    """Runs trials, records them, and scores them. Never writes to the brain.

    It holds a brain reference in order to READ activations, weights and the
    provenance ledger, and to freeze learning for an evaluation block. There is
    no path from here into brain state, and the test suite asserts it: the
    baited cup is known to this object and to nothing the squid can read.
    """

    def __init__(self, brain, layout: CupLayout,
                 rng: Optional[random.Random] = None):
        self.brain = brain
        self.layout = layout
        self.rng = rng or layout.rng
        self.trials: List[TrialRecord] = []
        self.phase: Phase = Phase.IDLE
        self.current: Optional[TrialRecord] = None
        self._phase_started = 0.0
        self._weights_at_start: Dict[Tuple[str, str], float] = {}
        self._ledger_marks: Dict[str, int] = {}
        self._stats_at_start: Dict[str, float] = {}

    # -- the brain, read-only -------------------------------------------
    def _brain_state(self) -> Dict[str, Any]:
        return dict(getattr(self.brain, 'state', {}) or {})

    def _weights(self) -> Dict[Tuple[str, str], float]:
        return dict(getattr(self.brain, 'weights', {}) or {})

    def _ledger(self):
        return getattr(self.brain, 'ledger', None)

    def neuron_names(self) -> frozenset:
        """Every neuron the brain currently has.

        Snapshotted before and after a run so "this experiment introduced no
        new neuron" is a checkable claim rather than an assurance.
        """
        positions = getattr(self.brain, 'neuron_positions', None)
        if positions is None:
            positions = getattr(self.brain, 'positions', {}) or {}
        return frozenset(positions)

    # -- freezing --------------------------------------------------------
    def set_learning_frozen(self, frozen: bool) -> bool:
        """Freeze or thaw the brain's plasticity for an evaluation block."""
        setter = getattr(self.brain, 'set_learning_frozen', None)
        if callable(setter):
            return setter(frozen)
        previous = bool(getattr(self.brain, 'learning_frozen', False))
        self.brain.learning_frozen = bool(frozen)
        return previous

    @property
    def learning_frozen(self) -> bool:
        return bool(getattr(self.brain, 'learning_frozen', False))

    # -- running a trial --------------------------------------------------
    def begin_trial(self, block: str = "train") -> TrialRecord:
        """Step 1-2: the player picks a cup and the food goes in, in plain view."""
        record = TrialRecord(index=len(self.trials) + 1, block=block,
                             learning_frozen=self.learning_frozen)
        baited = self.rng.choice(self.layout.identities)
        record.truth_baited_identity = baited
        record.truth_slot_of_identity = dict(self.layout.slot_of_identity)
        record.truth_baited_slot = self.layout.slot_of_identity[baited]

        self.current = record
        self._weights_at_start = self._weights()
        ledger = self._ledger()
        self._ledger_marks = {
            'changes': int(getattr(ledger, 'total_changes', 0) or 0),
            'episodes': len(getattr(ledger, 'episodes', []) or []),
        }
        self._stats_at_start = {
            k: v for k, v in self._brain_state().items()
            if k in ('hunger', 'happiness', 'satisfaction') and
            isinstance(v, (int, float))
        }
        self._enter(Phase.BAIT)
        return record

    def shuffle(self) -> Dict[str, int]:
        """Step 3: rearrange the cups. The bait travels with its own cup."""
        mapping = self.layout.shuffle()
        if self.current is not None:
            self.current.truth_slot_of_identity = dict(mapping)
            self.current.truth_baited_slot = mapping[
                self.current.truth_baited_identity]
        self._enter(Phase.SHUFFLE)
        return mapping

    def hide(self) -> int:
        """Step 4: the food is under a cup. Returns the slot it is under.

        The caller's job is to make that true in the world - to take the food
        out of the set of things the squid can see. `can_see_food` is then 0
        for the ordinary reason, and this layer asserts nothing about it.
        """
        self._enter(Phase.HIDDEN)
        return self.current.truth_baited_slot if self.current else -1

    def open_choice(self) -> None:
        """Step 5: the squid is swimming and we start watching where."""
        self._enter(Phase.CHOICE)

    def observe(self, squid_pos: Tuple[float, float], status: str = "",
                brain_state: Optional[Mapping[str, Any]] = None,
                t: Optional[float] = None) -> int:
        """One tick of watching. Returns the slot chosen, or -1 for not yet.

        Records what the squid perceived, then - during CHOICE only - reads its
        ordinary position to see whether it has arrived at a cup.
        """
        if self.current is None or self.phase in (Phase.IDLE, Phase.SETTLED):
            return -1
        state = dict(brain_state) if brain_state is not None else self._brain_state()
        self.current.perceptions.append(
            Perception.sample(self.phase, state, squid_pos, status, t))

        if self.phase is not Phase.CHOICE:
            return -1
        slot = self.layout.slot_nearest(squid_pos[0], squid_pos[1])
        if slot >= 0:
            self._commit_choice(slot, t)
        return slot

    def force_choice(self, slot: int, t: Optional[float] = None) -> None:
        """Record a selection the caller detected for itself (the game UI does)."""
        if self.current is not None and self.phase is Phase.CHOICE:
            self._commit_choice(int(slot), t)

    def _commit_choice(self, slot: int, t: Optional[float] = None) -> None:
        record = self.current
        now = time.time() if t is None else float(t)
        record.chosen_slot = int(slot)
        record.chosen_identity = self.layout.identity_at(slot)
        record.committed = True
        record.choice_latency = max(0.0, now - self._phase_started)
        record.correct = (record.chosen_slot == record.truth_baited_slot)
        self._enter(Phase.REVEAL)

    def give_up(self, t: Optional[float] = None) -> None:
        """The squid never reached a cup. Scored as a miss, and flagged as one.

        Not dropped: silently discarding the trials where the squid did not
        play would bias the hit rate upwards by exactly the trials the squid
        was least engaged in.
        """
        if self.current is None:
            return
        self.current.committed = False
        self.current.correct = False
        self.current.chosen_slot = -1
        self.current.choice_latency = max(
            0.0, (time.time() if t is None else float(t)) - self._phase_started)
        self._enter(Phase.REVEAL)

    def resolve(self, ate: bool) -> TrialRecord:
        """Steps 6-8: lift the cup, let the ordinary consequences happen, file it.

        `ate` is a report from the world, not a decision made here. When the
        squid picked the baited cup the caller reveals the food and the squid
        eats it through `Squid.eat()` - the same call a hand-fed squid gets.
        There is no reward path in this module.
        """
        record = self.current
        if record is None:
            raise RuntimeError("resolve() with no trial open")
        self._enter(Phase.OUTCOME)
        record.ate = bool(ate)

        now_state = self._brain_state()
        record.outcome_deltas = {
            k: float(now_state.get(k, 0.0)) - float(v)
            for k, v in self._stats_at_start.items()
            if isinstance(now_state.get(k, None), (int, float))
        }

        after = self._weights()
        for edge, new in after.items():
            old = self._weights_at_start.get(edge, 0.0)
            if abs(new - old) > 1e-9:
                record.weight_deltas[f"{edge[0]}->{edge[1]}"] = round(new - old, 6)

        ledger = self._ledger()
        if ledger is not None:
            changes = int(getattr(ledger, 'total_changes', 0) or 0)
            fresh = max(0, changes - self._ledger_marks.get('changes', 0))
            if fresh:
                try:
                    record.plasticity_events = [
                        e.describe() for e in ledger.recent_events(fresh)]
                except Exception:
                    record.plasticity_events = []
            episodes = list(getattr(ledger, 'episodes', []) or [])
            seen = self._ledger_marks.get('episodes', 0)
            record.episodes = [e.describe() for e in episodes[seen:]]
            try:
                record.knowledge = [k.describe()
                                    for k in ledger.knowledge(limit=6)]
            except Exception:
                record.knowledge = []

        record.learning_frozen = self.learning_frozen
        self.trials.append(record)
        self.current = None
        self._enter(Phase.SETTLED)
        return record

    def enter_phase(self, phase: Phase) -> None:
        """Move the open trial to `phase` and restart the phase clock.

        The headless runner walks the phases through the named steps below;
        the game UI drives them on a wall clock instead, and needs to say
        "we are in the choice phase now" without reaching into this object's
        internals to do it.
        """
        self._enter(phase)

    def _enter(self, phase: Phase) -> None:
        self.phase = phase
        self._phase_started = time.time()

    # -- reporting --------------------------------------------------------
    def block(self, name: str) -> List[TrialRecord]:
        return [r for r in self.trials if r.block == name]

    def score(self, name: str) -> BlockStats:
        return score_block(self.block(name), name, self.layout.cups)

    def report(self) -> Dict[str, Any]:
        """The whole run, block by block, plus the exploitability checks."""
        blocks = []
        for name in dict.fromkeys(r.block for r in self.trials):
            blocks.append(self.score(name))
        return {
            'cups': self.layout.cups,
            'chance': chance_rate(self.layout.cups),
            'trials': len(self.trials),
            'blocks': blocks,
            'fixed_strategies': fixed_strategy_scores(self.trials,
                                                      self.layout.cups),
            'omission_bias': omission_bias(self.trials, self.layout.cups),
        }


def fixed_strategy_scores(records: Sequence[TrialRecord],
                          cups: int = len(CUP_IDENTITIES)) -> Dict[str, float]:
    """What a squid with a fixed rule would have scored on these very trials.

    "Always slot 0", "always slot 1", ... and "always cup A", "always cup B",
    ... Every one of them should land near chance; if any of them does not,
    the randomisation is exploitable and a good score proves nothing.
    """
    out: Dict[str, float] = {}
    n = len(records)
    if not n:
        return out
    for slot in range(cups):
        out[f"always slot {slot}"] = sum(
            1 for r in records if r.truth_baited_slot == slot) / n
    identities = sorted({i for r in records for i in r.truth_slot_of_identity})
    for name in identities:
        out[f"always cup {name}"] = sum(
            1 for r in records if r.truth_baited_identity == name) / n
    return out


def omission_bias(records: Sequence[TrialRecord],
                  cups: int = len(CUP_IDENTITIES)) -> Dict[str, float]:
    """Is playing a trial related to which cup happened to be baited?

    Accuracy is scored over played trials only, which is sound just as long as
    the squid's willingness to play does not depend on the answer - and it
    cannot, because it has no way of knowing the answer. This measures it
    rather than asserting it: the play rate per baited slot should be flat.
    `spread` is the gap between the highest and lowest, and a large one would
    mean the omissions are not the random dropout the scoring assumes.
    """
    rates: Dict[str, float] = {}
    spread_values = []
    for slot in range(cups):
        block = [r for r in records if r.truth_baited_slot == slot]
        if not block:
            continue
        rate = sum(1 for r in block if r.committed) / len(block)
        rates[f"played when slot {slot} baited"] = rate
        spread_values.append(rate)
    rates['spread'] = (max(spread_values) - min(spread_values)
                       ) if spread_values else 0.0
    return rates
