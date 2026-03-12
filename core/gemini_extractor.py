"""
Google Gemini Vision integration: API key resolution, dynamic prompt from settings,
and document extraction (JSON response parsing).
"""
import os
import json
from datetime import datetime

try:
    import google.generativeai as genai
    from PIL import Image
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    Image = None
    genai = None

from . import paths as _paths

# Gemini model name (update if deprecated)
GEMINI_MODEL = "gemini-2.5-flash"


def get_gemini_api_key(app_base_dir: str = None) -> str:
    """
    Get Gemini API key from (1) env GEMINI_API_KEY, (2) .env in app dir, (3) config/api_key.json.
    app_base_dir: used for .env lookup when not frozen; ignored for api_key.json (uses paths).
    Returns empty string if not set.
    """
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key:
        return key
    if app_base_dir:
        env_path = os.path.join(app_base_dir, ".env")
        if os.path.isfile(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("GEMINI_API_KEY="):
                            key = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if key:
                                return key
                            break
            except Exception:
                pass
    api_key_path = _paths.get_api_key_path()
    if os.path.isfile(api_key_path):
        try:
            with open(api_key_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                key = (data.get("api_key") or data.get("GEMINI_API_KEY") or "").strip()
                if key:
                    return key
        except Exception:
            pass
    return ""


def save_gemini_api_key(api_key: str) -> None:
    """Store API key in config/api_key.json (writable app data when frozen)."""
    path = _paths.get_api_key_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"api_key": api_key.strip()}, f, indent=2)


def build_extraction_prompt(config: dict) -> str:
    """
    Build the system prompt for Gemini using only the fields enabled in config.
    config keys: invoice_fields, invoice_table_fields, challan_fields, challan_table_fields
    (each is a list of field names).
    """
    inv_h = config.get("invoice_fields") or []
    inv_t = config.get("invoice_table_fields") or []
    ch_h = config.get("challan_fields") or []
    ch_t = config.get("challan_table_fields") or []

    inv_header_str = ", ".join(inv_h) if inv_h else "(none)"
    inv_table_str = ", ".join(inv_t) if inv_t else "(none)"
    ch_header_str = ", ".join(ch_h) if ch_h else "(none)"
    ch_table_str = ", ".join(ch_t) if ch_t else "(none)"

    return f"""You are an expert OCR document parser.

You will receive a scanned business document image. The document will be one of:
- Tax Invoice
- Job Delivery Challan

STEP 1 — IDENTIFY DOCUMENT TYPE
Return exactly: "invoice" or "delivery_challan"

STEP 2 — EXTRACT HEADER INFORMATION
If the document is an INVOICE extract only these fields: {inv_header_str}
If the document is a DELIVERY CHALLAN extract only these fields: {ch_header_str}

STEP 3 — EXTRACT TABLE ROWS
If the document is an INVOICE extract for each row only: {inv_table_str}
If the document is a DELIVERY CHALLAN extract for each row only: {ch_table_str}

STEP 4 — OUTPUT FORMAT
Return ONLY valid JSON. No explanations, no markdown.
{{
  "document_type": "invoice" or "delivery_challan",
  "header": {{ }},
  "items": [ {{ }} ]
}}

RULES
- Extract values exactly as written. Use empty string "" if missing.
- Numbers stay numbers when possible.
- One object per table row in "items".
- Ignore signatures, stamps, handwritten marks.
- For invoice line items: total_value = taxable_value + tax_amount when both present. Use 2 decimal places for money.
- Return clean JSON only. No code fences."""


def extract_from_images(
    image_paths: list,
    config: dict,
    app_base_dir: str,
    log_callback=None,
) -> str | None:
    """
    Send preprocessed image paths to Gemini and return the raw text response.
    log_callback(message, is_error: bool) is optional for logging.
    Returns None on API/key/parse failure.
    """
    if not GEMINI_AVAILABLE:
        if log_callback:
            log_callback("Google Generative AI not installed. Run: pip install google-generativeai", True)
        return None

    api_key = get_gemini_api_key(app_base_dir)
    if not api_key:
        if log_callback:
            log_callback("Gemini API Key required. Set GEMINI_API_KEY in env or .env file.", True)
        return None

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(GEMINI_MODEL)
        prompt = build_extraction_prompt(config) + "\n\nReturn ONLY valid JSON. No markdown, no explanation."
        parts = [prompt]
        for path in image_paths:
            parts.append(Image.open(path))
        response = model.generate_content(parts)
        if not response or not response.text:
            if log_callback:
                log_callback("Gemini returned empty response.", True)
            return None
        return response.text.strip()
    except Exception as e:
        if log_callback:
            log_callback(f"Gemini API Error: {e}", True)
        return None


def parse_extraction_response(text: str, file_name: str, logs_dir: str = "") -> dict | None:
    """
    Parse Gemini's text response into a JSON object.
    Strips markdown code fences if present. On failure logs to logs_dir/errors.txt and returns None.
    """
    json_str = text
    if "```json" in text:
        json_str = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        json_str = text.split("```")[1].split("```")[0].strip()

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        if logs_dir:
            try:
                err_path = os.path.join(logs_dir, "errors.txt")
                with open(err_path, "a", encoding="utf-8") as f:
                    f.write(f"--- ERROR: {file_name} at {datetime.now()} ---\n")
                    f.write(text + "\n\n")
            except Exception:
                pass
        raise ValueError(f"JSON parse error for {file_name}: {e}") from e
