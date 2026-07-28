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
    "Quality",
    "Challan No.",
    "Piece No.",
    "Grey Mtr",
    "Expected Piece",
    "Status",
    "Reason",
    "Candidates",
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


def nearest_piece(ocr_piece: str, candidates: list[str]) -> str | None:
    if not candidates:
        return None
    return min(candidates, key=lambda c: piece_distance(ocr_piece, c))


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
        open_n = conn.execute(
            "SELECT COUNT(*) FROM dye_pieces WHERE status=?", (STATUS_OPEN,)
        ).fetchone()[0]
        matched_n = conn.execute(
            "SELECT COUNT(*) FROM dye_pieces WHERE status=?", (STATUS_MATCHED,)
        ).fetchone()[0]
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
        "open": int(open_n or 0),
        "matched": int(matched_n or 0),
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


def export_master_excel(file_path: str, *, status: str | None = "open") -> dict:
    """
    Export master rows to Excel for stock / audit.
    status: 'open' | 'matched' | None (all).
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
               status AS "Status",
               matched_at AS "Matched At",
               matched_challan_file AS "Matched Challan File",
               source_file AS "Source File"
        FROM dye_pieces
    """
    params: list = []
    if status in (STATUS_OPEN, STATUS_MATCHED):
        sql += " WHERE status=?"
        params.append(status)
    sql += " ORDER BY process_name, quality_name, challan_no, piece_no"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
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
                "Status",
                "Matched At",
                "Matched Challan File",
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
    replace: bool = False,
) -> dict:
    """
    Import/append dye master Excel into SQLite.
    Skips exact open duplicates of (process, quality, challan, piece, grey).
    """
    rows = parse_dye_master_excel(file_path)
    init_db()
    if replace:
        clear_all_master()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    source = os.path.basename(file_path)
    inserted = 0
    skipped = 0
    with _connect() as conn:
        for r in rows:
            exists = conn.execute(
                """
                SELECT id FROM dye_pieces
                WHERE process_name=? AND quality_name=? AND challan_no=?
                  AND piece_no=? AND grey_mtrs=? AND status=?
                LIMIT 1
                """,
                (
                    r["process_name"],
                    r["quality_name"],
                    r["challan_no"],
                    r["piece_no"],
                    r["grey_mtrs"],
                    STATUS_OPEN,
                ),
            ).fetchone()
            if exists:
                skipped += 1
                continue
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
                    r["date"],
                    source,
                    now,
                    STATUS_OPEN,
                ),
            )
            inserted += 1
        conn.commit()

    stats = get_master_stats()
    stats["inserted"] = inserted
    stats["skipped_duplicates"] = skipped
    stats["parsed"] = len(rows)
    return stats


def find_candidates(
    process_name: str,
    quality_name: str,
    challan_no: str,
    grey_mtrs: float | None,
    *,
    open_only: bool = True,
) -> list[dict]:
    """Lookup open master rows for the confirmation key."""
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
    if open_only:
        sql += " AND status=?"
        params.append(STATUS_OPEN)
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


def mark_matched(
    row_id: int,
    *,
    challan_file: str,
    s_no: Any,
    ocr_piece: str,
) -> None:
    init_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        conn.execute(
            """
            UPDATE dye_pieces
            SET status=?, matched_at=?, matched_challan_file=?, matched_s_no=?, matched_ocr_piece=?
            WHERE id=? AND status=?
            """,
            (
                STATUS_MATCHED,
                now,
                os.path.basename(challan_file or ""),
                "" if s_no is None else str(s_no),
                normalize_piece_key(ocr_piece),
                row_id,
                STATUS_OPEN,
            ),
        )
        conn.commit()


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
    Returns Piece_Check-style dict.
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
        base["Reason"] = "Piece contains TP; skipped for master check"
        return base

    cands = find_candidates(process_name, quality, table_challan_no, grey)
    cand_pieces = [c["piece_no"] for c in cands]
    base["Candidates"] = ", ".join(cand_pieces[:12]) + ("…" if len(cand_pieces) > 12 else "")

    if not cands:
        # Relax: try without quality if quality was provided but no hit
        if normalize_text(quality):
            cands = find_candidates(process_name, "", table_challan_no, grey)
            cand_pieces = [c["piece_no"] for c in cands]
            if cands:
                base["Candidates"] = ", ".join(cand_pieces[:12])
                base["Reason"] = "No quality match; fell back to process+challan+grey"
            else:
                base["Status"] = "NOT_FOUND"
                base["Reason"] = "No open master row for process + quality + challan + grey"
                return base
        else:
            base["Status"] = "NOT_FOUND"
            base["Reason"] = "No open master row for process + challan + grey"
            return base

    if len(cands) == 1:
        expected = cands[0]["piece_no"]
        base["Expected Piece"] = cands[0].get("piece_no_display") or expected
        if expected == piece_key:
            base["Status"] = "OK"
            base["Reason"] = "Exact match"
            if mark_on_ok:
                mark_matched(
                    cands[0]["id"],
                    challan_file=challan_file,
                    s_no=s_no,
                    ocr_piece=ocr_piece,
                )
        else:
            base["Status"] = "MISMATCH"
            base["Reason"] = f"Expected {base['Expected Piece']}, got {piece_raw}"
        return base

    # Multiple candidates: nearest piece, then exact compare
    expected = nearest_piece(piece_key, cand_pieces)
    chosen = next((c for c in cands if c["piece_no"] == expected), cands[0])
    base["Expected Piece"] = chosen.get("piece_no_display") or expected
    base["Candidates"] = ", ".join(cand_pieces[:12]) + ("…" if len(cand_pieces) > 12 else "")
    if expected == piece_key:
        base["Status"] = "OK"
        base["Reason"] = f"Matched nearest of {len(cands)} candidates"
        if mark_on_ok:
            mark_matched(
                chosen["id"],
                challan_file=challan_file,
                s_no=s_no,
                ocr_piece=ocr_piece,
            )
    else:
        base["Status"] = "MISMATCH"
        base["Reason"] = (
            f"Nearest of {len(cands)} candidates is {base['Expected Piece']}, "
            f"got {piece_raw}"
        )
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
        "  • Upload / Append for daily new rows; Replace all only for a full reset\n"
        "  • Matched pieces are soft-marked (not deleted)\n"
        "  • Export Open = pieces still outstanding at dye\n"
        "  • Reset matched = mark all matched rows open again (no delete)\n"
    )
