# KOL 简报 Skill

> 用途：周期性收集 KOL 推文 → 聚合权重 → Agent 直接读取并生成中文简报（加密 / 美股分区）。
> 脚本只做数据搬运与权重计算，**不调用任何 LLM API**；分析由 Agent 自身 LLM 能力完成。

## 目录结构

```
bitkol/
├─ data/
│  ├─ x_kol_list.jsonl              # KOL 名单（字段: handle/name/followers/category/type/track/source/...）
│  ├─ kol_avatars.json              # KOL 头像 URL 表（fetch_avatars.py 生成）
│  ├─ views/<handle>.jsonl          # 采集结果，按 handle 落盘，追加去重
│  └─ briefings/
│     ├─ _input/<date>_<partition>.json   # prep_briefing_input.py 输出，Agent 消费
│     └─ <date>_<partition>.md            # Agent 生成的最终简报
├─ viewer/
│  └─ index.html                    # KOL 发言浏览器（本地前端，浏览原始发言）
├─ scripts/
│  ├─ collect_tweets.py             # 采集编排器（薄层，委托 sources 包）
│  ├─ fetch_avatars.py              # 抓取 KOL 头像 URL → data/kol_avatars.json
│  └─ prep_briefing_input.py        # 聚合 + 权重 + 分区 → _input JSON
└─ skills/kol_briefing/
   ├─ SKILL.md                      # 本文件
   ├─ config.toml                   # 所有可调参数（数据源/采集/权重/分区）
   ├─ config_loader.py              # TOML 加载（3.11+ tomllib + fallback）
   ├─ weights.py                    # 权重公式 + 分区筛选
   ├─ sources/
   │  ├─ __init__.py                # TweetSource 抽象基类 + 工厂
   │  ├─ nitter_curl_cffi.py        # 默认源：Nitter HTML + curl_cffi（Firefox 指纹绕 JA3）
   │  ├─ nitter_html.py             # 备选源：Nitter HTML（urllib，无法绕 JA3 反爬）
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
# 默认全量采集（按 config.toml 的 max_per_kol=20、days_window=2 滚动缓冲）
python3 scripts/collect_tweets.py

# 或仅采集某分区
python3 scripts/collect_tweets.py --partition crypto

# 或单 handle 调试
python3 scripts/collect_tweets.py --handle cz_binance

# 重抓窗口内推文并合并重写（补全转推/引用等新字段，旧数据不丢）
python3 scripts/collect_tweets.py --refetch
```

- 采集源由 `config.toml` 的 `[source].active_source` 决定，默认 `nitter_curl_cffi`（**必须** `pip install curl_cffi`）。
- 沙箱/国内网络环境需设代理：`HTTPS_PROXY=http://127.0.0.1:7897 python3 scripts/collect_tweets.py ...`，或填 `config.toml` 的 `proxy_url`。
- 失败的 handle 会在终端打印 `FAIL (...)`，不影响其他 KOL。镜像全挂时换 `active_source` 或加镜像。
- 输出落盘到 `data/views/<handle>.jsonl`，按 tweet id 去重追加。
- 转推识别：status 链接路径作者 ≠ 本 KOL 时记录 `retweet_of`（原作者）；引用推文记录 `quoted` `{author, id, text}`。二者随推文透传到 _input JSON，viewer 据此渲染转推标识与引用卡片。
- 名单中 `"protected": true` 的账号（已上锁，如 `dotyyds1234`）自动跳过，终端打印 `[skip]`。

### Step 2：聚合 → _input JSON

```bash
python3 scripts/prep_briefing_input.py                        # 前一天（T-1）日报（默认）
python3 scripts/prep_briefing_input.py --date 2026-08-23      # 仅用户明确要求指定日期时
```

- **日报口径**：只聚合该日历日（UTC+8）的推文；默认出前一天 T-1，更早日期不自动补。
- **每 KOL 条数上限**：`[briefing].daily_max_per_kol`（默认 5）。超出时优先保留原创（非转推，引用推文 QT 算原创），原创仍超出则按正文字数降序取前 N 条。
- 按 `category` 字段分 crypto / us_stock 两区，`both` 类账号只进 crypto（`[partition].both_goes_to` 可调），避免两份简报内容重复。
- 每区按 `weights.py` 计算归一化权重（和 = 1.0），附 `weight_breakdown` 供审计。
- 输出：`data/briefings/_input/<date>_<partition>.json`，每区一份。
- 终端会打印 top 5 权重 KOL，用于人工 sanity check。

### Step 3：读取 _input JSON 并分析

**不要用 RunCommand 调用任何 LLM API**。Agent 自身就是 LLM，直接读 JSON 分析。

对每个分区文件 `data/briefings/_input/<date>_<partition>.json`：

1. 用 `Read` 工具打开 JSON。
2. 关注顶层字段：
   - `partition` / `partition_label`：分区标识
   - `window.date` / `window.max_per_kol`：本次日报口径（days 恒为 1）
   - `stats`：KOL 数、推文总数、空推文 KOL 列表
   - `kols[]`：按 `weight` 降序，每个 KOL 含 `weight` / `weight_breakdown` / `tweets[]`
3. 分析维度见 `prompts/briefing_system.md`：
   - 市场情绪（加权看多/看空/中性）
   - 热点赛道/标的
   - 机会与实用信息（理财/空投/事件/分析工具分享，单一来源也收）
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
- `config.toml` 的 `[briefing]` 调日报口径：`daily_max_per_kol`（每 KOL 日报最多收录条数，默认 5；超出时非转推优先、字数降序）。
- `[weights]` 调权重公式各系数。改完跑一次 `prep_briefing_input.py` 看终端 top 5 是否合理。
- KOL 名单 `data/x_kol_list.jsonl` 直接编辑，每行一个 JSON。`category ∈ {crypto, us_stock, both}`；已上锁账号可加 `"protected": true`，采集自动跳过。
- **handle 迁移**：KOL 有中英文双号时优先中文号。修改名单 handle 后需同步清理：删 `data/views/<旧handle>.jsonl`、从 `data/kol_avatars.json` 删旧条目、重跑 `fetch_avatars.py` + `collect_tweets.py --handle <新handle>` + `prep_briefing_input.py`。旧 handle 记录在 `migrated_from` 字段（已迁移：`justinsuntron→sunyuchentron`、`DoveyWan→DoveyWanCN`、`JiangZhuoer→JiangZhuoer2`）。

## KOL 发言浏览器（viewer/）

浏览采集到的 KOL 完整原始发言（不做 AI 整理），按日/分区切换，含头像、权重、互动数据：

```bash
cd bitkol && python3 -m http.server 8765
# 打开 http://localhost:8765/viewer/
```

- 数据源：`data/briefings/_input/*.json` + `data/kol_avatars.json`（fetch 读取，带 cache-busting）
- 新增 KOL 后需重跑 `fetch_avatars.py` 补头像（详见 README「KOL 头像维护」）

## 头像抓取

```bash
HTTPS_PROXY=http://127.0.0.1:7897 python3 scripts/fetch_avatars.py            # 增量
HTTPS_PROXY=http://127.0.0.1:7897 python3 scripts/fetch_avatars.py --force    # 全量重抓
HTTPS_PROXY=http://127.0.0.1:7897 python3 scripts/fetch_avatars.py --handle cz_binance  # 单个
```

依赖 `curl_cffi`；从 Nitter 个人页 HTML 反解原始 Twitter 头像 URL，输出 `data/kol_avatars.json`。

## 故障速查

| 现象 | 原因 | 处理 |
|---|---|---|
| 所有 handle `FAIL (empty body)` | Nitter Caddy 反爬 JA3 指纹过滤（urllib/curl 被识别） | 切换 `active_source = "nitter_curl_cffi"` 并 `pip install curl_cffi` |
| 所有 handle `FAIL (all mirrors failed)` | 代理未设或镜像全挂 | 沙箱/国内网络需设 `HTTPS_PROXY` 环境变量或 `config.toml` 的 `proxy_url` |
| 某些 handle 偶发 FAIL (429) | Nitter rate limit | 调大 `request_interval` 或重跑 |
| `no tweets in last Ns (parsed X, all older)` | KOL 低频发帖，窗口内无新推（**正常**，非失败） | 无需处理；旧数据已保留。需要历史数据可跑 `--days 60` 宽窗口回填 |
| `no tweets found`（无 parsed 计数） | 真抓取失败：页面空/账号改名/上锁 | 用 `--handle` 单测重试；确认账号状态（fxtwitter API） |
| `[skip] protected 账号不采集` | 名单标记 `"protected": true`（已上锁仅粉丝可见） | 预期行为；账号解锁后删名单中该字段恢复采集 |
| 推文时间解析失败 | Nitter 模板变动 | 检查 `nitter_html.py` 的 `_parse_created_at` |
| 权重 top 5 全是 CZ 这种超大 V | `log_base_followers` 被关 | 确保 `config.toml` 的 `log_base_followers = true` |
| both 类账号没进简报 | `category` 字段写错 | 名单里 `category` 必须是 `crypto`/`us_stock`/`both` 三选一 |
| viewer 刷新后数据没更新 | 浏览器缓存（已修复） | viewer 已带 cache-busting；旧版本可硬刷新或导航到 JSON URL 一次 |
| viewer 头像不显示 | 代理未开或 `kol_avatars.json` 缺该 handle | 开代理（Twitter CDN）或重跑 `fetch_avatars.py` |
| viewer 打不开 | http.server 未启动 | `cd bitkol && python3 -m http.server 8765` |
| viewer 转推/引用不显示 | 历史日期的 _input JSON 是旧版（无 `retweet_of`/`quoted` 字段） | 该日期重新聚合，或接受历史视图无标识（增量数据自动带上） |

## 不在本 Skill 范围

- 推送通知（IM/邮件）：由调用方在简报生成后自行处理。
- 历史简报对比、趋势曲线：后续扩展，当前只生成当日简报。
- 自动定时调度：交给 cron / launchd / Trae 定时任务，本 Skill 只在被调用时执行。
