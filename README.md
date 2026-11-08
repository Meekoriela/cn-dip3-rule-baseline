# cn-dip3-rule-baseline

[![verify](https://github.com/Meekoriela/cn-dip3-rule-baseline/actions/workflows/verify.yml/badge.svg)](https://github.com/Meekoriela/cn-dip3-rule-baseline/actions/workflows/verify.yml)
[![License: BSD 3-Clause](https://img.shields.io/badge/license-BSD%203--Clause-blue.svg)](LICENSE)

[English](README.en.md)

基于国家医保局公开的《按病种分值（DIP）付费 3.0 版分组方案》构建的**可验证规则基线数据集**。

> 本项目为独立研究实现，与发布机构无隶属关系，**未获任何官方认证**。
> 可发现性关键词：DIP 3.0 / CHS-DIP / 按病种分值付费 / 病种分值 / 医保支付 / 规则基线 / 数据校验。

> **定位说明（2026-11-05 复核后收窄）**：DIP 3.0 的入组引擎已有多个实现
> （OpenDRG 官网免费版、`Jensen-Yang-CN/DRG-DIP` 等），本项目不做第 N 个分组器。
> 目标是把官方 Excel 变成**可被引用、可复跑核对、带官方数字黄金断言**的数据产物：
> 别人写分组器时，可以直接拿这里的规则库做基准。

## P0 状态：23 条断言全绿（CI 自动复跑）

```
[PASS] 工作表解析数      =       10  (expected 10)
[PASS] 核心病种总数      =     5125  (expected 5125 个)   ← 官方公布口径
[PASS] 基层病种数        =      127  (expected 127 个)   ← 官方公布口径
[PASS] 源文件 SHA256 一致
[PASS] 有效数据行总数    =    14154
[PASS] 表 t01..t10 行数（10 条）
[PASS] 分类 XQ/BX/FZ/JC 条数（4 条）
[PASS] 竖线多编码单元格  =     1829
[PASS] 区间码 token 数   =       54
[PASS] t07 纯诊断入组    =     1960
[PASS] 排除表行数合计    =     8853

分类分布： BX=1725  FZ=113  JC=3268  XQ=19
断言总数：23（官方口径 4 条 + 解析基线 19 条）
```

**两类断言来源不同，README 与页面均单独标注**：4 条来自国家医保局公布口径；19 条是 2026-11-05 首次解析成功后锁定的结构快照，不是官方数字。后者的作用是防止「两条总数仍然绿、但解析口径已被改坏」——例如把 `|` 多编码或 `-` 区间码当普通字符串处理。

## 快速开始

需要 Python 3.10+ 与 `openpyxl`。

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

换版本只换 `--source`，不改代码。Parquet 为可选依赖，只要 `pyarrow`。

## 持续验证（CI）

`.github/workflows/verify.yml` 在每次 push / PR 时从**官方 xlsx 重新构建整条链路**：

```
extract.py → validate.py → export_web.py → export_parquet.py
           → verify_export.py → verify_roundtrip.py → 产物一致性比对
```

最后一步把重建产物与仓库内已提交的 JSON / 分片 / Parquet manifest 逐一比对（排除构建时间戳与跨平台字节差异），任一不同即失败。因此「可复现」不是 README 上的说法，而是每次提交都被机器核对的事实。徽章在 README 顶部。

`verify_roundtrip.py` 提供三个数据层闭环指标：

| 指标 | 实测 |
|---|---|
| 索引往返一致性 | 22974 条引用全部能指回原行并命中该编码，失配 0 |
| 核心病种有效编码自回查覆盖率 | **5084 / 5084 = 100%** |
| 排除项口径 | 区间码 26 条 + 说明性文字「所有诊断」15 条 = 41 条，不计入分母；含排除项总覆盖 99.20% |
| 三种形态行数 | SQLite / JSON 分片 / Parquet 逐表对齐，10 张表全一致 |

「所有诊断」是官方先期分组表里表示「不限诊断」的说明性文字，不是编码，索引按设计过滤；把它算成未命中会低估覆盖率，所以口径单独列出。`data/parquet/` 让数据集可直接被 pandas / DuckDB 读取，不必先跑 Python 管线。

## 数据源

| 项 | 值 |
|---|---|
| 文件 | 按病种分值（DIP）付费 3.0 版分组方案 .xlsx（2026-09-09 公告附件 2） |
| 仓库内路径 | `data/raw/dip-3.0-source.xlsx`（原样留存，clone 后无需另找文件） |
| 公告 | https://www.nhsa.gov.cn/art/2026/9/9/art_14_22070.html |
| SHA256 | `dec2b17b8f277bec8153d8d8922380e8145ca420dc90758bcb45ad2a98a5dc7d` |
| 字节 | 594645 |
| 工作表数 | 10 |
| 有效数据行 | 14154 |

2026-11-05 重新下载比对，与 2026-10-07 的副本 SHA256 完全一致。

## 黄金断言从哪来

国家医保局 2026-09-03 发布会 / 人民日报 2026-09-04 第 11 版公布：

- DIP 3.0 核心病种库 = **5125** 个病种（2.0 版为 9520）
- 第一批基层病种（DIP）= **127** 个

本地解析按「分类」列取值域 `XQ / BX / FZ / JC` 统计核心病种，
按「六、基层病种」表统计基层病种；两个数字与官方公布完全吻合。
解析口径一旦出错，断言立刻失败——这是官方免费提供的 ground truth。

## 目录

```
data/raw/       dip-3.0-source.xlsx（官方 xlsx 原样留存，供一键复现）
data/build/     生成的 SQLite 规则库
data/parquet/   10 张表的 Parquet（zstd），供 pandas / DuckDB 直接读取
pipeline/       extract.py、validate.py、export_web.py、export_parquet.py
schemas/        dataset.json 数据字典（字段、来源工作表、行数）
docs/           CODING_STANDARDS.md 编码体系与版本口径（中英）
                PAYMENT_SCOPE.md 支付测算口径与业务边界（中英）
web/            index.html 规则库查询页、explain.html 面向公众的解读页 + data/（索引分片、表分片、断言结果）
tests/          verify_export.py（分片自包含 + 查询口径回归）
                verify_roundtrip.py（往返一致性 + 自回查覆盖率 + 三形态行数对齐）
```

## 在线演示页（纯静态，无需服务器）

```bash
python pipeline/export_web.py --db data/build/dip_rules.db --source data/raw/dip-3.0-source.xlsx
python -m http.server 8000 -d web
```

浏览器打开 `http://127.0.0.1:8000/`。三个板块：规则库查询（编码 → 病种与来源行号）、校验结果、数据字典浏览。

同一站点另有**面向公众的解读页** `explain.html`（首页有入口）：用六个反直觉问题和一条滚动流程讲清「一次住院，医保的钱是怎么定下来的」。数字现场取自 `data/validation.json`，不含真实病案，不做支付测算，不构成结算或支付意见。

页面数据全部由构建脚本生成；断言结果来自 `validate.collect_checks()` 真实运行，不是手写常量。
编码索引按**编码首字符分片**：首屏只加载约 7 KB 的清单（`code_index.json`，含区间码、列名、表名、分片清单），查询时按需加载单个分片；每个分片自带命中行的字段内容，因此查询不再请求原始表。`sheets/*.json` 仅用于「数据字典」展开前 20 行。
索引构建时处理官方表的 `|` 多编码与 `-` 区间码；排除表与附表单独标注。
无后端、无数据库、无 CDN、无登录，可直接托管到 GitHub Pages / Cloudflare Pages。

产物校验（可复跑，含 6 个示例编码的查询口径回归）：

```bash
python tests/verify_export.py
```

## 编码体系说明

**本项目不内嵌、也不锁定某一版 ICD 全量编码表**——这是核查后的结论，不是遗漏。官方 DIP 3.0 附件只含病种目录与编码片段；全量 ICD-10 医保版 / ICD-9-CM-3 医保版由国家医保信息业务编码标准数据库**动态维护**（`code.nhsa.gov.cn`），且 `医保办函〔2025〕141号` 在 2025-12-31 又调整了手术操作代码，因此写死「2.0 版」会给出一个看似确定、实际过期的版本号。完整依据、查询入口与编码结构见 `docs/CODING_STANDARDS.md`。

**本项目也不提供「输入病案 → 输出报销金额」**：官方附件经实测全表无分值 / 点数列，分值属地方参数，点值须年终清算才确定，年内不存在实时点值。完整业务依据、参数化测算的允许形态与五条红线见 `docs/PAYMENT_SCOPE.md`。

## 尚未完成

- 无阻塞项。后续可选：ICD 全量编码表与 DIP 目录的版本对照（需以动态维护平台当期版本为准，且权利归发布方）
- 可选：DRG / DIP 双口径对照（已有多个现成实现，简历收益低）

已完成：源 xlsx 随仓库分发，一键复现不依赖外部文件；23 条断言、分片校验、往返一致性由 CI 每次自动复跑；SQLite / JSON / Parquet 三种数据形态；`v0.1.0` release 可引用；静态演示页已上线 https://meekoriela.github.io/cn-dip3-rule-baseline/ 。

## 许可证与数据权利

| 范围 | 适用文件 | 依据 |
|---|---|---|
| 原创代码 | `pipeline/*.py`、`tests/*.py`、`docs/*.md`、`web/index.html`、`web/explain.html`、README、脚本与配置 | `LICENSE`（BSD 3-Clause） |
| 官方数据及其派生 | `data/raw/`、`data/build/`、`data/parquet/`、`web/data/`、`schemas/dataset.json` | `DATA_NOTICE.md`，**不适用** BSD-3-Clause |

BSD-3-Clause 第 3 条禁止以作者或贡献者名义为衍生产品背书。官方数据的权利归发布方，本仓库不主张权利、不提供再授权；使用前请自行核对官方最新版本与地方实施细则。

## 免责声明

仅使用国家医保局公开数据，不接触任何真实病案数据。
本项目不是分组器，不构成结算或支付意见；分组结果以医保经办机构最终认定为准。
本项目未获任何官方认证，官方仅公开数据并鼓励研究。
