# cn-dip3-rule-baseline

基于国家医保局公开的《按病种分值（DIP）付费 3.0 版分组方案》构建的**可验证规则基线数据集**。

> 本项目为独立研究实现，与发布机构无隶属关系，**未获任何官方认证**。
> 可发现性关键词：DIP 3.0 / CHS-DIP / 按病种分值付费 / 病种分值 / 医保支付 / 规则基线 / 数据校验。

> **定位说明（2026-11-05 复核后收窄）**：DIP 3.0 的入组引擎已有多个实现
> （OpenDRG 官网免费版、`Jensen-Yang-CN/DRG-DIP` 等），本项目不做第 N 个分组器。
> 目标是把官方 Excel 变成**可被引用、可复跑核对、带官方数字黄金断言**的数据产物：
> 别人写分组器时，可以直接拿这里的规则库做基准。

## P0 状态：已跑通

```
[PASS] 工作表解析数      =       10  (expected 10)
[PASS] 核心病种总数      =     5125  (expected 5125 个)
[PASS] 基层病种数        =      127  (expected 127 个)
[PASS] 源文件 SHA256 一致
分类分布： BX=1725  FZ=113  JC=3268  XQ=19
总行数：14154
```

## 快速开始

需要 Python 3.10+ 与 `openpyxl`。

```bash
pip install openpyxl
python pipeline/extract.py \
  --source data/raw/dip-3.0-source.xlsx \
  --out data/build/dip_rules.db \
  --dict schemas/dataset.json
python pipeline/validate.py --db data/build/dip_rules.db --source data/raw/dip-3.0-source.xlsx
```

换版本只换 `--source`，不改代码。

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
pipeline/       extract.py（xlsx → SQLite）、validate.py（黄金断言）、export_web.py（导出静态页数据）
schemas/        dataset.json 数据字典（字段、来源工作表、行数）
web/            index.html 静态演示页 + data/（表分片、编码索引、断言结果）
tests/          待补：往返一致性、覆盖率、CI
```

## 在线演示页（纯静态，无需服务器）

```bash
python pipeline/export_web.py --db data/build/dip_rules.db --source data/raw/dip-3.0-source.xlsx
python -m http.server 8000 -d web
```

浏览器打开 `http://127.0.0.1:8000/`。三个板块：规则库查询（编码 → 病种与来源行号）、校验结果、数据字典浏览。

页面数据全部由构建脚本生成；断言结果来自 `validate.collect_checks()` 真实运行，不是手写常量。
编码索引处理了官方表的 `|` 多编码与 `-` 区间码；排除表与附表单独标注。
无后端、无数据库、无 CDN、无登录，可直接托管到 GitHub Pages / Cloudflare Pages。

## 尚未完成

- ICD-10 医保版 / ICD-9-CM-3 医保版全量编码表的来源与版本锁定（官方附件不含）
- Parquet 导出
- 往返一致性 / 病种库自回查覆盖率测试
- CI 与徽章
- 发布到 GitHub Pages（需建仓、push、开启 Pages；属对外发布动作，未执行）
- 源 xlsx 已随仓库分发，一键复现链路不依赖外部文件

## 免责声明

仅使用国家医保局公开数据，不接触任何真实病案数据。
本项目不是分组器，不构成结算或支付意见；分组结果以医保经办机构最终认定为准。
本项目未获任何官方认证，官方仅公开数据并鼓励研究。
