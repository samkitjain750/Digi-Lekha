"""
Dye-sent piece master: SQLite store, Excel import, and piece verification.
Master Challan No. is the table/grey challan — never the dye header challan.
"""
from __future__ import annotations

import os
import re
import sqlite3
from datetime import datetime
from typing import Any

from . import paths as _paths

DB_NAME = "dye_piece_master.sqlite"
STATUS_OPEN = "open"
STATUS_MATCHED = "matched"

PIECE_CHECK_COLUMNS = [
    "S No.",
    "Piece No.",
    "Grey Mtr",
    "Expected Piece",
    "Status",
    "Reason",
]


def get_db_path() -> str:
    return os.path.join(_paths.get_config_dir(writable=True), DB_NAME)


def normalize_text(value: Any) -> str:
    s = str(value or "").strip().upper()
    s = re.sub(r"\s+", " ", s)
    return s


def normalize_challan_no(value: Any) -> str:
    s = str(value or "").strip()
    if not s or s.lower() in ("nan", "none"):
        return ""
    try:
        f = float(str(s).replace(",", ""))
        if f.is_integer():
            return str(int(f))
        return str(f).rstrip("0").rstrip(".")
    except (ValueError, TypeError):
        return normalize_text(s)


def normalize_grey(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return round(float(str(value).replace(",", "")), 1)
    except (ValueError, TypeError):
        return None


def _strip_tp(piece: str) -> str:
    """Remove TP markers for matching keys (not for display/export)."""
    s = str(piece or "")
    s = re.sub(r"[\(\[\{]\s*TP\s*[\)\]\}]", "", s, flags=re.IGNORECASE)
    # Common master form: 276H-TP / 4486ZS-TP
    s = re.sub(r"[-\s]*TP\b", "", s, flags=re.IGNORECASE)
    out = []
    i = 0
    while i < len(s):
        if i + 1 < len(s) and s[i].upper() == "T" and s[i + 1].upper() == "P":
            i += 2
            continue
        out.append(s[i])
        i += 1
    return "".join(out).strip().rstrip("-").strip()


def normalize_piece_key(piece: Any) -> str:
    s = _strip_tp(str(piece or "").strip())
    s = s.lstrip("-").strip()
    s = re.sub(r"-\d+$", "", s)
    s = s.rstrip("-").strip()
    return s.upper()


def piece_display(piece: Any) -> str:
    """Display/export form: keep leading '-' and TP exactly as in the master Excel."""
    return str(piece or "").strip()


_PIECE_RE = re.compile(r"^(\d+)(.*)$")


def piece_distance(a: str, b: str) -> float:
    """Lower is closer. Numeric prefix delta + suffix penalty."""
    import difflib

    ka = normalize_piece_key(a)
    kb = normalize_piece_key(b)
    ma = _PIECE_RE.match(ka)
    mb = _PIECE_RE.match(kb)
    if not ma or not mb:
        return 1000.0 * (1.0 - difflib.SequenceMatcher(None, ka, kb).ratio())
    digit_diff = abs(int(ma.group(1)) - int(mb.group(1)))
    sa = ma.group(2) or ""
    sb = mb.group(2) or ""
    suffix_pen = 0 if sa == sb else 100
    return float(digit_diff + suffix_pen)


def piece_parts(piece: Any) -> tuple[str, str]:
    """Split piece key into (digit_prefix, letter_suffix)."""
    ka = normalize_piece_key(piece)
    m = re.match(r"^(\d+)([A-Z]*)$", ka)
    if not m:
        return ka, ""
    return m.group(1), m.group(2)


def piece_one_letter_slip(a: str, b: str) -> bool:
    """Backward-compatible: true when same digit prefix and letter suffix differs lightly."""
    return piece_suffix_slip(a, b)


def piece_suffix_slip(a: str, b: str) -> bool:
    """
    True when numeric prefix matches and only the last 1–2 letters differ.
    Allows 4703T↔4703Y, 4736ZA↔4736ZB. Rejects 4703T↔1119H.
    """
    pa, sa = piece_parts(a)
    pb, sb = piece_parts(b)
    if not pa or not pb or pa != pb:
        return False
    if sa == sb:
        return True
    # Suffix lengths should be similar (0–3 letters typical).
    if abs(len(sa) - len(sb)) > 1:
        return False
    # Compare suffixes: allow up to 2 char edits, focused on the end.
    if not sa or not sb:
        return len(sa) <= 2 and len(sb) <= 2
    # Pad shorter suffix on the left so differences count at the end.
    max_len = max(len(sa), len(sb))
    sa_p = sa.rjust(max_len, " ")
    sb_p = sb.rjust(max_len, " ")
    diffs = sum(1 for x, y in zip(sa_p, sb_p) if x != y)
    return 1 <= diffs <= 2


def nearest_piece(ocr_piece: str, candidates: list[str]) -> str | None:
    """Nearest among candidates that share the same digit prefix only."""
    if not candidates:
        return None
    prefix, _ = piece_parts(ocr_piece)
    same = [c for c in candidates if piece_parts(c)[0] == prefix]
    pool = same or []
    if not pool:
        return None
    return min(pool, key=lambda c: piece_distance(ocr_piece, c))


def _connect() -> sqlite3.Connection:
    path = get_db_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dye_pieces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                process_name TEXT NOT NULL,
                quality_name TEXT NOT NULL,
                challan_no TEXT NOT NULL,
                piece_no TEXT NOT NULL,
                piece_no_display TEXT NOT NULL,
                grey_mtrs REAL NOT NULL,
                date TEXT,
                source_file TEXT,
                imported_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                matched_at TEXT,
                matched_challan_file TEXT,
                matched_s_no TEXT,
                matched_ocr_piece TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_dye_lookup
            ON dye_pieces (process_name, quality_name, challan_no, grey_mtrs, status)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_dye_dup
            ON dye_pieces (process_name, quality_name, challan_no, piece_no, grey_mtrs, status)
            """
        )
        conn.commit()


def get_master_stats() -> dict:
    init_db()
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM dye_pieces").fetchone()[0]
        last = conn.execute(
            "SELECT MAX(imported_at) FROM dye_pieces"
        ).fetchone()[0]
        src = conn.execute(
            """
            SELECT source_file FROM dye_pieces
            WHERE imported_at = (SELECT MAX(imported_at) FROM dye_pieces)
            LIMIT 1
            """
        ).fetchone()
    return {
        "total": int(total or 0),
        "last_import": last or "",
        "source_file": (src[0] if src else "") or "",
    }


def clear_all_master() -> None:
    init_db()
    with _connect() as conn:
        conn.execute("DELETE FROM dye_pieces")
        conn.commit()


def reset_matched_to_open() -> int:
    """
    Re-open all matched rows so they can match again.
    Does not delete data. Returns number of rows reset.
    """
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            """
            UPDATE dye_pieces
            SET status=?, matched_at=NULL, matched_challan_file=NULL,
                matched_s_no=NULL, matched_ocr_piece=NULL
            WHERE status=?
            """,
            (STATUS_OPEN, STATUS_MATCHED),
        )
        conn.commit()
        return int(cur.rowcount or 0)


def export_master_excel(file_path: str, *, status: str | None = None) -> dict:
    """
    Export master rows to Excel for audit.
    status is ignored (kept for compatibility); always exports all rows.
    Returns {"exported": n, "path": file_path}.
    """
    import pandas as pd

    if not file_path:
        raise ValueError("Save path is required.")
    init_db()
    sql = """
        SELECT process_name AS "Process Name",
               quality_name AS "Quality",
               challan_no AS "Challan No.",
               piece_no_display AS "Piece No.",
               grey_mtrs AS "Grey Mtrs",
               date AS "Date",
               source_file AS "Source File"
        FROM dye_pieces
        ORDER BY process_name, quality_name, challan_no, piece_no
    """
    with _connect() as conn:
        rows = conn.execute(sql).fetchall()
    data = [dict(r) for r in rows]
    df = pd.DataFrame(data)
    if df.empty:
        df = pd.DataFrame(
            columns=[
                "Process Name",
                "Quality",
                "Challan No.",
                "Piece No.",
                "Grey Mtrs",
                "Date",
                "Source File",
            ]
        )
    os.makedirs(os.path.dirname(os.path.abspath(file_path)) or ".", exist_ok=True)
    df.to_excel(file_path, index=False, engine="openpyxl")
    return {"exported": len(data), "path": file_path}


def parse_dye_master_excel(file_path: str) -> list[dict]:
    """
    Parse Process Name / Quality Name block Excel into row dicts.
    Raises ValueError on unreadable/empty files.
    """
    import pandas as pd

    if not file_path or not os.path.isfile(file_path):
        raise ValueError("File not found.")
    ext = file_path.lower().rsplit(".", 1)[-1]
    if ext not in ("xlsx", "xls"):
        raise ValueError("Please upload an Excel file (.xlsx or .xls).")

    try:
        if ext == "xls":
            raw = pd.read_excel(file_path, header=None, engine="xlrd")
        else:
            raw = pd.read_excel(file_path, header=None, engine="openpyxl")
    except Exception as e:
        raise ValueError(f"Could not read Excel file.\nDetails: {e}") from e

    if raw is None or raw.empty:
        raise ValueError("The Excel sheet is empty.")

    process = ""
    quality = ""
    rows: list[dict] = []
    for i in range(len(raw)):
        c0 = raw.iat[i, 0] if raw.shape[1] > 0 else None
        c1 = raw.iat[i, 1] if raw.shape[1] > 1 else None
        c2 = raw.iat[i, 2] if raw.shape[1] > 2 else None
        c3 = raw.iat[i, 3] if raw.shape[1] > 3 else None
        c4 = raw.iat[i, 4] if raw.shape[1] > 4 else None
        s0 = str(c0).strip() if c0 is not None and str(c0) != "nan" else ""

        if s0.lower().startswith("process name"):
            process = str(c1).strip() if c1 is not None and str(c1) != "nan" else ""
            continue
        if s0.lower().startswith("quality name"):
            quality = str(c1).strip() if c1 is not None and str(c1) != "nan" else ""
            continue
        if "quality total" in s0.lower() or "grand total" in s0.lower():
            continue
        if not process:
            continue
        try:
            float(c0)
        except (TypeError, ValueError):
            continue
        if c3 is None or str(c3).strip() in ("", "nan"):
            continue
        grey = normalize_grey(c4)
        if grey is None:
            continue
        piece_key = normalize_piece_key(c3)
        if not piece_key:
            continue
        date_s = ""
        if c1 is not None and str(c1).strip() not in ("", "nan"):
            date_s = str(c1).strip()
        rows.append(
            {
                "process_name": normalize_text(process),
                "quality_name": normalize_text(quality),
                "challan_no": normalize_challan_no(c2),
                "piece_no": piece_key,
                "piece_no_display": piece_display(c3),
                "grey_mtrs": grey,
                "date": date_s,
            }
        )

    if not rows:
        raise ValueError(
            "No dye piece rows found.\n\n"
            "Expected blocks like:\n"
            "  Process Name : MANSAROVAR INDUSTRIES\n"
            "  Quality Name : CLASS MATE\n"
            "  then rows: SNo | Date | Challan No. | Piece No. | Grey Mtrs"
        )
    return rows


def import_dye_master_excel(
    file_path: str,
    *,
    replace: bool = True,
) -> dict:
    """
    Import Master Data Excel into SQLite as a full daily replace (no append).
    `replace` is kept for API compatibility and is always treated as True.
    """
    rows = parse_dye_master_excel(file_path)
    init_db()
    clear_all_master()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    source = os.path.basename(file_path)
    inserted = 0
    with _connect() as conn:
        for r in rows:
            conn.execute(
                """
                INSERT INTO dye_pieces (
                    process_name, quality_name, challan_no, piece_no, piece_no_display,
                    grey_mtrs, date, source_file, imported_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    r["process_name"],
                    r["quality_name"],
                    r["challan_no"],
                    r["piece_no"],
                    r["piece_no_display"],
                    r["grey_mtrs"],
                    r.get("date") or "",
                    source,
                    now,
                    STATUS_OPEN,
                ),
            )
            inserted += 1
        conn.commit()

    stats = get_master_stats()
    stats["inserted"] = inserted
    stats["skipped_duplicates"] = 0
    stats["parsed"] = len(rows)
    return stats


def quality_tokens(value: Any) -> set[str]:
    """Normalize quality to comparable tokens (ANGOORA/ANGORA/DMS-Angora → overlapping)."""
    s = normalize_text(value)
    if not s:
        return set()
    # Split on spaces and common separators; keep alpha chunks length>=3
    parts = re.split(r"[^A-Z0-9]+", s)
    tokens = {p for p in parts if len(p) >= 3}
    # Alias angora spellings so OCR "DMS-ANGORA" overlaps master "ANGOORA 5002"
    if any(t in tokens for t in ("ANGORA", "ANGOORA", "ANGOOR")):
        tokens.update({"ANGORA", "ANGOORA", "ANGOOR"})
    return tokens


def qualities_similar(ocr_quality: Any, master_quality: Any) -> bool:
    a = quality_tokens(ocr_quality)
    b = quality_tokens(master_quality)
    if not a or not b:
        return False
    # Ignore ultra-generic tokens that caused FU ANY → ANY COLOUR false matches.
    weak = {"ANY", "DARK", "FU", "PU", "DMS", "CALE", "COLOUR", "COLOR", "NO"}
    a2 = a - weak
    b2 = b - weak
    if not a2 or not b2:
        return False
    return bool(a2 & b2)


def find_candidates(
    process_name: str,
    quality_name: str,
    challan_no: str,
    grey_mtrs: float | None,
    *,
    open_only: bool = False,
) -> list[dict]:
    """Lookup master rows for the confirmation key (no open/matched filter)."""
    init_db()
    proc = normalize_text(process_name)
    qual = normalize_text(quality_name)
    ch = normalize_challan_no(challan_no)
    grey = normalize_grey(grey_mtrs)
    if not proc or grey is None:
        return []

    sql = """
        SELECT id, piece_no, piece_no_display, quality_name, challan_no, grey_mtrs, status
        FROM dye_pieces
        WHERE process_name=? AND grey_mtrs=?
    """
    params: list[Any] = [proc, grey]
    if qual:
        sql += " AND quality_name=?"
        params.append(qual)
    if ch:
        sql += " AND challan_no=?"
        params.append(ch)
    sql += " ORDER BY id ASC"

    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def find_by_piece(
    process_name: str,
    ocr_piece: str,
    *,
    challan_no: str = "",
    open_only: bool = False,
) -> list[dict]:
    """Find master rows by process + piece key (optional challan)."""
    init_db()
    proc = normalize_text(process_name)
    piece = normalize_piece_key(ocr_piece)
    ch = normalize_challan_no(challan_no)
    if not proc or not piece:
        return []
    sql = """
        SELECT id, piece_no, piece_no_display, quality_name, challan_no, grey_mtrs, status
        FROM dye_pieces
        WHERE process_name=? AND piece_no=?
    """
    params: list[Any] = [proc, piece]
    if ch:
        sql += " AND challan_no=?"
        params.append(ch)
    sql += " ORDER BY id ASC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def find_by_piece_prefix(
    process_name: str,
    ocr_piece: str,
    *,
    grey_mtrs: float | None = None,
) -> list[dict]:
    """Master rows for process with the same numeric piece prefix (optional grey filter)."""
    init_db()
    proc = normalize_text(process_name)
    prefix, _ = piece_parts(ocr_piece)
    if not proc or not prefix or not prefix.isdigit():
        return []
    sql = """
        SELECT id, piece_no, piece_no_display, quality_name, challan_no, grey_mtrs, status
        FROM dye_pieces
        WHERE process_name=? AND piece_no LIKE ?
    """
    params: list[Any] = [proc, f"{prefix}%"]
    grey = normalize_grey(grey_mtrs)
    if grey is not None:
        sql += " AND grey_mtrs=?"
        params.append(grey)
    sql += " ORDER BY id ASC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    # Keep only exact same digit prefix (LIKE can over-match 470 vs 4703).
    out = []
    for r in rows:
        d = dict(r)
        if piece_parts(d.get("piece_no"))[0] == prefix:
            out.append(d)
    return out


def mark_matched(
    row_id: int,
    *,
    challan_file: str,
    s_no: Any,
    ocr_piece: str,
) -> None:
    """No-op: open/matched tracking removed; master is replaced daily."""
    return


def match_one_row(
    *,
    process_name: str,
    quality: str,
    table_challan_no: str,
    grey_mtrs: Any,
    ocr_piece: str,
    s_no: Any = "",
    has_tp: bool = False,
    challan_file: str = "",
    mark_on_ok: bool = True,
) -> dict:
    """
    Match one OCR line against dye master.
    Piece-first: never jump to a totally different piece via quality/challan.
    OCR letter fixes only allowed on the last 1–2 letters (same numeric prefix).
    """
    piece_raw = piece_display(ocr_piece)
    piece_key = normalize_piece_key(ocr_piece)
    grey = normalize_grey(grey_mtrs)
    base = {
        "S No.": s_no,
        "Quality": str(quality or "").strip(),
        "Challan No.": normalize_challan_no(table_challan_no) or str(table_challan_no or "").strip(),
        "Piece No.": piece_raw,
        "Grey Mtr": grey,
        "Expected Piece": "",
        "Status": "",
        "Reason": "",
        "Candidates": "",
    }
    if has_tp or "TP" in str(ocr_piece or "").upper():
        base["Status"] = "SKIPPED_TP"
        base["Reason"] = "Has TP — skipped"
        return base
    if not piece_key:
        base["Status"] = "NOT_FOUND"
        base["Reason"] = "Empty piece number"
        return base

    def _pick(cands: list[dict], reason: str) -> dict:
        chosen = cands[0]
        # Prefer same challan / quality / grey when multiple.
        ch = normalize_challan_no(table_challan_no)
        if ch:
            same_ch = [c for c in cands if normalize_challan_no(c.get("challan_no")) == ch]
            if same_ch:
                cands = same_ch
                chosen = cands[0]
        if grey is not None:
            same_g = [c for c in cands if normalize_grey(c.get("grey_mtrs")) == grey]
            if same_g:
                cands = same_g
                chosen = cands[0]
        qn = normalize_text(quality)
        if qn and qn not in ("FU", "PU", "ANY", "DARK"):
            same_q = [c for c in cands if qualities_similar(quality, c.get("quality_name"))]
            if same_q:
                cands = same_q
                chosen = cands[0]
        base["Candidates"] = ", ".join(c["piece_no"] for c in cands[:12]) + (
            "…" if len(cands) > 12 else ""
        )
        base["Expected Piece"] = chosen.get("piece_no_display") or chosen["piece_no"]
        base["Status"] = "OK"
        base["Reason"] = reason
        if mark_on_ok:
            mark_matched(
                chosen["id"],
                challan_file=challan_file,
                s_no=s_no,
                ocr_piece=ocr_piece,
            )
        return base

    # 1) Exact piece under process (PRIMARY — ignore quality/challan first).
    exact = find_by_piece(process_name, piece_key, challan_no="", open_only=False)
    if exact:
        return _pick(exact, "Exact piece match")

    # 2) Same numeric prefix; allow last 1–2 letter OCR slips only.
    prefix_hits = find_by_piece_prefix(process_name, piece_key, grey_mtrs=None)
    slips = [c for c in prefix_hits if piece_suffix_slip(piece_key, c["piece_no"])]
    if slips:
        # Prefer same grey when available.
        if grey is not None:
            same_g = [c for c in slips if normalize_grey(c.get("grey_mtrs")) == grey]
            if same_g:
                slips = same_g
        return _pick(
            slips,
            f"OCR letter fix: {piece_raw} → "
            f"{slips[0].get('piece_no_display') or slips[0]['piece_no']}",
        )

    # 3) No safe piece-family match.
    cand_preview = [c["piece_no"] for c in prefix_hits[:12]]
    base["Candidates"] = ", ".join(cand_preview) + ("…" if len(prefix_hits) > 12 else "")
    base["Status"] = "NOT_FOUND"
    base["Reason"] = "Not in master"
    return base



def verify_items_against_master(
    items: list[dict],
    *,
    process_name: str,
    challan_file: str = "",
    mark_on_ok: bool = True,
) -> tuple[list[dict], dict]:
    """
    Verify extracted challan items. items should include quality, table_challan_no,
    piece_number (original preferred for TP detect), grey_mtrs, s_no, and optionally
    piece_has_tp / original_piece.
    """
    results = []
    counts = {"OK": 0, "MISMATCH": 0, "NOT_FOUND": 0, "SKIPPED_TP": 0}
    for it in items or []:
        if not isinstance(it, dict):
            continue
        original = str(
            it.get("original_piece")
            or it.get("piece_number_raw")
            or it.get("piece_number")
            or it.get("piece_no")
            or ""
        )
        has_tp = bool(it.get("piece_has_tp")) or ("TP" in original.upper())
        # Also treat flag reason mentioning TP as skip
        reason = str(it.get("reason") or "")
        if "TP" in reason.upper() and "piece" in reason.lower():
            has_tp = True
        row = match_one_row(
            process_name=process_name,
            quality=it.get("quality", ""),
            table_challan_no=it.get(
                "table_challan_no",
                it.get("grey_challan_number", it.get("challan_no", "")),
            ),
            grey_mtrs=it.get("grey_mtrs"),
            ocr_piece=original,
            s_no=it.get("s_no", ""),
            has_tp=has_tp,
            challan_file=challan_file,
            mark_on_ok=mark_on_ok,
        )
        st = row["Status"]
        counts[st] = counts.get(st, 0) + 1
        results.append(row)
    return results, counts


def format_help_text() -> str:
    return (
        "Master Data — Excel format\n"
        "==========================\n\n"
        "Upload Master Data.xls (or .xlsx) in this block layout:\n\n"
        "  Process Name : MANSAROVAR INDUSTRIES\n"
        "  Quality Name : CLASS MATE (DIMOND)\n"
        "  SNo. | Date | Challan No. | Piece No. | Grey Mtrs | ...\n"
        "  ...data rows...\n"
        "  Quality Total >>  (skipped)\n"
        "  Quality Name : NEXT QUALITY\n"
        "  ...\n\n"
        "This single file is used for:\n"
        "  • Piece_Check verification (Process + Quality + Challan No. + Grey + Piece)\n"
        "  • Sheet1 '-' display — kept exactly as in Master Data\n"
        "    (with '-' if master has '-', without if it does not)\n\n"
        "Notes:\n"
        "  • Process Name = dye house / mill\n"
        "  • Challan No. = grey/table challan (NOT dye header like 1022)\n"
        "  • Update Master Data daily with a full replace (no append)\n"
        "  • Piece check uses the latest uploaded file as-is\n"
    )
