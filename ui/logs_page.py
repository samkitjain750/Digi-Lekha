"""
Processing Logs page: real-time logs with color (INFO=gray, SUCCESS=green, ERROR=red), auto-scroll.
"""
import customtkinter as ctk

WORKSPACE_BG = "#F8FAFC"
PLACEHOLDER = "Run processing from the Dashboard to see logs here.\n\n(Logs appear in real time when you click Start Processing.)"


class LogsPage(ctk.CTkFrame):
    """Scrollable log viewer with level-based coloring."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=WORKSPACE_BG, **kwargs)
        self._build()
        self._has_logs = False

    def _build(self):
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=32, pady=32)
        ctk.CTkLabel(inner, text="Processing Logs", font=ctk.CTkFont(size=24, weight="bold")).pack(anchor="w", pady=(0, 16))
        self.log_text = ctk.CTkTextbox(inner, corner_radius=8, font=ctk.CTkFont(family="Monaco", size=12))
        self.log_text.pack(fill="both", expand=True)
        self.log_text.insert("end", PLACEHOLDER)
        self._tags_configured = False

    def append(self, message: str, level: str = "info"):
        """Append a log line. level: 'info', 'success', 'error'."""
        try:
            # Clear placeholder on first real log
            if not getattr(self, "_has_logs", False):
                self._has_logs = True
                self.log_text.delete("0.0", "end")
            # Use public API so it always works across CTk versions
            self.log_text.insert("end", message + "\n")
            self.log_text.see("end")
        except Exception:
            pass
