"""
Export Results page: tabs Document Summary / Line Items with ttk.Treeview tables.
"""
import os
import sys
import threading
import tkinter as tk
from tkinter import ttk

if __name__ != "__main__":
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)

import customtkinter as ctk

WORKSPACE_BG = "#F8FAFC"
BG_CARD = "#FFFFFF"

DOC_COLUMNS = [
    "file_name",
    "document_type",
]

ITEM_COLUMNS = [
    "Piece No",
    "Finished Mtrs",
]

# Default min width for columns (chars)
DEFAULT_COL_WIDTH = 10


def _treeview_with_scrollbars(parent, columns: list, min_col_width: int = 80):
    """Build a tk.Frame containing a ttk.Treeview and vertical + horizontal scrollbars."""
    container = tk.Frame(parent, bg=BG_CARD)
    # Style treeview to match light theme
    style = ttk.Style()
    style.configure("Treeview", background="#FFFFFF", foreground="#1e293b", fieldbackground="#FFFFFF", rowheight=22)
    style.configure("Treeview.Heading", background="#F1F5F9", foreground="#334155", font=("Helvetica", 11, "bold"))
    style.map("Treeview", background=[("selected", "#3B82F6")], foreground=[("selected", "#FFFFFF")])
    vsb = ttk.Scrollbar(container)
    hsb = ttk.Scrollbar(container, orient=tk.HORIZONTAL)
    tree = ttk.Treeview(container, columns=columns, show="headings", height=20, selectmode="none")
    tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
    vsb.configure(command=tree.yview)
    hsb.configure(command=tree.xview)
    for col in columns:
        tree.heading(col, text=col.replace("_", " ").title())
        tree.column(col, width=min_col_width, minwidth=min_col_width)
    vsb.pack(side=tk.RIGHT, fill=tk.Y)
    hsb.pack(side=tk.BOTTOM, fill=tk.X)
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    return container, tree


def _auto_resize_columns(tree: ttk.Treeview, columns: list):
    """Set column widths based on header and content."""
    px_per_char = 8
    for col in columns:
        try:
            title = col.replace("_", " ").title()
            w = max(len(title) * px_per_char, DEFAULT_COL_WIDTH * px_per_char)
            for item in tree.get_children():
                val = tree.set(item, col)
                if val:
                    w = max(w, min(len(str(val)) * px_per_char, 450))
            tree.column(col, width=min(max(w, 70), 450), minwidth=70)
        except Exception:
            tree.column(col, width=100, minwidth=70)


def _latest_excel_file(root_dir: str) -> str:
    """Return most recent challan .xlsx file under root_dir (recursive)."""
    if not root_dir or not os.path.isdir(root_dir):
        return ""
    latest = ""
    latest_mtime = -1.0
    challan_latest = ""
    challan_mtime = -1.0
    for dirpath, _, filenames in os.walk(root_dir):
        for name in filenames:
            if not name.lower().endswith(".xlsx"):
                continue
            path = os.path.join(dirpath, name)
            try:
                mtime = os.path.getmtime(path)
                if mtime > latest_mtime:
                    latest = path
                    latest_mtime = mtime
                if "delivery_challan" in name.lower() and mtime > challan_mtime:
                    challan_latest = path
                    challan_mtime = mtime
            except Exception:
                pass
    return challan_latest or latest


class ResultsPage(ctk.CTkFrame):
    """Two tabs with Treeview tables; Export to Excel opens output folder."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=WORKSPACE_BG, **kwargs)
        self.output_dir = ""
        self.on_export_click = None
        self._doc_tree = None
        self._items_tree = None
        self._doc_container = None
        self._items_container = None
        self._build()

    def _build(self):
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=32, pady=32)
        ctk.CTkLabel(
            inner,
            text="Export Results",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=("gray10", "gray90"),
        ).pack(anchor="w", pady=(0, 16))
        self.btn_export = ctk.CTkButton(
            inner,
            text="Export to Excel",
            corner_radius=8,
            height=40,
            fg_color="#3B82F6",
            command=self._on_export,
        )
        self.btn_export.pack(anchor="w", pady=(0, 16))

        self.tabview = ctk.CTkTabview(inner, fg_color=BG_CARD, corner_radius=12)
        self.tabview.pack(fill="both", expand=True)
        self.tab_docs = self.tabview.add("Document Summary")
        self.tab_items = self.tabview.add("Line Items")

        # Document Summary: table with scrollbars
        self._doc_container, self._doc_tree = _treeview_with_scrollbars(
            self.tab_docs,
            DOC_COLUMNS,
            min_col_width=90,
        )
        self._doc_container.pack(fill="both", expand=True, padx=8, pady=8)

        # Line Items: table with scrollbars
        self._items_container, self._items_tree = _treeview_with_scrollbars(
            self.tab_items,
            ITEM_COLUMNS,
            min_col_width=90,
        )
        self._items_container.pack(fill="both", expand=True, padx=8, pady=8)

        # Placeholder labels (shown when no data)
        self._doc_placeholder = ctk.CTkLabel(
            self.tab_docs,
            text="Set output folder and run processing to see results.",
            font=ctk.CTkFont(size=13),
            text_color="#64748B",
        )
        self._items_placeholder = ctk.CTkLabel(
            self.tab_items,
            text="Set output folder and run processing to see results.",
            font=ctk.CTkFont(size=13),
            text_color="#64748B",
        )

        # Loading overlay
        self.loader_frame = ctk.CTkFrame(
            self.tabview,
            fg_color="#E2E8F0",
            corner_radius=12,
            border_width=0,
        )
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
        """Show loader, then load Excel in background and fill Treeviews."""
        self._hide_loader()
        self._clear_tables()
        self._show_placeholders("Set output folder and run processing to see results.")

        if not self.output_dir:
            return
        xlsx = _latest_excel_file(self.output_dir)
        if not xlsx:
            self._show_placeholders("No Excel output found. Run processing first.")
            return

        self._hide_placeholders()
        self._show_loader()
        self.update_idletasks()

        def load_in_background():
            try:
                import pandas as pd
                df_doc = pd.read_excel(xlsx, sheet_name="Documents")
                df_items = pd.read_excel(xlsx, sheet_name="Items")
                # Replace NaN with empty string
                df_doc = df_doc.fillna("")
                df_items = df_items.fillna("")
                self.after(0, lambda: self._set_table_data(df_doc, df_items))
            except Exception as e:
                self.after(0, lambda: self._set_table_error(str(e)))

        threading.Thread(target=load_in_background, daemon=True).start()

    def _show_placeholders(self, message: str):
        self._doc_placeholder.configure(text=message)
        self._doc_placeholder.place(relx=0.5, rely=0.5, anchor="center")
        self._items_placeholder.configure(text=message)
        self._items_placeholder.place(relx=0.5, rely=0.5, anchor="center")

    def _hide_placeholders(self):
        self._doc_placeholder.place_forget()
        self._items_placeholder.place_forget()

    def _clear_tables(self):
        for t in (self._doc_tree, self._items_tree):
            if t:
                for item in t.get_children():
                    t.delete(item)

    def _set_table_error(self, message: str):
        self._hide_loader()
        self._clear_tables()
        self._show_placeholders(f"Could not load Excel: {message}")

    def _set_table_data(self, df_doc, df_items):
        self._hide_loader()
        self._hide_placeholders()
        self._clear_tables()

        # Document Summary: insert row by row
        for _, row in df_doc.iterrows():
            values = [str(row.get(c, "")) for c in DOC_COLUMNS]
            self._doc_tree.insert("", tk.END, values=values)

        # Line Items: insert row by row
        for _, row in df_items.iterrows():
            # Support both new export headers and older internal names.
            values = [
                str(row.get("Piece No", row.get("piece_number", ""))),
                str(row.get("Finished Mtrs", row.get("dispatch_mtr", ""))),
            ]
            self._items_tree.insert("", tk.END, values=values)

        _auto_resize_columns(self._doc_tree, DOC_COLUMNS)
        _auto_resize_columns(self._items_tree, ITEM_COLUMNS)

    def _show_loader(self):
        self.loader_frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.9, relheight=0.6)
        self.loader_frame.lift()

    def _hide_loader(self):
        self.loader_frame.place_forget()

    def _on_export(self):
        if self.on_export_click:
            self.on_export_click()
