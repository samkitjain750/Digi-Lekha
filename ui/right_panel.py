"""
Right panel: contextual document preview and extracted fields.
Shows document name and actual extracted data from Excel when a document is selected.
"""
import os
import customtkinter as ctk

PANEL_BG = "#FFFFFF"
PANEL_WIDTH = 320


class RightPanel(ctk.CTkFrame):
    """Right sidebar: document preview and extracted fields from Excel."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, width=PANEL_WIDTH, fg_color=PANEL_BG, corner_radius=0, **kwargs)
        self.pack_propagate(False)
        self.output_dir = ""
        self._build()
        self._current_path = None
        self._current_data = None

    def _build(self):
        ctk.CTkLabel(self, text="Preview", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=16, pady=16)
        self.preview_label = ctk.CTkLabel(
            self, text="Select a document from the\nDocuments page.", fg_color="#F1F5F9", corner_radius=8, padx=16, pady=24
        )
        self.preview_label.pack(fill="x", padx=16, pady=(0, 16))

        ctk.CTkLabel(self, text="Extracted fields", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=16, pady=(0, 8))
        self.fields_text = ctk.CTkTextbox(self, height=280, font=ctk.CTkFont(size=11))
        self.fields_text.pack(fill="both", expand=True, padx=16, pady=(0, 16))

    def set_output_dir(self, path: str):
        self.output_dir = path or ""

    def show_document(self, file_path: str, data: dict):
        """Show document name and load extracted fields from Excel (Documents + Items by file_name)."""
        self._current_path = file_path
        self._current_data = data or {}
        name = os.path.basename(file_path) if file_path else ""
        self.preview_label.configure(text=name[:36] + ("..." if len(name) > 36 else ""))

        self.fields_text.delete("0.0", "end")
        if not name:
            return

        # Load actual extracted data from Excel
        xlsx = os.path.join(self.output_dir, "extracted_data.xlsx") if self.output_dir else ""
        if xlsx and os.path.isfile(xlsx):
            try:
                import pandas as pd
                df_doc = pd.read_excel(xlsx, sheet_name="Documents")
                df_items = pd.read_excel(xlsx, sheet_name="Items")
                doc_row = df_doc[df_doc["file_name"].astype(str).str.strip() == name]
                items_rows = df_items[df_items["file_name"].astype(str).str.strip() == name]

                lines = []
                if not doc_row.empty:
                    row = doc_row.iloc[0]
                    lines.append("--- Document ---")
                    for col in doc_row.columns:
                        try:
                            val = row[col]
                        except Exception:
                            continue
                        if pd.isna(val) or str(val).strip() == "":
                            continue
                        lines.append(f"{col}: {val}")
                if not items_rows.empty:
                    lines.append("\n--- Line items ---")
                    for _, row in items_rows.iterrows():
                        parts = []
                        for c in items_rows.columns:
                            try:
                                v = row[c]
                                if not pd.isna(v) and str(v).strip():
                                    parts.append(str(v)[:18])
                            except Exception:
                                pass
                        if parts:
                            lines.append("  " + " | ".join(parts[:5]))
                if lines:
                    self.fields_text.insert("end", "\n".join(lines))
                    return
            except Exception:
                pass

        # Fallback: show status summary
        lines = [f"Status: {data.get('status', '-')}", f"Type: {data.get('doc_type', '-')}", f"Items: {data.get('items_count', 0)}"]
        self.fields_text.insert("end", "\n".join(lines))

    def clear(self):
        self._current_path = None
        self._current_data = None
        self.preview_label.configure(text="Select a document from the\nDocuments page.")
        self.fields_text.delete("0.0", "end")
