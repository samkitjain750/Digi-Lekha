"""
AI Document Extractor — entry point.
Launches the CustomTkinter UI. Loads config from config/settings.json on startup.
"""
import os
import sys

# Ensure project root is on path
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from ui.main_window import main

if __name__ == "__main__":
    main()
