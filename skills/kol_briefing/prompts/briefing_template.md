# KOL 简报模板

> Agent 生成简报时严格使用此模板。`{{...}}` 为占位符，输出时替换为实际内容。
> 输出文件：`data/briefings/{{date}}_{{partition}}.md`

---

# {{partition_label}} KOL 日报 · {{date}}

> 数据窗口：{{date}} 当天（UTC+8）/ 每 KOL 最多 {{max_per_kol}} 条
> 入选 KOL：{{kol_with_tweets}}/{{kol_total}}（共 {{tweets_total}} 条推文）
> 无新推文 KOL：{{excluded_empty_short}}（{{excluded_empty_count}}）

## 1. 一句话结论

{{一句话总结本期加权情绪、最热赛道，以及本期最值得关注的一个机会或风险。}}

## 2. 加权情绪指数

| 情绪 | 加权占比 | 主要贡献 KOL |
|---|---|---|
| 看多 | {{bull_ratio}} | {{bull_kols}} |
| 看空 | {{bear_ratio}} | {{bear_kols}} |
| 中性/未表态 | {{neutral_ratio}} | — |

> 计算方式：每个明确表态的 KOL 按 `weight` 累加，分母为分区内总权重（=1.0）。
> 解读：{{bull_bear_interpretation}}

## 3. 热点赛道 / 标的

### 3.1 {{topic_1_title}}（共识度：{{topic_1_consensus}}）

- **代表 KOL**：{{topic_1_kols}}
- **核心观点**：{{topic_1_summary}}（综合多位 KOL 观点，分点注明 @handle，突出侧重差异）
- **关键引用**：
  > {{topic_1_quote_1}} — @{{topic_1_kol_1}}
  > {{topic_1_quote_2}} — @{{topic_1_kol_2}}
  > {{topic_1_quote_3}} — @{{topic_1_kol_3}}

### 3.2 {{topic_2_title}}（共识度：{{topic_2_consensus}}）

- **代表 KOL**：{{topic_2_kols}}
- **核心观点**：{{topic_2_summary}}
- **关键引用**：
  > {{topic_2_quote_1}} — @{{topic_2_kol_1}}
  > {{topic_2_quote_2}} — @{{topic_2_kol_2}}

### 3.3 {{topic_3_title}}（如有）

...

> 共识度标注：高（≥3 位 KOL 且含高权重）/ 中 / 低（单一来源）。**单一 KOL 提及但有独立价值的观点不必丢弃**：可直接成小节标注「单一来源」，或移入第 4 章对应小节。

## 4. 机会与实用信息

> 收录标准：**不要求是交易信号，也不要求共识**——只要对读者有用就列：理财/收益机会、空投与交互机会、事件与日历、有价值的分析/数据/工具/教程分享。单个 KOL 提及也收录，注明 @handle 便于回查原推。

### 4.1 理财 / 收益

- **{{yield_1_name}}**：{{yield_1_detail}}（@{{yield_1_kol}}）

### 4.2 空投 / 撸毛

- **{{airdrop_1_name}}**：{{airdrop_1_detail}}（@{{airdrop_1_kol}}）

### 4.3 事件 / 日历

- **{{event_1_name}}**：{{event_1_detail}}（@{{event_1_kol}}）

### 4.4 分析 / 工具 / 其他分享

- {{share_1}}（@{{share_1_kol}}）

> 某小节本期无内容时写「本期无」，不要删掉小节。

## 5. 高权重 KOL 速写（Top 10）

| # | KOL | 权重 | 立场 | 本期动态 |
|---|---|---|---|---|
| 1 | @{{handle}}（{{name}}） | {{weight}} | {{stance}} | {{one_liner}} |
| 2 | ... | ... | ... | ... |
| ... | ... | ... | ... | ... |

> 「本期动态」写该 KOL 本期做了什么/说了什么：操作（开仓/加仓/止损/迁移）、核心观点、值得注意的发言或事件，1-2 句。

## 6. 分歧与共识

### 共识
- {{consensus_1}}
- {{consensus_2}}

### 分歧
- **{{dispute_topic}}**：@{{dispute_kol_a}}（{{dispute_stance_a}}） vs @{{dispute_kol_b}}（{{dispute_stance_b}}）
  > {{dispute_quote_a}} — @{{dispute_kol_a}}
  > {{dispute_quote_b}} — @{{dispute_kol_b}}
  > 解读：{{dispute_interpretation}}

## 7. 风险与异常信号

- {{risk_signal_1}}（@{{risk_kol_1}}）
- {{risk_signal_2}}（@{{risk_kol_2}}）

> 包括但不限于：交易所/项目暴雷预警、监管事件、宏观拐点、背离信号（价格涨但 KOL 加权转空）等。
> 无明显信号时写「本期无明显风险信号」。

## 8. 数据口径

- 数据源：Nitter 镜像（`config.toml` 当前 `active_source = {{active_source}}`）
- 采集时间：{{generated_at}}
- 权重公式：`log10(followers) × type_mult × source_mult × track_bonus`，分区内归一化

---

## 模板使用说明（Agent 内部参考，不写入输出）

- 所有 `{{...}}` 占位符必须替换；无内容时按章节规则写「本期无明显信号」「本期无」或「—」。
- 章节顺序固定，不要增删顶层章节。
- `topic_*` 章节数量按实际热点定，至少 1 个，至多 6 个；超过 6 个合并到「其他关注」一段。
- 引用必须来自 `_input` JSON 的 `tweets[].text`，不可改写原文意思，可截取关键句。
- 情绪指数保留两位小数（如 0.62）。
- `excluded_empty_short`：只列前 5 个 handle，余下用 `等 N 个` 省略。
- **内容量目标：正文 800–2500 字**（当天数据丰富时可上浮）。宁可多列一条有用的信息，不要为凑字数注水；每个热点赛道至少 2 条引用，「核心观点」综合多人时逐条注明归属。当天推文少时如实写短，不硬撑结构。
- 第 4 章「机会与实用信息」是给读者的行动清单：理财、空投、事件、分析工具都算，**单一来源也收**，宁全勿缺，注明 @handle 便于回查。
- 第 5 章固定取权重 Top 10（不足 10 个则取全部有推文的 KOL）。
- 默认生成**前一天（T-1）**的日报，更早日期不补（用户显式要求时才补）。
