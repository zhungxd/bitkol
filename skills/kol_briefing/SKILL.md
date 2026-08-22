# KOL 简报 Skill

> 用途：周期性收集 KOL 推文 → 聚合权重 → Agent 直接读取并生成中文简报（加密 / 美股分区）。
> 脚本只做数据搬运与权重计算，**不调用任何 LLM API**；分析由 Agent 自身 LLM 能力完成。

## 目录结构

```
bitkol/
├─ data/
│  ├─ x_kol_list.jsonl              # KOL 名单（字段: handle/name/followers/category/type/track/source/...）
│  ├─ views/<handle>.jsonl          # 采集结果，按 handle 落盘，追加去重
│  └─ briefings/
│     ├─ _input/<date>_<partition>.json   # prep_briefing_input.py 输出，Agent 消费
│     └─ <date>_<partition>.md            # Agent 生成的最终简报
├─ scripts/
│  ├─ collect_tweets.py             # 采集编排器（薄层，委托 sources 包）
│  └─ prep_briefing_input.py        # 聚合 + 权重 + 分区 → _input JSON
└─ skills/kol_briefing/
   ├─ SKILL.md                      # 本文件
   ├─ config.toml                   # 所有可调参数（数据源/采集/权重/分区）
   ├─ config_loader.py              # TOML 加载（3.11+ tomllib + fallback）
   ├─ weights.py                    # 权重公式 + 分区筛选
   ├─ sources/
   │  ├─ __init__.py                # TweetSource 抽象基类 + 工厂
   │  ├─ nitter_html.py             # 默认源：Nitter HTML 抓取（多镜像 failover）
   │  └─ nitter_rss.py              # 备选源：Nitter RSS（多数镜像已禁用，保留兼容）
   └─ prompts/
      ├─ briefing_system.md         # Agent system prompt
      └─ briefing_template.md       # 简报输出模板
```

## 数据流（4 步）

```
[1] KOL 名单              [2] 推文                 [3] 聚合权重                [4] 简报
data/x_kol_list.jsonl  →  data/views/*.jsonl  →  data/briefings/_input/*.json  →  data/briefings/*.md
        │                      ↑                          ↑                            ↑
        └──────────────────────┴──────────────────────────┴────────────────────────┘
                          collect_tweets.py          prep_briefing_input.py        Agent (本 Skill)
```

## Agent 执行流程

收到「生成 KOL 简报」类请求时，按下列顺序执行。**不要跳步**。

### Step 1：采集推文（可选，若 _input 已是最新可跳过）

```bash
# 默认全量采集（按 config.toml 的 max_per_kol=20、days_window=7）
python3 scripts/collect_tweets.py

# 或仅采集某分区
python3 scripts/collect_tweets.py --partition crypto

# 或单 handle 调试
python3 scripts/collect_tweets.py --handle cz_binance
```

- 采集源由 `config.toml` 的 `[source].active_source` 决定，默认 `nitter_html`。
- 失败的 handle 会在终端打印 `FAIL (...)`，不影响其他 KOL。镜像全挂时换 `active_source` 或加镜像。
- 输出落盘到 `data/views/<handle>.jsonl`，按 tweet id 去重追加。

### Step 2：聚合 → _input JSON

```bash
python3 scripts/prep_briefing_input.py           # 默认窗口
python3 scripts/prep_briefing_input.py --days 3  # 覆盖窗口
```

- 按 `category` 字段分 crypto / us_stock 两区，`both` 类账号同时进两份。
- 每区按 `weights.py` 计算归一化权重（和 = 1.0），附 `weight_breakdown` 供审计。
- 输出：`data/briefings/_input/<date>_<partition>.json`，每区一份。
- 终端会打印 top 5 权重 KOL，用于人工 sanity check。

### Step 3：读取 _input JSON 并分析

**不要用 RunCommand 调用任何 LLM API**。Agent 自身就是 LLM，直接读 JSON 分析。

对每个分区文件 `data/briefings/_input/<date>_<partition>.json`：

1. 用 `Read` 工具打开 JSON。
2. 关注顶层字段：
   - `partition` / `partition_label`：分区标识
   - `window.days` / `window.max_per_kol`：本次采集口径
   - `stats`：KOL 数、推文总数、空推文 KOL 列表
   - `kols[]`：按 `weight` 降序，每个 KOL 含 `weight` / `weight_breakdown` / `tweets[]`
3. 分析维度见 `prompts/briefing_system.md`：
   - 市场情绪（加权看多/看空/中性）
   - 热点赛道/标的
   - 高权重 KOL 个别观点
   - 分歧与共识
   - 风险信号

### Step 4：按模板输出简报

- 模板：`skills/kol_briefing/prompts/briefing_template.md`
- 输出文件：`data/briefings/<date>_<partition>.md`（注意：不带 `_input/` 前缀）
- 文件名与 _input JSON 同名同日期，仅扩展名不同，便于追溯。
- 用 `Write` 工具落盘，不要直接 echo 到 stdout。

## 换数据源（后期维护）

1. 在 `sources/` 新增一个继承 `TweetSource` 的模块，实现 `fetch_recent(handle, max_results, days_window)`。
2. 在 `sources/__init__.py` 的 `get_source()` 加一个分支。
3. 改 `config.toml` 的 `[source].active_source` 指向新源。

`collect_tweets.py` / `prep_briefing_input.py` 无需改动。

## 调参

- `config.toml` 的 `[collect]` 调采集口径（条数/窗口/限速）。
- `[weights]` 调权重公式各系数。改完跑一次 `prep_briefing_input.py` 看终端 top 5 是否合理。
- KOL 名单 `data/x_kol_list.jsonl` 直接编辑，每行一个 JSON。`category ∈ {crypto, us_stock, both}`。

## 故障速查

| 现象 | 原因 | 处理 |
|---|---|---|
| 所有 handle `FAIL (empty body)` | Nitter 镜像全挂 / 沙箱网络限制 | WebFetch 验证镜像可达性 → 换 `active_source` 或加镜像到 `config.toml` |
| 某些 handle 偶发 FAIL | 镜像限流 | 调大 `rate_limit_sec` 或重跑 |
| 推文时间解析失败 | Nitter 模板变动 | 检查 `nitter_html.py` 的 `_parse_created_at` |
| 权重 top 5 全是 CZ 这种超大 V | `log_base_followers` 被关 | 确保 `config.toml` 的 `log_base_followers = true` |
| both 类账号没进简报 | `category` 字段写错 | 名单里 `category` 必须是 `crypto`/`us_stock`/`both` 三选一 |

## 不在本 Skill 范围

- 推送通知（IM/邮件）：由调用方在简报生成后自行处理。
- 历史简报对比、趋势曲线：后续扩展，当前只生成当日简报。
- 自动定时调度：交给 cron / launchd / Trae 定时任务，本 Skill 只在被调用时执行。
