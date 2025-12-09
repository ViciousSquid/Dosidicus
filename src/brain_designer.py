#!/usr/bin/env python3
"""
Brain Designer - Visual Neural Network Designer for Dosidicus-2

Launch the brain designer GUI application with error handling and logging.
"""

import sys
import os
import shutil
import argparse

# Ensure the designer package can be found
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)


def perform_cleanup_and_exit():
    """Recursively delete __pycache__ directories."""
    print("🧹 Cleaning environment...")
    root_dir = os.path.dirname(os.path.abspath(__file__))
    
    deleted_count = 0
    
    for root, dirs, files in os.walk(root_dir, topdown=True):
        # Filter and remove specific directories
        for name in list(dirs):
            if name == '__pycache__':
                path = os.path.join(root, name)
                try:
                    shutil.rmtree(path)
                    print(f"   Deleted: {path}")
                    dirs.remove(name)  # Prevent os.walk from trying to enter this dir
                    deleted_count += 1
                except Exception as e:
                    print(f"   ❌ Failed to delete {path}: {e}")
                    
    print(f"✨ Cleanup complete. Removed {deleted_count} directories.")
    sys.exit(0)


def show_error_dialog(title: str, message: str):
    """Show an error dialog using PyQt5 if available, otherwise print."""
    try:
        from PyQt5.QtWidgets import QApplication, QMessageBox
        
        # Create app if needed (for showing dialog before main app starts)
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec_()
    except Exception:
        # Fallback to console
        print(f"\n{'='*60}")
        print(f"ERROR: {title}")
        print('='*60)
        print(message)
        print('='*60 + "\n")


def check_dependencies():
    """Check that required dependencies are available."""
    missing = []
    
    try:
        import PyQt5
    except ImportError:
        missing.append("PyQt5")
    
    if missing:
        msg = (
            f"Missing required dependencies:\n\n"
            f"  {', '.join(missing)}\n\n"
            f"Please install with:\n"
            f"  pip install {' '.join(missing)}"
        )
        show_error_dialog("Missing Dependencies", msg)
        sys.exit(1)


def main():
    """Main entry point with full error handling."""
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Brain Designer - Visual Neural Network Designer")
    parser.add_argument('-c', '--clean', action='store_true',
                       help='Clean __pycache__ folders from designer directory before starting')
    
    # Use parse_known_args so we don't choke if Qt arguments are passed implicitly
    args, _ = parser.parse_known_args()

    # Perform cleanup if requested
    if args.clean:
        perform_cleanup_and_exit()
    
    # Check dependencies first
    check_dependencies()
    
    # Import logging after dependency check
    from designer_logging import (
        initialize_error_handling, 
        get_logger,
        OperationLogger
    )
    
    # Initialize error handling and logging
    crash_reporter = initialize_error_handling()
    logger = get_logger()
    
    # Set up error dialog callback
    crash_reporter.set_error_dialog_callback(show_error_dialog)
    
    logger.info("Starting Brain Designer application")
    
    try:
        from PyQt5.QtWidgets import QApplication
        from PyQt5.QtGui import QColor, QPalette
        from PyQt5.QtCore import Qt
        
        with OperationLogger("Creating QApplication"):
            app = QApplication(sys.argv)
            app.setApplicationName("Brain Designer (Beta)")
            app.setApplicationVersion("1.1.0")
        
        with OperationLogger("Applying theme"):
            # Light theme setup
            app.setStyle('Fusion')
            
            palette = app.palette()
            palette.setColor(QPalette.Window, QColor(240, 240, 245))
            palette.setColor(QPalette.WindowText, QColor(40, 40, 50))
            palette.setColor(QPalette.Base, QColor(255, 255, 255))
            palette.setColor(QPalette.AlternateBase, QColor(245, 245, 250))
            palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 230))
            palette.setColor(QPalette.ToolTipText, QColor(40, 40, 50))
            palette.setColor(QPalette.Text, QColor(40, 40, 50))
            palette.setColor(QPalette.Button, QColor(240, 240, 245))
            palette.setColor(QPalette.ButtonText, QColor(40, 40, 50))
            palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
            palette.setColor(QPalette.Highlight, QColor(70, 130, 200))
            palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
            app.setPalette(palette)
        
        with OperationLogger("Importing designer window"):
            from designer_window import BrainDesignerWindow
        
        with OperationLogger("Creating main window"):
            window = BrainDesignerWindow()
        
        logger.info("Showing main window")
        window.show()
        
        logger.info("Entering event loop")
        exit_code = app.exec_()
        
        logger.info(f"Application exited with code {exit_code}")
        sys.exit(exit_code)
        
    except ImportError as e:
        logger.critical(f"Import error: {e}")
        show_error_dialog(
            "Import Error",
            f"Failed to import required module:\n\n{e}\n\n"
            f"Please ensure all dependencies are installed."
        )
        sys.exit(1)
        
    except Exception as e:
        logger.critical(f"Startup error: {e}", exc_info=True)
        show_error_dialog(
            "Startup Error",
            f"Failed to start Brain Designer:\n\n{e}\n\n"
            f"Check the logs folder for details."
        )
        sys.exit(1)


if __name__ == '__main__':
    main()