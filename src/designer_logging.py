"""
Logging and Error Handling for Brain Designer

Provides comprehensive logging, crash reporting, and error recovery.
"""

import sys
import os
import logging
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable
from functools import wraps

# Determine log directory
def get_log_directory() -> Path:
    """Get or create the logs directory."""
    # Try to use a logs folder next to the script
    script_dir = Path(__file__).parent.parent
    log_dir = script_dir / "logs"
    
    # Fallback to user's home directory
    if not log_dir.exists():
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError):
            log_dir = Path.home() / ".dosidicus" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
    
    return log_dir


def setup_logging(level: int = logging.DEBUG) -> logging.Logger:
    """
    Setup logging with both file and console handlers.
    
    Returns the configured logger.
    """
    log_dir = get_log_directory()
    
    # Create timestamped log file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"brain_designer_{timestamp}.log"
    
    # Also maintain a "latest" log
    latest_log = log_dir / "brain_designer_latest.log"
    
    # Configure root logger
    logger = logging.getLogger("brain_designer")
    logger.setLevel(level)
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # File handler - detailed logging
    file_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # Also write to latest log (overwrite mode)
    latest_handler = logging.FileHandler(latest_log, mode='w', encoding='utf-8')
    latest_handler.setLevel(logging.DEBUG)
    latest_handler.setFormatter(file_formatter)
    logger.addHandler(latest_handler)
    
    # Console handler - less verbose
    console_formatter = logging.Formatter(
        '%(levelname)s: %(message)s'
    )
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # Log startup
    logger.info("=" * 60)
    logger.info("Brain Designer Started")
    logger.info(f"Log file: {log_file}")
    logger.info(f"Python version: {sys.version}")
    logger.info("=" * 60)
    
    return logger


def get_logger(name: str = "brain_designer") -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)


class CrashReporter:
    """
    Handles uncaught exceptions and creates crash reports.
    """
    
    def __init__(self, log_dir: Optional[Path] = None):
        self.log_dir = log_dir or get_log_directory()
        self.logger = get_logger()
        self._original_excepthook = sys.excepthook
        self._error_dialog_callback: Optional[Callable] = None
    
    def install(self):
        """Install the crash reporter as the global exception handler."""
        sys.excepthook = self._handle_exception
        self.logger.debug("Crash reporter installed")
    
    def uninstall(self):
        """Restore the original exception handler."""
        sys.excepthook = self._original_excepthook
    
    def set_error_dialog_callback(self, callback: Callable[[str, str], None]):
        """
        Set a callback for showing error dialogs.
        
        Callback signature: callback(title: str, message: str)
        """
        self._error_dialog_callback = callback
    
    def _handle_exception(self, exc_type, exc_value, exc_traceback):
        """Handle uncaught exceptions."""
        # Don't handle KeyboardInterrupt
        if issubclass(exc_type, KeyboardInterrupt):
            self._original_excepthook(exc_type, exc_value, exc_traceback)
            return
        
        # Create crash report
        crash_file = self._write_crash_report(exc_type, exc_value, exc_traceback)
        
        # Log the error
        self.logger.critical(
            "Uncaught exception",
            exc_info=(exc_type, exc_value, exc_traceback)
        )
        
        # Show error dialog if callback is set
        if self._error_dialog_callback:
            error_msg = (
                f"An unexpected error occurred:\n\n"
                f"{exc_type.__name__}: {exc_value}\n\n"
                f"A crash report has been saved to:\n{crash_file}\n\n"
                f"Please report this issue with the crash report."
            )
            try:
                self._error_dialog_callback("Brain Designer - Crash", error_msg)
            except Exception:
                pass  # Don't let dialog errors cause more problems
        
        # Call original handler to print to stderr
        self._original_excepthook(exc_type, exc_value, exc_traceback)
    
    def _write_crash_report(self, exc_type, exc_value, exc_traceback) -> Path:
        """Write a detailed crash report to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        crash_file = self.log_dir / f"crash_{timestamp}.txt"
        
        with open(crash_file, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("BRAIN DESIGNER CRASH REPORT\n")
            f.write("=" * 60 + "\n\n")
            
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            f.write(f"Python Version: {sys.version}\n")
            f.write(f"Platform: {sys.platform}\n\n")
            
            f.write("-" * 40 + "\n")
            f.write("EXCEPTION\n")
            f.write("-" * 40 + "\n")
            f.write(f"Type: {exc_type.__name__}\n")
            f.write(f"Message: {exc_value}\n\n")
            
            f.write("-" * 40 + "\n")
            f.write("TRACEBACK\n")
            f.write("-" * 40 + "\n")
            f.write("".join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
            f.write("\n")
            
            f.write("-" * 40 + "\n")
            f.write("SYSTEM INFO\n")
            f.write("-" * 40 + "\n")
            f.write(f"Executable: {sys.executable}\n")
            f.write(f"Working Directory: {os.getcwd()}\n")
            f.write(f"Script: {sys.argv[0] if sys.argv else 'Unknown'}\n")
            
            # Try to get PyQt5 version
            try:
                from PyQt5.QtCore import QT_VERSION_STR, PYQT_VERSION_STR
                f.write(f"Qt Version: {QT_VERSION_STR}\n")
                f.write(f"PyQt5 Version: {PYQT_VERSION_STR}\n")
            except ImportError:
                f.write("PyQt5: Not available\n")
        
        return crash_file


def log_exceptions(logger: Optional[logging.Logger] = None):
    """
    Decorator to log exceptions from a function.
    
    Usage:
        @log_exceptions()
        def my_function():
            ...
    """
    if logger is None:
        logger = get_logger()
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.exception(f"Exception in {func.__name__}: {e}")
                raise
        return wrapper
    return decorator


def safe_call(func: Callable, *args, default=None, logger: Optional[logging.Logger] = None, **kwargs):
    """
    Safely call a function, logging any exceptions.
    
    Returns the default value if an exception occurs.
    """
    if logger is None:
        logger = get_logger()
    
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.warning(f"Safe call failed for {func.__name__}: {e}")
        return default


class OperationLogger:
    """
    Context manager for logging operations with timing.
    
    Usage:
        with OperationLogger("Loading design"):
            design = load_design(path)
    """
    
    def __init__(self, operation_name: str, logger: Optional[logging.Logger] = None):
        self.operation_name = operation_name
        self.logger = logger or get_logger()
        self.start_time = None
    
    def __enter__(self):
        self.start_time = datetime.now()
        self.logger.debug(f"Starting: {self.operation_name}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = (datetime.now() - self.start_time).total_seconds()
        
        if exc_type is None:
            self.logger.debug(f"Completed: {self.operation_name} ({elapsed:.3f}s)")
        else:
            self.logger.error(
                f"Failed: {self.operation_name} ({elapsed:.3f}s) - {exc_type.__name__}: {exc_val}"
            )
        
        # Don't suppress exceptions
        return False


def cleanup_old_logs(max_logs: int = 20, max_crashes: int = 10):
    """Remove old log and crash files, keeping the most recent."""
    log_dir = get_log_directory()
    logger = get_logger()
    
    try:
        # Cleanup regular logs
        log_files = sorted(
            log_dir.glob("brain_designer_2*.log"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        for old_log in log_files[max_logs:]:
            old_log.unlink()
            logger.debug(f"Removed old log: {old_log.name}")
        
        # Cleanup crash reports
        crash_files = sorted(
            log_dir.glob("crash_*.txt"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        for old_crash in crash_files[max_crashes:]:
            old_crash.unlink()
            logger.debug(f"Removed old crash report: {old_crash.name}")
            
    except Exception as e:
        logger.warning(f"Error cleaning up old logs: {e}")


# Global crash reporter instance
_crash_reporter: Optional[CrashReporter] = None


def initialize_error_handling() -> CrashReporter:
    """Initialize the global error handling system."""
    global _crash_reporter
    
    # Setup logging first
    setup_logging()
    
    # Create and install crash reporter
    _crash_reporter = CrashReporter()
    _crash_reporter.install()
    
    # Cleanup old logs
    cleanup_old_logs()
    
    return _crash_reporter


def get_crash_reporter() -> Optional[CrashReporter]:
    """Get the global crash reporter instance."""
    return _crash_reporter
