"""
Dashboard page: Input/Output folder selectors, Start Processing,
Open Output Folder, and a progress card (total files, processed, errors, progress bar).
"""
import os
import customtkinter as ctk
from tkinter import filedialog

PRIMARY = "#3B82F6"
BG_CARD = "#FFFFFF"
WORKSPACE_BG = "#F8FAFC"


class DashboardPage(ctk.CTkFrame):
    """Dashboard with folder selection and processing progress card."""

    def __init__(self, parent, base_dir: str, **kwargs):
        super().__init__(parent, fg_color=WORKSPACE_BG, **kwargs)
        self.base_dir = base_dir
        # Start with empty paths on first load; user chooses folders explicitly.
        self.input_var = ctk.StringVar(value="")
        self.output_var = ctk.StringVar(value="")
        self.on_start = None
        self.on_open_output = None
        self.btn_start = None
        self._build()

    def _build(self):
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=32, pady=32)

        ctk.CTkLabel(inner, text="Dashboard", font=ctk.CTkFont(size=24, weight="bold")).pack(anchor="w", pady=(0, 24))

        # Card: Folder selection
        card = ctk.CTkFrame(inner, fg_color=BG_CARD, corner_radius=12, border_width=0)
        card.pack(fill="x", pady=(0, 20))
        card_inner = ctk.CTkFrame(card, fg_color="transparent")
        card_inner.pack(fill="x", padx=24, pady=24)

        ctk.CTkLabel(card_inner, text="Folders", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", pady=(0, 16))

        row1 = ctk.CTkFrame(card_inner, fg_color="transparent")
        row1.pack(fill="x", pady=8)
        ctk.CTkLabel(row1, text="Input Folder", width=120, anchor="w").pack(side="left", padx=(0, 10))
        ctk.CTkEntry(row1, textvariable=self.input_var, height=36, corner_radius=8).pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkButton(row1, text="Browse", width=100, corner_radius=8, command=lambda: self._browse(self.input_var)).pack(side="left")

        row2 = ctk.CTkFrame(card_inner, fg_color="transparent")
        row2.pack(fill="x", pady=8)
        ctk.CTkLabel(row2, text="Output Folder", width=120, anchor="w").pack(side="left", padx=(0, 10))
        ctk.CTkEntry(row2, textvariable=self.output_var, height=36, corner_radius=8).pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkButton(row2, text="Browse", width=100, corner_radius=8, command=lambda: self._browse(self.output_var)).pack(side="left")
        ctk.CTkLabel(card_inner, text="Tip: Add files by opening the input folder in Finder/Explorer and dragging files in.", font=ctk.CTkFont(size=11), text_color="#64748B").pack(anchor="w", pady=(6, 0))

        btn_row = ctk.CTkFrame(card_inner, fg_color="transparent")
        btn_row.pack(fill="x", pady=16)
        self.btn_start = ctk.CTkButton(btn_row, text="Start Processing", corner_radius=8, height=40, fg_color=PRIMARY, command=self._on_start)
        self.btn_start.pack(side="left", padx=(0, 10))
        self.btn_open_output = ctk.CTkButton(btn_row, text="Open Output Folder", corner_radius=8, height=40, fg_color="gray", command=self._on_open_output_click)
        self.btn_open_output.pack(side="left", padx=5)
        self.status_hint = ctk.CTkLabel(card_inner, text="", font=ctk.CTkFont(size=12), text_color="#64748B", anchor="w")
        self.status_hint.pack(anchor="w", pady=(8, 0))

        # Progress card
        prog_card = ctk.CTkFrame(inner, fg_color=BG_CARD, corner_radius=12, border_width=0)
        prog_card.pack(fill="x", pady=(0, 20))
        prog_inner = ctk.CTkFrame(prog_card, fg_color="transparent")
        prog_inner.pack(fill="x", padx=24, pady=24)

        ctk.CTkLabel(prog_inner, text="Processing progress", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", pady=(0, 16))

        stats_row = ctk.CTkFrame(prog_inner, fg_color="transparent")
        stats_row.pack(fill="x", pady=8)
        self.lbl_total = ctk.CTkLabel(stats_row, text="Total files detected: 0", anchor="w")
        self.lbl_total.pack(side="left", padx=(0, 24))
        self.lbl_processed = ctk.CTkLabel(stats_row, text="Files processed: 0", anchor="w")
        self.lbl_processed.pack(side="left", padx=(0, 24))
        self.lbl_errors = ctk.CTkLabel(stats_row, text="Errors: 0", anchor="w")
        self.lbl_errors.pack(side="left")

        self.progress_bar = ctk.CTkProgressBar(prog_inner, height=14, corner_radius=7, fg_color="#E2E8F0", progress_color=PRIMARY)
        self.progress_bar.pack(fill="x", pady=12)
        self.progress_bar.set(0)

    def _browse(self, var: ctk.StringVar):
        folder = filedialog.askdirectory()
        if folder:
            var.set(folder)

    def _on_start(self):
        if self.on_start:
            self.on_start()

    def _on_open_output_click(self):
        if self.on_open_output:
            self.on_open_output()

    def set_progress(self, total: int, processed: int, errors: int):
        """Update progress card."""
        self.lbl_total.configure(text=f"Total files detected: {total}")
        self.lbl_processed.configure(text=f"Files processed: {processed}")
        self.lbl_errors.configure(text=f"Errors: {errors}")
        if total > 0:
            self.progress_bar.set(processed / total)
        else:
            self.progress_bar.set(0)

    def set_processing_state(self, is_processing: bool):
        """Show loading state: disable Start button, show hint."""
        if is_processing:
            self.btn_start.configure(state="disabled", text="Processing… please wait")
            self.status_hint.configure(text="Processing documents. This may take 30–60 seconds per file. Do not click again.")
        else:
            self.btn_start.configure(state="normal", text="Start Processing")
            self.status_hint.configure(text="")
