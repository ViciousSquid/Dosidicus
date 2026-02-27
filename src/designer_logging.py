"""
Designer Logging - Centralized logging for Brain Designer

Provides logging utilities that can be enabled/disabled based on debug mode.
"""

import logging
import os
import sys
import traceback
from datetime import datetime
from contextlib import contextmanager


# Global logger instance
_logger = None
_logging_enabled = False


class NullHandler(logging.Handler):
    """A handler that does nothing - used when logging is disabled."""
    def emit(self, record):
        pass


class CrashReporter:
    """Handles crash reporting and error dialogs."""
    
    def __init__(self, enable_logging: bool = False):
        self._error_dialog_callback = None
        self._logging_enabled = enable_logging
    
    def set_error_dialog_callback(self, callback):
        """Set the callback function for showing error dialogs."""
        self._error_dialog_callback = callback
    
    def report_crash(self, exc_type, exc_value, exc_tb):
        """Report a crash - log it and optionally show dialog."""
        error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
        
        if self._logging_enabled:
            logger = get_logger()
            logger.critical(f"Crash reported:\n{error_msg}")
        
        if self._error_dialog_callback:
            self._error_dialog_callback(
                "Critical Error",
                f"An unexpected error occurred:\n\n{exc_value}"
            )


def get_log_directory() -> str:
    """Get the directory for log files."""
    # Logs go in the root folder's logs/ directory (one level up from src/)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(script_dir)  # Go up one level from src/
    log_dir = os.path.join(parent_dir, 'logs')
    return log_dir


def initialize_error_handling(enable_logging: bool = False) -> CrashReporter:
    """
    Initialize error handling and optionally set up logging.
    
    Args:
        enable_logging: If True, creates log files and enables logging.
                       If False, logging calls are no-ops.
    
    Returns:
        CrashReporter instance
    """
    global _logger, _logging_enabled
    _logging_enabled = enable_logging
    
    # Create logger
    _logger = logging.getLogger('brain_designer')
    _logger.handlers.clear()  # Remove any existing handlers
    
    if enable_logging:
        # Set up actual logging
        _logger.setLevel(logging.DEBUG)
        
        # Create logs directory
        log_dir = get_log_directory()
        os.makedirs(log_dir, exist_ok=True)
        
        # Create file handler with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = os.path.join(log_dir, f'designer_{timestamp}.log')
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        # Create console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        _logger.addHandler(file_handler)
        _logger.addHandler(console_handler)
        
        _logger.info(f"Logging initialized. Log file: {log_file}")
    else:
        # Disable logging - use null handler
        _logger.setLevel(logging.CRITICAL + 1)  # Effectively disable all logging
        _logger.addHandler(NullHandler())
    
    # Create crash reporter
    crash_reporter = CrashReporter(enable_logging)
    
    # Install global exception handler
    def exception_handler(exc_type, exc_value, exc_tb):
        if exc_type != KeyboardInterrupt:
            crash_reporter.report_crash(exc_type, exc_value, exc_tb)
        sys.__excepthook__(exc_type, exc_value, exc_tb)
    
    sys.excepthook = exception_handler
    
    return crash_reporter


def get_logger(name: str = None) -> logging.Logger:
    """
    Get a logger instance.
    
    Args:
        name: Optional sub-logger name. If None, returns the main designer logger.
    
    Returns:
        Logger instance
    """
    global _logger
    
    if _logger is None:
        # Initialize with logging disabled by default
        initialize_error_handling(enable_logging=False)
    
    if name:
        return _logger.getChild(name)
    return _logger


@contextmanager
def OperationLogger(operation_name: str, logger: logging.Logger = None):
    """
    Context manager for logging operations with timing.
    
    Usage:
        with OperationLogger("Loading data"):
            load_data()
    
    Args:
        operation_name: Name of the operation being performed
        logger: Optional specific logger to use
    """
    if logger is None:
        logger = get_logger()
    
    if not _logging_enabled:
        # Just execute the block without logging
        yield
        return
    
    start_time = datetime.now()
    logger.debug(f"Starting: {operation_name}")
    
    try:
        yield
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.debug(f"Completed: {operation_name} ({elapsed:.3f}s)")
    except Exception as e:
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.error(f"Failed: {operation_name} ({elapsed:.3f}s) - {e}")
        raise


def log_exceptions(func):
    """
    Decorator to log exceptions from a function.
    
    Usage:
        @log_exceptions
        def my_function():
            ...
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if _logging_enabled:
                logger = get_logger()
                logger.error(f"Exception in {func.__name__}: {e}", exc_info=True)
            raise
    return wrapper


def safe_call(func, *args, default=None, **kwargs):
    """
    Safely call a function, returning default on exception.
    
    Args:
        func: Function to call
        *args: Positional arguments
        default: Value to return on exception
        **kwargs: Keyword arguments
    
    Returns:
        Function result or default value
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        if _logging_enabled:
            logger = get_logger()
            logger.warning(f"safe_call caught exception in {func.__name__}: {e}")
        return default
