"""
Sleep Replay – Control Panel

A small dockable dialog for inspecting the experience buffer, tuning the
replay / pruning parameters at runtime, and triggering a consolidation pass
on demand (useful for demos – you don't have to wait for the squid to sleep).
"""

import os
import sys

from PyQt5 import QtCore, QtWidgets

try:
    from display_scaling import DisplayScaling
except ImportError:  # pragma: no cover
    class DisplayScaling:
        @classmethod
        def font_size(cls, size):
            return size

        @classmethod
        def scale(cls, size):
            return size


class SleepReplayControlPanel(QtWidgets.QWidget):
    """Runtime controls + live stats for the Sleep Replay plugin."""

    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        self.plugin = plugin
        self.setWindowTitle("Sleep Replay & Consolidation")
        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.WindowStaysOnTopHint)
        self.resize(DisplayScaling.scale(420), DisplayScaling.scale(520))
        self._build_ui()

        self._refresh_timer = QtCore.QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_stats)
        self._refresh_timer.start(1000)
        self._refresh_stats()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.setStyleSheet("""
            QWidget { background-color: #10181f; color: #d7f0f2; }
            QLabel#title { font-size: 17px; font-weight: 700; color: #e6fbfd; }
            QLabel#subtitle { color: #83b4bc; }
            QGroupBox {
                border: 1px solid #2f6f7a; border-radius: 8px;
                margin-top: 10px; padding: 10px; font-weight: 600;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
            QLabel#stat { font-family: 'Consolas','Courier New',monospace; color: #7fd4c1; }
            QPushButton {
                background-color: #1d3b44; border: 1px solid #2f6f7a;
                border-radius: 6px; padding: 7px 12px; color: #d7f0f2;
            }
            QPushButton:hover { background-color: #24505c; }
            QPushButton:disabled { color: #55707a; border-color: #24404a; }
        """)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # Header
        header = QtWidgets.QVBoxLayout()
        header.setSpacing(2)
        title = QtWidgets.QLabel("🌙  Sleep Replay & Consolidation")
        title.setObjectName("title")
        header.addWidget(title)
        subtitle = QtWidgets.QLabel(
            "The day's strongest co-activations are replayed during sleep; "
            "weak synapses are pruned.")
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        header.addWidget(subtitle)
        root.addLayout(header)

        # Enabled toggle
        self.enabled_check = QtWidgets.QCheckBox("Plugin enabled")
        self.enabled_check.setChecked(self.plugin.enabled)
        self.enabled_check.toggled.connect(self.plugin.set_enabled)
        root.addWidget(self.enabled_check)

        # --- Live stats ---
        stats_box = QtWidgets.QGroupBox("Live state")
        stats_layout = QtWidgets.QVBoxLayout(stats_box)
        self.stat_labels = {}
        for key, label in [
            ('phase', 'Phase'),
            ('buffer_size', 'Buffer (tracked pairs)'),
            ('samples_today', 'Samples today'),
            ('peak_score', 'Peak co-activation'),
            ('days_completed', 'Sleeps consolidated'),
            ('total_replayed', 'Total strengthened'),
            ('total_pruned', 'Total pruned'),
            ('last_replay_pairs', 'Last sleep: replayed'),
            ('last_pruned', 'Last sleep: pruned'),
        ]:
            row = QtWidgets.QHBoxLayout()
            name = QtWidgets.QLabel(label)
            value = QtWidgets.QLabel("—")
            value.setObjectName("stat")
            value.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            row.addWidget(name)
            row.addStretch()
            row.addWidget(value)
            stats_layout.addLayout(row)
            self.stat_labels[key] = value
        root.addWidget(stats_box)

        # --- Tuning ---
        tune_box = QtWidgets.QGroupBox("Tuning")
        tune_layout = QtWidgets.QVBoxLayout(tune_box)

        cfg = self.plugin.config
        self.top_k_spin = self._add_int_row(
            tune_layout, "Experiences replayed (top-k)", 1, 30, cfg.replay_top_k,
            self._on_top_k)
        self.cycles_spin = self._add_int_row(
            tune_layout, "Ripple bursts per sleep", 1, 12, cfg.replay_cycles,
            self._on_cycles)
        self.strength_spin = self._add_double_row(
            tune_layout, "Replay strength", 0.01, 0.30, cfg.replay_strength, 0.01,
            self._on_strength)
        self.prune_spin = self._add_double_row(
            tune_layout, "Prune threshold |w|", 0.0, 0.30, cfg.prune_threshold, 0.01,
            self._on_prune_threshold)
        self.prune_check = QtWidgets.QCheckBox("Prune weak synapses during sleep")
        self.prune_check.setChecked(cfg.prune_enabled)
        self.prune_check.toggled.connect(self._on_prune_toggle)
        tune_layout.addWidget(self.prune_check)
        root.addWidget(tune_box)

        # --- Actions ---
        actions = QtWidgets.QHBoxLayout()
        self.replay_btn = QtWidgets.QPushButton("🌙  Replay now")
        self.replay_btn.clicked.connect(self.plugin.force_replay_now)
        actions.addWidget(self.replay_btn)
        clear_btn = QtWidgets.QPushButton("Clear buffer")
        clear_btn.clicked.connect(self.plugin.clear_buffer)
        actions.addWidget(clear_btn)
        root.addLayout(actions)

        root.addStretch()

    def _add_int_row(self, layout, label, lo, hi, val, cb):
        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel(label))
        row.addStretch()
        spin = QtWidgets.QSpinBox()
        spin.setRange(lo, hi)
        spin.setValue(int(val))
        spin.valueChanged.connect(cb)
        row.addWidget(spin)
        layout.addLayout(row)
        return spin

    def _add_double_row(self, layout, label, lo, hi, val, step, cb):
        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel(label))
        row.addStretch()
        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(lo, hi)
        spin.setSingleStep(step)
        spin.setDecimals(3)
        spin.setValue(float(val))
        spin.valueChanged.connect(cb)
        row.addWidget(spin)
        layout.addLayout(row)
        return spin

    # ------------------------------------------------------------------
    # Config callbacks
    # ------------------------------------------------------------------

    def _on_top_k(self, v):
        self.plugin.config.replay_top_k = int(v)

    def _on_cycles(self, v):
        self.plugin.config.replay_cycles = int(v)

    def _on_strength(self, v):
        self.plugin.config.replay_strength = float(v)

    def _on_prune_threshold(self, v):
        self.plugin.config.prune_threshold = float(v)

    def _on_prune_toggle(self, checked):
        self.plugin.config.prune_enabled = bool(checked)

    # ------------------------------------------------------------------
    # Stats refresh
    # ------------------------------------------------------------------

    def _refresh_stats(self):
        try:
            s = self.plugin.get_stats()
        except Exception:
            return
        phase = "💤 replaying" if s.get('replaying') else (
            "asleep" if s.get('asleep') else "awake")
        self.stat_labels['phase'].setText(phase)
        for key in ('buffer_size', 'samples_today', 'peak_score', 'days_completed',
                    'total_replayed', 'total_pruned', 'last_replay_pairs',
                    'last_pruned'):
            if key in self.stat_labels:
                self.stat_labels[key].setText(str(s.get(key, '—')))
        self.replay_btn.setEnabled(bool(s.get('enabled')) and not s.get('replaying'))
        if self.enabled_check.isChecked() != bool(s.get('enabled')):
            self.enabled_check.blockSignals(True)
            self.enabled_check.setChecked(bool(s.get('enabled')))
            self.enabled_check.blockSignals(False)

    def closeEvent(self, event):
        self._refresh_timer.stop()
        super().closeEvent(event)
