"""
Left sidebar navigation: Dashboard, Documents, Extraction Settings,
Processing Logs, Export Results; bottom: Settings, About.
Uses text + emoji as icons for cross-platform consistency.
"""
import customtkinter as ctk

# Nav item: (key, label, icon)
NAV_ITEMS = [
    ("dashboard", "Dashboard", "📊"),
    ("documents", "Documents", "📄"),
    ("logs", "Processing Logs", "📋"),
    ("results", "Export Results", "📤"),
    ("invoice_results", "Invoice Results", "🧾"),
]
BOTTOM_ITEMS = [
    ("settings", "Settings", "⚙️"),
    ("about", "About", "ℹ️"),
]

PRIMARY_COLOR = "#3B82F6"
SIDEBAR_BG = "#F1F5F9"
SIDEBAR_WIDTH = 200


class Sidebar(ctk.CTkFrame):
    """Left sidebar with navigation buttons. Calls on_select(key) when an item is clicked."""

    def __init__(self, parent, on_select, **kwargs):
        super().__init__(parent, width=SIDEBAR_WIDTH, fg_color=SIDEBAR_BG, corner_radius=0, **kwargs)
        self.on_select = on_select
        self.selected_key = "dashboard"
        self.buttons = {}
        self._build()

    def _build(self):
        self.pack_propagate(False)
        # Logo / title area
        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.pack(fill="x", padx=16, pady=20)
        ctk.CTkLabel(
            title_frame,
            text="Digi Lekha",
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w",
            justify="left",
        ).pack(anchor="w")

        # Main nav
        nav_frame = ctk.CTkFrame(self, fg_color="transparent")
        nav_frame.pack(fill="x", padx=8, pady=8)
        for key, label, icon in NAV_ITEMS:
            btn = ctk.CTkButton(
                nav_frame,
                text=f"  {icon}  {label}",
                anchor="w",
                height=40,
                corner_radius=8,
                fg_color="transparent",
                text_color=("gray10", "gray90"),
                hover_color=("gray85", "gray25"),
                command=lambda k=key: self._select(k),
            )
            btn.pack(fill="x", pady=2)
            self.buttons[key] = btn

        # Spacer
        ctk.CTkFrame(self, fg_color="transparent", height=20).pack(fill="x")

        # Bottom nav
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.pack(side="bottom", fill="x", padx=8, pady=16)
        for key, label, icon in BOTTOM_ITEMS:
            btn = ctk.CTkButton(
                bottom_frame,
                text=f"  {icon}  {label}",
                anchor="w",
                height=36,
                corner_radius=8,
                fg_color="transparent",
                text_color=("gray10", "gray90"),
                hover_color=("gray85", "gray25"),
                command=lambda k=key: self._select(k),
            )
            btn.pack(fill="x", pady=2)
            self.buttons[key] = btn

        self._update_highlight()

    def _select(self, key: str):
        self.selected_key = key
        self._update_highlight()
        if self.on_select:
            self.on_select(key)

    def _update_highlight(self):
        for k, btn in self.buttons.items():
            if k == self.selected_key:
                btn.configure(fg_color=PRIMARY_COLOR, text_color="white")
            else:
                btn.configure(fg_color="transparent", text_color=("gray10", "gray90"))
