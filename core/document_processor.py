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
from .excel_writer import write_to_excel, write_invoice_to_excel


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
    log_callback(message: str, is_error: bool)
    progress_callback(current: int, total: int)  # 1-based current
    status_callback(text: str)
    on_file_done(filename: str, status: str, doc_type: str, items_count: int)  # optional
    """
    if not get_openai_api_key(base_dir):
        if log_callback:
            log_callback("OpenAI API Key required. Set OPENAI_API_KEY in env or .env.", True)
        return

    processed_dir, logs_dir = ensure_directories(input_dir, output_dir, base_dir)
    run_date = datetime.now().strftime("%Y-%m-%d")
    run_stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    challan_output_dir = os.path.join(output_dir, "delivery_challan", run_date)
    invoice_output_dir = os.path.join(output_dir, "invoice", run_date)
    os.makedirs(challan_output_dir, exist_ok=True)
    os.makedirs(invoice_output_dir, exist_ok=True)
    challan_output_file = os.path.join(challan_output_dir, f"delivery_challan_{run_stamp}.xlsx")
    invoice_output_file = os.path.join(invoice_output_dir, f"invoice_{run_stamp}.xlsx")
    if log_callback:
        log_callback(f"Run challan output: {challan_output_file}")
        log_callback(f"Run invoice output: {invoice_output_file}")
    files = load_supported_files(input_dir)

    if not files:
        if log_callback:
            log_callback("No files found to process.")
        return

    total = len(files)
    if log_callback:
        log_callback(f"Found {total} files to process.")

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

        if log_callback:
            log_callback("Sending to OpenAI API...")
        response_text = extract_from_images(processed_images, config, base_dir, log_callback)
        if not response_text:
            if log_callback:
                log_callback(f"Skipping {filename} due to API failure.", True)
            if on_file_done:
                on_file_done(filename, "error", "", 0)
            cleanup_temp_files(processed_images)
            if progress_callback:
                progress_callback(i + 1, total)
            continue

        if log_callback:
            log_callback("Parsing response...")
        try:
            data = parse_extraction_response(response_text, filename, logs_dir)
        except ValueError as e:
            if log_callback:
                log_callback(str(e), True)
            if on_file_done:
                on_file_done(filename, "error", "", 0)
            cleanup_temp_files(processed_images)
            if progress_callback:
                progress_callback(i + 1, total)
            continue

        if log_callback:
            log_callback("Writing to Excel...")
        try:
            doc_type = str(data.get("document_type", "")).strip().lower()
            if "invoice" in doc_type:
                write_invoice_to_excel(data, filename, output_file=invoice_output_file)
            else:
                write_to_excel(data, filename, output_dir, config, output_file=challan_output_file)
        except Exception as e:
            if log_callback:
                log_callback(f"Excel writing error: {e}", True)
            if on_file_done:
                on_file_done(filename, "error", "", 0)
            cleanup_temp_files(processed_images)
            if progress_callback:
                progress_callback(i + 1, total)
            continue

        doc_type = data.get("document_type", "")
        if isinstance(doc_type, dict):
            doc_type = doc_type.get("document_type", "")
        items_count = len(data.get("items", []))
        move_to_processed(file_path, processed_dir, log_callback)
        if log_callback:
            log_callback("SUCCESS File processed")
        if on_file_done:
            on_file_done(filename, "completed", str(doc_type), items_count)
        cleanup_temp_files(processed_images)

        if progress_callback:
            progress_callback(i + 1, total)

    if status_callback:
        status_callback("Processing Complete!")
    if log_callback:
        log_callback("=== Processing Finished ===")
