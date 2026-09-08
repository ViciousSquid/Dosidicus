"""
Sleep Replay & Consolidation plugin - a control surface, not a second engine.

Sleep-dependent replay is a CORE feature. It lives in
src/sleep_consolidation.py (the algorithm) and src/consolidation.py (the
engine-side owner), it runs on every simulation tick from
TamagotchiLogic.update_simulation, and it consolidates the squid's day whether
this plugin is loaded or not.

This plugin used to be a complete parallel implementation: its own
SleepReplayEngine, its own sampling timer, its own sleep-edge detection, its
own replay bursts and its own pruning pass, all mutating brain_widget.weights
directly. With the core manager also running, two engines sampled the same
brain, built two different experience buffers, and both strengthened and pruned
the same synapses - and neither recorded why.

What is left is the part that was always the plugin's job: showing the player
what consolidation is doing, and letting them drive it.

  * live view of the buffer, the night's replay and the pruning
  * "Replay Now" to force a consolidation pass while awake
  * runtime tuning of the real ReplayConfig the engine reads
  * a status banner on the Learning tab

Enabling and disabling this plugin shows and hides the inspector; the
"Consolidation runs during sleep" toggle is the one that turns the core
feature itself on and off.
"""

import os
import sys
import logging
import traceback
from typing import Optional, Dict

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

# The engine's own config type - the plugin edits the live instance of it,
# and only falls back to a detached default before the brain window exists.
try:
    from src.sleep_consolidation import ReplayConfig
except ImportError:  # pragma: no cover
    from sleep_consolidation import ReplayConfig

# ---------------------------------------------------------------------------
# Plugin metadata
# ---------------------------------------------------------------------------
PLUGIN_NAME        = "Sleep Replay"
PLUGIN_VERSION     = "2.0.0"
PLUGIN_AUTHOR      = "ViciousSquid"
PLUGIN_DESCRIPTION = ("Inspector and controls for the engine's core sleep replay "
                      "and synaptic consolidation")
PLUGIN_REQUIRES    = []


class SleepReplayPlugin:
    """A window onto the engine's own sleep consolidation."""

    def __init__(self):
        self.logger: Optional[logging.Logger] = None
        self.plugin_manager = None
        self.tamagotchi_logic = None

        self._brain_widget = None
        self._brain_window = None
        self._resolve_attempts = 0
        self._fallback_config = ReplayConfig()

        self._banner_timer: Optional[QtCore.QTimer] = None
        self._ui_banner: Optional[QtWidgets.QWidget] = None
        self._banner_stats_label: Optional[QtWidgets.QLabel] = None
        self._panel = None

        self.is_setup = False
        self.enabled = False

    # =====================================================================
    # The core objects this panel is a view of
    # =====================================================================
    @property
    def consolidation(self):
        """The engine's one ConsolidationManager."""
        return getattr(self._brain_widget, 'consolidation', None)

    @property
    def engine(self):
        """The engine's one SleepReplayEngine."""
        manager = self.consolidation
        return getattr(manager, 'engine', None) if manager is not None else None

    @property
    def config(self) -> ReplayConfig:
        """The live ReplayConfig - editing it changes what the squid does."""
        engine = self.engine
        cfg = getattr(engine, 'config', None) if engine is not None else None
        return cfg if cfg is not None else self._fallback_config

    @property
    def consolidation_active(self) -> bool:
        manager = self.consolidation
        return bool(getattr(manager, 'enabled', False)) if manager is not None else False

    # =====================================================================
    # Lifecycle
    # =====================================================================
    def setup(self, plugin_manager, tamagotchi_logic) -> bool:
        self.plugin_manager = plugin_manager
        self.tamagotchi_logic = tamagotchi_logic

        if hasattr(plugin_manager, 'logger'):
            self.logger = plugin_manager.logger.getChild(PLUGIN_NAME.replace(' ', ''))
        else:  # pragma: no cover
            self.logger = logging.getLogger(PLUGIN_NAME)
            self.logger.setLevel(logging.INFO)

        self.logger.info(f"Setting up {PLUGIN_NAME} v{PLUGIN_VERSION}...")

        plugin_key = PLUGIN_NAME.lower()
        plugin_data = plugin_manager.plugins.get(plugin_key, {})
        self.enabled = plugin_data.get('is_enabled_by_default', True)

        self._resolve_brain_references()

        self.is_setup = True
        if self.enabled:
            QtCore.QTimer.singleShot(1200, self._inject_ui_banner)

        self._print_banner()
        return True

    def cleanup(self):
        if self.logger:
            self.logger.info(f"{PLUGIN_NAME}: cleanup called")
        try:
            if self._banner_timer:
                self._banner_timer.stop()
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
                f"References resolved: watching {type(self.consolidation).__name__}"
            )
            return True

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
    # Public API (used by control panel and menu)
    # =====================================================================
    def force_replay_now(self):
        """Ask the engine to consolidate now, awake or asleep."""
        manager = self.consolidation
        if manager is None:
            print("🌙 No brain to consolidate yet.")
            return
        if not manager.enabled:
            print("🌙 Consolidation is switched off - turn it back on first.")
            return
        summary = manager.force_consolidation()
        if summary is None:
            print("🌙 Not enough experience buffered yet to replay.")
        else:
            print(f"🌙 Manual consolidation: replayed {summary.get('replayed', 0)}, "
                  f"pruned {summary.get('pruned', 0)}.")
        self._refresh_banner_stats()

    def clear_buffer(self):
        manager = self.consolidation
        if manager is not None:
            manager.clear_buffer()
            print("🌙 Experience buffer cleared.")
        self._refresh_banner_stats()

    def get_stats(self) -> dict:
        manager = self.consolidation
        if manager is None:
            return {'enabled': False, 'buffer_size': 0, 'samples_today': 0,
                    'total_replayed': 0, 'total_pruned': 0}
        try:
            stats = manager.get_stats()
        except Exception:
            stats = {}
        squid = self._get_squid()
        stats['enabled'] = manager.enabled
        stats['asleep'] = bool(getattr(squid, 'is_sleeping', False))
        stats['replaying'] = manager.is_replaying
        return stats

    def set_consolidation_active(self, active: bool):
        """Turn the core sleep-consolidation feature on or off."""
        manager = self.consolidation
        if manager is not None:
            manager.enabled = bool(active)
        print(f"🌙 Sleep consolidation {'enabled' if active else 'disabled'} in the engine")

    # =====================================================================
    # Enable / disable (the inspector, not the feature)
    # =====================================================================
    def enable(self):
        self.set_enabled(True)
        return True

    def disable(self):
        self.set_enabled(False)
        return True

    def set_enabled(self, enabled: bool):
        self.enabled = bool(enabled)
        if self.logger:
            self.logger.info(
                f"Sleep Replay inspector {'shown' if enabled else 'hidden'} "
                f"(consolidation itself is unaffected)")
        if enabled:
            if self._ui_banner is None:
                QtCore.QTimer.singleShot(0, self._inject_ui_banner)
            else:
                self._ui_banner.setVisible(True)
        elif self._ui_banner is not None:
            self._ui_banner.setVisible(False)

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
            s = self.get_stats()
            phase = "💤 replaying" if s.get('replaying') else (
                "asleep" if s.get('asleep') else "awake")
            if not s.get('enabled', True):
                phase = "switched off"
            self._banner_stats_label.setText(
                f"{phase} · buffer {s.get('buffer_size', 0)} · "
                f"today {s.get('samples_today', 0)} · "
                f"replayed {s.get('total_replayed', 0)} · "
                f"pruned {s.get('total_pruned', 0)} · "
                f"nights {s.get('nights_completed', 0)}"
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

        core_action = QtWidgets.QAction("Consolidation runs during sleep", main_window)
        core_action.setCheckable(True)
        core_action.setChecked(self.consolidation_active)
        core_action.toggled.connect(self.set_consolidation_active)
        menu.addAction(core_action)

        toggle_action = QtWidgets.QAction("Show inspector", main_window)
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
        print("  🌙  SLEEP REPLAY INSPECTOR  🌙")
        print("=" * 60)
        print("  Consolidation is part of the engine, not this plugin.")
        print("  This plugin shows you what it is doing and lets you drive it.")
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
