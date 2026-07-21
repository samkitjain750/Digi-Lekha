"""
OpenAI Vision integration: API key resolution, extraction prompt, and JSON parsing.
"""
import base64
import json
import os
from datetime import datetime

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None

from . import paths as _paths

# Vision model for document OCR.
# OpenAI has no gpt-5.5-mini; latest mini with image input is gpt-5.4-mini.
# Override via OPENAI_MODEL in .env (e.g. gpt-5.5, gpt-5-mini, gpt-4o).
DEFAULT_OPENAI_MODEL = "gpt-5.4-mini"


def get_openai_model(app_base_dir: str = None) -> str:
    model = os.environ.get("OPENAI_MODEL", "").strip()
    if model:
        return model
    if app_base_dir:
        env_path = os.path.join(app_base_dir, ".env")
        if os.path.isfile(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("OPENAI_MODEL="):
                            model = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if model:
                                return model
                            break
            except Exception:
                pass
    return DEFAULT_OPENAI_MODEL


def get_openai_api_key(app_base_dir: str = None) -> str:
    """
    Get OpenAI API key from (1) env OPENAI_API_KEY, (2) .env, (3) config/api_key.json.
    Returns empty string if not set.
    """
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if key:
        return key
    if app_base_dir:
        env_path = os.path.join(app_base_dir, ".env")
        if os.path.isfile(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("OPENAI_API_KEY="):
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
                key = (data.get("api_key") or data.get("OPENAI_API_KEY") or "").strip()
                if key:
                    return key
        except Exception:
            pass
    return ""


def save_openai_api_key(api_key: str) -> None:
    """Store API key in config/api_key.json (writable app data when frozen)."""
    path = _paths.get_api_key_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"api_key": api_key.strip()}, f, indent=2)


def build_extraction_prompt(config: dict) -> str:
    """Build OCR prompt supporting both delivery challans and invoices."""
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
- Extract ONLY the delivery challan visible on the provided page/image(s).
- If this page is a continuation of a challan, still extract all visible line items;
  include challan_number/party_name when printed on the page (even on Cont. pages).
- Extract header fields when visible:
  challan_number (header Challan No. only, NOT table Challan No.),
  challan_date,
  company_name (REQUIRED: From / mill / supplier company on the LEFT — e.g. MANSAROVAR INDUSTRIES; NOT the To/buyer),
  party_name (To / buyer / consignee company on the RIGHT — e.g. SAFFRON SUITING),
  party_address, ewb_no, vehicle_no, goods_value
- Never put the To/buyer name into company_name.
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
- Do NOT invent rows from other challans. Skip quality-total / grand-total rows.

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


def _image_mime(path: str) -> str:
    ext = path.lower().rsplit(".", 1)[-1]
    if ext in ("jpg", "jpeg"):
        return "image/jpeg"
    if ext == "png":
        return "image/png"
    if ext == "webp":
        return "image/webp"
    if ext == "gif":
        return "image/gif"
    return "image/jpeg"


def _encode_image_b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def extract_from_images(
    image_paths: list,
    config: dict,
    app_base_dir: str,
    log_callback=None,
) -> str | None:
    """
    Send preprocessed image paths to OpenAI Vision and return the raw text response.
    Returns None on API/key/parse failure.
    """
    if not OPENAI_AVAILABLE:
        if log_callback:
            log_callback("OpenAI SDK not installed. Run: pip install openai", True)
        return None

    api_key = get_openai_api_key(app_base_dir)
    if not api_key:
        if log_callback:
            log_callback("OpenAI API Key required. Set OPENAI_API_KEY in env or .env file.", True)
        return None

    prompt = build_extraction_prompt(config) + "\n\nReturn ONLY valid JSON. No markdown, no explanation."
    content = [{"type": "text", "text": prompt}]
    for path in image_paths:
        try:
            b64 = _encode_image_b64(path)
            mime = _image_mime(path)
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{b64}"},
                }
            )
        except OSError as e:
            if log_callback:
                log_callback(f"Could not read image {path}: {e}", True)
            return None

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=get_openai_model(app_base_dir),
            messages=[{"role": "user", "content": content}],
            max_completion_tokens=16384,
        )
        text = (response.choices[0].message.content or "").strip()
        if not text:
            if log_callback:
                log_callback("OpenAI returned empty response.", True)
            return None
        return text
    except Exception as e:
        if log_callback:
            log_callback(f"OpenAI API Error: {e}", True)
        return None


def parse_extraction_response(text: str, file_name: str, logs_dir: str = "") -> dict | None:
    """
    Parse model text response into a JSON object.
    Strips markdown code fences if present. On failure logs to logs_dir/errors.txt.
    """
    json_str = text
    if "```json" in text:
        json_str = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        json_str = text.split("```")[1].split("```")[0].strip()

    try:
        parsed = json.loads(json_str)
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
