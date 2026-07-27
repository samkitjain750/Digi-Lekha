"""
Extraction Settings page: toggles for challan fields + prior-year due pieces
+ dye piece master upload.
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
from core.prior_pieces import (
    extract_pieces_from_excel,
    format_help_text,
    load_prior_pieces_meta,
    save_prior_pieces,
)
from core.dye_master import (
    format_help_text as dye_format_help_text,
    get_master_stats,
    import_dye_master_excel,
)

WORKSPACE_BG = "#F8FAFC"
BG_CARD = "#FFFFFF"

CHALLAN_TABLE_FIELDS = {
    "piece_number": "Piece No",
    "grey_mtrs": "Grey Mtrs",
    "dispatch_mtr": "Finished Mtrs (Dispatch Mtr)",
}


class SettingsPage(ctk.CTkFrame):
    """Extraction toggles + prior-year piece list + dye master upload."""

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
            inner, text="Extraction Settings", font=ctk.CTkFont(size=24, weight="bold")
        ).pack(anchor="w", pady=(0, 24))

        def add_section(title: str, field_labels: dict, config_key: str):
            card = ctk.CTkFrame(inner, fg_color=BG_CARD, corner_radius=12)
            card.pack(fill="x", pady=(0, 16))
            card_inner = ctk.CTkFrame(card, fg_color="transparent")
            card_inner.pack(fill="x", padx=24, pady=24)
            ctk.CTkLabel(
                card_inner, text=title, font=ctk.CTkFont(size=16, weight="bold")
            ).pack(anchor="w", pady=(0, 12))
            selected = set(self.config.get(config_key, []))
            for key, label in field_labels.items():
                var = ctk.BooleanVar(value=key in selected)
                sw = ctk.CTkSwitch(card_inner, text=label, variable=var)
                sw.pack(anchor="w", pady=4)
                self._switches[(config_key, key)] = var

        add_section("Delivery challan table fields", CHALLAN_TABLE_FIELDS, "challan_table_fields")

        # --- Prior-year due pieces ---
        prior_card = ctk.CTkFrame(inner, fg_color=BG_CARD, corner_radius=12)
        prior_card.pack(fill="x", pady=(0, 16))
        prior_inner = ctk.CTkFrame(prior_card, fg_color="transparent")
        prior_inner.pack(fill="x", padx=24, pady=24)

        title_row = ctk.CTkFrame(prior_inner, fg_color="transparent")
        title_row.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(
            title_row,
            text="Last-year due pieces",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(side="left")
        self.btn_format_help = ctk.CTkButton(
            title_row,
            text="?",
            width=32,
            height=28,
            corner_radius=8,
            fg_color="#64748B",
            hover_color="#475569",
            command=self._show_format_help,
        )
        self.btn_format_help.pack(side="left", padx=10)

        ctk.CTkLabel(
            prior_inner,
            text=(
                "Upload an Excel list of piece numbers that were sent last year "
                "and may return this year. Matching pieces get a '-' prefix on Sheet1."
            ),
            font=ctk.CTkFont(size=13),
            text_color="#64748B",
            wraplength=640,
            justify="left",
            anchor="w",
        ).pack(anchor="w", pady=(0, 12))

        self.prior_status = ctk.CTkLabel(
            prior_inner,
            text="",
            font=ctk.CTkFont(size=13),
            text_color="#334155",
            anchor="w",
            justify="left",
        )
        self.prior_status.pack(anchor="w", pady=(0, 12))
        self._refresh_prior_status()

        btn_row_prior = ctk.CTkFrame(prior_inner, fg_color="transparent")
        btn_row_prior.pack(anchor="w")
        ctk.CTkButton(
            btn_row_prior,
            text="Upload piece list Excel",
            corner_radius=8,
            height=36,
            fg_color="#3B82F6",
            command=self._upload_prior_pieces,
        ).pack(side="left")

        # --- Dye piece master ---
        dye_card = ctk.CTkFrame(inner, fg_color=BG_CARD, corner_radius=12)
        dye_card.pack(fill="x", pady=(0, 16))
        dye_inner = ctk.CTkFrame(dye_card, fg_color="transparent")
        dye_inner.pack(fill="x", padx=24, pady=24)

        dye_title = ctk.CTkFrame(dye_inner, fg_color="transparent")
        dye_title.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(
            dye_title,
            text="Dye piece master",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(side="left")
        ctk.CTkButton(
            dye_title,
            text="?",
            width=32,
            height=28,
            corner_radius=8,
            fg_color="#64748B",
            hover_color="#475569",
            command=self._show_dye_format_help,
        ).pack(side="left", padx=10)

        ctk.CTkLabel(
            dye_inner,
            text=(
                "Upload fabric sent-to-dye register (Process Name / Quality Name blocks). "
                "Used to verify piece numbers on extracted challans. "
                "Append daily; matched rows are soft-marked (not deleted)."
            ),
            font=ctk.CTkFont(size=13),
            text_color="#64748B",
            wraplength=640,
            justify="left",
            anchor="w",
        ).pack(anchor="w", pady=(0, 12))

        self.dye_status = ctk.CTkLabel(
            dye_inner,
            text="",
            font=ctk.CTkFont(size=13),
            text_color="#334155",
            anchor="w",
            justify="left",
        )
        self.dye_status.pack(anchor="w", pady=(0, 12))
        self._refresh_dye_status()

        dye_btns = ctk.CTkFrame(dye_inner, fg_color="transparent")
        dye_btns.pack(anchor="w")
        ctk.CTkButton(
            dye_btns,
            text="Upload / Append Excel",
            corner_radius=8,
            height=36,
            fg_color="#3B82F6",
            command=lambda: self._upload_dye_master(replace=False),
        ).pack(side="left")
        ctk.CTkButton(
            dye_btns,
            text="Replace all",
            corner_radius=8,
            height=36,
            fg_color="#EF4444",
            hover_color="#DC2626",
            command=lambda: self._upload_dye_master(replace=True),
        ).pack(side="left", padx=10)

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

    def _refresh_prior_status(self):
        meta = load_prior_pieces_meta()
        count = meta.get("count") or 0
        if count <= 0:
            from core.prior_pieces import load_prior_piece_set

            load_prior_piece_set()
            meta = load_prior_pieces_meta()
            count = meta.get("count") or 0
        if count <= 0:
            self.prior_status.configure(
                text="No list saved yet. Upload an Excel file with piece numbers."
            )
            return
        src = meta.get("source_file") or "saved list"
        updated = meta.get("updated_at") or "-"
        self.prior_status.configure(
            text=f"Saved: {count} piece numbers\nSource: {src}\nUpdated: {updated}"
        )

    def _refresh_dye_status(self):
        try:
            stats = get_master_stats()
        except Exception:
            stats = {"total": 0, "open": 0, "matched": 0, "last_import": "", "source_file": ""}
        if not stats.get("total"):
            self.dye_status.configure(
                text="No dye master loaded yet. Upload the historical Excel once, then append daily."
            )
            return
        self.dye_status.configure(
            text=(
                f"Total: {stats['total']}  |  Open: {stats['open']}  |  Matched: {stats['matched']}\n"
                f"Last import: {stats.get('last_import') or '-'}\n"
                f"Source: {stats.get('source_file') or '-'}"
            )
        )

    def _show_format_help(self):
        messagebox.showinfo("Excel format", format_help_text(), parent=self.winfo_toplevel())

    def _show_dye_format_help(self):
        messagebox.showinfo(
            "Dye master Excel format",
            dye_format_help_text(),
            parent=self.winfo_toplevel(),
        )

    def _upload_prior_pieces(self):
        path = filedialog.askopenfilename(
            parent=self.winfo_toplevel(),
            title="Select prior-year piece numbers Excel",
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
            pieces, col_name = extract_pieces_from_excel(path)
            meta = save_prior_pieces(pieces, source_file=path)
            self._refresh_prior_status()
            messagebox.showinfo(
                "List saved",
                f"Imported {meta['count']} piece numbers from column “{col_name}”.\n"
                "This list is saved for future extractions.",
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

    def _upload_dye_master(self, *, replace: bool):
        if replace:
            ok = messagebox.askyesno(
                "Replace dye master?",
                "This will DELETE all existing dye master rows (open and matched),\n"
                "then import the selected Excel.\n\nContinue?",
                parent=self.winfo_toplevel(),
            )
            if not ok:
                return
        path = filedialog.askopenfilename(
            parent=self.winfo_toplevel(),
            title="Select dye piece master Excel",
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
            self._refresh_dye_status()
            action = "Replaced and imported" if replace else "Appended"
            messagebox.showinfo(
                "Dye master updated",
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
