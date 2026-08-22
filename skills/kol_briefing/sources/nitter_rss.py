#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nitter RSS 抓取 source（备选）。

注：nitter.net 已禁用 RSS（返回 "RSS feed is disabled"）。
此 source 仅当某些镜像开启 RSS 端点时可用。
路径：<mirror>/<handle>/rss，用 xml.etree.ElementTree（标准库）解析。
"""
import re
import time
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

from . import TweetSource

_TZ_LOCAL = timezone(timedelta(hours=8))
_STATUS_RE = re.compile(r'/status/(\d{5,})', re.IGNORECASE)


def _fetch_rss(mirror, handle, timeout):
    """请求 nitter 镜像的 handle RSS，返回 XML 文本或 None。"""
    url = f"{mirror.rstrip('/')}/{handle}/rss"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; bitkol-collector/1.0)",
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def _parse_rss(xml_text, handle, mirror):
    """解析 nitter RSS XML，返回推文列表。"""
    tweets = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return tweets
    # RSS 2.0: rss/channel/item
    items = root.findall(".//item")
    for item in items:
        # guid/permalink 中含 status id
        guid = (item.findtext("guid") or item.findtext("link") or "")
        m = _STATUS_RE.search(guid)
        if not m:
            continue
        tid = m.group(1)
        link = item.findtext("link") or f"{mirror.rstrip('/')}/{handle}/status/{tid}"
        title = item.findtext("title") or ""
        desc = item.findtext("description") or ""
        pub = item.findtext("pubDate")
        created_at = None
        if pub:
            try:
                dt = parsedate_to_datetime(pub)
                if dt:
                    created_at = dt.isoformat()
            except Exception:
                created_at = pub
        # 描述里可能含 HTML，粗去标签
        text = re.sub(r'<[^>]+>', '', desc).strip() if desc else title
        if not text:
            text = title
        tweets.append({
            "id": tid,
            "text": text,
            "url": link,
            "created_at": created_at,
        })
    return tweets


class NitterRssSource(TweetSource):
    """Nitter RSS 抓取 source（备选）。"""

    name = "nitter_rss"

    def __init__(self, config):
        super().__init__(config)
        self.mirrors = config.get("mirrors", ["https://nitter.net"])
        self.timeout = config.get("request_timeout", 10)

    def fetch_recent(self, handle, max_results, days_window):
        handle = handle.lstrip("@")
        fetched_at = datetime.now(_TZ_LOCAL)
        tweets = []
        error = None
        used_mirror = None

        # 镜像 failover
        xml_text = None
        for mirror in self.mirrors:
            xml_text = _fetch_rss(mirror, handle, self.timeout)
            if xml_text and "<rss" in xml_text.lower():
                used_mirror = mirror
                break
            time.sleep(0.3)
        if not xml_text or not used_mirror:
            return {"ok": False, "tweets": [], "error": f"all mirrors failed for {handle} (rss)"}

        tweets = _parse_rss(xml_text, handle, used_mirror)

        # 时间窗口过滤
        if days_window and days_window > 0:
            cutoff = fetched_at - timedelta(days=days_window)
            tweets = [t for t in tweets if not t.get("created_at") or _within(t["created_at"], cutoff)]

        tweets = tweets[:max_results]
        if not tweets:
            error = f"no tweets in rss for {handle}"
        return {"ok": bool(tweets), "tweets": tweets, "error": error}


def _within(created_at_str, cutoff):
    if not created_at_str:
        return True
    try:
        s = created_at_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_TZ_LOCAL)
        return dt >= cutoff
    except Exception:
        return True
