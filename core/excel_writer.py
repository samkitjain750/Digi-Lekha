"""
Excel export: normalize extracted data, filter columns by config, append to extracted_data.xlsx.
"""
import os
import pandas as pd
from datetime import datetime
from openpyxl.styles import PatternFill

from core.invoice_validation import validate_invoice_line_row, _parse_number as _inv_parse_num


def _safe_float(value):
    """Convert to float if possible, else None."""
    if value is None or value == "":
        return None
    try:
        if isinstance(value, (int, float)):
            return float(value)
        s = str(value).strip().replace(",", "")
        return float(s) if s else None
    except (ValueError, TypeError):
        return None


def _normalize_document_type(doc_type: str) -> str:
    """Normalize to 'invoice' or 'delivery_challan'."""
    if not doc_type:
        return "unknown"
    t = str(doc_type).strip().lower().replace(" ", "_")
    if "invoice" in t or t == "invoice":
        return "invoice"
    if "challan" in t or "delivery_challan" in t:
        return "delivery_challan"
    return doc_type


def _normalize_header_value(header: dict, key: str) -> str:
    """Get header value as string, format total_invoice_value to 2 decimals."""
    v = header.get(key) or ""
    if v is None:
        return ""
    v = str(v).strip()
    if key == "total_invoice_value" and v:
        fv = _safe_float(v)
        if fv is not None:
            return f"{fv:.2f}"
    return v


def _normalize_item_row(item: dict, file_name: str) -> dict:
    """
    Build one full item row (invoice + challan columns) with normalized numbers.
    Used for both invoice and challan; unused columns will be filtered later.
    """
    def v(key, default=""):
        x = item.get(key) or default
        return "" if x is None else str(x).strip()

    taxable_val = _safe_float(item.get("taxable_value"))
    tax_amt = _safe_float(item.get("tax_amount"))
    total = _safe_float(item.get("total_value"))
    if taxable_val is not None and tax_amt is not None:
        total = round(taxable_val + tax_amt, 2)
    unit_price = _safe_float(item.get("unit_price"))
    quantity = _safe_float(item.get("quantity"))
    if quantity is None:
        quantity = item.get("quantity") or item.get("dispatch_mtr") or ""

    row = {
        "file_name": file_name,
        "item_description": v("item_description") or v("fabric_name"),
        "hsn_code": v("hsn_code"),
        "quantity": f"{quantity:.2f}" if isinstance(quantity, (int, float)) else quantity,
        "uom": v("uom"),
        "unit_price": f"{unit_price:.2f}" if unit_price is not None else v("unit_price"),
        "discount": v("discount"),
        "taxable_value": f"{taxable_val:.2f}" if taxable_val is not None else v("taxable_value"),
        "gst_rate": v("gst_rate"),
        "tax_amount": f"{tax_amt:.2f}" if tax_amt is not None else v("tax_amount"),
        "total_value": f"{total:.2f}" if total is not None else v("total_value"),
        "fabric_name": v("fabric_name"),
        "fd_number": v("fd_number"),
        "piece_number": v("piece_number") or v("piece_no"),
        "challan_mtr": v("challan_mtr"),
        "dispatch_mtr": v("dispatch_mtr") or v("finished_mtrs") or v("fin_mtrs"),
        "grey_mtrs": v("grey_mtrs"),
        "grey_received_date": v("grey_received_date"),
        "grey_challan_number": v("grey_challan_number"),
        "beam": v("beam"),
    }
    return row


def _build_full_doc_row(header: dict, file_name: str, doc_type: str) -> dict:
    """Build document summary row with all possible columns (filtered by config later)."""
    def h(key):
        return _normalize_header_value(header, key)

    total_inv = h("total_invoice_value")
    return {
        "file_name": file_name,
        "document_type": doc_type,
        "invoice_number": h("invoice_number"),
        "invoice_date": h("invoice_date"),
        "supplier_name": h("supplier_name"),
        "supplier_gstin": h("supplier_gstin"),
        "buyer_name": h("buyer_name"),
        "buyer_gstin": h("buyer_gstin"),
        "buyer_address": h("buyer_address"),
        "state_code": h("state_code"),
        "place_of_supply": h("place_of_supply"),
        "total_taxable_value": h("total_taxable_value"),
        "cgst_amount": h("cgst_amount"),
        "sgst_amount": h("sgst_amount"),
        "igst_amount": h("igst_amount"),
        "total_tax": h("total_tax"),
        "total_invoice_value": total_inv,
        "challan_number": h("challan_number"),
        "challan_date": h("challan_date"),
        "company_name": h("company_name"),
        "party_name": h("party_name"),
        "party_address": h("party_address"),
        "hsn_code": h("hsn_code"),
        "total_beam_total": h("total_beam_total"),
        "total_dispatch_mtr": h("total_dispatch_mtr"),
    }


# Column order for sheets.
DOC_STATIC_COLS = ["file_name", "document_type"]
ITEM_STATIC_COLS = []

# Export headers required by challan import format.
EXPORT_PIECE_COL = "Piece No"
EXPORT_GREY_COL = "Grey Mtrs"
EXPORT_MTR_COL = "Finished Mtrs"


def get_document_columns(config: dict) -> list:
    """Ordered list of document columns to write (file_name, document_type + selected fields)."""
    inv = config.get("invoice_fields") or []
    ch = config.get("challan_fields") or []
    # All possible header keys in display order (no duplicates)
    all_header_keys = [
        "invoice_number", "invoice_date", "supplier_name", "supplier_gstin",
        "buyer_name", "buyer_gstin", "buyer_address", "state_code", "place_of_supply",
        "total_taxable_value", "cgst_amount", "sgst_amount", "igst_amount",
        "total_tax", "total_invoice_value",
        "challan_number", "challan_date", "company_name", "party_name",
        "party_address", "hsn_code", "total_beam_total", "total_dispatch_mtr",
    ]
    selected = [k for k in all_header_keys if k in inv or k in ch]
    return DOC_STATIC_COLS + selected


def get_item_columns(config: dict) -> list:
    """Ordered list of item columns to write in final Excel."""
    ch_t = config.get("challan_table_fields") or []
    # Keep only challan import style columns and map to required export headers.
    all_item_keys = ["piece_number", "grey_mtrs", "dispatch_mtr"]
    selected = [k for k in all_item_keys if k in ch_t]
    if not selected:
        selected = ["piece_number", "grey_mtrs", "dispatch_mtr"]
    out = []
    if "piece_number" in selected:
        out.append(EXPORT_PIECE_COL)
    if "grey_mtrs" in selected:
        out.append(EXPORT_GREY_COL)
    if "dispatch_mtr" in selected:
        out.append(EXPORT_MTR_COL)
    return ITEM_STATIC_COLS + out


def _build_validation_rows(line_items: list, file_name: str) -> list:
    """
    Build validation report rows using extraction flags + deterministic checks:
    - finished_mtrs < grey_mtrs
    - shrinkage between 2% and 10%
    """
    rows = []
    for r in line_items:
        piece = str(r.get("piece_number", "") or "").strip()
        grey = _safe_float(r.get("grey_mtrs"))
        finished = _safe_float(r.get("dispatch_mtr"))
        model_flag = bool(r.get("flag", False))
        reason = str(r.get("reason", "") or "").strip()
        issue_parts = []
        shrinkage = ""

        if grey is not None and finished is not None:
            if finished >= grey:
                issue_parts.append("finished_mtrs is not smaller than grey_mtrs")
            if grey != 0:
                shrink = ((grey - finished) / grey) * 100.0
                shrinkage = round(shrink, 2)
                if shrink < 2 or shrink > 10:
                    issue_parts.append("shrinkage outside 2%-10%")
        else:
            issue_parts.append("missing numeric value(s)")

        final_flag = model_flag or len(issue_parts) > 0
        if not reason and issue_parts:
            reason = "; ".join(issue_parts)

        rows.append(
            {
                "file_name": file_name,
                "piece_no": piece,
                "grey_mtrs": "" if grey is None else grey,
                "finished_mtrs": "" if finished is None else finished,
                "shrinkage_percent": shrinkage,
                "flag": final_flag,
                "reason": reason,
            }
        )
    return rows


def _apply_validation_row_colors(ws, start_data_row: int, end_data_row: int) -> None:
    """
    Color rows in Validation_Report:
    - green when flag is false
    - red when flag is true
    """
    if end_data_row < start_data_row:
        return
    header = [c.value for c in ws[1]]
    try:
        flag_col_idx = header.index("flag") + 1  # 1-based
    except ValueError:
        return

    green_fill = PatternFill(start_color="E8F5E9", end_color="E8F5E9", fill_type="solid")
    red_fill = PatternFill(start_color="FDECEC", end_color="FDECEC", fill_type="solid")

    for row_idx in range(start_data_row, end_data_row + 1):
        flag_val = ws.cell(row=row_idx, column=flag_col_idx).value
        is_flagged = str(flag_val).strip().lower() in {"true", "1", "yes"}
        fill = red_fill if is_flagged else green_fill
        for col_idx in range(1, ws.max_column + 1):
            ws.cell(row=row_idx, column=col_idx).fill = fill


def write_to_excel(
    data: dict,
    file_name: str,
    output_dir: str,
    config: dict,
    output_file: str = None,
) -> bool:
    """
    Append one document's extracted data to extracted_data.xlsx.
    Only columns in config are written. Creates file/sheets if missing.
    """
    output_file = output_file or os.path.join(output_dir, "extracted_data.xlsx")
    doc_type = _normalize_document_type(data.get("document_type", ""))
    header = data.get("header", {})
    items = data.get("items", [])

    doc_row = _build_full_doc_row(header, file_name, doc_type)
    doc_cols = get_document_columns(config)
    doc_summary = {k: doc_row.get(k, "") for k in doc_cols}

    line_items = [_normalize_item_row(it, file_name) for it in items]
    item_cols = get_item_columns(config)
    rows_items = []
    for r in line_items:
        row = {}
        if EXPORT_PIECE_COL in item_cols:
            row[EXPORT_PIECE_COL] = r.get("piece_number", "")
        if EXPORT_GREY_COL in item_cols:
            row[EXPORT_GREY_COL] = r.get("grey_mtrs", "")
        if EXPORT_MTR_COL in item_cols:
            row[EXPORT_MTR_COL] = r.get("dispatch_mtr", "")
        rows_items.append(row)
    validation_rows = _build_validation_rows(line_items, file_name)

    df_doc = pd.DataFrame([doc_summary])
    df_items = pd.DataFrame(rows_items)
    df_validation = pd.DataFrame(
        validation_rows,
        columns=[
            "file_name",
            "piece_no",
            "grey_mtrs",
            "finished_mtrs",
            "shrinkage_percent",
            "flag",
            "reason",
        ],
    )

    try:
        if not os.path.exists(output_file):
            with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
                df_doc.to_excel(writer, sheet_name="Documents", index=False)
                df_items.to_excel(writer, sheet_name="Items", index=False)
                df_validation.to_excel(writer, sheet_name="Validation_Report", index=False)
                ws_v = writer.sheets.get("Validation_Report")
                if ws_v is not None:
                    _apply_validation_row_colors(ws_v, 2, 1 + len(df_validation))
        else:
            with pd.ExcelWriter(output_file, engine="openpyxl", mode="a", if_sheet_exists="overlay") as writer:
                startrow = writer.sheets["Documents"].max_row
                df_doc.to_excel(writer, sheet_name="Documents", startrow=startrow, index=False, header=False)
                startrow = writer.sheets["Items"].max_row
                df_items.to_excel(writer, sheet_name="Items", startrow=startrow, index=False, header=False)
                if "Validation_Report" not in writer.sheets:
                    df_validation.to_excel(writer, sheet_name="Validation_Report", index=False)
                    ws_v = writer.sheets.get("Validation_Report")
                    if ws_v is not None:
                        _apply_validation_row_colors(ws_v, 2, 1 + len(df_validation))
                else:
                    startrow = writer.sheets["Validation_Report"].max_row
                    df_validation.to_excel(writer, sheet_name="Validation_Report", startrow=startrow, index=False, header=False)
                    ws_v = writer.sheets.get("Validation_Report")
                    if ws_v is not None:
                        _apply_validation_row_colors(ws_v, startrow + 1, startrow + len(df_validation))
        return True
    except Exception:
        raise


def _invoice_h(header: dict, *keys: str) -> str:
    """Get first non-empty header value from alias keys."""
    if not isinstance(header, dict):
        return ""
    for k in keys:
        v = header.get(k)
        if v is not None and str(v).strip() != "":
            return str(v).strip()
    return ""


def _normalize_invoice_item(item: dict) -> dict:
    """Normalize invoice table row to required output columns."""
    def pick(*keys):
        for k in keys:
            v = item.get(k)
            if v is not None and str(v).strip() != "":
                return str(v).strip()
        return ""
    quality = pick("quality", "item_description", "fabric_name")
    fin = pick("finished_mtrs", "fin_mtrs", "dispatch_mtr")
    rate = pick("rate", "unit_price")
    amount = pick("amount", "Amount", "line_amount", "total_value")
    model_flag = bool(item.get("flag", False))
    model_reason = str(item.get("reason", "") or "").strip()
    final_flag, reason = validate_invoice_line_row(
        quality, fin, rate, amount if amount else None, model_flag=model_flag, model_reason=model_reason
    )
    return {
        "Quality": quality,
        "Fin. Mtrs": fin,
        "Rate": rate,
        "Amount": amount,
        "flag": final_flag,
        "reason": reason,
    }


def write_invoice_to_excel(
    data: dict,
    file_name: str,
    output_file: str,
) -> bool:
    """
    Append one invoice extraction to invoice Excel file.
    Keeps invoice data separate from delivery challan output.
    """
    header = data.get("header", {}) or {}
    items = data.get("items", []) or []

    doc_row = {
        "file_name": file_name,
        "document_type": "invoice",
        "supplier_name": _invoice_h(header, "supplier_name", "company_name"),
        "supplier_gstin": _invoice_h(header, "supplier_gstin", "gstin"),
        "bill_to": _invoice_h(header, "bill_to", "buyer_name", "party_name"),
        "bill_to_gstin": _invoice_h(header, "bill_to_gstin", "buyer_gstin"),
        "invoice_number": _invoice_h(header, "invoice_number"),
        "invoice_date": _invoice_h(header, "invoice_date", "dated"),
        "challan_number": _invoice_h(header, "challan_number"),
        "ewb_no": _invoice_h(header, "ewb_no"),
        "ack_no": _invoice_h(header, "ack_no"),
        "irn": _invoice_h(header, "irn"),
        "state_code": _invoice_h(header, "state_code"),
    }
    item_rows = [_normalize_invoice_item(it) for it in items if isinstance(it, dict)]
    df_doc = pd.DataFrame([doc_row])
    df_items = pd.DataFrame(item_rows, columns=["Quality", "Fin. Mtrs", "Rate", "Amount", "flag", "reason"])

    # Validation sheet (one row per line item)
    val_rows = []
    for idx, row in enumerate(item_rows, start=1):
        fin = _inv_parse_num(row.get("Fin. Mtrs"))
        r = _inv_parse_num(row.get("Rate"))
        amt = _inv_parse_num(row.get("Amount"))
        expected = ""
        if fin is not None and r is not None:
            expected = round(fin * r, 2)
        val_rows.append(
            {
                "file_name": file_name,
                "row": idx,
                "Quality": row.get("Quality", ""),
                "Fin. Mtrs": row.get("Fin. Mtrs", ""),
                "Rate": row.get("Rate", ""),
                "Amount": row.get("Amount", ""),
                "expected_amount": expected,
                "flag": row.get("flag", False),
                "reason": row.get("reason", ""),
            }
        )
    df_val = pd.DataFrame(val_rows)

    try:
        if not os.path.exists(output_file):
            with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
                df_doc.to_excel(writer, sheet_name="Invoice_Documents", index=False)
                df_items.to_excel(writer, sheet_name="Invoice_Items", index=False)
                df_val.to_excel(writer, sheet_name="Invoice_Validation", index=False)
                ws_v = writer.sheets.get("Invoice_Validation")
                if ws_v is not None and len(df_val) > 0:
                    _apply_validation_row_colors(ws_v, 2, 1 + len(df_val))
        else:
            with pd.ExcelWriter(output_file, engine="openpyxl", mode="a", if_sheet_exists="overlay") as writer:
                if "Invoice_Documents" not in writer.sheets:
                    df_doc.to_excel(writer, sheet_name="Invoice_Documents", index=False)
                else:
                    startrow = writer.sheets["Invoice_Documents"].max_row
                    df_doc.to_excel(writer, sheet_name="Invoice_Documents", startrow=startrow, index=False, header=False)

                if "Invoice_Items" not in writer.sheets:
                    df_items.to_excel(writer, sheet_name="Invoice_Items", index=False)
                else:
                    startrow = writer.sheets["Invoice_Items"].max_row
                    df_items.to_excel(writer, sheet_name="Invoice_Items", startrow=startrow, index=False, header=False)

                if "Invoice_Validation" not in writer.sheets:
                    df_val.to_excel(writer, sheet_name="Invoice_Validation", index=False)
                    ws_v = writer.sheets.get("Invoice_Validation")
                    if ws_v is not None and len(df_val) > 0:
                        _apply_validation_row_colors(ws_v, 2, 1 + len(df_val))
                else:
                    startrow = writer.sheets["Invoice_Validation"].max_row
                    df_val.to_excel(writer, sheet_name="Invoice_Validation", startrow=startrow, index=False, header=False)
                    ws_v = writer.sheets.get("Invoice_Validation")
                    if ws_v is not None and len(df_val) > 0:
                        _apply_validation_row_colors(ws_v, startrow + 1, startrow + len(df_val))
        return True
    except Exception:
        raise
