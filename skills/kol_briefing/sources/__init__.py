#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""可插拔推文数据源。

换源只需：
  1. 改 skills/kol_briefing/config.toml 的 [source].active_source
  2. （如需新源）在此包内新增一个实现 TweetSource 的模块

collect_tweets.py 通过 get_source() 获取实例，不含任何具体抓取逻辑。
"""
import sys
from pathlib import Path

# 让 sources 包能被 scripts/ 下的脚本以「绝对导入 + sys.path 注入」方式使用
_SKILL_DIR = Path(__file__).resolve().parent.parent
if str(_SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(_SKILL_DIR))


class TweetSource:
    """推文数据源抽象基类。所有 source 实现此接口。"""

    name = "base"

    def __init__(self, config):
        # config 为该 source 对应的配置子树（如 config["source"]["nitter"]）
        self.config = config or {}

    def fetch_recent(self, handle, max_results, days_window):
        """抓取某 handle 近期推文。

        参数:
            handle: X 用户名（不含 @）
            max_results: 最多返回多少条
            days_window: 时间窗口（天），0 表示不限

        返回:
            {"ok": bool, "tweets": [...], "error": str|None}
            每条 tweet: {id, created_at, text, url, public_metrics?}
            实现需自行处理镜像 failover、限速、超时。不抛异常。
        """
        raise NotImplementedError


def get_source(config):
    """工厂：按 config[source].active_source 实例化对应 source。

    config 为完整 config.toml 解析后的 dict。
    """
    source_section = config.get("source", {})
    active = source_section.get("active_source", "nitter_html")
    nitter_cfg = source_section.get("nitter", {})

    if active == "nitter_html":
        from .nitter_html import NitterHtmlSource
        return NitterHtmlSource(nitter_cfg)
    elif active == "nitter_rss":
        from .nitter_rss import NitterRssSource
        return NitterRssSource(nitter_cfg)
    # 后期新增: elif active == "fxtwitter_ext": ...
    raise ValueError(f"unknown active_source: {active}")
