"""
Document processing pipeline: discover files, preprocess images, call OpenAI Vision,
parse response, write Excel, move processed files. Runs in a worker thread.
"""
import os
import glob
import shutil
from datetime import datetime

from .image_preprocessor import preprocess_image, cleanup_temp_files
from .openai_extractor import extract_from_images, parse_extraction_response, get_openai_api_key
from .excel_writer import (
    write_to_excel,
    build_challan_excel_filename,
)
from .totals_reconcile import (
    header_grand_totals,
    merge_header_totals,
    reconcile_challan_excel,
)


def ensure_directories(input_dir: str, output_dir: str, base_dir: str) -> tuple[str, str]:
    """
    Create input, output, processed, logs dirs. Return (processed_dir, logs_dir).
    """
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    parent = os.path.dirname(input_dir) or base_dir
    processed_dir = os.path.join(parent, "processed")
    logs_dir = os.path.join(parent, "logs")
    os.makedirs(processed_dir, exist_ok=True)
    os.makedirs(logs_dir, exist_ok=True)
    return processed_dir, logs_dir


def load_supported_files(input_dir: str) -> list:
    """Return sorted list of supported file paths (jpg, jpeg, png, pdf)."""
    files = []
    for ext in ("*.jpg", "*.jpeg", "*.png", "*.pdf"):
        files.extend(glob.glob(os.path.join(input_dir, ext)))
        files.extend(glob.glob(os.path.join(input_dir, ext.upper())))
    return sorted(list(set(files)))


def move_to_processed(file_path: str, processed_dir: str, log_callback=None) -> None:
    """Move file to processed_dir; add timestamp suffix if duplicate."""
    name = os.path.basename(file_path)
    dest = os.path.join(processed_dir, name)
    if os.path.exists(dest):
        base, ext = os.path.splitext(name)
        dest = os.path.join(processed_dir, f"{base}_{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}")
    shutil.move(file_path, dest)
    if log_callback:
        log_callback(f"Moved {name} to processed folder")


def _header_value(header: dict, *keys: str) -> str:
    if not isinstance(header, dict):
        return ""
    for k in keys:
        v = header.get(k)
        if v is not None and str(v).strip() != "":
            return str(v).strip()
    return ""


def _apply_header_carryforward(data: dict, last_header: dict) -> dict:
    """
    Continuation pages often omit Challan No. / company.
    Reuse the previous page header when the current page has no challan_number.
    If challan_number matches the previous page, keep the previous company name
    so OCR typos do not create a second Excel for the same challan.
    Preserve printed Grand Totals once seen until a newer Grand Total overwrites them.
    """
    header = dict(data.get("header") or {})
    curr_challan = _header_value(header, "challan_number", "challan_no")
    last_challan = _header_value(last_header, "challan_number", "challan_no")

    if not curr_challan and last_header:
        merged = dict(last_header)
        for k, v in header.items():
            if v is not None and str(v).strip() != "":
                merged[k] = v
        # Prefer stable From-company / challan identity from the previous page.
        for key in ("company_name", "supplier_name", "from_company", "mill_name", "challan_number"):
            if _header_value(last_header, key):
                merged[key] = last_header[key]
        merged = merge_header_totals(merged, header)
        # If this page had no grand totals, keep previous.
        g, f = header_grand_totals(header)
        if g is None and f is None:
            merged = merge_header_totals(merged, last_header)
        data["header"] = merged
        return merged

    if curr_challan and last_challan and curr_challan == last_challan and last_header:
        for key in ("company_name", "supplier_name", "from_company", "mill_name"):
            if _header_value(last_header, key):
                header[key] = last_header[key]
        g, f = header_grand_totals(header)
        if g is None and f is None:
            header = merge_header_totals(header, last_header)
        data["header"] = header
        return header

    data["header"] = header
    return header


def _write_challan_excel(
    data: dict,
    source_label: str,
    output_dir: str,
    challan_output_dir: str,
    config: dict,
    log_callback=None,
) -> tuple[str, int]:
    """Write/append one challan extraction. Returns (excel_path, items_count)."""
    excel_name = build_challan_excel_filename(data)
    challan_output_file = os.path.join(challan_output_dir, excel_name)
    if log_callback:
        log_callback(f"Challan Excel: {challan_output_file}")
    write_to_excel(
        data,
        source_label,
        output_dir,
        config,
        output_file=challan_output_file,
    )
    return challan_output_file, len(data.get("items", []) or [])


def _update_challan_state(
    challan_states: dict,
    excel_path: str,
    data: dict,
    page_image: str,
    source_label: str,
) -> None:
    """Accumulate items, header totals, and page images per challan Excel."""
    state = challan_states.setdefault(
        excel_path,
        {"items": [], "header": {}, "images": [], "source_label": source_label},
    )
    state["source_label"] = source_label
    state["header"] = merge_header_totals(
        dict(state.get("header") or {}),
        dict(data.get("header") or {}),
    )
    # Keep identity fields from latest header when present.
    for key in (
        "challan_number",
        "challan_no",
        "company_name",
        "party_name",
        "ewb_no",
        "goods_value",
    ):
        v = (data.get("header") or {}).get(key)
        if v is not None and str(v).strip() != "":
            state["header"][key] = v
    for it in data.get("items") or []:
        if isinstance(it, dict):
            state["items"].append(dict(it))
    if page_image and page_image not in state["images"]:
        state["images"].append(page_image)


def process_documents(
    input_dir: str,
    output_dir: str,
    base_dir: str,
    config: dict,
    *,
    log_callback=None,
    progress_callback=None,
    status_callback=None,
    on_file_done=None,
) -> None:
    """
    Main processing loop. Call from a background thread.
    Multi-page PDFs are extracted page-by-page so different challans become
    separate Excel files; continuation pages of the same challan append together.
    After all files, printed Grand Totals are checked against extracted meter sums.
    """
    if not get_openai_api_key(base_dir):
        if log_callback:
            log_callback("OpenAI API Key required. Set OPENAI_API_KEY in env or .env.", True)
        return

    processed_dir, logs_dir = ensure_directories(input_dir, output_dir, base_dir)
    run_date = datetime.now().strftime("%Y-%m-%d")
    challan_output_dir = os.path.join(output_dir, "delivery_challan", run_date)
    os.makedirs(challan_output_dir, exist_ok=True)
    if log_callback:
        log_callback(f"Challan output folder: {challan_output_dir}")
        log_callback("Invoice export is disabled for now.")
    files = load_supported_files(input_dir)

    if not files:
        if log_callback:
            log_callback("No files found to process.")
        return

    total = len(files)
    if log_callback:
        log_callback(f"Found {total} files to process.")

    challan_states: dict = {}
    all_temp_images: list = []

    try:
        for i, file_path in enumerate(files):
            filename = os.path.basename(file_path)
            if status_callback:
                status_callback(f"Processing {i + 1} of {total}: {filename}")
            if log_callback:
                log_callback(f"--- Starting {filename} ---")

            if log_callback:
                log_callback("Preprocessing image...")
            processed_images = preprocess_image(file_path, log_callback)
            if not processed_images:
                if log_callback:
                    log_callback(f"Skipping {filename} due to preprocessing failure.", True)
                if on_file_done:
                    on_file_done(filename, "error", "", 0)
                if progress_callback:
                    progress_callback(i + 1, total)
                continue

            all_temp_images.extend(processed_images)
            page_count = len(processed_images)
            if log_callback and page_count > 1:
                log_callback(f"Multi-page document ({page_count} pages) — extracting each page separately.")

            last_header = {}
            total_items = 0
            wrote_any = False
            saw_invoice_only = False
            last_doc_type = "delivery_challan"
            excel_files_written = set()
            last_excel_path = None

            for page_idx, page_image in enumerate(processed_images):
                page_label = f"{filename}#page{page_idx + 1}" if page_count > 1 else filename
                if log_callback:
                    log_callback(f"Sending page {page_idx + 1}/{page_count} to OpenAI API...")

                response_text = extract_from_images(
                    [page_image], config, base_dir, log_callback
                )
                if not response_text:
                    if log_callback:
                        log_callback(f"Skipping page {page_idx + 1} due to API failure.", True)
                    continue

                if log_callback:
                    log_callback(f"Parsing page {page_idx + 1} response...")
                try:
                    data = parse_extraction_response(response_text, page_label, logs_dir)
                except ValueError as e:
                    if log_callback:
                        log_callback(str(e), True)
                    continue

                doc_type = str(data.get("document_type", "")).strip().lower()
                last_doc_type = doc_type or last_doc_type
                if "invoice" in doc_type:
                    saw_invoice_only = saw_invoice_only or not wrote_any
                    if log_callback:
                        log_callback(
                            f"Skipping invoice on page {page_idx + 1} (invoice export disabled)."
                        )
                    continue

                header = _apply_header_carryforward(data, last_header)
                if _header_value(header, "challan_number", "challan_no"):
                    last_header = dict(data.get("header") or header)

                items = data.get("items") or []
                g_tot, f_tot = header_grand_totals(header)
                if g_tot is not None or f_tot is not None:
                    if log_callback:
                        log_callback(
                            f"Grand Total on page {page_idx + 1}: "
                            f"Grey={g_tot if g_tot is not None else '—'}, "
                            f"Finish={f_tot if f_tot is not None else '—'}"
                        )

                if not items:
                    # Still attach grand totals / image to the open challan when possible.
                    if last_excel_path and (g_tot is not None or f_tot is not None):
                        _update_challan_state(
                            challan_states,
                            last_excel_path,
                            data,
                            page_image,
                            page_label,
                        )
                    if log_callback:
                        log_callback(f"No line items on page {page_idx + 1}.")
                    continue

                if log_callback:
                    log_callback(f"Writing page {page_idx + 1} ({len(items)} items) to Excel...")
                try:
                    excel_path, n_items = _write_challan_excel(
                        data,
                        page_label,
                        output_dir,
                        challan_output_dir,
                        config,
                        log_callback=log_callback,
                    )
                    excel_files_written.add(excel_path)
                    last_excel_path = excel_path
                    _update_challan_state(
                        challan_states,
                        excel_path,
                        data,
                        page_image,
                        page_label,
                    )
                    total_items += n_items
                    wrote_any = True
                    saw_invoice_only = False
                except Exception as e:
                    if log_callback:
                        log_callback(f"Excel writing error on page {page_idx + 1}: {e}", True)
                    continue

            if not wrote_any:
                status = "skipped" if saw_invoice_only else "error"
                if on_file_done:
                    on_file_done(filename, status, last_doc_type if saw_invoice_only else "", 0)
                if saw_invoice_only:
                    move_to_processed(file_path, processed_dir, log_callback)
                if progress_callback:
                    progress_callback(i + 1, total)
                continue

            move_to_processed(file_path, processed_dir, log_callback)
            if log_callback:
                log_callback(
                    f"SUCCESS {filename}: {total_items} items across "
                    f"{len(excel_files_written)} Excel file(s)"
                )
            if on_file_done:
                on_file_done(filename, "completed", str(last_doc_type), total_items)

            if progress_callback:
                progress_callback(i + 1, total)

        if challan_states:
            if status_callback:
                status_callback("Checking Grand Totals...")
            if log_callback:
                log_callback("--- Grand Total reconciliation ---")
            for excel_path, state in challan_states.items():
                try:
                    reconcile_challan_excel(
                        excel_path,
                        state,
                        config,
                        base_dir,
                        log_callback=log_callback,
                    )
                except Exception as e:
                    if log_callback:
                        log_callback(
                            f"Totals reconciliation error for {os.path.basename(excel_path)}: {e}",
                            True,
                        )
    finally:
        cleanup_temp_files(all_temp_images)

    if status_callback:
        status_callback("Processing Complete!")
    if log_callback:
        log_callback("=== Processing Finished ===")
