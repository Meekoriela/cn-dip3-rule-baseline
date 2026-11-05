#!/usr/bin/env python3
"""校验 web/data 静态产物：分片自包含、查询口径回归、首屏清单体积。

用法：
    python tests/verify_export.py
    python tests/verify_export.py --data web/data
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# 与 2026-11-05 首版实测一致的 6 个示例编码，用于锁定查询口径不随索引结构变化
GOLDEN = {
    "A01.0": 1,
    "A09.0": 3,
    "Z51.1": 34,
    "44.1300x001": 28,
    "C34.1": 7,
    "A15.0": 26,
}


def shard_key(code: str) -> str:
    c = code[0].upper() if code else "_"
    return c if re.fullmatch(r"[A-Z0-9]", c) else "_"


def head(code: str):
    m = re.match(r"^([A-Z])(\d{2})", code.upper())
    return (m.group(1), int(m.group(2))) if m else None


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, default=root / "web/data")
    d = ap.parse_args().data
    sys.stdout.reconfigure(encoding="utf-8")

    failures = []

    def check(label, ok, detail=""):
        print(f"[{'PASS' if ok else 'FAIL'}] {label}{('  ' + detail) if detail else ''}")
        if not ok:
            failures.append(label)

    manifest = json.loads((d / "code_index.json").read_text(encoding="utf-8"))
    check("索引模式 = sharded", manifest.get("mode") == "sharded")
    shards = manifest.get("shards", [])
    actual = sorted(p.stem for p in (d / "shards").glob("*.json"))
    check("清单分片数与实际文件一致", shards == actual, f"{len(actual)} 个")

    manifest_bytes = (d / "code_index.json").stat().st_size
    check("首屏清单 < 10 KB", manifest_bytes < 10_000, f"{manifest_bytes:,} B")

    loaded = {k: json.loads((d / "shards" / f"{k}.json").read_text(encoding="utf-8"))
              for k in actual}
    codes = 0
    missing = 0
    for key, shard in loaded.items():
        for code, refs in shard["exact"].items():
            codes += 1
            if shard_key(code) != key:
                missing += 1
            for ref in refs:
                if f"{ref[0]}:{ref[1]}" not in shard["rows"]:
                    missing += 1
    check("全部精确编码归片正确且行内容自包含", missing == 0, f"{codes} 个编码")

    range_missing = 0
    for rg in manifest.get("ranges", []):
        key = shard_key(rg["start"])
        if f"{rg['ref'][0]}:{rg['ref'][1]}" not in loaded.get(key, {}).get("rows", {}):
            range_missing += 1
    check("全部区间码命中行自包含", range_missing == 0,
          f"{len(manifest.get('ranges', []))} 条区间码")

    for code, expected in GOLDEN.items():
        q = code.upper()
        shard = loaded.get(shard_key(q), {"exact": {}, "rows": {}})
        exact = len(shard["exact"].get(q, []))
        h = head(q)
        ranges = 0
        for rg in manifest.get("ranges", []):
            s, e = head(rg["start"]), head(rg["end"])
            if h and s and e and s[0] == e[0] and h[0] == s[0] and s[1] <= h[1] <= e[1]:
                ranges += 1
        check(f"查询口径回归 {code}", exact + ranges == expected,
              f"精确 {exact} + 区间 {ranges} = {exact + ranges}（期望 {expected}）")

    print()
    if failures:
        print(f"结果：{len(failures)} 项失败 —— {', '.join(failures)}")
        return 1
    print("结果：全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
