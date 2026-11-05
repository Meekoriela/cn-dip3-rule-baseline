#!/usr/bin/env python3
"""把 SQLite 规则库导出为 Parquet，供数据分析工具直接读取。

设计约束：
- 10 张表各导出一个 .parquet，列名使用官方表头，另加 src_row（Excel 原始行号）
- 所有值保持字符串，不做类型推断、不做编码补全，避免悄悄改变官方口径
- 排序固定（按 row_id），保证可复现
- 不覆盖 SQLite / JSON 产物，是并列的第三种数据形态

用法：
    python pipeline/export_parquet.py --db data/build/dip_rules.db
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


def main() -> int:
    here = Path(__file__).resolve().parent
    root = here.parent
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=root / "data/build/dip_rules.db")
    ap.add_argument("--out", type=Path, default=root / "data/parquet")
    args = ap.parse_args()

    if not args.db.is_file():
        print(f"[FAIL] 规则库不存在: {args.db}", file=sys.stderr)
        return 2

    args.out.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(args.db)
    sheets = conn.execute(
        "SELECT table_name, sheet_name, col_count, row_count FROM sheets ORDER BY sheet_index"
    ).fetchall()
    colmap: dict[str, list[str]] = {}
    for table, _i, name in conn.execute(
        "SELECT table_name, col_index, col_name FROM columns ORDER BY table_name, col_index"
    ):
        colmap.setdefault(table, []).append(name)

    # 不记录 pyarrow 版本：manifest 是数据契约，不应随构建环境变化
    manifest = {"format": "parquet", "compression": "zstd", "tables": []}
    total = 0
    for table, sheet_name, col_count, _row_count in sheets:
        names = colmap.get(table, [])
        fields = ["src_row"] + names
        select = "src_row, " + ", ".join(f'"c{i+1}"' for i in range(col_count))
        rows = conn.execute(f'SELECT {select} FROM "{table}" ORDER BY row_id').fetchall()
        arrays = [pa.array([("" if r[i] is None else str(r[i])) for r in rows], type=pa.string())
                  for i in range(len(fields))]
        tbl = pa.Table.from_arrays(arrays, names=fields)
        dest = args.out / f"{table}.parquet"
        pq.write_table(tbl, dest, compression="zstd")
        total += len(rows)
        manifest["tables"].append({
            "table": table,
            "sheet": sheet_name,
            "file": f"{table}.parquet",
            "rows": len(rows),
            "columns": fields,
            "bytes": dest.stat().st_size,
        })
        print(f"  {table}.parquet  {len(rows):>6,} 行  {dest.stat().st_size:>9,} B")
    conn.close()

    (args.out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"[OK] Parquet {len(sheets)} 张表 / {total} 行，pyarrow {pa.__version__}")
    print(f"[OK] 输出 = {args.out}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
