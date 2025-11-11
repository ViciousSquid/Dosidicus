# multiplayer_config_dialog.py
from PyQt5 import QtCore, QtGui, QtWidgets
from plugins.multiplayer import mp_constants
import os

class MultiplayerConfigDialog(QtWidgets.QDialog):
    """
    Modal dialog that lets the user change multiplayer network settings.
    New: checkbox to switch to TCP/IP list + line-edit for addresses.
    """
    def __init__(self, plugin_instance, parent=None, initial_settings=None):
        super().__init__(parent)
        self.plugin = plugin_instance
        self.setWindowTitle("Multiplayer Network Settings")
        self.setModal(True)
        self.resize(500, 400)
        self._build_ui(initial_settings or {})

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self, cfg):
        main_layout = QtWidgets.QVBoxLayout(self)

        # ----- multicast group / port -----
        grp_multicast = QtWidgets.QGroupBox("Multicast (UDP)")
        form = QtWidgets.QFormLayout(grp_multicast)
        self.mc_group_edit = QtWidgets.QLineEdit(cfg.get("multicast_group", mp_constants.MULTICAST_GROUP))
        self.mc_port_spin = QtWidgets.QSpinBox()
        self.mc_port_spin.setRange(1024, 65535)
        self.mc_port_spin.setValue(cfg.get("port", mp_constants.MULTICAST_PORT))
        form.addRow("Group:", self.mc_group_edit)
        form.addRow("Port:", self.mc_port_spin)
        main_layout.addWidget(grp_multicast)

        # ----- TCP/IP list -----
        grp_tcp = QtWidgets.QGroupBox("TCP/IP Peer List")
        vbox = QtWidgets.QVBoxLayout(grp_tcp)
        self.use_tcp_check = QtWidgets.QCheckBox("Use TCP/IP list instead of multicast")
        self.use_tcp_check.setToolTip("Check this to connect to specific IPs across routers / Internet.")
        self.tcp_ip_edit = QtWidgets.QLineEdit(cfg.get("tcp_ip_list", ""))
        self.tcp_ip_edit.setPlaceholderText("e.g. 192.168.1.50,203.0.113.12,example.com")
        self.tcp_ip_edit.setEnabled(False)
        self.use_tcp_check.toggled.connect(lambda on: self.tcp_ip_edit.setEnabled(on))
        self.use_tcp_check.setChecked(cfg.get("use_tcp", False))
        vbox.addWidget(self.use_tcp_check)
        vbox.addWidget(self.tcp_ip_edit)
        main_layout.addWidget(grp_tcp)

        # ----- other existing sliders -----
        self.opacity_slider = self._new_slider(cfg.get("remote_opacity", 1.0), 0.2, 1.0, 0.05, "Remote opacity")
        self.sync_spin = QtWidgets.QSpinBox()
        self.sync_spin.setRange(1, 10)
        self.sync_spin.setValue(int(cfg.get("sync_interval", 2)))
        form2 = QtWidgets.QFormLayout()
        form2.addRow("Remote squid opacity:", self.opacity_slider)
        form2.addRow("Sync interval (s):", self.sync_spin)
        main_layout.addLayout(form2)

        # ----- OK / Cancel -----
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _new_slider(self, val, minv, maxv, step, label):
        slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        slider.setRange(int(minv / step), int(maxv / step))
        slider.setValue(int(val / step))
        slider.setTickPosition(QtWidgets.QSlider.TicksBelow)
        slider.setTickInterval(1)
        slider.setSingleStep(1)
        return slider

    def _on_ok(self):
        self.new_settings = {
            "multicast_group": self.mc_group_edit.text().strip(),
            "port": self.mc_port_spin.value(),
            "remote_opacity": self.opacity_slider.value() * 0.05,
            "sync_interval": self.sync_spin.value(),
            "use_tcp": self.use_tcp_check.isChecked(),
            "tcp_ip_list": self.tcp_ip_edit.text().strip()
        }
        self.accept()

    # ------------------------------------------------------------------
    # let caller re-load values if dialog is re-opened
    # ------------------------------------------------------------------
    def load_settings(self, cfg):
        self.mc_group_edit.setText(cfg.get("multicast_group", mp_constants.MULTICAST_GROUP))
        self.mc_port_spin.setValue(cfg.get("port", mp_constants.MULTICAST_PORT))
        self.opacity_slider.setValue(int(cfg.get("remote_opacity", 1.0) / 0.05))
        self.sync_spin.setValue(int(cfg.get("sync_interval", 2)))
        self.use_tcp_check.setChecked(cfg.get("use_tcp", False))
        self.tcp_ip_edit.setText(cfg.get("tcp_ip_list", ""))