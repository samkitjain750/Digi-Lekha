"""
Export Results page: tabs Document Summary / Line Items, scrollable tables, Export to Excel button.
"""
import os
import sys
import threading

if __name__ != "__main__":
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)

import customtkinter as ctk

WORKSPACE_BG = "#F8FAFC"
BG_CARD = "#FFFFFF"


class ResultsPage(ctk.CTkFrame):
    """Two tabs with table preview; Export to Excel opens output folder or triggers export."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=WORKSPACE_BG, **kwargs)
        self.output_dir = ""
        self.on_export_click = None
        self._build()

    def _build(self):
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=32, pady=32)
        ctk.CTkLabel(inner, text="Export Results", font=ctk.CTkFont(size=24, weight="bold")).pack(anchor="w", pady=(0, 16))
        self.btn_export = ctk.CTkButton(inner, text="Export to Excel", corner_radius=8, height=40, fg_color="#3B82F6", command=self._on_export)
        self.btn_export.pack(anchor="w", pady=(0, 16))

        self.tabview = ctk.CTkTabview(inner, fg_color=BG_CARD, corner_radius=12)
        self.tabview.pack(fill="both", expand=True)
        self.tab_docs = self.tabview.add("Document Summary")
        self.tab_items = self.tabview.add("Line Items")

        self.doc_text = ctk.CTkTextbox(self.tab_docs, font=ctk.CTkFont(family="Monaco", size=11))
        self.doc_text.pack(fill="both", expand=True, padx=8, pady=8)
        self.items_text = ctk.CTkTextbox(self.tab_items, font=ctk.CTkFont(family="Monaco", size=11))
        self.items_text.pack(fill="both", expand=True, padx=8, pady=8)

        # Visible loading overlay: big card on top of tabview when loading Excel
        self.loader_frame = ctk.CTkFrame(self.tabview, fg_color="#E2E8F0", corner_radius=12, border_width=0)
        self.loader_label = ctk.CTkLabel(
            self.loader_frame,
            text="Loading preview…",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#334155",
        )
        self.loader_label.pack(pady=48, padx=64)
        ctk.CTkLabel(
            self.loader_frame,
            text="Reading extracted_data.xlsx",
            font=ctk.CTkFont(size=13),
            text_color="#64748B",
        ).pack(pady=(0, 48))
        self.loader_frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.9, relheight=0.6)
        self.loader_frame.place_forget()

    def set_output_dir(self, path: str):
        self.output_dir = path or ""
        self.load_preview()

    def load_preview(self):
        """Show visible loader overlay, then load Excel in background."""
        self._hide_loader()

        if not self.output_dir:
            self.doc_text.delete("0.0", "end")
            self.doc_text.insert("end", "Set output folder and run processing to see results.")
            self.items_text.delete("0.0", "end")
            return

        xlsx = os.path.join(self.output_dir, "extracted_data.xlsx")
        if not os.path.isfile(xlsx):
            self.doc_text.delete("0.0", "end")
            self.doc_text.insert("end", "No extracted_data.xlsx found. Run processing first.")
            self.items_text.delete("0.0", "end")
            return

        self.doc_text.delete("0.0", "end")
        self.items_text.delete("0.0", "end")
        self._show_loader()
        self.update_idletasks()

        def load_in_background():
            try:
                import pandas as pd
                df_doc = pd.read_excel(xlsx, sheet_name="Documents")
                df_items = pd.read_excel(xlsx, sheet_name="Items")
                doc_str = df_doc.to_string()
                items_str = df_items.to_string()
            except Exception as e:
                doc_str = f"Could not load Excel: {e}"
                items_str = ""
            self.after(0, lambda: self._set_preview_text(doc_str, items_str))

        threading.Thread(target=load_in_background, daemon=True).start()

    def _show_loader(self):
        self.loader_frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.9, relheight=0.6)
        self.loader_frame.lift()

    def _hide_loader(self):
        self.loader_frame.place_forget()

    def _set_preview_text(self, doc_str: str, items_str: str):
        self._hide_loader()
        self.doc_text.delete("0.0", "end")
        self.doc_text.insert("end", doc_str)
        self.items_text.delete("0.0", "end")
        self.items_text.insert("end", items_str)

    def _on_export(self):
        if self.on_export_click:
            self.on_export_click()
