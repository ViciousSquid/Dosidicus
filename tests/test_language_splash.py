"""The launch splash: a language is chosen before anything else starts.

  * it lists every translation shipped, by its native name;
  * it preselects the language last chosen, and saves the new choice;
  * nothing else starts until a language is chosen - main.py shows it before
    the game is even imported, and closing it quits;
  * so everything after it, the "Show tutorial?" question included, is in
    the chosen language - and that question is drawn the same way.
"""
import os
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                   # noqa: E402
from PyQt5 import QtCore, QtGui, QtWidgets                      # noqa: E402

from src import language_splash                                 # noqa: E402
from src.config_manager import ConfigManager                    # noqa: E402
from src.localisation import Localisation                       # noqa: E402

APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def config(tmp_path):
    manager = ConfigManager(str(tmp_path / 'config.ini'))
    yield manager
    Localisation.instance().set_language('en')


def choosing(monkeypatch, code=None):
    """The splash, answered: `code` chosen and OK pressed, or closed (None)."""
    def answer(splash):
        if code is None:
            return QtWidgets.QDialog.Rejected
        splash.bar.setCurrentIndex(splash.bar.findData(code))
        return QtWidgets.QDialog.Accepted
    monkeypatch.setattr(language_splash.LanguageSplash, 'exec_', answer)


def test_every_translation_is_offered_by_its_own_name():
    offered = dict(language_splash.available_languages())
    shipped = {p.stem for p in (ROOT / 'translations').glob('*.py')}
    assert set(offered) == shipped
    assert offered['en'] == 'English' and offered['de'] == 'Deutsch'
    assert offered['fr'] == 'Français' and offered['ja'] == '日本語'


def test_it_looks_like_the_mockup_and_preselects_the_saved_language():
    splash = language_splash.LanguageSplash(language_splash.available_languages(), 'es')
    assert splash.language() == 'es' and splash.bar.currentText() == 'Español'
    assert splash.ok.text() == 'OK' and splash.ok.isDefault()
    assert splash.windowFlags() & QtCore.Qt.FramelessWindowHint
    unknown = language_splash.LanguageSplash(language_splash.available_languages(), 'xx')
    assert unknown.language() == 'en'


def test_escape_does_not_skip_the_choice():
    splash = language_splash.LanguageSplash(language_splash.available_languages(), 'en')
    closed = []
    splash.rejected.connect(lambda: closed.append(True))
    splash.keyPressEvent(QtGui.QKeyEvent(QtCore.QEvent.KeyPress, QtCore.Qt.Key_Escape,
                                         QtCore.Qt.NoModifier))
    assert not closed


def test_the_choice_is_applied_and_saved(config, monkeypatch):
    choosing(monkeypatch, 'de')
    assert language_splash.choose_language(config) == 'de'
    assert Localisation.instance().current_language == 'de'
    assert ConfigManager(config.config_path).get_language() == 'de'
    choosing(monkeypatch, 'fr')                 # next launch starts from German
    seen = []
    monkeypatch.setattr(language_splash.LanguageSplash, 'exec_',
                        lambda splash: seen.append(splash.language()) or 0)
    language_splash.choose_language(ConfigManager(config.config_path))
    assert seen == ['de']


def test_closing_without_a_choice_changes_nothing(config, monkeypatch):
    choosing(monkeypatch, None)
    assert language_splash.choose_language(config) is None
    assert ConfigManager(config.config_path).get_language() == 'en'


def test_the_tutorial_question_comes_after_and_in_the_chosen_language(config, monkeypatch):
    import main
    choosing(monkeypatch, 'ja')
    language_splash.choose_language(config)
    loc = Localisation.instance()
    dialog = main.TimedMessageBox(None, loc.get('startup'), loc.get('show_tutorial_q'))
    texts = [label.text() for label in dialog.findChildren(QtWidgets.QLabel)]
    assert 'チュートリアルを表示しますか？' in texts
    assert dialog.windowTitle() == loc.get('startup') != 'Startup'
    dialog.deleteLater()


def test_main_shows_it_before_the_game_is_imported_and_closing_quits(tmp_path):
    """Run main.py as the launcher does, with the splash closed unanswered:
    it must have been shown with no game module loaded, and the launch stops."""
    probe = tmp_path / 'probe.txt'
    code = f'''
import runpy, sys
sys.argv = ['main.py']
sys.path.insert(0, {str(ROOT)!r})
import src.language_splash as splash
def closed(config_manager=None):
    loaded = [m for m in ('src.tamagotchi_logic', 'src.ui', 'src.brain_tool') if m in sys.modules]
    open({str(probe)!r}, 'w').write(repr(loaded))
    return None
splash.choose_language = closed
runpy.run_path({str(ROOT / 'main.py')!r}, run_name='__main__')
open({str(probe)!r}, 'a').write(' GAME STARTED')
'''
    result = subprocess.run([sys.executable, '-c', code], cwd=ROOT, capture_output=True,
                            text=True, timeout=120,
                            env=dict(os.environ, QT_QPA_PLATFORM='offscreen'))
    assert result.returncode == 0, result.stderr[-2000:]
    assert probe.read_text() == '[]'                # shown first, and nothing after it


def test_the_tutorial_prompt_is_drawn_like_the_splash():
    import main
    dialog = main.TimedMessageBox(None, 'Startup', 'Show tutorial?')
    splash = language_splash.LanguageSplash(language_splash.available_languages(), 'en')
    assert dialog.windowFlags() & QtCore.Qt.FramelessWindowHint
    assert language_splash.BAR_GREY in dialog.message_label.styleSheet()
    assert dialog.message_label.font().family() == splash.bar.font().family()
    assert dialog.message_label.font().bold()
    for button in (dialog.yes_button, dialog.no_button):
        assert button.styleSheet() == language_splash.orange_button(
            button.text(), language_splash.scale_factor(), width=140).styleSheet()
    assert splash.ok.styleSheet() == language_splash.orange_button(
        'OK', language_splash.scale_factor()).styleSheet()
    assert dialog.width() == splash.width()
    dialog.deleteLater()


def test_the_tutorial_prompt_answers_yes_no_and_declines_itself():
    import main
    yes = main.TimedMessageBox(None, 'Startup', 'Show tutorial?')
    yes.yes_button.click()
    assert yes.get_result() == QtWidgets.QMessageBox.Yes and not yes.timer.isActive()
    escaped = main.TimedMessageBox(None, 'Startup', 'Show tutorial?')
    escaped.result_value = QtWidgets.QMessageBox.Yes
    escaped.keyPressEvent(QtGui.QKeyEvent(QtCore.QEvent.KeyPress, QtCore.Qt.Key_Escape,
                                          QtCore.Qt.NoModifier))
    assert escaped.get_result() == QtWidgets.QMessageBox.No
    timed = main.TimedMessageBox(None, 'Startup', 'Show tutorial?', timeout_seconds=1)
    timed.update_countdown()
    assert timed.get_result() == QtWidgets.QMessageBox.No and not timed.timer.isActive()
