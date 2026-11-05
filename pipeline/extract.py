#!/usr/bin/env python3
"""从国家医保局《按病种分值（DIP）付费 3.0 版分组方案》官方 xlsx 构建 SQLite 规则库。

设计原则：规则库 100% 由官方文件生成，不手写任何分组规则。
换版本只换 --source，不改代码。

用法：
    python pipeline/extract.py --source data/raw/dip-3.0-source.xlsx --out data/build/dip_rules.db
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import openpyxl

HEADER_FIRST_CELLS = {"分类", "序号", "主要诊断编码", "主要手术操作编码"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def clean(value) -> str | None:
    if value is None:
        return None
    s = str(value).replace("\n", "").replace("\r", "").strip()
    return s or None


def locate_header(rows: list[tuple]) -> int | None:
    """表头行位置在各表不固定（第 2 或第 3 行），按首列锚点定位。"""
    for i, row in enumerate(rows[:6]):
        first = clean(row[0]) if row else None
        if first in HEADER_FIRST_CELLS:
            return i
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="官方 xlsx 路径")
    parser.add_argument("--out", type=Path, required=True, help="输出 SQLite 路径")
    parser.add_argument("--dict", type=Path, default=None, help="数据字典 JSON 输出路径")
    args = parser.parse_args()

    if not args.source.is_file():
        print(f"[FAIL] 源文件不存在: {args.source}", file=sys.stderr)
        return 2

    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.out.exists():
        args.out.unlink()

    digest = sha256_file(args.source)
    wb = openpyxl.load_workbook(args.source, read_only=True, data_only=True)
    conn = sqlite3.connect(args.out)

    conn.executescript(
        """
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE sheets (
            table_name TEXT PRIMARY KEY,
            sheet_index INTEGER NOT NULL,
            sheet_name TEXT NOT NULL,
            header_row INTEGER NOT NULL,
            col_count INTEGER NOT NULL,
            row_count INTEGER NOT NULL
        );
        CREATE TABLE columns (
            table_name TEXT NOT NULL,
            col_index INTEGER NOT NULL,
            col_name TEXT NOT NULL,
            PRIMARY KEY (table_name, col_index)
        );
        """
    )

    summary = []
    skipped = []

    for idx, sheet_name in enumerate(wb.sheetnames, start=1):
        ws = wb[sheet_name]
        rows = list(ws.iter_rows(values_only=True))
        header_idx = locate_header(rows)
        if header_idx is None:
            skipped.append(sheet_name)
            continue

        header = list(rows[header_idx])
        while header and clean(header[-1]) is None:
            header.pop()
        col_names = [clean(c) or f"col_{i + 1}" for i, c in enumerate(header)]
        n_cols = len(col_names)
        if n_cols == 0:
            skipped.append(sheet_name)
            continue

        data_rows = []
        for src_row, row in enumerate(rows[header_idx + 1 :], start=header_idx + 2):
            values = [clean(row[i]) if i < len(row) else None for i in range(n_cols)]
            if not any(values):
                continue
            data_rows.append((src_row, values))

        table_name = f"t{idx:02d}"
        col_defs = ", ".join(f'"c{i + 1}" TEXT' for i in range(n_cols))
        conn.execute(
            f'CREATE TABLE "{table_name}" '
            f'(row_id INTEGER PRIMARY KEY, src_row INTEGER NOT NULL, {col_defs})'
        )
        placeholders = ", ".join("?" for _ in range(n_cols))
        conn.executemany(
            f'INSERT INTO "{table_name}" (src_row, '
            + ", ".join(f'"c{i + 1}"' for i in range(n_cols))
            + f") VALUES (?, {placeholders})",
            [(src_row, *values) for src_row, values in data_rows],
        )

        conn.execute(
            "INSERT INTO sheets VALUES (?,?,?,?,?,?)",
            (table_name, idx, sheet_name, header_idx + 1, n_cols, len(data_rows)),
        )
        conn.executemany(
            "INSERT INTO columns VALUES (?,?,?)",
            [(table_name, i + 1, name) for i, name in enumerate(col_names)],
        )
        summary.append(
            {
                "table": table_name,
                "sheet": sheet_name,
                "header_row": header_idx + 1,
                "columns": col_names,
                "rows": len(data_rows),
            }
        )

    total_rows = sum(s["rows"] for s in summary)
    meta = {
        "source_file": args.source.name,
        "source_sha256": digest,
        "source_bytes": args.source.stat().st_size,
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sheet_total": len(wb.sheetnames),
        "sheet_parsed": len(summary),
        "row_total": total_rows,
        "openpyxl_version": openpyxl.__version__,
    }
    conn.executemany("INSERT INTO meta VALUES (?,?)", meta.items())
    conn.commit()
    conn.close()
    wb.close()

    if args.dict:
        args.dict.parent.mkdir(parents=True, exist_ok=True)
        args.dict.write_text(
            json.dumps({"meta": meta, "sheets": summary, "skipped": skipped},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    for s in summary:
        print(f"  {s['table']}  {s['rows']:>5} 行  {s['sheet']}")
    if skipped:
        print(f"[WARN] 未识别表头的表: {skipped}", file=sys.stderr)
    print(f"[OK] 解析 {len(summary)}/{len(wb.sheetnames)} 表，共 {total_rows} 行")
    print(f"[OK] SHA256 = {digest}")
    print(f"[OK] 输出 = {args.out}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
