"""
Excel export: normalize extracted data, filter columns by config, append to extracted_data.xlsx.
"""
import os
import pandas as pd
from datetime import datetime


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
        "piece_number": v("piece_number"),
        "challan_mtr": v("challan_mtr"),
        "dispatch_mtr": v("dispatch_mtr"),
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


# Column order for Documents sheet: always file_name, document_type, then config-driven.
DOC_STATIC_COLS = ["file_name", "document_type"]
ITEM_STATIC_COLS = ["file_name"]


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
    """Ordered list of item columns to write (file_name + selected table fields)."""
    inv_t = config.get("invoice_table_fields") or []
    ch_t = config.get("challan_table_fields") or []
    all_item_keys = [
        "item_description", "hsn_code", "quantity", "uom", "unit_price", "discount",
        "taxable_value", "gst_rate", "tax_amount", "total_value",
        "fabric_name", "fd_number", "piece_number", "challan_mtr", "dispatch_mtr",
        "grey_received_date", "grey_challan_number", "beam",
    ]
    selected = [k for k in all_item_keys if k in inv_t or k in ch_t]
    return ITEM_STATIC_COLS + selected


def write_to_excel(
    data: dict,
    file_name: str,
    output_dir: str,
    config: dict,
) -> bool:
    """
    Append one document's extracted data to extracted_data.xlsx.
    Only columns in config are written. Creates file/sheets if missing.
    """
    output_file = os.path.join(output_dir, "extracted_data.xlsx")
    doc_type = _normalize_document_type(data.get("document_type", ""))
    header = data.get("header", {})
    items = data.get("items", [])

    doc_row = _build_full_doc_row(header, file_name, doc_type)
    doc_cols = get_document_columns(config)
    doc_summary = {k: doc_row.get(k, "") for k in doc_cols}

    line_items = [_normalize_item_row(it, file_name) for it in items]
    item_cols = get_item_columns(config)
    rows_items = [{k: r.get(k, "") for k in item_cols} for r in line_items]

    df_doc = pd.DataFrame([doc_summary])
    df_items = pd.DataFrame(rows_items)

    try:
        if not os.path.exists(output_file):
            with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
                df_doc.to_excel(writer, sheet_name="Documents", index=False)
                df_items.to_excel(writer, sheet_name="Items", index=False)
        else:
            with pd.ExcelWriter(output_file, engine="openpyxl", mode="a", if_sheet_exists="overlay") as writer:
                startrow = writer.sheets["Documents"].max_row
                df_doc.to_excel(writer, sheet_name="Documents", startrow=startrow, index=False, header=False)
                startrow = writer.sheets["Items"].max_row
                df_items.to_excel(writer, sheet_name="Items", startrow=startrow, index=False, header=False)
        return True
    except Exception:
        raise
