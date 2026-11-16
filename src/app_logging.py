"""One place that decides where the game's log goes.

Every module logs through the standard library::

    import logging
    _LOG = logging.getLogger(__name__)

and `setup_logging()` - called once by main.py - sends all of it to
`logs/dosidicus_log.txt`, beside the saves. That is the file to attach to a
bug report: it holds the traceback of every error the game caught and carried
on from, not only the ones that stopped it.

The file is kept small (three rotated files of 1 MB at most). Set
`DOSIDICUS_LOG_LEVEL=DEBUG` to also record errors the game deliberately
ignores, which is usually what explains "nothing happened".
"""
import logging
import logging.handlers
import os
import sys
import threading

LOG_DIRECTORY = 'logs'
LOG_FILE_NAME = 'dosidicus_log.txt'
LOG_FORMAT = '%(asctime)s %(levelname)-7s %(name)s: %(message)s'
MAX_BYTES = 1_000_000
BACKUPS = 2

_file_handler = None


def log_path(directory=LOG_DIRECTORY):
    return os.path.abspath(os.path.join(directory, LOG_FILE_NAME))


def _level_from_environment(default):
    name = os.environ.get('DOSIDICUS_LOG_LEVEL', '').strip().upper()
    level = logging.getLevelName(name) if name else default
    return level if isinstance(level, int) else default


def setup_logging(directory=LOG_DIRECTORY, level=logging.INFO):
    """Send every logger's output to the log file. Safe to call twice.

    Returns the path of the log file, or None where it cannot be written
    (a read-only folder): the game still runs, it just keeps no log.
    """
    global _file_handler
    root = logging.getLogger()
    if _file_handler is not None:
        root.removeHandler(_file_handler)
        _file_handler.close()
        _file_handler = None
    level = _level_from_environment(level)
    try:
        os.makedirs(directory, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            log_path(directory), maxBytes=MAX_BYTES, backupCount=BACKUPS,
            encoding='utf-8', delay=True)
    except OSError:
        return None
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root.addHandler(handler)
    if root.level == logging.NOTSET or root.level > level:
        root.setLevel(level)
    _file_handler = handler
    return log_path(directory)


def log_uncaught_exceptions(also_call=None):
    """Record exceptions nothing caught - on any thread - in the log.

    `also_call(exctype, value, traceback)` runs afterwards for main-thread
    exceptions (the game uses it to show its error dialog).
    """
    log = logging.getLogger('dosidicus.uncaught')

    def on_exception(exctype, value, tb):
        if issubclass(exctype, KeyboardInterrupt):
            sys.__excepthook__(exctype, value, tb)
            return
        log.critical('Unhandled exception', exc_info=(exctype, value, tb))
        if also_call is not None:
            also_call(exctype, value, tb)

    def on_thread_exception(args):
        if issubclass(args.exc_type, SystemExit):
            return
        log.critical('Unhandled exception in thread %s',
                     getattr(args.thread, 'name', '?'),
                     exc_info=(args.exc_type, args.exc_value, args.exc_traceback))

    sys.excepthook = on_exception
    threading.excepthook = on_thread_exception
