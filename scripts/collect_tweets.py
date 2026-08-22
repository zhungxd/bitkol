#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""采集 KOL 近期推文，落盘到 data/views/<handle>.jsonl（按 tweet id 去重追加）。

薄编排层：不含任何具体抓取逻辑，全部委托给 skills/kol_briefing/sources 的可插拔 source。
换源只需改 skills/kol_briefing/config.toml 的 [source].active_source，本文件零改动。

Input : data/x_kol_list.jsonl, skills/kol_briefing/config.toml
Output: data/views/<handle>.jsonl（每行一个推文 JSON，UTF-8）

用法:
  python3 scripts/collect_tweets.py                          # 全量，按 config 默认
  python3 scripts/collect_tweets.py --handle hebi555          # 单 handle（Phase 0 验证用）
  python3 scripts/collect_tweets.py --days 7 --max-per-kol 20 # 覆盖 config
  python3 scripts/collect_tweets.py --partition crypto        # 只抓加密分区（含 both）
  python3 scripts/collect_tweets.py --source nitter_rss      # 临时换源（不改 config）
"""
import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = PROJECT_ROOT / "skills" / "kol_briefing"
DATA_DIR = PROJECT_ROOT / "data"
VIEWS_DIR = DATA_DIR / "views"
KOL_LIST_PATH = DATA_DIR / "x_kol_list.jsonl"
CONFIG_PATH = SKILL_DIR / "config.toml"

# 注入 skill 目录到 sys.path，使 sources 包与 config_loader 可被绝对导入
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

_TZ_LOCAL = timezone(timedelta(hours=8))


def load_kols(kol_list_path, partition=None):
    """加载 KOL 名单。partition 过滤：crypto/us_stock（both 两边都含）。"""
    kols = []
    for line in kol_list_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        kols.append(json.loads(line))
    if partition:
        both_to = ["crypto", "us_stock"]
        kols = [k for k in kols if k.get("category") == partition or
                (k.get("category") == "both" and partition in both_to)]
    return kols


def load_existing_ids(view_path):
    """读取已有 data/views/<handle>.jsonl，返回已存在的 tweet id 集合。"""
    ids = set()
    if not view_path.exists():
        return ids
    for line in view_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
            if d.get("id"):
                ids.add(d["id"])
        except json.JSONDecodeError:
            continue
    return ids


def append_tweets(view_path, tweets, handle):
    """追加新推文到 data/views/<handle>.jsonl。"""
    view_path.parent.mkdir(parents=True, exist_ok=True)
    now_iso = datetime.now(_TZ_LOCAL).isoformat()
    with open(view_path, "a", encoding="utf-8") as f:
        for t in tweets:
            t["fetched_at"] = now_iso
            t["handle"] = handle
            # 字段顺序：id, created_at, text, url, public_metrics, fetched_at, handle
            ordered = {
                "id": t.get("id"),
                "created_at": t.get("created_at"),
                "text": t.get("text", ""),
                "url": t.get("url", ""),
            }
            if t.get("public_metrics"):
                ordered["public_metrics"] = t["public_metrics"]
            ordered["fetched_at"] = now_iso
            ordered["handle"] = handle
            f.write(json.dumps(ordered, ensure_ascii=False) + "\n")


# ---- CLI ----
ap = argparse.ArgumentParser(description="采集 KOL 近期推文")
ap.add_argument("--days", type=int, default=None, help="时间窗口（天），覆盖 config")
ap.add_argument("--max-per-kol", type=int, default=None, help="每 KOL 最多采集条数，覆盖 config")
ap.add_argument("--handle", type=str, default=None, help="只抓单个 handle（调试/验证用）")
ap.add_argument("--partition", type=str, default=None, choices=["crypto", "us_stock"], help="只抓该分区（含 both）")
ap.add_argument("--source", type=str, default=None, help="临时覆盖 active_source（不改 config）")
args = ap.parse_args()

# 加载配置
from config_loader import load_config
config = load_config(CONFIG_PATH)
collect_cfg = config.get("collect", {})
max_per_kol = args.max_per_kol if args.max_per_kol is not None else collect_cfg.get("max_per_kol", 20)
days_window = args.days if args.days is not None else collect_cfg.get("days_window", 7)
rate_limit = collect_cfg.get("rate_limit_sec", 1.5)

# 临时换源
if args.source:
    config.setdefault("source", {})["active_source"] = args.source

# 获取 source 实例
from sources import get_source
source = get_source(config)
print(f"[config] active_source={source.name}, max_per_kol={max_per_kol}, days_window={days_window}, rate_limit={rate_limit}s")

# 加载 KOL
if args.handle:
    kols = [{"handle": args.handle, "name": args.handle, "category": "unknown"}]
else:
    kols = load_kols(KOL_LIST_PATH, partition=args.partition)
print(f"[kol] {len(kols)} KOLs to collect")

# 采集循环
total_new = 0
failed = []
for i, k in enumerate(kols):
    handle = k.get("handle")
    name = k.get("name", handle)
    view_path = VIEWS_DIR / f"{handle}.jsonl"
    existing_ids = load_existing_ids(view_path)

    print(f"[{i+1}/{len(kols)}] @{handle} ({name}): ", end="", flush=True)
    result = source.fetch_recent(handle, max_per_kol, days_window)
    if not result.get("ok"):
        print(f"FAIL ({result.get('error', 'unknown')})")
        failed.append(handle)
        time.sleep(rate_limit)
        continue

    all_tweets = result.get("tweets", [])
    new_tweets = [t for t in all_tweets if t.get("id") and t["id"] not in existing_ids]
    if new_tweets:
        append_tweets(view_path, new_tweets, handle)
    print(f"got={len(all_tweets)} new={len(new_tweets)} total={len(existing_ids)+len(new_tweets)}")
    total_new += len(new_tweets)
    time.sleep(rate_limit)

# 汇总
print(f"\n=== Summary ===")
print(f"OK: {len(kols)-len(failed)}/{len(kols)} handles, {total_new} new tweets")
if failed:
    print(f"Failed ({len(failed)}): {', '.join(failed)}")
