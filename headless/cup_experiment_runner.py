#!/usr/bin/env python3
"""
cup_experiment_runner.py - the cup-and-food experiment, run reproducibly.

The game in `src/cup_game_ui.py` is the same experiment with a player in the
loop. This is the version you can seed, repeat and put in a test: a real
`HeadlessBrain` (the engine the game runs, not a model of it), a squid body in
tank coordinates, and the SHIPPING VisionWorker computing `can_see_food`.

Nothing here is a reimplementation of a mechanism that exists elsewhere:

  vision      `VisionWorker._calculate_visibility` - called directly. It touches
              no `self`, so it runs without the thread, and `can_see_food` is
              therefore decided by the code the game ships rather than by a
              second copy of the cone arithmetic that could quietly disagree.
  decisions   `decision_engine.select_action` - the same function the squid uses,
              and the same one a squid visiting another tank uses.
  movement    modelled on `Squid.move_squid`: an innate reflex towards food the
              squid can SEE, otherwise the decision's drive, otherwise a random
              walk. Food it cannot see cannot steer it.
  learning    `HeadlessBrain`, i.e. PlasticityEngine + STDP + ConsolidationManager
              + EnhancedNeurogenesis + CausalLedger, untouched.

The hidden food is never in `world.food_items` while it is under a cup, so
there is no object for the vision cone to find and none for a drive to home in
on. Its location exists in `CupExperiment` - the experimenter's notebook - and
nowhere the squid can reach.

Run it:

    python headless/cup_experiment_runner.py --seed 1 --train 40 --eval 30
    python headless/cup_experiment_runner.py --seed 1 --train 40 --eval 30 --control
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from headless_trainer import HeadlessBrain, HeadlessSquid, TrainingConfig  # noqa: E402
from src.cup_experiment import (  # noqa: E402
    CUP_IDENTITIES, Comparison, CupExperiment, CupLayout, DriveComparison,
    Phase, TrialRecord, DEFAULT_SELECT_RADIUS, persistence_values, score_block,
    two_proportion_p,
)
from src.decision_engine import select_action  # noqa: E402
from src.vision_worker import (  # noqa: E402
    SceneObject, SquidVisionState, VisionWorker,
)

TANK_WIDTH = 1280.0
TANK_HEIGHT = 900.0
SQUID_SIZE = 60.0
FOOD_SIZE = 64.0

#: Where a settled object rests on the tank floor - the same clamp
#: TamagotchiLogic.move_cheese applies, so a cup sits where food would.
FLOOR_Y = TANK_HEIGHT - 120.0 - FOOD_SIZE


def floor_slots(n: int = len(CUP_IDENTITIES)) -> List[Tuple[float, float]]:
    """n evenly spaced places along the tank floor."""
    margin = 140.0
    span = TANK_WIDTH - 2 * margin
    return [(margin + span * i / (n - 1), FLOOR_Y) for i in range(n)] \
        if n > 1 else [(TANK_WIDTH / 2, FLOOR_Y)]


# ---------------------------------------------------------------------------
# A body
# ---------------------------------------------------------------------------
class CupSquidBody(HeadlessSquid):
    """A squid with a position in the tank, moving the way the game's one does.

    `HeadlessSquid` keeps a normalised position it jitters at random, which is
    fine for a trainer that never asks where the squid is. This experiment's
    whole measurement is where the squid went, so the body needs real
    coordinates, a view cone and the heading arbitration from
    `Squid.move_squid`.
    """

    VIEW_CONE_ANGLE = math.pi / 2.5
    LOOK_AROUND_EVERY = 6          # ticks between re-aiming the cone

    def __init__(self, rng: random.Random, personality=None):
        super().__init__(personality)
        self.rng = rng
        self.squid_width = SQUID_SIZE
        self.squid_height = SQUID_SIZE
        self.squid_x = TANK_WIDTH / 2 - SQUID_SIZE / 2
        self.squid_y = TANK_HEIGHT / 2
        self.squid_direction = "right"
        self.base_speed = 22.0
        self.current_view_angle = rng.uniform(0, 2 * math.pi)
        self.view_cone_angle = self.VIEW_CONE_ANGLE
        self.target_food: Optional[Tuple[float, float]] = None
        self._ticks = 0

    # -- geometry -------------------------------------------------------
    @property
    def centre(self) -> Tuple[float, float]:
        return (self.squid_x + self.squid_width / 2,
                self.squid_y + self.squid_height / 2)

    def vision_state(self) -> SquidVisionState:
        return SquidVisionState(
            squid_x=self.squid_x, squid_y=self.squid_y,
            squid_width=self.squid_width, squid_height=self.squid_height,
            current_view_angle=self.current_view_angle,
            view_cone_angle=self.view_cone_angle,
            window_width=TANK_WIDTH, window_height=TANK_HEIGHT)

    def look(self, food_positions: Sequence[Tuple[float, float]]):
        """What the squid can see, decided by the shipping VisionWorker.

        `_calculate_visibility` never touches `self`, so it is called unbound:
        the cone arithmetic is literally the game's, with no thread and no Qt
        event loop needed to get at it.
        """
        objects = [SceneObject(x=x, y=y, width=FOOD_SIZE, height=FOOD_SIZE,
                               category='food', obj_id=i)
                   for i, (x, y) in enumerate(food_positions)]
        return VisionWorker._calculate_visibility(None, self.vision_state(), objects)

    # -- movement -------------------------------------------------------
    def move_towards(self, x: float, y: float) -> None:
        """Pick the axis with the bigger error, as Squid.move_towards does."""
        dx = x - (self.squid_x + self.squid_width / 2)
        dy = y - (self.squid_y + self.squid_height / 2)
        if abs(dx) > abs(dy):
            self.squid_direction = "right" if dx > 0 else "left"
        else:
            self.squid_direction = "down" if dy > 0 else "up"

    DIRECTIONS = ("left", "right", "up", "down")

    def move_randomly(self) -> None:
        """`Squid.move_randomly`: a one-in-five chance of turning, and never
        back onto the heading it already had."""
        if self.rng.random() < 0.20:
            choices = [d for d in self.DIRECTIONS if d != self.squid_direction]
            self.squid_direction = self.rng.choice(choices)

    def step(self, visible_food: Sequence[Tuple[float, float]],
             drive_target: Optional[Tuple[float, float]]) -> None:
        """One tick of the heading arbitration and one step of the body.

        Order copied from `Squid.move_squid`: the innate food reflex first -
        it needs no brain and interrupts whatever was being deliberated - then
        the decision's drive, then a random walk. Food the squid cannot see is
        not in `visible_food` and so cannot appear in this function at all.
        """
        self._ticks += 1
        if visible_food:
            cx, cy = self.centre
            target = min(visible_food,
                         key=lambda f: math.hypot(f[0] - cx, f[1] - cy))
            self.pursuing_food = True
            self.target_food = target
            self.move_towards(target[0] + FOOD_SIZE / 2, target[1] + FOOD_SIZE / 2)
            self.current_view_angle = math.atan2(target[1] - cy, target[0] - cx)
        else:
            if self.pursuing_food:
                self.pursuing_food = False
                self.target_food = None
            if drive_target is not None:
                self.move_towards(*drive_target)
            else:
                self.move_randomly()
            if self._ticks % self.LOOK_AROUND_EVERY == 0:
                self.current_view_angle = self.rng.uniform(0, 2 * math.pi)

        speed = self.base_speed
        if self.squid_direction == "left":
            self.squid_x -= speed
        elif self.squid_direction == "right":
            self.squid_x += speed
        elif self.squid_direction == "up":
            self.squid_y -= speed
        elif self.squid_direction == "down":
            self.squid_y += speed

        # Boundaries, as the game clamps them.
        low_x, high_x = 50.0, TANK_WIDTH - 50.0 - self.squid_width
        low_y, high_y = 50.0, TANK_HEIGHT - 120.0 - self.squid_height
        if self.squid_x < low_x:
            self.squid_x, self.squid_direction = low_x, "right"
        elif self.squid_x > high_x:
            self.squid_x, self.squid_direction = high_x, "left"
        if self.squid_y < low_y:
            self.squid_y, self.squid_direction = low_y, "down"
        elif self.squid_y > high_y:
            self.squid_y, self.squid_direction = high_y, "up"

        # Keep the normalised position HeadlessSquid reports in step with the
        # real one, so `position` in brain state is not two different places.
        self.x = self.squid_x / TANK_WIDTH
        self.y = self.squid_y / TANK_HEIGHT

    def update(self, dt: float = 1.0):
        """Drive drift, without HeadlessSquid's normalised random walk.

        The base class jitters `x`/`y` itself; here the body owns its position
        and that jitter would be a second mover fighting `step()`.
        """
        x, y = self.x, self.y
        super().update(dt)
        self.x, self.y = x, y

    def rest(self, dt: float = 1.0) -> None:
        """One second of sleep, with the game's own restorative rates.

        `HeadlessSquid.update` raises sleepiness and never lowers it, so a
        squid that falls asleep in the trainer stays asleep; the recovery lives
        in `TamagotchiLogic.update_simulation`, which this experiment does not
        run. The numbers are that method's.
        """
        self.sleepiness = max(0.0, self.sleepiness - 28.0 * dt)
        self.happiness = min(100.0, self.happiness + 0.45 * dt)
        self.satisfaction = min(100.0, self.satisfaction + 0.30 * dt)
        if self.sleepiness <= 25.0:
            self.is_sleeping = False
            self.status = "roaming"


# ---------------------------------------------------------------------------
# The world one trial happens in
# ---------------------------------------------------------------------------
@dataclass
class TrialSettings:
    """The protocol, as numbers. Every one of them is a stated choice."""

    #: Step 2 is "the food is initially visible to the squid", so the bait
    #: phase ends when the squid has ACTUALLY seen it rather than after a fixed
    #: count that a wandering view cone might spend looking the other way.
    #: This is the patience limit, not the duration.
    bait_ticks: int = 120
    #: ...and then it gets a proper look. Without a dwell the phase ends on the
    #: first frame of the sighting, which is one propagation step - not enough
    #: for `can_see_food -> act_eat` to drive anything, and not what anyone
    #: would call an experience of where the food is.
    bait_dwell: int = 12

    #: Step 3. The cups are rearranged and the bait travels with its own cup,
    #: IN VIEW - that is what makes a shell game solvable in principle rather
    #: than a guess. Long enough that the squid can see where its cup went;
    #: with this at 3 the squid was still sitting at the pre-shuffle slot when
    #: the choice opened, which scored BELOW chance for a reason that had
    #: nothing to do with what it knew.
    shuffle_ticks: int = 16

    #: Step 4, and the actual memory demand: how long the food stays hidden
    #: before the squid is allowed to commit. Long enough that the heading it
    #: had when the food vanished is gone - the body re-randomises its
    #: direction with p=0.25 per tick, so after ~20 ticks a trial cannot be
    #: won by coasting. Vary it with --delay: at delay 0 a good score means
    #: ballistic continuation, not memory, and the report says so.
    hidden_ticks: int = 20
    #: The start position, and the single most important control in the
    #: apparatus. The squid spends the bait and shuffle phases swimming TO the
    #: baited cup, so when the food vanishes it is standing on the answer - and
    #: a squid that simply picks the nearest cup then scores far above 1/3
    #: while knowing nothing whatever. Requiring it to be this far from EVERY
    #: cup before the choice opens breaks the correlation between where it
    #: happens to be and where the food is. Same rule for all three cups, so it
    #: introduces no preference of its own.
    #:
    #: The cups are ~500px apart, so this is most of the way to the next one.
    start_clearance: float = 330.0
    clearance_ticks: int = 220

    #: How long the squid gets to reach a cup. Generous, because a trial it
    #: never plays is an omission rather than an error and the fewer of those
    #: the better - but capped, because waiting indefinitely would turn every
    #: trial into "eventually it bumped into something".
    choice_ticks: int = 320
    outcome_ticks: int = 10
    hebbian_interval: int = 10
    select_radius: float = DEFAULT_SELECT_RADIUS

    # --- husbandry: looking after the animal BETWEEN trials ---------------
    #: A trial is several minutes of the squid's life and a run is dozens of
    #: trials. Left to itself over that span the trainer's squid model starves,
    #: never sleeps off its sleepiness and - because `HeadlessSquid.update`
    #: only ever RAISES anxiety - finishes every long run pinned at 100, in a
    #: collapse that inhibits every voluntary action it has. An experiment run
    #: that way measures a distressed animal, not a learning one.
    #:
    #: So between trials, and never inside one, the experimenter does what a
    #: player does: lets it sleep, feeds it, cleans the tank. None of it
    #: touches the network directly and none of it happens while a trial is
    #: open, so it cannot contribute to the contingency being tested.
    husbandry: bool = True
    clean_below: float = 40.0
    #: Rested well before `HeadlessSquid` would put itself to sleep at 90.
    #: A trial is long enough to add ~25 sleepiness, so a squid that starts one
    #: at 70 falls asleep partway through - and a sleeping squid's `act_eat` is
    #: held at zero by the sleep gating, which silently turned the drive
    #: measure into a reading of how tired the animal was.
    rest_above: float = 45.0
    wake_at: float = 25.0           # the game's own waking threshold
    max_rest_ticks: int = 300
    #: Maintenance feeding. A squid that only eats when it guesses right eats
    #: on a third of trials, so hunger climbs until `hunger -> act_eat` pins
    #: the neuron at 100 and the drive measure becomes a ceiling no learning
    #: could move. Fed enough to work, hungry enough to care.
    feed_above: float = 70.0
    max_feeds_per_trial: int = 3
    #: A fed, clean, rested animal calms down. `HeadlessSquid` has no anxiety
    #: decay at all, so this relaxes it towards that model's own resting value
    #: rather than inventing a level for it.
    resting_anxiety: float = 10.0
    calm_fraction: float = 0.34


class CupWorld:
    """Tank, cups, body, brain. Drives one `CupExperiment` through its phases."""

    def __init__(self, seed: int = 0, settings: Optional[TrialSettings] = None,
                 config: Optional[TrainingConfig] = None):
        # Seed the global module too, not just this world's own stream.
        # `decision_engine.select_action` draws its tie-breaking jitter from
        # `random` directly, so a run is only reproducible if that is seeded as
        # well - the same reason `HeadlessSimulation` seeds it in ITS
        # constructor, and the same place to do it.
        random.seed(seed)
        self.rng = random.Random(seed)
        self.settings = settings or TrialSettings()
        self.brain = HeadlessBrain(config or TrainingConfig(seed=seed))
        self.body = CupSquidBody(self.rng)
        self.layout = CupLayout(floor_slots(), CUP_IDENTITIES, self.rng)
        self.experiment = CupExperiment(self.brain, self.layout, self.rng)

        #: Food the squid could see if it looked - the ONLY food that reaches
        #: the vision cone or a movement drive. While the bait is under a cup
        #: this list is empty, which is what makes the food genuinely hidden.
        self.food_items: List[Tuple[float, float]] = []
        self.tick = 0
        self.saw_bait: List[bool] = []
        self.maintenance_feeds = 0

    # -- one tick -------------------------------------------------------
    def _sensors(self, vision) -> Dict[str, float]:
        """The sensor block, matching `BrainNeuronHooks` handler for handler.

        No entry here exists because of this experiment, and none of them
        carries a position: this is the whole of what the world tells the
        network, and it is the same set a squid gets on any ordinary day.
        """
        threat = self.body.anxiety + (30.0 if self.body.is_fleeing else 0.0)
        return {
            'can_see_food': 100.0 if vision.can_see_food else 0.0,
            'plant_proximity': float(vision.plant_proximity_value),
            'external_stimulus': 0.0,
            'threat_level': max(0.0, min(100.0, threat)),
            'pursuing_food': 100.0 if self.body.pursuing_food else 0.0,
            'is_sick': 100.0 if self.body.is_sick else 0.0,
            'is_fleeing': 100.0 if self.body.is_fleeing else 0.0,
            'is_eating': 100.0 if self.body.is_eating else 0.0,
            'is_sleeping': 100.0 if self.body.is_sleeping else 0.0,
            'is_startled': 100.0 if self.body.is_startled else 0.0,
        }

    def step(self, learn: bool = True) -> Dict[str, float]:
        """One simulation tick: sense, decide, learn, move."""
        self.tick += 1
        self.body.update(1.0)
        self.brain.advance_clock(1.0)

        vision = self.body.look(self.food_items)
        state = self.body.get_state_dict()
        state.update(self._sensors(vision))
        self.brain.update_state(state)

        behaviour, _confidence, _urgency = select_action(dict(self.brain.state))
        self.body.status = behaviour or "exploring"
        self.brain.causal_learning.on_action(self.body.status)
        self.brain.propagate()

        if learn and self.tick % self.settings.hebbian_interval == 0:
            self.brain.perform_hebbian_learning()
        if learn:
            self.brain.check_neurogenesis(state, self.tick)

        # Where the decision sends the body. `DecisionEngine._execute` seeks the
        # nearest FOOD ITEM when it chooses eating - and while the bait is under
        # a cup there is no food item, so it drifts. That absence is the point:
        # it is the same absence the squid's eyes report.
        drive_target = None
        if behaviour == "eating" and self.food_items:
            cx, cy = self.body.centre
            drive_target = min(self.food_items,
                               key=lambda f: math.hypot(f[0] - cx, f[1] - cy))

        visible = list(vision.visible_food)
        self.body.step(visible, drive_target)
        return dict(self.brain.state)

    def _run(self, ticks: int, learn: bool, watch: bool = False,
             until_seen: bool = False) -> bool:
        """Advance the world, feeding every tick to the open trial.

        Returns True if the stopping condition fired: a choice was committed
        (`watch`), or the squid actually laid eyes on the food (`until_seen`).
        """
        for _ in range(int(ticks)):
            state = self.step(learn=learn)
            slot = self.experiment.observe(
                self.body.centre, self.body.status, state, t=float(self.tick))
            if watch and slot >= 0:
                return True
            if until_seen and float(state.get('can_see_food', 0.0)) >= 100.0:
                return True
        return False

    def husbandry(self) -> None:
        """Look after the animal between trials.

        A sleeping squid is left to sleep itself out and a dirty tank is
        cleaned - the two things a player does between feeds. Neither touches
        the network directly; both go through the ordinary squid model.
        """
        if not self.settings.husbandry:
            return
        s = self.settings
        if self.body.sleepiness > s.rest_above or self.body.is_sleeping:
            self.body.is_sleeping = True
            rested = 0
            while self.body.sleepiness > s.wake_at and rested < s.max_rest_ticks:
                self.body.rest(1.0)
                self.brain.advance_clock(1.0)
                rested += 1
            self.body.is_sleeping = False
            self.body.status = "roaming"
        fed = 0
        while self.body.hunger > s.feed_above and fed < s.max_feeds_per_trial:
            self.body.feed()
            fed += 1
        if fed:
            self.body.is_eating = False
            self.body.pursuing_food = False
            self.maintenance_feeds += fed
        if self.body.cleanliness < s.clean_below:
            self.body.clean()
        if self.body.hunger < s.feed_above and self.body.cleanliness > 50.0:
            self.body.anxiety += (s.resting_anxiety - self.body.anxiety) * s.calm_fraction

    # -- one trial ------------------------------------------------------
    def _clear_of_cups(self) -> bool:
        """Is the squid far enough from every cup to start from a fair place?"""
        return self.layout.slot_nearest(
            *self.body.centre, radius=self.settings.start_clearance) < 0

    def run_trial(self, block: str = "train", learn: bool = True,
                  show_bait: bool = True) -> TrialRecord:
        """One trial. `show_bait=False` is the no-information control.

        With the bait never shown, the squid has no way even in principle to be
        right more often than 1 in 3, so that arm measures the chance rate of
        this exact apparatus - cups, geometry, body, wander and all - rather
        than asserting 33.3% from the arithmetic of three cups.
        """
        s = self.settings
        self.husbandry()
        record = self.experiment.begin_trial(block)

        # 1-2. The food goes under a cup, in plain view, and stays there until
        #      the squid has seen it and had a proper look at where it is.
        if show_bait:
            self.food_items = [
                self.layout.position_of_slot(record.truth_baited_slot)]
            seen = self._run(s.bait_ticks, learn, until_seen=True)
            self.saw_bait.append(bool(seen))
            if seen:
                self._run(s.bait_dwell, learn)

        # 3. Shuffle. The bait travels with its cup and is still in view, so
        #    the squid CAN watch where its cup went. Whether anything in the
        #    squid retains that is the question the trial asks.
        self.experiment.shuffle()
        if show_bait:
            self.food_items = [
                self.layout.position_of_slot(record.truth_baited_slot)]
        self._run(s.shuffle_ticks, learn)

        # 4. Hidden: the food leaves the set of things that can be seen or
        #    homed in on. `can_see_food` falls to 0 through the ordinary path,
        #    and the retention interval runs.
        self.food_items = []
        self.experiment.hide()
        self._run(s.hidden_ticks, learn)
        waited = 0
        while not self._clear_of_cups() and waited < s.clearance_ticks:
            self._run(1, learn)
            waited += 1
        record.started_clear = self._clear_of_cups()

        # 5. The squid swims. Whichever cup it reaches first is its selection.
        self.experiment.open_choice()
        committed = self._run(s.choice_ticks, learn, watch=True)
        if not committed:
            self.experiment.give_up(t=float(self.tick))

        # 6-7. Lift the cup. If it picked right, the food is there and it eats -
        #      the same consequence a hand-fed squid gets, through the same
        #      stat changes. If it picked wrong, nothing happens, which is
        #      also information.
        ate = False
        if record.correct:
            self.food_items = [self.layout.position_of_slot(record.chosen_slot)]
            self.body.feed()
            ate = True
        self._run(s.outcome_ticks, learn)
        self.food_items = []
        self.body.is_eating = False

        return self.experiment.resolve(ate)

    # -- a whole run ----------------------------------------------------
    def run(self, train: int = 40, evaluate: int = 30,
            control: bool = False, naive: int = 20) -> Dict:
        """Baseline, then training, then evaluation with learning frozen.

        Three blocks, and each answers a different question.

        `naive` is the no-information baseline: the same apparatus, the same
        body, the same wander, but the squid is never shown the bait. Nothing
        it does can beat 1 in 3, so whatever this block scores is what chance
        looks like HERE - the number the other blocks have to be compared
        against, rather than a 33.3% taken on faith. It runs frozen, because it
        is a measurement and not a training phase.

        `train` is the protocol with the squid free to learn from it.

        `eval` is the protocol again with learning frozen, so an improvement
        over the baseline cannot be something that happened during the
        measuring.

        `control` freezes training too - the learning-disabled arm. Comparing
        eval against control is what separates a real improvement from one the
        apparatus would have produced anyway: a squid ends a trial near the cup
        it last saw the food at, and being already there is worth points that
        have nothing to do with having learned anything.
        """
        neurons_before = self.experiment.neuron_names()

        self.experiment.set_learning_frozen(True)
        for _ in range(int(naive)):
            self.run_trial("naive", learn=False, show_bait=False)

        self.experiment.set_learning_frozen(control)
        for _ in range(int(train)):
            self.run_trial("train", learn=not control)

        # Frozen evaluation. `set_learning_frozen` refuses every write through
        # `RecordedSynapses.apply_weight_change`, so nothing measured below can
        # be the product of adaptation happening during the measurement.
        self.experiment.set_learning_frozen(True)
        weights_at_freeze = dict(self.brain.weights)
        changes_at_freeze = int(self.brain.ledger.total_changes)
        for _ in range(int(evaluate)):
            self.run_trial("eval", learn=False)
        froze_clean = (dict(self.brain.weights) == weights_at_freeze and
                       int(self.brain.ledger.total_changes) == changes_at_freeze)
        self.experiment.set_learning_frozen(False)

        report = self.experiment.report()
        report.update({
            'seed_trials': len(self.experiment.trials),
            'control': bool(control),
            'evaluation_was_frozen': froze_clean,
            'neurons_before': sorted(neurons_before),
            'neurons_after': sorted(self.experiment.neuron_names()),
            'neurons_added': sorted(self.experiment.neuron_names() - neurons_before),
            'saw_bait_rate': (sum(self.saw_bait) / len(self.saw_bait))
            if self.saw_bait else 0.0,
            'hidden_ticks': self.settings.hidden_ticks,
            'maintenance_feeds': self.maintenance_feeds,
            'weight_changes': int(self.brain.ledger.total_changes),
            'ledger': self.brain.ledger.summary(),
        })
        return report


# ---------------------------------------------------------------------------
# Running both arms
# ---------------------------------------------------------------------------
def run_paired(seed: int = 1, naive: int = 30, train: int = 40,
               evaluate: int = 40, settings: Optional[TrialSettings] = None,
               growth: bool = True) -> Dict:
    """Run the learning arm and the learning-disabled arm from the same seed.

    This is the comparison the design turns on. Measuring the learning arm
    against 1/3 would credit it with everything the apparatus gives away for
    free - and the apparatus gives away a lot, because a squid finishes a trial
    near the cup it last saw the food at, and the nearest cup is the one it
    then swims to. The control arm is that same free gift with learning
    switched off. Whatever is left over is learning.

    Same seed for both arms, so the two see the same opening conditions. The
    streams diverge as soon as behaviour does, which is the point: if learning
    changes behaviour, the divergence is the effect.
    """
    def one(control: bool) -> Tuple[CupWorld, Dict]:
        config = TrainingConfig(seed=seed)
        config.neurogenesis_enabled = bool(growth)
        world = CupWorld(seed=seed, settings=settings or TrialSettings(),
                         config=config)
        return world, world.run(train=train, evaluate=evaluate,
                                control=control, naive=naive)

    learning_world, learning = one(control=False)
    control_world, control = one(control=True)

    def block(report: Dict, name: str):
        for stats in report['blocks']:
            if stats.block == name:
                return stats
        return None

    comparisons = []
    for name, label in (("eval", "eval: learning vs frozen control"),
                        ("train", "train: learning vs frozen control")):
        a, b = block(learning, name), block(control, name)
        if a is not None and b is not None:
            comparisons.append(Comparison(label, a, b))
    naive_block = block(learning, "naive")
    eval_block = block(learning, "eval")
    if naive_block is not None and eval_block is not None:
        comparisons.insert(0, Comparison(
            "eval vs no-information baseline", eval_block, naive_block))

    # The other measure: food-seeking drive with the food out of sight. Read
    # per trial rather than off the block means, so the test has samples to
    # permute.
    def drive(world, name):
        return persistence_values(
            [r for r in world.experiment.trials if r.block == name])

    drive_comparisons = [
        DriveComparison("eval: learning vs frozen control",
                        drive(learning_world, "eval"),
                        drive(control_world, "eval")),
        DriveComparison("learning arm: eval vs its own no-information baseline",
                        drive(learning_world, "eval"),
                        drive(learning_world, "naive")),
        DriveComparison("control arm: eval vs its own no-information baseline",
                        drive(control_world, "eval"),
                        drive(control_world, "naive")),
    ]

    return {
        'learning': learning,
        'control': control,
        'comparisons': comparisons,
        'drive_comparisons': drive_comparisons,
        'worlds': (learning_world, control_world),
        'growth': bool(growth),
    }


# ---------------------------------------------------------------------------
# Replication
# ---------------------------------------------------------------------------
def replicate(seeds: Sequence[int], naive: int = 30, train: int = 50,
              evaluate: int = 50, settings: Optional[TrialSettings] = None,
              growth: bool = False) -> Dict:
    """Run the paired design over several seeds and POOL the trials.

    This exists because of a real mistake made while building this experiment.
    Seed 7 produced a rise in occlusion persistence of +22 percentage points at
    p < 0.001 - a clean, significant, entirely convincing effect. Seed 2
    produced -1 point at p = 0.68. One run of this experiment is one animal, and
    one animal is not a result; a single seed will hand you a significant effect
    roughly as often as the significance level says it will.

    Pooling the trials rather than averaging the per-seed p-values, because a
    mean of p-values is not a p-value.
    """
    seeds = list(seeds)
    per_seed = []
    pooled = {'learning': {}, 'control': {}}
    for arm in pooled:
        pooled[arm] = {'naive': [], 'train': [], 'eval': []}

    for seed in seeds:
        paired = replicate_one(seed, naive, train, evaluate, settings, growth)
        per_seed.append(paired)
        for arm, world in (('learning', paired['worlds'][0]),
                           ('control', paired['worlds'][1])):
            for name in pooled[arm]:
                pooled[arm][name].extend(
                    r for r in world.experiment.trials if r.block == name)

    blocks = {arm: {name: score_block(records, name)
                    for name, records in by_block.items()}
              for arm, by_block in pooled.items()}

    comparisons = [
        Comparison("eval: learning vs frozen control",
                   blocks['learning']['eval'], blocks['control']['eval']),
        Comparison("eval vs no-information baseline",
                   blocks['learning']['eval'], blocks['learning']['naive']),
    ]
    drive_comparisons = [
        DriveComparison("eval: learning vs frozen control",
                        persistence_values(pooled['learning']['eval']),
                        persistence_values(pooled['control']['eval'])),
        DriveComparison("learning arm: eval vs no-information baseline",
                        persistence_values(pooled['learning']['eval']),
                        persistence_values(pooled['learning']['naive'])),
        DriveComparison("control arm: eval vs no-information baseline",
                        persistence_values(pooled['control']['eval']),
                        persistence_values(pooled['control']['naive'])),
    ]
    return {
        'seeds': seeds,
        'per_seed': per_seed,
        'blocks': blocks,
        'comparisons': comparisons,
        'drive_comparisons': drive_comparisons,
    }


def replicate_one(seed, naive, train, evaluate, settings, growth):
    return run_paired(seed=seed, naive=naive, train=train, evaluate=evaluate,
                      settings=settings, growth=growth)


def format_replication(result: Dict) -> str:
    lines = ["=" * 72,
             f"REPLICATION over {len(result['seeds'])} seeds: "
             f"{result['seeds']}",
             "=" * 72,
             "",
             "-- per seed, so you can see the spread " + "-" * 32]
    for seed, paired in zip(result['seeds'], result['per_seed']):
        cup = next(c for c in paired['comparisons']
                   if c.label.startswith("eval: "))
        drive = next(c for c in paired['drive_comparisons']
                     if c.label.startswith("eval: "))
        lines.append(f"  seed {seed:>4}  cup   {cup.describe()}")
        lines.append(f"            drive {drive.describe()}")
    lines += ["", "-- pooled over every trial " + "-" * 45]
    for arm in ('learning', 'control'):
        for name in ('naive', 'train', 'eval'):
            lines.append(f"  {arm:<9} " + result['blocks'][arm][name].describe())
    lines += ["", "-- the verdict, on the pooled data " + "-" * 37,
              "  WHICH CUP:"]
    for comparison in result['comparisons']:
        lines.append("    " + comparison.describe())
    lines.append("  DRIVE UNDER OCCLUSION:")
    for comparison in result['drive_comparisons']:
        lines.append("    " + comparison.describe())
    lines.append("=" * 72)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def format_report(report: Dict) -> str:
    lines = []
    lines.append("=" * 72)
    lines.append("CUP-AND-FOOD EXPERIMENT")
    lines.append("=" * 72)
    lines.append(f"cups: {report['cups']}   chance: {report['chance']:.1%}   "
                 f"trials: {report['trials']}"
                 f"{'   [LEARNING-DISABLED CONTROL]' if report['control'] else ''}")
    lines.append(f"bait seen before hiding on {report['saw_bait_rate']:.0%} of trials"
                 f"   retention interval: {report['hidden_ticks']} ticks")
    lines.append("")
    lines.append("-- accuracy: which cup did it go to? " + "-" * 35)
    for stats in report['blocks']:
        lines.append("  " + stats.describe())
    lines.append("")
    lines.append("-- where the trial started from " + "-" * 40)
    for stats in report['blocks']:
        lines.append("  " + stats.describe_start())
    lines.append("")
    lines.append("-- drive: did it still want to eat once the food vanished? " + "-" * 13)
    for stats in report['blocks']:
        lines.append("  " + stats.describe_drive())
    lines.append("")
    lines.append("-- controls " + "-" * 60)
    lines.append("  a fixed strategy would have scored:")
    for name, rate in sorted(report['fixed_strategies'].items()):
        lines.append(f"    {name:<16} {rate:.1%}")
    bias = report.get('omission_bias', {})
    if bias:
        lines.append("  omissions are unrelated to the answer "
                     f"(spread {bias.get('spread', 0.0):.1%}):")
        for name, rate in sorted(k for k in bias.items() if k[0] != 'spread'):
            lines.append(f"    {name:<28} {rate:.1%}")
    lines.append(f"  evaluation block was genuinely frozen: "
                 f"{report['evaluation_was_frozen']}")
    lines.append(f"  neurons added by the experiment: "
                 f"{report['neurons_added'] or 'none'}")
    lines.append("")
    lines.append("-- learning machinery " + "-" * 50)
    lines.append(f"  recorded weight changes: {report['weight_changes']}")
    lines.append(f"  maintenance feeds between trials: "
                 f"{report['maintenance_feeds']}")
    for mechanism, total in sorted(report['ledger'].get('by_mechanism', {}).items()):
        lines.append(f"    {mechanism:<14} {total:+.3f} total movement")
    lines.append(f"  episodes: {report['ledger'].get('episodes', 0)}   "
                 f"neurons grown: {report['ledger'].get('neurons_grown', 0)}")
    lines.append("=" * 72)
    return "\n".join(lines)


def format_paired(paired: Dict) -> str:
    lines = [format_report(paired['learning'])]
    lines.append("")
    lines.append("=" * 72)
    lines.append("LEARNING-DISABLED CONTROL ARM (same seed, plasticity frozen "
                 "throughout)")
    lines.append("=" * 72)
    for stats in paired['control']['blocks']:
        lines.append("  " + stats.describe())
    lines.append("")
    lines.append("=" * 72)
    lines.append("DID IT LEARN?")
    lines.append("=" * 72)
    lines.append("  WHICH CUP - a spatial fact:")
    for comparison in paired['comparisons']:
        lines.append("    " + comparison.describe())
    lines.append("")
    lines.append("  HOW MUCH IT STILL WANTED TO EAT once the food vanished -")
    lines.append("  an activation on a neuron it already had:")
    for comparison in paired.get('drive_comparisons', []):
        lines.append("    " + comparison.describe())
    lines.append("")

    cup_verdict = next((c for c in paired['comparisons']
                        if c.label.startswith("eval: ")), None)
    drive_verdict = next((c for c in paired.get('drive_comparisons', [])
                          if c.label.startswith("eval: ")), None)
    if cup_verdict is not None and not cup_verdict.significant:
        lines.append("  WHICH CUP: no. The learning arm and the frozen arm")
        lines.append("  score alike, and alike with a squid that was never")
        lines.append("  shown the bait at all. Nothing the world writes into")
        lines.append("  this network distinguishes one cup from another and no")
        lines.append("  action it can take is directional, so 'the food is")
        lines.append("  under the left one' is not a thought this brain can")
        lines.append("  have - and experience cannot teach a representation")
        lines.append("  the architecture cannot form. See the module docstring")
        lines.append("  of src/cup_experiment.py.")
    if drive_verdict is not None and drive_verdict.significant:
        lines.append("")
        lines.append("  DRIVE: yes. Food-seeking survives occlusion better")
        lines.append("  after training than it does with plasticity switched")
        lines.append("  off, measured in a block where learning was frozen, so")
        lines.append("  it is not adaptation happening during the measurement.")
        lines.append("  Every weight behind it is in the ledger above.")
    lines.append("=" * 72)
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--train", type=int, default=40)
    ap.add_argument("--eval", type=int, default=30, dest="evaluate")
    ap.add_argument("--naive", type=int, default=20,
                    help="no-information baseline trials (bait never shown)")
    ap.add_argument("--no-growth", action="store_true", dest="no_growth",
                    help="switch off neurogenesis, isolating plasticity")
    ap.add_argument("--control", action="store_true",
                    help="run ONLY the learning-disabled control arm")
    ap.add_argument("--seeds", type=int, default=0, metavar="N",
                    help="replicate the paired design over N seeds starting at "
                         "--seed and pool the trials. One seed is one animal, "
                         "and one animal is not a result.")
    ap.add_argument("--single", action="store_true",
                    help="run one arm instead of the paired learning-vs-control "
                         "design")
    ap.add_argument("--delay", type=int, default=None,
                    help="retention interval in ticks (default 20). At 0 a "
                         "good score means the squid coasted into the cup it "
                         "was already heading for, not that it remembered.")
    ap.add_argument("--json", type=str, default=None,
                    help="also write the full trial log here")
    args = ap.parse_args()

    settings = TrialSettings()
    if args.delay is not None:
        settings.hidden_ticks = max(0, args.delay)
    if args.seeds:
        result = replicate(range(args.seed, args.seed + args.seeds),
                           naive=args.naive, train=args.train,
                           evaluate=args.evaluate, settings=settings,
                           growth=not args.no_growth)
        print(format_replication(result))
        return 0

    if args.single or args.control:
        config = TrainingConfig(seed=args.seed)
        config.neurogenesis_enabled = not args.no_growth
        world = CupWorld(seed=args.seed, settings=settings, config=config)
        report = world.run(train=args.train, evaluate=args.evaluate,
                           control=args.control, naive=args.naive)
        print(format_report(report))
        worlds = [world]
        reports = [report]
    else:
        paired = run_paired(seed=args.seed, naive=args.naive, train=args.train,
                            evaluate=args.evaluate, settings=settings,
                            growth=not args.no_growth)
        print(format_paired(paired))
        worlds = list(paired['worlds'])
        reports = [paired['learning'], paired['control']]

    if args.json:
        payload = {
            'arms': [
                {
                    'report': {k: v for k, v in report.items()
                               if k not in ('blocks',)},
                    'blocks': [vars(b) for b in report['blocks']],
                    'trials': [t.to_dict() for t in world.experiment.trials],
                }
                for world, report in zip(worlds, reports)
            ],
        }
        Path(args.json).write_text(json.dumps(payload, indent=2))
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
