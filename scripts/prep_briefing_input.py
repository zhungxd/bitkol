#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""聚合 KOL 推文 + 权重 + 分区，生成 Agent 直接消费的 briefing input JSON。

把分散的 data/views/*.jsonl + data/x_kol_list.jsonl + 权重逻辑合成单文件输入。
Agent 读取此 JSON 后用自身 LLM 能力生成简报（脚本不调用任何 LLM）。

日报口径：按一个日历日（本地时区 UTC+8）过滤推文，默认出前一天（T-1）的日报
（一天走完数据才完整）。更早的日期不自动补，需要时显式传 --date。

Input : data/views/<handle>.jsonl, data/x_kol_list.jsonl, skills/kol_briefing/config.toml, skills/kol_briefing/weights.py
Output: data/briefings/_input/<date>_<partition>.json（crypto 与 us_stock 各一）

用法:
  python3 scripts/prep_briefing_input.py                        # 前一天（T-1）日报
  python3 scripts/prep_briefing_input.py --date 2026-08-23      # 指定日期（补报/当天）
"""
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = PROJECT_ROOT / "skills" / "kol_briefing"
DATA_DIR = PROJECT_ROOT / "data"
VIEWS_DIR = DATA_DIR / "views"
KOL_LIST_PATH = DATA_DIR / "x_kol_list.jsonl"
CONFIG_PATH = SKILL_DIR / "config.toml"
INPUT_DIR = DATA_DIR / "briefings" / "_input"

if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

_TZ_LOCAL = timezone(timedelta(hours=8))


def load_kols(kol_list_path):
    kols = []
    for line in kol_list_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            kols.append(json.loads(line))
    return kols


def load_tweets(handle, report_date):
    """读 data/views/<handle>.jsonl，只保留本地时区（UTC+8）日历日 == report_date 的推文。"""
    path = VIEWS_DIR / f"{handle}.jsonl"
    if not path.exists():
        return []
    tweets = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            t = json.loads(line)
        except json.JSONDecodeError:
            continue
        ca = t.get("created_at")
        if not ca:
            continue
        try:
            s = ca.replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=_TZ_LOCAL)
            if dt.astimezone(_TZ_LOCAL).date() != report_date:
                continue
        except Exception:
            continue
        tweets.append(t)
    return tweets


# ---- CLI ----
ap = argparse.ArgumentParser(description="聚合 KOL 推文+权重+分区 → 日报 briefing input JSON")
ap.add_argument("--date", type=str, default=None, help="日报日期 YYYY-MM-DD，默认前一天 T-1（更早的不自动补）")
args = ap.parse_args()

from config_loader import load_config
from weights import select_kols_for_partition, compute_weights

config = load_config(CONFIG_PATH)
briefing_cfg = config.get("briefing", {})
daily_max = briefing_cfg.get("daily_max_per_kol", 5)

now = datetime.now(_TZ_LOCAL)
if args.date:
    try:
        report_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    except ValueError:
        sys.exit(f"[error] --date 格式应为 YYYY-MM-DD，收到: {args.date}")
else:
    report_date = (now - timedelta(days=1)).date()
date_str = report_date.strftime("%Y-%m-%d")
INPUT_DIR.mkdir(parents=True, exist_ok=True)

all_kols = load_kols(KOL_LIST_PATH)
print(f"[load] {len(all_kols)} KOLs, report_date={date_str}, daily_max_per_kol={daily_max}")

PARTITIONS = ["crypto", "us_stock"]
PARTITION_LABELS = {"crypto": "加密货币", "us_stock": "美股"}

for partition in PARTITIONS:
    selected = select_kols_for_partition(all_kols, partition, config)
    print(f"\n=== {partition} ({PARTITION_LABELS[partition]}) ===")
    print(f"  KOLs in partition: {len(selected)}")

    # 收集每个 KOL 的推文
    kols_with_tweets = []
    excluded_empty = []
    total_tweets = 0
    for k in selected:
        handle = k.get("handle")
        tweets = load_tweets(handle, report_date)
        # 日报每 KOL 最多 daily_max 条；超出时：优先原创（非转推），再按正文字数降序
        # （引用推文 QT 有自己的观点，算原创；纯转推 text 即原文，排在后面）
        if len(tweets) > daily_max:
            def _pick_key(t):
                is_retweet = 1 if t.get("retweet_of") else 0
                return (is_retweet, -len(t.get("text") or ""))
            tweets = sorted(tweets, key=_pick_key)[:daily_max]
        if not tweets:
            excluded_empty.append(handle)
            continue
        total_tweets += len(tweets)
        kols_with_tweets.append({**k, "_tweets": tweets})

    print(f"  KOLs with tweets: {len(kols_with_tweets)}")
    print(f"  Excluded (no tweets): {len(excluded_empty)}")
    print(f"  Total tweets: {total_tweets}")
    if excluded_empty:
        print(f"  Empty: {', '.join(excluded_empty[:10])}{'...' if len(excluded_empty)>10 else ''}")

    if not kols_with_tweets:
        print(f"  [skip] no tweets for {partition}, skipping")
        continue

    # 计算权重（分区归一化）
    # 只取 KOL 元数据字段（不含 _tweets）参与权重计算
    kols_meta = [{k: v for k, v in kol.items() if k != "_tweets"} for kol in kols_with_tweets]
    weighted = compute_weights(kols_meta, partition, config)

    # 组装 briefing input
    kols_out = []
    for i, kol in enumerate(weighted):
        tweets = kols_with_tweets[i]["_tweets"]
        kols_out.append({
            "handle": kol.get("handle"),
            "name": kol.get("name"),
            "url": kol.get("url"),
            "followers": kol.get("followers"),
            "category": kol.get("category"),
            "type": kol.get("type"),
            "track": kol.get("track"),
            "focus": kol.get("focus"),
            "source": kol.get("source"),
            "weight": kol.get("weight"),
            "weight_breakdown": kol.get("weight_breakdown"),
            "tweets": [
                {
                    "id": t.get("id"),
                    "created_at": t.get("created_at"),
                    "text": t.get("text", ""),
                    "url": t.get("url", ""),
                    "public_metrics": t.get("public_metrics"),
                    "retweet_of": t.get("retweet_of"),
                    "quoted": t.get("quoted"),
                }
                for t in tweets
            ],
        })

    # 按 weight 降序
    kols_out.sort(key=lambda k: k["weight"], reverse=True)

    briefing_input = {
        "partition": partition,
        "partition_label": PARTITION_LABELS[partition],
        "generated_at": now.isoformat(),
        "window": {"days": 1, "date": date_str, "max_per_kol": daily_max},
        "stats": {
            "kol_total": len(selected),
            "kol_with_tweets": len(kols_with_tweets),
            "tweets_total": total_tweets,
            "excluded_empty": excluded_empty,
        },
        "kols": kols_out,
    }

    out_path = INPUT_DIR / f"{date_str}_{partition}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(briefing_input, f, ensure_ascii=False, indent=2)
    print(f"  [out] {out_path}")

    # 打印权重 top5
    print(f"  Weight top 5:")
    for k in kols_out[:5]:
        print(f"    {k['weight']:.4f} @{k['handle']} ({k['name']}) [{k['type']}]")

print(f"\nDone. Output dir: {INPUT_DIR}")
