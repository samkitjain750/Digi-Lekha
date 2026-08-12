"""
OpenAI Vision integration: API key resolution, extraction prompt, and JSON parsing.
"""
import base64
import json
import os
import re
from datetime import datetime
from typing import Any

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
    """Build OCR prompt supporting varied process challan layouts + invoices."""
    return """You are an OCR extraction and validation engine for textile delivery challans and invoices.

Different PROCESS houses / mills print DIFFERENT challan layouts. You MUST adapt:
1) Read the title and letterhead (process/company name).
2) Read the table HEADER row(s) on THIS page (when present).
3) Map each printed column to JSON fields by MEANING, not fixed position.
4) Do not assume every challan has the same columns.

Identify document type first:
- delivery_challan  (includes "Delivery Challan", "Job Delivery Challan", dye-job challans)
- invoice

Always return ONLY valid JSON object (no markdown/no explanation):
{
  "document_type": "delivery_challan" or "invoice",
  "header": {},
  "items": []
}

========================
DELIVERY CHALLAN (any process)
========================
- Extract ONLY what is visible on the provided page/image(s).
- Continuation pages (Page 2/3, Cont.): still extract every visible piece row;
  include challan_number / company_name / party_name when printed.
- "Job Delivery Challan" is ALWAYS delivery_challan (never invoice), even with GSTIN/CIN/PAN.

Header fields (when visible):
  challan_number <- header Job Challan No. / Challan No. / DC No. ONLY (e.g. 4020020135)
  challan_date
  company_name <- process/mill letterhead (Sonaselection India Limited, MANSAROVAR, …). NEVER buyer.
  party_name <- To / buyer (SAFFRON SUITING, …)
  party_address, ewb_no, vehicle_no, goods_value
  grand_total_grey_mtrs, grand_total_finished_mtrs
    <- ONLY printed Grand Total row. Not Quality Wise Summary / subtotals.

Line items — one JSON object per fabric PIECE row:
  s_no, quality, table_challan_no, piece_no, grey_mtrs, finished_mtrs, shrinkage_percent, flag, reason

Column meaning (CRITICAL):
  piece_no <- Piece No codes: 4703T, 4736ZA, 3488A, -3956ZQ, 276H-TP
  Piece format: optional leading '-', then 1–5 digits + 1–3 letters ONLY (must end on a letter).
  Drop OCR noise after letters (3052A1 → 3052A; 4002ZC1B → 4002ZC). Never output trailing digits.
  table_challan_no <- Grey Challan / per-row source challan (e.g. 1350, 1351, 1104, 981)
                     NOT header Job Challan No. NOT piece codes. NOT Beam No.
  quality <- Quality No. / Quality Name block on the LEFT
             (WOOL TOUCH, TROUSER BLACK, TROUSER LINE -167, ANGOORA 5002, …).
             Carry forward the quality block name until the next quality block.
  grey_mtrs / finished_mtrs <- Grey MTR / Finish or Dispatch MTR
  s_no <- printed S.No. if present; else 1-based row order on THIS page

NEVER put these into quality / piece_no / table_challan_no:
  PD FD values: FU, PU
  Shade No. values: ANY, DARK
  Treat. values alone: 215%, DMS, CALE (unless that is clearly the only quality label)
  Beam No. (e.g. 232920, 425811)
  Weight (0.325), dates, beam totals

If you see cells "FU" and "ANY" beside a piece code, those are PD FD + Shade — IGNORE them for quality.
quality must be the fabric quality name (TROUSER LINE -167, etc.), never "FU ANY".

Layout examples:
  A) Classic (Mansarovar/Mukesh): S.No | Quality | Challan No. | Piece | Grey | Finish
  B) Sonaselection Job Delivery Challan (page 1 has headers):
     Quality No. | Beam No. | Treat. | PD FD | Shade No. | Piece No | Grey MTR | Finish MTR | … | Grey Challan
     -> quality=Quality No.; piece_no=Piece No; table_challan_no=Grey Challan (1350/1351/…);
        IGNORE Beam, Treat, PD FD (FU/PU), Shade (ANY/DARK).
     On later pages without headers, keep the same mapping: left quality block, then FU/ANY, then piece, grey, finish, date, wgt, Grey Challan.
  C) Other processes: read headers; map by meaning.

Rules:
  1) finished_mtrs < grey_mtrs when both present
  2) shrinkage_percent = ((grey_mtrs - finished_mtrs)/grey_mtrs)*100 when both present
  3) unclear columns => flag true with reason
  4) Do NOT flag merely for letters I,J,L,O,Q,V,W in piece_no
  5) Skip quality headers-only, quality totals, grand totals, Quality Wise Summary rows
  6) Do NOT invent rows; do NOT skip piece rows because S.No. is missing

========================
INVOICE
========================
- Header: supplier_name, supplier_gstin, bill_to, bill_to_gstin, invoice_number, invoice_date,
  challan_number, ewb_no, ack_no, irn, state_code
- Items: quality, finished_mtrs, rate, amount

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


def _looks_like_piece_code(value) -> bool:
    """True for canonical piece codes (1–5 digits + 1–3 letters, ends on letter)."""
    from core.dye_master import is_valid_piece_format

    return is_valid_piece_format(value)


def _canonicalize_piece(value) -> str:
    from core.dye_master import extract_canonical_piece

    return extract_canonical_piece(value) or ""


def _looks_like_job_number(value) -> bool:
    """True for Job No. style values like 232923 / 425815 (not piece codes)."""
    s = str(value or "").strip()
    return s.isdigit() and len(s) >= 5


_BOGUS_QUALITY = {
    "FU",
    "PU",
    "ANY",
    "DARK",
    "FU ANY",
    "PU ANY",
    "FU / ANY",
    "PU / ANY",
    "FU/ANY",
    "PU/ANY",
    "DMS",
    "CALE",
    "215%",
    "215",
    "NAN",
    "NONE",
    "NULL",
}


def _clean_quality(value: Any) -> str:
    """Drop PD FD / Shade / Treat noise wrongly stored as quality (e.g. FU ANY)."""
    s = str(value or "").strip()
    if not s or s.lower() == "nan":
        return ""
    if s.upper() in _BOGUS_QUALITY:
        return ""
    # Entire quality is only FU/PU + ANY/DARK
    toks = [t for t in re.split(r"[^A-Za-z0-9%]+", s.upper()) if t]
    if toks and all(t in ("FU", "PU", "ANY", "DARK", "DMS", "CALE", "215", "215%") for t in toks):
        return ""
    return s


def _normalize_challan_item_row(row: dict, *, fallback_s_no: int | None = None) -> dict | None:
    """
    Normalize one challan line item across different process layouts.
    Repairs common swaps and strips Sonaselection PD FD/Shade noise from quality.
    """
    if not isinstance(row, dict):
        return None

    s_no = row.get("s_no", row.get("sno", row.get("serial_no", row.get("S.No.", row.get("S No.", "")))))
    quality = _clean_quality(row.get("quality", row.get("quality_name", "")))
    table_challan_no = row.get(
        "table_challan_no",
        row.get("challan_no_row", row.get("grey_challan_number", row.get("table_challan", ""))),
    )
    piece_number = row.get("piece_number", row.get("piece_no", ""))
    dispatch_mtr = row.get("dispatch_mtr", row.get("finished_mtrs", row.get("fin_mtrs", "")))
    grey_mtrs = row.get("grey_mtrs", "")
    shrinkage_percent = row.get("shrinkage_percent", "")
    flag = row.get("flag", False)
    reason = row.get("reason", "")

    piece_s = str(piece_number or "").strip()
    table_s = str(table_challan_no or "").strip()
    s_no_s = "" if s_no is None else str(s_no).strip()

    # Piece code landed in table_challan_no, piece empty.
    if not piece_s and _looks_like_piece_code(table_s):
        piece_s = table_s
        table_s = ""
    # Swapped: piece holds short numeric challan, table holds piece code.
    elif (
        _looks_like_piece_code(table_s)
        and piece_s.isdigit()
        and len(piece_s) <= 4
        and not _looks_like_piece_code(piece_s)
    ):
        piece_s, table_s = table_s, piece_s
    # Job No. / Beam wrongly stored as table_challan when we already have a piece code.
    if piece_s and _looks_like_piece_code(piece_s) and _looks_like_job_number(table_s):
        table_s = ""
    # Job No. wrongly used as s_no on job-delivery style forms.
    if piece_s and _looks_like_job_number(s_no_s):
        s_no_s = str(fallback_s_no) if fallback_s_no is not None else ""

    if not piece_s and not str(grey_mtrs or "").strip() and not str(dispatch_mtr or "").strip():
        return None

    if not s_no_s:
        if piece_s and fallback_s_no is not None:
            s_no_s = str(fallback_s_no)
        else:
            return None

    if piece_s:
        piece_s = _canonicalize_piece(piece_s)

    return {
        "s_no": s_no_s,
        "quality": quality,
        "table_challan_no": table_s,
        "piece_number": piece_s,
        "dispatch_mtr": dispatch_mtr,
        "grey_mtrs": grey_mtrs,
        "shrinkage_percent": shrinkage_percent,
        "flag": flag,
        "reason": reason,
    }


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
            for idx, row in enumerate(parsed, start=1):
                norm = _normalize_challan_item_row(row, fallback_s_no=idx)
                if norm:
                    items.append(norm)
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
            for idx, row in enumerate(items, start=1):
                norm = _normalize_challan_item_row(row, fallback_s_no=idx)
                if norm:
                    norm_items.append(norm)
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
