"""
Main window: three-section layout (sidebar | workspace | right panel).
Uses CustomTkinter with modern styling. Switches workspace by sidebar selection.
"""
import os
import sys
import threading
import logging
from tkinter import filedialog, messagebox

try:
    import customtkinter as ctk
except ImportError:
    ctk = None

_APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _APP_ROOT not in sys.path:
    sys.path.insert(0, _APP_ROOT)

from core import paths as _paths
from core.config_loader import load_config
from core.document_processor import process_documents
from ui.sidebar import Sidebar
from ui.dashboard_page import DashboardPage
from ui.documents_page import DocumentsPage
from ui.settings_page import SettingsPage
from ui.logs_page import LogsPage
from ui.results_page import ResultsPage
from ui.right_panel import RightPanel
from ui.about_dialog import AboutDialog

LOGGER = logging.getLogger("DocumentExtractor")
LOGGER.setLevel(logging.INFO)

WORKSPACE_BG = "#F8FAFC"


def _open_output_folder(path: str) -> None:
    if not path or not os.path.exists(path):
        return
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        import subprocess
        subprocess.Popen(["open", path])
    else:
        import subprocess
        subprocess.Popen(["xdg-open", path])


class MainWindow:
    """Three-section app: Sidebar | Workspace (pages) | RightPanel."""

    def __init__(self):
        self.base_dir = _paths.get_writable_base() if _paths.is_frozen() else _APP_ROOT
        self.config = load_config(self.base_dir)
        self.is_processing = False
        self.progress_total = 0
        self.progress_processed = 0
        self.progress_errors = 0

        if ctk is None:
            raise RuntimeError("Install CustomTkinter: pip install customtkinter")

        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title("Digi Lekha")
        self.root.geometry("1200x720")
        self.root.minsize(900, 600)
        self.root.configure(fg_color=WORKSPACE_BG)

        self.pages = {}
        self.current_page = None
        self._build_ui()
        self._setup_logging()
        self._show_page("dashboard")
        self.root.update_idletasks()

    def _build_ui(self):
        # Left sidebar
        self.sidebar = Sidebar(self.root, on_select=self._show_page)
        self.sidebar.pack(side="left", fill="y")

        # Center: workspace (stacked pages)
        self.workspace = ctk.CTkFrame(self.root, fg_color=WORKSPACE_BG, corner_radius=0)
        self.workspace.pack(side="left", fill="both", expand=True, padx=0, pady=0)

        # Dashboard
        self.dashboard = DashboardPage(self.workspace, self.base_dir)
        self.dashboard.on_start = self._start_processing
        self.dashboard.on_open_output = lambda: _open_output_folder(self.dashboard.output_var.get())
        self.pages["dashboard"] = self.dashboard

        # Documents
        self.documents = DocumentsPage(self.workspace)
        self.documents.on_select_document = self._on_select_document
        self.pages["documents"] = self.documents

        # Extraction Settings
        self.settings_page = SettingsPage(self.workspace, self.base_dir)
        self.settings_page.on_save = lambda cfg: setattr(self, "config", cfg)
        self.pages["settings_extract"] = self.settings_page

        # Logs
        self.logs_page = LogsPage(self.workspace)
        self.pages["logs"] = self.logs_page

        # Results
        self.results_page = ResultsPage(self.workspace)
        self.results_page.on_export_click = lambda: _open_output_folder(self.dashboard.output_var.get())
        self.pages["results"] = self.results_page

        # Right panel (Preview + Extracted fields) — shown only on Documents tab
        self.right_panel = RightPanel(self.root)

        # Bottom sidebar: Settings -> extraction settings page; About -> messagebox
        # (handled in sidebar _select: "settings" and "about" keys)
        # We need to handle them in _show_page
        self.sidebar.buttons.get("settings")
        self.sidebar.buttons.get("about")

    def _show_page(self, key: str):
        if key == "about":
            AboutDialog(self.root)
            return
        page_key = key
        if key == "settings":
            page_key = "settings_extract"
        if self.current_page:
            self.pages[self.current_page].place_forget()
        self.current_page = page_key
        if page_key in self.pages:
            self.pages[page_key].place(in_=self.workspace, x=0, y=0, relwidth=1, relheight=1)
        self.sidebar.selected_key = key
        self.sidebar._update_highlight()
        # Show right panel (Preview + Extracted fields) only on Documents tab
        if page_key == "documents":
            self.right_panel.pack(side="right", fill="y")
            self.documents.set_input_dir(self.dashboard.input_var.get())
        else:
            self.right_panel.pack_forget()
        if page_key == "results":
            self.results_page.set_output_dir(self.dashboard.output_var.get())
            self.results_page.load_preview()

    def _on_select_document(self, path: str, data: dict):
        self.right_panel.set_output_dir(self.dashboard.output_var.get())
        self.right_panel.show_document(path, data)

    def _setup_logging(self):
        class DualLogHandler(logging.Handler):
            def __init__(self, logs_page_append):
                super().__init__()
                self.logs_append = logs_page_append

            def emit(self, record):
                msg = self.format(record)
                level = "error" if record.levelno >= logging.ERROR else ("success" if "SUCCESS" in msg or "Finished" in msg else "info")
                def do():
                    try:
                        self.logs_append(msg, level)
                    except Exception:
                        pass
                self.logs_page._textbox and getattr(self.logs_page._textbox, "after", lambda ms, fn: fn())(0, do)

        # Simpler: just use a handler that writes to logs_page if we have reference
        self._log_buffer = []

        class BufferHandler(logging.Handler):
            def __init__(self, app_ref):
                super().__init__()
                self.app_ref = app_ref

            def emit(self, record):
                msg = self.format(record)
                level = "error" if record.levelno >= logging.ERROR else ("success" if "SUCCESS" in msg or "Finished" in msg else "info")
                def flush():
                    try:
                        lp = self.app_ref.logs_page
                        lp.append(msg, level)
                    except Exception:
                        pass
                try:
                    self.app_ref.root.after(0, flush)
                except Exception:
                    pass

        h = BufferHandler(self)
        h.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        LOGGER.addHandler(h)

    def _log(self, message: str, is_error: bool = False):
        if is_error:
            LOGGER.error(message)
        else:
            LOGGER.info(message)
        self.root.update_idletasks()

    def _start_processing(self):
        if self.is_processing:
            return
        self.is_processing = True
        self.dashboard.set_processing_state(True)
        self.progress_total = 0
        self.progress_processed = 0
        self.progress_errors = 0
        self.dashboard.set_progress(0, 0, 0)
        self.root.update_idletasks()
        self.documents.set_input_dir(self.dashboard.input_var.get())
        input_dir = self.dashboard.input_var.get().strip()
        output_dir = self.dashboard.output_var.get().strip()

        def run():
            try:
                process_documents(
                    input_dir,
                    output_dir,
                    self.base_dir,
                    self.config,
                    log_callback=self._log,
                    progress_callback=self._on_progress,
                    status_callback=lambda t: self.root.after(0, lambda: None),
                    on_file_done=self._on_file_done,
                )
                self.root.after(0, lambda: messagebox.showinfo("Success", "Document processing completed!"))
                self.root.after(0, self.results_page.load_preview)
            except Exception as e:
                self._log(f"Critical error: {e}", is_error=True)
                self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
            finally:
                self.root.after(0, self._processing_done)

        thread = threading.Thread(target=run, daemon=True)
        thread.start()

    def _on_progress(self, current: int, total: int):
        self.progress_total = total
        self.progress_processed = current
        def upd():
            self.dashboard.set_progress(self.progress_total, self.progress_processed, self.progress_errors)
        self.root.after(0, upd)

    def _on_file_done(self, filename: str, status: str, doc_type: str, items_count: int):
        if status == "error":
            self.progress_errors = getattr(self, "progress_errors", 0) + 1
        def upd():
            self.documents.update_file_status(filename, status, doc_type, items_count)
        self.root.after(0, upd)

    def _processing_done(self):
        self.is_processing = False
        self.dashboard.set_processing_state(False)
        self.dashboard.set_progress(self.progress_total, self.progress_processed, self.progress_errors)

    def run(self):
        self.root.mainloop()


def main():
    app = MainWindow()
    app.run()


if __name__ == "__main__":
    main()
