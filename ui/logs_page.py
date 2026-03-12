"""
Processing Logs page: real-time logs with level-based coloring and clear layout.
"""
import customtkinter as ctk

WORKSPACE_BG = "#F8FAFC"
CARD_BG = "#FFFFFF"
PLACEHOLDER = "Run processing from the Dashboard to see logs here.\n\nLogs appear in real time when you click Start Processing."

# Colors for log levels
COLOR_INFO = "#475569"
COLOR_SUCCESS = "#059669"
COLOR_ERROR = "#DC2626"


class LogsPage(ctk.CTkFrame):
    """Scrollable log viewer with level-based coloring and card layout."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=WORKSPACE_BG, **kwargs)
        self._build()
        self._has_logs = False

    def _build(self):
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=32, pady=32)

        ctk.CTkLabel(
            inner,
            text="Processing Logs",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=("gray10", "gray90"),
        ).pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(
            inner,
            text="Live output from document extraction. Success lines are green; errors are red.",
            font=ctk.CTkFont(size=13),
            text_color="#64748B",
        ).pack(anchor="w", pady=(0, 16))

        card = ctk.CTkFrame(inner, fg_color=CARD_BG, corner_radius=12, border_width=0)
        card.pack(fill="both", expand=True)
        card_inner = ctk.CTkFrame(card, fg_color="transparent")
        card_inner.pack(fill="both", expand=True, padx=16, pady=16)

        self.log_text = ctk.CTkTextbox(
            card_inner,
            corner_radius=8,
            font=ctk.CTkFont(family="Menlo", size=12),
            fg_color="#F8FAFC",
            border_width=1,
            border_color="#E2E8F0",
        )
        self.log_text.pack(fill="both", expand=True)
        self.log_text.insert("end", PLACEHOLDER)

        self._configure_tags()

    def _configure_tags(self):
        """Apply colors to tags on the underlying Text widget."""
        try:
            text = getattr(self.log_text, "_textbox", None)
            if text is not None:
                text.tag_configure("info", foreground=COLOR_INFO)
                text.tag_configure("success", foreground=COLOR_SUCCESS, font=("Menlo", 12, "bold"))
                text.tag_configure("error", foreground=COLOR_ERROR, font=("Menlo", 12, "bold"))
        except Exception:
            pass

    def append(self, message: str, level: str = "info"):
        """Append a log line. level: 'info', 'success', 'error'."""
        try:
            if not getattr(self, "_has_logs", False):
                self._has_logs = True
                self.log_text.delete("0.0", "end")

            text = getattr(self.log_text, "_textbox", None)
            if text is not None:
                start = text.index("end-1c")
                self.log_text.insert("end", message + "\n")
                end = text.index("end-1c")
                tag = level if level in ("info", "success", "error") else "info"
                text.tag_add(tag, start, end)
            else:
                self.log_text.insert("end", message + "\n")

            self.log_text.see("end")
        except Exception:
            try:
                self.log_text.insert("end", message + "\n")
                self.log_text.see("end")
            except Exception:
                pass
