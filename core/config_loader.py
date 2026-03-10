"""
Load and save extraction field settings from config/settings.json.
Used by the Settings window and by the document processor / prompt builder.
"""
import json
import os

# Default field keys (all enabled). Must match options in settings UI.
DEFAULT_CONFIG = {
    "invoice_fields": [
        "invoice_number",
        "invoice_date",
        "supplier_name",
        "supplier_gstin",
        "buyer_name",
        "buyer_gstin",
        "total_tax",
        "total_invoice_value",
    ],
    "invoice_table_fields": [
        "item_description",
        "hsn_code",
        "quantity",
        "uom",
        "unit_price",
        "discount",
        "taxable_value",
        "gst_rate",
        "tax_amount",
        "total_value",
    ],
    "challan_fields": [
        "challan_number",
        "challan_date",
        "party_name",
        "hsn_code",
    ],
    "challan_table_fields": [
        "fabric_name",
        "fd_number",
        "piece_number",
        "challan_mtr",
        "dispatch_mtr",
        "grey_received_date",
        "grey_challan_number",
        "beam",
    ],
}


def get_config_path(base_dir: str) -> str:
    """Return path to config/settings.json under base_dir."""
    return os.path.join(base_dir, "config", "settings.json")


def load_config(base_dir: str) -> dict:
    """
    Load settings from config/settings.json.
    Returns DEFAULT_CONFIG if file is missing or invalid.
    """
    path = get_config_path(base_dir)
    if not os.path.isfile(path):
        return DEFAULT_CONFIG.copy()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Ensure all keys exist
        for key in DEFAULT_CONFIG:
            if key not in data or not isinstance(data[key], list):
                data[key] = list(DEFAULT_CONFIG[key])
        return data
    except Exception:
        return DEFAULT_CONFIG.copy()


def save_config(base_dir: str, config: dict) -> None:
    """Save settings to config/settings.json. Creates config dir if needed."""
    path = get_config_path(base_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
