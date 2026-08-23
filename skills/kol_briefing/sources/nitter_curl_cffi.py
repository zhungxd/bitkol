#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nitter HTML 抓取 source（curl_cffi 版，绕 JA3 反爬）。

为什么需要这个 source：
  Nitter 的 Caddy 反代对 JA3 TLS 指纹做了反爬过滤：
    - Chrome/Safari/Edge 指纹：返回 200 + Content-Length: 0（空 body）
    - Firefox 指纹：正常返回 HTML
  纯 stdlib 的 urllib 和系统 curl 都无法绕过（Client Hello 指纹被识别）。
  curl_cffi 内置 curl-impersonate，能完美模仿 Firefox 的 TLS 指纹。

实测：nitter.net 用 firefox133 impersonate 可稳定拿到 76905 字节真实 HTML，
HTMLParser 提取 20 条推文（id + text + created_at + public_metrics 全字段）。

依赖（可选）：
  pip install curl_cffi    # 约 5MB，含 curl-impersonate 二进制

如果未安装，import 时会抛 ImportError，由调用方引导用户安装。
"""
import os
import time
import urllib.parse
from datetime import datetime, timedelta, timezone

from . import TweetSource
from .nitter_html import (
    _NitterTimelineParser,
    _fallback_regex_parse,
    _parse_created_at,
    _within_window,
    _STATUS_RE,
)

# 时区
_TZ_LOCAL = timezone(timedelta(hours=8))

# curl_cffi 是可选依赖，延迟到 __init__ 时 import 以便错误信息更清晰
try:
    from curl_cffi import requests as _crequests
    _HAS_CURL_CFFI = True
except ImportError:
    _crequests = None
    _HAS_CURL_CFFI = False


# 默认 impersonate 值：实测 firefox133 能绕过 nitter 的 JA3 反爬
# chrome* / safari* / edge* 指纹都会被 Caddy 返回 0 字节
_DEFAULT_IMPERSONATE = "firefox133"


def _fetch_html_curl_cffi(mirror, handle, timeout, impersonate, proxy_url,
                          cursor=None, max_retries=2):
    """用 curl_cffi 请求 nitter 镜像的 handle 页面，返回 HTML 文本或 None。

    curl_cffi 通过 impersonate 参数模仿浏览器的 TLS Client Hello 指纹，
    绕过 Caddy 反代对 urllib/curl 的 JA3 检测。

    proxy_url 形如 "http://127.0.0.1:7897"，None 表示不走代理直连。
    """
    if not _HAS_CURL_CFFI:
        return None

    url = f"{mirror.rstrip('/')}/{handle}"
    if cursor:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}cursor={urllib.parse.quote(cursor)}"

    proxies = None
    if proxy_url:
        proxies = {"http": proxy_url, "https": proxy_url}

    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en,zh;q=0.9",
    }

    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            r = _crequests.get(
                url,
                impersonate=impersonate,
                proxies=proxies,
                headers=headers,
                timeout=timeout,
            )
            # nitter 对 Chrome 指纹返回 200 + 0 字节；对 Firefox 返回真实 HTML
            # 偶发 429 rate limit：等一会重试
            if r.status_code == 429:
                time.sleep(2.0 * (attempt + 1))
                continue
            if r.status_code == 200 and len(r.content) > 500:
                return r.text
            # 0 字节 / 非 200：可能是反爬触发或临时故障，短暂重试
            time.sleep(0.5 * (attempt + 1))
        except Exception as e:
            last_exc = e
            time.sleep(0.5 * (attempt + 1))
    if last_exc:
        # 不抛，让上层走 mirror failover
        pass
    return None


class NitterCurlCffiSource(TweetSource):
    """Nitter HTML 抓取 source（curl_cffi + Firefox 指纹，绕 JA3 反爬）。

    与 NitterHtmlSource 共享 parser 逻辑（_NitterTimelineParser + _fallback_regex_parse），
    仅 HTTP 层换为 curl_cffi（impersonate=firefox133）。
    """

    name = "nitter_curl_cffi"

    def __init__(self, config):
        super().__init__(config)
        if not _HAS_CURL_CFFI:
            raise ImportError(
                "curl_cffi 未安装。Nitter 的 JA3 反爬要求用 curl_cffi 模仿 Firefox 指纹。\n"
                "安装命令：pip install curl_cffi\n"
                "或在 config.toml 切换 active_source = \"nitter_html\"（仅本地 urllib，"
                "沙箱/反爬环境将拿不到数据）"
            )
        self.mirrors = config.get("mirrors", ["https://nitter.net"])
        self.max_pages = config.get("max_pages", 2)
        self.timeout = config.get("request_timeout", 20)
        self.impersonate = config.get("impersonate", _DEFAULT_IMPERSONATE)
        # 代理 URL：config 优先，否则读环境变量 HTTPS_PROXY/HTTP_PROXY（小写也读）
        # 形如 "http://127.0.0.1:7897"。空字符串/None 表示直连
        self.proxy_url = (
            config.get("proxy_url")
            or os.environ.get("HTTPS_PROXY")
            or os.environ.get("https_proxy")
            or os.environ.get("HTTP_PROXY")
            or os.environ.get("http_proxy")
            or None
        )
        # 每个 KOL 抓取后的间隔（秒），缓解 nitter rate limit
        self.request_interval = float(config.get("request_interval", 1.0))

    def fetch_recent(self, handle, max_results, days_window):
        handle = handle.lstrip("@")
        fetched_at = datetime.now(_TZ_LOCAL)
        tweets = []
        seen_ids = set()
        used_mirror = None
        cursor = None
        error = None
        parsed_total = 0  # 解析出的推文总数（窗口过滤前），用于区分「没发推」和「抓取失败」

        for page in range(self.max_pages):
            html_text = None
            for mirror in self.mirrors:
                html_text = _fetch_html_curl_cffi(
                    mirror, handle, self.timeout, self.impersonate,
                    self.proxy_url, cursor,
                )
                if html_text and ("timeline" in html_text or _STATUS_RE.search(html_text)):
                    used_mirror = mirror
                    break
                time.sleep(0.3)
            if not html_text:
                error = f"all mirrors failed for {handle} (page {page})"
                break
            if not used_mirror:
                used_mirror = self.mirrors[0]

            # 解析（复用 nitter_html 的 parser）
            parser = _NitterTimelineParser(handle)
            try:
                parser.feed(html_text)
                page_tweets = parser.tweets
            except Exception:
                page_tweets = []
            if not page_tweets:
                page_tweets = _fallback_regex_parse(html_text, handle, fetched_at, used_mirror)
            parsed_total += len(page_tweets)

            # 后处理：补全 url、created_at
            for t in page_tweets:
                if t["id"] in seen_ids:
                    continue
                seen_ids.add(t["id"])
                # url：parser 不存（nitter 返回相对路径），外层用 mirror 拼
                if not t.get("url"):
                    t["url"] = f"{used_mirror.rstrip('/')}/{handle}/status/{t['id']}"
                if t.get("created_at"):
                    t["created_at"] = _parse_created_at(t["created_at"], fetched_at)
                else:
                    t["created_at"] = None
                tweets.append(t)
                if len(tweets) >= max_results:
                    break

            # 时间窗口过滤
            if days_window and days_window > 0:
                cutoff = fetched_at - timedelta(days=days_window)
                tweets = [t for t in tweets if not t.get("created_at") or _within_window(t["created_at"], cutoff)]

            if len(tweets) >= max_results:
                break
            # 翻页 cursor
            cursor = parser.cursor
            if not cursor:
                import re
                more_m = re.search(r'href="[^"]*cursor=([^&"]+)', html_text)
                if more_m:
                    cursor = urllib.parse.unquote(more_m.group(1))
            if not cursor:
                break
            time.sleep(self.request_interval)

        tweets = tweets[:max_results]
        if not tweets and not error:
            if parsed_total:
                error = f"no tweets in last {days_window}d for {handle} (parsed {parsed_total}, all older)"
            else:
                error = f"no tweets found for {handle}"
        return {"ok": bool(tweets), "tweets": tweets, "error": error}
