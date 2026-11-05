#!/usr/bin/env python3
"""规则库自检：官方口径黄金断言 + 解析口径基线断言。

断言分两类，来源不同，报告中分别标注：
  【官方】国家医保局 2026-09-03 发布会 / 人民日报 2026-09-04 第 11 版
    - DIP 3.0 核心病种库 = 5125 个病种
    - 第一批基层病种（DIP）= 127 个
  【基线】2026-11-05 首次解析成功后锁定的结构快照（非官方数字）
    - 各表行数、分类分布、编码特征、排除表、纯诊断入组条数
    - 作用：防止 AI 辅助开发或换版本时静默改变解析口径
      （例如把 `|` 多编码或 `-` 区间码当普通字符串处理，两条总数仍会绿）

collect_checks() 可被 export_web.py 复用，保证页面展示的断言结果来自真实运行，
而不是手写常量。

用法：
    python pipeline/validate.py --db data/build/dip_rules.db --source data/raw/dip-3.0-source.xlsx
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sqlite3
import sys
from pathlib import Path

# === 【官方】国家医保局公布口径 ===
EXPECTED_CORE_DISEASES = 5125
EXPECTED_PRIMARY_CARE = 127
EXPECTED_SHEETS = 10

# === 【基线】2026-11-05 实测锁定，非官方数字 ===
EXPECTED_SHEET_ROWS = {
    "t01": 20, "t02": 1725, "t03": 25, "t04": 42, "t05": 46,
    "t06": 48, "t07": 3268, "t08": 4742, "t09": 4111, "t10": 127,
}
EXPECTED_BREAKDOWN = {"XQ": 19, "BX": 1725, "FZ": 113, "JC": 3268}
EXPECTED_TOTAL_ROWS = 14154
EXPECTED_PIPE_CELLS = 1829       # 含 `|` 的编码单元格（跨全部表）
EXPECTED_RANGE_TOKENS = 54       # 形如 C00-C75 / A15-A16 的区间码 token
EXPECTED_EMPTY_OP = 1960         # t07 中手术操作编码为空（纯诊断入组）
EXPECTED_EXCLUSION_ROWS = 8853   # t08 + t09 不纳入分组表合计

CATEGORY_CODES = ("XQ", "BX", "FZ", "JC")
RANGE_TOKEN_RE = re.compile(r"^[A-Z]\d{2}-[A-Z]?\d{2}$")


def _columns(conn: sqlite3.Connection) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for table, _idx, name in conn.execute(
        "SELECT table_name, col_index, col_name FROM columns ORDER BY table_name, col_index"
    ):
        out.setdefault(table, []).append(name)
    return out


def profile_features(conn: sqlite3.Connection, sheets, colmap) -> dict:
    """从规则库实测编码特征；这是被断言的对象，不读任何常量。"""
    pipe_cells = 0
    range_tokens = 0
    empty_op = 0
    for table_name, _sheet_name, col_count, _row_count in sheets:
        names = colmap.get(table_name, [])
        code_idx = [j for j, n in enumerate(names) if "编码" in n]
        op_idx = [j for j, n in enumerate(names)
                  if ("手术操作" in n or "手术" in n) and "编码" in n]
        q = "SELECT " + ", ".join(f"c{j+1}" for j in range(col_count)) + f' FROM "{table_name}"'
        for row in conn.execute(q).fetchall():
            if table_name == "t07" and not any(str(row[j] or "").strip() for j in op_idx):
                empty_op += 1
            for j in code_idx:
                v = str(row[j] or "").strip()
                if not v:
                    continue
                if "|" in v:
                    pipe_cells += 1
                for tok in v.split("|"):
                    if RANGE_TOKEN_RE.match(tok.strip().upper()):
                        range_tokens += 1
    return {"pipe_cells": pipe_cells, "range_tokens": range_tokens, "empty_op": empty_op}


def collect_checks(conn: sqlite3.Connection, source_path: Path | None = None) -> dict:
    """返回结构化断言结果；不打印、不退出，供 CLI 与网页导出共用。"""
    meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())
    sheets = conn.execute(
        "SELECT table_name, sheet_name, col_count, row_count FROM sheets ORDER BY sheet_index"
    ).fetchall()
    colmap = _columns(conn)

    checks: list[dict] = []

    def add(label, actual, expected, unit="", origin="官方", line=None):
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
                "origin": origin,
                "passed": passed,
                "line": line,
            }
        )

    # --- 官方口径 ---
    add("工作表解析数", len(sheets), EXPECTED_SHEETS)

    breakdown: dict[str, int] = {}
    core_total = 0
    placeholders = ",".join("?" for _ in CATEGORY_CODES)
    for table_name, _sheet_name, _cc, _rc in sheets:
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

    primary_tables = [t for t, name, _cc, _rc in sheets if "基层病种" in name]
    primary_total = sum(
        conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in primary_tables
    )
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

    # --- 实测锁定基线（非官方数字） ---
    add("有效数据行总数", int(meta.get("row_total", -1)), EXPECTED_TOTAL_ROWS,
        " 行", "基线")
    for table_name, _sheet_name, _cc, _rc in sheets:
        expected = EXPECTED_SHEET_ROWS.get(table_name)
        if expected is None:
            continue
        actual = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
        add(f"表 {table_name} 行数", actual, expected, " 行", "基线")
    for code in CATEGORY_CODES:
        add(f"分类 {code} 条数", breakdown.get(code, 0), EXPECTED_BREAKDOWN[code],
            " 条", "基线")

    feat = profile_features(conn, sheets, colmap)
    add("竖线多编码单元格", feat["pipe_cells"], EXPECTED_PIPE_CELLS, " 个", "基线")
    add("区间码 token 数", feat["range_tokens"], EXPECTED_RANGE_TOKENS, " 条", "基线")
    add("t07 纯诊断入组行数", feat["empty_op"], EXPECTED_EMPTY_OP, " 行", "基线")
    exclusion = sum(
        conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        for t, name, _cc, _rc in sheets if "不纳入分组" in name
    )
    add("排除表行数合计", exclusion, EXPECTED_EXCLUSION_ROWS, " 行", "基线")

    return {
        "checks": checks,
        "breakdown": breakdown,
        "meta": meta,
        "sheet_count": len(sheets),
        "core_total": core_total,
        "primary_total": primary_total,
        "origin_note": "官方 = 国家医保局公布口径；基线 = 2026-11-05 首次解析成功后的实测快照，非官方数字",
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
    print(f"断言总数：{len(result['checks'])}（官方口径 4 条 + 解析基线 {len(result['checks'])-4} 条）")
    print("\n结果：" + ("全部通过" if result["ok"] else "存在失败项"))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
