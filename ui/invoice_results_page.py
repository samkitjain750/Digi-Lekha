"""
Invoice Results page: preview latest invoice run Excel (Documents, Items, Validation).
"""
import os
import sys
import threading
import tkinter as tk

if __name__ != "__main__":
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)

import customtkinter as ctk

from ui.results_page import (
    BG_CARD,
    WORKSPACE_BG,
    _auto_resize_columns,
    _treeview_with_scrollbars,
)


def _latest_invoice_excel(output_root: str) -> str:
    """Most recently modified invoice_*.xlsx under output_root/invoice/ (recursive)."""
    if not output_root or not os.path.isdir(output_root):
        return ""
    best = ""
    best_mtime = -1.0
    for dirpath, _, names in os.walk(output_root):
        pnorm = dirpath.replace("\\", "/").lower()
        if "/invoice/" not in pnorm and not pnorm.endswith("/invoice"):
            continue
        for name in names:
            if not name.lower().endswith(".xlsx"):
                continue
            if not name.lower().startswith("invoice"):
                continue
            path = os.path.join(dirpath, name)
            try:
                m = os.path.getmtime(path)
                if m > best_mtime:
                    best_mtime = m
                    best = path
            except OSError:
                pass
    return best


class InvoiceResultsPage(ctk.CTkFrame):
    """Three tabs: invoice header rows, line items, validation report."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=WORKSPACE_BG, **kwargs)
        self.output_dir = ""
        self.on_export_click = None
        self._doc_tree = None
        self._items_tree = None
        self._val_tree = None
        self._build()

    def _build(self):
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=32, pady=32)
        ctk.CTkLabel(
            inner,
            text="Invoice Results",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=("gray10", "gray90"),
        ).pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(
            inner,
            text="Latest run file under output/invoice/<date>/invoice_<timestamp>.xlsx",
            font=ctk.CTkFont(size=12),
            text_color="#64748B",
        ).pack(anchor="w", pady=(0, 12))

        self.btn_open = ctk.CTkButton(
            inner,
            text="Open output folder",
            corner_radius=8,
            height=36,
            fg_color="#3B82F6",
            command=self._on_export,
        )
        self.btn_open.pack(anchor="w", pady=(0, 16))

        self.tabview = ctk.CTkTabview(inner, fg_color=BG_CARD, corner_radius=12)
        self.tabview.pack(fill="both", expand=True)
        self.tab_docs = self.tabview.add("Invoice header")
        self.tab_items = self.tabview.add("Line items")
        self.tab_val = self.tabview.add("Validation")

        self._doc_container, self._doc_tree = _treeview_with_scrollbars(self.tab_docs, ["placeholder"], min_col_width=80)
        self._doc_container.pack(fill="both", expand=True, padx=8, pady=8)
        self._items_container, self._items_tree = _treeview_with_scrollbars(self.tab_items, ["placeholder"], min_col_width=80)
        self._items_container.pack(fill="both", expand=True, padx=8, pady=8)
        self._val_container, self._val_tree = _treeview_with_scrollbars(self.tab_val, ["placeholder"], min_col_width=80)
        self._val_container.pack(fill="both", expand=True, padx=8, pady=8)

        self._placeholder = ctk.CTkLabel(
            self.tabview,
            text="Set output folder and process an invoice to see preview.",
            font=ctk.CTkFont(size=13),
            text_color="#64748B",
        )
        self.loader = ctk.CTkFrame(self.tabview, fg_color="#E2E8F0", corner_radius=12)
        ctk.CTkLabel(self.loader, text="Loading…", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=40)
        self.loader.place_forget()

    def set_output_dir(self, path: str):
        self.output_dir = path or ""

    def load_preview(self):
        self._hide_loader()
        self._clear_all()
        self._show_placeholder("Set output folder and run processing on an invoice.")

        if not self.output_dir:
            return
        xlsx = _latest_invoice_excel(self.output_dir)
        if not xlsx:
            self._show_placeholder("No invoice Excel found yet. Run processing on a Tax Invoice.")
            return

        self._hide_placeholder()
        self._show_loader()
        self.update_idletasks()

        def work():
            try:
                import pandas as pd

                df_doc = pd.read_excel(xlsx, sheet_name="Invoice_Documents")
                df_items = pd.read_excel(xlsx, sheet_name="Invoice_Items")
                try:
                    df_val = pd.read_excel(xlsx, sheet_name="Invoice_Validation")
                except Exception:
                    df_val = None
                df_doc = df_doc.fillna("")
                df_items = df_items.fillna("")
                if df_val is not None:
                    df_val = df_val.fillna("")
                self.after(0, lambda: self._render(df_doc, df_items, df_val))
            except Exception as e:
                self.after(0, lambda err=str(e): self._error(err))

        threading.Thread(target=work, daemon=True).start()

    def _rebuild_tree(self, parent_tab, old_container, columns: list):
        old_container.destroy()
        cont, tree = _treeview_with_scrollbars(parent_tab, columns, min_col_width=80)
        cont.pack(fill="both", expand=True, padx=8, pady=8)
        return cont, tree

    def _populate(self, tree, df, columns):
        for _, row in df.iterrows():
            vals = [str(row.get(c, "")) for c in columns]
            tree.insert("", tk.END, values=vals)
        _auto_resize_columns(tree, columns)

    def _render(self, df_doc, df_items, df_val):
        self._hide_loader()
        self._hide_placeholder()

        doc_cols = [str(c) for c in df_doc.columns]
        item_cols = [str(c) for c in df_items.columns]
        self._doc_container, self._doc_tree = self._rebuild_tree(self.tab_docs, self._doc_container, doc_cols)
        self._items_container, self._items_tree = self._rebuild_tree(self.tab_items, self._items_container, item_cols)

        self._populate(self._doc_tree, df_doc, doc_cols)
        self._populate(self._items_tree, df_items, item_cols)

        if df_val is not None and len(df_val.columns) > 0:
            val_cols = [str(c) for c in df_val.columns]
            self._val_container, self._val_tree = self._rebuild_tree(self.tab_val, self._val_container, val_cols)
            self._populate(self._val_tree, df_val, val_cols)
        else:
            self._val_container, self._val_tree = self._rebuild_tree(self.tab_val, self._val_container, ["info"])
            self._val_tree.insert("", tk.END, values=("No Invoice_Validation sheet in this file.",))

    def _clear_all(self):
        for tree in (getattr(self, "_doc_tree", None), getattr(self, "_items_tree", None), getattr(self, "_val_tree", None)):
            if tree:
                for i in tree.get_children():
                    tree.delete(i)

    def _show_placeholder(self, msg):
        self._placeholder.configure(text=msg)
        self._placeholder.place(relx=0.5, rely=0.5, anchor="center")

    def _hide_placeholder(self):
        self._placeholder.place_forget()

    def _show_loader(self):
        self.loader.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.85, relheight=0.5)
        self.loader.lift()

    def _hide_loader(self):
        self.loader.place_forget()

    def _error(self, msg):
        self._hide_loader()
        self._show_placeholder(f"Could not load invoice Excel: {msg}")

    def _on_export(self):
        if self.on_export_click:
            self.on_export_click()
