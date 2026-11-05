#!/usr/bin/env python3
"""往返一致性 / 病种库自回查覆盖率测试。

不实现入组引擎，只验证「数据层闭环」：
  A. 索引往返：每个索引分片的 ref 指回原始表时，该行确实含有所查编码。
     精确编码必须逐 token 命中；区间码必须能在该行找到对应区间 token。
  B. 病种库自回查覆盖率：5125 个核心病种的主要诊断编码，有多少能通过
     索引查回自己所在的行（同表同 row_i）。区间码 / 说明性文字不计入。
  C. 三种数据形态行数一致：SQLite / JSON 表分片 / Parquet 逐表对齐。

用法：
    python tests/verify_roundtrip.py
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

RANGE_TOKEN_RE = re.compile(r"^[A-Z]\d{2}-[A-Z]?\d{2}$")


def tokens(cell: str) -> set[str]:
    return {t.strip().upper() for t in str(cell or "").split("|") if t.strip()}


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=root / "data/build/dip_rules.db")
    ap.add_argument("--data", type=Path, default=root / "web/data")
    ap.add_argument("--parquet", type=Path, default=root / "data/parquet")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    failures = []

    def check(label, ok, detail=""):
        print(f"[{'PASS' if ok else 'FAIL'}] {label}{('  ' + detail) if detail else ''}")
        if not ok:
            failures.append(label)

    conn = sqlite3.connect(args.db)
    sheets = conn.execute(
        "SELECT table_name, sheet_name, col_count FROM sheets ORDER BY sheet_index"
    ).fetchall()
    colmap: dict[str, list[str]] = {}
    for table, _i, name in conn.execute(
        "SELECT table_name, col_index, col_name FROM columns ORDER BY table_name, col_index"
    ):
        colmap.setdefault(table, []).append(name)
    rows: dict[str, list[tuple]] = {}
    for table, _name, cc in sheets:
        select = "src_row, " + ", ".join(f'"c{i+1}"' for i in range(cc))
        rows[table] = conn.execute(f'SELECT {select} FROM "{table}" ORDER BY row_id').fetchall()
    conn.close()

    manifest = json.loads((args.data / "code_index.json").read_text(encoding="utf-8"))
    shards = {k: json.loads((args.data / "shards" / f"{k}.json").read_text(encoding="utf-8"))
              for k in manifest["shards"]}

    # A. 索引往返：ref 指向的行必须含有该编码（或其区间 token）
    total_refs = 0
    broken = 0
    for key, shard in shards.items():
        for code, refs in shard["exact"].items():
            for ref in refs:
                total_refs += 1
                table, row_i = ref[0], ref[1]
                if table not in rows or row_i >= len(rows[table]):
                    broken += 1
                    continue
                names = colmap[table]
                cells = [str(v or "") for v in rows[table][row_i][1:]]
                code_cells = [cells[j] for j, n in enumerate(names) if "编码" in n and j < len(cells)]
                if not any(code in tokens(c) for c in code_cells):
                    broken += 1
    for rg in manifest["ranges"]:
        total_refs += 1
        table, row_i = rg["ref"][0], rg["ref"][1]
        names = colmap[table]
        cells = [str(v or "") for v in rows[table][row_i][1:]]
        code_cells = [cells[j] for j, n in enumerate(names) if "编码" in n and j < len(cells)]
        if not any(rg["raw"] in tokens(c) for c in code_cells):
            broken += 1
    check("索引往返一致性", broken == 0, f"{total_refs:,} 条引用 / 失配 {broken}")

    # B. 病种库自回查覆盖率
    core = 0
    self_hit = 0
    skipped_range = 0
    skipped_text = 0
    eligible = 0
    for table, _name, _cc in sheets:
        names = colmap[table]
        cat_i = 0 if names and names[0] == "分类" else None
        if cat_i is None:
            continue
        main_dx = [j for j, n in enumerate(names) if "主要诊断编码" in n]
        if not main_dx:
            continue
        j = main_dx[0] + 1  # rows 元组第 0 位是 src_row
        for row_i, row in enumerate(rows[table]):
            if str(row[cat_i + 1] or "").strip() not in ("XQ", "BX", "FZ", "JC"):
                continue
            core += 1
            cell = str(row[j] or "").strip().upper()
            first = cell.split("|")[0].strip() if cell else ""
            # 官方表里的说明性文字（如先期分组的「所有诊断」）不是编码，索引按设计过滤
            if not cell or not re.match(r"^[A-Z0-9]", first):
                skipped_text += 1
                continue
            if RANGE_TOKEN_RE.match(first):
                skipped_range += 1
                continue
            eligible += 1
            key = first[0] if re.match(r"[A-Z0-9]", first[0]) else "_"
            refs = shards.get(key, {}).get("exact", {}).get(first, [])
            if any(r[0] == table and r[1] == row_i for r in refs):
                self_hit += 1
    rate = self_hit / eligible * 100 if eligible else 0
    overall = self_hit / core * 100 if core else 0
    check("核心病种数 = 5125", core == 5125, f"{core} 个")
    check("有效编码自回查覆盖率 = 100%", self_hit == eligible,
          f"{self_hit}/{eligible} = {rate:.2f}%")
    check("排除项口径可核对", skipped_range + skipped_text + eligible == core,
          f"区间码 {skipped_range} + 说明性文字/空值 {skipped_text} + 有效 {eligible} = {core}"
          f"；含排除项总覆盖 {overall:.2f}%")

    # C. 三种数据形态行数一致
    pm = json.loads((args.parquet / "manifest.json").read_text(encoding="utf-8"))
    parquet_rows = {t["table"]: t["rows"] for t in pm["tables"]}
    sheet_rows = {}
    for table, _name, _cc in sheets:
        s = json.loads((args.data / "sheets" / f"{table}.json").read_text(encoding="utf-8"))
        sheet_rows[table] = len(s["rows"])
    mismatch = [t for t, n in sheet_rows.items()
                if n != len(rows[t]) or parquet_rows.get(t) != n]
    check("SQLite / JSON / Parquet 逐表行数一致", not mismatch,
          f"{len(sheet_rows)} 张表" + (f"，不一致 {mismatch}" if mismatch else ""))

    # Parquet 字节可读性
    try:
        import pyarrow.parquet as pq
        bad = []
        for t in pm["tables"]:
            tbl = pq.read_table(args.parquet / t["file"])
            if tbl.num_rows != t["rows"]:
                bad.append(t["table"])
        check("Parquet 可回读且行数一致", not bad, f"{len(pm['tables'])} 个文件")
    except ImportError:
        check("Parquet 可回读且行数一致", False, "pyarrow 未安装，跳过回读")

    print()
    if failures:
        print(f"结果：{len(failures)} 项失败 —— {', '.join(failures)}")
        return 1
    print("结果：全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
