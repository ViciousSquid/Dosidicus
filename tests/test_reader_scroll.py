"""
A list someone is reading must not be rebuilt underneath them.

Every panel in the Brain Tool refreshes on a timer, and several of them do it
by tearing their contents down and building them again. Restoring the scroll
position afterwards is timing-sensitive - it depends on when the platform gets
round to laying the new contents out - and each time it misses, the reader is
thrown back to the top of a list they were halfway down.

So the rule these tests hold the panels to is simpler than restoration: while
someone is reading a view (holding its scrollbar, or with the pointer over it
and scrolled away from the top) it is left exactly as it is, and it catches up
once they move on. A view at the top keeps updating, because that is where new
entries arrive.

Reading is simulated by marking the view as under the mouse, which is what Qt
itself does when the pointer enters it.
"""

import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5 import QtCore, QtWidgets  # noqa: E402

from src.brain_ui_utils import (preserve_scroll, reader_is_busy,  # noqa: E402
                                set_html)

_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _settle(rounds=30):
    for _ in range(rounds):
        _app.processEvents()


def _hover(view, on=True):
    """Put the pointer over a view (or take it away), as Qt does on enter/leave."""
    view.setAttribute(QtCore.Qt.WA_UnderMouse, on)
    viewport = view.viewport() if hasattr(view, 'viewport') else None
    if viewport is not None:
        viewport.setAttribute(QtCore.Qt.WA_UnderMouse, on)


def _scroll_to_middle(bar):
    """Scroll the way a reader does - through slider actions, not setValue."""
    while bar.value() < bar.maximum() // 2:
        bar.triggerAction(QtWidgets.QAbstractSlider.SliderPageStepAdd)
    return bar.value()


def _long_html(tag):
    return "".join(f"<p>{tag} paragraph {i} " + "words " * 30 + "</p>"
                   for i in range(80))


class TextViewTests(unittest.TestCase):

    def setUp(self):
        self.view = QtWidgets.QTextBrowser()
        self.view.resize(500, 300)
        self.view.show()
        set_html(self.view, _long_html("first"))
        _settle()
        self.bar = self.view.verticalScrollBar()
        self.assertGreater(self.bar.maximum(), 200, "the view has to scroll")

    def tearDown(self):
        self.view.deleteLater()

    def test_a_view_being_read_is_not_rewritten(self):
        where = _scroll_to_middle(self.bar)
        _hover(self.view)

        self.assertFalse(set_html(self.view, _long_html("second")))
        _settle()
        self.assertIn("first paragraph", self.view.toPlainText())
        self.assertEqual(self.bar.value(), where)

    def test_it_catches_up_once_the_reader_moves_on_and_stays_put(self):
        where = _scroll_to_middle(self.bar)
        _hover(self.view)
        set_html(self.view, _long_html("second"))
        _hover(self.view, False)

        self.assertTrue(set_html(self.view, _long_html("second")))
        _settle()
        self.assertIn("second paragraph", self.view.toPlainText())
        self.assertEqual(self.bar.value(), where)

    def test_a_view_at_the_top_keeps_updating_under_the_pointer(self):
        self.bar.setValue(0)
        _hover(self.view)
        self.assertTrue(set_html(self.view, _long_html("second")))
        self.assertIn("second paragraph", self.view.toPlainText())

    def test_holding_the_scrollbar_blocks_the_rewrite(self):
        _scroll_to_middle(self.bar)
        self.bar.setSliderDown(True)
        try:
            self.assertTrue(reader_is_busy(self.view))
            self.assertFalse(set_html(self.view, _long_html("second")))
        finally:
            self.bar.setSliderDown(False)


class RestoreTests(unittest.TestCase):

    def test_scrolling_after_a_refresh_is_not_undone(self):
        """The restore listener must let go as soon as the reader scrolls.

        A rebuilt panel keeps changing size for a moment while it lays out,
        and the restore re-applies the old position each time it does. If the
        reader has scrolled on in that moment, re-applying it drags them back.
        """
        area = QtWidgets.QScrollArea()
        area.setWidgetResizable(True)
        content = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(content)
        for i in range(60):
            layout.addWidget(QtWidgets.QLabel(f"row {i}"))
        area.setWidget(content)
        area.resize(300, 200)
        area.show()
        _settle()
        bar = area.verticalScrollBar()
        _scroll_to_middle(bar)

        with preserve_scroll(area):
            pass                               # the refresh
        bar.triggerAction(QtWidgets.QAbstractSlider.SliderPageStepAdd)
        moved_to = bar.value()

        for i in range(10):                    # content keeps changing size
            layout.addWidget(QtWidgets.QLabel(f"late row {i}"))
        _settle()
        self.assertGreaterEqual(bar.value(), moved_to)
        area.deleteLater()


class PanelTests(unittest.TestCase):
    """The panels themselves, against a real brain."""

    @classmethod
    def setUpClass(cls):
        with redirect_stdout(io.StringIO()):
            from test_organism import make_organism
            cls.org = make_organism(neurogenesis=False)
            for _ in range(40):
                cls.org.bout(['eating'], {'satisfaction': +4.0, 'hunger': -5.0})
                cls.org.bout(['grooming'], {'cleanliness': +6.0})

    def test_the_knowledge_list_is_left_alone_while_it_is_read(self):
        from src.brain_knowledge_tab import KnowledgeTab
        with redirect_stdout(io.StringIO()):
            tab = KnowledgeTab(brain_widget=self.org.brain)
        tab._refresh_timer.stop()
        tab.resize(700, 350)
        tab.show()
        _settle()
        view = tab.knowledge_view
        bar = view.verticalScrollBar()
        self.assertGreater(bar.maximum(), 0, "the list has to scroll")
        _scroll_to_middle(bar)
        _hover(view)
        before = view.toHtml()

        with redirect_stdout(io.StringIO()):
            for _ in range(10):
                self.org.bout(['grooming'], {'cleanliness': +6.0})
            tab._refresh_if_visible()
        self.assertEqual(view.toHtml(), before)

        _hover(view, False)
        with redirect_stdout(io.StringIO()):
            tab._refresh_if_visible()
        self.assertNotEqual(view.toHtml(), before,
                            "it never caught up after the reader moved on")
        tab.deleteLater()

    def test_the_memory_lists_are_left_alone_while_they_are_read(self):
        from src.brain_memory_tab import MemoryTab
        memories = [{'category': 'food', 'key': f'snack_{i}',
                     'value': f'Ate snack number {i}', 'timestamp': i}
                    for i in range(30)]
        manager = SimpleNamespace(
            get_all_short_term_memories=lambda: list(memories),
            get_all_long_term_memories=lambda: [])
        logic = SimpleNamespace(squid=SimpleNamespace(memory_manager=manager))
        with redirect_stdout(io.StringIO()):
            tab = MemoryTab(tamagotchi_logic=logic, brain_widget=self.org.brain)
        tab.resize(600, 400)
        tab.show()
        tab.memory_subtabs.setCurrentIndex(
            tab.memory_subtabs.indexOf(tab.stm_tab))
        _settle()
        with redirect_stdout(io.StringIO()):
            tab.update_from_brain_state({})
        _settle()
        bar = tab.stm_scroll.verticalScrollBar()
        self.assertGreater(bar.maximum(), 0, "the list has to scroll")
        _scroll_to_middle(bar)
        _hover(tab.stm_scroll)
        first_card = tab.stm_content_layout.itemAt(0).widget()

        memories.insert(0, {'category': 'food', 'key': 'new', 'value': 'Something new'})
        with redirect_stdout(io.StringIO()):
            tab.update_from_brain_state({})
        _settle()
        self.assertIs(tab.stm_content_layout.itemAt(0).widget(), first_card,
                      "the list was rebuilt while it was being read")

        _hover(tab.stm_scroll, False)
        with redirect_stdout(io.StringIO()):
            tab.update_from_brain_state({})
        _settle()
        self.assertIsNot(tab.stm_content_layout.itemAt(0).widget(), first_card,
                         "it never caught up after the reader moved on")
        tab.deleteLater()

    def test_the_laboratory_leaves_the_page_being_read_alone(self):
        from src.laboratory import NeuronLaboratory
        with redirect_stdout(io.StringIO()):
            lab = NeuronLaboratory(self.org.brain)
        lab.timer.stop()
        lab._force_timer.stop()
        lab.resize(600, 300)
        lab.show()
        _settle()
        bar = lab.ov_scroll.verticalScrollBar()
        self.assertGreater(bar.maximum(), 0, "the overview has to scroll")
        _scroll_to_middle(bar)
        _hover(lab.ov_scroll)
        first_card = lab.ov_grid.itemAt(0).widget()

        with redirect_stdout(io.StringIO()):
            lab._refresh()
        self.assertIs(lab.ov_grid.itemAt(0).widget(), first_card)

        _hover(lab.ov_scroll, False)
        with redirect_stdout(io.StringIO()):
            lab._refresh()
        self.assertIsNot(lab.ov_grid.itemAt(0).widget(), first_card)
        lab.deleteLater()

    def test_the_laboratory_picker_is_only_refilled_when_the_neurons_change(self):
        from src.laboratory import NeuronLaboratory
        with redirect_stdout(io.StringIO()):
            lab = NeuronLaboratory(self.org.brain)
        lab.timer.stop()
        lab._force_timer.stop()
        rebuilt = []
        lab.pick_neuron.model().modelReset.connect(lambda: rebuilt.append(1))
        lab.pick_neuron.model().rowsRemoved.connect(lambda *a: rebuilt.append(1))
        with redirect_stdout(io.StringIO()):
            for _ in range(5):
                lab._refresh()
        self.assertEqual(rebuilt, [], "the neuron picker was cleared and "
                                      "refilled with the same neurons")
        lab.deleteLater()


if __name__ == '__main__':
    unittest.main()
