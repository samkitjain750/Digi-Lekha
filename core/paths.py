"""
Path resolution for development vs PyInstaller frozen bundle.
- Resource base: where to read bundled config/assets (sys._MEIPASS when frozen).
- Writable base: where to store api_key.json and settings (app data dir when frozen).
"""
import os
import sys

APP_NAME = "Digi Lekha"


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def get_resource_base() -> str:
    """
    Base path for reading bundled resources (config, assets).
    When frozen: sys._MEIPASS. Otherwise: project root (parent of main.py directory).
    """
    if is_frozen():
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_writable_base() -> str:
    """
    Base path for writing config (api_key.json, settings.json).
    When frozen: platform-specific application data directory. Otherwise: project root.
    """
    if not is_frozen():
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    elif sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.path.expanduser("~")
    app_dir = os.path.join(base, APP_NAME)
    os.makedirs(app_dir, exist_ok=True)
    return app_dir


def get_config_dir(writable: bool = False) -> str:
    """Config directory. writable=True for saving (api key, settings)."""
    base = get_writable_base() if writable else get_resource_base()
    path = os.path.join(base, "config")
    if writable:
        os.makedirs(path, exist_ok=True)
    return path


def get_api_key_path() -> str:
    """Path to config/api_key.json (always in writable location)."""
    return os.path.join(get_config_dir(writable=True), "api_key.json")


def get_settings_path(for_read: bool = True) -> str:
    """
    Path to config/settings.json.
    for_read: try writable first (user may have saved), then resource (bundle default).
    """
    writable = get_config_dir(writable=True)
    writable_file = os.path.join(writable, "settings.json")
    if for_read and os.path.isfile(writable_file):
        return writable_file
    resource_file = os.path.join(get_config_dir(writable=False), "settings.json")
    return resource_file if os.path.isfile(resource_file) else writable_file


def get_assets_base() -> str:
    """Base path for assets (e.g. icons). Resource when frozen."""
    return os.path.join(get_resource_base(), "assets")
