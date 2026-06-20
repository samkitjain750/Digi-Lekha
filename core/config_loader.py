"""
Load and save extraction field settings from config/settings.json.
Uses paths module for bundle vs writable location when frozen.
"""
import json
import os

from . import paths as _paths

# Default config: delivery challan only, with piece and dispatch meters.
DEFAULT_CONFIG = {
    "invoice_fields": [],
    "invoice_table_fields": [],
    "challan_fields": [],
    "challan_table_fields": [
        "piece_number",
        "grey_mtrs",
        "dispatch_mtr",
    ],
}


def get_config_path(base_dir: str = None) -> str:
    """Return path to config/settings.json. When frozen uses paths; else base_dir."""
    if _paths.is_frozen():
        return _paths.get_settings_path(for_read=True)
    base = base_dir or _paths.get_resource_base()
    return os.path.join(base, "config", "settings.json")


def load_config(base_dir: str = None) -> dict:
    """
    Load settings from config/settings.json (writable or bundled when frozen).
    Returns DEFAULT_CONFIG if file is missing or invalid.
    """
    path = get_config_path(base_dir)
    if not os.path.isfile(path):
        return DEFAULT_CONFIG.copy()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for key in DEFAULT_CONFIG:
            if key not in data or not isinstance(data[key], list):
                data[key] = list(DEFAULT_CONFIG[key])
        return data
    except Exception:
        return DEFAULT_CONFIG.copy()


def save_config(base_dir: str = None, config: dict = None) -> None:
    """Save settings to config/settings.json (writable location when frozen)."""
    if config is None:
        return
    if _paths.is_frozen():
        path = os.path.join(_paths.get_config_dir(writable=True), "settings.json")
    else:
        path = os.path.join(base_dir or _paths.get_resource_base(), "config", "settings.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
