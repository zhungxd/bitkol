# x.com 中文加密 & 美股 KOL 数据项目

本项目提供一份**可脚本处理**的 x.com（Twitter）中文 KOL 名单（加密货币 + 美股方向），所有账号粉丝数均为 **fxtwitter 公开 API 实测值**（抓取日期见各文件），并附带刷新与生成脚本；同时已落地 **KOL 简报 Skill**，可周期性采集推文 → 聚合权重 → 由 Agent 生成加密 / 美股分区简报。

## 目录结构

```
bitkol/
├── data/                          # ★ 所有数据产物
│   ├── x_kol_list.jsonl            #   主名单：77 个 KOL，每行一个 JSON（脚本处理首选）
│   ├── x_kol_list.md              #   人类可读版：按「加密 / 美股」分组的表格
│   ├── kol_avatars.json           #   KOL 头像 URL 表（fetch_avatars.py 生成，handle → twitter/nitter URL）
│   ├── raw/                       #   原始抓取/存档数据（勿手动修改）
│   │   ├── followers_raw.json     #     第一次批量抓取的粉丝数原始数据（105 个候选 handle）
│   │   ├── extra_raw.jsonl        #     补充验证的原始数据（9 个知名账号）
│   │   ├── biteye_kol.html        #     数据来源：Biteye《华语加密 KOL 影响力图鉴》存档
│   │   └── odaily_us.html         #     数据来源：Biteye《X 美股投资交易 50 位大咖》存档
│   ├── views/                     #   采集到的推文存档，按 <handle>.jsonl 落盘追加去重
│   └── briefings/                 #   简报产物
│       ├── _input/<date>_<partition>.json   # prep_briefing_input.py 输出，Agent 消费
│       └── <date>_<partition>.md            # Agent 生成的最终简报
├── viewer/
│   └── index.html                 # ★ KOL 发言浏览器（单文件前端，本地 http.server 承载）
├── scripts/                       # 采集 / 生成 / 聚合脚本
│   ├── fetch_followers.py         #   批量抓取粉丝数（fxtwitter API）→ data/raw/followers_raw.json
│   ├── build_list.py              #   元数据合并 → 生成 data/x_kol_list.{jsonl,md}
│   ├── collect_tweets.py           #   采集编排器（薄层，委托 skills/kol_briefing/sources）
│   ├── fetch_avatars.py           #   抓取 KOL 头像 URL（Nitter HTML 反解 Twitter 原始 URL）
│   └── prep_briefing_input.py      #   聚合 + 权重 + 分区 → _input JSON
├── skills/kol_briefing/           # ★ KOL 简报 Skill
│   ├── SKILL.md                   #   Agent 执行流程（必读：4 步操作指南）
│   ├── config.toml                #   所有可调参数（数据源 / 采集 / 权重 / 分区）
│   ├── config_loader.py           #   TOML 加载（3.11+ tomllib + fallback）
│   ├── weights.py                 #   权重公式 + 分区筛选（纯函数）
│   ├── sources/                   #   可插拔推文数据源
│   │   ├── __init__.py             #     TweetSource 抽象基类 + 工厂
│   │   ├── nitter_html.py           #     备选源：Nitter HTML（urllib，无法绕 JA3 反爬）
│   │   ├── nitter_curl_cffi.py     #     默认源：Nitter HTML + curl_cffi（Firefox 指纹绕 JA3）
│   │   └── nitter_rss.py            #     备选源：Nitter RSS（多数镜像已禁用，保留兼容）
│   └── prompts/                   #   Agent prompt 与输出模板
│       ├── briefing_system.md      #     system prompt（分析原则 / 立场判定速查）
│       └── briefing_template.md    #     简报 7 章节输出模板
├── .env.example                   # 环境变量示例（Nitter 镜像列表等）
└── README.md                      # 本文档
```

## 数据格式：data/x_kol_list.jsonl

每行一个 JSON 对象，UTF-8 编码，共 77 行。字段说明：

| 字段 | 类型 | 说明 |
|---|---|---|
| `name` | string | 中文名 / 常用名 |
| `handle` | string | X 用户名（不含 @，实际 screen_name，区分大小写） |
| `url` | string | 主页链接 `https://x.com/<handle>` |
| `followers` | int | 粉丝数（实测值） |
| `followers_fetched_at` | string | 粉丝数抓取日期 `YYYY-MM-DD` |
| `category` | string | `crypto`（加密）/ `us_stock`（美股）/ `both`（双领域） |
| `type` | string | 账号性质：`个人-创始人` / `个人-投资人` / `个人-投研` / `个人-交易` / `个人-空投` / `个人-DeFi` / `个人-AI` / `个人-RWA` / `个人-研究` / `个人-可视化` / `媒体` / `官方` |
| `track` | string | 内容赛道，如 `交易`、`空投`、`半导体/科技股`、`宏观/期权` |
| `focus` | string | 一句话简介（关注方向 / 身份） |
| `bio` | string | X 账号原始简介（description，可能为空字符串） |
| `source` | string | 数据来源：`知名人物` / `知名媒体` / `知名官方` / `Biteye华语KOL榜` / `Biteye美股50人榜` |
| `note` | string | 备注（handle 变更、粉丝接近门槛等），无则空串 |
| `migrated_from` | string | 可选。handle 迁移来源（如 bio 声明「中文号见 @xxx」后，英文号被替换为中文号时记录旧 handle，如 `justinsuntron`） |
| `protected` | bool | 可选。`true` 表示账号已上锁（仅粉丝可见），采集脚本自动跳过（如 `dotyyds1234`）。删除该字段即可恢复采集 |

示例（首行）：

```json
{"name": "CZ 赵长鹏", "handle": "cz_binance", "url": "https://x.com/cz_binance",
 "followers": 12523757, "followers_fetched_at": "2026-08-22",
 "category": "crypto", "type": "个人-创始人", "track": "交易所",
 "focus": "币安创始人，加密行业最具影响力的华人领袖",
 "bio": "Buy the book (proceeds go to charity)...",
 "source": "知名人物", "note": ""}
```

### 常用处理示例

```bash
# 列出 10 万粉以上的 handle + 粉丝数
jq -r 'select(.followers >= 100000) | .handle + " " + (.followers|tostring)' data/x_kol_list.jsonl

# 只看美股分类的链接
jq -r 'select(.category == "us_stock" or .category == "both") | .url' data/x_kol_list.jsonl
```

```python
import json

kols = [json.loads(line) for line in open("data/x_kol_list.jsonl", encoding="utf-8")]
targets = [k["url"] for k in kols if k["followers"] >= 20000]   # 全部均≥2万
```

## 如何刷新粉丝数

粉丝数会随时间变化，重跑抓取脚本即可更新（修改 `scripts/fetch_followers.py` 顶部的 `HANDLES` 列表可增删候选）：

```bash
python3 scripts/fetch_followers.py
# 输出 data/raw/followers_raw.json（全量原始数据），并打印 ≥2万 的账号
```

抓取结果为全量原始数据，之后需重跑生成脚本才会更新主数据文件。

## 如何新增 / 修改 KOL

人工维护入口是 `scripts/build_list.py` 中的 `CURATED` 元组列表：

```python
# 格式: (handle, 中文名, category, type, track, focus, source, note)
("0xtodd", "0xTodd", "crypto", "个人-投研", "以太坊/策略", "知名加密投研", "知名人物", ""),
```

流程：
1. 在 `CURATED` 中新增元组（handle 必须小写）；
2. 确认该 handle 在 `scripts/fetch_followers.py` 的 `HANDLES` 中（或先跑一遍抓取）；
3. 运行 `python3 scripts/build_list.py`，重新生成 `data/x_kol_list.jsonl` 与 `data/x_kol_list.md`。

## 数据来源

| 来源 | 说明 |
|---|---|
| [Biteye《华语加密 KOL 影响力图鉴》](https://m.163.com/dy/article/KASUM7BB05568W0A.html)（XHunt 联合发布，2025-09-24 快照） | 空投 / 交易 / DeFi / AI / RWA 五大赛道榜单，原始页面已存档到 `data/raw/biteye_kol.html` |
| [Biteye《X 美股投资交易 50 位大咖「去噪」清单》](https://www.odaily.news/zh-CN/post/5210990) | 美股核心 / 科技 AI 半导体 / 资讯三类，原始页面已存档到 `data/raw/odaily_us.html` |
| 公开知名人物 / 媒体清单 | CZ、何一、孙宇晨、神鱼、立党、吴说、硅谷王川等 |

粉丝数由 [fxtwitter API](https://api.fxtwitter.com/<handle>) 于 `followers_fetched_at` 日期实测，非第三方估算。

## 已知问题与边界

- **粉丝数门槛**：全部账号 ≥2 万（唯一例外 `老白 @bclaobai` 19,834 在 `note` 中标注，接近门槛）。
- **已剔除的知名账号**（粉丝不足或账号异常，未收录）：李笑来（6.5k）、赵东（5.2k）、PANews（11.9k）、华尔街见闻（疑似停用）、律动 BlockBeats（疑似停用）。
- **handle 可能变更**：神鱼实际 handle 为 `@bitfish`（DiscusFish）；硅谷王川为 `@Svwang1`。
- **中文号优先**：已扫描全部 KOL bio，3 个声明「中文号见 @xxx」的英文号已替换为中文号（旧 handle 记录在 `migrated_from` 字段）：
  - `@justinsuntron` → `@sunyuchentron`（孙宇晨，bio: "Chinese @sunyuchentron"）
  - `@DoveyWan` → `@DoveyWanCN`（万卉 Dovey Wan，bio: "@DoveyWanCN for 中文"）
  - `@JiangZhuoer` → `@JiangZhuoer2`（江卓尔，bio: "这是英文号，中文号见 @JiangZhuoer2"）
- **已上锁账号**：`@dotyyds1234`（憨巴龙王）已设为 protected（仅粉丝可见，无法采集），名单中标记 `"protected": true`，采集脚本自动跳过；解锁后删除该字段即可恢复。
- 榜单快照本质：`source=Biteye华语KOL榜` 的账号为 2025-09-24 影响力快照，活跃度可能变化，建议采集时校验。

## KOL 简报 Skill（已落地）

完整的「采集 → 聚合权重 → Agent 生成简报」流水线已实现，**不调用任何 LLM API**：脚本只做数据搬运与权重计算，分析由 Agent 自身能力完成。

**前置依赖**：默认源 `nitter_curl_cffi` 需安装 `curl_cffi`（约 5MB，含 curl-impersonate 二进制）：

```bash
pip install curl_cffi
```

**完整说明见 [skills/kol_briefing/SKILL.md](skills/kol_briefing/SKILL.md)，4 步执行流程：**

1. **采集**：`python3 scripts/collect_tweets.py` → 推文落盘到 `data/views/<handle>.jsonl`（按 tweet id 去重追加；转推/引用推文带 `retweet_of` / `quoted` 字段。补全历史数据的转推信息可加 `--refetch`：重抓窗口内推文并合并重写，同 id 新数据优先、旧数据不丢）
2. **聚合**：`python3 scripts/prep_briefing_input.py` → 输出 `data/briefings/_input/<date>_<partition>.json`（含权重 / breakdown / 分区 / 转推与引用信息；每 KOL 当天最多 5 条，超出时非转推优先、正文字数降序，上限可在 `config.toml` 的 `[briefing].daily_max_per_kol` 调）
3. **分析**：Agent 用 `Read` 工具打开 _input JSON，按 [prompts/briefing_system.md](skills/kol_briefing/prompts/briefing_system.md) 的原则与立场判定速查分析
4. **输出**：按 [prompts/briefing_template.md](skills/kol_briefing/prompts/briefing_template.md) 模板生成 `data/briefings/<date>_<partition>.md`

### 数据源（默认 Nitter + curl_cffi，可一行切换）

- `active_source = "nitter_curl_cffi"`（**默认，推荐**）：用 `curl_cffi` + Firefox TLS 指纹绕过 Nitter Caddy 的 JA3 反爬。需 `pip install curl_cffi`。代理走 `HTTPS_PROXY` 环境变量或 `config.toml` 的 `proxy_url`。
- `active_source = "nitter_html"`（备选）：纯 stdlib urllib，沙箱/反爬环境可能拿不到数据（Caddy 返回 200 + 空 body）
- `active_source = "nitter_rss"`（备选）：多数镜像已禁用 RSS，保留兼容
- 官方 X API 因收费未采用；如需切换或新增源（如 fxtwitter_ext），见 [SKILL.md](skills/kol_briefing/SKILL.md) 的「换数据源」章节，编排脚本零改动。

> **JA3 反爬说明**：实测 Nitter 的 Caddy 反代按 TLS Client Hello 指纹过滤，Chrome/Safari/Edge 指纹被返回空 body，仅 Firefox 指纹能拿到真实 HTML。`curl_cffi` 内置 curl-impersonate 可完美模仿浏览器指纹，是当前唯一不依赖浏览器自动化就能绕过的方法。

### 权重设计

权重公式：`raw = log10(followers) × type_mult × source_mult × track_bonus`，**分区内归一化**（每区 weight 之和 = 1.0），各系数在 [config.toml](skills/kol_briefing/config.toml) 集中可调，每个 KOL 附 `weight_breakdown` 供审计。

- **影响力**：log10 压缩粉丝数，避免 CZ 等超大 V 压倒一切
- **专业度**：投研 / 研究 > 交易 > 投资人 / 创始人 > 赛道专家 > 媒体 > 官方
- **权威度**：知名人物 > Biteye 榜 > 媒体 > 官方
- **赛道匹配**：KOL `track` 与分区匹配则乘 bonus（如「半导体/科技股」在 us_stock 分区加成）

### 分区逻辑

按 KOL 名单的 `category` 字段分 crypto / us_stock 两区，`both` 类账号同时进两份简报。

### 推文数据格式（data/views/<handle>.jsonl）

每行一个 JSON，UTF-8，按 tweet `id` 去重追加：

| 字段 | 说明 |
|---|---|
| `id` | 推文 id（主键） |
| `created_at` | ISO8601 时间字符串 |
| `text` | 推文全文 |
| `url` | 推文链接 |
| `public_metrics` | `{replies, retweets, likes}`（如源支持） |
| `author` | 可选。推文作者 handle（从 status 链接路径提取；转推时为原作者，原创时等于本 KOL） |
| `retweet_of` | 可选。转推标识：原作者 handle（status 链接作者 ≠ 本 KOL 时记录） |
| `quoted` | 可选。引用推文 `{author, id, text}`（被引用推文的作者 / id / 正文） |
| `fetched_at` | 抓取时间戳 |
| `handle` | 所属 KOL handle |

## KOL 发言浏览器（viewer/）

本地 Web 前端，直观浏览采集到的 KOL 完整原始发言（不做 AI 整理），按日切换，展示 KOL 名 / 关注数 / 头像 / 权重与全部推文。

### 启动

```bash
cd /path/to/bitkol
python3 -m http.server 8765
# 浏览器打开 http://localhost:8765/viewer/
```

### 功能

- **日期切换**：只显示本地实际有数据的日期（`data/briefings/_input/` 下存在对应 JSON 的日期）
- **分区切换**：加密 / 美股
- **排序**：权重 ↓ / 关注数 ↓ / 最新推文 ↓ / 推文数 ↓
- **搜索**：KOL 名 / handle / 推文内容关键词
- **KOL 聚合长列表**：每个 KOL 一个 section（头像 + 名 + handle + 类型/赛道标签 + 关注/权重/推文数统计），默认展开全部推文，点击头部折叠
- **推文渲染**：保留换行，@mention / #hashtag / $TICKER / URL 自动链接化，互动数据 + 原文外链
- **转推展示**：绿色「转推自 @原作者」标识条（原作者可点击跳 x.com），外链按钮变「原推 ↗」直指原推
- **引用推文卡片**：正文下方嵌套引用块（橙色竖线 + @原作者 + 引用正文，超 200 字渐隐截断），整卡可点跳原推
- **搜索增强**：转推者 handle、引用推文正文也纳入关键词匹配
- **头像三级 fallback**：Twitter 原始 URL → Nitter 镜像 URL → 首字母色块（配色按 handle hash）
- **cache-busting**：所有 fetch 带时间戳参数，刷新即最新数据，不受浏览器缓存影响

单文件实现（HTML + CSS + JS 内联，无构建依赖），编辑/杂志风暗色主题。

### KOL 头像维护

头像 URL 表 `data/kol_avatars.json` 由 `scripts/fetch_avatars.py` 生成（从 Nitter 个人页 HTML 的 `/pic/...` 路径反解出原始 Twitter 头像 URL）：

```bash
# 全量抓取（增量：跳过已有 handle）
HTTPS_PROXY=http://127.0.0.1:7897 python3 scripts/fetch_avatars.py

# 强制重新抓取所有（保留缓存，逐个覆盖）
HTTPS_PROXY=http://127.0.0.1:7897 python3 scripts/fetch_avatars.py --force

# 单 handle 调试
HTTPS_PROXY=http://127.0.0.1:7897 python3 scripts/fetch_avatars.py --handle cz_binance
```

依赖 `curl_cffi`（与采集源相同）。新增 KOL 后重跑一次即可补齐头像。
