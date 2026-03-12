"""
About dialog: app info, developer, company, social links, version.
Uses CustomTkinter with rounded corners and clean typography.
"""
import webbrowser
import customtkinter as ctk

PRIMARY = "#3B82F6"
CARD_BG = "#FFFFFF"
TEXT_MUTED = "#64748B"
LINK_COLOR = "#3B82F6"
VERSION = "1.0.0"
WEBSITE_URL = "https://socialsolicitor.in"


def open_website():
    webbrowser.open(WEBSITE_URL)


class AboutDialog(ctk.CTkToplevel):
    """Professional About popup with developer and company info."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.title("About")
        self.geometry("420x560")
        self.resizable(False, False)
        self.configure(fg_color="#F1F5F9")
        self._build()
        self.transient(parent)
        self.grab_set()
        self.focus_set()

    def _build(self):
        # Outer card with shadow effect (padding + rounded frame)
        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=24, pady=24)
        card = ctk.CTkFrame(outer, fg_color=CARD_BG, corner_radius=16, border_width=0)
        card.pack(fill="both", expand=True)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=32, pady=28)

        # App icon
        icon_frame = ctk.CTkFrame(inner, fg_color="#EFF6FF", corner_radius=12, width=64, height=64)
        icon_frame.pack(pady=(0, 12))
        icon_frame.pack_propagate(False)
        ctk.CTkLabel(icon_frame, text="📄", font=ctk.CTkFont(size=32)).pack(expand=True)
        # App name
        ctk.CTkLabel(
            inner,
            text="Digi Lekha",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=("gray10", "gray90"),
        ).pack(pady=(0, 8))
        # Description
        desc = (
            "Extract structured data from scanned invoices and delivery challans "
            "using Google Gemini Vision and export the results to Excel."
        )
        ctk.CTkLabel(
            inner,
            text=desc,
            font=ctk.CTkFont(size=13),
            text_color=TEXT_MUTED,
            wraplength=340,
            justify="center",
        ).pack(pady=(0, 20))

        # Divider
        div = ctk.CTkFrame(inner, fg_color="#E2E8F0", height=1)
        div.pack(fill="x", pady=(0, 16))

        # Developer section
        ctk.CTkLabel(
            inner,
            text="Developer",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=("gray20", "gray85"),
        ).pack(anchor="w")
        ctk.CTkLabel(
            inner,
            text="Samkit Jain",
            font=ctk.CTkFont(size=13),
            text_color=("gray10", "gray90"),
        ).pack(anchor="w", pady=(2, 0))
        ctk.CTkLabel(
            inner,
            text="AI Automation Developer",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED,
        ).pack(anchor="w", pady=(0, 12))

        # Company section
        ctk.CTkLabel(
            inner,
            text="Company",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=("gray20", "gray85"),
        ).pack(anchor="w")
        ctk.CTkLabel(
            inner,
            text="Social Solicitor",
            font=ctk.CTkFont(size=13),
            text_color=("gray10", "gray90"),
        ).pack(anchor="w", pady=(2, 12))

        # Social / Website
        ctk.CTkLabel(
            inner,
            text="Website",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=("gray20", "gray85"),
        ).pack(anchor="w")
        url_lbl = ctk.CTkLabel(
            inner,
            text=WEBSITE_URL,
            font=ctk.CTkFont(size=12),
            text_color=LINK_COLOR,
            cursor="hand2",
        )
        url_lbl.pack(anchor="w", pady=(2, 16))
        url_lbl.bind("<Button-1>", lambda e: open_website())

        # Buttons row
        btn_frame = ctk.CTkFrame(inner, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(8, 20))
        ctk.CTkButton(
            btn_frame,
            text="Visit Website",
            font=ctk.CTkFont(size=13),
            fg_color=PRIMARY,
            hover_color="#2563EB",
            command=open_website,
            width=120,
            height=36,
            corner_radius=8,
        ).pack(side="left", padx=(0, 10))
        ctk.CTkButton(
            btn_frame,
            text="OK",
            font=ctk.CTkFont(size=13),
            fg_color=PRIMARY,
            hover_color="#2563EB",
            command=self.destroy,
            width=80,
            height=36,
            corner_radius=8,
        ).pack(side="left")

        # Version at bottom
        ctk.CTkLabel(
            inner,
            text=f"Version: {VERSION}",
            font=ctk.CTkFont(size=11),
            text_color=TEXT_MUTED,
        ).pack(pady=(8, 0))
