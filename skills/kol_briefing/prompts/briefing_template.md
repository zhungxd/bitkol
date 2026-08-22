# KOL 简报模板

> Agent 生成简报时严格使用此模板。`{{...}}` 为占位符，输出时替换为实际内容。
> 输出文件：`data/briefings/{{date}}_{{partition}}.md`

---

# {{partition_label}} KOL 简报 · {{date}}

> 窗口：{{window_days}} 天 / 每 KOL 最多 {{max_per_kol}} 条
> 入选 KOL：{{kol_with_tweets}}/{{kol_total}}（共 {{tweets_total}} 条推文）
> 无新推文 KOL：{{excluded_empty_short}}（{{excluded_empty_count}}）

## 1. 一句话结论

{{一句话总结本期加权情绪与最热赛道。例：「加权情绪偏多（多 0.62 / 空 0.18 / 中 0.20），BTC 与 AI 算力板块共识最强，立党与 CZ 在纳指上出现分歧。」}}

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
- **核心观点**：{{topic_1_summary}}
- **关键引用**：
  > {{topic_1_quote_1}} — @{{topic_1_kol_1}}
  > {{topic_1_quote_2}} — @{{topic_1_kol_2}}

### 3.2 {{topic_2_title}}（共识度：{{topic_2_consensus}}）

- **代表 KOL**：{{topic_2_kols}}
- **核心观点**：{{topic_2_summary}}
- **关键引用**：
  > {{topic_2_quote}} — @{{topic_2_kol}}

### 3.3 {{topic_3_title}}（如有）

...

> 若某赛道仅有 1-2 位 KOL 提及，标注「小众信号」，不强行列为热点。

## 4. 高权重 KOL 速写（Top 5）

| # | KOL | 权重 | 立场 | 核心一句话 |
|---|---|---|---|---|
| 1 | @{{handle}}（{{name}}） | {{weight}} | {{stance}} | {{one_liner}} |
| 2 | ... | ... | ... | ... |
| 3 | ... | ... | ... | ... |
| 4 | ... | ... | ... | ... |
| 5 | ... | ... | ... | ... |

## 5. 分歧与共识

### 共识
- {{consensus_1}}
- {{consensus_2}}

### 分歧
- **{{dispute_topic}}**：@{{dispute_kol_a}}（{{dispute_stance_a}}） vs @{{dispute_kol_b}}（{{dispute_stance_b}}）
  > {{dispute_quote_a}} — @{{dispute_kol_a}}
  > {{dispute_quote_b}} — @{{dispute_kol_b}}
  > 解读：{{dispute_interpretation}}

## 6. 风险与异常信号

- {{risk_signal_1}}（@{{risk_kol_1}}）
- {{risk_signal_2}}（@{{risk_kol_2}}）

> 包括但不限于：交易所/项目暴雷预警、监管事件、宏观拐点、背离信号（价格涨但 KOL 加权转空）等。
> 无明显信号时写「本期无明显风险信号」。

## 7. 数据口径与免责

- 数据源：Nitter 镜像（`config.toml` 当前 `active_source = {{active_source}}`）
- 采集时间：{{generated_at}}
- 权重公式：`log10(followers) × type_mult × source_mult × track_bonus`，分区内归一化
- 本简报仅基于 KOL 公开发言，**不构成投资建议**。KOL 观点可能存在利益相关，请独立判断。

---

## 模板使用说明（Agent 内部参考，不写入输出）

- 所有 `{{...}}` 占位符必须替换；无内容时按章节规则写「本期无明显信号」或「—」。
- 章节顺序固定，不要增删顶层章节。
- `topic_*` 章节数量按实际热点定，至少 1 个，至多 5 个；超过 5 个合并到「其他关注」一段。
- 引用必须来自 `_input` JSON 的 `tweets[].text`，不可改写原文意思，可截取关键句。
- 情绪指数保留两位小数（如 0.62）。
- `excluded_empty_short`：只列前 5 个 handle，余下用 `等 N 个` 省略。
