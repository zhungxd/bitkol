#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KOL 权重计算（纯函数，无副作用）。

被 scripts/prep_briefing_input.py 导入。

权重公式：
    raw = base(followers) × type_mult × source_mult × track_match_bonus
    weight = raw / sum(raws_in_partition)   # 分区归一化，权重和 = 1.0

设计原则：
1. 影响力（base）：log10(粉丝数) 压缩，避免头部超大 V 压倒一切
2. 专业度（type_mult）：投研/研究 > 交易 > 投资人/创始人 > 赛道专家 > 媒体 > 官方
3. 权威度（source_mult）：知名人物 > Biteye 榜 > 媒体 > 官方
4. 赛道匹配（track_bonus）：KOL 赛道与分区匹配则加成
5. 分区归一化：每分区内权重和 = 1.0，便于加权情绪指数计算
"""
import math


def _base_followers(followers, config):
    """粉丝数 → 影响力基数。log10 压缩或线性。"""
    if followers is None or followers <= 0:
        followers = 1
    if config.get("weights", {}).get("log_base_followers", True):
        return math.log10(followers)
    return float(followers)


def _type_mult(kol, config):
    """账号性质系数。默认 1.0。"""
    t = kol.get("type", "")
    return config.get("weights", {}).get("type_mult", {}).get(t, 1.0)


def _source_mult(kol, config):
    """数据来源系数。默认 1.0。"""
    s = kol.get("source", "")
    return config.get("weights", {}).get("source_mult", {}).get(s, 1.0)


def _track_matches_partition(track, partition, config):
    """判断 KOL 赛道是否匹配分区（用于 track_bonus）。"""
    keywords_cfg = config.get("weights", {}).get("track_keywords", {}).get(partition, {})
    keywords = keywords_cfg.get("keywords", [])
    if not keywords:
        return False
    track_lower = (track or "").lower()
    for kw in keywords:
        if kw.lower() in track_lower:
            return True
    return False


def _track_bonus(kol, partition, config):
    """赛道匹配加成。匹配则乘 bonus，否则 1.0。"""
    bonus_cfg = config.get("weights", {}).get("track_match_bonus", {})
    if not bonus_cfg.get("enabled", True):
        return 1.0
    if _track_matches_partition(kol.get("track", ""), partition, config):
        return bonus_cfg.get("bonus", 1.10)
    return 1.0


def compute_raw(kol, partition, config):
    """计算单个 KOL 在指定分区的原始权重（未归一化）+ breakdown。

    返回 {"raw": float, "breakdown": {...}}
    """
    base = _base_followers(kol.get("followers"), config)
    tm = _type_mult(kol, config)
    sm = _source_mult(kol, config)
    tb = _track_bonus(kol, partition, config)
    raw = base * tm * sm * tb
    return {
        "raw": raw,
        "breakdown": {
            "base_log_followers": round(base, 4),
            "type_mult": tm,
            "source_mult": sm,
            "track_bonus": tb,
            "raw": round(raw, 4),
        },
    }


def compute_weights(kols, partition, config):
    """对一组 KOL 在指定分区内计算归一化权重。

    入参 kols: list[dict]，每个含 followers/type/source/track 等字段
    返回 list[dict]，每个含原 kol 字段 + weight + weight_breakdown
    分区内 weight 之和 = 1.0（误差 < 1e-9）
    """
    if not kols:
        return []
    raws = [compute_raw(k, partition, config) for k in kols]
    total = sum(r["raw"] for r in raws)
    if total <= 0:
        # 兜底：均匀分配
        n = len(kols)
        return [
            {
                **k,
                "weight": round(1.0 / n, 6),
                "weight_breakdown": raws[i]["breakdown"],
            }
            for i, k in enumerate(kols)
        ]
    result = []
    for i, k in enumerate(kols):
        w = raws[i]["raw"] / total
        result.append(
            {
                **k,
                "weight": round(w, 6),
                "weight_breakdown": raws[i]["breakdown"],
            }
        )
    return result


def select_kols_for_partition(all_kols, partition, config):
    """按分区选 KOL：category == partition 或 category == 'both'。

    both 类账号同时进入 crypto 与 us_stock 两份简报。
    """
    both_to = config.get("partition", {}).get("both_goes_to", ["crypto", "us_stock"])
    selected = []
    for k in all_kols:
        cat = k.get("category", "")
        if cat == partition:
            selected.append(k)
        elif cat == "both" and partition in both_to:
            selected.append(k)
    return selected
