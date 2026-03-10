"""
Documents page: table of files (File Name, Document Type, Status, Extracted Items).
Status icons: Waiting, Processing, Completed, Error. Click row to show preview in right panel.
"""
import os
import glob
import customtkinter as ctk

WORKSPACE_BG = "#F8FAFC"
BG_CARD = "#FFFFFF"

STATUS_ICONS = {"waiting": "⏳", "processing": "🔄", "completed": "✅", "error": "❌"}


class DocumentsPage(ctk.CTkFrame):
    """Table of documents in input folder; selection triggers on_select_document(path, data)."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=WORKSPACE_BG, **kwargs)
        self.input_dir = ""
        self.file_status = {}  # filename -> { status, doc_type, items_count }
        self.on_select_document = None
        self._build()

    def _build(self):
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=32, pady=32)
        ctk.CTkLabel(inner, text="Documents", font=ctk.CTkFont(size=24, weight="bold")).pack(anchor="w", pady=(0, 16))
        self.btn_refresh = ctk.CTkButton(inner, text="Refresh list", corner_radius=8, width=120, command=self.refresh)
        self.btn_refresh.pack(anchor="w", pady=(0, 12))

        self.table_frame = ctk.CTkScrollableFrame(inner, fg_color=BG_CARD, corner_radius=12)
        self.table_frame.pack(fill="both", expand=True)
        self.rows = []

    def set_input_dir(self, path: str):
        self.input_dir = path or ""
        # Processed folder is sibling "processed" next to input folder
        parent = os.path.dirname(self.input_dir)
        self.processed_dir = os.path.join(parent, "processed") if parent else ""
        self.refresh()

    def refresh(self):
        """Reload table from input_dir and processed folder (so completed files still show)."""
        for r in self.rows:
            try:
                r.destroy()
            except Exception:
                pass
        self.rows = []

        if not self.input_dir:
            ctk.CTkLabel(self.table_frame, text="Set the input folder on the Dashboard, then refresh.", fg_color="transparent").pack(pady=20)
            return

        files = []
        if os.path.isdir(self.input_dir):
            for ext in ("*.jpg", "*.jpeg", "*.png", "*.pdf"):
                files.extend(glob.glob(os.path.join(self.input_dir, ext)))
                files.extend(glob.glob(os.path.join(self.input_dir, ext.upper())))
        if getattr(self, "processed_dir", "") and os.path.isdir(self.processed_dir):
            for ext in ("*.jpg", "*.jpeg", "*.png", "*.pdf"):
                files.extend(glob.glob(os.path.join(self.processed_dir, ext)))
                files.extend(glob.glob(os.path.join(self.processed_dir, ext.upper())))
        files = sorted(set(files))

        # Header row
        h = ctk.CTkFrame(self.table_frame, fg_color="transparent")
        h.pack(fill="x", pady=2, padx=8)
        ctk.CTkLabel(h, text="File Name", font=ctk.CTkFont(weight="bold"), width=200, anchor="w").pack(side="left", padx=4)
        ctk.CTkLabel(h, text="Document Type", font=ctk.CTkFont(weight="bold"), width=120, anchor="w").pack(side="left", padx=4)
        ctk.CTkLabel(h, text="Status", font=ctk.CTkFont(weight="bold"), width=100, anchor="w").pack(side="left", padx=4)
        ctk.CTkLabel(h, text="Extracted Items", font=ctk.CTkFont(weight="bold"), width=100, anchor="w").pack(side="left", padx=4)
        self.rows.append(h)

        for path in files:
            name = os.path.basename(path)
            info = self.file_status.get(name, {"status": "waiting", "doc_type": "-", "items_count": 0})
            status = info.get("status", "waiting")
            # Files in processed folder are completed if we don't have status
            if not self.file_status.get(name) and getattr(self, "processed_dir", "") and path.startswith(self.processed_dir):
                status = "completed"
                info = {"status": "completed", "doc_type": info.get("doc_type", "-"), "items_count": info.get("items_count", 0)}
            icon = STATUS_ICONS.get(status, "⏳")
            row = ctk.CTkFrame(self.table_frame, fg_color="transparent", cursor="hand2")
            row.pack(fill="x", pady=2, padx=8)
            row.bind("<Button-1>", lambda e, p=path, d=info: self._on_click(p, d))
            ctk.CTkLabel(row, text=name[:40] + ("..." if len(name) > 40 else ""), width=200, anchor="w").pack(side="left", padx=4)
            ctk.CTkLabel(row, text=str(info.get("doc_type", "-")), width=120, anchor="w").pack(side="left", padx=4)
            ctk.CTkLabel(row, text=f"{icon} {status}", width=100, anchor="w").pack(side="left", padx=4)
            ctk.CTkLabel(row, text=str(info.get("items_count", 0)), width=100, anchor="w").pack(side="left", padx=4)
            for c in row.winfo_children():
                c.bind("<Button-1>", lambda e, p=path, d=info: self._on_click(p, d))
            self.rows.append(row)

    def update_file_status(self, filename: str, status: str, doc_type: str = "", items_count: int = 0):
        """Update status for one file (called from processor)."""
        self.file_status[filename] = {"status": status, "doc_type": doc_type, "items_count": items_count}
        self.refresh()

    def _on_click(self, path: str, data: dict):
        if self.on_select_document:
            self.on_select_document(path, data)
