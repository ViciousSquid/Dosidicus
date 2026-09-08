"""
causal_learning.py - action → consequence → outcome → learning.

Correlation is not causation, and until now the squid only had correlation:
plasticity noticed that two neurons moved together, and that was the whole of
its understanding. A creature that only correlates cannot answer "what did *I*
do that made that happen?", which is the difference between noticing that food
and satisfaction co-occur and knowing that *eating* is what produces the
satisfaction.

This module gives the squid the missing half.

    1. ACTION EPISODES. Every time the squid starts doing something
       (eating, exploring, throwing, sleeping, fleeing...) an episode opens,
       recording the sensory cue that was present at the moment it acted.

    2. OUTCOME WINDOW. The episode stays open for a few seconds. When it
       closes, the change in every homeostatic drive over that window is the
       measured consequence.

    3. CONTINGENCY, NOT CO-OCCURRENCE. The consequence is compared against the
       baseline drift of the same drive when that action was NOT running.
       "Hunger fell 20 while eating; hunger drifts up 0.4 otherwise" is a
       causal claim. "Hunger and eating co-occur" is not.

    4. TEMPORAL CREDIT ASSIGNMENT. The outcome's valence is broadcast to the
       STDP eligibility traces laid down during the episode. Synapses that
       were causally active in the seconds leading up to a good outcome are
       strengthened; those active before a bad one are weakened. This is the
       third factor in a three-factor learning rule, and it is what lets a
       consequence that arrives seconds after the action still reach the
       synapses that produced it.

Everything it concludes is written to the provenance ledger with the episode
attached, so "what experience caused it to learn this?" has an answer that
names the action, the cue and the consequence.
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Iterable, List, Optional, Set, Tuple

from .brain_constants import CORE_STAT_NEURONS, PURE_INPUT_NEURONS
from .neural_provenance import Episode, KnowledgeItem, humanise

# How each drive contributes to whether an outcome was good or bad for the
# squid. Signs follow the game's own semantics: hunger and anxiety going UP is
# bad, happiness and satisfaction going up is good.
VALENCE_WEIGHTS: Dict[str, float] = {
    'happiness': 1.0,
    'satisfaction': 1.0,
    'anxiety': -1.0,
    'hunger': -0.7,
    'cleanliness': 0.4,
    'sleepiness': -0.3,
    'curiosity': 0.2,
}

# Actions that are not really actions - the squid is idling or the status
# string carries no behavioural commitment.
_NON_ACTIONS = {'', 'none', 'idle', 'unknown'}

# Several behaviours can have overlapping outcome windows. The cap only
# exists so a runaway cannot grow without bound; overflow drops the oldest
# unclosed episode, which is the one whose consequence is least readable.
_MAX_OPEN_EPISODES = 16
_MAX_HISTORY = 400

# A sensor reads 0 when it has nothing to report and 100 when it does. The
# threshold matches CapabilityMonitor.situation_signature, so "the squid could
# see food" means the same thing to the causal ledger and to the diagnosis.
SENSOR_PRESENT = 70.0


@dataclass
class Contingency:
    """The squid's estimate of what one of its actions does to one drive."""
    action: str
    stat: str
    n: int = 0
    sum_delta: float = 0.0
    sum_sq: float = 0.0
    last_seen: float = 0.0

    @property
    def mean_delta(self) -> float:
        return self.sum_delta / self.n if self.n else 0.0

    @property
    def sd(self) -> float:
        if self.n < 2:
            return 0.0
        mean = self.mean_delta
        var = max(0.0, self.sum_sq / self.n - mean * mean)
        return var ** 0.5

    def observe(self, delta: float, when: float) -> None:
        self.n += 1
        self.sum_delta += delta
        self.sum_sq += delta * delta
        self.last_seen = when

    def effect(self, baseline: float) -> float:
        """How much of the change this action is actually responsible for."""
        return self.mean_delta - baseline

    def confidence(self, baseline: float) -> float:
        """How sure the squid can reasonably be about this claim.

        Grows with repetition and with the size of the effect relative to how
        variable it is. A single observation is never confident, no matter how
        dramatic - which is the correct epistemics for a creature that has to
        live with its conclusions.
        """
        if self.n < 2:
            return 0.0
        effect = abs(self.effect(baseline))
        if effect < 0.5:
            return 0.0
        spread = self.sd + 1.0
        signal = min(1.0, effect / spread)
        repetition = 1.0 - (1.0 / (self.n ** 0.5))
        return round(max(0.0, min(1.0, signal * repetition)), 3)

    def to_dict(self) -> dict:
        return {'action': self.action, 'stat': self.stat, 'n': self.n,
                'sum_delta': self.sum_delta, 'sum_sq': self.sum_sq,
                'last_seen': self.last_seen}

    @classmethod
    def from_dict(cls, d: dict) -> 'Contingency':
        return cls(action=str(d.get('action', '')), stat=str(d.get('stat', '')),
                   n=int(d.get('n', 0)), sum_delta=float(d.get('sum_delta', 0.0)),
                   sum_sq=float(d.get('sum_sq', 0.0)),
                   last_seen=float(d.get('last_seen', 0.0)))


@dataclass
class _OpenEpisode:
    episode_id: str
    action: str
    started: float
    closes_at: float
    cue: Dict[str, float]
    baseline_state: Dict[str, float]
    ticks: int = 0


@dataclass
class CausalConfig:
    """Tuning for causal learning."""
    outcome_window: float = 6.0      # seconds an action's consequence is watched
    min_valence_for_reward: float = 0.04
    reward_gain: float = 1.0         # scales the three-factor weight change
    max_reward_delta: float = 0.08   # per synapse, per outcome
    cue_size: int = 4                # how many context values define "the cue"
    min_confidence_to_teach: float = 0.35


class ActionOutcomeLedger:
    """Discovers which of the squid's own actions cause what, and learns from it."""

    def __init__(self, brain=None, config: Optional[CausalConfig] = None):
        self.brain = brain
        self.config = config or CausalConfig()

        # How this ledger reads the passage of time. The game uses the wall
        # clock; the headless trainer substitutes simulated seconds. An outcome
        # window measured in wall-clock seconds would be nine thousand ticks
        # long in a trainer running 1 500 ticks a second, so nothing would ever
        # settle and the trainer would learn no contingencies at all.
        self.clock = time.time

        self._open: Deque[_OpenEpisode] = deque(maxlen=_MAX_OPEN_EPISODES)
        self._current_action: str = ""
        self.closed_episodes = 0
        self.rewarded_episodes = 0

        # action -> stat -> Contingency
        self.contingencies: Dict[str, Dict[str, Contingency]] = defaultdict(dict)

        # Baseline drift of each drive over one outcome window, measured while
        # NOT performing the action in question. Without this the squid would
        # credit "exploring" with the hunger it accumulates simply by existing.
        # Raw measured change per outcome window: every window once in
        # `_all_windows`, and once per action that was running in `_raw`. The
        # difference between the two is what an action is actually worth -
        # "hunger fell 20 while eating; over windows in which the squid was NOT
        # eating it rose 0.4" is a causal claim, and it is the only comparison
        # that makes one.
        self._all_windows: Dict[str, Contingency] = {}
        self._raw: Dict[Tuple[str, str], Contingency] = {}
        # A window measured while the squid was doing nothing at all. These
        # count toward every action's background: without them, a squid whose
        # only behaviour is grooming has no window that does not contain
        # grooming, and so no way to discover that hunger climbs anyway.
        self._idle_probe: Optional[_OpenEpisode] = None

        # How often each action has been observed, and - for every ordered
        # pair - how often the two ran together and how often the first ran
        # WITHOUT the second. Two actions that have never once occurred apart
        # are perfectly confounded: no amount of further repetition can tell
        # them apart, and the ledger has to be able to say so rather than
        # quietly splitting the credit forever.
        self.action_episodes: Dict[str, int] = {}
        self._together: Dict[Tuple[str, str], int] = {}
        self._apart: Dict[Tuple[str, str], int] = {}

        # The windows of episodes that have already settled. Two behaviours
        # that overlap need not expire together - a bout of A started a second
        # before a bout of B closes a second before it too - and reading only
        # the episodes still open at settlement time made the whole question of
        # what overlapped what depend on which one happened to expire first.
        self._settled_windows: Deque[Tuple[str, float, float]] = deque(maxlen=64)

        self.history: Deque[Episode] = deque(maxlen=_MAX_HISTORY)
        self.last_outcome: Dict[str, Any] = {}

    @property
    def current_action(self) -> str:
        """What the squid has most recently committed to doing.

        Read by the brain to drive any action-representation neuron it has
        grown: an action the network can represent is one it can learn about
        synaptically rather than only in a table.
        """
        return self._current_action

    # ------------------------------------------------------------------
    # Plumbing
    # ------------------------------------------------------------------
    @property
    def _ledger(self):
        return getattr(self.brain, 'ledger', None)

    @property
    def _stdp(self):
        engine = getattr(self.brain, 'plasticity', None)
        return getattr(engine, 'stdp', None) if engine is not None else None

    @staticmethod
    def _numeric(state: Dict[str, Any]) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for key, value in (state or {}).items():
            if isinstance(value, bool):
                out[key] = 100.0 if value else 0.0
            elif isinstance(value, (int, float)):
                out[key] = float(value)
        return out

    def _capture_cue(self, state: Dict[str, float]) -> Dict[str, float]:
        """The salient context at the moment of acting.

        Sensors first - what the squid could actually perceive is the honest
        antecedent of a causal claim - then whichever drives were furthest from
        neutral.
        """
        sensors = {k: v for k, v in state.items() if k in PURE_INPUT_NEURONS}
        drives = {k: v for k, v in state.items() if k in CORE_STAT_NEURONS}
        cue: Dict[str, float] = {}
        # A sensor is salient when it is REPORTING something, not when it is
        # far from the middle of its range. Scoring it by deviation from 50
        # made "no food anywhere" (can_see_food = 0) the most salient thing in
        # the squid's world, and the brain went on to grow structure to act on
        # the absence of food.
        for name, value in sorted(sensors.items(), key=lambda kv: -kv[1]):
            if value >= SENSOR_PRESENT:
                cue[name] = value
        for name, value in sorted(drives.items(), key=lambda kv: -abs(kv[1] - 50.0)):
            if len(cue) >= self.config.cue_size:
                break
            cue[name] = value
        return dict(list(cue.items())[:self.config.cue_size])

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------
    def on_action(self, action: str, state: Optional[Dict[str, Any]] = None,
                  now: Optional[float] = None) -> Optional[str]:
        """The squid has committed to doing something. Open an episode.

        Repeating the same action does not re-open an episode: an episode is a
        transition into a behaviour, which is the thing whose consequence can
        be measured.
        """
        action = (action or "").strip().lower()
        if action in _NON_ACTIONS:
            self._current_action = ""
            return None
        # Repeating the same behaviour re-opens an episode only once the
        # previous bout's outcome window has closed: a continuous behaviour is
        # one episode, but going back to it later is a fresh observation, and a
        # contingency needs repeated observations to become believable.
        if action == self._current_action and any(
                open_ep.action == action for open_ep in self._open):
            return None

        now = self.clock() if now is None else now
        self._current_action = action
        snapshot = self._numeric(state if state is not None
                                 else getattr(self.brain, 'state', {}) or {})

        episode = _OpenEpisode(
            episode_id=uuid.uuid4().hex[:12],
            action=action,
            started=now,
            closes_at=now + self.config.outcome_window,
            cue=self._capture_cue(snapshot),
            baseline_state={k: v for k, v in snapshot.items()
                            if k in CORE_STAT_NEURONS},
        )
        self._open.append(episode)
        return episode.episode_id

    def on_tick(self, state: Optional[Dict[str, Any]] = None,
                now: Optional[float] = None) -> List[Episode]:
        """Advance every open episode; close the ones whose window has expired."""
        now = self.clock() if now is None else now
        snapshot = self._numeric(state if state is not None
                                 else getattr(self.brain, 'state', {}) or {})
        if not snapshot:
            return []

        self._advance_idle_probe(snapshot, now)

        expiring: List[_OpenEpisode] = []
        still_open: List[_OpenEpisode] = []
        for episode in self._open:
            episode.ticks += 1
            (expiring if now >= episode.closes_at else still_open).append(episode)

        self._open = deque(still_open, maxlen=_MAX_OPEN_EPISODES)
        if not expiring:
            return []
        # Settled together, so which episode happens to be first in the deque
        # cannot decide which action gets the credit.
        return self._settle(expiring, snapshot, now)

    def _advance_idle_probe(self, snapshot: Dict[str, float], now: float) -> None:
        """Measure one outcome window's worth of doing nothing.

        Runs only while no episode is open, and files its result alongside the
        action windows, attributed to no action. That is what makes it a
        background: it counts in the total every action is compared against and
        in none of the per-action totals.
        """
        if self._open:
            self._idle_probe = None
            return
        probe = self._idle_probe
        if probe is None or now < probe.closes_at:
            if probe is None:
                self._idle_probe = _OpenEpisode(
                    episode_id='idle', action='', started=now,
                    closes_at=now + self.config.outcome_window, cue={},
                    baseline_state={k: v for k, v in snapshot.items()
                                    if k in CORE_STAT_NEURONS})
            return
        self._record_window(probe, set(), snapshot, now)
        self._idle_probe = _OpenEpisode(
            episode_id='idle', action='', started=now,
            closes_at=now + self.config.outcome_window, cue={},
            baseline_state={k: v for k, v in snapshot.items()
                            if k in CORE_STAT_NEURONS})

    def baseline_drift(self, stat: str, action: Optional[str] = None) -> float:
        """How this drive moves over an outcome window ANYWAY.

        With an action named, over the windows in which that action was not
        running - which is the comparison a contingency actually needs. A
        dedicated "the squid is doing nothing" probe cannot supply it: the
        squid is always doing something, so such a probe either never fires or,
        if it is allowed to run during actions, measures a background that
        already contains the effect being tested and cancels it out. Both of
        those were tried; this is the arithmetic that answers the question.
        """
        total = self._all_windows.get(stat)
        if total is None or total.n == 0:
            return 0.0
        if action is None:
            return total.mean_delta
        with_action = self._raw.get((action, stat))
        if with_action is None or with_action.n == 0:
            return total.mean_delta
        without_n = total.n - with_action.n
        if without_n <= 0:
            # This action has been running for every window ever measured, so
            # there is no "otherwise" to compare it against. Zero is the honest
            # answer: no evidence about the background. Falling back to the
            # overall mean was worse than useless - that mean is made entirely
            # of windows containing the action, so subtracting it cancels the
            # effect out and can flip its sign.
            return 0.0
        return (total.sum_delta - with_action.sum_delta) / without_n

    def _record_window(self, episode: _OpenEpisode, scope: Set[str],
                       snapshot: Dict[str, float], now: float) -> None:
        """File one outcome window's raw measurements."""
        for stat, before in episode.baseline_state.items():
            after = snapshot.get(stat)
            if after is None:
                continue
            delta = after - before
            entry = self._all_windows.get(stat)
            if entry is None:
                entry = Contingency(action='window', stat=stat)
                self._all_windows[stat] = entry
            entry.observe(delta, now)
            for action in scope:
                key = (action, stat)
                raw = self._raw.get(key)
                if raw is None:
                    raw = Contingency(action=action, stat=stat)
                    self._raw[key] = raw
                raw.observe(delta, now)

    # ------------------------------------------------------------------
    # Closing an episode: this is where learning happens
    # ------------------------------------------------------------------
    def _settle(self, expiring: List[_OpenEpisode], snapshot: Dict[str, float],
                now: float) -> List[Episode]:
        """Close every episode whose window has run out, competing for credit.

        Actions overlap constantly - a squid is exploring while it notices food
        while it drifts - so the question is never "what happened after this
        action?" but "how much of what happened was down to THIS action rather
        than whatever else was going on?".

        Each drive is settled by shared prediction error, the rule animal
        learning calls cue competition:

            error   = observed change  -  what every action in scope already
                                          predicts, together
            target  = this action's own current estimate + error

        Two actions that always co-occur end up splitting the effect, which is
        the honest answer: nothing can separate perfectly confounded causes,
        and inventing a split would be worse than admitting the tie. The moment
        one of them happens without the other, its estimate is corrected toward
        nothing and the real cause absorbs the effect. That is the difference
        between learning a contingency and noticing a coincidence.

        Every action in scope for an outcome is updated against that outcome,
        with a single shared prediction error, and every estimate is read
        BEFORE any of them moves. Both halves are needed.

        Updating only the episode that happened to expire is what made an
        earlier attempt at this hand the whole effect to whichever action's
        window closed first: two behaviours that always overlap almost never
        expire on the same tick, so the first one to settle took the error
        while the second, settling a second later, found its partner's estimate
        already explaining everything and learned nothing. That is not cue
        competition, it is a race. Updating every action that was running gives
        the same result whichever order the windows close in, and it is also
        what Rescorla and Wagner actually say: all cues present on a trial move
        together, on the error they jointly failed to predict.
        """
        scopes: Dict[str, Set[str]] = {}
        in_scope: Set[str] = set()
        for episode in expiring:
            scope = {episode.action} | self._overlapping(episode, expiring)
            scopes[episode.episode_id] = scope
            in_scope.update(scope)

        self._record_co_occurrence(expiring)

        prior: Dict[Tuple[str, str], float] = {}
        for action in in_scope:
            for stat, entry in self.contingencies.get(action, {}).items():
                prior[(action, stat)] = entry.mean_delta if entry.n else 0.0

        closed: List[Episode] = []
        pending: List[Tuple[str, str, float, float]] = []

        for open_ep in expiring:
            consequence: Dict[str, float] = {}
            for stat, before in open_ep.baseline_state.items():
                after = snapshot.get(stat)
                if after is None:
                    continue
                delta = after - before
                if abs(delta) >= 0.25:
                    consequence[stat] = delta

            # Valence is the SURPRISE, not the raw change.
            #
            # An outcome the squid already expects teaches it nothing - that is
            # the whole content of prediction-error learning, and it is what
            # keeps the reward channel honest. Scoring the raw change instead
            # made almost every episode "rewarding", because the drives always
            # drift a little, so reward fired constantly and swamped the
            # correlational rule that carries what the squid actually
            # experienced. As the squid learns what its actions do, routine
            # outcomes stop moving weights and only genuine surprises do.
            scope = scopes.get(open_ep.episode_id, {open_ep.action})
            self._record_window(open_ep, scope, snapshot, now)
            valence = 0.0
            for stat, delta in consequence.items():
                weight = VALENCE_WEIGHTS.get(stat, 0.0)
                if not weight:
                    continue
                predicted = sum(prior.get((a, stat), 0.0) for a in scope)
                # Normalise: a full 100-point swing in one drive is one unit.
                valence += weight * ((delta - predicted) / 100.0)
            valence = max(-1.0, min(1.0, valence))

            episode = Episode(
                episode_id=open_ep.episode_id, action=open_ep.action,
                started=open_ep.started, ended=now, cue=dict(open_ep.cue),
                consequence=consequence, valence=round(valence, 4))

            # Settle every drive this action already has an expectation about,
            # not just the ones that visibly moved. "I did that and the thing I
            # expected did NOT happen" is the observation that corrects a
            # mistaken belief; discarding it because the change was too small
            # to display meant a coincidence, once learned, could never be
            # unlearned. The episode's `consequence` still carries only what
            # actually moved, because that is what gets shown to the player.
            settled = set(consequence)
            settled.update(stat for (action, stat) in prior if action in scope)
            for stat in settled:
                if stat not in open_ep.baseline_state:
                    continue
                after = snapshot.get(stat)
                if after is None:
                    continue
                delta = after - open_ep.baseline_state[stat]
                predicted = sum(prior.get((a, stat), 0.0) for a in scope)
                error = delta - predicted
                for action in scope:
                    own = prior.get((action, stat), 0.0)
                    pending.append((action, stat, own + error, now))

            self.closed_episodes += 1
            self.history.append(episode)
            self.last_outcome = {'action': episode.action, 'valence': valence,
                                 'consequence': consequence, 'at': now}
            ledger = self._ledger
            if ledger is not None:
                ledger.record_episode(episode)
            closed.append(episode)

        for action, stat, target, when in pending:
            table = self.contingencies[action]
            entry = table.get(stat)
            if entry is None:
                entry = Contingency(action=action, stat=stat)
                table[stat] = entry
            entry.observe(target, when)

        for episode in closed:
            self._assign_credit(episode)
        return closed

    def _record_co_occurrence(self, expiring: List[_OpenEpisode]) -> None:
        """Note, for each closing episode, which other actions overlapped it.

        This is the evidence that separates "two causes the squid has not yet
        told apart" from "two causes it never can": an action that has run at
        least once while another did not is separable in principle, and
        ordinary Rescorla-Wagner settlement will do the separating. An action
        that has NEVER run apart from another is perfectly confounded with it,
        and no amount of further repetition of the same experience will help.
        """
        for episode in expiring:
            action = episode.action
            concurrent = self._overlapping(episode, expiring)

            self.action_episodes[action] = self.action_episodes.get(action, 0) + 1
            known = set(self.action_episodes) | concurrent
            for other in known:
                if other == action:
                    continue
                if other in concurrent:
                    key = (action, other)
                    self._together[key] = self._together.get(key, 0) + 1
                else:
                    key = (action, other)
                    self._apart[key] = self._apart.get(key, 0) + 1

        for episode in expiring:
            self._settled_windows.append(
                (episode.action, episode.started, episode.closes_at))

    def _overlapping(self, episode: _OpenEpisode,
                     expiring: List[_OpenEpisode]) -> Set[str]:
        """Which other behaviours were running during this episode's window.

        Read from the windows themselves - open, expiring and recently
        settled - rather than from whatever happens to be open at the moment of
        settlement. Two behaviours that always overlap do not expire together,
        so reading the open list alone made A look like it always had company
        and B look like it never did, purely from the order the windows closed
        in. Everything downstream of this - cue competition, the confounding
        record, the deficit - inherited that asymmetry.
        """
        others: Set[str] = set()
        for other in expiring:
            if other is episode:
                continue
            if (other.started <= episode.closes_at
                    and other.closes_at >= episode.started):
                others.add(other.action)
        for other in self._open:
            if (other.started <= episode.closes_at
                    and other.closes_at >= episode.started):
                others.add(other.action)
        for action, started, closes_at in self._settled_windows:
            if started <= episode.closes_at and closes_at >= episode.started:
                others.add(action)
        others.discard(episode.action)
        return others

    def together(self, a: str, b: str) -> int:
        """Episodes of `a` during which `b` was also running."""
        return self._together.get((a, b), 0)

    def apart(self, a: str, b: str) -> int:
        """Episodes of `a` during which `b` was NOT running."""
        return self._apart.get((a, b), 0)

    def is_confounded(self, a: str, b: str, min_episodes: int = 4) -> bool:
        """Have these two actions genuinely never been observed apart?"""
        if a == b:
            return False
        if self.together(a, b) < min_episodes:
            return False
        return self.apart(a, b) == 0 and self.apart(b, a) == 0

    def unresolved_attributions(self, min_episodes: int = 4,
                                min_effect: float = 1.0,
                                balance: float = 0.4) -> List[Dict[str, Any]]:
        """Outcomes whose cause the squid demonstrably cannot pin down.

        An entry appears when two or more of the squid's actions each carry a
        substantial share of the same outcome, in the same direction, and have
        never once been observed apart. Splitting the credit between them is
        the correct thing for the learning rule to do - inventing a winner
        would be worse - but a permanent half-strength claim about each is not
        knowledge, it is an admission that the evidence so far cannot decide.

        Reported so the capability monitor can ask the structural question:
        does the network even have the means to hold the distinction, should
        the evidence ever arrive?
        """
        out: List[Dict[str, Any]] = []
        by_stat: Dict[str, List[Tuple[str, float, Contingency]]] = {}
        for action, table in self.contingencies.items():
            if self.action_episodes.get(action, 0) < min_episodes:
                continue
            for stat, entry in table.items():
                effect = entry.effect(self.baseline_drift(stat, action))
                if abs(effect) < min_effect or entry.n < min_episodes:
                    continue
                by_stat.setdefault(stat, []).append((action, effect, entry))

        for stat, rows in by_stat.items():
            for sign in (1.0, -1.0):
                same = [r for r in rows if r[1] * sign > 0]
                if len(same) < 2:
                    continue
                same.sort(key=lambda r: -abs(r[1]))
                # Grow a clique of mutually confounded candidates around the
                # largest share, keeping only shares of comparable size: a
                # bystander with a tenth of the effect is not a rival
                # explanation, it is noise.
                lead_effect = abs(same[0][1])
                clique: List[Tuple[str, float, Contingency]] = [same[0]]
                for candidate in same[1:]:
                    if abs(candidate[1]) < lead_effect * balance:
                        continue
                    if all(self.is_confounded(candidate[0], member[0], min_episodes)
                           for member in clique):
                        clique.append(candidate)
                if len(clique) < 2:
                    continue

                actions = sorted(row[0] for row in clique)
                shares = {row[0]: round(row[1], 3) for row in clique}
                together = min(self.together(a, b)
                               for a in actions for b in actions if a != b)
                out.append({
                    'stat': stat,
                    'candidates': actions,
                    'shares': shares,
                    'combined': round(sum(shares.values()), 3),
                    'together': together,
                    'apart': {a: sum(self.apart(a, b) for b in actions if b != a)
                              for a in actions},
                    'episodes': {a: self.action_episodes.get(a, 0) for a in actions},
                    'confidence': round(max(
                        row[2].confidence(self.baseline_drift(stat, row[0]))
                        for row in clique), 3),
                })
        out.sort(key=lambda row: (-abs(row['combined']), row['stat']))
        return out

    def describe_attribution(self, row: Dict[str, Any]) -> str:
        """The confounded claim, in the words the squid would use."""
        names = [humanise(a) for a in row['candidates']]
        joined = " and ".join(names) if len(names) == 2 else \
            ", ".join(names[:-1]) + " and " + names[-1]
        direction = "up" if row['combined'] > 0 else "down"
        return (f"Something about {joined} sends {humanise(row['stat'])} "
                f"{direction} by about {abs(row['combined']):.0f} points, but "
                f"they have happened together {row['together']} times and apart "
                f"none, so the squid cannot tell which of them does it.")

    def _assign_credit(self, episode: Episode) -> None:
        """Broadcast the outcome to the synapses that were causally active.

        This is the temporal part of temporal credit assignment: STDP has been
        laying down eligibility traces on every causally-ordered pair of spikes
        for the last few seconds, and the reward signal now reaches back along
        those traces. A synapse that fired in the right order just before a
        good outcome is strengthened even though the outcome arrived long after
        the spikes did.
        """
        if abs(episode.valence) < self.config.min_valence_for_reward:
            return
        stdp = self._stdp
        brain = self.brain
        if stdp is None or brain is None:
            return

        engine = getattr(brain, 'plasticity', None)
        rate = getattr(getattr(engine, 'config', None), 'learning_rate', None)
        try:
            deltas = stdp.apply_reward_modulation(
                episode.valence * self.config.reward_gain, rate=rate)
        except Exception:
            return
        if not deltas:
            return

        applied = 0
        cap = self.config.max_reward_delta
        for edge, delta in deltas.items():
            if not delta:
                continue
            delta = max(-cap, min(cap, float(delta)))
            note = (f"{humanise(episode.action)} led to "
                    f"{'a good' if episode.valence > 0 else 'a bad'} outcome "
                    f"{self.config.outcome_window:.0f}s later")
            ok = brain.apply_weight_change(
                edge, delta=delta, mechanism='causal_reward',
                detail={'valence': round(episode.valence, 3),
                        'action': episode.action,
                        'eligibility_delta': round(float(deltas[edge]), 5),
                        'note': note},
                episode_id=episode.episode_id, create=False, directed=False)
            if ok:
                applied += 1
        if applied:
            self.rewarded_episodes += 1

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------
    def known_contingencies(self, min_confidence: Optional[float] = None
                            ) -> List[Tuple[Contingency, float, float]]:
        """(contingency, effect, confidence) for everything worth believing."""
        threshold = (self.config.min_confidence_to_teach
                     if min_confidence is None else min_confidence)
        out = []
        for table in self.contingencies.values():
            for entry in table.values():
                baseline = self.baseline_drift(entry.stat, entry.action)
                confidence = entry.confidence(baseline)
                if confidence >= threshold:
                    out.append((entry, entry.effect(baseline), confidence))
        out.sort(key=lambda row: (-row[2], -abs(row[1])))
        return out

    def describe_contingency(self, entry: Contingency, effect: float,
                             confidence: float) -> str:
        direction = "down" if effect < 0 else "up"
        return (f"When it {humanise(entry.action)}, {humanise(entry.stat)} goes "
                f"{direction} by about {abs(effect):.0f} points "
                f"(seen {entry.n} time{'s' if entry.n != 1 else ''}).")

    def knowledge_items(self) -> List[KnowledgeItem]:
        """What the squid knows about its own effect on the world."""
        items: List[KnowledgeItem] = []
        for entry, effect, confidence in self.known_contingencies():
            baseline = self.baseline_drift(entry.stat, entry.action)
            recent = self._last_episode_for(entry.action)
            experience = recent.describe() if recent is not None else (
                f"{entry.n} separate occasions on which it {humanise(entry.action)}")
            consequence = (f"{humanise(entry.stat)} "
                           f"{'fell' if effect < 0 else 'rose'} by "
                           f"{abs(entry.mean_delta):.0f} on average, against a "
                           f"background drift of {baseline:+.1f}")
            items.append(KnowledgeItem(
                subject=humanise(entry.stat),
                statement=self.describe_contingency(entry, effect, confidence),
                experience=experience,
                action=entry.action,
                consequence=consequence,
                reason=(f"the same thing happened {entry.n} times, and it does not "
                        f"happen when the squid is doing something else "
                        f"(background drift {baseline:+.1f})"),
                confidence=confidence,
                strength=effect / 100.0,
                behaviour=("outcomes like this are broadcast back along the spike-timing "
                           "traces, so the synapses that produced the action are the ones "
                           "that change"),
                kind='contingency', updated=entry.last_seen))

        # What it knows it does NOT know. An honest account of the squid's
        # knowledge has to include the questions its experience cannot answer,
        # otherwise two permanent half-strength claims read as two facts.
        for row in self.unresolved_attributions():
            names = " and ".join(humanise(a) for a in row['candidates'])
            items.append(KnowledgeItem(
                subject=humanise(row['stat']),
                statement=self.describe_attribution(row),
                experience=(f"{row['together']} occasions on which {names} "
                            f"happened together, and none on which either "
                            f"happened without the other"),
                action=" + ".join(row['candidates']),
                consequence=(f"{humanise(row['stat'])} moved by "
                             f"{row['combined']:+.0f} on average"),
                reason=("the credit is split between them because nothing in "
                        "the squid's experience separates them; a share each "
                        "is the honest answer, not two facts"),
                confidence=row['confidence'],
                strength=row['combined'] / 100.0,
                behaviour=("until one of them happens without the other, or the "
                           "brain grows structure that can represent them "
                           "separately, neither claim can get any stronger"),
                kind='confounded', updated=max(
                    (e.ended for e in self.history
                     if e.action in row['candidates']), default=0.0)))
        return items

    def _last_episode_for(self, action: str) -> Optional[Episode]:
        for episode in reversed(self.history):
            if episode.action == action:
                return episode
        return None

    def cue_outcome_links(self, min_confidence: float = 0.4
                          ) -> List[Tuple[str, str, str, float]]:
        """(cue_neuron, action, outcome_stat, confidence) the squid believes in.

        Used by the capability monitor to ask a structural question: the squid
        knows this cue predicts this outcome - does its network actually have a
        pathway that can act on it?
        """
        links: List[Tuple[str, str, str, float]] = []
        seen = set()
        for entry, _effect, confidence in self.known_contingencies(min_confidence):
            for episode in reversed(self.history):
                if episode.action != entry.action:
                    continue
                for cue_name, cue_value in episode.cue.items():
                    if cue_name in PURE_INPUT_NEURONS:
                        if cue_value < SENSOR_PRESENT:
                            continue
                    elif abs(cue_value - 50.0) < 20.0:
                        continue
                    key = (cue_name, entry.action, entry.stat)
                    if key in seen:
                        continue
                    seen.add(key)
                    links.append((cue_name, entry.action, entry.stat, confidence))
                break
        return links

    def get_stats(self) -> Dict[str, Any]:
        return {
            'episodes_closed': self.closed_episodes,
            'episodes_open': len(self._open),
            'rewarded': self.rewarded_episodes,
            'actions_tracked': len(self.contingencies),
            'confident_contingencies': len(self.known_contingencies()),
            'unresolved_attributions': self.unresolved_attributions(),
            'last_outcome': dict(self.last_outcome),
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            'closed_episodes': self.closed_episodes,
            'rewarded_episodes': self.rewarded_episodes,
            'contingencies': [c.to_dict() for table in self.contingencies.values()
                              for c in table.values()],
            'all_windows': [c.to_dict() for c in self._all_windows.values()],
            'raw': [c.to_dict() for c in self._raw.values()],
            'history': [e.to_dict() for e in list(self.history)[-120:]],
            'action_episodes': dict(self.action_episodes),
            'together': [[a, b, n] for (a, b), n in self._together.items()],
            'apart': [[a, b, n] for (a, b), n in self._apart.items()],
        }

    def from_dict(self, data: dict) -> None:
        if not isinstance(data, dict):
            return
        self.closed_episodes = int(data.get('closed_episodes', 0))
        self.rewarded_episodes = int(data.get('rewarded_episodes', 0))
        self.contingencies = defaultdict(dict)
        for raw in data.get('contingencies') or []:
            try:
                entry = Contingency.from_dict(raw)
            except Exception:
                continue
            if entry.action and entry.stat:
                self.contingencies[entry.action][entry.stat] = entry
        self._all_windows = {}
        for row in data.get('all_windows') or []:
            try:
                entry = Contingency.from_dict(row)
            except Exception:
                continue
            if entry.stat:
                self._all_windows[entry.stat] = entry
        self._raw = {}
        for row in data.get('raw') or []:
            try:
                entry = Contingency.from_dict(row)
            except Exception:
                continue
            if entry.action and entry.stat:
                self._raw[(entry.action, entry.stat)] = entry
        self.history.clear()
        for raw in data.get('history') or []:
            try:
                self.history.append(Episode.from_dict(raw))
            except Exception:
                continue
        self.action_episodes = {str(k): int(v) for k, v in
                                (data.get('action_episodes') or {}).items()}
        self._together = {}
        for row in data.get('together') or []:
            if isinstance(row, (list, tuple)) and len(row) == 3:
                self._together[(str(row[0]), str(row[1]))] = int(row[2])
        self._apart = {}
        for row in data.get('apart') or []:
            if isinstance(row, (list, tuple)) and len(row) == 3:
                self._apart[(str(row[0]), str(row[1]))] = int(row[2])

    def reset(self) -> None:
        self._open.clear()
        self._current_action = ""
        self.closed_episodes = 0
        self.rewarded_episodes = 0
        self.contingencies = defaultdict(dict)
        self._all_windows = {}
        self._raw = {}
        self._idle_probe = None
        self.action_episodes = {}
        self._together = {}
        self._apart = {}
        self._settled_windows.clear()
        self.history.clear()
        self.last_outcome = {}
