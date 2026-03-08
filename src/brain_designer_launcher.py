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
    # Build command line args
    if debug_mode:
        if '-d' not in sys.argv:
            sys.argv.append('-d')
    
    # Import and run the designer's main function
    from src.brain_designer import main as designer_main
    designer_main()