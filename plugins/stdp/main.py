"""
STDP Plugin for Dosidicus

Augments the existing Hebbian learning system with Spike-Timing-Dependent
Plasticity (STDP). Connections strengthen when the pre-synaptic neuron fires
BEFORE the post-synaptic neuron (causal), and weaken when the order is
reversed (acausal). This teaches the squid cause-and-effect rather than
mere correlation.

Integration method: monkey-patches BrainWorker._perform_hebbian_learning on
the live instance, so it slots in without touching any core files.

Reward signals are applied on feed / clean / medicine events via the
standard hook system, using STDP eligibility traces as the third learning
factor.
"""

import sys
import os
import time
import logging
import traceback
from heapq import nlargest
from collections import deque
from typing import Optional, Dict

# ---------------------------------------------------------------------------
# Ensure the project root is importable (mirrors multiplayer plugin pattern)
# ---------------------------------------------------------------------------
try:
    _current_dir = os.path.dirname(os.path.abspath(__file__))
    _project_root = os.path.abspath(os.path.join(_current_dir, '..', '..'))
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)
except Exception as _e:
    print(f"STDP Plugin: sys.path setup warning: {_e}")

from PyQt5 import QtCore, QtWidgets

try:
    from display_scaling import DisplayScaling
except ImportError:
    class DisplayScaling:
        @classmethod
        def font_size(cls, size): return size
        @classmethod
        def scale_css(cls, css): return css

# Import STDP core from this package
try:
    from .stdp_core import STDPLearner, STDPConfig
except ImportError:
    from stdp_core import STDPLearner, STDPConfig

# ---------------------------------------------------------------------------
# Plugin metadata
# ---------------------------------------------------------------------------
PLUGIN_NAME        = "STDP"
PLUGIN_VERSION     = "1.0.0"
PLUGIN_AUTHOR      = "ViciousSquid"
PLUGIN_DESCRIPTION = "Spike-Timing-Dependent Plasticity – adds causal learning on top of Hebbian"
PLUGIN_REQUIRES    = []

# Neurons that receive external input – never modified by learning
_PURE_INPUTS = {
    "can_see_food", "is_eating", "is_sleeping", "is_sick",
    "pursuing_food", "is_fleeing", "is_startled", "external_stimulus",
    "plant_proximity",
}


# ===========================================================================
# Plugin class
# ===========================================================================

class STDPPlugin:
    """
    Integrates STDP learning into Dosidicus without modifying core files.

    Lifecycle
    ---------
    setup()  – called by PluginManager once tamagotchi_logic is ready
    cleanup() – called on disable / app exit
    """

    def __init__(self):
        self.logger: Optional[logging.Logger] = None
        self.plugin_manager = None
        self.tamagotchi_logic = None

        # References resolved during setup()
        self._brain_worker  = None   # BrainWorker QThread instance
        self._brain_widget  = None   # BrainWidget QWidget instance

        # The STDP learning engine
        self.stdp_learner: Optional[STDPLearner] = None

        # Saved reference so we can restore on cleanup
        self._original_hebbian_fn = None

        # Timer for periodic spike sampling (main thread)
        self._spike_timer: Optional[QtCore.QTimer] = None

        # Periodic cleanup timer
        self._cleanup_timer: Optional[QtCore.QTimer] = None

        # UI banner widget injected into the learning tab
        self._ui_banner: Optional[QtWidgets.QWidget] = None
        self._banner_stats_label: Optional[QtWidgets.QLabel] = None
        self._banner_update_timer: Optional[QtCore.QTimer] = None

        # Control panel (opened on demand from the Plugins menu)
        self._panel = None

        self.is_setup = False
        self.enabled  = False

        # Thread-safe queue: worker thread pushes (pair, weight_change, meta),
        # main-thread spike timer drains it into the learning tab.
        self._pending_tab_updates: deque = deque()

        # Configurable parameters (can be adjusted at runtime)
        self.config = STDPConfig(
            tau_plus=0.15,
            tau_minus=0.15,
            A_plus=0.08,
            A_minus=0.05,
            time_window=0.5,
            spike_threshold=60.0,
            spike_rising_threshold=8.0,
            refractory_period=0.08,
            burst_bonus=1.5,
            stdp_weight=0.4,        # 40 % STDP, 60 % Hebbian
            eligibility_decay=0.95,
            eligibility_window=2.0,
        )

    # -----------------------------------------------------------------------
    # Setup / teardown
    # -----------------------------------------------------------------------

    def setup(self, plugin_manager, tamagotchi_logic) -> bool:
        """Called by PluginManager after core components are ready."""
        self.plugin_manager    = plugin_manager
        self.tamagotchi_logic  = tamagotchi_logic

        # Logger
        if hasattr(plugin_manager, 'logger'):
            self.logger = plugin_manager.logger.getChild(PLUGIN_NAME)
        else:
            self.logger = logging.getLogger(PLUGIN_NAME)
            if not self.logger.handlers:
                h = logging.StreamHandler()
                h.setFormatter(logging.Formatter('%(levelname)s:%(name)s: %(message)s'))
                self.logger.addHandler(h)
            self.logger.setLevel(logging.INFO)

        self.logger.info(f"Setting up {PLUGIN_NAME} v{PLUGIN_VERSION}...")

        # Build the learner
        self.stdp_learner = STDPLearner(self.config)

        # Resolve brain_worker and brain_widget
        if not self._resolve_brain_references():
            self.logger.error("Could not resolve BrainWorker / BrainWidget – setup aborted.")
            return False

        # Patch the worker
        self._install_hebbian_patch()

        # Spike-sampling timer (runs on main thread, safe to touch brain_widget)
        self._spike_timer = QtCore.QTimer()
        self._spike_timer.timeout.connect(self._sample_spikes)
        self._spike_timer.start(150)   # sample every 150 ms

        # Periodic STDP cleanup timer
        self._cleanup_timer = QtCore.QTimer()
        self._cleanup_timer.timeout.connect(self._periodic_cleanup)
        self._cleanup_timer.start(10_000)  # every 10 s

        # Subscribe to game-event hooks for reward modulation
        self._subscribe_hooks()

        self.is_setup = True

        # Respect is_enabled_by_default from the plugin registry.
        # The core app calls setup() on every plugin unconditionally, so we
        # must read the flag ourselves rather than relying on the caller.
        plugin_key  = PLUGIN_NAME.lower()
        plugin_data = plugin_manager.plugins.get(plugin_key, {})
        self.enabled = plugin_data.get('is_enabled_by_default', False)

        # Only inject the UI banner if the plugin is actually starting enabled.
        if self.enabled:
            QtCore.QTimer.singleShot(1200, self._inject_ui_banner)

        self.logger.info(f"{PLUGIN_NAME} setup complete. "
                         f"Patched BrainWorker._perform_hebbian_learning ✓  "
                         f"(enabled={self.enabled})")

        print("\n")
        print("=" * 60)
        if self.enabled:
            print("  ⚡  STDP LEARNING IS ACTIVE  ⚡")
        else:
            print("  ⚡  STDP plugin loaded (DISABLED – enable via Plugins menu)  ⚡")
        print("=" * 60)
        print(f"  Blend     : {int((1 - self.config.stdp_weight)*100)}% Hebbian  +  {int(self.config.stdp_weight*100)}% STDP")
        print(f"  Window    : {int(self.config.time_window * 1000)} ms")
        print(f"  Threshold : {self.config.spike_threshold}")
        print(f"  Worker    : {type(self._brain_worker).__name__} patched ✓")
        print("=" * 60)
        print("  Watch for [LTP] / [LTD] tags on Hebbian lines")
        print("=" * 60)
        print("\n")

        return True

    def cleanup(self):
        """Restore original BrainWorker method and stop timers."""
        if self.logger:
            self.logger.info(f"{PLUGIN_NAME}: cleanup called")

        if self._spike_timer:
            self._spike_timer.stop()
        if self._cleanup_timer:
            self._cleanup_timer.stop()
        if self._banner_update_timer:
            self._banner_update_timer.stop()

        self._restore_hebbian_patch()

        # Close control panel if open
        if self._panel is not None:
            try:
                self._panel.close()
            except Exception:
                pass
            self._panel = None

        # Remove UI banner if present
        if self._ui_banner is not None:
            try:
                self._ui_banner.setParent(None)
                self._ui_banner.deleteLater()
                self._ui_banner = None
            except Exception:
                pass

        self.is_setup = False

    def shutdown(self):
        """Called by PluginManager when the plugin is disabled/unloaded."""
        self.cleanup()

    # -----------------------------------------------------------------------
    # Reference resolution
    # -----------------------------------------------------------------------

    def _resolve_brain_references(self) -> bool:
        """Walk the object graph to find BrainWorker and BrainWidget."""
        tl = self.tamagotchi_logic

        # brain_window → brain_widget
        brain_window = getattr(tl, 'brain_window', None)
        if brain_window is None:
            # Try plugin_manager path
            pm = self.plugin_manager
            brain_window = getattr(pm, 'brain_window', None)

        if brain_window is None:
            self.logger.error("Cannot find brain_window on tamagotchi_logic or plugin_manager")
            return False

        self._brain_widget = getattr(brain_window, 'brain_widget', None)
        if self._brain_widget is None:
            self.logger.error("brain_window has no brain_widget")
            return False

        # brain_worker is typically on brain_widget (set by SquidBrainWindow)
        self._brain_worker = getattr(self._brain_widget, 'brain_worker', None)
        if self._brain_worker is None:
            # Fallback: look on brain_window itself
            self._brain_worker = getattr(brain_window, 'brain_worker', None)

        if self._brain_worker is None:
            self.logger.error("Cannot find brain_worker on brain_widget or brain_window")
            return False

        self.logger.info(
            f"References resolved: worker={type(self._brain_worker).__name__} "
            f"widget={type(self._brain_widget).__name__}"
        )
        return True

    # -----------------------------------------------------------------------
    # Monkey-patch
    # -----------------------------------------------------------------------

    def _install_hebbian_patch(self):
        """Replace _perform_hebbian_learning on the live BrainWorker instance."""
        worker = self._brain_worker
        self._original_hebbian_fn = worker._perform_hebbian_learning

        stdp_plugin_ref = self   # captured in closure

        def _stdp_perform_hebbian_learning():
            """STDP-augmented drop-in for BrainWorker._perform_hebbian_learning."""
            # Fall back to original if plugin was disabled/unloaded
            if not stdp_plugin_ref.is_setup or stdp_plugin_ref._original_hebbian_fn is None:
                if stdp_plugin_ref._original_hebbian_fn:
                    stdp_plugin_ref._original_hebbian_fn()
                return

            # Fall back to original if STDP is toggled off by the user
            if not stdp_plugin_ref.enabled:
                stdp_plugin_ref._original_hebbian_fn()
                return

            stdp_plugin_ref._run_stdp_hebbian(worker)

        # Bind to the instance (not the class) so only this worker is affected
        import types
        worker._perform_hebbian_learning = types.MethodType(
            lambda self_w: _stdp_perform_hebbian_learning(), worker
        )
        # Simpler: just replace the bound reference directly
        worker._perform_hebbian_learning = _stdp_perform_hebbian_learning

        self.logger.info("Hebbian patch installed on BrainWorker instance")

    def _restore_hebbian_patch(self):
        """Undo the monkey-patch."""
        if self._brain_worker and self._original_hebbian_fn:
            self._brain_worker._perform_hebbian_learning = self._original_hebbian_fn
            self.logger.info("Hebbian patch removed – BrainWorker restored")

    # -----------------------------------------------------------------------
    # Learning-tab UI banner
    # -----------------------------------------------------------------------

    def _inject_ui_banner(self):
        """
        Insert a styled STDP status banner at the top of the Learning tab's
        card area.  Safe to call from main thread only.
        """
        if not self.enabled:
            return
        try:
            brain_window = getattr(self.tamagotchi_logic, 'brain_window', None)
            if brain_window is None:
                return

            nn_viz_tab = getattr(brain_window, 'nn_viz_tab', None)
            if nn_viz_tab is None:
                return

            layout = getattr(nn_viz_tab, 'learning_content_layout', None)
            if layout is None:
                return

            # Idempotent: the app reloads plugins at startup (load_all_plugins
            # replaces instances), so setup()/_inject can run more than once.
            # Sweep any existing STDP banner(s) out of the shared Learning tab
            # first so we never stack duplicates.
            if self._banner_update_timer is not None:
                self._banner_update_timer.stop()
            for _old in nn_viz_tab.findChildren(QtWidgets.QWidget, "stdp_banner"):
                _old.setParent(None)
                _old.deleteLater()
            self._ui_banner = None
            self._banner_stats_label = None

            # Build the banner widget
            banner = QtWidgets.QWidget()
            banner.setObjectName("stdp_banner")
            banner.setStyleSheet("""
                QWidget#stdp_banner {
                    background: qlineargradient(
                        x1:0, y1:0, x2:1, y2:0,
                        stop:0 #1a237e, stop:1 #283593
                    );
                    border-radius: 10px;
                    border: 2px solid #5c6bc0;
                }
            """)

            row = QtWidgets.QHBoxLayout(banner)
            row.setContentsMargins(16, 12, 16, 12)
            row.setSpacing(12)

            # Lightning icon
            icon_label = QtWidgets.QLabel("⚡")
            icon_label.setStyleSheet(f"font-size: {DisplayScaling.font_size(28)}px; background: transparent;")
            row.addWidget(icon_label)

            # Text block
            text_col = QtWidgets.QVBoxLayout()
            text_col.setSpacing(2)

            title = QtWidgets.QLabel("STDP Learning Active")
            title.setStyleSheet(
                f"font-size: {DisplayScaling.font_size(15)}px; font-weight: 700; color: #e8eaf6; background: transparent;"
            )
            text_col.addWidget(title)

            detail = QtWidgets.QLabel(
                f"{int((1 - self.config.stdp_weight) * 100)}% Hebbian  +  "
                f"{int(self.config.stdp_weight * 100)}% spike-timing  ·  "
                f"window {int(self.config.time_window * 1000)} ms  ·  "
                f"threshold {self.config.spike_threshold:.0f}"
            )
            detail.setStyleSheet(
                f"font-size: {DisplayScaling.font_size(12)}px; color: #9fa8da; background: transparent;"
            )
            text_col.addWidget(detail)
            row.addLayout(text_col)

            row.addStretch()

            # Live LTP/LTD counters (updated by a timer)
            self._banner_stats_label = QtWidgets.QLabel("LTP — · LTD —")
            self._banner_stats_label.setStyleSheet(
                f"font-size: {DisplayScaling.font_size(12)}px; font-weight: 600; color: #80cbc4; background: transparent;"
            )
            row.addWidget(self._banner_stats_label)

            # Insert at position 0 (before the stretch at the bottom)
            layout.insertWidget(0, banner)
            self._ui_banner = banner

            # Timer to keep the LTP/LTD counter live
            self._banner_update_timer = QtCore.QTimer()
            self._banner_update_timer.timeout.connect(self._refresh_banner_stats)
            self._banner_update_timer.start(3000)   # refresh every 3 s

            self.logger.info("STDP banner injected into Learning tab")

        except Exception as exc:
            self.logger.warning(f"Could not inject UI banner: {exc}")

    def _refresh_banner_stats(self):
        """Update the live counter label on the banner."""
        if self._ui_banner is None or self.stdp_learner is None:
            return
        try:
            stats = self.stdp_learner.get_stats()
            ltp = stats.get('ltp_events', 0)
            ltd = stats.get('ltd_events', 0)
            spikes = stats.get('spike_stats', {}).get('total_spikes', 0)
            self._banner_stats_label.setText(
                f"LTP {ltp}  ·  LTD {ltd}  ·  spikes {spikes}"
            )
        except RuntimeError:
            # Banner was swept by a reloaded instance – stop this stale timer.
            if self._banner_update_timer is not None:
                self._banner_update_timer.stop()
        except Exception:
            pass

    # -----------------------------------------------------------------------
    # Patched Hebbian learning (runs on BrainWorker thread)
    # -----------------------------------------------------------------------

    def _run_stdp_hebbian(self, worker):
        """
        STDP-augmented Hebbian learning.

        Mirrors the original BrainWorker._perform_hebbian_learning logic but
        replaces the pure-Hebbian delta with the combined STDP+Hebbian signal
        from STDPLearner.compute_combined_learning().
        """
        from PyQt5.QtCore import QMutexLocker

        # --- Snapshot cache (thread-safe) ---
        with QMutexLocker(worker._cache_mutex):
            state           = worker.cache['state']
            weights         = worker.cache['weights']
            neuron_list     = list(worker.cache['positions'].keys())
            excluded        = worker.cache['excluded_neurons']
            connector_nrns  = worker.cache['connector_neurons']
            config          = worker.cache['config']
            base_lr         = worker.cache['learning_rate']
            new_neurons     = worker.cache['new_neurons']
            custom_neurons  = worker.cache.get('custom_neurons', set())

        if not config:
            self.logger.warning("STDP Hebbian skipped – no config in cache")
            return
        if not neuron_list:
            self.logger.warning("STDP Hebbian skipped – no neurons in cache")
            return

        # Record spikes from current state into STDP learner
        # (spike_tracker.record_batch is thread-safe via its own mutex)
        self.stdp_learner.record_state(state)

        # --- Build candidate list (same exclusion rules as original) ---
        candidates = [
            n for n in neuron_list
            if n not in excluded
            and n not in connector_nrns
            and n not in _PURE_INPUTS
        ]

        if len(candidates) < 2:
            worker.hebbian_result.emit({'updated_pairs': []})
            return

        # --- Score pairs ---
        scored_pairs = []
        import random
        for i, n1 in enumerate(candidates):
            for n2 in candidates[i + 1:]:
                v1 = self._get_neuron_value(state.get(n1, 50))
                v2 = self._get_neuron_value(state.get(n2, 50))
                score = v1 + v2 + random.uniform(0, 40)

                pair_key = tuple(sorted((n1, n2)))
                if pair_key in worker._last_hebbian_pairs:
                    score -= 500   # same cooldown penalty as original

                scored_pairs.append((score, n1, n2, v1, v2))

        if not scored_pairs:
            return

        # --- Select top pairs ---
        top_k = 2
        if hasattr(config, 'neurogenesis'):
            top_k = config.neurogenesis.get('max_hebbian_pairs', 2)

        top_pairs = nlargest(top_k, scored_pairs)
        worker._last_hebbian_pairs = [tuple(sorted((n1, n2))) for _, n1, n2, _, _ in top_pairs]

        # --- Compute weight updates with STDP ---
        hebbian_cfg = getattr(config, 'hebbian', {})
        decay_rate  = hebbian_cfg.get('weight_decay', 0.01)

        weight_updates     = {}
        updated_pairs_list = []
        ltp_count = 0
        ltd_count = 0

        for _, n1, n2, v1, v2 in top_pairs:
            pair         = (n1, n2)
            reverse_pair = (n2, n1)

            use_pair = None
            if pair in weights:
                use_pair = pair
            elif reverse_pair in weights:
                use_pair = reverse_pair

            if not use_pair:
                use_pair = pair
                old_w = 0.0
                weight_updates[use_pair] = {
                    'old_weight': 0.0,
                    'new_weight': 0.0,
                    'is_new_connection': True,
                }
            else:
                old_w = weights[use_pair]

            # Learning rate boost for new neurons
            lr = base_lr
            if n1 in new_neurons or n2 in new_neurons:
                lr *= 2.0

            is_custom = (n1 in custom_neurons or n2 in custom_neurons)

            # Combined STDP + Hebbian delta
            combined_delta, meta = self.stdp_learner.compute_combined_learning(
                n1, n2, v1, v2,
                base_learning_rate=lr,
                is_custom=is_custom,
            )

            if meta.get('is_ltp'):
                ltp_count += 1
            elif meta.get('is_ltd'):
                ltd_count += 1

            # Forward to control panel logger (main thread will flush)
            if self._panel:
                self._panel.record_encoding(
                    n1, n2,
                    meta.get('hebbian_delta', 0.0),
                    meta.get('stdp_delta', 0.0),
                    combined_delta,
                    meta.get('stdp_direction', 'none'),
                    self.config.stdp_weight,
                )

            new_w = old_w + combined_delta - (old_w * decay_rate)
            new_w = max(-1.0, min(1.0, new_w))

            is_new = (
                use_pair in weight_updates
                and weight_updates[use_pair].get('is_new_connection', False)
            )
            weight_updates[use_pair] = {
                'old_weight': old_w,
                'new_weight': new_w,
                'is_new_connection': is_new,
            }
            updated_pairs_list.append(use_pair)

            # Queue a learning-tab update with full STDP metadata (drained on main thread)
            weight_change = "increase" if new_w > old_w else ("decrease" if new_w < old_w else None)
            tab_meta = dict(meta)
            tab_meta['stdp_weight'] = self.config.stdp_weight
            self._pending_tab_updates.append((use_pair, weight_change, tab_meta))

        if updated_pairs_list:
            stdp_tag = ""
            if ltp_count:
                stdp_tag += f" [LTP×{ltp_count}]"
            if ltd_count:
                stdp_tag += f" [LTD×{ltd_count}]"
            print(f"🧠 STDP+Hebbian: updated {len(updated_pairs_list)} pair(s){stdp_tag}")

        worker.hebbian_result.emit({
            'updated_pairs': updated_pairs_list,
            'weight_updates': weight_updates,
        })

    @staticmethod
    def _get_neuron_value(raw) -> float:
        """Normalise neuron values (mirrors BrainWorker._get_neuron_value)."""
        if isinstance(raw, (int, float)):
            return float(raw)
        if isinstance(raw, bool):
            return 100.0 if raw else 0.0
        return 50.0

    # -----------------------------------------------------------------------
    # Spike sampling (main thread timer)
    # -----------------------------------------------------------------------

    def _sample_spikes(self):
        """
        Periodically read the live brain state and feed it into the spike
        tracker.  Runs on the main thread so it's safe to read brain_widget
        and call into the learning tab UI.
        """
        if not self.enabled or self.stdp_learner is None:
            return
        if self._brain_widget is None:
            return

        state = getattr(self._brain_widget, 'state', None)
        if not state:
            return

        spikes = self.stdp_learner.record_state(state)

        # Forward new spikes to the control panel logger
        if self._panel and spikes:
            tracker = self.stdp_learner.spike_tracker
            for neuron_name, spike_event in spikes:
                is_burst = tracker._is_bursting_nolock(neuron_name)
                self._panel.record_spike(
                    neuron_name,
                    spike_event.activation_level,
                    spike_event.was_rising,
                    is_burst,
                )

        # Drain pending learning-tab updates (pushed by worker thread)
        if self._pending_tab_updates:
            nn_viz_tab = None
            try:
                brain_window = getattr(self.tamagotchi_logic, 'brain_window', None)
                if brain_window:
                    nn_viz_tab = getattr(brain_window, 'nn_viz_tab', None)
            except Exception:
                pass

            while self._pending_tab_updates:
                try:
                    pair, weight_change, meta = self._pending_tab_updates.popleft()
                    if nn_viz_tab is not None:
                        nn_viz_tab.add_log_entry("", pair, weight_change, stdp_meta=meta)
                except Exception:
                    pass

    # -----------------------------------------------------------------------
    # Reward modulation via eligibility traces
    # -----------------------------------------------------------------------

    def apply_reward(self, signal: float, reason: str = ""):
        """
        Modulate recent eligibility traces by *signal* and apply the resulting
        weight deltas directly to brain_widget.weights.

        Positive signal → reinforce recent causal connections.
        Negative signal → weaken them.
        """
        if not self.enabled or self.stdp_learner is None:
            return
        if self._brain_widget is None:
            return

        deltas: Dict = self.stdp_learner.apply_reward_modulation(signal)
        if not deltas:
            return

        weights = getattr(self._brain_widget, 'weights', {})
        applied = 0
        for (pre, post), delta in deltas.items():
            pair = (pre, post)
            rev  = (post, pre)
            use  = pair if pair in weights else (rev if rev in weights else None)
            if use:
                old_w = weights[use]
                weights[use] = max(-1.0, min(1.0, old_w + delta))
                applied += 1

        if applied:
            tag = f" ({reason})" if reason else ""
            sign = "+" if signal > 0 else ""
            self.logger.debug(
                f"Reward{tag}: signal={sign}{signal:.2f}, "
                f"modulated {applied} connection(s)"
            )
            print(f"⚡ STDP reward{tag}: {sign}{signal:.2f} → {applied} weight(s) modulated")

    # -----------------------------------------------------------------------
    # Hook subscriptions
    # -----------------------------------------------------------------------

    def _subscribe_hooks(self):
        pm = self.plugin_manager
        if pm is None:
            return

        subscriptions = [
            ("on_feed",      self._on_feed),
            ("on_clean",     self._on_clean),
            ("on_medicine",  self._on_medicine),
            ("on_sleep",     self._on_sleep),
            ("on_wake",      self._on_wake),
            ("on_startle",   self._on_startle),
        ]

        for hook_name, cb in subscriptions:
            try:
                if hasattr(pm, 'subscribe_to_hook'):
                    pm.subscribe_to_hook(hook_name, PLUGIN_NAME, cb)
                    self.logger.debug(f"Subscribed to {hook_name}")
            except Exception as exc:
                self.logger.warning(f"Could not subscribe to {hook_name}: {exc}")

    # Hook callbacks --------------------------------------------------------

    def _on_feed(self, **kwargs):
        self.apply_reward(+0.5, "fed")

    def _on_clean(self, **kwargs):
        self.apply_reward(+0.3, "cleaned")

    def _on_medicine(self, **kwargs):
        self.apply_reward(+0.4, "medicine")

    def _on_sleep(self, **kwargs):
        self.apply_reward(+0.2, "sleep")

    def _on_wake(self, **kwargs):
        # Waking resets recent context – mild positive
        self.apply_reward(+0.1, "wake")

    def _on_startle(self, **kwargs):
        self.apply_reward(-0.3, "startled")

    # -----------------------------------------------------------------------
    # Periodic cleanup
    # -----------------------------------------------------------------------

    def _periodic_cleanup(self):
        """Remove stale spike records and eligibility traces."""
        if self.stdp_learner:
            self.stdp_learner.cleanup()

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return current STDP statistics (safe to call from any thread)."""
        if self.stdp_learner is None:
            return {}
        stats = self.stdp_learner.get_stats()
        stats['enabled'] = self.enabled
        stats['stdp_weight'] = self.config.stdp_weight
        return stats

    def set_stdp_weight(self, weight: float):
        """Adjust the STDP/Hebbian blend ratio at runtime (0 = pure Hebbian, 1 = pure STDP)."""
        self.config.stdp_weight = max(0.0, min(1.0, weight))
        if self.stdp_learner:
            self.stdp_learner.config.stdp_weight = self.config.stdp_weight
        if self.logger:
            self.logger.info(f"STDP weight set to {self.config.stdp_weight:.2f}")

    def enable(self):
        """Called by PluginManager when the plugin is enabled."""
        self.set_enabled(True)
        return True

    def disable(self):
        """Called by PluginManager when the plugin is disabled."""
        self.set_enabled(False)
        return True

    def set_enabled(self, enabled: bool):
        self.enabled = enabled
        status = "enabled" if enabled else "disabled (pure Hebbian)"
        if self.logger:
            self.logger.info(f"STDP {status}")
        print(f"⚡ STDP learning {status}")
        if enabled:
            if self._ui_banner is None:
                QtCore.QTimer.singleShot(0, self._inject_ui_banner)
            elif self._ui_banner is not None:
                self._ui_banner.setVisible(True)
        else:
            if self._ui_banner is not None:
                self._ui_banner.setVisible(False)

    def reset_stats(self):
        if self.stdp_learner:
            self.stdp_learner.reset_stats()

    # -----------------------------------------------------------------------
    # Plugin menu integration
    # -----------------------------------------------------------------------

    def register_menu_actions(self, main_window: QtWidgets.QMainWindow,
                              menu: QtWidgets.QMenu):
        """Called by the UI to populate the Plugins > STDP submenu."""
        panel_action = QtWidgets.QAction("Control Panel…", main_window)
        panel_action.triggered.connect(
            lambda: self.show_control_panel(main_window)
        )
        menu.addAction(panel_action)

        menu.addSeparator()

        toggle_action = QtWidgets.QAction("Enabled", main_window)
        toggle_action.setCheckable(True)
        toggle_action.setChecked(self.enabled)
        toggle_action.toggled.connect(self.set_enabled)
        menu.addAction(toggle_action)

    def show_control_panel(self, parent=None):
        """Open (or raise) the STDP control panel."""
        if self._panel is None or not self._panel.isVisible():
            try:
                from .stdp_control_panel import STDPControlPanel
            except ImportError:
                from stdp_control_panel import STDPControlPanel
            self._panel = STDPControlPanel(self, parent)
            self._panel.show()
        else:
            self._panel.raise_()
            self._panel.activateWindow()


# ===========================================================================
# Plugin registration (called by PluginManager.load_all_plugins)
# ===========================================================================

def initialize(plugin_manager) -> bool:
    """
    Register the STDP plugin with the PluginManager.
    The PluginManager will later call instance.setup(pm, tamagotchi_logic).
    """
    plugin_key = PLUGIN_NAME.lower()

    if plugin_key in plugin_manager.plugins:
        if hasattr(plugin_manager, 'logger'):
            plugin_manager.logger.warning(
                f"{PLUGIN_NAME} is already registered. Skipping."
            )
        return True

    try:
        instance = STDPPlugin()
        instance.plugin_manager = plugin_manager

        plugin_manager.plugins[plugin_key] = {
            'instance':            instance,
            'name':                PLUGIN_NAME,
            'version':             PLUGIN_VERSION,
            'author':              PLUGIN_AUTHOR,
            'description':         PLUGIN_DESCRIPTION,
            'requires':            PLUGIN_REQUIRES,
            'is_setup':            False,
            'is_enabled_by_default': True,
        }

        print(f"⚡ {PLUGIN_NAME} v{PLUGIN_VERSION} by {PLUGIN_AUTHOR} registered.")
        return True

    except Exception as exc:
        if hasattr(plugin_manager, 'logger'):
            plugin_manager.logger.error(
                f"Failed to initialize {PLUGIN_NAME}: {exc}"
            )
        traceback.print_exc()
        return False
