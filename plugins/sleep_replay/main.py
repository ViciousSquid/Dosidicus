"""
Sleep Replay & Consolidation Plugin for Dosidicus
=================================================

Turns sleep from a stat-restore into a cognitively load-bearing phase.

While the squid is awake, the plugin quietly records which neurons fire together
(a recency-weighted "experience buffer", biased by the memories the squid forms).
When the squid falls asleep, the day's strongest co-activations are **replayed**
in a series of bursts – their connections are strengthened, the analogue of
hippocampal sharp-wave-ripple consolidation. Sleep then **prunes** weak, unused
synapses (the synaptic-homeostasis hypothesis), so the connectome reflects what
actually mattered instead of only ever growing.

Integration
-----------
Purely additive – no core files are modified. The plugin:
  * polls ``squid.is_sleeping`` on a main-thread timer to detect sleep/wake edges
    (robust to every sleep path, including forced sleep at 100% sleepiness, which
    fires no hook);
  * samples ``brain_widget.state`` while awake to accumulate co-activation;
  * mutates ``brain_widget.weights`` on the main thread during sleep (same pattern
    the STDP plugin uses for reward modulation) and drives the existing weight
    animations;
  * reuses the brain widget's own connector / new-neuron immunity for pruning.

All heavy lifting lives in ``replay_core.py`` (Qt-free, unit-testable).
"""

import os
import sys
import time
import logging
import traceback
from collections import deque
from typing import Optional, Dict, List

# ---------------------------------------------------------------------------
# Make the project root importable (mirrors the STDP / multiplayer plugins)
# ---------------------------------------------------------------------------
try:
    _current_dir = os.path.dirname(os.path.abspath(__file__))
    _project_root = os.path.abspath(os.path.join(_current_dir, '..', '..'))
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)
except Exception as _e:  # pragma: no cover
    print(f"Sleep Replay Plugin: sys.path setup warning: {_e}")

from PyQt5 import QtCore, QtWidgets

try:
    from display_scaling import DisplayScaling
except ImportError:  # pragma: no cover - fallback when scaling helper absent
    class DisplayScaling:
        @classmethod
        def font_size(cls, size):
            return size

        @classmethod
        def scale(cls, size):
            return size

        @classmethod
        def scale_css(cls, css):
            return css

# Core engine (package-relative, with flat fallback)
try:
    from .replay_core import ReplayConfig, SleepReplayEngine
except ImportError:  # pragma: no cover
    from replay_core import ReplayConfig, SleepReplayEngine

# ---------------------------------------------------------------------------
# Plugin metadata
# ---------------------------------------------------------------------------
PLUGIN_NAME        = "Sleep Replay"
PLUGIN_VERSION     = "1.0.0"
PLUGIN_AUTHOR      = "ViciousSquid"
PLUGIN_DESCRIPTION = ("Replays the day's strongest co-activations during sleep to "
                      "consolidate them, and prunes weak unused synapses")
PLUGIN_REQUIRES    = []

# Sensor neurons that receive external input – never learned on or pruned.
PURE_INPUTS = {
    "can_see_food", "is_eating", "is_sleeping", "is_sick",
    "pursuing_food", "is_fleeing", "is_startled", "external_stimulus",
    "plant_proximity", "threat_level",
}


class SleepReplayPlugin:
    """Sleep-dependent replay, consolidation and synaptic pruning."""

    def __init__(self):
        self.logger: Optional[logging.Logger] = None
        self.plugin_manager = None
        self.tamagotchi_logic = None

        # Resolved during setup()
        self._brain_widget = None
        self._brain_window = None

        # Engine
        self.config = ReplayConfig()
        self.engine = SleepReplayEngine(self.config)

        # Timers (all main-thread)
        self._sample_timer: Optional[QtCore.QTimer] = None
        self._sleep_timer: Optional[QtCore.QTimer] = None
        self._replay_timer: Optional[QtCore.QTimer] = None
        self._banner_timer: Optional[QtCore.QTimer] = None
        self._resolve_attempts = 0

        # Sleep-edge state machine
        self._asleep = False
        self._session = None
        self._replay_running = False
        self._pending_prune = False
        self._session_replayed = 0
        self._last_pruned = 0

        # Memory-harvest dedupe
        self._seen_memories: deque = deque(maxlen=256)
        self._seen_memory_set: set = set()

        # UI
        self._ui_banner: Optional[QtWidgets.QWidget] = None
        self._banner_stats_label: Optional[QtWidgets.QLabel] = None
        self._panel = None

        self.is_setup = False
        self.enabled = False

    # =====================================================================
    # Lifecycle
    # =====================================================================

    def setup(self, plugin_manager, tamagotchi_logic) -> bool:
        self.plugin_manager = plugin_manager
        self.tamagotchi_logic = tamagotchi_logic

        # Logger
        if hasattr(plugin_manager, 'logger'):
            self.logger = plugin_manager.logger.getChild(PLUGIN_NAME.replace(' ', ''))
        else:  # pragma: no cover
            self.logger = logging.getLogger(PLUGIN_NAME)
            self.logger.setLevel(logging.INFO)

        self.logger.info(f"Setting up {PLUGIN_NAME} v{PLUGIN_VERSION}...")

        # Read the default-enabled flag from the registry (set in initialize()).
        plugin_key = PLUGIN_NAME.lower()
        plugin_data = plugin_manager.plugins.get(plugin_key, {})
        self.enabled = plugin_data.get('is_enabled_by_default', True)

        # Resolve brain references (retries if the brain window isn't ready yet).
        self._resolve_brain_references()

        # Awake co-activation sampling
        self._sample_timer = QtCore.QTimer()
        self._sample_timer.timeout.connect(self._sample_tick)
        self._sample_timer.start(self.config_sample_interval_ms())

        # Sleep/wake edge detection
        self._sleep_timer = QtCore.QTimer()
        self._sleep_timer.timeout.connect(self._sleep_tick)
        self._sleep_timer.start(500)

        # Replay burst driver (started/stopped per sleep episode)
        self._replay_timer = QtCore.QTimer()
        self._replay_timer.timeout.connect(self._replay_cycle)

        # Also subscribe to the on_sleep hook as a prompt (idempotent with polling)
        self._subscribe_hooks()

        self.is_setup = True

        if self.enabled:
            QtCore.QTimer.singleShot(1200, self._inject_ui_banner)

        self._print_banner()
        return True

    def config_sample_interval_ms(self) -> int:
        # Sampling cadence is independent of sim speed so the "day" is wall-clock.
        return 650

    def cleanup(self):
        if self.logger:
            self.logger.info(f"{PLUGIN_NAME}: cleanup called")
        for t in (self._sample_timer, self._sleep_timer,
                  self._replay_timer, self._banner_timer):
            try:
                if t:
                    t.stop()
            except Exception:
                pass
        if self._panel is not None:
            try:
                self._panel.close()
            except Exception:
                pass
            self._panel = None
        self._remove_ui_banner()
        self.is_setup = False

    def shutdown(self):
        self.cleanup()

    # =====================================================================
    # Reference resolution
    # =====================================================================

    def _resolve_brain_references(self) -> bool:
        tl = self.tamagotchi_logic
        brain_window = getattr(tl, 'brain_window', None) if tl else None
        if brain_window is None and self.plugin_manager is not None:
            brain_window = getattr(self.plugin_manager, 'brain_window', None)

        if brain_window is not None:
            self._brain_window = brain_window
            self._brain_widget = getattr(brain_window, 'brain_widget', None)

        if self._brain_widget is not None:
            self.logger.info(
                f"References resolved: widget={type(self._brain_widget).__name__}"
            )
            return True

        # Not ready yet – retry a handful of times, then give up quietly.
        self._resolve_attempts += 1
        if self._resolve_attempts <= 20:
            QtCore.QTimer.singleShot(750, self._resolve_brain_references)
        else:
            self.logger.warning("Could not resolve brain_widget after retries.")
        return False

    def _get_squid(self):
        tl = self.tamagotchi_logic
        return getattr(tl, 'squid', None) if tl else None

    def _nn_viz_tab(self):
        bw = self._brain_window
        return getattr(bw, 'nn_viz_tab', None) if bw else None

    # =====================================================================
    # Awake: co-activation sampling
    # =====================================================================

    def _sample_tick(self):
        if not self.enabled or self._brain_widget is None:
            return
        squid = self._get_squid()
        if squid is None:
            return
        # Only accumulate experience while awake.
        if getattr(squid, 'is_sleeping', False):
            return

        active = self._learnable_state()
        if len(active) >= 2:
            self.engine.record_sample(active)

        # Fold in any newly-formed memories before sleep clears them.
        self._harvest_new_memories(squid)

    def _learnable_state(self) -> Dict[str, float]:
        """Filtered view of the brain state: real, learnable neuron activations."""
        bw = self._brain_widget
        state = getattr(bw, 'state', None)
        if not state:
            return {}
        excluded = getattr(bw, 'excluded_neurons', set()) or set()
        out: Dict[str, float] = {}
        for name, val in state.items():
            if name in PURE_INPUTS or name in excluded:
                continue
            if isinstance(val, bool):
                continue
            if not isinstance(val, (int, float)):
                continue
            try:
                if bw.is_connector_neuron(name):
                    continue
            except Exception:
                pass
            out[name] = float(val)
        return out

    def _harvest_new_memories(self, squid):
        mm = getattr(squid, 'memory_manager', None)
        if mm is None or not hasattr(mm, 'get_all_short_term_memories'):
            return
        try:
            mems = mm.get_all_short_term_memories(raw=True)
        except Exception:
            return
        fresh = []
        for m in mems or []:
            try:
                sig = (m.get('category'), m.get('key'), m.get('timestamp'))
            except Exception:
                continue
            if sig in self._seen_memory_set:
                continue
            self._seen_memory_set.add(sig)
            self._seen_memories.append(sig)
            # Keep the dedupe set bounded alongside the deque.
            while len(self._seen_memory_set) > self._seen_memories.maxlen:
                old = self._seen_memories.popleft()
                self._seen_memory_set.discard(old)
            fresh.append(m)
        if fresh:
            self.engine.harvest_memory(fresh)

    # =====================================================================
    # Sleep/wake edge detection
    # =====================================================================

    def _sleep_tick(self):
        if not self.enabled:
            return
        squid = self._get_squid()
        if squid is None:
            return
        sleeping = bool(getattr(squid, 'is_sleeping', False))
        if sleeping and not self._asleep:
            self._asleep = True
            self._on_sleep_onset()
        elif not sleeping and self._asleep:
            self._asleep = False
            self._on_wake()

    def _on_sleep_hook(self, **kwargs):
        """on_sleep hook – prompt an immediate edge check (idempotent)."""
        QtCore.QTimer.singleShot(0, self._sleep_tick)

    def _on_sleep_onset(self):
        if self._brain_widget is None:
            return
        if not self.engine.has_enough_to_replay():
            self.logger.info("Sleep onset – not enough experience to replay yet.")
            return
        self._start_replay(manual=False)

    def _on_wake(self):
        # If a replay was still in flight when the squid woke, wrap it up.
        if self._replay_running:
            self._finish_replay()
        stats = self.engine.get_stats()
        self.logger.info(
            f"Wake – day complete. Replayed {stats['last_replay_pairs']} pair(s), "
            f"pruned {stats['last_pruned']}."
        )
        self._refresh_banner_stats()

    # =====================================================================
    # Replay
    # =====================================================================

    def _start_replay(self, manual: bool = False):
        if self._replay_running:
            return
        session = self.engine.build_session()
        if not session.cycles:
            self.logger.info("Replay: nothing salient to consolidate.")
            return
        self._session = session
        self._replay_running = True
        self._session_replayed = 0

        n_sel = len(session.selected)
        tag = " (manual)" if manual else ""
        print(f"\n🌙 Sleep replay{tag}: consolidating {n_sel} experience(s) "
              f"over {session.total_cycles} ripple burst(s)...")
        self.logger.info(f"Replay session started: {n_sel} pairs, "
                         f"{session.total_cycles} cycles.")

        # Kick the first burst immediately, then space the rest out.
        self._replay_timer.start(self._replay_cycle_interval_ms())
        self._replay_cycle()

    def _replay_cycle_interval_ms(self) -> int:
        return 1400

    def _replay_cycle(self):
        if self._session is None:
            self._replay_timer.stop()
            self._replay_running = False
            return

        batch = self._session.next_cycle()
        if batch is None:
            # All bursts done – prune, then finish.
            self._replay_timer.stop()
            self._do_prune()
            self._finish_replay()
            return

        applied = 0
        nn_tab = self._nn_viz_tab()
        for item in batch:
            if self._apply_replay_item(item):
                applied += 1
                self._session_replayed += 1
                if nn_tab is not None and hasattr(nn_tab, 'add_log_entry'):
                    try:
                        nn_tab.add_log_entry("", item.pair, "increase", stdp_meta=None)
                    except Exception:
                        pass

        # Make the consolidation visible in the network view.
        try:
            self._brain_widget.mark_render_dirty()
            self._brain_widget.update()
        except Exception:
            pass

        cyc = self._session.cycles_done
        print(f"   🌙 ripple {cyc}/{self._session.total_cycles}: "
              f"strengthened {applied} connection(s)")

    def _apply_replay_item(self, item) -> bool:
        """Strengthen one connection on the main thread. Returns True if changed."""
        bw = self._brain_widget
        weights = getattr(bw, 'weights', None)
        if weights is None:
            return False

        a, b = item.pair
        pair = (a, b)
        rev = (b, a)
        use = pair if pair in weights else (rev if rev in weights else None)

        if use is None:
            if not self.config.create_missing_connections:
                return False
            positions = getattr(bw, 'neuron_positions', {})
            if a not in positions or b not in positions:
                return False
            # Respect the same connector degree limit as update_connection().
            try:
                if bw.is_connector_neuron(a) and bw.get_neuron_degree(a) >= 3:
                    return False
                if bw.is_connector_neuron(b) and bw.get_neuron_degree(b) >= 3:
                    return False
            except Exception:
                pass
            weights[pair] = 0.0
            use = pair

        old_w = weights[use]
        new_w = max(-1.0, min(1.0, old_w + item.delta))
        if new_w == old_w:
            return False
        weights[use] = new_w

        try:
            bw.add_weight_animation(use[0], use[1], old_w, new_w)
        except Exception:
            pass
        return True

    def _do_prune(self):
        bw = self._brain_widget
        weights = getattr(bw, 'weights', None)
        if weights is None:
            return
        # Honour the core pruning switch too – if the user disabled pruning
        # globally, don't prune here either.
        if not getattr(bw, 'pruning_enabled', True):
            return

        prunes = self.engine.plan_prune(weights, self._is_immune)
        removed = 0
        for pair in prunes:
            if pair in weights:
                del weights[pair]
                removed += 1

        downs = self.engine.plan_downscale(weights, self._is_immune)
        for pair, new_w in downs.items():
            if pair in weights:
                weights[pair] = new_w

        if removed or downs:
            print(f"   ✂️  sleep pruning: removed {removed} weak synapse(s)"
                  + (f", down-scaled {len(downs)}" if downs else ""))
            try:
                bw.mark_render_dirty()
                bw.update()
            except Exception:
                pass
        self._last_pruned = removed

    def _is_immune(self, n1: str, n2: str) -> bool:
        """Connections spared from pruning: connectors, pure inputs, immature."""
        if n1 in PURE_INPUTS or n2 in PURE_INPUTS:
            return True
        bw = self._brain_widget
        try:
            if bw.is_connector_neuron(n1) or bw.is_connector_neuron(n2):
                return True
        except Exception:
            pass
        try:
            age = self.config.prune_min_age_sec
            if bw.is_new_neuron(n1, age) or bw.is_new_neuron(n2, age):
                return True
        except Exception:
            pass
        return False

    def _finish_replay(self):
        pruned = getattr(self, '_last_pruned', 0)
        cycles = self._session.total_cycles if self._session else 0
        self.engine.finish_day(self._session_replayed, pruned, cycles)

        # Push the consolidated weights to the worker cache so the change sticks.
        try:
            if hasattr(self._brain_widget, '_update_worker_cache'):
                self._brain_widget._update_worker_cache()
        except Exception:
            pass

        stats = self.engine.get_stats()
        print(f"🌙 Consolidation complete: {self._session_replayed} strengthened, "
              f"{pruned} pruned. (day #{stats['days_completed']})\n")

        self._session = None
        self._replay_running = False
        self._last_pruned = 0
        self._refresh_banner_stats()

    # =====================================================================
    # Public API (used by control panel)
    # =====================================================================

    def force_replay_now(self):
        """Trigger a consolidation pass on demand (works even while awake)."""
        if not self.enabled:
            print("🌙 Sleep Replay is disabled – enable it first.")
            return
        if self._brain_widget is None:
            return
        if not self.engine.has_enough_to_replay():
            print("🌙 Not enough experience buffered yet to replay.")
            return
        self._start_replay(manual=True)

    def clear_buffer(self):
        self.engine.tracker.clear()
        self._refresh_banner_stats()
        print("🌙 Experience buffer cleared.")

    def get_stats(self) -> dict:
        stats = self.engine.get_stats()
        stats['enabled'] = self.enabled
        stats['asleep'] = self._asleep
        stats['replaying'] = self._replay_running
        return stats

    # =====================================================================
    # Enable / disable
    # =====================================================================

    def enable(self):
        self.set_enabled(True)
        return True

    def disable(self):
        self.set_enabled(False)
        return True

    def set_enabled(self, enabled: bool):
        self.enabled = bool(enabled)
        status = "enabled" if enabled else "disabled"
        if self.logger:
            self.logger.info(f"Sleep Replay {status}")
        print(f"🌙 Sleep Replay {status}")
        if enabled:
            if self._ui_banner is None:
                QtCore.QTimer.singleShot(0, self._inject_ui_banner)
            else:
                self._ui_banner.setVisible(True)
        else:
            if self._replay_running:
                self._replay_timer.stop()
                self._replay_running = False
                self._session = None
            if self._ui_banner is not None:
                self._ui_banner.setVisible(False)

    # =====================================================================
    # Hooks
    # =====================================================================

    def _subscribe_hooks(self):
        pm = self.plugin_manager
        if pm is None or not hasattr(pm, 'subscribe_to_hook'):
            return
        try:
            pm.subscribe_to_hook("on_sleep", PLUGIN_NAME, self._on_sleep_hook)
        except Exception as exc:
            if self.logger:
                self.logger.warning(f"Could not subscribe to on_sleep: {exc}")

    # =====================================================================
    # UI: Learning-tab banner
    # =====================================================================

    def _inject_ui_banner(self):
        if not self.enabled or self._ui_banner is not None:
            return
        try:
            nn_viz_tab = self._nn_viz_tab()
            if nn_viz_tab is None:
                return
            layout = getattr(nn_viz_tab, 'learning_content_layout', None)
            if layout is None:
                return

            # Idempotent: the app reloads plugins at startup (load_all_plugins
            # replaces instances), so setup()/_inject can run more than once.
            # Sweep any existing Sleep Replay banner(s) out of the shared Learning
            # tab first so we never stack duplicates.
            if self._banner_timer is not None:
                self._banner_timer.stop()
            for _old in nn_viz_tab.findChildren(QtWidgets.QWidget, "sleep_replay_banner"):
                _old.setParent(None)
                _old.deleteLater()
            self._ui_banner = None
            self._banner_stats_label = None

            banner = QtWidgets.QWidget()
            banner.setObjectName("sleep_replay_banner")
            banner.setStyleSheet("""
                QWidget#sleep_replay_banner {
                    background: qlineargradient(
                        x1:0, y1:0, x2:1, y2:0,
                        stop:0 #1a2740, stop:1 #14343a
                    );
                    border-radius: 10px;
                    border: 2px solid #2f6f7a;
                }
            """)

            row = QtWidgets.QHBoxLayout(banner)
            row.setContentsMargins(16, 12, 16, 12)
            row.setSpacing(12)

            icon = QtWidgets.QLabel("🌙")
            icon.setStyleSheet(
                f"font-size: {DisplayScaling.font_size(26)}px; background: transparent;")
            row.addWidget(icon)

            text_col = QtWidgets.QVBoxLayout()
            text_col.setSpacing(2)
            title = QtWidgets.QLabel("Sleep Replay & Consolidation")
            title.setStyleSheet(
                f"font-size: {DisplayScaling.font_size(15)}px; font-weight: 700; "
                f"color: #d7f0f2; background: transparent;")
            text_col.addWidget(title)
            detail = QtWidgets.QLabel(
                "Co-active experiences replay during sleep · weak synapses pruned")
            detail.setStyleSheet(
                f"font-size: {DisplayScaling.font_size(12)}px; color: #83b4bc; "
                f"background: transparent;")
            text_col.addWidget(detail)
            row.addLayout(text_col)
            row.addStretch()

            self._banner_stats_label = QtWidgets.QLabel("buffer — · replayed —")
            self._banner_stats_label.setStyleSheet(
                f"font-size: {DisplayScaling.font_size(12)}px; font-weight: 600; "
                f"color: #7fd4c1; background: transparent;")
            row.addWidget(self._banner_stats_label)

            layout.insertWidget(0, banner)
            self._ui_banner = banner

            self._banner_timer = QtCore.QTimer()
            self._banner_timer.timeout.connect(self._refresh_banner_stats)
            self._banner_timer.start(3000)

            self.logger.info("Sleep Replay banner injected into Learning tab")
        except Exception as exc:
            if self.logger:
                self.logger.warning(f"Could not inject UI banner: {exc}")

    def _refresh_banner_stats(self):
        if self._ui_banner is None or self._banner_stats_label is None:
            return
        try:
            s = self.engine.get_stats()
            phase = "💤 replaying" if self._replay_running else (
                "asleep" if self._asleep else "awake")
            self._banner_stats_label.setText(
                f"{phase} · buffer {s['buffer_size']} · "
                f"today {s['samples_today']} · "
                f"replayed {s['total_replayed']} · pruned {s['total_pruned']}"
            )
        except RuntimeError:
            # Banner was swept by a reloaded instance – stop this stale timer.
            if self._banner_timer is not None:
                self._banner_timer.stop()
        except Exception:
            pass

    def _remove_ui_banner(self):
        if self._ui_banner is not None:
            try:
                self._ui_banner.setParent(None)
                self._ui_banner.deleteLater()
            except Exception:
                pass
            self._ui_banner = None
            self._banner_stats_label = None

    # =====================================================================
    # Menu integration
    # =====================================================================

    def register_menu_actions(self, main_window, menu):
        panel_action = QtWidgets.QAction("Control Panel…", main_window)
        panel_action.triggered.connect(lambda: self.show_control_panel(main_window))
        menu.addAction(panel_action)

        replay_action = QtWidgets.QAction("Replay Now", main_window)
        replay_action.triggered.connect(self.force_replay_now)
        menu.addAction(replay_action)

        menu.addSeparator()

        toggle_action = QtWidgets.QAction("Enabled", main_window)
        toggle_action.setCheckable(True)
        toggle_action.setChecked(self.enabled)
        toggle_action.toggled.connect(self.set_enabled)
        menu.addAction(toggle_action)

    def show_control_panel(self, parent=None):
        if self._panel is None or not self._panel.isVisible():
            try:
                from .replay_control_panel import SleepReplayControlPanel
            except ImportError:  # pragma: no cover
                from replay_control_panel import SleepReplayControlPanel
            self._panel = SleepReplayControlPanel(self, parent)
            self._panel.show()
        else:
            self._panel.raise_()
            self._panel.activateWindow()

    # =====================================================================
    # Console banner
    # =====================================================================

    def _print_banner(self):
        print("\n" + "=" * 60)
        if self.enabled:
            print("  🌙  SLEEP REPLAY & CONSOLIDATION IS ACTIVE  🌙")
        else:
            print("  🌙  Sleep Replay loaded (DISABLED – enable via Plugins menu)  🌙")
        print("=" * 60)
        print(f"  Replay      : top {self.config.replay_top_k} experiences "
              f"× {self.config.replay_cycles} ripple bursts")
        print(f"  Strength    : {self.config.replay_strength} (falloff "
              f"{self.config.replay_falloff})")
        print(f"  Pruning     : {'on' if self.config.prune_enabled else 'off'} "
              f"(|w| < {self.config.prune_threshold})")
        print("=" * 60)
        print("  The squid consolidates its day whenever it sleeps.")
        print("=" * 60 + "\n")


# ===========================================================================
# Plugin registration (called by PluginManager.load_all_plugins)
# ===========================================================================

def initialize(plugin_manager) -> bool:
    """Register the Sleep Replay plugin with the PluginManager."""
    plugin_key = PLUGIN_NAME.lower()

    if plugin_key in plugin_manager.plugins:
        if hasattr(plugin_manager, 'logger'):
            plugin_manager.logger.warning(f"{PLUGIN_NAME} already registered. Skipping.")
        return True

    try:
        instance = SleepReplayPlugin()
        instance.plugin_manager = plugin_manager

        plugin_manager.plugins[plugin_key] = {
            'instance': instance,
            'name': PLUGIN_NAME,
            'original_name': PLUGIN_NAME,
            'version': PLUGIN_VERSION,
            'author': PLUGIN_AUTHOR,
            'description': PLUGIN_DESCRIPTION,
            'requires': PLUGIN_REQUIRES,
            'is_setup': False,
            'is_enabled_by_default': True,
        }

        print(f"🌙 {PLUGIN_NAME} v{PLUGIN_VERSION} by {PLUGIN_AUTHOR} registered.")
        return True

    except Exception as exc:
        if hasattr(plugin_manager, 'logger'):
            plugin_manager.logger.error(f"Failed to initialize {PLUGIN_NAME}: {exc}")
        traceback.print_exc()
        return False
