"""
Settings window: checkboxes for extraction fields grouped by document type.
Saves to config/settings.json.
"""
import sys
import os

# Add project root so we can import core
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config_loader import load_config, save_config, DEFAULT_CONFIG, get_config_path

try:
    import customtkinter as ctk
except ImportError:
    ctk = None

# Human-readable labels for each field key (for checkboxes)
INVOICE_FIELD_LABELS = {
    "invoice_number": "Invoice Number",
    "invoice_date": "Invoice Date",
    "supplier_name": "Supplier Name",
    "supplier_gstin": "Supplier GSTIN",
    "buyer_name": "Buyer Name",
    "buyer_gstin": "Buyer GSTIN",
    "total_tax": "Total Tax",
    "total_invoice_value": "Total Invoice Value",
}

INVOICE_TABLE_FIELD_LABELS = {
    "item_description": "Item Description",
    "hsn_code": "HSN Code",
    "quantity": "Quantity",
    "uom": "UOM",
    "unit_price": "Unit Price",
    "discount": "Discount",
    "taxable_value": "Taxable Value",
    "gst_rate": "GST Rate",
    "tax_amount": "Tax Amount",
    "total_value": "Total Value",
}

CHALLAN_FIELD_LABELS = {
    "challan_number": "Challan Number",
    "challan_date": "Challan Date",
    "party_name": "Party Name",
    "hsn_code": "HSN Code",
}

CHALLAN_TABLE_FIELD_LABELS = {
    "fabric_name": "Fabric Name",
    "fd_number": "FD Number",
    "piece_number": "Piece Number",
    "challan_mtr": "Challan MTR",
    "dispatch_mtr": "Dispatch MTR",
    "grey_received_date": "Grey Received Date",
    "grey_challan_number": "Grey Challan Number",
    "beam": "Beam",
}


def _make_checkbox_section(parent, title: str, field_labels: dict, selected_keys: list):
    """Create a labeled section with checkboxes. Returns (frame, dict of key -> BooleanVar)."""
    frame = ctk.CTkFrame(parent, fg_color="transparent")
    ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(weight="bold"), anchor="w").pack(anchor="w", pady=(0, 8))
    vars_map = {}
    for key, label in field_labels.items():
        var = ctk.BooleanVar(value=key in selected_keys)
        cb = ctk.CTkCheckBox(frame, text=label, variable=var)
        cb.pack(anchor="w", pady=2)
        vars_map[key] = var
    return frame, vars_map


def open_settings_window(base_dir: str, on_save=None):
    """
    Open the Settings window (CustomTkinter). on_save(config_dict) is called after saving.
    If CustomTkinter is not available, falls back to a message.
    """
    if ctk is None:
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo("Settings", "Install CustomTkinter: pip install customtkinter")
            root.destroy()
        except Exception:
            pass
        return

    config = load_config(base_dir)
    win = ctk.CTkToplevel()
    win.title("Settings — Extraction Fields")
    win.geometry("480x620")
    win.transient()

    scroll = ctk.CTkScrollableFrame(win, fg_color="transparent")
    scroll.pack(fill="both", expand=True, padx=20, pady=20)

    # Invoice header
    inv_frame, inv_vars = _make_checkbox_section(
        scroll,
        "Invoice fields",
        INVOICE_FIELD_LABELS,
        config.get("invoice_fields", []),
    )
    inv_frame.pack(fill="x", pady=(0, 16))

    # Invoice table
    inv_table_frame, inv_table_vars = _make_checkbox_section(
        scroll,
        "Invoice table fields",
        INVOICE_TABLE_FIELD_LABELS,
        config.get("invoice_table_fields", []),
    )
    inv_table_frame.pack(fill="x", pady=(0, 16))

    # Challan header
    ch_frame, ch_vars = _make_checkbox_section(
        scroll,
        "Delivery challan fields",
        CHALLAN_FIELD_LABELS,
        config.get("challan_fields", []),
    )
    ch_frame.pack(fill="x", pady=(0, 16))

    # Challan table
    ch_table_frame, ch_table_vars = _make_checkbox_section(
        scroll,
        "Delivery challan table fields",
        CHALLAN_TABLE_FIELD_LABELS,
        config.get("challan_table_fields", []),
    )
    ch_table_frame.pack(fill="x", pady=(0, 16))

    def collect():
        return {
            "invoice_fields": [k for k, v in inv_vars.items() if v.get()],
            "invoice_table_fields": [k for k, v in inv_table_vars.items() if v.get()],
            "challan_fields": [k for k, v in ch_vars.items() if v.get()],
            "challan_table_fields": [k for k, v in ch_table_vars.items() if v.get()],
        }

    def save():
        new_config = collect()
        save_config(base_dir, new_config)
        if on_save:
            on_save(new_config)
        win.destroy()

    btn_frame = ctk.CTkFrame(win, fg_color="transparent")
    btn_frame.pack(fill="x", padx=20, pady=(0, 20))
    ctk.CTkButton(btn_frame, text="Save", command=save, corner_radius=8).pack(side="right", padx=5)
    ctk.CTkButton(btn_frame, text="Cancel", command=win.destroy, corner_radius=8, fg_color="gray").pack(side="right")


if __name__ == "__main__":
    # Quick test
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    open_settings_window(base)
    import customtkinter as ctk
    ctk.CTk().mainloop()
