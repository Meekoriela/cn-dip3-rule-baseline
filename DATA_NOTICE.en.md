# Data Provenance and Rights Notice

[中文](DATA_NOTICE.md)

## Source

| Item | Value |
|---|---|
| In-repo file | `data/raw/dip-3.0-source.xlsx` |
| Original file | 《按病种分值（DIP）付费 3.0 版分组方案》.xlsx (DIP 3.0 Grouping Scheme) |
| Published as | Attachment 2 of the 2026-09-09 NHSA announcement "3.0 grouping scheme configuration information is now open" |
| Announcement | https://www.nhsa.gov.cn/art/2026/9/9/art_14_22070.html |
| Size | 594645 bytes |
| SHA256 | `dec2b17b8f277bec8153d8d8922380e8145ca420dc90758bcb45ad2a98a5dc7d` |

The file in this repository is a byte-for-byte copy of the published attachment; its contents have not been altered.

## Rights

- Copyright and all other rights in the original data, the grouping rules, disease catalogue and coding system remain with the publisher.
- This repository performs **format conversion only** (xlsx -> SQLite / JSON), field indexing, code tokenisation and consistency checks. It does not rewrite or create derivative authorship over the source content.
- This repository **claims no rights** over the original data and **grants no sublicense** for it.
- The following derived artifacts are likewise **outside the scope** of the repository's BSD-3-Clause code license: `data/build/dip_rules.db`, `web/data/*.json`, `schemas/dataset.json`.

## Conditions of use

1. Verify the latest official version, its effective scope and local implementation rules before using or citing the data. Grouping schemes are revised periodically.
2. Do not describe this repository or its outputs as officially published, officially certified, or as having any affiliation, authorisation or partnership with the publisher.
3. When citing, attribute the data source and link the official announcement, and state that this repository provides only structural conversion and validation.
4. No real patient records are included and no patient privacy is involved. Results constitute neither settlement nor payment advice; final determinations rest with the competent medical insurance administration.
5. Users are responsible for determining whether their use case complies with applicable data regulations and medical insurance policy.

## Relationship to the code license

This repository uses a **code / data split**:

- **Original code**: `LICENSE` (BSD 3-Clause), with an explicit copyright notice and a non-endorsement clause.
- **Official data and derivatives**: governed by this notice, not by any open-source license.

The two must not be conflated. Treating the entire repository as BSD-3-Clause-licensed content is a misreading.
