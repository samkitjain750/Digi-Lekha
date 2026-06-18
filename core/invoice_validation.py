"""
Deterministic validation for invoice line items (used when writing Excel and in UI).
"""


def _parse_number(s):
    if s is None or (isinstance(s, float) and str(s) == "nan"):
        return None
    t = str(s).strip().replace(",", "")
    if not t:
        return None
    try:
        return float(t)
    except ValueError:
        return None


def validate_invoice_line_row(
    quality: str,
    fin_mtrs,
    rate,
    amount=None,
    *,
    model_flag: bool = False,
    model_reason: str = "",
) -> tuple[bool, str]:
    """
    Returns (final_flag, merged_reason).
    Rules:
    - Missing or non-numeric Fin. Mtrs -> flag
    - Missing or invalid rate (must parse as positive number) -> flag
    - If amount provided and fin+rate numeric: check fin*rate ~= amount (tolerance)
    """
    reasons = []
    if model_reason and str(model_reason).strip():
        reasons.append(str(model_reason).strip())

    fin = _parse_number(fin_mtrs)
    if fin is None:
        reasons.append("Fin. Mtrs missing or not numeric")

    r = _parse_number(rate)
    if r is None or r <= 0:
        reasons.append("Rate missing or invalid")

    amt = _parse_number(amount) if amount not in (None, "", "nan") else None
    if amt is not None and fin is not None and r is not None:
        expected = fin * r
        # Allow small absolute tolerance for rounding / OCR
        if abs(expected - amt) > max(1.0, abs(expected) * 0.02):
            reasons.append(f"amount mismatch: expected ~{expected:.2f}, got {amt}")

    has_structural = fin is None or r is None or r <= 0
    has_amount_mismatch = False
    if amt is not None and fin is not None and r is not None:
        expected = fin * r
        has_amount_mismatch = abs(expected - amt) > max(1.0, abs(expected) * 0.02)
    final = bool(model_flag) or has_structural or has_amount_mismatch

    reason = "; ".join(reasons) if reasons else ("model flagged" if model_flag else "")
    return final, reason
