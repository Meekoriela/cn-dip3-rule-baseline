# cn-dip3-rule-baseline

[![verify](https://github.com/Meekoriela/cn-dip3-rule-baseline/actions/workflows/verify.yml/badge.svg)](https://github.com/Meekoriela/cn-dip3-rule-baseline/actions/workflows/verify.yml)
[![License: BSD 3-Clause](https://img.shields.io/badge/license-BSD%203--Clause-blue.svg)](LICENSE)

[中文](README.md)

A **verifiable rule baseline dataset** built from the publicly released *Diagnosis-Intervention Packet (DIP) 3.0 Grouping Scheme* (按病种分值（DIP）付费 3.0 版分组方案) published by China's National Healthcare Security Administration (NHSA).

> This is an independent research implementation. It has **no affiliation with, and no certification from, the publishing authority**.
> Keywords: DIP 3.0 / CHS-DIP / diagnosis-intervention packet / medical insurance payment / rule baseline / data validation / China healthcare.

> **Scope (revised 2026-11-05 after a competitive review):** several DIP 3.0 grouping engines already exist (the OpenDRG online DIP edition, `Jensen-Yang-CN/DRG-DIP`, etc.). This project is deliberately **not another grouper**. It turns the public Excel workbook into a **citable, reproducible dataset with gold-standard assertions**, so that others writing a grouper have an independent baseline to check against.

## P0 status: 23 checks passing, re-run in CI

```
[PASS] sheets parsed             =       10  (expected 10)
[PASS] core diseases             =     5125  (expected 5125)   <- published figure
[PASS] primary-care diseases     =      127  (expected 127)    <- published figure
[PASS] source SHA256 unchanged
[PASS] total data rows           =    14154
[PASS] per-sheet row counts (10 checks)
[PASS] category XQ/BX/FZ/JC counts (4 checks)
[PASS] pipe-separated code cells =     1829
[PASS] range-code tokens         =       54
[PASS] diagnosis-only rows (t07) =     1960
[PASS] exclusion-table rows      =     8853

Category breakdown: BX=1725  FZ=113  JC=3268  XQ=19
Checks: 23 (4 published figures + 19 locked parsing-baseline checks)
```

**Two different sources, labelled separately in both the README and the demo page.** Four checks come from figures published by the NHSA. The other 19 are a structural snapshot locked after the first successful parse on 2026-11-05 — they are *not* official figures. Their purpose is to catch a silently broken parser that would still pass the two headline totals, e.g. treating `|`-separated multi-codes or `-` range codes as plain strings.

(The CLI prints Chinese labels; the numbers above are translated. Run `pipeline/validate.py` for the raw output.)

## Quick start

Requires Python 3.10+ and `openpyxl`.

```bash
pip install openpyxl pyarrow
python pipeline/extract.py \
  --source data/raw/dip-3.0-source.xlsx \
  --out data/build/dip_rules.db \
  --dict schemas/dataset.json
python pipeline/validate.py --db data/build/dip_rules.db --source data/raw/dip-3.0-source.xlsx
python pipeline/export_parquet.py
python tests/verify_roundtrip.py
```

Changing the policy version means changing only `--source`; the code stays the same. The source workbook ships with the repository, so a clone can reproduce every artifact without external files. Parquet is optional and requires `pyarrow`.

## Continuous verification (CI)

`.github/workflows/verify.yml` rebuilds the whole pipeline from the published workbook on every push and pull request:

```
extract.py -> validate.py -> export_web.py -> export_parquet.py
           -> verify_export.py -> verify_roundtrip.py -> artifact comparison
```

The last step compares every regenerated JSON / shard / Parquet manifest against the committed copy (excluding the build timestamp and cross-platform byte-size differences) and fails on any difference. Reproducibility is therefore verified by a machine on each commit, not merely claimed in the README. The badge is at the top of this file.

`verify_roundtrip.py` provides three data-layer closure metrics:

| Metric | Measured |
|---|---|
| Index round-trip | 22974 references all resolve back to their row and code; 0 mismatches |
| Self-lookup coverage of valid core-disease codes | **5084 / 5084 = 100%** |
| Excluded by definition | 26 range codes + 15 descriptive cells ("所有诊断" / all diagnoses) = 41; overall coverage including exclusions 99.20% |
| Three formats | SQLite / JSON shards / Parquet row counts match across all 10 tables |

"所有诊断" is a descriptive phrase in the official early-grouping table meaning "any diagnosis", not a code; the index filters it by design. Counting it as a miss would understate coverage, so the exclusion is reported separately. `data/parquet/` lets pandas / DuckDB read the dataset directly without running the Python pipeline.

## Data source

| Item | Value |
|---|---|
| File | DIP 3.0 grouping scheme .xlsx (attachment 2 of the 2026-09-09 NHSA announcement) |
| In-repo path | `data/raw/dip-3.0-source.xlsx` (byte-for-byte copy) |
| Announcement | https://www.nhsa.gov.cn/art/2026/9/9/art_14_22070.html |
| SHA256 | `dec2b17b8f277bec8153d8d8922380e8145ca420dc90758bcb45ad2a98a5dc7d` |
| Size | 594645 bytes |
| Worksheets | 10 |
| Data rows | 14154 |

Re-downloaded on 2026-11-05; the SHA256 matches the copy obtained on 2026-10-07.

## Where the gold-standard numbers come from

Announced at the NHSA press conference on 2026-09-03 and reported by People's Daily on 2026-09-04 (p. 11):

- DIP 3.0 core disease library = **5125** diseases (DIP 2.0 had 9520)
- First batch of primary-care diseases (DIP) = **127**

The parser counts core diseases by the value domain of the `分类` column (`XQ / BX / FZ / JC`) and primary-care diseases from the dedicated worksheet. Both match the published figures exactly — a wrong parsing rule fails the assertions immediately. These published numbers are free ground truth.

## Layout

```
data/raw/       dip-3.0-source.xlsx (verbatim source workbook)
data/build/     generated SQLite rule database
data/parquet/   10 Parquet tables (zstd), readable directly by pandas / DuckDB
pipeline/       extract.py, validate.py, export_web.py, export_parquet.py
schemas/        dataset.json data dictionary (fields, source sheets, row counts)
docs/           CODING_STANDARDS.md coding-system scope and version policy
                PAYMENT_SCOPE.md payment calculation scope and boundaries
web/            index.html rule lookup, explain.html public explainer + data/ (index shards, sheet shards, assertion results)
tests/          verify_export.py (shard self-containment + query regression)
                verify_roundtrip.py (round-trip + self-lookup + cross-format row counts)
```

## Live demo (pure static, no server required)

```bash
python pipeline/export_web.py --db data/build/dip_rules.db --source data/raw/dip-3.0-source.xlsx
python -m http.server 8000 -d web
```

Open `http://127.0.0.1:8000/`. Three panels: rule lookup (code -> disease and source row), validation results, and data dictionary.

The same site also ships a **public explainer** at `explain.html` (linked from the landing page): six counter-intuitive questions and a scroll-driven walkthrough of how a hospital stay turns into a payment. All figures are read live from `data/validation.json`; no real patient records, no payment calculation, no settlement advice.

All site data is generated by the build script; assertion results come from an actual `validate.collect_checks()` run, never from hand-written constants. The code index is **sharded by the first character of the code**: the first screen loads only a ~7 KB manifest (`code_index.json`, containing range codes, column names, sheet names and the shard list), and a query loads a single shard on demand. Each shard carries the field values of the rows it references, so a query never fetches the original worksheets. `sheets/*.json` is used only to show the first 20 rows in the data dictionary. The build handles `|`-separated multi-codes and `-` range codes; exclusion and lookup tables are tagged separately. No backend, no database, no CDN, no login — the site is hosted on GitHub Pages at https://meekoriela.github.io/cn-dip3-rule-baseline/.

Reproducible artifact check (includes query regression on six sample codes):

```bash
python tests/verify_export.py
```

## Coding-system scope

**This project deliberately does not embed or pin a complete ICD code table.** The published DIP 3.0 workbook contains only disease catalogue entries and code fragments; the full ICD-10 / ICD-9-CM-3 medical-insurance dictionaries are **continuously maintained** by the NHSA coding standards platform (`code.nhsa.gov.cn`), and `医保办函〔2025〕141号` (2025-12-31) adjusted procedure codes again. Hard-coding "edition 2.0" would produce a version number that looks authoritative but is already stale. Full evidence, query entry points and code structure: `docs/CODING_STANDARDS.md` (Chinese) and `docs/CODING_STANDARDS.en.md`.

**This project also does not offer "enter a case, get a reimbursement amount".** Inspection confirmed the official workbook has no point-value or rate columns; point values are local parameters and the monetary rate is only fixed at year-end settlement, so no real-time rate exists during the year. Full rationale, the acceptable form of a parametric estimator and five explicit boundaries: `docs/PAYMENT_SCOPE.md` (Chinese) and `docs/PAYMENT_SCOPE.en.md`.

## Roadmap

- No blocking items. Optional: version comparison between the full ICD dictionaries and the DIP catalogue (must use the currently effective version from the maintenance platform; rights remain with the publisher)
- Optional: DRG / DIP dual-scheme comparison (several implementations already exist; low resume value)

Completed: source workbook shipped for one-command rebuild; 23 assertions, shard checks and round-trip tests re-run in CI; SQLite / JSON / Parquet formats; `v0.1.0` release; live static demo at https://meekoriela.github.io/cn-dip3-rule-baseline/ .

## License and data rights

| Scope | Files | Governing document |
|---|---|---|
| Original code | `pipeline/*.py`, `web/index.html`, `web/explain.html`, README, scripts and config | `LICENSE` (BSD 3-Clause) |
| Official data and derivatives | `data/raw/`, `data/build/`, `data/parquet/`, `web/data/`, `schemas/dataset.json` | `DATA_NOTICE.md` — **not** covered by BSD-3-Clause |

Clause 3 of BSD-3-Clause prohibits using the author's or contributors' names to endorse derived products. Rights in the official data remain with the publisher; this repository claims no rights and grants no sublicense. Verify the latest official version and local implementation rules before use. See [DATA_NOTICE.en.md](DATA_NOTICE.en.md).

## Disclaimer

Only publicly released data is used; no real patient records are involved. This project is not a grouper and constitutes neither settlement nor payment advice — final determinations rest with the competent medical insurance administration. The publisher released the data and encouraged research; it has not certified this implementation.
