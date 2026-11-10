"""How the squid learns what is worth doing: motor exploration and
outcome-gated motor synapses.

A synapse into an action neuron says "in this situation, do that". The
correlational rule cannot teach it - the cue drives the action, so the two
always move together and the rule concludes the squid should do more of
whatever it already does. And an action nothing drives is never tried, so
there is never any evidence about it at all: a newborn's rest, shelter and
play neurons have no excitatory wiring, and co-activation alone will not give
them any.

This module supplies both missing halves.

  MOTOR EXPLORATION   Now and then, more often the more curious the squid is,
                      one of its unwired action neurons fires by itself. It is
                      a spike in a neuron, not a decision: the ordinary
                      contest between actions (decision_engine.select_action)
                      still decides what the body does, and a real urge - to
                      flee, to eat - always wins.

  OUTCOME EVIDENCE    When an action the squid actually took has run its
                      course, the causal ledger has measured what happened to
                      each drive over and above how it drifts anyway. That is
                      weighed by how much the squid NEEDED it: sleepiness
                      falling is worth something to a tired squid and nothing
                      to a rested one. The result is filed against every cue
                      that was present, and - separately - against every cue
                      that was not.

  THE SYNAPSE         A cue -> action synapse is moved only when the action
                      has been tried both WITH the cue and WITHOUT it, and
                      came out differently. The weight then tracks the size of
                      that difference: up when the action works better with
                      the cue, down again if it stops, below zero if it works
                      worse. A cue that was simply always there is credited
                      with nothing, because nothing distinguishes it.

  THE COMBINATION     Sometimes an action pays only when two things are true
                      together - shelter when a plant is in sight AND the
                      squid is frightened. No single synapse can say that. When
                      the evidence shows each cue mattering only in the
                      presence of the other, this module reports a combination
                      the brain has no neuron for, and neurogenesis may grow
                      one (see `wanted_combinations`). That neuron is then a
                      cue like any other.

Nothing here tells the squid what to do in any situation. The need-weighted
outcome is a measure of how things turned out, the same for every action; the
associations are the squid's own.

Originated on the CANARY branch (experiments/action_discovery), where the
single-cue rule was validated against placebo and overgeneralisation controls.
What is added here: weights that follow the evidence in both directions,
evidence that fades so an old contingency can be unlearned, exploration paced
by curiosity, combinations, and persistence.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, FrozenSet, Iterable, List, Optional, Tuple

from .brain_constants import (
    ACTION_BEHAVIOURS, ACTION_THRESHOLDS, CORE_STAT_NEURONS,
    LEARNED_ACTIONS, PURE_INPUT_NEURONS,
)
from .causal_learning import VALENCE_WEIGHTS
from .propagation import rests_at_zero, signal_of

# Only voluntary, previously unwired motor neurons are explored.
_EXPLORE_ACTIONS = tuple(x for x in LEARNED_ACTIONS if x in (
    "act_play", "act_shelter", "act_rest",
))
_BY_BEHAVIOUR = {ACTION_BEHAVIOURS[x]: x for x in _EXPLORE_ACTIONS}

#: The drives whose distress sends a squid looking for something to do about
#: it: the ones VALENCE_WEIGHTS counts as bad when they rise.
_NEEDS = tuple(stat for stat, weight in VALENCE_WEIGHTS.items() if weight < 0)

#: The chance, each tick the squid has nothing urgent to do, that an unwired
#: action neuron fires by itself - at ordinary curiosity. Low: a squid that
#: tried something new every few seconds would never finish anything.
DEFAULT_RATE = 0.03

#: A cue counts as present from here up, on the 0-100 scale. The same line the
#: capability monitor draws for "this sensor is reporting something".
PRESENT = 70.0

#: The benefit contrast that earns a full-strength synapse: twice the smallest
#: difference worth noticing (minimum_benefit). A synapse is only any use if it
#: can fire its action, so a difference that is clearly real has to be able to
#: reach full strength - at the old scale of four times the minimum, a squid
#: could be quite sure sheltering helped and still be left a hair short of
#: ever doing it (measured: a learned weight of 0.757 where 0.76 was needed).
FULL_CONTRAST = 0.05

#: How much more evidence a combination NEURON needs than a synapse does:
#: this many times the trials, and this many times the difference.
NEURON_EVIDENCE = 2.0

#: After this many tries in a given situation an action is tried there half
#: as often.
FAMILIAR_AFTER = 4.0

#: Each new trial counts for this much more than the one before it, so that
#: evidence from long ago gives way to what happens now. 0.97 is a memory of
#: roughly the last thirty trials.
EVIDENCE_RETENTION = 0.97


@dataclass
class _Evidence:
    """What came of an action with one cue present, and with it absent.

    A cue -> action association is only identifiable from BOTH: two good
    outcomes with the cue there say nothing about the cue unless there are
    outcomes without it to compare them to.
    """
    count: float = 0.0
    total_benefit: float = 0.0
    absent_count: float = 0.0
    absent_benefit: float = 0.0

    @property
    def mean(self):
        return self.total_benefit / self.count if self.count else 0.0

    @property
    def absent_mean(self):
        return (self.absent_benefit / self.absent_count
                if self.absent_count else 0.0)

    @property
    def contrast(self):
        return self.mean - self.absent_mean

    def add(self, present: bool, benefit: float) -> None:
        # What is already known about THIS side fades a little, then the
        # trial is added whole. Each side keeps its own clock: a cue that is
        # rarely present must not have what little is known about it worn away
        # by every trial made without it.
        if present:
            self.count = self.count * EVIDENCE_RETENTION + 1.0
            self.total_benefit = self.total_benefit * EVIDENCE_RETENTION + benefit
        else:
            self.absent_count = self.absent_count * EVIDENCE_RETENTION + 1.0
            self.absent_benefit = self.absent_benefit * EVIDENCE_RETENTION + benefit

    def to_list(self) -> list:
        return [round(self.count, 4), round(self.total_benefit, 6),
                round(self.absent_count, 4), round(self.absent_benefit, 6)]

    @classmethod
    def from_list(cls, raw) -> '_Evidence':
        try:
            return cls(*(float(v) for v in list(raw)[:4]))
        except (TypeError, ValueError):
            return cls()


#: What the game's body is doing, by the movement drive it is running, in the
#: names the action neurons go by (brain_constants.ACTION_BEHAVIOURS).
DRIVE_BEHAVIOURS = {'seek_plant': 'approaching_plant', 'approach_rock': 'playing'}


def behaviour_under_way(drive_action: Optional[str], fell_asleep: bool,
                        chose_rest: bool) -> Optional[str]:
    """Which LEARNED action the squid has just started, if any.

    Sheltering and playing are read off the movement drive it is running.
    Resting is harder to tell from collapsing, since both end in sleep, and it
    matters: being dropped by exhaustion is something that happened to the
    squid, not something it did, and must not be filed as a trial of resting.
    It counts only when the squid fell asleep with its rest neuron firing.
    """
    if fell_asleep:
        return 'sleeping' if chose_rest else None
    return DRIVE_BEHAVIOURS.get(drive_action or '')


class ActionDiscovery:
    """Tries out unwired actions and learns, from what follows, when each is
    worth doing. One per brain; the game and the headless trainer share it."""

    def __init__(self, brain, *, rate: float = DEFAULT_RATE, seed: int = 0,
                 trials_to_learn: int = 3, minimum_benefit: float = 0.025,
                 learning_step: float = 0.5, teaching: bool = True,
                 bout_ticks: int = 1):
        if not 0.0 <= rate <= 1.0:
            raise ValueError("rate must be in [0, 1]")
        self.brain = brain
        self.rate = rate
        self.rng = random.Random(seed)
        self.trials_to_learn = max(2, int(trials_to_learn))
        self.minimum_absent_trials = 2
        self.minimum_benefit = float(minimum_benefit)
        self.learning_step = float(learning_step)
        self.teaching = bool(teaching)
        #: How many ticks a spontaneous urge lasts. One is a single spike; the
        #: headless body needs a few to get anywhere, as the game's own drives
        #: last several seconds.
        self.bout_ticks = max(1, int(bout_ticks))
        self._bout: Optional[Tuple[str, int]] = None

        self.pending = {}  # episode_id -> (motor_neuron, copy of pre-action state)
        self.evidence: Dict[Tuple[str, str], _Evidence] = {}
        #: (cue, other cue, motor): what came of the action WITH `cue` present,
        #: split by whether `other cue` was there too. Kept only for cues that
        #: were present, which is all a combination needs.
        self.joint: Dict[Tuple[str, str, str], _Evidence] = {}
        #: Synapses this mechanism created. Only these are allowed to fade back
        #: to nothing when the evidence for them does; an instinct or a
        #: hand-wired synapse is never erased for want of evidence.
        self.taught: set = set()
        #: The last spontaneous urge and what the squid's senses and drives
        #: were when it arose, until the action it led to is under way.
        self.urge: Optional[str] = None
        self.urge_context: Optional[dict] = None
        #: motor -> how many spontaneous tries in a row came to nothing.
        self.fruitless: Dict[str, int] = {}
        self.probes = 0
        self.executed_probes = 0
        self.trials_closed = 0
        self.connections_taught = 0
        self.aborted_trials = 0
        self._closed_seen = 0

    @property
    def _positions(self):
        """The brain's neurons, whichever brain this is (the game's widget
        calls them neuron_positions; the headless brain answers to both)."""
        return getattr(self.brain, 'neuron_positions', None) or {}

    # ------------------------------------------------------------------
    # What counts as a cue
    # ------------------------------------------------------------------
    def _is_cue(self, name: str) -> bool:
        """Something a motor synapse could come from: a drive, a sense, or a
        neuron the squid grew to stand for a situation."""
        return (name in CORE_STAT_NEURONS or name in PURE_INPUT_NEURONS
                or name in self._situation_neurons())

    def _situation_neurons(self) -> Dict[str, FrozenSet[str]]:
        """{grown neuron: the cues it is a combination of}."""
        growth = getattr(self.brain, 'enhanced_neurogenesis', None)
        neurons = getattr(growth, 'functional_neurons', None) or {}
        return {name: frozenset(getattr(fn, 'combines', ()) or ())
                for name, fn in neurons.items()
                if getattr(fn, 'combines', None)}

    # ------------------------------------------------------------------
    # Motor exploration
    # ------------------------------------------------------------------
    def explore_probability(self, state: dict) -> float:
        """How likely a spontaneous urge is this tick.

        Two things raise it. CURIOSITY: an incurious squid tries very little,
        an inquisitive one a good deal more. And DISTRESS: a squid with a need
        nothing it knows is answering - frightened, exhausted, starving - casts
        about for something that helps, as animals do. That is also when a new
        action has anything to prove: relief is only relief to a squid that
        needed it, so a try made in comfort can teach nothing.
        """
        if self.rate >= 1.0:
            return 1.0

        def level(name: str) -> float:
            try:
                return max(0.0, min(100.0, float(state.get(name, 50.0))))
            except (TypeError, ValueError):
                return 50.0

        distress = max(0.0, max(level(need) for need in _NEEDS) - 50.0) / 50.0
        return min(1.0, self.rate * (0.25 + 1.5 * level('curiosity') / 100.0
                                     + 2.0 * distress))

    def excite(self, state: dict) -> Optional[str]:
        """Stochastically stimulate an unlearned motor; no body action chosen."""
        if self.rate <= 0:
            return None
        if state.get("is_sleeping", 0.0) >= 50:
            self._bout = None
            return None

        # Urgent innate actions take priority. Babbling cannot override an
        # obvious threat, food-seeking or involuntary exhaustion.
        for name in ("act_flee", "act_eat", "act_collapse"):
            if state.get(name, 0.0) >= ACTION_THRESHOLDS[name]:
                self._bout = None
                return None

        # An urge already under way carries on for its few ticks.
        if self._bout is not None:
            neuron, remaining = self._bout
            self._bout = (neuron, remaining - 1) if remaining > 1 else None
            if neuron in self._positions:
                state[neuron] = max(float(state.get(neuron, 0.0)), 96.0)
                return neuron
            return None

        if self.rng.random() >= self.explore_probability(state):
            return None

        # A weak connection is not a usable skill. Evaluate the *current*
        # cue-drive contribution via the engine's own signal function. Using
        # a theoretical saturated 100-point input prematurely declared a
        # sleepiness->rest edge "learned" even though real fatigue could not
        # fire the motor before the innate exhaustion reflex took over.
        actionable = {}
        for motor in _EXPLORE_ACTIONS:
            incoming = sum(
                max(0.0, signal_of(src, float(state.get(src, 0.0)))
                    * float(weight))
                for (src, dst), weight in self.brain.weights.items()
                if dst == motor and self._is_cue(src)
            )
            actionable[motor] = incoming >= ACTION_THRESHOLDS[motor] + 1.0
        actions = [a for a in _EXPLORE_ACTIONS
                   if a in self._positions and not actionable[a]]
        if not actions:
            return None

        # What is there to find out? An action is worth trying in a situation
        # it has not been tried in. A squid that has napped thirty times while
        # wide awake knows what that does, and napping again teaches it
        # nothing - worse, it keeps the squid from ever being tired enough to
        # discover what rest is FOR. So interest in an action follows how
        # unfamiliar the present moment is for it, and fades as the moment
        # becomes familiar - never to nothing, because the tank can change.
        interest = [self._unfamiliarity(a, state) for a in actions]
        if self.rate < 1.0 and self.rng.random() >= max(interest):
            return None
        neuron = self.rng.choices(actions, weights=interest, k=1)[0]
        # Endogenous motor spike, not an action selection. The same neural
        # rank_actions then resolves this against all other action neurons.
        state[neuron] = max(float(state.get(neuron, 0.0)), 96.0)
        self.probes += 1
        if self.bout_ticks > 1:
            self._bout = (neuron, self.bout_ticks - 1)
        return neuron

    def _unfamiliarity(self, motor: str, state: dict) -> float:
        """How new the present situation is, as far as this action goes. 0-1.

        For each cue, how often has the action been tried with that cue the
        way it is right now - present, or absent? The least-tried one sets the
        answer: one thing about this moment being new is enough to make the
        action worth trying again.
        """
        newest = 0.0
        for cue in self._positions:
            if cue == motor or not self._is_cue(cue):
                continue
            try:
                on = float(state.get(cue, 0.0)) >= PRESENT
            except (TypeError, ValueError):
                continue
            record = self.evidence.get((cue, motor))
            tried = 0.0 if record is None else (record.count if on else record.absent_count)
            newest = max(newest, 1.0 / (1.0 + tried / FAMILIAR_AFTER))
            if newest >= 1.0:
                break
        return newest

    def committed(self, episode_id: Optional[str], neuron: Optional[str],
                  behaviour: Optional[str], pre_action_state: dict) -> None:
        """An action was really taken: make its outcome count as evidence.

        `neuron` is the motor a spontaneous urge fired, if one did. A learned
        action the squid chose through its own synapses is evidence too - that
        is how a skill it has goes on being checked against what it gets.
        """
        motor = _BY_BEHAVIOUR.get(behaviour)
        if not episode_id or motor is None:
            return
        if neuron is not None:
            if neuron != motor:
                return
            self.executed_probes += 1
        if not self.teaching:
            return
        self.pending[episode_id] = (
            motor, {k: float(v) for k, v in pre_action_state.items()
                    if isinstance(v, (int, float))},
        )

    # ------------------------------------------------------------------
    # The game loop's two calls. The headless tank chooses an action and moves
    # the body in one step, so it calls excite/committed directly; the game
    # spreads a decision over several ticks and several systems, and these two
    # are what it calls instead.
    # ------------------------------------------------------------------
    def tick(self, state: dict, asleep: bool = False) -> Optional[str]:
        """Once per brain tick, straight after propagation: settle what earlier
        actions led to, then perhaps fire an unwired action neuron."""
        self.process_closed()
        if asleep:
            self._bout = None
            return None
        urge = self.excite(state)
        if urge is not None:
            self.urge = urge
            self.urge_context = {k: float(v) for k, v in state.items()
                                 if isinstance(v, (int, float))
                                 and not isinstance(v, bool)}
        return urge

    def acted(self, behaviour: str, state: dict) -> Optional[str]:
        """The squid is now really doing `behaviour` (a learned action): open
        its outcome window and file it as a trial. Safe to call every tick the
        behaviour continues - one bout is one trial."""
        motor = _BY_BEHAVIOUR.get(behaviour)
        ledger = getattr(self.brain, 'causal_learning', None)
        if motor is None or ledger is None:
            return None
        episode_id = ledger.on_action(behaviour, state)
        if episode_id is None:
            return None
        urge = getattr(self, 'urge', None)
        if urge == motor:
            context = getattr(self, 'urge_context', None) or state
            self.committed(episode_id, motor, behaviour, context)
        else:
            self.committed(episode_id, None, behaviour, state)
        self.urge, self.urge_context = None, None
        return episode_id

    # ------------------------------------------------------------------
    # Outcomes
    # ------------------------------------------------------------------
    def _benefit(self, episode, context: dict) -> float:
        """How much better off the squid was for having done this, given what
        it needed at the time. Positive is good."""
        ledger = self.brain.causal_learning
        benefit = 0.0
        for stat, delta in episode.consequence.items():
            importance = VALENCE_WEIGHTS.get(stat)
            if not importance:
                continue
            # Measured against how the drive moves anyway, without this action.
            background = ledger.baseline_drift(stat, episode.action)
            contribution = importance * (delta - background) / 100.0
            if importance < 0.0:
                # A drive that is already low has no further beneficial
                # "need reduction" to discover. Rewarding sleepiness
                # reductions when the animal is fully rested trained an
                # inappropriate sleep-anytime motor association.
                pressure = max(0.0, min(
                    1.0, (context.get(stat, 50.0) - 50.0) / 50.0))
                contribution *= pressure
            benefit += contribution
        return benefit

    def process_closed(self) -> int:
        """Turn genuine settled experiences into *recorded* synaptic updates."""
        if not self.teaching:
            return 0
        ledger = self.brain.causal_learning
        changes = 0
        # Process only newly closed outcomes. Rescanning the entire rolling
        # history (up to 400 episodes) every simulation tick made a small
        # experimental feature grow costly with age.
        freshly_closed = max(0, ledger.closed_episodes - self._closed_seen)
        self._closed_seen = ledger.closed_episodes
        new_episodes = list(ledger.history)[-freshly_closed:] if freshly_closed else ()
        for episode in new_episodes:
            trial = self.pending.pop(episode.episode_id, None)
            if trial is None:
                continue
            motor, context = trial
            self.trials_closed += 1
            benefit = self._benefit(episode, context)
            if benefit > self.minimum_benefit:
                self.fruitless[motor] = 0
            else:
                self.fruitless[motor] = self.fruitless.get(motor, 0) + 1
            changes += self._file(motor, context, benefit, episode)

        # Scripted feed/clean/set_state events deliberately invalidate
        # currently open causal windows. Their probes must never remain
        # eligible for future unrelated episodes or accumulate indefinitely.
        still_open = {e.episode_id for e in ledger._open}
        for episode_id in tuple(self.pending):
            if episode_id not in still_open:
                self.pending.pop(episode_id)
                self.aborted_trials += 1
        return changes

    def _file(self, motor: str, context: dict, benefit: float, episode) -> int:
        """File one trial against every cue, then move the synapses it bears on."""
        positions = self._positions
        cues = {name: activation >= PRESENT
                for name, activation in context.items()
                if name in positions and name != motor and self._is_cue(name)}

        # A situation neuron that is on speaks for the cues it combines: the
        # trial is evidence about the combination, not about each part alone.
        # Without this a plant in sight would go on being credited with the
        # relief that only a frightened squid gets from it.
        spoken_for = set()
        for neuron, parts in self._situation_neurons().items():
            if cues.get(neuron):
                spoken_for |= parts

        # BLOCKING. When one cue present already accounts for how this action
        # turns out, the other cues that happen to be there learn nothing
        # from the trial - the finding Kamin made in animals, and the reason a
        # squid that has learned "shelter when frightened by a plant" does not
        # go on to conclude that food being in sight had something to do with
        # it. The best-evidenced cue present takes the trial; any cue it
        # clearly outdoes is left as it was.
        standing = {}
        for cue, on in cues.items():
            if on and cue not in spoken_for:
                record = self.evidence.get((cue, motor))
                if record is not None and self._qualified(record):
                    standing[cue] = record.contrast
        best = max(standing.values(), default=0.0)
        blocked = set()
        if best > self.minimum_benefit:
            blocked = {cue for cue, on in cues.items()
                       if on and cue not in spoken_for
                       and best - standing.get(cue, 0.0) > self.minimum_benefit}

        changes = 0
        present = [c for c, on in cues.items() if on and c not in spoken_for]
        for cue, on in cues.items():
            if cue in spoken_for or cue in blocked:
                continue
            key = (cue, motor)
            record = self.evidence.setdefault(key, _Evidence())
            record.add(on, benefit)
            if on:
                changes += self._teach(key, record, episode)
        # A blocked cue's own synapse still follows what is known about it,
        # so one that was credited before the better cue was found fades.
        for cue in blocked:
            record = self.evidence.get((cue, motor))
            if record is not None and (cue, motor) in self.taught:
                changes += self._teach((cue, motor), record, episode)
        for cue in present:
            for other, on in cues.items():
                if other != cue and other not in spoken_for:
                    self.joint.setdefault((cue, other, motor), _Evidence()).add(on, benefit)
        return changes

    def _qualified(self, record: _Evidence, factor: float = 1.0) -> bool:
        """Has the action been tried enough both with and without the cue?"""
        return (record.count >= self.trials_to_learn * factor - 1e-9
                and record.absent_count >= self.minimum_absent_trials * factor - 1e-9)

    def _teach(self, key: Tuple[str, str], record: _Evidence, episode) -> int:
        """Move one cue -> action synapse toward what the evidence supports."""
        # A learnable contingency needs observations from BOTH conditions, not
        # merely two co-activations of a sensor.
        if not self._qualified(record):
            return 0
        weights = self.brain.weights
        exists = key in weights
        owned = key in self.taught
        significant = (abs(record.contrast) > self.minimum_benefit
                       and (record.contrast < 0 or record.mean > self.minimum_benefit))
        if not significant and not owned:
            # No case for a synapse, and no synapse of ours to revise.
            return 0

        target = (max(-1.0, min(1.0, record.contrast / FULL_CONTRAST))
                  if significant else 0.0)
        old = float(weights.get(key, 0.0))
        delta = self.learning_step * (target - old)
        if abs(delta) < 1e-4:
            return 0
        if not exists and target <= 0.0:
            return 0     # nothing to weaken, and nothing learned to avoid yet

        if target > old:
            note = "worked better with this cue present than without it"
        elif target < 0:
            note = "turned out worse with this cue present than without it"
        else:
            note = "stopped making a difference whether this cue was present"
        if self.brain.apply_weight_change(
            key, delta=delta, mechanism="causal_motor_discovery",
            detail={
                "note": note,
                "mean_benefit_cue_present": round(record.mean, 5),
                "mean_benefit_cue_absent": round(record.absent_mean, 5),
                "benefit_contrast": round(record.contrast, 5),
                "present_trials": round(record.count, 2),
                "absent_trials": round(record.absent_count, 2),
                "action": episode.action,
            },
            episode_id=episode.episode_id,
            create=True, directed=True,
        ):
            self.taught.add(key)
            self.connections_taught += 1
            return 1
        return 0

    # ------------------------------------------------------------------
    # Combinations the brain has no neuron for
    # ------------------------------------------------------------------
    def wanted_combinations(self) -> List[dict]:
        """Pairs of cues an action depends on TOGETHER, with no neuron for the pair.

        The test is an interaction, in both directions: with A present the
        action works better when B is too, AND with B present it works better
        when A is too. If only one of those held, the one cue would be enough
        by itself and an ordinary synapse could say so.

        Read by the capability monitor; growing the neuron is neurogenesis's
        decision, on the same terms as any other growth.
        """
        existing = set(self._situation_neurons().values())
        positions = self._positions
        seen, wanted = set(), []
        for (cue, other, motor), record in self.joint.items():
            pair = frozenset((cue, other))
            if pair in seen or pair in existing:
                continue
            if cue not in positions or other not in positions:
                continue
            # A combination of combinations is not grown: one level is what
            # the evidence here can support.
            situations = self._situation_neurons()
            if cue in situations or other in situations:
                continue
            mirror = self.joint.get((other, cue, motor))
            if mirror is None:
                continue
            if not (self._qualified(record, NEURON_EVIDENCE)
                    and self._qualified(mirror, NEURON_EVIDENCE)):
                continue
            # A neuron is a bigger commitment than a synapse and has to clear
            # a higher bar: more trials on every side, and twice the
            # difference. On the synapse's terms a pairing with something that
            # is nearly always there (food, in a well-fed tank) qualified on
            # two unrepresentative trials.
            bar = self.minimum_benefit * NEURON_EVIDENCE
            if min(record.contrast, mirror.contrast) <= bar:
                continue
            if record.mean <= bar:
                continue
            seen.add(pair)
            wanted.append({
                'cues': sorted(pair), 'motor': motor,
                'behaviour': ACTION_BEHAVIOURS.get(motor, motor),
                'benefit_together': round(record.mean, 4),
                'benefit_with_only_' + cue: round(record.absent_mean, 4),
                'benefit_with_only_' + other: round(mirror.absent_mean, 4),
                'trials_together': round(record.count, 1),
                'strength': round(min(record.contrast, mirror.contrast), 4),
            })
        wanted.sort(key=lambda w: -w['strength'])
        return wanted

    def adopt_combination(self, neuron: str, cues: Iterable[str], motor: str,
                          deficit=None) -> None:
        """A neuron has been grown for a combination: hand it the evidence.

        What is already known about the pair is what is known about the new
        neuron - it is on exactly when they both are - so it does not have to
        be learned a second time from nothing.
        """
        cues = sorted(cues)
        if len(cues) != 2:
            return
        record = self.joint.get((cues[0], cues[1], motor))
        if record is None:
            return
        # Present: both together. Absent: the better-evidenced "one without
        # the other" - what the action is worth when the combination is not
        # there.
        adopted = _Evidence(record.count, record.total_benefit,
                            record.absent_count, record.absent_benefit)
        self.evidence[(neuron, motor)] = adopted

        # ...and what is known about each cue BY ITSELF is now only what
        # happened when it was there without the other. Those trials were
        # being counted for the cue alone because there was nowhere else to
        # put them; there is now. Its own synapse then follows the corrected
        # record, so a cue that only ever mattered as half of the pair stops
        # driving the action alone.
        for cue, other in ((cues[0], cues[1]), (cues[1], cues[0])):
            pair = self.joint.get((cue, other, motor))
            single = self.evidence.get((cue, motor))
            if pair is None or single is None:
                continue
            single.count = pair.absent_count
            single.total_benefit = pair.absent_benefit
            if self.teaching and (cue, motor) in self.taught:
                target = (max(-1.0, min(1.0, single.contrast / FULL_CONTRAST))
                          if (self._qualified(single)
                              and abs(single.contrast) > self.minimum_benefit) else 0.0)
                old = float(self.brain.weights.get((cue, motor), 0.0))
                self.brain.apply_weight_change(
                    (cue, motor), value=old + self.learning_step * (target - old),
                    mechanism="causal_motor_discovery",
                    detail={"note": f"what it had been credited with turned out "
                                    f"to belong to {neuron.replace('_', ' ')}",
                            "benefit_contrast": round(single.contrast, 5),
                            "present_trials": round(single.count, 2),
                            "absent_trials": round(single.absent_count, 2)},
                    create=False, directed=True)
        if not self.teaching or adopted.contrast <= self.minimum_benefit:
            return
        key = (neuron, motor)
        target = max(-1.0, min(1.0, adopted.contrast / FULL_CONTRAST))
        behaviour = ACTION_BEHAVIOURS.get(motor, motor)
        if self.brain.apply_weight_change(
                key, delta=self.learning_step * target,
                mechanism="causal_motor_discovery",
                detail={
                    "note": "worked better with both of these present than "
                            "with either alone - the evidence this neuron "
                            "was grown on",
                    "mean_benefit_cue_present": round(adopted.mean, 5),
                    "mean_benefit_cue_absent": round(adopted.absent_mean, 5),
                    "benefit_contrast": round(adopted.contrast, 5),
                    "present_trials": round(adopted.count, 2),
                    "absent_trials": round(adopted.absent_count, 2),
                    "action": behaviour,
                }, create=True, directed=True):
            self.taught.add(key)
            self.connections_taught += 1

    # ------------------------------------------------------------------
    def statistics(self):
        return {
            "motor_probes": self.probes,
            "motor_trials_executed": self.executed_probes,
            "motor_trials_closed": self.trials_closed,
            "motor_connections_taught": self.connections_taught,
            "motor_evidence_pairs": len(self.evidence),
            "motor_aborted_trials": self.aborted_trials,
            "motor_pending_trials": len(self.pending),
        }

    def describe(self, cue: str, motor: str) -> str:
        """What the squid has found out about one cue and one action, in words."""
        record = self.evidence.get((cue, motor))
        behaviour = ACTION_BEHAVIOURS.get(motor, motor).replace('_', ' ')
        cue_words = cue.replace('_', ' ')
        if record is None or not (record.count or record.absent_count):
            return f"It has not tried {behaviour} enough to say anything about {cue_words}."
        if not self._qualified(record):
            return (f"It has tried {behaviour} {record.count:.0f} time(s) with "
                    f"{cue_words} and {record.absent_count:.0f} without - not "
                    f"enough of both to compare.")
        if record.contrast > self.minimum_benefit:
            verdict = "works better with"
        elif record.contrast < -self.minimum_benefit:
            verdict = "works worse with"
        else:
            verdict = "works about the same with or without"
        return (f"{behaviour.capitalize()} {verdict} {cue_words} "
                f"({record.mean:+.3f} with, {record.absent_mean:+.3f} without, "
                f"over about {record.count + record.absent_count:.0f} tries).")

    # ------------------------------------------------------------------
    # Persistence - what the squid has found out goes with it
    # ------------------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            'evidence': [[cue, motor, record.to_list()]
                         for (cue, motor), record in self.evidence.items()],
            'joint': [[cue, other, motor, record.to_list()]
                      for (cue, other, motor), record in self.joint.items()],
            'taught': [list(edge) for edge in sorted(self.taught)],
            'fruitless': dict(self.fruitless),
            'probes': self.probes,
            'executed_probes': self.executed_probes,
            'trials_closed': self.trials_closed,
            'connections_taught': self.connections_taught,
            'aborted_trials': self.aborted_trials,
        }

    def from_dict(self, data) -> None:
        if not isinstance(data, dict):
            return
        self.evidence = {}
        for row in data.get('evidence') or []:
            try:
                cue, motor, raw = row
                self.evidence[(str(cue), str(motor))] = _Evidence.from_list(raw)
            except (TypeError, ValueError):
                continue
        self.joint = {}
        for row in data.get('joint') or []:
            try:
                cue, other, motor, raw = row
                self.joint[(str(cue), str(other), str(motor))] = _Evidence.from_list(raw)
            except (TypeError, ValueError):
                continue
        self.taught = {tuple(edge) for edge in data.get('taught') or []
                       if isinstance(edge, (list, tuple)) and len(edge) == 2}
        self.fruitless = {str(k): int(v) for k, v in (data.get('fruitless') or {}).items()
                          if isinstance(v, (int, float))}
        for name in ('probes', 'executed_probes', 'trials_closed',
                     'connections_taught', 'aborted_trials'):
            try:
                setattr(self, name, int(data.get(name, 0)))
            except (TypeError, ValueError):
                pass
        # Outcome windows that were open when the squid was saved are gone.
        self.pending = {}
        self._bout = None
        self._closed_seen = getattr(self.brain.causal_learning, 'closed_episodes', 0)

    def reset(self) -> None:
        self.evidence, self.joint, self.taught, self.pending = {}, {}, set(), {}
        self.fruitless = {}
        self._bout = None
        self.probes = self.executed_probes = self.trials_closed = 0
        self.connections_taught = self.aborted_trials = 0
        self._closed_seen = getattr(self.brain.causal_learning, 'closed_episodes', 0)
