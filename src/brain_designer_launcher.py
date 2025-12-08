# src/brain_designer_launcher.py
# This file exists solely to safely launch Brain Designer in a separate process

import multiprocessing
import sys
import os

# Fix path issues when running from PyInstaller bundle
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.abspath(os.path.join(os.path.dirname(__file__)))

if base_path not in sys.path:
    sys.path.insert(0, base_path)

def launch_brain_designer_process():
    """Launch the Brain Designer window in a separate process."""
    try:
        from PyQt5.QtWidgets import QApplication
        from src.brain_designer import BrainDesignerWindow

        app = QApplication(sys.argv)
        app.setStyle('Fusion')  # Optional: matches main app style
        
        window = BrainDesignerWindow()
        window.show()
        
        sys.exit(app.exec_())
    except Exception as e:
        import traceback
        print("Failed to launch Brain Designer:")
        traceback.print_exc()
        # Show error dialog if possible
        try:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(None, "Brain Designer Error", f"Could not start Brain Designer:\n\n{e}")
        except:
            pass


if __name__ == "__main__":
    multiprocessing.freeze_support()
    launch_brain_designer_process()