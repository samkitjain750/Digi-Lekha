"""
First-run setup: prompt for OpenAI API key when not found.
Stores key in config/api_key.json (writable app data when frozen).
"""
import customtkinter as ctk

PRIMARY = "#3B82F6"


class ApiKeySetupDialog(ctk.CTkToplevel):
    """Modal dialog to enter and save OpenAI API key."""

    def __init__(self, parent, on_saved, **kwargs):
        super().__init__(parent, **kwargs)
        self.on_saved = on_saved
        self.result_key = None
        self.title("API Key Setup")
        self.geometry("480x260")
        self.resizable(False, False)
        self.configure(fg_color="#F8FAFC")
        self._build()
        self.transient(parent)
        self.grab_set()
        self.focus_set()
        self._entry.focus_set()

    def _build(self):
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=32, pady=24)
        ctk.CTkLabel(
            inner,
            text="OpenAI API Key Required",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=("gray10", "gray90"),
        ).pack(anchor="w", pady=(0, 8))
        ctk.CTkLabel(
            inner,
            text="Enter your OpenAI API key. It will be stored locally and used for document extraction.",
            font=ctk.CTkFont(size=13),
            text_color=("#64748B", "gray70"),
            wraplength=400,
            justify="left",
        ).pack(anchor="w", pady=(0, 16))
        self._entry = ctk.CTkEntry(
            inner,
            placeholder_text="Paste your API key here",
            height=40,
            corner_radius=8,
            show="•",
        )
        self._entry.pack(fill="x", pady=(0, 8))
        self._error = ctk.CTkLabel(inner, text="", font=ctk.CTkFont(size=12), text_color="#DC2626")
        self._error.pack(anchor="w", pady=(0, 16))
        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(fill="x")
        ctk.CTkButton(
            btn_row,
            text="Save and Continue",
            font=ctk.CTkFont(size=13),
            fg_color=PRIMARY,
            hover_color="#2563EB",
            command=self._save,
            width=140,
            height=36,
            corner_radius=8,
        ).pack(side="left", padx=(0, 10))
        ctk.CTkButton(
            btn_row,
            text="Cancel",
            font=ctk.CTkFont(size=13),
            fg_color="gray",
            hover_color="gray60",
            command=self._cancel,
            width=80,
            height=36,
            corner_radius=8,
        ).pack(side="left")

    def _save(self):
        key = (self._entry.get() or "").strip()
        if not key:
            self._error.configure(text="Please enter an API key.")
            return
        self._error.configure(text="")
        self.result_key = key
        self.on_saved(key)
        self.destroy()

    def _cancel(self):
        self.destroy()
