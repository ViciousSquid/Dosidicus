"""Shared setup for the desktop tests.

Qt needs two things before any widget is made: a platform that works without
a display, and one application object. Individual test files used to arrange
this for themselves, so a file could pass in the full run (an earlier file
had made the application) and abort the interpreter when run on its own.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session", autouse=True)
def qt_application():
    from PyQt5 import QtWidgets
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app
