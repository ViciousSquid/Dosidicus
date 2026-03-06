"""
STDP Control Panel

A dockable dialog for tuning STDP parameters and optionally recording
spike and directional-encoding logs to disk.

Log files
---------
spikes_YYYYMMDD_HHMMSS.csv   – one row per detected spike
    timestamp, neuron, activation, was_rising, is_burst

encoding_YYYYMMDD_HHMMSS.csv – one row per Hebbian+STDP pair update
    timestamp, pre, post, hebbian_delta, stdp_delta, combined_delta,
    direction, ltp_ltd, stdp_weight
"""

import os
import csv
import time
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from PyQt5 import QtCore, QtGui, QtWidgets

if TYPE_CHECKING:
    from .main import STDPPlugin


# ── palette ────────────────────────────────────────────────────────────────
_BG       = "#0f1923"
_SURFACE  = "#16232f"
_BORDER   = "#1e3448"
_ACCENT   = "#00bcd4"
_ACCENT2  = "#7c4dff"
_TEXT     = "#cfd8dc"
_TEXT_DIM = "#546e7a"
_LTP      = "#00e676"
_LTD      = "#ff5252"
_WARN     = "#ffc107"


_PANEL_STYLE = f"""
QDialog {{
    background: {_BG};
    color: {_TEXT};
    font-family: "Consolas", "Courier New", monospace;
}}
QGroupBox {{
    background: {_SURFACE};
    border: 1px solid {_BORDER};
    border-radius: 6px;
    margin-top: 10px;
    padding: 8px;
    color: {_ACCENT};
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1px;
    text-transform: uppercase;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
}}
QLabel {{
    color: {_TEXT};
    font-size: 12px;
    background: transparent;
}}
QLabel#dim {{
    color: {_TEXT_DIM};
    font-size: 11px;
}}
QLabel#ltp {{
    color: {_LTP};
    font-weight: bold;
}}
QLabel#ltd {{
    color: {_LTD};
    font-weight: bold;
}}
QLabel#accent {{
    color: {_ACCENT};
    font-weight: bold;
}}
QSlider::groove:horizontal {{
    height: 4px;
    background: {_BORDER};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
    background: {_ACCENT};
}}
QSlider::sub-page:horizontal {{
    background: {_ACCENT};
    border-radius: 2px;
}}
QCheckBox {{
    color: {_TEXT};
    spacing: 8px;
    font-size: 12px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 1px solid {_BORDER};
    background: {_SURFACE};
}}
QCheckBox::indicator:checked {{
    background: {_ACCENT};
    border-color: {_ACCENT};
    image: none;
}}
QPushButton {{
    background: {_SURFACE};
    color: {_TEXT};
    border: 1px solid {_BORDER};
    border-radius: 5px;
    padding: 6px 14px;
    font-size: 12px;
    font-family: "Consolas", "Courier New", monospace;
}}
QPushButton:hover {{
    background: {_BORDER};
    border-color: {_ACCENT};
    color: {_ACCENT};
}}
QPushButton:pressed {{
    background: {_ACCENT};
    color: {_BG};
}}
QPushButton#danger {{
    border-color: {_LTD};
    color: {_LTD};
}}
QPushButton#danger:hover {{
    background: {_LTD};
    color: {_BG};
}}
QPushButton#export {{
    border-color: {_LTP};
    color: {_LTP};
}}
QPushButton#export:hover {{
    background: {_LTP};
    color: {_BG};
}}
QLineEdit {{
    background: {_SURFACE};
    color: {_TEXT};
    border: 1px solid {_BORDER};
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 11px;
    font-family: "Consolas", "Courier New", monospace;
}}
QScrollBar:vertical {{
    background: {_BG};
    width: 8px;
}}
QScrollBar::handle:vertical {{
    background: {_BORDER};
    border-radius: 4px;
    min-height: 20px;
}}
QFrame#separator {{
    color: {_BORDER};
}}
"""


class _Slider(QtWidgets.QWidget):
    """Label + slider + value label in one row."""
    valueChanged = QtCore.pyqtSignal(float)

    def __init__(self, label: str, min_val: float, max_val: float,
                 value: float, decimals: int = 2, parent=None):
        super().__init__(parent)
        self._scale = 10 ** decimals
        self._decimals = decimals

        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        lbl = QtWidgets.QLabel(label)
        lbl.setFixedWidth(130)
        row.addWidget(lbl)

        self._slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self._slider.setRange(int(min_val * self._scale),
                              int(max_val * self._scale))
        self._slider.setValue(int(value * self._scale))
        row.addWidget(self._slider, 1)

        self._val_lbl = QtWidgets.QLabel(f"{value:.{decimals}f}")
        self._val_lbl.setFixedWidth(46)
        self._val_lbl.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self._val_lbl.setObjectName("accent")
        row.addWidget(self._val_lbl)

        self._slider.valueChanged.connect(self._on_change)

    def _on_change(self, raw: int):
        v = raw / self._scale
        self._val_lbl.setText(f"{v:.{self._decimals}f}")
        self.valueChanged.emit(v)

    def value(self) -> float:
        return self._slider.value() / self._scale

    def setValue(self, v: float):
        self._slider.setValue(int(v * self._scale))


class STDPControlPanel(QtWidgets.QDialog):
    """
    Floating control panel for the STDP plugin.
    """

    def __init__(self, plugin: "STDPPlugin", parent=None):
        super().__init__(parent)
        self.plugin = plugin
        self.setWindowTitle("STDP Control Panel")
        self.setWindowFlags(
            QtCore.Qt.Window |
            QtCore.Qt.WindowCloseButtonHint |
            QtCore.Qt.WindowMinimizeButtonHint
        )
        self.setMinimumWidth(520)
        self.setStyleSheet(_PANEL_STYLE)

        # Logging state
        self._logging_active    = False
        self._log_dir           = self._default_log_dir()
        self._spike_writer      = None
        self._spike_file        = None
        self._encoding_writer   = None
        self._encoding_file     = None
        self._spike_count       = 0
        self._encoding_count    = 0

        # Connect to plugin's logging hooks
        self.plugin._panel = self

        self._build_ui()

        # Refresh stats every 2 s
        self._refresh_timer = QtCore.QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_stats)
        self._refresh_timer.start(2000)

    # ── UI construction ────────────────────────────────────────────────────

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(14, 14, 14, 14)

        # Title bar
        title = QtWidgets.QLabel("⚡  STDP CONTROL PANEL")
        title.setStyleSheet(f"color:{_ACCENT}; font-size:14px; font-weight:bold;"
                            f" letter-spacing:2px;")
        root.addWidget(title)

        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.HLine)
        sep.setObjectName("separator")
        root.addWidget(sep)

        # ── Parameters ──────────────────────────────────────────────────
        params_grp = QtWidgets.QGroupBox("Parameters")
        params_lay = QtWidgets.QVBoxLayout(params_grp)
        params_lay.setSpacing(8)

        cfg = self.plugin.config

        self._w_blend = _Slider("STDP blend",   0.0, 1.0, cfg.stdp_weight,    2)
        self._w_taup  = _Slider("τ+ (LTP)",     0.02, 1.0, cfg.tau_plus,      2)
        self._w_taum  = _Slider("τ− (LTD)",     0.02, 1.0, cfg.tau_minus,     2)
        self._w_aplus = _Slider("A+ amplitude", 0.01, 0.3, cfg.A_plus,        3)
        self._w_aminus= _Slider("A− amplitude", 0.01, 0.3, cfg.A_minus,       3)
        self._w_win   = _Slider("Time window",  0.1,  2.0, cfg.time_window,   2)
        self._w_thr   = _Slider("Spike thresh", 20.0, 90.0, cfg.spike_threshold, 1)

        for w in (self._w_blend, self._w_taup, self._w_taum,
                  self._w_aplus, self._w_aminus, self._w_win, self._w_thr):
            params_lay.addWidget(w)

        self._w_blend .valueChanged.connect(lambda v: self.plugin.set_stdp_weight(v))
        self._w_taup  .valueChanged.connect(lambda v: self._set_cfg('tau_plus', v))
        self._w_taum  .valueChanged.connect(lambda v: self._set_cfg('tau_minus', v))
        self._w_aplus .valueChanged.connect(lambda v: self._set_cfg('A_plus', v))
        self._w_aminus.valueChanged.connect(lambda v: self._set_cfg('A_minus', v))
        self._w_win   .valueChanged.connect(lambda v: self._set_cfg('time_window', v))
        self._w_thr   .valueChanged.connect(lambda v: self._set_cfg('spike_threshold', v))

        root.addWidget(params_grp)

        # ── Live stats ───────────────────────────────────────────────────
        stats_grp = QtWidgets.QGroupBox("Live Statistics")
        stats_grid = QtWidgets.QGridLayout(stats_grp)
        stats_grid.setSpacing(6)

        def _stat_row(grid, row, name):
            lbl = QtWidgets.QLabel(name)
            lbl.setObjectName("dim")
            val = QtWidgets.QLabel("—")
            grid.addWidget(lbl, row, 0)
            grid.addWidget(val, row, 1, QtCore.Qt.AlignRight)
            return val

        self._s_ltp      = _stat_row(stats_grid, 0, "LTP events")
        self._s_ltp.setObjectName("ltp")
        self._s_ltd      = _stat_row(stats_grid, 1, "LTD events")
        self._s_ltd.setObjectName("ltd")
        self._s_spikes   = _stat_row(stats_grid, 2, "Total spikes")
        self._s_neurons  = _stat_row(stats_grid, 3, "Tracked neurons")
        self._s_bursting = _stat_row(stats_grid, 4, "Bursting now")
        self._s_traces   = _stat_row(stats_grid, 5, "Eligibility traces")

        reset_btn = QtWidgets.QPushButton("Reset counters")
        reset_btn.setObjectName("danger")
        reset_btn.clicked.connect(self._reset_stats)
        stats_grid.addWidget(reset_btn, 6, 0, 1, 2)

        root.addWidget(stats_grp)

        # ── Logging ──────────────────────────────────────────────────────
        log_grp = QtWidgets.QGroupBox("Data Export")
        log_lay = QtWidgets.QVBoxLayout(log_grp)
        log_lay.setSpacing(8)

        # What to log
        self._chk_spikes   = QtWidgets.QCheckBox("Log spike events  (spikes_*.csv)")
        self._chk_encoding = QtWidgets.QCheckBox("Log directional encoding  (encoding_*.csv)")
        self._chk_spikes.setChecked(True)
        self._chk_encoding.setChecked(True)
        log_lay.addWidget(self._chk_spikes)
        log_lay.addWidget(self._chk_encoding)

        # Output directory
        dir_row = QtWidgets.QHBoxLayout()
        dir_row.setSpacing(6)
        dir_lbl = QtWidgets.QLabel("Output dir:")
        dir_lbl.setObjectName("dim")
        self._dir_edit = QtWidgets.QLineEdit(self._log_dir)
        browse_btn = QtWidgets.QPushButton("…")
        browse_btn.setFixedWidth(32)
        browse_btn.clicked.connect(self._browse_dir)
        dir_row.addWidget(dir_lbl)
        dir_row.addWidget(self._dir_edit, 1)
        dir_row.addWidget(browse_btn)
        log_lay.addLayout(dir_row)

        # Start / stop
        btn_row = QtWidgets.QHBoxLayout()
        self._start_btn = QtWidgets.QPushButton("▶  Start logging")
        self._start_btn.setObjectName("export")
        self._start_btn.clicked.connect(self._toggle_logging)
        self._export_now_btn = QtWidgets.QPushButton("⬇  Export snapshot now")
        self._export_now_btn.clicked.connect(self._export_snapshot)
        btn_row.addWidget(self._start_btn)
        btn_row.addWidget(self._export_now_btn)
        log_lay.addLayout(btn_row)

        # Status line
        self._log_status = QtWidgets.QLabel("Logging inactive")
        self._log_status.setObjectName("dim")
        self._log_status.setAlignment(QtCore.Qt.AlignCenter)
        log_lay.addWidget(self._log_status)

        root.addWidget(log_grp)

        # ── Close ────────────────────────────────────────────────────────
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.close)
        root.addWidget(close_btn, alignment=QtCore.Qt.AlignRight)

        self._refresh_stats()

    # ── Config helpers ─────────────────────────────────────────────────────

    def _set_cfg(self, attr: str, value: float):
        setattr(self.plugin.config, attr, value)
        if self.plugin.stdp_learner:
            setattr(self.plugin.stdp_learner.config, attr, value)

    def _reset_stats(self):
        self.plugin.reset_stats()
        self._spike_count    = 0
        self._encoding_count = 0
        self._refresh_stats()

    # ── Stats refresh ──────────────────────────────────────────────────────

    def _refresh_stats(self):
        stats = self.plugin.get_stats()
        ss    = stats.get('spike_stats', {})
        self._s_ltp     .setText(str(stats.get('ltp_events', 0)))
        self._s_ltd     .setText(str(stats.get('ltd_events', 0)))
        self._s_spikes  .setText(str(ss.get('total_spikes', 0)))
        self._s_neurons .setText(str(ss.get('tracked_neurons', 0)))
        self._s_bursting.setText(str(ss.get('bursting_neurons', 0)))
        self._s_traces  .setText(str(stats.get('active_eligibility_traces', 0)))

        if self._logging_active:
            self._log_status.setText(
                f"● Recording  —  "
                f"spikes: {self._spike_count}  |  "
                f"pairs: {self._encoding_count}"
            )
            self._log_status.setStyleSheet(f"color:{_LTP}; font-size:11px;")

    # ── Directory browse ───────────────────────────────────────────────────

    def _browse_dir(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select output directory", self._dir_edit.text()
        )
        if d:
            self._dir_edit.setText(d)

    # ── Continuous logging toggle ──────────────────────────────────────────

    def _toggle_logging(self):
        if not self._logging_active:
            self._start_logging()
        else:
            self._stop_logging()

    def _start_logging(self):
        self._log_dir = self._dir_edit.text().strip() or self._default_log_dir()
        os.makedirs(self._log_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        if self._chk_spikes.isChecked():
            path = os.path.join(self._log_dir, f"spikes_{ts}.csv")
            self._spike_file = open(path, 'w', newline='', encoding='utf-8')
            self._spike_writer = csv.writer(self._spike_file)
            self._spike_writer.writerow(
                ["timestamp", "neuron", "activation", "was_rising", "is_burst"]
            )

        if self._chk_encoding.isChecked():
            path = os.path.join(self._log_dir, f"encoding_{ts}.csv")
            self._encoding_file = open(path, 'w', newline='', encoding='utf-8')
            self._encoding_writer = csv.writer(self._encoding_file)
            self._encoding_writer.writerow([
                "timestamp", "pre", "post",
                "hebbian_delta", "stdp_delta", "combined_delta",
                "direction", "ltp_ltd", "stdp_weight"
            ])

        self._logging_active = True
        self._spike_count    = 0
        self._encoding_count = 0
        self._start_btn.setText("■  Stop logging")
        self._start_btn.setObjectName("danger")
        self._start_btn.setStyleSheet(
            f"border-color:{_LTD}; color:{_LTD};"
            f"background:{_SURFACE}; border-radius:5px; padding:6px 14px;"
        )
        self._log_status.setText("● Recording …")
        self._log_status.setStyleSheet(f"color:{_LTP}; font-size:11px;")
        print(f"⚡ STDP logging started → {self._log_dir}")

    def _stop_logging(self):
        self._logging_active = False
        for f in (self._spike_file, self._encoding_file):
            if f:
                try:
                    f.close()
                except Exception:
                    pass
        self._spike_file      = None
        self._encoding_file   = None
        self._spike_writer    = None
        self._encoding_writer = None
        self._start_btn.setText("▶  Start logging")
        self._start_btn.setObjectName("export")
        self._start_btn.setStyleSheet("")   # revert to stylesheet default
        self._log_status.setText(
            f"Stopped.  Wrote {self._spike_count} spike rows, "
            f"{self._encoding_count} encoding rows."
        )
        self._log_status.setStyleSheet(f"color:{_TEXT_DIM}; font-size:11px;")
        print(f"⚡ STDP logging stopped — "
              f"{self._spike_count} spikes, {self._encoding_count} pairs written.")

    # ── Snapshot export ────────────────────────────────────────────────────

    def _export_snapshot(self):
        """Export a one-shot CSV of current spike history and recent pairs."""
        log_dir = self._dir_edit.text().strip() or self._default_log_dir()
        os.makedirs(log_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        learner = self.plugin.stdp_learner
        if learner is None:
            QtWidgets.QMessageBox.warning(self, "STDP", "Plugin not active.")
            return

        written = []

        # Spikes snapshot
        spike_path = os.path.join(log_dir, f"snapshot_spikes_{ts}.csv")
        with open(spike_path, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(["neuron", "timestamp", "activation", "was_rising"])
            tracker = learner.spike_tracker
            with __import__('PyQt5.QtCore', fromlist=['QMutexLocker']).QMutexLocker(tracker._mutex):
                for name, history in tracker._spike_history.items():
                    for spike in history:
                        w.writerow([
                            name,
                            f"{spike.timestamp:.4f}",
                            f"{spike.activation_level:.2f}",
                            spike.was_rising,
                        ])
        written.append(spike_path)

        # Eligibility traces snapshot (best proxy for recent directional encoding)
        enc_path = os.path.join(log_dir, f"snapshot_encoding_{ts}.csv")
        with open(enc_path, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(["pre", "post", "eligibility_trace", "last_update"])
            with __import__('PyQt5.QtCore', fromlist=['QMutexLocker']).QMutexLocker(learner._mutex):
                for (pre, post), (trace, t) in learner._eligibility_traces.items():
                    w.writerow([pre, post, f"{trace:.4f}", f"{t:.4f}"])
        written.append(enc_path)

        msg = "Exported:\n" + "\n".join(written)
        QtWidgets.QMessageBox.information(self, "STDP snapshot saved", msg)
        print(f"⚡ STDP snapshot exported → {log_dir}")

    # ── Called by plugin to record events ─────────────────────────────────

    def record_spike(self, neuron: str, activation: float,
                     was_rising: bool, is_burst: bool):
        """Called from the spike sampling timer in the plugin."""
        if not self._logging_active or self._spike_writer is None:
            return
        self._spike_writer.writerow([
            f"{time.time():.4f}", neuron, f"{activation:.2f}",
            was_rising, is_burst
        ])
        self._spike_count += 1
        # Flush periodically so the file is readable while recording
        if self._spike_count % 50 == 0:
            self._spike_file.flush()

    def record_encoding(self, pre: str, post: str,
                        hebbian_delta: float, stdp_delta: float,
                        combined_delta: float, direction: str,
                        stdp_weight: float):
        """Called from _run_stdp_hebbian after each pair update."""
        if not self._logging_active or self._encoding_writer is None:
            return
        ltp_ltd = ("LTP" if stdp_delta > 0 else
                   "LTD" if stdp_delta < 0 else "neutral")
        self._encoding_writer.writerow([
            f"{time.time():.4f}", pre, post,
            f"{hebbian_delta:.5f}", f"{stdp_delta:.5f}", f"{combined_delta:.5f}",
            direction, ltp_ltd, f"{stdp_weight:.2f}"
        ])
        self._encoding_count += 1
        if self._encoding_count % 20 == 0:
            self._encoding_file.flush()

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _default_log_dir() -> str:
        return os.path.join(os.getcwd(), "logs", "stdp")

    def closeEvent(self, event):
        if self._logging_active:
            self._stop_logging()
        self._refresh_timer.stop()
        # Detach panel reference from plugin
        if hasattr(self.plugin, '_panel') and self.plugin._panel is self:
            self.plugin._panel = None
        super().closeEvent(event)
