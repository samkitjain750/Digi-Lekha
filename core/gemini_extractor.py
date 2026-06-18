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
    Build OCR prompt supporting both delivery challans and invoices.
    """
    return """You are an OCR extraction and validation engine for textile challans/invoices.

Identify document type first:
- delivery_challan
- invoice

Always return ONLY valid JSON object (no markdown/no explanation):
{
  "document_type": "delivery_challan" or "invoice",
  "header": {},
  "items": []
}

For DELIVERY CHALLAN:
- Extract row-wise:
  piece_no, grey_mtrs, finished_mtrs, shrinkage_percent, flag, reason
- Alias mapping:
  finished_mtrs <- Finished Mtrs/Finished Mtr/Dispatch Mtr/Dispatch Mtrs/Final Mtrs/Net Mtrs
  grey_mtrs <- Grey Mtrs/Grey Mtr/Grey
  piece_no <- Piece No/Invoice No/Lot No/Roll No
- Rules:
  1) finished_mtrs < grey_mtrs
  2) shrinkage_percent = ((grey_mtrs - finished_mtrs)/grey_mtrs)*100
  3) normal shrinkage range 2%-10%, outside => flag true
  4) unclear text or column shift => flag true
  5) confusion I/J, O/0, S/5, B/8 => flag true

For INVOICE:
- Extract header fields when visible:
  supplier_name, supplier_gstin, bill_to, bill_to_gstin, invoice_number, invoice_date,
  challan_number, ewb_no, ack_no, irn, state_code
- Extract these table fields row-wise when visible:
  quality, finished_mtrs, rate, and amount (line total / Amount column if printed; else empty string)
- Alias mapping for finished_mtrs same as above.
- amount <- Amount/Value/Total/Line Amount when present.
- If a row value is unclear, set flag true and add reason.

Keep decimals as printed. Use empty string for missing values.
"""


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
        parsed = json.loads(json_str)
        # Support legacy strict challan prompt that returns a JSON array of rows.
        if isinstance(parsed, list):
            items = []
            for row in parsed:
                if not isinstance(row, dict):
                    continue
                items.append(
                    {
                        "piece_number": row.get("piece_no", ""),
                        "dispatch_mtr": row.get("finished_mtrs", ""),
                        "grey_mtrs": row.get("grey_mtrs", ""),
                        "shrinkage_percent": row.get("shrinkage_percent", ""),
                        "flag": row.get("flag", False),
                        "reason": row.get("reason", ""),
                    }
                )
            return {
                "document_type": "delivery_challan",
                "header": {},
                "items": items,
            }
        # Normalize invoice items from aliases
        if isinstance(parsed, dict) and str(parsed.get("document_type", "")).strip().lower().startswith("invoice"):
            items = parsed.get("items", []) or []
            norm_items = []
            for row in items:
                if not isinstance(row, dict):
                    continue
                norm_items.append(
                    {
                        "quality": row.get("quality", row.get("item_description", "")),
                        "finished_mtrs": row.get("finished_mtrs", row.get("fin_mtrs", row.get("dispatch_mtr", ""))),
                        "rate": row.get("rate", row.get("unit_price", "")),
                        "amount": row.get("amount", row.get("Amount", row.get("line_amount", ""))),
                        "flag": row.get("flag", False),
                        "reason": row.get("reason", ""),
                    }
                )
            parsed["items"] = norm_items
        # Normalize challan items from Gemini field names (piece_no, finished_mtrs)
        elif isinstance(parsed, dict) and "challan" in str(parsed.get("document_type", "")).strip().lower():
            items = parsed.get("items", []) or []
            norm_items = []
            for row in items:
                if not isinstance(row, dict):
                    continue
                norm_items.append(
                    {
                        "piece_number": row.get("piece_number", row.get("piece_no", "")),
                        "dispatch_mtr": row.get("dispatch_mtr", row.get("finished_mtrs", row.get("fin_mtrs", ""))),
                        "grey_mtrs": row.get("grey_mtrs", ""),
                        "shrinkage_percent": row.get("shrinkage_percent", ""),
                        "flag": row.get("flag", False),
                        "reason": row.get("reason", ""),
                    }
                )
            parsed["items"] = norm_items
        return parsed
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
