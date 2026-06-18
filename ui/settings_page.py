"""
Extraction Settings page: toggles for invoice/challan fields. Saves to config/settings.json.
"""
import os
import sys

if __name__ != "__main__":
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)

import customtkinter as ctk
from core.config_loader import load_config, save_config, DEFAULT_CONFIG

WORKSPACE_BG = "#F8FAFC"
BG_CARD = "#FFFFFF"

CHALLAN_TABLE_FIELDS = {
    "piece_number": "Piece No",
    "dispatch_mtr": "Finished Mtrs (Dispatch Mtr)",
}


class SettingsPage(ctk.CTkFrame):
    """Extraction toggles grouped by document type. on_save(config) when user saves."""

    def __init__(self, parent, base_dir: str, **kwargs):
        super().__init__(parent, fg_color=WORKSPACE_BG, **kwargs)
        self.base_dir = base_dir
        self.config = load_config(base_dir)
        self.on_save = None
        self._switches = {}
        self._save_after_id = None
        self._build()
        self.bind("<Destroy>", self._on_destroy, add="+")

    def _build(self):
        inner = ctk.CTkScrollableFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=32, pady=32)
        ctk.CTkLabel(inner, text="Extraction Settings", font=ctk.CTkFont(size=24, weight="bold")).pack(anchor="w", pady=(0, 24))

        def add_section(title: str, field_labels: dict, config_key: str):
            card = ctk.CTkFrame(inner, fg_color=BG_CARD, corner_radius=12)
            card.pack(fill="x", pady=(0, 16))
            card_inner = ctk.CTkFrame(card, fg_color="transparent")
            card_inner.pack(fill="x", padx=24, pady=24)
            ctk.CTkLabel(card_inner, text=title, font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", pady=(0, 12))
            selected = set(self.config.get(config_key, []))
            for key, label in field_labels.items():
                var = ctk.BooleanVar(value=key in selected)
                sw = ctk.CTkSwitch(card_inner, text=label, variable=var)
                sw.pack(anchor="w", pady=4)
                self._switches[(config_key, key)] = var

        add_section("Delivery challan table fields", CHALLAN_TABLE_FIELDS, "challan_table_fields")

        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(anchor="w", pady=16)
        self.btn_save = ctk.CTkButton(btn_row, text="Save settings", corner_radius=8, height=40, command=self._save)
        self.btn_save.pack(side="left")
        self.save_message = ctk.CTkLabel(btn_row, text="", font=ctk.CTkFont(size=14), text_color="#22C55E", anchor="w")
        self.save_message.pack(side="left", padx=16)

    def _save(self):
        cfg = {k: [] for k in DEFAULT_CONFIG}
        for (config_key, key), var in self._switches.items():
            if var.get():
                cfg[config_key].append(key)
        save_config(self.base_dir, cfg)
        self.config = cfg
        if self.on_save:
            self.on_save(cfg)
        self.save_message.configure(text="Settings saved.")
        self.btn_save.configure(text="Saved!")
        if self._save_after_id:
            try:
                self.after_cancel(self._save_after_id)
            except Exception:
                pass
        self._save_after_id = self.after(2500, self._reset_save_ui)

    def _reset_save_ui(self):
        self._save_after_id = None
        if not self.winfo_exists():
            return
        self.btn_save.configure(text="Save settings")
        self.save_message.configure(text="")

    def get_config(self):
        return self.config

    def _on_destroy(self, event):
        # Prevent pending after-callback from firing on a destroyed widget.
        if event.widget is not self:
            return
        if self._save_after_id:
            try:
                self.after_cancel(self._save_after_id)
            except Exception:
                pass
            self._save_after_id = None
