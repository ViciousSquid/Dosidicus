"""An ink cloud fades out, and only then goes - it does not vanish at once.

The fade animation used to be held only by a local variable, so Python
collected it the moment create_ink_cloud returned: the cloud sat at full
opacity and was then removed all at once by the backup timer.
"""
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5 import QtWidgets                         # noqa: E402
from PyQt5.QtTest import QTest                      # noqa: E402

from src.tamagotchi_logic import TamagotchiLogic    # noqa: E402

APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_an_ink_cloud_fades_and_then_goes():
    scene = QtWidgets.QGraphicsScene()
    ui = SimpleNamespace(scene=scene)
    logic = SimpleNamespace(
        INK_FADE_MS=600, user_interface=ui,
        squid=SimpleNamespace(squid_x=100, squid_y=100, squid_width=60,
                              squid_height=40, ui=ui),
        statistics_window=SimpleNamespace(award=lambda points: None),
        record_statistic_event=lambda name: None)
    logic.remove_ink_cloud = lambda item: TamagotchiLogic.remove_ink_cloud(logic, item)
    logic.force_remove_ink_cloud = lambda item: TamagotchiLogic.force_remove_ink_cloud(logic, item)

    TamagotchiLogic.create_ink_cloud(logic)
    (cloud,) = scene.items()
    QTest.qWait(350)
    fading = cloud.graphicsEffect().opacity()
    assert 0.0 < fading < 1.0, f"half way through it should be fading, not {fading}"
    QTest.qWait(600)
    assert scene.items() == []
