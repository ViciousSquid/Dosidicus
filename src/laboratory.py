# 2.4.5.1 | rev3_dec25
#  --------------------------------------------------------------
#  NEURON LABORATORY
#  --------------------------------------------------------------

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
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
from .localisation import loc  # Import localisation

# ------------------------------------------------------------------
#  Helper: coloured connection badge
# ------------------------------------------------------------------
def badge(text, color="#333", bg="#eee"):
    return f"""<span style="color:{color};background:{bg};
               padding:2px 6px;border-radius:4px;font-size:10pt;
               font-weight:600;">{text}</span>"""


# ------------------------------------------------------------------
#  Main Laboratory Dialog
# ------------------------------------------------------------------
class NeuronLaboratory(QDialog):
    def __init__(self, brain_widget, parent=None):
        super().__init__(parent)
        self.bw = brain_widget
        self.setWindowTitle(loc("lab_title", "🧠  Neuron Laboratory"))
        self.resize(900, 750)
        self.setWindowFlag(Qt.WindowMinMaxButtonsHint)

        # ---- top toolbar ----
        bar = QHBoxLayout()
        self.live_check = QCheckBox(loc("lab_live_refresh", "Live refresh"))
        self.live_check.setChecked(True)
        self.live_check.toggled.connect(self._toggle_live)
        bar.addWidget(self.live_check)

        bar.addStretch()
        self.lock_check = QCheckBox(loc("lab_unlock_editing", "🔓  Unlock editing"))
        self.lock_check.toggled.connect(self._unlock_editing)
        bar.addWidget(self.lock_check)

        # ---- main notebook ----
        self.tabs = QTabWidget()
        
        # --- Apply Card-Based Styling ---
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
        self.status_lbl = QLabel(loc("lab_status_ready", "Ready"))
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
    #  Construction helpers
    # ================================================================
    def _build_overview_tab(self):
        self.ov_scroll = QScrollArea()
        self.ov_widget = QWidget()
        self.ov_grid = QGridLayout(self.ov_widget)
        self.ov_scroll.setWidget(self.ov_widget)
        self.ov_scroll.setWidgetResizable(True)
        self.tabs.addTab(self.ov_scroll, loc("lab_tab_overview", "📊  Live Overview"))

    def _build_inspector_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        self.pick_neuron = QComboBox()
        self.pick_neuron.currentTextChanged.connect(self._inspect_neuron)
        lay.addWidget(QLabel(loc("lab_pick_neuron", "Pick a neuron to inspect:")))
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
        self.tabs.addTab(w, loc("lab_tab_inspector", "🔍  Deep Inspector"))

    def _build_edit_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        warn = QLabel(loc("lab_edit_locked_msg", "⚠️  Editing is locked – check 'Unlock editing' in the toolbar."))
        warn.setStyleSheet("color:#d9534f;font-weight:bold;")
        lay.addWidget(warn)
        self.edit_warn = warn
        self.edit_scroll = QScrollArea()
        self.edit_cards = QWidget()
        self.edit_lay = QVBoxLayout(self.edit_cards)
        self.edit_scroll.setWidget(self.edit_cards)
        self.edit_scroll.setWidgetResizable(True)
        lay.addWidget(self.edit_scroll, 1)
        self.tabs.addTab(w, loc("lab_tab_edit", "🔧  Edit Sandbox"))

    # ================================================================
    #  Live refresh
    # ================================================================
    def _refresh(self):
        if not self.live_check.isChecked():
            return
        current = self.pick_neuron.currentText()
        self.pick_neuron.clear()
        
        # Translate neuron names if needed, or use raw keys? 
        # Usually keys are used internally, but displayed names might be localized.
        # For this tool, we usually show keys, but let's stick to keys for consistency with other tools.
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
            return
                
        # 1. Select the neuron in the dropdown
        idx = self.pick_neuron.findText(neuron_name)
        if idx >= 0:
            self.pick_neuron.blockSignals(True)
            self.pick_neuron.setCurrentIndex(idx)
            self.pick_neuron.blockSignals(False)
                
            # 2. Force the inspection of the newly selected neuron
            self._inspect_neuron(neuron_name)
                
            # 3. Switch to the "Deep Inspector" tab
            self.tabs.setCurrentIndex(1)
                
            # 4. Update the view to reflect the change
            self.update()

    # ================================================================
    #  Overview / Inspector / Edit
    # ================================================================
    def _paint_overview(self):
        while self.ov_grid.count():
            item = self.ov_grid.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        nd = getattr(self.bw, 'neurogenesis_data', {})
        cfg = getattr(self.bw, 'neurogenesis_config', {})
        
        # Card 1: Counters
        card1 = QGroupBox(loc("lab_ov_counters", "Counter progress"))
        g1 = QGridLayout(card1)
        # We localize the counter labels here using existing keys or raw if simple
        metrics = [(loc("novelty", "Novelty"), nd.get('novelty_counter', 0), cfg.get('novelty_threshold', 3)),
                   (loc("stress", "Stress"), nd.get('stress_counter', 0), cfg.get('stress_threshold', .7)),
                   (loc("reward", "Reward"), nd.get('reward_counter', 0), cfg.get('reward_threshold', .6))]
        for row, (name, cur, thr) in enumerate(metrics):
            pct = min(100, (cur / thr) * 100) if thr else 0
            bar = self._progress_bar(pct)
            g1.addWidget(QLabel(f"{name} <b>{cur:.2f}</b>/{thr}"), row, 0)
            g1.addWidget(bar, row, 1)
        self.ov_grid.addWidget(card1, 0, 0)
        
        # Card 2: Newest neurons
        card2 = QGroupBox(loc("lab_ov_newest", "Newest neurogenesis neurons"))
        v2 = QVBoxLayout(card2)
        details = nd.get('new_neurons_details', {})
        for name, info in sorted(details.items(), key=lambda x: x[1].get('created_at', 0), reverse=True)[:5]:
            age = int(time.time() - info.get('created_at', 0))
            ago_text = loc("lab_ago", "{seconds}s ago", seconds=age)
            v2.addWidget(QLabel(f"<b>{name}</b>  –  {info.get('trigger_type','?')}  –  {ago_text}"))
        if not details:
            v2.addWidget(QLabel(loc("lab_none_yet", "None yet")))
        self.ov_grid.addWidget(card2, 0, 1)
        
        # Card 3: Limits
        card3 = QGroupBox(loc("lab_ov_limits", "Limits & pruning"))
        v3 = QVBoxLayout(card3)
        current = len(self.bw.neuron_positions) - len(self.bw.excluded_neurons)
        max_n = cfg.get('max_neurons', 32)
        v3.addWidget(self._progress_widget(loc("neurons", "Neurons"), current, max_n))
        pruning_text = loc("lab_pruning_enabled", "Pruning enabled:")
        v3.addWidget(QLabel(f"{pruning_text} <b>{self.bw.pruning_enabled}</b>"))
        self.ov_grid.addWidget(card3, 1, 0)
        
        # Card 4: Quick Actions
        card4 = QGroupBox(loc("lab_ov_actions", "Quick actions"))
        h = QHBoxLayout(card4)
        btn = QPushButton(loc("lab_force_hebbian", "Force Hebbian cycle"))
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

        # Card: Connector Special Details (If applicable)
        if details and details.get('trigger_type') == 'connector':
            card_special = QGroupBox(loc("lab_connector_title", "Network Bridge Protocol"))
            v_special = QVBoxLayout(card_special)
            
            info_text = (
                "<b>Status:</b> <span style='color:blue'>Active Bridge</span><br>"
                "This neuron was synthesized to rescue an isolated node.<br><br>"
                "<b>Wiring Topology:</b><br>"
                "• <b>Primary:</b> Connection to the Orphan<br>"
                "• <b>Anchor:</b> Connection to Closest Neighbor<br>"
                "• <b>Diversity:</b> Random connection to Network"
            )
            lbl_special = QLabel(info_text)
            lbl_special.setTextFormat(QtCore.Qt.RichText)
            v_special.addWidget(lbl_special)
            self.inspector_lay.addWidget(card_special)

        # Card: Connections
        card2 = QGroupBox(loc("lab_connections_title", "Connections (excitatory vs inhibitory)"))
        v2 = QVBoxLayout(card2)
        
        h_partner = loc("lab_header_partner", "Partner")
        h_weight = loc("lab_header_weight", "Weight")
        h_type = loc("lab_header_type", "Type")
        h_inf = loc("lab_header_inf", "Influence")
        
        html = "<table width='100%'>"
        html += f"<tr><th>{h_partner}</th><th>{h_weight}</th><th>{h_type}</th><th>{h_inf}</th></tr>"
        
        t_exc = loc("lab_type_excitatory", "Excitatory")
        t_inh = loc("lab_type_inhibitory", "Inhibitory")
        
        for (src, dst), w in self.bw.weights.items():
            if src == name:
                typ = t_exc if w > 0 else t_inh
                col = "#d4ffd4" if w > 0 else "#ffd4d4"
                html += f"<tr bgcolor='{col}'>"
                html += f"<td>{dst}</td><td>{w:+.3f}</td><td>{badge(typ,'#000',col)}</td>"
                html += f"<td>{self._influence_badge(w)}</td></tr>"
        for (src, dst), w in self.bw.weights.items():
            if dst == name:
                typ = t_exc if w > 0 else t_inh
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
        
        # Card: Impacts
        card3 = QGroupBox(loc("lab_impact_title", "Functional impact simulation"))
        v3 = QVBoxLayout(card3)
        impacts = self._compute_impacts(name)
        if impacts:
            h_neuron = loc("lab_header_neuron", "Neuron")
            h_delta = loc("lab_header_delta", "Δ Value")
            
            html = "<table width='100%'>"
            html += f"<tr><th>{h_neuron}</th><th>{h_delta}</th></tr>"
            for partner, delta in impacts.items():
                col = "#d4ffd4" if delta > 0 else "#ffd4d4"
                html += f"<tr bgcolor='{col}'><td>{partner}</td><td>{delta:+.2f}</td></tr>"
            html += "</table>"
            lbl = QLabel(html)
            lbl.setWordWrap(True)
            lbl.setTextFormat(QtCore.Qt.RichText)
            v3.addWidget(lbl)
        else:
            v3.addWidget(QLabel(loc("lab_no_connections", "No active connections at the moment")))
        self.inspector_lay.addWidget(card3)
        
        # Card: Educational
        card4 = QGroupBox(loc("lab_did_you_know", "Did you know?"))
        v4 = QVBoxLayout(card4)
        v4.addWidget(QLabel(self._educational_tip(name)))
        self.inspector_lay.addWidget(card4)
        self.inspector_lay.addStretch(1)

    # ================================================================
    #  EDIT tab
    # ================================================================
    def _paint_edit(self):
        while self.edit_lay.count():
            item = self.edit_lay.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        if not self.lock_check.isChecked():
            return

        card = QGroupBox(loc("lab_edit_header", "Neuron values (drag to change)  –  click 🔒 to lock"))
        grid = QGridLayout(card)

        for row, name in enumerate(sorted(self.bw.neuron_positions.keys())):
            val = self.forced_neurons.get(name, self.bw.state.get(name, 50))
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
        self._refresh()

    def _toggle_lock(self, name, button):
        is_locked = button.isChecked()
        self.locked_neurons[name]["locked"] = is_locked
        button.setText("🔒" if is_locked else "🔓")
        
        if is_locked:
            current_value = self.bw.state.get(name, 50)
            self.forced_neurons[name] = int(current_value)
            self.status_lbl.setText(loc("lab_status_locked", "🔒 {name} locked at {value}", name=name, value=current_value))
        else:
            if name in self.forced_neurons:
                del self.forced_neurons[name]
            self.status_lbl.setText(loc("lab_status_unlocked", "🔓 {name} unlocked", name=name))

    def _set_neuron(self, name, value):
        self.forced_neurons[name] = value
        self.bw.state[name] = value
        self.bw.update()

    def _apply_forced_values(self):
        if not self.isVisible():
            return
            
        for name, value in self.forced_neurons.items():
            if name in self.bw.state:
                self.bw.state[name] = value
                
                # NEW: Sync to squid if it's a core statistic neuron
                if hasattr(self.bw, 'tamagotchi_logic') and hasattr(self.bw.tamagotchi_logic, 'squid'):
                    squid = self.bw.tamagotchi_logic.squid
                    if name in ['hunger', 'happiness', 'cleanliness', 'sleepiness', 
                            'health', 'satisfaction', 'curiosity', 'anxiety']:
                        setattr(squid, name, value)
                
                if name in self.locked_neurons and self.locked_neurons[name]["locked"]:
                    slider = self.locked_neurons[name]["slider"]
                    spin = self.locked_neurons[name]["spin"]
                    
                    int_value = int(value)
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
            title = loc("lab_unlock_title", "Unlock editing?")
            msg = loc("lab_unlock_msg", "You can now change neuron values and force creation events. Use responsibly!")
            ans = QMessageBox.question(self, title, msg)
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
            return badge(loc("lab_inf_tiny", "tiny"), "#666", "#fff")
        if mag < 0.3:
            return badge(loc("lab_inf_mild", "mild"), "#fff", "#555")
        if mag < 0.6:
            return badge(loc("lab_inf_mod", "moderate"), "#fff", "#000")
        return badge(loc("lab_inf_strong", "STRONG"), "#fff", "#d9534f")

    def _compute_impacts(self, name):
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
        # 1. Try specific key first
        specific_key = f"lab_tip_{name}"
        text = loc(specific_key)
        
        # Check if translation was found (if loc returns key when missing)
        if text != specific_key:
            return text

        # 2. Core neurons
        core_keys = ["hunger", "happiness", "anxiety", "curiosity"]
        if name in core_keys:
            return loc(specific_key)
                
        if name in self.bw.original_neuron_positions:
            return loc("lab_tip_core", "Core neuron – fundamental to survival.")
                
        nd = getattr(self.bw, 'neurogenesis_data', {})
        det = nd.get('new_neurons_details', {}).get(name)
            
        if not det:
            return loc("lab_tip_neuro_default", "Neurogenesis neuron – purpose inferred from birth context.")

        # Special handling for connectors
        if det.get('trigger_type') == 'connector':
            return loc("lab_tip_connector", "Generated by the network to connect orphaned neurons. Has 3 connections.")
                
        return loc("lab_tip_neuro_fmt", 
                "Created by <b>{trigger}</b> – specialises in <b>{spec}</b>. Its job is to turn experiences into long-term behaviour.",
                trigger=det.get('trigger_type'),
                spec=det.get('specialisation','?'))


NeurogenesisDebugDialog = NeuronLaboratory  #  Old name alias – Backwards compatibility


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
        original_neuron_positions = {"hunger": (100, 100), "happiness": (200, 100)}
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
