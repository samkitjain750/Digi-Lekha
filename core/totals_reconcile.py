"""
Reconcile extracted challan line-item meter sums against printed Grand Totals.
On mismatch, re-read page images with OpenAI and rewrite the Excel if fixed.
"""
from __future__ import annotations

import json
import os
from typing import Callable

from core.excel_writer import _safe_float, rewrite_challan_excel
from core.openai_extractor import (
    OPENAI_AVAILABLE,
    OpenAI,
    _encode_image_b64,
    _image_mime,
    get_openai_api_key,
    get_openai_model,
    parse_extraction_response,
)

TOTALS_TOLERANCE = 0.05  # allow tiny float / rounding noise


def header_grand_totals(header: dict) -> tuple[float | None, float | None]:
    """Return (grand_total_grey, grand_total_finished) from header, if present."""
    if not isinstance(header, dict):
        return None, None
    grey = _safe_float(
        header.get("grand_total_grey_mtrs")
        or header.get("grand_total_grey")
        or header.get("total_grey_mtrs")
    )
    finished = _safe_float(
        header.get("grand_total_finished_mtrs")
        or header.get("grand_total_finished")
        or header.get("grand_total_finish_mtrs")
        or header.get("total_finished_mtrs")
        or header.get("total_dispatch_mtr")
    )
    return grey, finished


def merge_header_totals(target: dict, source: dict) -> dict:
    """Copy grand totals from source into target when source has them."""
    out = dict(target or {})
    g, f = header_grand_totals(source or {})
    if g is not None:
        out["grand_total_grey_mtrs"] = g
    if f is not None:
        out["grand_total_finished_mtrs"] = f
    return out


def sum_item_meters(items: list) -> tuple[float, float]:
    """Sum grey_mtrs and finished/dispatch meters across line items."""
    grey_sum = 0.0
    fin_sum = 0.0
    for it in items or []:
        if not isinstance(it, dict):
            continue
        g = _safe_float(it.get("grey_mtrs"))
        f = _safe_float(
            it.get("dispatch_mtr", it.get("finished_mtrs", it.get("fin_mtrs")))
        )
        if g is not None:
            grey_sum += g
        if f is not None:
            fin_sum += f
    return round(grey_sum, 2), round(fin_sum, 2)


def totals_match(
    printed_grey: float | None,
    printed_fin: float | None,
    sum_grey: float,
    sum_fin: float,
    tol: float = TOTALS_TOLERANCE,
) -> tuple[bool, bool]:
    """Return (grey_ok, finished_ok). Missing printed total => treat as ok (skip check)."""
    grey_ok = printed_grey is None or abs(printed_grey - sum_grey) <= tol
    fin_ok = printed_fin is None or abs(printed_fin - sum_fin) <= tol
    return grey_ok, fin_ok


def _build_correction_prompt(
    printed_grey: float | None,
    printed_fin: float | None,
    sum_grey: float,
    sum_fin: float,
    items: list,
) -> str:
    diff_g = None if printed_grey is None else round(printed_grey - sum_grey, 2)
    diff_f = None if printed_fin is None else round(printed_fin - sum_fin, 2)
    payload = {
        "printed_grand_total_grey_mtrs": printed_grey,
        "printed_grand_total_finished_mtrs": printed_fin,
        "extracted_sum_grey_mtrs": sum_grey,
        "extracted_sum_finished_mtrs": sum_fin,
        "diff_grey_mtrs_printed_minus_sum": diff_g,
        "diff_finished_mtrs_printed_minus_sum": diff_f,
        "current_items": items,
    }
    return f"""You are correcting OCR extraction for a textile delivery challan.

The printed Grand Total (Grey Mtrs / Finished Mtrs) does not match the sum of extracted line items.
Find the mistake(s) by re-reading the image(s): wrong meters, missing row, duplicate row,
decimal error, or a Quality Total / Grand Total wrongly included as a line item.

Rules:
- Return ONLY valid JSON (no markdown).
- Include EVERY line item that has a printed S.No. across all provided pages (full corrected list).
- Do NOT invent rows. Do NOT include Quality Total / Grand Total as items.
- Keep s_no as the printed S.No. value.
- After your corrections, sum(grey_mtrs) MUST equal printed_grand_total_grey_mtrs
  and sum(finished_mtrs) MUST equal printed_grand_total_finished_mtrs (within 0.05).
- Also return the printed grand totals in header.

JSON shape:
{{
  "document_type": "delivery_challan",
  "header": {{
    "grand_total_grey_mtrs": <number>,
    "grand_total_finished_mtrs": <number>
  }},
  "items": [
    {{
      "s_no": ...,
      "piece_no": ...,
      "grey_mtrs": ...,
      "finished_mtrs": ...,
      "shrinkage_percent": ...,
      "flag": false,
      "reason": ""
    }}
  ],
  "corrections_made": ["short description of each fix"]
}}

Mismatch context:
{json.dumps(payload, ensure_ascii=False, indent=2)}
"""


def request_corrected_extraction(
    image_paths: list,
    items: list,
    printed_grey: float | None,
    printed_fin: float | None,
    sum_grey: float,
    sum_fin: float,
    app_base_dir: str,
    log_callback: Callable | None = None,
) -> dict | None:
    """Ask OpenAI to return a corrected full items list for the challan images."""
    if not OPENAI_AVAILABLE:
        if log_callback:
            log_callback("OpenAI SDK not available for totals correction.", True)
        return None
    api_key = get_openai_api_key(app_base_dir)
    if not api_key:
        if log_callback:
            log_callback("OpenAI API key missing; cannot correct totals.", True)
        return None
    if not image_paths:
        if log_callback:
            log_callback("No page images available for totals correction.", True)
        return None

    # Cap images to keep request size reasonable (multi-page challans).
    paths = list(image_paths)[-12:]
    prompt = _build_correction_prompt(
        printed_grey, printed_fin, sum_grey, sum_fin, items
    )
    content = [{"type": "text", "text": prompt}]
    for path in paths:
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
                log_callback(f"Could not read image for correction: {e}", True)
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
                log_callback("Totals correction returned empty response.", True)
            return None
        return parse_extraction_response(text, "totals_correction", logs_dir="")
    except Exception as e:
        if log_callback:
            log_callback(f"Totals correction API error: {e}", True)
        return None


def reconcile_challan_excel(
    excel_path: str,
    state: dict,
    config: dict,
    app_base_dir: str,
    log_callback: Callable | None = None,
) -> bool:
    """
    Compare Sheet1 item sums to printed Grand Totals for one challan Excel.
    If mismatch, attempt one correction pass and rewrite the Excel on success.
    Returns True if totals match (or no printed totals to check).
    """
    items = list(state.get("items") or [])
    header = dict(state.get("header") or {})
    images = list(state.get("images") or [])
    source_label = str(state.get("source_label") or os.path.basename(excel_path))

    printed_grey, printed_fin = header_grand_totals(header)
    if printed_grey is None and printed_fin is None:
        if log_callback:
            log_callback(
                f"Totals check skipped for {os.path.basename(excel_path)} "
                "(no Grand Total found on images)."
            )
        return True

    sum_grey, sum_fin = sum_item_meters(items)
    grey_ok, fin_ok = totals_match(printed_grey, printed_fin, sum_grey, sum_fin)

    def _fmt(v):
        return "—" if v is None else f"{v:.2f}"

    if grey_ok and fin_ok:
        if log_callback:
            log_callback(
                f"Totals OK {os.path.basename(excel_path)}: "
                f"Grey {_fmt(sum_grey)}={_fmt(printed_grey)}, "
                f"Finish {_fmt(sum_fin)}={_fmt(printed_fin)}"
            )
        return True

    if log_callback:
        log_callback(
            f"Totals MISMATCH {os.path.basename(excel_path)}: "
            f"Grey sum={_fmt(sum_grey)} printed={_fmt(printed_grey)} "
            f"(diff={_fmt(None if printed_grey is None else round(printed_grey - sum_grey, 2))}); "
            f"Finish sum={_fmt(sum_fin)} printed={_fmt(printed_fin)} "
            f"(diff={_fmt(None if printed_fin is None else round(printed_fin - sum_fin, 2))}). "
            "Re-checking images to find the mistake...",
            True,
        )

    corrected = request_corrected_extraction(
        images,
        items,
        printed_grey,
        printed_fin,
        sum_grey,
        sum_fin,
        app_base_dir,
        log_callback=log_callback,
    )
    if not corrected:
        _append_mismatch_validation(
            excel_path,
            config,
            source_label,
            printed_grey,
            printed_fin,
            sum_grey,
            sum_fin,
            items,
        )
        return False

    new_items = corrected.get("items") or []
    new_header = merge_header_totals(header, corrected.get("header") or {})
    # Prefer original printed totals if correction omitted them.
    if printed_grey is not None:
        new_header["grand_total_grey_mtrs"] = printed_grey
    if printed_fin is not None:
        new_header["grand_total_finished_mtrs"] = printed_fin

    new_sum_g, new_sum_f = sum_item_meters(new_items)
    pg, pf = header_grand_totals(new_header)
    # Compare against originally printed totals when available.
    check_g = printed_grey if printed_grey is not None else pg
    check_f = printed_fin if printed_fin is not None else pf
    ok_g, ok_f = totals_match(check_g, check_f, new_sum_g, new_sum_f)

    if not (ok_g and ok_f) or not new_items:
        if log_callback:
            log_callback(
                f"Correction still mismatched for {os.path.basename(excel_path)}: "
                f"Grey {_fmt(new_sum_g)} vs {_fmt(check_g)}, "
                f"Finish {_fmt(new_sum_f)} vs {_fmt(check_f)}.",
                True,
            )
        _append_mismatch_validation(
            excel_path,
            config,
            source_label,
            printed_grey,
            printed_fin,
            sum_grey,
            sum_fin,
            items,
        )
        return False

    notes = corrected.get("corrections_made") or []
    if log_callback:
        if notes:
            log_callback(f"Corrections applied: {'; '.join(str(n) for n in notes)}")
        log_callback(
            f"Totals fixed {os.path.basename(excel_path)}: "
            f"Grey {_fmt(new_sum_g)}={_fmt(check_g)}, "
            f"Finish {_fmt(new_sum_f)}={_fmt(check_f)}. Rewriting Excel..."
        )

    state["items"] = new_items
    state["header"] = new_header
    rewrite_challan_excel(
        excel_path,
        {"header": new_header, "items": new_items, "document_type": "delivery_challan"},
        source_label,
        config,
    )
    return True


def _append_mismatch_validation(
    excel_path: str,
    config: dict,
    source_label: str,
    printed_grey,
    printed_fin,
    sum_grey,
    sum_fin,
    items: list,
) -> None:
    """Leave existing Sheet1; add a totals-mismatch row on Validation_Report via rewrite note."""
    # Keep original items; rewrite so Validation includes an explicit totals failure row.
    reason = (
        f"Grand total mismatch: printed Grey={printed_grey} sum={sum_grey}; "
        f"printed Finish={printed_fin} sum={sum_fin}. Auto-correction failed."
    )
    rewrite_challan_excel(
        excel_path,
        {
            "header": {
                "grand_total_grey_mtrs": printed_grey,
                "grand_total_finished_mtrs": printed_fin,
            },
            "items": items,
            "document_type": "delivery_challan",
        },
        source_label,
        config,
        totals_note=reason,
        totals_failed=True,
    )
