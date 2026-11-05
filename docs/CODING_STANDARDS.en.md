# Coding standards and version scope

[中文](CODING_STANDARDS.md)

## Conclusion

**This project does not embed or pin a complete ICD code table.** That is a deliberate finding, not an omission.

The *DIP 3.0 Grouping Scheme* workbook published by China's National Healthcare Security Administration (NHSA) contains only disease catalogue entries and code fragments (main diagnosis code, procedure code, other diagnosis code, etc.). It does not contain the full ICD-10 / ICD-9-CM-3 medical-insurance dictionaries. Those are maintained through a separate mechanism:

| Item | Value |
|---|---|
| Official source | NHSA dynamic maintenance platform for medical insurance coding standards: `https://code.nhsa.gov.cn/` |
| Diagnosis codes | `https://code.nhsa.gov.cn/jbzd/public/dataWesterSearch.html` (ICD-10, medical insurance edition) |
| Procedure codes | `https://code.nhsa.gov.cn/jbzd/public/dataOperationSearch.html` (ICD-9-CM-3, medical insurance edition) |
| Coding rules | *Rules and methods for the four medical insurance information business coding standards*, `https://code.nhsa.gov.cn:8000/lib/img/file1/attachment.pdf` |
| Full datasets | "Data download" section of the diagnosis/procedure code database on the platform; new versions are also pushed to local agencies through the national medical insurance information platform |
| Maintenance model | **Continuously maintained** — there is no single frozen version number |

## Version scope (verified 2026-11-06)

1. **Medical insurance edition 2.0 is a historical baseline.** Local agencies began adopting ICD-10 (2.0) and ICD-9-CM-3 (2.0) medical insurance code sets from 2021-10-01. This is the static version number visible in public documents.
2. **Formal changes have been issued after 2.0.** `医保办函〔2025〕141号` (Notice on further application of medical insurance diagnosis and procedure codes; issued 2025-12-31, published 2026-01-19) adjusted the procedure code set, adding 7 and revising 4 focused-ultrasound codes. The updated database was pushed to local agencies and can be downloaded from the dynamic maintenance platform.
3. Consequently, **"ICD medical insurance edition 2.0" cannot represent the code set actually in force when DIP 3.0 is implemented**. Hard-coding it would produce a version number that looks authoritative but is already stale.

## How this project handles it

- The reproducibility anchor is **the published DIP 3.0 workbook itself**: SHA256 `dec2b17b8f277bec8153d8d8922380e8145ca420dc90758bcb45ad2a98a5dc7d`, 594645 bytes, shipped with the repository.
- Code columns are structured verbatim: no completion, no mapping, no inferred code names. `|`-separated multi-codes are split and `-` range codes are indexed separately, but the original notation is preserved.
- The coding system is declared explicitly as an **external, dynamically maintained standard**, with source and verification entry points. No claim is made of strict conformance to any frozen version.
- Anyone building real case grouping or ICD mapping must obtain the currently effective version from the maintenance platform and check local implementation rules. This repository provides neither that capability nor a sublicense (see `DATA_NOTICE.md`).

## Code structure (from the official coding rules)

- **ICD-10, medical insurance edition**: first 3 characters are the category (one uppercase letter + two digits), the 4th is the subcategory, and the 5th/6th are extension identifiers.
- **ICD-9-CM-3, medical insurance edition**: all digits; first 2 are the category (procedure chapter), 3rd subcategory, 4th detail, 5th/6th extension identifiers.
- This matches forms seen in the workbook such as `A01.0`, `C00-C75`, `44.1300x001`. The `x` suffix reflects local / clinical extensions and is preserved verbatim, with no normalisation.

## Sources checked

- `医保发〔2026〕22号` (Notice on issuing the DRG/DIP 3.0 grouping schemes and implementation, 2026-09-02, nhsa.gov.cn): neither the text nor the attachments include a full ICD code table or specify a code-set version.
- `医保办函〔2025〕141号` (2025-12-31): procedure code adjustments, distribution and download of the updated database.
- NHSA dynamic maintenance platform: query pages and the coding rules PDF (links above).
- Local public notices from 2021 adopting edition 2.0: used only to establish the historical starting point, not as the current version.
