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
        
        # --- NEW: Apply Card-Based Styling from learning_tab/memory_tab ---
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 2px solid #e1e5eb;
                border-radius: 12px;
                background-color: #f8f9fa;
            }
            QTabBar::tab {
                background: #f8f9fa;
                border: 1px solid #e1e5eb;
                padding: 10px 20px;
                margin-right: 5px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-size: 14px;
                color: #2c3e50;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                border-bottom: none;
                font-weight: 600;
            }
            /* Style all QGroupBoxes to appear as modern cards */
            QGroupBox { 
                background-color: #ffffff;
                border: 1px solid #dee2e6;
                border-radius: 10px;
                padding-top: 20px; 
                margin-top: 10px; 
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 3px;
                left: 10px;
                color: #1976d2; /* Use a primary color for card titles */
                font-weight: bold;
                font-size: 12pt;
            }
        """)
        # ------------------------------------------------------------------
        
        # Initialize forced values and timer for absolute override
        self.forced_neurons = {}  # Dictionary to store forced values: name -> value
        self._force_timer = QTimer(self)
        self._force_timer.timeout.connect(self._apply_forced_values)
        self._force_timer.start(100)  # Check 10 times per second for smooth override
        
        self._build_overview_tab()
        self._build_inspector_tab()
        self._build_edit_tab()

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
        self.pick_neuron.setStyleSheet("""
            QComboBox { font-size: 18px; min-height: 36px; padding: 4px; }
        """)
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
        self._inspect_neuron(self.pick_neuron.currentText())
        self._paint_edit()

    def select_neuron_by_name(self, neuron_name: str):
        """
        Selects the specified neuron in the pick_neuron dropdown
        and refreshes the Inspector tab content.
        """
        if not hasattr(self, 'pick_neuron'):
            # pick_neuron is defined in _build_inspector_tab
            return
                
        # 1. Select the neuron in the dropdown
        idx = self.pick_neuron.findText(neuron_name)
        if idx >= 0:
            # Block signals to prevent _inspect_neuron being called twice if the index is already set
            self.pick_neuron.blockSignals(True)
            self.pick_neuron.setCurrentIndex(idx)
            self.pick_neuron.blockSignals(False)
                
            # 2. Force the inspection of the newly selected neuron
            self._inspect_neuron(neuron_name)
                
            # 3. Switch to the "Deep Inspector" tab
            self.tabs.setCurrentIndex(1)  # Index 1 corresponds to the "Deep Inspector" tab
                
            # 4. Update the view to reflect the change
            self.update()

    # ================================================================
    #  Overview / Inspector / Edit  (Refactored for card styling)
    # ================================================================
    def _paint_overview(self):
        while self.ov_grid.count():
            item = self.ov_grid.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        nd = getattr(self.bw, 'neurogenesis_data', {})
        cfg = getattr(self.bw, 'neurogenesis_config', {})
        
        # Removed: card1.setStyleSheet("QGroupBox{font-weight:bold;}")
        card1 = QGroupBox("Counter progress")
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
        
        # Removed: card2.setStyleSheet("QGroupBox{font-weight:bold;}")
        card2 = QGroupBox("Newest neurogenesis neurons")
        v2 = QVBoxLayout(card2)
        details = nd.get('new_neurons_details', {})
        for name, info in sorted(details.items(), key=lambda x: x[1].get('created_at', 0), reverse=True)[:5]:
            age = int(time.time() - info.get('created_at', 0))
            v2.addWidget(QLabel(f"<b>{name}</b>  –  {info.get('trigger_type','?')}  –  {age}s ago"))
        if not details:
            v2.addWidget(QLabel("None yet"))
        self.ov_grid.addWidget(card2, 0, 1)
        
        # Removed: card3.setStyleSheet("QGroupBox{font-weight:bold;}")
        card3 = QGroupBox("Limits & pruning")
        v3 = QVBoxLayout(card3)
        current = len(self.bw.neuron_positions) - len(self.bw.excluded_neurons)
        max_n = cfg.get('max_neurons', 32)
        v3.addWidget(self._progress_widget(f"Neurons", current, max_n))
        v3.addWidget(QLabel(f"Pruning enabled: <b>{self.bw.pruning_enabled}</b>"))
        self.ov_grid.addWidget(card3, 1, 0)
        
        # Removed: card4.setStyleSheet("QGroupBox{font-weight:bold;}")
        card4 = QGroupBox("Quick actions")
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
        
        # Removed: card2.setStyleSheet("QGroupBox{font-weight:bold;}")
        card2 = QGroupBox("Connections (excitatory vs inhibitory)")
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
        
        # Removed: card3.setStyleSheet("QGroupBox{font-weight:bold;}")
        card3 = QGroupBox("Functional impact simulation")
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
        
        # Removed: card4.setStyleSheet("QGroupBox{font-weight:bold;}")
        card4 = QGroupBox("Did you know?")
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

        # Removed: card.setStyleSheet("QGroupBox{font-weight:bold;}")
        card = QGroupBox("Neuron values (drag to change)  –  click 🔒 to lock")
        grid = QGridLayout(card)

        for row, name in enumerate(sorted(self.bw.neuron_positions.keys())):
            val = self.forced_neurons.get(name, self.bw.state.get(name, 50))  # Use forced value if available
            if isinstance(val, bool):
                continue

            # Preserve existing lock state
            was_locked = self.locked_neurons.get(name, {}).get("locked", False)

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
            btn.setChecked(was_locked)
            btn.setText("🔒" if was_locked else "🔓")
            btn.setFixedSize(24, 24)
            btn.setStyleSheet("QToolButton:checked { color: red; }")
            btn.toggled.connect(lambda checked, n=name, b=btn: self._toggle_lock(n, b))
            grid.addWidget(btn, row, 3)

            # store references
            self.locked_neurons[name] = {
                "locked": was_locked,
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
        """Toggle lock state and store current value as forced when locked"""
        is_locked = button.isChecked()
        self.locked_neurons[name]["locked"] = is_locked
        button.setText("🔒" if is_locked else "🔓")
        
        if is_locked:
            current_value = self.bw.state.get(name, 50)
            self.forced_neurons[name] = int(current_value)  # CAST TO INT
            self.status_lbl.setText(f"🔒 {name} locked at {current_value}")
        else:
            if name in self.forced_neurons:
                del self.forced_neurons[name]
            self.status_lbl.setText(f"🔓 {name} unlocked")

    def _set_neuron(self, name, value):
        """Store and apply a forced neuron value that overrides simulation"""
        self.forced_neurons[name] = value  # Store as forced
        self.bw.state[name] = value        # Apply immediately
        self.bw.update()

    def _apply_forced_values(self):
        """Continuously enforce forced neuron values, overriding simulation"""
        if not self.isVisible():  # Don't run when dialog is hidden
            return
            
        for name, value in self.forced_neurons.items():
            if name in self.bw.state:
                # Force the brain widget state to our value
                self.bw.state[name] = value
                
                # NEW: Sync to squid if it's a core statistic neuron
                if hasattr(self.bw, 'tamagotchi_logic') and hasattr(self.bw.tamagotchi_logic, 'squid'):
                    squid = self.bw.tamagotchi_logic.squid
                    # Only sync the 8 core stats that StatisticsWindow displays
                    if name in ['hunger', 'happiness', 'cleanliness', 'sleepiness', 
                            'health', 'satisfaction', 'curiosity', 'anxiety']:
                        setattr(squid, name, value)
                
                # If locked, ensure controls stay perfectly synced
                if name in self.locked_neurons and self.locked_neurons[name]["locked"]:
                    slider = self.locked_neurons[name]["slider"]
                    spin = self.locked_neurons[name]["spin"]
                    
                    # Update controls without triggering signals to avoid loops
                    int_value = int(value)  # CAST TO INT FOR UI
                    if slider.value() != int_value:
                        slider.blockSignals(True)
                        slider.setValue(int_value)
                        slider.blockSignals(False)
                    
                    if spin.value() != int_value:
                        spin.blockSignals(True)
                        spin.setValue(int_value)
                    spin.blockSignals(False)

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

        def perform_hebbian_learning(self):
            print("Hebbian cycle triggered")
            
        def update(self):
            # dummy update for slider/spinbox changes
            pass

    dlg = NeuronLaboratory(DummyBW())
    dlg.show()
    sys.exit(app.exec_())