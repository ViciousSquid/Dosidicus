"""The game's log file: one place, every module, tracebacks included."""
import logging
import sys
import threading

import pytest

from src import app_logging


@pytest.fixture
def log_file(tmp_path):
    root = logging.getLogger()
    before_level, before_hook, before_thread_hook = root.level, sys.excepthook, threading.excepthook
    path = app_logging.setup_logging(str(tmp_path / 'logs'))
    yield path
    root.removeHandler(app_logging._file_handler)
    app_logging._file_handler.close()
    app_logging._file_handler = None
    root.setLevel(before_level)
    sys.excepthook, threading.excepthook = before_hook, before_thread_hook


def _read(path):
    for handler in logging.getLogger().handlers:
        handler.flush()
    with open(path, encoding='utf-8') as handle:
        return handle.read()


def test_any_modules_logger_reaches_the_file(log_file):
    logging.getLogger('src.some_module').warning('squid %s', 'noticed')
    text = _read(log_file)
    assert 'squid noticed' in text and 'src.some_module' in text


def test_a_handled_exception_keeps_its_traceback(log_file):
    try:
        raise ValueError('lost the food')
    except Exception:
        logging.getLogger('src.x').warning('Handled exception', exc_info=True)
    text = _read(log_file)
    assert 'ValueError: lost the food' in text and 'Traceback' in text


def test_setting_up_twice_does_not_write_every_line_twice(tmp_path, log_file):
    again = app_logging.setup_logging(str(tmp_path / 'logs'))
    logging.getLogger('src.x').error('only once')
    assert _read(again).count('only once') == 1


def test_ignored_exceptions_are_recorded_only_when_asked(tmp_path, monkeypatch, log_file):
    logging.getLogger('src.x').debug('quiet detail')
    logging.getLogger('src.x').info('normal detail')
    assert 'quiet detail' not in _read(log_file)
    monkeypatch.setenv('DOSIDICUS_LOG_LEVEL', 'DEBUG')
    path = app_logging.setup_logging(str(tmp_path / 'logs'))
    logging.getLogger('src.x').debug('loud detail')
    assert 'loud detail' in _read(path)


def test_uncaught_exceptions_are_logged_and_reported(log_file):
    seen = []
    app_logging.log_uncaught_exceptions(also_call=lambda *args: seen.append(args[0]))
    try:
        raise RuntimeError('nobody caught this')
    except RuntimeError:
        sys.excepthook(*sys.exc_info())
    assert seen == [RuntimeError]
    assert 'RuntimeError: nobody caught this' in _read(log_file)


def test_an_exception_on_another_thread_is_logged(log_file):
    app_logging.log_uncaught_exceptions()

    def fail():
        raise KeyError('thread fell over')

    worker = threading.Thread(target=fail, name='vision-worker')
    worker.start()
    worker.join()
    text = _read(log_file)
    assert 'thread fell over' in text and 'vision-worker' in text


def test_an_unwritable_folder_does_not_stop_the_game(tmp_path):
    blocker = tmp_path / 'logs'
    blocker.write_text('a file where the folder should be')
    assert app_logging.setup_logging(str(blocker)) is None


def test_a_new_game_can_save_its_empty_memory(tmp_path):
    """Found by the log: the first save of a new game failed, because the
    memory folder was only created when there was a memory to write."""
    import json
    from src.memory_manager import MemoryManager
    folder = tmp_path / '_memory'
    manager = MemoryManager(memory_dir=str(folder))
    manager.save_memory([], manager.short_term_file)
    assert json.loads((folder / 'ShortTerm.json').read_text()) == []
