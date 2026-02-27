"""
Brain Designer Launcher - Spawns the designer in a subprocess

This module provides a function to launch the Brain Designer tool
from the main game process, optionally passing debug mode.
"""

import sys
import os


def launch_brain_designer_process(debug_mode: bool = False):
    """
    Entry point for Brain Designer when launched as a subprocess.
    
    Args:
        debug_mode: If True, enables logging in the designer
    """
    # Everything is in src/ folder
    script_dir = os.path.dirname(os.path.abspath(__file__))  # src/
    
    # Ensure src/ is in path
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    
    # Build command line args
    if debug_mode:
        if '-d' not in sys.argv:
            sys.argv.append('-d')
    
    # Import and run the designer's main function
    from brain_designer import main as designer_main
    designer_main()
