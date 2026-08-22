# x.com 中文加密 & 美股 KOL 数据项目

本项目提供一份**可脚本处理**的 x.com（Twitter）中文 KOL 名单（加密货币 + 美股方向），所有账号粉丝数均为 **fxtwitter 公开 API 实测值**（抓取日期见各文件），并附带刷新与生成脚本，供后续开发"定期收集 KOL 观点"等下游任务使用。

## 目录结构

```
bitkol/
├── data/                        # ★ 所有数据收集产物
│   ├── x_kol_list.jsonl         #   主数据：77 个 KOL，每行一个 JSON（脚本处理首选）
│   ├── x_kol_list.md            #   人类可读版：按「加密 / 美股」分组的表格
│   ├── raw/                     #   原始抓取/存档数据（勿手动修改）
│   │   ├── followers_raw.json   #     第一次批量抓取的粉丝数原始数据（105 个候选 handle）
│   │   ├── extra_raw.jsonl      #     补充验证的原始数据（9 个知名账号）
│   │   ├── biteye_kol.html      #     数据来源：Biteye《华语加密 KOL 影响力图鉴》存档
│   │   └── odaily_us.html       #     数据来源：Biteye《X 美股投资交易 50 位大咖》存档
│   └── views/                   #   （预留）后续定期采集的 KOL 观点，按 <handle>.jsonl 存放
├── scripts/                     # 采集 / 生成脚本（代码与数据分离）
│   ├── fetch_followers.py       #   批量抓取粉丝数（fxtwitter API）→ data/raw/followers_raw.json
│   └── build_list.py            #   元数据合并 → 生成 data/x_kol_list.{jsonl,md}
└── README.md                    # 本文档
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
- 榜单快照本质：`source=Biteye华语KOL榜` 的账号为 2025-09-24 影响力快照，活跃度可能变化，建议采集时校验。

## 后续开发：定期采集 KOL 观点

采集到的观点统一落盘到 **`data/views/<handle>.jsonl`**，与名单数据保持同一目录体系。

### 方案 A：X API v2（官方，推荐，需付费/申请）

```python
import json, time, requests

BEARER = "你的 X API Bearer Token"   # 在 developer.twitter.com 申请

def fetch_recent_tweets(handle: str, max_results: int = 10) -> list:
    user = requests.get(
        f"https://api.twitter.com/2/users/by/username/{handle}",
        headers={"Authorization": f"Bearer {BEARER}"},
    ).json()["data"]
    r = requests.get(
        f"https://api.twitter.com/2/users/{user['id']}/tweets",
        headers={"Authorization": f"Bearer {BEARER}"},
        params={"max_results": max_results, "tweet.fields": "created_at,public_metrics,entities"},
    )
    return r.json().get("data", [])

kols = [json.loads(line) for line in open("data/x_kol_list.jsonl", encoding="utf-8")]
for k in kols:
    tweets = fetch_recent_tweets(k["handle"])
    # TODO: 落盘到 data/views/<handle>.jsonl，记录抓取时间戳
    time.sleep(1.2)   # 注意 Basic 层级的应用级限流 ~10 req/min
```

### 方案 B：nitter 镜像（免费，无需 token，但实例不稳定）

```python
# 例：https://nitter.net/<handle>/rss 或 /search，HTML/XML 解析
# 需自行维护可用镜像列表，建议多实例 failover
```

### 建议的数据流水线

```
定时任务（cron / GitHub Actions）
   ↓
scripts/fetch_followers.py   → 刷新粉丝数（可选，低频，如每周）
   ↓
采集脚本（方案 A/B）           → 抓取每个 handle 最近推文
   ↓
data/views/<handle>.jsonl     → 原始推文存档（带抓取时间戳，去重 by tweet id）
   ↓
分析脚本                      → 观点聚类 / 情绪 / 关键词 / 报告
```

采集去重建议：以推文 `id` 为主键建索引（如 SQLite 或按日分片的 JSONL），避免重复入库；每条记录至少保留 `id`、`created_at`、`text`、`public_metrics`、`fetched_at` 五要素。
