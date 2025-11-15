# 2.4.5.0 | rev2_nov25
#  --------------------------------------------------------------
#  Powerful all-in-one viewer + editor for every neuron, especially
#  those born via neurogenesis.  Excitatory vs inhibitory, beautiful
#  cards, live edit mode (locked by default), educational hints.
#  --------------------------------------------------------------

from PyQt5.QtCore import Qt, QTimer, pyqtSignal   # Qt now covers WindowMinMaxButtonsHint
from PyQt5 import QtCore
from PyQt5.QtGui import (
    QFont, QPixmap, QColor, QPainter, QBrush, QPen, QDoubleValidator
)
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFormLayout, QFrame,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QProgressBar,
    QPushButton, QScrollArea, QSlider, QSpinBox, QTabWidget, QTextEdit,
    QVBoxLayout, QWidget, QMessageBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QSplitter, QToolButton
)

import json, math, time, random, datetime as dt

# ------------------------------------------------------------------
#  Helper: coloured connection badge
# ------------------------------------------------------------------
def badge(text, color="#333", bg="#eee"):
    return f"""<span style="color:{color};background:{bg};
               padding:2px 6px;border-radius:4px;font-size:8pt;
               font-weight:600;">{text}</span>"""


# ------------------------------------------------------------------
#  Main Laboratory Dialog
# ------------------------------------------------------------------
class NeuronLaboratory(QDialog):
    def __init__(self, brain_widget, parent=None):
        super().__init__(parent)
        self.bw = brain_widget
        self.setWindowTitle("🧠  Neuron Laboratory")
        self.resize(900, 750)
        self.setWindowFlag(Qt.WindowMinMaxButtonsHint)

        # ---- top toolbar ----
        bar = QHBoxLayout()
        self.live_check = QCheckBox("Live refresh")
        self.live_check.setChecked(True)
        self.live_check.toggled.connect(self._toggle_live)
        bar.addWidget(self.live_check)

        bar.addStretch()
        self.lock_check = QCheckBox("🔓  Unlock editing")
        self.lock_check.toggled.connect(self._unlock_editing)
        bar.addWidget(self.lock_check)

        # ---- main notebook ----
        self.tabs = QTabWidget()
        self._build_overview_tab()
        self._build_inspector_tab()
        self._build_edit_tab()
        self._build_experience_buffer_tab()   #  <── NEW

        # ---- footer ----
        self.status_lbl = QLabel("Ready")
        self.status_lbl.setStyleSheet("color:#888;font-size:9pt;")

        lay = QVBoxLayout(self)
        lay.addLayout(bar)
        lay.addWidget(self.tabs)
        lay.addWidget(self.status_lbl)

        # ---- refresh timer ----
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh)
        self.timer.start(1000)  # 1 Hz

        self._refresh()  # first paint

        # ---- per-neuron manual lock table ----
        self.locked_neurons = {}   # name -> {locked: bool, slider, spin, button}

    # ================================================================
    #  NEW  –  Experience-Buffer tab
    # ================================================================
    def _build_experience_buffer_tab(self):
        """Fourth tab: full human-readable experience buffer + pattern table"""
        w = QWidget()
        lay = QVBoxLayout(w)

        splitter = QSplitter(Qt.Horizontal)

        # Left side: chronological experience log
        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.addWidget(QLabel("<b>Chronological experience log</b>  (last 50)"))
        self.exp_log_text = QTextEdit()
        self.exp_log_text.setReadOnly(True)
        left_lay.addWidget(self.exp_log_text)
        splitter.addWidget(left)

        # Right side: pattern-counter table
        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.addWidget(QLabel("<b>Pattern recurrence counts</b>"))
        self.pattern_table = QTableWidget()
        self.pattern_table.setColumnCount(2)
        self.pattern_table.setHorizontalHeaderLabels(["Pattern signature", "Count"])
        header = self.pattern_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        right_lay.addWidget(self.pattern_table)
        splitter.addWidget(right)

        lay.addWidget(splitter)

        # Buttons to manipulate buffer
        btn_bar = QHBoxLayout()
        btn_bar.addWidget(QLabel("Actions:"))
        self.clear_buffer_btn = QPushButton("Clear buffer")
        self.clear_buffer_btn.clicked.connect(self._clear_buffer)
        btn_bar.addWidget(self.clear_buffer_btn)

        self.inject_btn = QPushButton("Inject artificial experience")
        self.inject_btn.clicked.connect(self._inject_dummy)
        btn_bar.addWidget(self.inject_btn)

        btn_bar.addStretch()
        lay.addLayout(btn_bar)

        self.tabs.addTab(w, "🧾  Experience Buffer")

    # ----------  helpers for experience buffer ----------------------
    def _paint_experience_buffer(self):
        """Fill the new tab with human-readable data."""
        # 1.  Chronological log
        html = ""
        buffer = getattr(self.bw.enhanced_neurogenesis, 'experience_buffer', None)
        if buffer and buffer.buffer:
            for exp in reversed(buffer.buffer):   # newest first
                age = int(time.time() - exp.timestamp)
                html += f"<b>{age}s ago</b>  –  <b>{exp.trigger_type.upper()}</b>  –  outcome <b>{exp.outcome}</b><br>"
                html += f"Actions: {', '.join(exp.recent_actions) or 'none'}<br>"
                html += f"Environment: {exp.environmental_state}<br>"
                # top 3 active neurons
                top = sorted(exp.active_neurons.items(), key=lambda kv: abs(kv[1] - 50), reverse=True)[:3]
                html += "Top active: " + ", ".join(f"{n}({v:.0f})" for n, v in top) + "<br><br>"
        else:
            html = "No experiences recorded yet."
        self.exp_log_text.setHtml(html)

        # 2.  Pattern table
        self.pattern_table.setRowCount(0)
        if buffer and buffer.pattern_counts:
            for row, (pat, cnt) in enumerate(sorted(buffer.pattern_counts.items(),
                                                    key=lambda kv: kv[1], reverse=True)):
                self.pattern_table.insertRow(row)
                self.pattern_table.setItem(row, 0, QTableWidgetItem(pat))
                self.pattern_table.setItem(row, 1, QTableWidgetItem(str(cnt)))

    def _clear_buffer(self):
        buffer = getattr(self.bw.enhanced_neurogenesis, 'experience_buffer', None)
        if buffer:
            buffer.buffer.clear()
            buffer.pattern_counts.clear()
            self.status_lbl.setText("Experience buffer cleared")
            self._paint_experience_buffer()

    def _inject_dummy(self):
        """Inject a fake but valid experience (for quick testing)."""
        from .neurogenesis import ExperienceContext
        buffer = getattr(self.bw.enhanced_neurogenesis, 'experience_buffer', None)
        if not buffer:
            return
        fake = ExperienceContext(
            trigger_type='novelty',
            active_neurons={'curiosity': 85, 'anxiety': 20},
            recent_actions=['approach_plant', 'hide'],
            environmental_state={'plant': True, 'food_count': 0},
            outcome='positive',
            timestamp=time.time()
        )
        buffer.add_experience(fake)
        self.status_lbl.setText("Injected artificial novelty experience")
        self._paint_experience_buffer()

    # ================================================================
    #  Construction helpers (unchanged)
    # ================================================================
    def _build_overview_tab(self):
        self.ov_scroll = QScrollArea()
        self.ov_widget = QWidget()
        self.ov_grid = QGridLayout(self.ov_widget)
        self.ov_scroll.setWidget(self.ov_widget)
        self.ov_scroll.setWidgetResizable(True)
        self.tabs.addTab(self.ov_scroll, "📊  Live Overview")

    def _build_inspector_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        self.pick_neuron = QComboBox()
        self.pick_neuron.currentTextChanged.connect(self._inspect_neuron)
        lay.addWidget(QLabel("Pick a neuron to inspect:"))
        lay.addWidget(self.pick_neuron)
        self.inspector_scroll = QScrollArea()
        self.inspector_cards = QWidget()
        self.inspector_lay = QVBoxLayout(self.inspector_cards)
        self.inspector_scroll.setWidget(self.inspector_cards)
        self.inspector_scroll.setWidgetResizable(True)
        lay.addWidget(self.inspector_scroll, 1)
        self.tabs.addTab(w, "🔍  Deep Inspector")

    def _build_edit_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        warn = QLabel("⚠️  Editing is locked – check 'Unlock editing' in the toolbar.")
        warn.setStyleSheet("color:#d9534f;font-weight:bold;")
        lay.addWidget(warn)
        self.edit_warn = warn
        self.edit_scroll = QScrollArea()
        self.edit_cards = QWidget()
        self.edit_lay = QVBoxLayout(self.edit_cards)
        self.edit_scroll.setWidget(self.edit_cards)
        self.edit_scroll.setWidgetResizable(True)
        lay.addWidget(self.edit_scroll, 1)
        self.tabs.addTab(w, "🔧  Edit Sandbox")

    # ================================================================
    #  Live refresh (extended)
    # ================================================================
    def _refresh(self):
        if not self.live_check.isChecked():
            return
        current = self.pick_neuron.currentText()
        self.pick_neuron.clear()
        self.pick_neuron.addItems(sorted(self.bw.neuron_positions.keys()))
        idx = self.pick_neuron.findText(current)
        if idx >= 0:
            self.pick_neuron.setCurrentIndex(idx)
        self._paint_overview()
        self._paint_experience_buffer()   #  <── NEW
        self._inspect_neuron(self.pick_neuron.currentText())
        self._paint_edit()

    # ================================================================
    #  Overview / Inspector / Edit  (unchanged helpers)
    # ================================================================
    def _paint_overview(self):
        while self.ov_grid.count():
            item = self.ov_grid.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        nd = getattr(self.bw, 'neurogenesis_data', {})
        cfg = getattr(self.bw, 'neurogenesis_config', {})
        card1 = QGroupBox("Counter progress")
        card1.setStyleSheet("QGroupBox{font-weight:bold;}")
        g1 = QGridLayout(card1)
        metrics = [('Novelty', nd.get('novelty_counter', 0), cfg.get('novelty_threshold', 3)),
                   ('Stress', nd.get('stress_counter', 0), cfg.get('stress_threshold', .7)),
                   ('Reward', nd.get('reward_counter', 0), cfg.get('reward_threshold', .6))]
        for row, (name, cur, thr) in enumerate(metrics):
            pct = min(100, (cur / thr) * 100) if thr else 0
            bar = self._progress_bar(pct)
            g1.addWidget(QLabel(f"{name} <b>{cur:.2f}</b>/{thr}"), row, 0)
            g1.addWidget(bar, row, 1)
        self.ov_grid.addWidget(card1, 0, 0)
        card2 = QGroupBox("Newest neurogenesis neurons")
        card2.setStyleSheet("QGroupBox{font-weight:bold;}")
        v2 = QVBoxLayout(card2)
        details = nd.get('new_neurons_details', {})
        for name, info in sorted(details.items(), key=lambda x: x[1].get('created_at', 0), reverse=True)[:5]:
            age = int(time.time() - info.get('created_at', 0))
            v2.addWidget(QLabel(f"<b>{name}</b>  –  {info.get('trigger_type','?')}  –  {age}s ago"))
        if not details:
            v2.addWidget(QLabel("None yet"))
        self.ov_grid.addWidget(card2, 0, 1)
        card3 = QGroupBox("Limits & pruning")
        card3.setStyleSheet("QGroupBox{font-weight:bold;}")
        v3 = QVBoxLayout(card3)
        current = len(self.bw.neuron_positions) - len(self.bw.excluded_neurons)
        max_n = cfg.get('max_neurons', 32)
        v3.addWidget(self._progress_widget(f"Neurons", current, max_n))
        v3.addWidget(QLabel(f"Pruning enabled: <b>{self.bw.pruning_enabled}</b>"))
        self.ov_grid.addWidget(card3, 1, 0)
        card4 = QGroupBox("Quick actions")
        card4.setStyleSheet("QGroupBox{font-weight:bold;}")
        h = QHBoxLayout(card4)
        btn = QPushButton("Force Hebbian cycle")
        btn.clicked.connect(self.bw.perform_hebbian_learning)
        h.addWidget(btn)
        self.ov_grid.addWidget(card4, 1, 1)
        self.ov_grid.setRowStretch(2, 1)

    def _inspect_neuron(self, name):
        if not name:
            return
        while self.inspector_lay.count():
            item = self.inspector_lay.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        nd = getattr(self.bw, 'neurogenesis_data', {})
        details = nd.get('new_neurons_details', {}).get(name)
        card1 = QGroupBox("Identity & creation story")
        card1.setStyleSheet("QGroupBox{font-weight:bold;}")
        v1 = QVBoxLayout(card1)
        if details:
            age = int(time.time() - details.get('created_at', 0))
            v1.addWidget(QLabel(f"""
            <b>Neurogenesis neuron</b> created <b>{age}s</b> ago<br>
            Trigger: <b>{details.get('trigger_type','?')}</b>  (value {details.get('trigger_value_at_creation','?')})<br>
            Specialisation: <b>{details.get('specialisation','?')}</b>
            """))
            snap = details.get('associated_state_snapshot', {})
            if snap:
                v1.addWidget(QLabel("State snapshot at birth:"))
                txt = QTextEdit()
                txt.setPlainText(json.dumps(snap, indent=2))
                txt.setMaximumHeight(80)
                txt.setReadOnly(True)
                v1.addWidget(txt)
        else:
            v1.addWidget(QLabel("Core neuron – part of original brain"))
        self.inspector_lay.addWidget(card1)
        card2 = QGroupBox("Connections (excitatory vs inhibitory)")
        card2.setStyleSheet("QGroupBox{font-weight:bold;}")
        v2 = QVBoxLayout(card2)
        html = "<table width='100%'>"
        html += "<tr><th>Partner</th><th>Weight</th><th>Type</th><th>Influence</th></tr>"
        for (src, dst), w in self.bw.weights.items():
            if src == name:
                typ = "Excitatory" if w > 0 else "Inhibitory"
                col = "#d4ffd4" if w > 0 else "#ffd4d4"
                html += f"<tr bgcolor='{col}'>"
                html += f"<td>{dst}</td><td>{w:+.3f}</td><td>{badge(typ,'#000',col)}</td>"
                html += f"<td>{self._influence_badge(w)}</td></tr>"
        for (src, dst), w in self.bw.weights.items():
            if dst == name:
                typ = "Excitatory" if w > 0 else "Inhibitory"
                col = "#d4ffd4" if w > 0 else "#ffd4d4"
                html += f"<tr bgcolor='{col}'>"
                html += f"<td>{src} →</td><td>{w:+.3f}</td><td>{badge(typ,'#000',col)}</td>"
                html += f"<td>{self._influence_badge(w, incoming=True)}</td></tr>"
        html += "</table>"
        lbl = QLabel(html)
        lbl.setWordWrap(True)
        lbl.setTextFormat(QtCore.Qt.RichText)
        v2.addWidget(lbl)
        self.inspector_lay.addWidget(card2)
        card3 = QGroupBox("Functional impact simulation")
        card3.setStyleSheet("QGroupBox{font-weight:bold;}")
        v3 = QVBoxLayout(card3)
        impacts = self._compute_impacts(name)
        if impacts:
            html = "<table width='100%'>"
            html += "<tr><th>Neuron</th><th>Δ Value</th></tr>"
            for partner, delta in impacts.items():
                col = "#d4ffd4" if delta > 0 else "#ffd4d4"
                html += f"<tr bgcolor='{col}'><td>{partner}</td><td>{delta:+.2f}</td></tr>"
            html += "</table>"
            lbl = QLabel(html)
            lbl.setWordWrap(True)
            lbl.setTextFormat(QtCore.Qt.RichText)
            v3.addWidget(lbl)
        else:
            v3.addWidget(QLabel("No active connections at the moment"))
        self.inspector_lay.addWidget(card3)
        card4 = QGroupBox("Did you know?")
        card4.setStyleSheet("QGroupBox{font-weight:bold;}")
        v4 = QVBoxLayout(card4)
        v4.addWidget(QLabel(self._educational_tip(name)))
        self.inspector_lay.addWidget(card4)
        self.inspector_lay.addStretch(1)

    # ================================================================
    #  NEW  –  paint EDIT tab with individual pad-locks
    # ================================================================
    def _paint_edit(self):
        while self.edit_lay.count():
            item = self.edit_lay.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        if not self.lock_check.isChecked():
            return

        card = QGroupBox("Neuron values (drag to change)  –  click 🔒 to lock")
        card.setStyleSheet("QGroupBox{font-weight:bold;}")
        grid = QGridLayout(card)

        for row, name in enumerate(sorted(self.bw.neuron_positions.keys())):
            val = self.bw.state.get(name, 50)
            if isinstance(val, bool):
                continue

            # label
            grid.addWidget(QLabel(name), row, 0)

            # slider
            slider = QSlider(QtCore.Qt.Horizontal)
            slider.setRange(0, 100)
            slider.setValue(int(val))
            slider.valueChanged.connect(lambda v, n=name: self._set_neuron(n, v))
            grid.addWidget(slider, row, 1)

            # spin-box
            spin = QSpinBox()
            spin.setRange(0, 100)
            spin.setValue(int(val))
            spin.valueChanged.connect(lambda v, n=name: self._set_neuron(n, v))
            grid.addWidget(spin, row, 2)

            # pad-lock button
            btn = QToolButton()
            btn.setCheckable(True)
            btn.setText("🔓")          # unlocked by default
            btn.setFixedSize(24, 24)
            btn.setStyleSheet("QToolButton:checked { color: red; }")
            btn.toggled.connect(lambda checked, n=name, b=btn: self._toggle_lock(n, b))
            grid.addWidget(btn, row, 3)

            # store references
            self.locked_neurons[name] = {
                "locked": False,
                "slider": slider,
                "spin": spin,
                "button": btn
            }

        self.edit_lay.addWidget(card)
        self.edit_lay.addStretch(1)

    # -----------  lock / set slots  ---------------------------------
    def update_debug_info(self):
        """Public method to refresh the dialog - called from external code"""
        self._refresh()

    def _toggle_lock(self, name, button):
        self.locked_neurons[name]["locked"] = button.isChecked()
        button.setText("🔒" if button.isChecked() else "🔓")

    def _set_neuron(self, name, value):
        # when locked we *force* the value and clamp controls
        if self.locked_neurons[name]["locked"]:
            self.bw.state[name] = value
            self.locked_neurons[name]["slider"].setValue(value)
            self.locked_neurons[name]["spin"].setValue(value)
            self.bw.update()
        else:
            # normal free edit – will be overwritten by simulation next tick
            self.bw.state[name] = value
            self.bw.update()

    # ================================================================
    #  Slots
    # ================================================================
    def _toggle_live(self, on):
        self.timer.setInterval(1000 if on else 10000)

    def _unlock_editing(self, on):
        if on:
            ans = QMessageBox.question(self, "Unlock editing?",
                                     "You can now change neuron values and force creation events.  Use responsibly!")
            if ans != QMessageBox.Yes:
                self.lock_check.setChecked(False)
                return
        self.edit_warn.setVisible(not on)
        self._paint_edit()

    def _force_neurogenesis(self, typ):
        fake_state = {"_debug_forced_neurogenesis": True,
                      f"{typ}_exposure": 999}
        self.bw.update_state(fake_state)

    # ================================================================
    #  Pretty helpers
    # ================================================================
    def _progress_bar(self, pct):
        from PyQt5.QtWidgets import QProgressBar   # add this import
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(int(pct))
        bar.setTextVisible(True)
        bar.setStyleSheet("QProgressBar::chunk{background:#4CAF50;}")
        return bar

    def _progress_widget(self, title, cur, maxi):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(QLabel(f"{title}  {cur}/{maxi}"))
        bar = self._progress_bar((cur / maxi) * 100)
        bar.setMaximumHeight(12)
        h.addWidget(bar)
        return w

    def _influence_badge(self, w, incoming=False):
        mag = abs(w)
        if mag < 0.1:
            return badge("tiny", "#666", "#fff")
        if mag < 0.3:
            return badge("mild", "#fff", "#555")
        if mag < 0.6:
            return badge("moderate", "#fff", "#000")
        return badge("STRONG", "#fff", "#d9534f")

    def _compute_impacts(self, name):
        """Return dict partner→estimated delta if name activates"""
        impacts = {}
        val = self.bw.state.get(name, 50)
        if abs(val - 50) < 5:
            return impacts
        # outgoing
        for (src, dst), w in self.bw.weights.items():
            if src == name and dst not in self.bw.excluded_neurons:
                impacts[dst] = (val - 50) * w * 0.5
        return impacts

    def _educational_tip(self, name):
        tips = {
            "hunger": "Hunger is a homeostatic drive.  High hunger inhibits satisfaction and boosts anxiety.",
            "happiness": "Happiness is reinforced by reward neurons.  It inhibits anxiety and promotes curiosity.",
            "anxiety": "Anxiety is reduced by stress neurons (inhibitory).  High anxiety suppresses curiosity.",
            "curiosity": "Curiosity spikes when novelty is high.  It encourages exploration and reduces anxiety.",
        }
        if name in self.bw.original_neuron_positions:
            return tips.get(name, "Core neuron – fundamental to survival.")
        nd = getattr(self.bw, 'neurogenesis_data', {})
        det = nd.get('new_neurons_details', {}).get(name)
        if not det:
            return "Neurogenesis neuron – purpose inferred from birth context."
        return (f"Created by <b>{det.get('trigger_type')}</b> – specialises in "
                f"<b>{det.get('specialisation','?')}</b>.  "
                f"Its job is to turn experiences into long-term behaviour.")


# ------------------------------------------------------------------
#  Old name alias – drop-in compatibility
# ------------------------------------------------------------------
NeurogenesisDebugDialog = NeuronLaboratory


# ------------------------------------------------------------------
#  Quick test when run standalone
# ------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    # dummy brain-widget for test
    class DummyBW:
        neuron_positions = {"hunger": (100, 100), "happiness": (200, 100)}
        excluded_neurons = []
        state = {"hunger": 60, "happiness": 40}
        pruning_enabled = True
        weights = {("hunger", "happiness"): 0.75}
        neurogenesis_data = {
            "novelty_counter": 2.3,
            "stress_counter": 0.4,
            "reward_counter": 1.1,
            "new_neurons_details": {
                "novelty_0": {"trigger_type": "novelty", "created_at": time.time() - 120,
                              "specialisation": "object_investigation", "trigger_value_at_creation": 3.2,
                              "associated_state_snapshot": {"curiosity": 80}}
            },
            "last_neuron_time": time.time() - 300
        }
        neurogenesis_config = {"novelty_threshold": 3, "stress_threshold": 0.7, "reward_threshold": 0.6,
                               "max_neurons": 32, "cooldown": 180}

        # NEW: minimal dummy experience buffer so the tab shows something
        class DummyExpBuffer:
            def __init__(self):
                from collections import deque
                from .neurogenesis import ExperienceContext
                self.buffer = deque(maxlen=50)
                self.pattern_counts = {}
                # seed with one dummy
                dummy = ExperienceContext(
                    trigger_type='novelty',
                    active_neurons={'curiosity': 80, 'anxiety': 25},
                    recent_actions=['approach_plant'],
                    environmental_state={'plant': True, 'food_count': 0},
                    outcome='positive',
                    timestamp=time.time()
                )
                self.add_experience(dummy)

            def add_experience(self, ctx):
                self.buffer.append(ctx)
                pat = ctx.get_pattern_signature()
                self.pattern_counts[pat] = self.pattern_counts.get(pat, 0) + 1

        enhanced_neurogenesis = type('obj', (object,), {
            'experience_buffer': DummyExpBuffer()
        })()

        def perform_hebbian_learning(self):
            print("Hebbian cycle triggered")

    dlg = NeuronLaboratory(DummyBW())
    dlg.show()
    sys.exit(app.exec_())