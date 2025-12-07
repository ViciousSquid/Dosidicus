# launch_designer.py
import sys
import os

# Add the tools directory to path so brain_designer can find its imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '_internal', 'tools'))

# Import and run the designer
from brain_designer import main

if __name__ == '__main__':
    main()