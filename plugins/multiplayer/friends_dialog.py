"""Plugins > Multiplayer > Friends: meet a friend's squid over the internet.

Two things on one small window. YOUR CODE, to give to a friend; and a box for
THEIR code (or their IP address), to link your tank to theirs. Everything it
does is in MultiplayerPlugin and friend_link.py; this is only the window.
"""
import threading
import time

from PyQt5 import QtCore, QtWidgets


class FriendsDialog(QtWidgets.QDialog):
    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        self.plugin = plugin
        self.setWindowTitle("Friends - internet play")
        self.resize(520, 520)
        layout = QtWidgets.QVBoxLayout(self)

        # ---- your code ----------------------------------------------------
        yours = QtWidgets.QGroupBox("Your friend code")
        box = QtWidgets.QVBoxLayout(yours)
        self.code = QtWidgets.QLineEdit()
        self.code.setReadOnly(True)
        self.code.setAlignment(QtCore.Qt.AlignCenter)
        self.code.setPlaceholderText("press 'Get my code'")
        font = self.code.font()
        font.setPointSize(font.pointSize() + 4)
        font.setBold(True)
        self.code.setFont(font)
        box.addWidget(self.code)
        row = QtWidgets.QHBoxLayout()
        self.get_button = QtWidgets.QPushButton("Get my code")
        self.get_button.clicked.connect(self.get_code)
        self.copy_button = QtWidgets.QPushButton("Copy")
        self.copy_button.clicked.connect(self.copy_code)
        self.new_button = QtWidgets.QPushButton("New code")
        self.new_button.setToolTip("Make the old code useless. Friends already "
                                   "linked stay linked.")
        self.new_button.clicked.connect(self.new_code)
        for button in (self.get_button, self.copy_button, self.new_button):
            row.addWidget(button)
        box.addLayout(row)
        self.code_note = QtWidgets.QLabel(
            "Give this to a friend. It tells their game where your tank is, so "
            "it contains your internet address - only give it to someone you "
            "would give that to. 'Get my code' asks a public server what your "
            "address is; nothing else is sent anywhere.")
        self.code_note.setWordWrap(True)
        box.addWidget(self.code_note)
        layout.addWidget(yours)

        # ---- their code ---------------------------------------------------
        theirs = QtWidgets.QGroupBox("Add a friend")
        box = QtWidgets.QVBoxLayout(theirs)
        row = QtWidgets.QHBoxLayout()
        self.entry = QtWidgets.QLineEdit()
        self.entry.setPlaceholderText("their friend code, or an IP address (1.2.3.4 or 1.2.3.4:10000)")
        self.entry.returnPressed.connect(self.add_friend)
        self.add_button = QtWidgets.QPushButton("Connect")
        self.add_button.clicked.connect(self.add_friend)
        row.addWidget(self.entry)
        row.addWidget(self.add_button)
        box.addLayout(row)
        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        box.addWidget(self.status)
        layout.addWidget(theirs)

        # ---- who is linked ---------------------------------------------------
        linked = QtWidgets.QGroupBox("Linked tanks")
        box = QtWidgets.QVBoxLayout(linked)
        self.friends = QtWidgets.QListWidget()
        box.addWidget(self.friends)
        self.remove_button = QtWidgets.QPushButton("Remove")
        self.remove_button.clicked.connect(self.remove_friend)
        box.addWidget(self.remove_button, alignment=QtCore.Qt.AlignRight)
        layout.addWidget(linked)

        help_text = QtWidgets.QLabel(
            "<b>If nothing happens:</b> home routers only let in traffic from "
            "somewhere your game has just sent to. Either <b>both</b> of you "
            "enter each other's code, or whoever is being joined forwards UDP "
            f"port {plugin.listening_port()} on their router. Your squid still "
            "decides for itself whether to visit: linking tanks only makes it "
            "possible. A tank holds its own squid and up to three visitors.")
        help_text.setWordWrap(True)
        layout.addWidget(help_text)

        close = QtWidgets.QPushButton("Close")
        close.clicked.connect(self.hide)
        layout.addWidget(close, alignment=QtCore.Qt.AlignRight)

        self._finding = None
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(1000)
        self.refresh()

    # ------------------------------------------------------------------
    def get_code(self):
        """Ask for the tank's outside address without freezing the window."""
        if self._finding is not None and self._finding.is_alive():
            return
        self.get_button.setEnabled(False)
        self.code_note.setText("Asking what your address is...")
        self._finding = threading.Thread(target=self.plugin.find_friend_code,
                                         name="FriendCode", daemon=True)
        self._finding.start()

    def copy_code(self):
        if self.code.text():
            QtWidgets.QApplication.clipboard().setText(self.code.text())
            self.status.setText("Code copied.")

    def new_code(self):
        self.code.setText(self.plugin.new_friend_code())
        self.status.setText("New code made. The old one no longer works.")

    def add_friend(self):
        ok, message = self.plugin.connect_to_friend(self.entry.text())
        self.status.setText(message)
        if ok:
            self.entry.clear()
        self.refresh()

    def remove_friend(self):
        item = self.friends.currentItem()
        if item is None:
            return
        ip, port = item.data(QtCore.Qt.UserRole)
        self.plugin.forget_friend(ip, port)
        self.refresh()

    def refresh(self):
        if self._finding is not None and not self._finding.is_alive():
            self._finding = None
            self.get_button.setEnabled(True)
            self.code_note.setText(self.plugin.friend_code_note())
        code = self.plugin.friend_code()
        if code and (self.code.text() or self.plugin.friend_code_known()):
            self.code.setText(code)
        selected = self.friends.currentRow()
        self.friends.clear()
        now = time.time()
        for friend in self.plugin.friends():
            heard = friend['last_heard']
            if not heard:
                state = "no answer yet"
            elif now - heard < 15:
                state = "connected"
            else:
                state = f"last heard {int(now - heard)}s ago"
            how = "joined with your code" if friend['theirs'] else "added by you"
            item = QtWidgets.QListWidgetItem(
                f"{friend['ip']}:{friend['port']}   -   {state}   ({how})")
            item.setData(QtCore.Qt.UserRole, (friend['ip'], friend['port']))
            self.friends.addItem(item)
        if 0 <= selected < self.friends.count():
            self.friends.setCurrentRow(selected)
