#!/usr/bin/env python3
"""规则库自检：用国家医保局公布的官方口径数字做黄金断言。

基准来源：国家医保局 2026-09-03 发布会 / 人民日报 2026-09-04 第 11 版
  - DIP 3.0 核心病种库 = 5125 个病种
  - 第一批基层病种（DIP）= 127 个
分组表「分类」列的取值域 = XQ / BX / FZ / JC，重复表头行与空行不计入。

collect_checks() 可被 export_web.py 复用，保证页面展示的断言结果来自真实运行，
而不是手写常量。

用法：
    python pipeline/validate.py --db data/build/dip_rules.db
"""
from __future__ import annotations

import argparse
import hashlib
import sqlite3
import sys
from pathlib import Path

EXPECTED_CORE_DISEASES = 5125
EXPECTED_PRIMARY_CARE = 127
EXPECTED_SHEETS = 10
CATEGORY_CODES = ("XQ", "BX", "FZ", "JC")


def collect_checks(conn: sqlite3.Connection, source_path: Path | None = None) -> dict:
    """返回结构化断言结果；不打印、不退出，供 CLI 与网页导出共用。"""
    meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())
    sheets = conn.execute(
        "SELECT table_name, sheet_name, row_count FROM sheets ORDER BY sheet_index"
    ).fetchall()

    checks: list[dict] = []

    def add(label, actual, expected, unit="", line=None):
        passed = actual == expected
        if line is None:
            line = (
                f"[{'PASS' if passed else 'FAIL'}] {label:<28} "
                f"= {actual!s:>8}  (expected {expected}{unit})"
            )
        checks.append(
            {
                "label": label,
                "actual": actual,
                "expected": expected,
                "unit": unit,
                "passed": passed,
                "line": line,
            }
        )

    add("工作表解析数", len(sheets), EXPECTED_SHEETS)

    breakdown: dict[str, int] = {}
    core_total = 0
    placeholders = ",".join("?" for _ in CATEGORY_CODES)
    for table_name, _sheet_name, _row_count in sheets:
        n = conn.execute(
            f'SELECT COUNT(*) FROM "{table_name}" '
            f'WHERE TRIM(COALESCE(c1, "")) IN ({placeholders})',
            CATEGORY_CODES,
        ).fetchone()[0]
        if n:
            for code in CATEGORY_CODES:
                c = conn.execute(
                    f'SELECT COUNT(*) FROM "{table_name}" WHERE TRIM(COALESCE(c1, "")) = ?',
                    (code,),
                ).fetchone()[0]
                if c:
                    breakdown[code] = breakdown.get(code, 0) + c
            core_total += n
    add("核心病种总数", core_total, EXPECTED_CORE_DISEASES, " 个")

    primary_tables = [t for t, name, _ in sheets if "基层病种" in name]
    primary_total = 0
    for table_name in primary_tables:
        primary_total += conn.execute(
            f'SELECT COUNT(*) FROM "{table_name}"'
        ).fetchone()[0]
    add("基层病种数", primary_total, EXPECTED_PRIMARY_CARE, " 个")

    if source_path and source_path.is_file():
        h = hashlib.sha256()
        with source_path.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        digest = h.hexdigest()
        recorded = meta.get("source_sha256", "")
        match = digest == recorded
        add(
            "源文件 SHA256 一致",
            digest,
            recorded,
            line=f"[{'PASS' if match else 'FAIL'}] 源文件 SHA256 一致           {digest[:16]}…",
        )

    return {
        "checks": checks,
        "breakdown": breakdown,
        "meta": meta,
        "sheet_count": len(sheets),
        "core_total": core_total,
        "primary_total": primary_total,
        "ok": all(c["passed"] for c in checks),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True, help="extract.py 生成的 SQLite")
    parser.add_argument("--source", type=Path, default=None,
                        help="官方 xlsx；提供时额外校验 SHA256 未被替换")
    args = parser.parse_args()

    if not args.db.is_file():
        print(f"[FAIL] 规则库不存在: {args.db}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(args.db)
    result = collect_checks(conn, args.source)
    conn.close()

    for c in result["checks"]:
        print(c["line"])

    print("\n分类分布：", "  ".join(f"{k}={v}" for k, v in sorted(result["breakdown"].items())))
    print(f"总行数：{result['meta'].get('row_total', '?')}  构建时间：{result['meta'].get('built_at', '?')}")
    print("\n结果：" + ("全部通过" if result["ok"] else "存在失败项"))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
