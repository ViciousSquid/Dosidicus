"""
STDP plugin for Dosidicus - a control surface, not a learning system.

Spike-Timing-Dependent Plasticity is a CORE feature of the engine. It lives in
src/stdp.py, it is owned by src/plasticity.py, and it contributes to every
weight change the squid makes whether this plugin is loaded or not.

This plugin used to be the implementation: it monkey-patched
BrainWorker._perform_hebbian_learning on the live instance, ran its own copy of
the learning loop against a stale cache, kept its own STDPLearner, and wrote
brain_widget.weights directly for reward modulation. That meant the squid's
learning rule depended on whether a plugin happened to be enabled, two engines
could disagree about the same synapse, and nothing anywhere recorded why a
weight had moved.

What is left here is what a plugin should be: a window onto the core.

  * turn the spike-timing term of the core rule on and off
  * adjust the Hebbian/STDP blend
  * watch spikes, LTP/LTD events and eligibility traces as they happen
  * a status banner on the Learning tab

Disabling the plugin no longer disables STDP - it hides the panel. Use the
"Spike timing contributes to learning" toggle for that; it sets
plasticity.config.stdp_enabled, which is the one switch the engine reads.
"""

import os
import sys
import logging
import traceback
from collections import deque
from typing import Optional, Dict

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

# ---------------------------------------------------------------------------
# Plugin metadata
# ---------------------------------------------------------------------------
PLUGIN_NAME        = "STDP"
PLUGIN_VERSION     = "2.0.0"
PLUGIN_AUTHOR      = "ViciousSquid"
PLUGIN_DESCRIPTION = "Inspector and controls for the engine's core spike-timing plasticity"
PLUGIN_REQUIRES    = []


class STDPPlugin:
    """A control surface over the engine's own STDP learner."""

    def __init__(self):
        self.logger: Optional[logging.Logger] = None
        self.plugin_manager = None
        self.tamagotchi_logic = None

        self._brain_widget = None
        self._fallback_config = None

        self._spike_timer: Optional[QtCore.QTimer] = None
        self._cleanup_timer: Optional[QtCore.QTimer] = None
        self._banner_update_timer: Optional[QtCore.QTimer] = None

        self._ui_banner: Optional[QtWidgets.QWidget] = None
        self._banner_stats_label: Optional[QtWidgets.QLabel] = None
        self._panel = None

        self._resolve_attempts = 0
        self._seen_keys = deque(maxlen=200)
        self._seen_key_set = set()
        self.is_setup = False
        self.enabled = False

    # =====================================================================
    # The core objects this panel is a view of
    # =====================================================================
    @property
    def _plasticity(self):
        return getattr(self._brain_widget, 'plasticity', None)

    @property
    def stdp_learner(self):
        """The engine's learner. There is exactly one, and this is it."""
        engine = self._plasticity
        return getattr(engine, 'stdp', None) if engine is not None else None

    @property
    def config(self):
        """The engine's STDP config - edits here change the real thing.

        Before the brain window exists there is nothing to point at, so the
        panel is handed a detached default rather than None; it is replaced by
        the live config as soon as the brain resolves.
        """
        learner = self.stdp_learner
        cfg = getattr(learner, 'config', None) if learner is not None else None
        if cfg is not None:
            return cfg
        if self._fallback_config is None:
            try:
                from src.stdp import STDPConfig
            except ImportError:
                from stdp import STDPConfig
            self._fallback_config = STDPConfig()
        return self._fallback_config

    @property
    def stdp_active(self) -> bool:
        engine = self._plasticity
        if engine is None:
            return False
        return bool(getattr(engine.config, 'stdp_enabled', False))

    # =====================================================================
    # Lifecycle
    # =====================================================================
    def setup(self, plugin_manager, tamagotchi_logic) -> bool:
        self.plugin_manager = plugin_manager
        self.tamagotchi_logic = tamagotchi_logic

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
        self._resolve_brain_references()

        # Watch the core learner's spikes so the panel can show them live.
        self._spike_timer = QtCore.QTimer()
        self._spike_timer.timeout.connect(self._sample_tick)
        self._spike_timer.start(150)

        self._cleanup_timer = QtCore.QTimer()
        self._cleanup_timer.timeout.connect(self._periodic_cleanup)
        self._cleanup_timer.start(10_000)

        self.is_setup = True

        plugin_key = PLUGIN_NAME.lower()
        plugin_data = plugin_manager.plugins.get(plugin_key, {})
        self.enabled = plugin_data.get('is_enabled_by_default', True)

        if self.enabled:
            QtCore.QTimer.singleShot(1200, self._inject_ui_banner)

        print("\n" + "=" * 64)
        print("  ⚡  STDP INSPECTOR  ⚡")
        print("=" * 64)
        print("  Spike-timing plasticity is part of the engine, not this plugin.")
        print(f"  Currently contributing : {self.stdp_active}")
        engine = self._plasticity
        if engine is not None:
            print(f"  Blend                  : "
                  f"{int((1 - engine.config.stdp_weight) * 100)}% Hebbian + "
                  f"{int(engine.config.stdp_weight * 100)}% spike timing")
        print("  This plugin shows you what it is doing and lets you tune it.")
        print("=" * 64 + "\n")
        return True

    def cleanup(self):
        if self.logger:
            self.logger.info(f"{PLUGIN_NAME}: cleanup called")
        for timer in (self._spike_timer, self._cleanup_timer,
                      self._banner_update_timer):
            try:
                if timer:
                    timer.stop()
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
            self._brain_widget = getattr(brain_window, 'brain_widget', None)

        if self._brain_widget is not None:
            self.logger.info("References resolved: the engine's own STDP learner "
                             f"is {type(self.stdp_learner).__name__}")
            return True

        self._resolve_attempts += 1
        if self._resolve_attempts <= 20:
            QtCore.QTimer.singleShot(750, self._resolve_brain_references)
        else:
            self.logger.warning("Could not resolve brain_widget after retries.")
        return False

    # =====================================================================
    # Live view of the core learner
    # =====================================================================
    def _sample_tick(self):
        """Mirror what the core learner has been doing into the panel.

        The plugin does NOT record spikes itself - PlasticityEngine.observe()
        already feeds every tick of the authoritative state to the learner. All
        this does is read what is there, so the panel and the brain can never
        disagree.
        """
        if not self.enabled or self._panel is None:
            return
        learner = self.stdp_learner
        if learner is None:
            return

        tracker = getattr(learner, 'spike_tracker', None)
        if tracker is None:
            return
        try:
            for neuron_name in list(getattr(tracker, '_spike_history', {}).keys()):
                spikes = tracker.get_recent_spikes(neuron_name, window=0.4)
                for spike in spikes[-2:]:
                    self._panel.record_spike(
                        neuron_name, spike.activation_level, spike.was_rising,
                        tracker.is_bursting(neuron_name))
        except Exception:
            pass

        # Encodings come from the ledger, so the panel shows the changes the
        # engine actually made rather than a parallel tally of its own.
        ledger = getattr(self._brain_widget, 'ledger', None)
        if ledger is None:
            return
        try:
            for event in ledger.recent_events(limit=25):
                stdp_delta = event.detail.get('stdp_delta')
                if not stdp_delta:
                    continue
                key = (round(event.timestamp, 4), event.edge)
                if key in self._seen_key_set:
                    continue
                if len(self._seen_keys) == self._seen_keys.maxlen:
                    self._seen_key_set.discard(self._seen_keys[0])
                self._seen_keys.append(key)
                self._seen_key_set.add(key)
                self._panel.record_encoding(
                    event.edge[0], event.edge[1],
                    event.detail.get('hebbian_delta', 0.0) or 0.0,
                    stdp_delta, event.delta,
                    event.detail.get('stdp_direction', 'none'),
                    event.detail.get('stdp_weight', 0.0) or 0.0)
        except Exception:
            pass

    def _periodic_cleanup(self):
        learner = self.stdp_learner
        if learner is not None:
            try:
                learner.cleanup()
            except Exception:
                pass

    # =====================================================================
    # Public API (used by the control panel)
    # =====================================================================
    def get_stats(self) -> dict:
        learner = self.stdp_learner
        if learner is None:
            return {'enabled': False}
        try:
            stats = learner.get_stats()
        except Exception:
            stats = {}
        engine = self._plasticity
        stats['enabled'] = self.stdp_active
        stats['stdp_weight'] = getattr(engine.config, 'stdp_weight', 0.0) if engine else 0.0
        return stats

    def set_stdp_weight(self, weight: float):
        """Change the real blend the engine uses."""
        weight = max(0.0, min(1.0, float(weight)))
        engine = self._plasticity
        if engine is not None:
            engine.config.stdp_weight = weight
        cfg = self.config
        if cfg is not None:
            cfg.stdp_weight = weight
        if self.logger:
            self.logger.info(f"STDP blend set to {weight:.2f} (engine config)")

    def set_stdp_active(self, active: bool):
        """Turn the spike-timing term of the core learning rule on or off."""
        engine = self._plasticity
        if engine is not None:
            engine.config.stdp_enabled = bool(active)
        print(f"⚡ Spike-timing contribution {'enabled' if active else 'disabled'} "
              f"in the core learning rule")

    def apply_reward(self, signal: float, reason: str = ""):
        """Deliver a reward through the engine's own three-factor channel."""
        bw = self._brain_widget
        if bw is None or not hasattr(bw, 'deliver_reward'):
            return 0
        return bw.deliver_reward(signal, reason or "manually delivered from the STDP panel")

    def reset_stats(self):
        learner = self.stdp_learner
        if learner is not None:
            try:
                learner.reset_stats()
            except Exception:
                pass

    def enable(self):
        self.set_enabled(True)
        return True

    def disable(self):
        self.set_enabled(False)
        return True

    def set_enabled(self, enabled: bool):
        """Show or hide the inspector. Does NOT disable the engine's STDP."""
        self.enabled = enabled
        if self.logger:
            self.logger.info(f"STDP inspector {'shown' if enabled else 'hidden'} "
                             f"(core spike-timing itself is unaffected)")
        if enabled:
            if self._ui_banner is None:
                QtCore.QTimer.singleShot(0, self._inject_ui_banner)
            else:
                self._ui_banner.setVisible(True)
        elif self._ui_banner is not None:
            self._ui_banner.setVisible(False)

    # =====================================================================
    # Learning-tab banner
    # =====================================================================
    def _nn_viz_tab(self):
        brain_window = getattr(self.tamagotchi_logic, 'brain_window', None)
        return getattr(brain_window, 'nn_viz_tab', None) if brain_window else None

    def _inject_ui_banner(self):
        if not self.enabled or self._ui_banner is not None:
            return
        try:
            tab = self._nn_viz_tab()
            if tab is None:
                return
            layout = getattr(tab, 'learning_content_layout', None)
            if layout is None:
                return

            banner = QtWidgets.QWidget()
            banner.setObjectName("stdp_banner")
            banner.setStyleSheet(f"""
                QWidget#stdp_banner {{
                    background-color: #e0f2f1;
                    border: 2px solid #80cbc4;
                    border-radius: 10px;
                }}
            """)
            row = QtWidgets.QVBoxLayout(banner)
            row.setContentsMargins(16, 10, 16, 10)

            title = QtWidgets.QLabel(
                f"<b style='font-size:{DisplayScaling.font_size(13)}px; color:#00695c;'>"
                f"⚡ Spike-timing plasticity (core engine)</b>")
            row.addWidget(title)

            self._banner_stats_label = QtWidgets.QLabel("waiting for spikes…")
            self._banner_stats_label.setStyleSheet(
                f"color:#00796b; font-size:{DisplayScaling.font_size(11)}px;")
            row.addWidget(self._banner_stats_label)

            layout.insertWidget(0, banner)
            self._ui_banner = banner

            self._banner_update_timer = QtCore.QTimer()
            self._banner_update_timer.timeout.connect(self._refresh_banner_stats)
            self._banner_update_timer.start(3000)
            self.logger.info("STDP banner injected into Learning tab")
        except Exception as exc:
            self.logger.warning(f"Could not inject UI banner: {exc}")

    def _refresh_banner_stats(self):
        if self._ui_banner is None or self._banner_stats_label is None:
            return
        try:
            stats = self.get_stats()
            ltp = stats.get('ltp_events', 0)
            ltd = stats.get('ltd_events', 0)
            spikes = stats.get('spike_stats', {}).get('total_spikes', 0)
            blend = stats.get('stdp_weight', 0.0)
            state = "contributing" if stats.get('enabled') else "switched off"
            self._banner_stats_label.setText(
                f"{state} · blend {int(blend * 100)}% · LTP {ltp} · LTD {ltd} · "
                f"spikes {spikes}")
        except RuntimeError:
            if self._banner_update_timer is not None:
                self._banner_update_timer.stop()
        except Exception:
            pass

    def _remove_ui_banner(self):
        if self._ui_banner is None:
            return
        try:
            self._ui_banner.setParent(None)
            self._ui_banner.deleteLater()
        except Exception:
            pass
        self._ui_banner = None
        self._banner_stats_label = None

    # =====================================================================
    # Plugin menu integration
    # =====================================================================
    def register_menu_actions(self, main_window: QtWidgets.QMainWindow,
                              menu: QtWidgets.QMenu):
        panel_action = QtWidgets.QAction("Control Panel…", main_window)
        panel_action.triggered.connect(lambda: self.show_control_panel(main_window))
        menu.addAction(panel_action)

        menu.addSeparator()

        core_action = QtWidgets.QAction("Spike timing contributes to learning", main_window)
        core_action.setCheckable(True)
        core_action.setChecked(self.stdp_active)
        core_action.toggled.connect(self.set_stdp_active)
        menu.addAction(core_action)

        toggle_action = QtWidgets.QAction("Show inspector", main_window)
        toggle_action.setCheckable(True)
        toggle_action.setChecked(self.enabled)
        toggle_action.toggled.connect(self.set_enabled)
        menu.addAction(toggle_action)

    def show_control_panel(self, parent=None):
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
# Plugin registration
# ===========================================================================
def initialize(plugin_manager) -> bool:
    plugin_key = PLUGIN_NAME.lower()

    if plugin_key in plugin_manager.plugins:
        if hasattr(plugin_manager, 'logger'):
            plugin_manager.logger.warning(f"{PLUGIN_NAME} is already registered. Skipping.")
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
            plugin_manager.logger.error(f"Failed to initialize {PLUGIN_NAME}: {exc}")
        traceback.print_exc()
        return False
