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

# Add the base_path to sys.path so we can find the designer modules
if base_path not in sys.path:
    sys.path.insert(0, base_path)

def launch_brain_designer_process():
    """Launch the Brain Designer window in a separate process."""
    
    # 1. Initialize QApplication FIRST so we can show error dialogs if imports fail
    try:
        from PyQt5.QtWidgets import QApplication, QMessageBox
        app = QApplication(sys.argv)
        app.setStyle('Fusion')
    except ImportError:
        print("CRITICAL: PyQt5 is missing. Cannot launch GUI.")
        return

    try:
        # 2. Correct Import: Point to the actual location of the class
        # (It is in 'designer.designer_window', NOT 'src.brain_designer')
        from designer_window import BrainDesignerWindow

        # 3. Create and show the window
        window = BrainDesignerWindow()
        window.show()
        
        # 4. Execute the application loop
        sys.exit(app.exec_())
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        
        # Now this will work because 'app' is guaranteed to exist
        QMessageBox.critical(None, "Brain Designer Error", 
                             f"Could not start Brain Designer:\n\n{e}\n\n"
                             f"Check console for full traceback.")

if __name__ == "__main__":
    multiprocessing.freeze_support()
    launch_brain_designer_process()