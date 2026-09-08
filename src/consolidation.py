"""
consolidation.py - sleep-time memory consolidation, as a core engine feature.

While the squid is awake, PlasticityEngine accumulates evidence tick by tick
and commits small weight changes. While it sleeps, the day's strongest
co-activations are replayed and made durable, and connections that never
amounted to anything are pruned. That is the second half of "the squid learns
from its environment": waking experience proposes, sleep disposes.

The replay algorithm itself lives in src/sleep_consolidation.py (formerly
plugins/sleep_replay/replay_core.py). This module is the engine-side owner:
it samples during waking hours, runs the replay session when the squid falls
asleep, and applies the results to the live network. The Sleep Replay plugin
is now a control surface over this instance rather than a second copy.
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional, Tuple

from .sleep_consolidation import ReplayConfig, SleepReplayEngine

Pair = Tuple[str, str]


class ConsolidationManager:
    """Owns the sleep/replay cycle for one brain."""

    def __init__(self, brain_widget, config: Optional[ReplayConfig] = None):
        self.brain_widget = brain_widget
        self.engine = SleepReplayEngine(config or ReplayConfig())
        self.enabled = True

        self._was_sleeping = False
        self._session = None
        self.last_summary: Dict = {}
        self.nights_completed = 0

    # ------------------------------------------------------------------
    def observe(self, state: Dict[str, float]) -> int:
        """Record one waking sample of which neurons were active together."""
        if not self.enabled:
            return 0
        try:
            return self.engine.record_sample(state)
        except Exception:
            return 0

    # ------------------------------------------------------------------
    def on_tick(self, is_sleeping: bool, state: Dict[str, float]) -> Optional[Dict]:
        """Drive the consolidation state machine. Call once per simulation tick.

        Returns a summary dict on the tick a night's consolidation completes.
        """
        if not self.enabled:
            return None

        if not is_sleeping:
            self.observe(state)
            self._was_sleeping = False
            self._session = None
            return None

        # Falling asleep: build the night's replay programme.
        if not self._was_sleeping:
            self._was_sleeping = True
            self._session = self._begin_night()
            return None

        # Asleep: run one replay cycle per tick so it is visible, not instant.
        if self._session is not None:
            return self._step_night()
        return None

    # ------------------------------------------------------------------
    def _begin_night(self):
        try:
            if not self.engine.has_enough_to_replay():
                return None
            # Memories bias which pairs are worth consolidating.
            squid = getattr(getattr(self.brain_widget, 'tamagotchi_logic', None), 'squid', None)
            mm = getattr(squid, 'memory_manager', None)
            if mm is not None and hasattr(mm, 'get_all_short_term_memories'):
                try:
                    self.engine.harvest_memory(mm.get_all_short_term_memories(raw=True) or [])
                except Exception:
                    pass
            session = self.engine.build_session()
            self._replayed = 0
            self._pruned = 0
            self._cycles = 0
            return session
        except Exception as e:
            print(f"[Consolidation] could not start night: {type(e).__name__}: {e}")
            return None

    def _step_night(self) -> Optional[Dict]:
        session = self._session
        if session is None:
            return None

        try:
            items = session.next_cycle()
        except Exception:
            items = None

        if items:
            self._cycles += 1
            for item in items:
                self._strengthen(item)
                self._replayed += 1
            return None

        # Programme finished: prune, then close the night.
        summary = self._finish_night()
        self._session = None
        return summary

    # ------------------------------------------------------------------
    def _strengthen(self, item) -> None:
        """Apply one replayed co-activation to the live weights.

        Replay reinforces the SIGN the waking network already discovered: a
        pair that became inhibitory is consolidated as more inhibitory. Replay
        must not be able to flip an association, only deepen it.
        """
        bw = self.brain_widget
        pair = getattr(item, 'pair', None)
        delta = float(getattr(item, 'delta', 0.0) or 0.0)
        if not pair or len(pair) != 2 or delta == 0.0:
            return

        n1, n2 = pair
        edge = None
        if (n1, n2) in bw.weights:
            edge = (n1, n2)
        elif (n2, n1) in bw.weights:
            edge = (n2, n1)
        if edge is None:
            return  # replay deepens existing structure, it does not invent it

        old = float(bw.weights[edge])
        direction = 1.0 if old >= 0 else -1.0
        score = float(getattr(item, 'salience', 0.0) or 0.0)
        apply_change = getattr(bw, 'apply_weight_change', None)
        note = ("replayed during sleep because these two were among the day's "
                "strongest co-activations")
        if apply_change is not None:
            apply_change(edge, delta=direction * abs(delta),
                         mechanism='consolidation',
                         detail={'note': note, 'salience': round(score, 4),
                                 'night': self.nights_completed + 1},
                         create=False, animate=True)
        else:
            bw.weights[edge] = max(-1.0, min(1.0, old + direction * abs(delta)))

    def _finish_night(self) -> Dict:
        bw = self.brain_widget
        pruned: List[Pair] = []
        protected = self._protected_neurons()

        def is_immune(n1, n2):
            return n1 in protected or n2 in protected

        try:
            plan = self.engine.plan_prune(bw.weights, is_immune)
            remove = getattr(bw, 'remove_weight', None)
            for edge in plan or []:
                if edge not in bw.weights:
                    continue
                reason = ("pruned during sleep - it stayed weak and was never "
                          "replayed, so it never came to mean anything")
                if remove is not None:
                    remove(edge, mechanism='prune', reason=reason)
                else:
                    del bw.weights[edge]
                pruned.append(edge)
        except Exception as e:
            print(f"[Consolidation] prune skipped: {type(e).__name__}: {e}")

        # Synaptic homeostasis: what survives pruning is still scaled back, so
        # a night of sleep lowers the whole network's gain and only what was
        # replayed comes out ahead.
        downscaled = 0
        try:
            for edge, new_w in (self.engine.plan_downscale(bw.weights, is_immune) or {}).items():
                if edge not in bw.weights:
                    continue
                apply_change = getattr(bw, 'apply_weight_change', None)
                if apply_change is not None:
                    if apply_change(edge, value=new_w, mechanism='consolidation',
                                    detail={'note': "scaled back during sleep "
                                                    "(synaptic homeostasis)"},
                                    create=False, animate=False):
                        downscaled += 1
                else:
                    bw.weights[edge] = new_w
                    downscaled += 1
        except Exception as e:
            print(f"[Consolidation] downscale skipped: {type(e).__name__}: {e}")

        try:
            self.engine.finish_day(self._replayed, len(pruned), self._cycles)
        except Exception:
            pass

        self.nights_completed += 1
        self.last_summary = {
            'replayed': self._replayed,
            'pruned': len(pruned),
            'cycles': self._cycles,
            'pruned_pairs': pruned,
            'downscaled': downscaled,
            'night': self.nights_completed,
            'finished_at': time.time(),
        }
        print(f"🌙 Consolidation night {self.nights_completed}: "
              f"replayed {self._replayed} pair(s) over {self._cycles} cycle(s), "
              f"pruned {len(pruned)}")
        if hasattr(bw, 'sync_connections_from_weights'):
            bw.sync_connections_from_weights()
        bw.mark_render_dirty()
        return self.last_summary

    def _protected_neurons(self) -> set:
        """Never prune a new neuron's only links, or a connector's."""
        bw = self.brain_widget
        protected = set()
        neuro = getattr(bw, 'enhanced_neurogenesis', None)
        if neuro is not None:
            for name, fn in getattr(neuro, 'functional_neurons', {}).items():
                if getattr(fn, 'neuron_type', '') == 'connector':
                    protected.add(name)
        data = getattr(bw, 'neurogenesis_data', {}) or {}
        protected.update(data.get('new_neurons', []) or [])
        return protected

    # ------------------------------------------------------------------
    # Manual control (used by the Sleep Replay control panel)
    # ------------------------------------------------------------------
    def force_consolidation(self, max_cycles: int = 200) -> Optional[Dict]:
        """Run a full consolidation pass now, even while the squid is awake.

        Same engine, same weights, same provenance as a real night - it just
        does not wait for the squid to fall asleep.
        """
        if self._session is not None:
            return None
        session = self._begin_night()
        if session is None:
            return None
        self._session = session
        summary = None
        for _ in range(max_cycles):
            summary = self._step_night()
            if summary is not None:
                break
        if self._session is not None:
            summary = self._finish_night()
            self._session = None
        return summary

    def clear_buffer(self) -> None:
        """Forget the day's accumulated co-activation without consolidating it."""
        try:
            self.engine.tracker.clear()
        except Exception:
            pass

    @property
    def is_replaying(self) -> bool:
        return self._session is not None

    # ------------------------------------------------------------------
    def get_stats(self) -> Dict:
        stats = {'nights_completed': self.nights_completed,
                 'enabled': self.enabled,
                 'asleep': self._was_sleeping,
                 'last': self.last_summary}
        try:
            stats.update(self.engine.get_stats())
        except Exception:
            pass
        return stats

    def to_dict(self) -> Dict:
        return {'nights_completed': self.nights_completed}

    def from_dict(self, data: Dict) -> None:
        if isinstance(data, dict):
            self.nights_completed = int(data.get('nights_completed', 0))
