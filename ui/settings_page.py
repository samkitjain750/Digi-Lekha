"""
Settings: Sheet1 column toggles, Master Data, and OpenAI API key.
Master Data.xls drives Piece_Check verification and Sheet1 '-' display.
"""
import os
import sys
from tkinter import filedialog, messagebox

if __name__ != "__main__":
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)

import customtkinter as ctk
from core.config_loader import load_config, save_config, DEFAULT_CONFIG
from core.dye_master import (
    export_master_excel,
    format_help_text as master_format_help_text,
    get_master_stats,
    import_dye_master_excel,
    reset_matched_to_open,
)
from core.openai_extractor import (
    get_openai_api_key,
    get_openai_model,
    save_openai_api_key,
)

WORKSPACE_BG = "#F8FAFC"
BG_CARD = "#FFFFFF"
PRIMARY = "#3B82F6"

CHALLAN_TABLE_FIELDS = {
    "piece_number": "Piece No",
    "grey_mtrs": "Grey Mtrs",
    "dispatch_mtr": "Finished Mtrs (Dispatch Mtr)",
}


def _mask_api_key(key: str) -> str:
    key = (key or "").strip()
    if not key:
        return ""
    if len(key) <= 8:
        return "••••" + key[-2:]
    return key[:4] + "••••••••" + key[-4:]


class SettingsPage(ctk.CTkFrame):
    """Sheet1 columns, Master Data, and API key."""

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
        ctk.CTkLabel(
            inner, text="Settings", font=ctk.CTkFont(size=24, weight="bold")
        ).pack(anchor="w", pady=(0, 24))

        self._build_api_section(inner)
        self._build_sheet1_section(inner)
        self._build_master_section(inner)

        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(anchor="w", pady=16)
        self.btn_save = ctk.CTkButton(
            btn_row, text="Save settings", corner_radius=8, height=40, command=self._save
        )
        self.btn_save.pack(side="left")
        self.save_message = ctk.CTkLabel(
            btn_row, text="", font=ctk.CTkFont(size=14), text_color="#22C55E", anchor="w"
        )
        self.save_message.pack(side="left", padx=16)

    def _card(self, parent) -> ctk.CTkFrame:
        card = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=12)
        card.pack(fill="x", pady=(0, 16))
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=24, pady=24)
        return inner

    def _build_api_section(self, parent):
        inner = self._card(parent)
        ctk.CTkLabel(
            inner, text="OpenAI API", font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", pady=(0, 8))
        ctk.CTkLabel(
            inner,
            text="Required for challan extraction. Stored only on this computer.",
            font=ctk.CTkFont(size=13),
            text_color="#64748B",
            wraplength=640,
            justify="left",
            anchor="w",
        ).pack(anchor="w", pady=(0, 12))

        self.api_status = ctk.CTkLabel(
            inner,
            text="",
            font=ctk.CTkFont(size=13),
            text_color="#334155",
            anchor="w",
            justify="left",
        )
        self.api_status.pack(anchor="w", pady=(0, 8))

        self.api_entry = ctk.CTkEntry(
            inner,
            placeholder_text="Paste a new API key to update",
            height=36,
            corner_radius=8,
            show="•",
        )
        self.api_entry.pack(fill="x", pady=(0, 10))

        btns = ctk.CTkFrame(inner, fg_color="transparent")
        btns.pack(anchor="w")
        ctk.CTkButton(
            btns,
            text="Save API key",
            corner_radius=8,
            height=36,
            fg_color=PRIMARY,
            command=self._save_api_key,
        ).pack(side="left")
        ctk.CTkButton(
            btns,
            text="Clear field",
            corner_radius=8,
            height=36,
            fg_color="#64748B",
            hover_color="#475569",
            command=lambda: self.api_entry.delete(0, "end"),
        ).pack(side="left", padx=10)
        self._refresh_api_status()

    def _build_sheet1_section(self, parent):
        inner = self._card(parent)
        ctk.CTkLabel(
            inner,
            text="Sheet1 columns",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(anchor="w", pady=(0, 8))
        ctk.CTkLabel(
            inner,
            text="Choose which columns appear on Sheet1. Quality and Challan No. "
            "are used for Piece_Check only and are not exported.",
            font=ctk.CTkFont(size=13),
            text_color="#64748B",
            wraplength=640,
            justify="left",
            anchor="w",
        ).pack(anchor="w", pady=(0, 12))

        selected = set(self.config.get("challan_table_fields", []))
        for key, label in CHALLAN_TABLE_FIELDS.items():
            var = ctk.BooleanVar(value=key in selected)
            sw = ctk.CTkSwitch(inner, text=label, variable=var)
            sw.pack(anchor="w", pady=4)
            self._switches[("challan_table_fields", key)] = var

    def _build_master_section(self, parent):
        inner = self._card(parent)

        title_row = ctk.CTkFrame(inner, fg_color="transparent")
        title_row.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(
            title_row,
            text="Master Data",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(side="left")
        ctk.CTkButton(
            title_row,
            text="?",
            width=32,
            height=28,
            corner_radius=8,
            fg_color="#64748B",
            hover_color="#475569",
            command=self._show_master_format_help,
        ).pack(side="left", padx=10)

        ctk.CTkLabel(
            inner,
            text=(
                "Upload Master Data.xls (Process Name / Quality Name blocks). "
                "One file verifies piece numbers and sets '-' on Sheet1 "
                "exactly as stored in Master Data."
            ),
            font=ctk.CTkFont(size=13),
            text_color="#64748B",
            wraplength=640,
            justify="left",
            anchor="w",
        ).pack(anchor="w", pady=(0, 12))

        self.master_status = ctk.CTkLabel(
            inner,
            text="",
            font=ctk.CTkFont(size=13),
            text_color="#334155",
            anchor="w",
            justify="left",
        )
        self.master_status.pack(anchor="w", pady=(0, 12))
        self._refresh_master_status()

        btns = ctk.CTkFrame(inner, fg_color="transparent")
        btns.pack(anchor="w")
        ctk.CTkButton(
            btns,
            text="Upload / Append Excel",
            corner_radius=8,
            height=36,
            fg_color=PRIMARY,
            command=lambda: self._upload_master(replace=False),
        ).pack(side="left")
        ctk.CTkButton(
            btns,
            text="Replace all",
            corner_radius=8,
            height=36,
            fg_color="#EF4444",
            hover_color="#DC2626",
            command=lambda: self._upload_master(replace=True),
        ).pack(side="left", padx=10)

        btns2 = ctk.CTkFrame(inner, fg_color="transparent")
        btns2.pack(anchor="w", pady=(10, 0))
        ctk.CTkButton(
            btns2,
            text="Export open pieces",
            corner_radius=8,
            height=36,
            fg_color="#0F766E",
            hover_color="#0D9488",
            command=lambda: self._export_master(status="open"),
        ).pack(side="left")
        ctk.CTkButton(
            btns2,
            text="Export all",
            corner_radius=8,
            height=36,
            fg_color="#475569",
            hover_color="#334155",
            command=lambda: self._export_master(status=None),
        ).pack(side="left", padx=10)
        ctk.CTkButton(
            btns2,
            text="Reset matched → open",
            corner_radius=8,
            height=36,
            fg_color="#D97706",
            hover_color="#B45309",
            command=self._reset_matched,
        ).pack(side="left")

    def _refresh_api_status(self):
        key = get_openai_api_key(self.base_dir)
        model = get_openai_model(self.base_dir)
        if key:
            self.api_status.configure(
                text=f"Key: {_mask_api_key(key)}  |  Model: {model}",
                text_color="#334155",
            )
        else:
            self.api_status.configure(
                text=f"No API key saved.  |  Model: {model}",
                text_color="#DC2626",
            )

    def _save_api_key(self):
        key = (self.api_entry.get() or "").strip()
        if not key:
            messagebox.showwarning(
                "API key",
                "Paste an API key in the field first.",
                parent=self.winfo_toplevel(),
            )
            return
        try:
            save_openai_api_key(key)
            self.api_entry.delete(0, "end")
            self._refresh_api_status()
            messagebox.showinfo(
                "API key saved",
                "OpenAI API key updated for this computer.",
                parent=self.winfo_toplevel(),
            )
        except Exception as e:
            messagebox.showerror(
                "Save failed",
                f"Could not save API key.\n{e}",
                parent=self.winfo_toplevel(),
            )

    def _refresh_master_status(self):
        try:
            stats = get_master_stats()
        except Exception:
            stats = {"total": 0, "open": 0, "matched": 0, "last_import": "", "source_file": ""}
        if not stats.get("total"):
            self.master_status.configure(
                text="No Master Data loaded yet. Upload Master Data.xls once, then append daily."
            )
            return
        self.master_status.configure(
            text=(
                f"Total: {stats['total']}  |  Open: {stats['open']}  |  Matched: {stats['matched']}\n"
                f"Last import: {stats.get('last_import') or '-'}\n"
                f"Source: {stats.get('source_file') or '-'}"
            )
        )

    def _show_master_format_help(self):
        messagebox.showinfo(
            "Master Data Excel format",
            master_format_help_text(),
            parent=self.winfo_toplevel(),
        )

    def _upload_master(self, *, replace: bool):
        if replace:
            ok = messagebox.askyesno(
                "Replace Master Data?",
                "This will DELETE all existing Master Data rows (open and matched),\n"
                "then import the selected Excel.\n\nContinue?",
                parent=self.winfo_toplevel(),
            )
            if not ok:
                return
        path = filedialog.askopenfilename(
            parent=self.winfo_toplevel(),
            title="Select Master Data Excel",
            filetypes=[
                ("Excel files", "*.xlsx *.xls"),
                ("Excel (xlsx)", "*.xlsx"),
                ("Excel (xls)", "*.xls"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        try:
            stats = import_dye_master_excel(path, replace=replace)
            self._refresh_master_status()
            action = "Replaced and imported" if replace else "Appended"
            messagebox.showinfo(
                "Master Data updated",
                f"{action} {stats.get('inserted', 0)} new rows "
                f"(parsed {stats.get('parsed', 0)}, "
                f"skipped duplicates {stats.get('skipped_duplicates', 0)}).\n\n"
                f"Open: {stats.get('open', 0)}  |  Matched: {stats.get('matched', 0)}  |  "
                f"Total: {stats.get('total', 0)}",
                parent=self.winfo_toplevel(),
            )
        except ValueError as e:
            messagebox.showerror(
                "Wrong Excel format",
                str(e),
                parent=self.winfo_toplevel(),
            )
        except Exception as e:
            messagebox.showerror(
                "Upload failed",
                f"Could not import the file.\n{e}",
                parent=self.winfo_toplevel(),
            )

    def _export_master(self, *, status: str | None):
        try:
            stats = get_master_stats()
        except Exception:
            stats = {"total": 0, "open": 0}
        if status == "open" and not stats.get("open"):
            messagebox.showinfo(
                "Nothing to export",
                "There are no open pieces in Master Data.",
                parent=self.winfo_toplevel(),
            )
            return
        if status is None and not stats.get("total"):
            messagebox.showinfo(
                "Nothing to export",
                "Master Data is empty. Upload Master Data.xls first.",
                parent=self.winfo_toplevel(),
            )
            return
        label = "open" if status == "open" else "all"
        path = filedialog.asksaveasfilename(
            parent=self.winfo_toplevel(),
            title=f"Export Master Data ({label})",
            defaultextension=".xlsx",
            initialfile=f"Master_Data_{label}.xlsx",
            filetypes=[("Excel (xlsx)", "*.xlsx"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            result = export_master_excel(path, status=status)
            messagebox.showinfo(
                "Export complete",
                f"Exported {result.get('exported', 0)} rows to:\n{result.get('path')}",
                parent=self.winfo_toplevel(),
            )
        except Exception as e:
            messagebox.showerror(
                "Export failed",
                f"Could not export.\n{e}",
                parent=self.winfo_toplevel(),
            )

    def _reset_matched(self):
        try:
            stats = get_master_stats()
        except Exception:
            stats = {"matched": 0}
        matched = int(stats.get("matched") or 0)
        if matched <= 0:
            messagebox.showinfo(
                "Nothing to reset",
                "There are no matched pieces.",
                parent=self.winfo_toplevel(),
            )
            return
        ok = messagebox.askyesno(
            "Reset matched pieces?",
            f"This will mark {matched} matched piece(s) as open again\n"
            "(so they can match on the next run). Nothing is deleted.\n\nContinue?",
            parent=self.winfo_toplevel(),
        )
        if not ok:
            return
        try:
            n = reset_matched_to_open()
            self._refresh_master_status()
            messagebox.showinfo(
                "Reset complete",
                f"Re-opened {n} matched piece(s).",
                parent=self.winfo_toplevel(),
            )
        except Exception as e:
            messagebox.showerror(
                "Reset failed",
                f"Could not reset matched pieces.\n{e}",
                parent=self.winfo_toplevel(),
            )

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
        if event.widget is not self:
            return
        if self._save_after_id:
            try:
                self.after_cancel(self._save_after_id)
            except Exception:
                pass
            self._save_after_id = None
