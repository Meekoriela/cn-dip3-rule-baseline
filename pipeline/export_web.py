#!/usr/bin/env python3
"""把 SQLite 规则库导出为纯静态网页所需的 JSON。

设计约束：
- 页面不依赖任何后端，所有计算在构建时完成
- 断言结果由 validate.collect_checks() 真实运行生成，不手写常量
- 处理官方表的两个编码难点：`|` 多编码拆开、`-` 区间码单独建索引
- 编码索引只存 [表, 行下标, 字段类型]，前端按需加载对应表分片

用法：
    python pipeline/export_web.py \
      --db data/build/dip_rules.db --source data/raw/dip-3.0-source.xlsx
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import collect_checks  # noqa: E402

RANGE_RE = re.compile(r"^([A-Z])(\d{2})-([A-Z]?)(\d{2})$")
CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-]*$")


def is_code(token: str) -> bool:
    """过滤表里的说明性文字（如「所有诊断」），只索引真正的 ICD 样式编码。"""
    return bool(CODE_RE.match(token)) and any(ch.isdigit() for ch in token)


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                    encoding="utf-8")


def field_kind(column_name: str, sheet_name: str) -> str:
    if "不纳入分组" in sheet_name:
        return "excl"
    if "附表" in sheet_name:
        return "lookup"
    if "其他诊断" in column_name:
        return "other_dx"
    if "相关手术" in column_name and "主要手术" in column_name:
        return "mixed_op"
    if "相关手术" in column_name:
        return "related_op"
    if "主要手术" in column_name:
        return "main_op"
    return "main_dx"


def main() -> int:
    here = Path(__file__).resolve().parent
    root = here.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=root / "data/build/dip_rules.db")
    parser.add_argument("--source", type=Path,
                        default=root / "data/raw/dip-3.0-source.xlsx")
    parser.add_argument("--out", type=Path, default=root / "web/data")
    args = parser.parse_args()

    if not args.db.is_file():
        print(f"[FAIL] 规则库不存在: {args.db}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(args.db)
    sheets = conn.execute(
        "SELECT table_name, sheet_index, sheet_name, header_row, col_count, row_count "
        "FROM sheets ORDER BY sheet_index"
    ).fetchall()
    columns = {}
    for table, idx, name in conn.execute(
        "SELECT table_name, col_index, col_name FROM columns ORDER BY table_name, col_index"
    ):
        columns.setdefault(table, []).append({"index": idx, "name": name})

    # 1) 真实断言结果
    validation = collect_checks(conn, args.source if args.source.is_file() else None)
    validation["category_labels"] = {
        "XQ": "先期分组", "FZ": "诊断辅助细分", "BX": "并项规则", "JC": "基础规则"
    }
    write_json(args.out / "validation.json", validation)

    # 2) 数据字典
    dictionary = {"sheets": []}
    for table, idx, sheet_name, header_row, col_count, row_count in sheets:
        dictionary["sheets"].append({
            "table": table,
            "index": idx,
            "sheet": sheet_name,
            "header_row": header_row,
            "col_count": col_count,
            "row_count": row_count,
            "columns": columns.get(table, []),
        })
    write_json(args.out / "dictionary.json", dictionary)

    # 3) 表分片 + 编码索引
    exact: dict[str, list] = {}
    ranges: list[dict] = []
    sheet_dir = args.out / "sheets"
    total_rows = 0

    for table, _idx, sheet_name, _header_row, col_count, _row_count in sheets:
        col_names = [c["name"] for c in columns.get(table, [])]
        code_cols = [(i, n) for i, n in enumerate(col_names) if "编码" in n]
        select_cols = ", ".join(f'"c{i + 1}"' for i in range(col_count))
        raw = conn.execute(
            f'SELECT src_row, {select_cols} FROM "{table}" ORDER BY row_id'
        ).fetchall()

        rows = []
        for row_i, row in enumerate(raw):
            src_row = row[0]
            values = ["" if v is None else str(v) for v in row[1:]]
            rows.append({"src": src_row, "v": values})
            for col_i, col_name in code_cols:
                if col_i >= len(values):
                    continue
                cell = values[col_i].strip()
                if not cell:
                    continue
                kind = field_kind(col_name, sheet_name)
                for token in cell.split("|"):
                    token = token.strip().upper()
                    if not token:
                        continue
                    m = RANGE_RE.match(token)
                    if not m and not is_code(token):
                        continue
                    ref = [table, row_i, kind]
                    if m:
                        start_l, start_n, end_l, end_n = m.groups()
                        ranges.append({
                            "start": f"{start_l}{start_n}",
                            "end": f"{(end_l or start_l)}{end_n}",
                            "raw": token,
                            "ref": ref,
                        })
                    else:
                        exact.setdefault(token, []).append(ref)

        write_json(sheet_dir / f"{table}.json", {
            "table": table,
            "sheet": sheet_name,
            "columns": col_names,
            "rows": rows,
        })
        total_rows += len(rows)

    write_json(args.out / "code_index.json", {
        "exact": exact,
        "ranges": ranges,
        "stats": {
            "exact_keys": len(exact),
            "exact_refs": sum(len(v) for v in exact.values()),
            "ranges": len(ranges),
            "rows_indexed": total_rows,
        },
    })
    conn.close()

    for p in sorted(args.out.rglob("*.json")):
        print(f"  {p.relative_to(args.out)}  {p.stat().st_size:>9,} B")
    print(f"[OK] 表分片 {len(sheets)} 个，行 {total_rows} 条")
    print(f"[OK] 精确编码 {len(exact)} 个 / 引用 {sum(len(v) for v in exact.values())} 条 / 区间码 {len(ranges)} 条")
    print(f"[OK] 断言 {'全部通过' if validation['ok'] else '存在失败项'}")
    print(f"[OK] 输出 = {args.out}")
    return 0 if validation["ok"] else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
