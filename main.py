"""
Digi Lekha — entry point.
Launches the CustomTkinter UI. When packaged (PyInstaller), uses bundled config and first-run API key setup.
"""
import os
import sys

# Ensure project root is on path (development)
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

try:
    import customtkinter as ctk
except ImportError:
    ctk = None

from core import paths as _paths
from core.openai_extractor import get_openai_api_key, save_openai_api_key
from ui.api_key_setup import ApiKeySetupDialog
from ui.main_window import MainWindow


def _bring_to_front(window):
    """Raise window and force it on top (fixes macOS .app launching with no visible window)."""
    try:
        window.update_idletasks()
        window.lift()
        window.attributes("-topmost", True)
        window.after(150, lambda: window.attributes("-topmost", False))
        window.focus_force()
    except Exception:
        pass


def main():
    if ctk is None:
        raise RuntimeError("Install CustomTkinter: pip install customtkinter")
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")
    root = ctk.CTk()
    # Hide root off-screen so dialog/main window can show (withdraw() can hide children on macOS .app)
    root.geometry("1x1+-10000+-10000")
    base = _paths.get_resource_base()
    if not get_openai_api_key(base):
        def on_saved(key: str):
            save_openai_api_key(key)
        dialog = ApiKeySetupDialog(root, on_saved=on_saved)
        root.after(100, lambda: _bring_to_front(dialog))
        dialog.wait_window()
        if not get_openai_api_key(base):
            root.destroy()
            return
    root.destroy()
    app = MainWindow()
    _bring_to_front(app.root)
    app.run()


if __name__ == "__main__":
    main()
