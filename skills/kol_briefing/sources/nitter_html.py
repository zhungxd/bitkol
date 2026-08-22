#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nitter HTML 抓取 source（默认，已验证 nitter.net 可用）。

实测：https://nitter.net/<handle> 返回真实推文 HTML（含正文、互动数、相对时间、status 链接）。
nitter.net 的 RSS 端点已禁用，故默认走 HTML。

解析策略（resilient）：
  - 主路径：用 html.parser.HTMLParser 遍历，按 class="timeline-item" 切分推文块
  - 兜底：正则提取所有 status 链接（/<handle>/status/<id>），最稳定信号
  - 每条推文提取：id / text / created_at / url / public_metrics?
"""
import re
import time
import urllib.request
import urllib.parse
import html as html_module
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser

from . import TweetSource

# 时区
_TZ_LOCAL = timezone(timedelta(hours=8))  # 东八区

# 推文 status 链接正则：/<handle>/status/<digits>
_STATUS_RE = re.compile(r'/status/(\d{5,})', re.IGNORECASE)
# 互动数正则（仅匹配纯数字，可含千位逗号）
_INT_RE = re.compile(r'(\d[\d,]*)')


class _NitterTimelineParser(HTMLParser):
    """解析 nitter 主页 HTML，提取推文列表。

    nitter 主页结构（各镜像可能略有差异，本解析器做容错）：
      <div class="timeline-item">
        <div class="tweet-body">
          <div class="tweet-content ...">推文正文</div>
          ...
          <div class="tweet-stats">
            <span class="icon-comment"> 47 </span>
            <span class="icon-retweet"> 21 </span>
            <span class="icon-heart"> 14,659 </span>
          </div>
          <a class="tweet-date" title="Aug 20, 2026 ...">2h</a>
        </div>
      </div>
      ...
      <a class="show-more" href="/<handle>?cursor=...">Load more</a>
    """

    # 互动数 icon class → metric 名
    _METRIC_ICONS = {
        "icon-comment": "replies",
        "icon-retweet": "retweets",
        "icon-heart": "likes",
    }

    def __init__(self, handle):
        super().__init__(convert_charrefs=True)
        self.handle = handle.lower()
        self.tweets = []
        self.cursor = None  # Load more 链接的 cursor

        # 解析状态
        self._in_item = False          # 是否在 timeline-item 内
        self._item_div_depth = 0        # timeline-item 内 div 嵌套深度（用于判定 item 结束）
        self._cur = None                # 当前推文 dict
        self._capture = None            # None | "content" | "tweet_stat" | "tweet_date"
        self._capture_tag = None        # 开启 capture 的 tag（用于 endtag 时判断外层关闭）
        self._capture_depth = 0         # 同 _capture_tag 嵌套深度，endtag 时递减到 -1 才 flush
        self._metric_name = None        # 当前收集的 metric 名
        self._buf = []                  # 当前捕获的文本片段
        self._stats = {}                # 当前 item 的互动数
        self._date_title = None         # tweet-date 内层 a 的 title（绝对时间）
        self._date_text = None          # tweet-date 文本（相对时间，如 "7h"）

    def _reset_item(self):
        self._cur = {}
        self._stats = {}
        self._date_title = None
        self._date_text = None
        self._capture = None
        self._capture_tag = None
        self._capture_depth = 0
        self._metric_name = None
        self._buf = []

    def _start_capture(self, mode, tag):
        """开启新的 capture 模式，记录开启它的 tag。"""
        self._flush_capture()
        self._capture = mode
        self._capture_tag = tag
        self._capture_depth = 0
        self._buf = []

    def _flush_capture(self):
        """结束当前捕获，把 _buf 写入对应字段。"""
        if self._capture is None:
            return
        text = "".join(self._buf).strip()
        self._buf = []
        mode = self._capture
        self._capture = None
        self._capture_tag = None
        self._capture_depth = 0
        if mode == "content":
            if self._cur is not None and "text" not in self._cur:
                self._cur["text"] = text
        elif mode == "tweet_stat":
            # 数值在外层 tweet-stat span 文本里（如 "13"）
            if self._metric_name and self._cur is not None:
                m = _INT_RE.search(text)
                if m:
                    try:
                        self._stats[self._metric_name] = int(m.group(1).replace(",", ""))
                    except ValueError:
                        pass
            self._metric_name = None
        elif mode == "tweet_date":
            # 优先用 title（绝对时间），否则用文本（相对时间）
            if self._cur is not None and "created_at" not in self._cur:
                self._cur["created_at"] = self._date_title or text or None
            self._date_title = None
            self._date_text = None

    def handle_starttag(self, tag, attrs):
        attrs_d = dict(attrs)
        cls = attrs_d.get("class", "")

        # capture 模式下，同 _capture_tag 嵌套（如 content div 内还有 div）
        # 必须先递增 depth，避免 endtag 误判为外层关闭
        if self._capture is not None and tag == self._capture_tag:
            self._capture_depth += 1

        # timeline-item 开始
        if "timeline-item" in cls:
            self._in_item = True
            self._item_div_depth = 0
            self._reset_item()
            return

        # Load more 链接（cursor 翻页）
        if "show-more" in cls:
            href = attrs_d.get("href", "")
            cursor_m = re.search(r'cursor=([^&"]+)', href)
            if cursor_m:
                self.cursor = urllib.parse.unquote(cursor_m.group(1))
            return

        if not self._in_item:
            return

        # div 嵌套深度（仅对 div 计，用于判定 item 结束）
        if tag == "div":
            self._item_div_depth += 1

        # 推文正文容器
        if "tweet-content" in cls:
            self._start_capture("content", tag)
            return

        # status 链接（最可靠：id + url）
        href = attrs_d.get("href", "")
        m = _STATUS_RE.search(href)
        if m and self._cur is not None:
            tid = m.group(1)
            if "id" not in self._cur:
                self._cur["id"] = tid
            # URL 由外层 fetch_recent 用 mirror 拼接，parser 不存 url

        # tweet-stat 容器（外层 span，nitter 当前结构）：
        #   <span class="tweet-stat"><div class="icon-container">
        #     <span class="icon-comment"></span> 13
        #   </div></span>
        if tag == "span" and "tweet-stat" in cls:
            self._start_capture("tweet_stat", tag)
            return

        # 内层 icon-X span（在 tweet_stat capture 模式下，设置 metric_name）
        if self._capture == "tweet_stat":
            for icon_cls, metric in self._METRIC_ICONS.items():
                if icon_cls in cls:
                    self._metric_name = metric
                    return

        # tweet-date 容器（外层 span）：
        #   <span class="tweet-date"><a title="Aug 22, 2026 · 1:04 AM UTC">7h</a></span>
        if tag == "span" and "tweet-date" in cls:
            self._start_capture("tweet_date", tag)
            return

        # tweet-date 内层 a 的 title 属性（绝对时间）
        if self._capture == "tweet_date" and tag == "a":
            t = attrs_d.get("title")
            if t:
                self._date_title = t

        # 兼容旧结构：<a class="tweet-date" title="...">
        if tag == "a" and "tweet-date" in cls:
            t = attrs_d.get("title")
            if t and self._cur is not None and "created_at" not in self._cur:
                self._cur["created_at"] = t

        # <time datetime=...>
        if tag == "time" and attrs_d.get("datetime"):
            if self._cur is not None and "created_at" not in self._cur:
                self._cur["created_at"] = attrs_d["datetime"]

    def handle_endtag(self, tag):
        if not self._in_item:
            return
        # capture 模式下的嵌套控制：
        #   - 当前 tag == 开启 capture 的 tag：depth 递减，回到 -1 时表示外层关闭，flush
        #   - 当前 tag != _capture_tag：忽略（不 flush），让 capture 继续
        if self._capture is not None and tag == self._capture_tag:
            self._capture_depth -= 1
            if self._capture_depth < 0:
                self._flush_capture()
        # div 深度递减，判定 item 结束
        if tag == "div":
            self._item_div_depth -= 1
            if self._item_div_depth <= 0:
                self._in_item = False
                self._flush_capture()
                if self._cur and "id" in self._cur:
                    if self._stats:
                        self._cur["public_metrics"] = dict(self._stats)
                    if "created_at" not in self._cur and self._date_title:
                        self._cur["created_at"] = self._date_title
                    if "url" not in self._cur:
                        self._cur["url"] = None  # 外层 fetch_recent 用 mirror 拼
                    if "text" not in self._cur:
                        self._cur["text"] = ""
                    self.tweets.append(self._cur)
                self._cur = None

    def handle_data(self, data):
        if self._capture is not None:
            self._buf.append(data)

    def handle_startendtag(self, tag, attrs):
        # <br/> 等：在 content 模式下插入换行
        if self._capture == "content" and tag == "br":
            self._buf.append("\n")


def _fetch_html(mirror, handle, timeout, cursor=None):
    """请求 nitter 镜像的 handle 页面，返回 HTML 文本或 None。"""
    url = f"{mirror.rstrip('/')}/{handle}"
    if cursor:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}cursor={urllib.parse.quote(cursor)}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en,zh;q=0.9",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def _parse_created_at(value, fetched_at):
    """nitter 时间字段可能是绝对（ISO/datetime title）或相对（'2h','1d'），统一转 ISO 字符串。"""
    if not value:
        return None
    value = value.strip()
    # 相对时间：2h, 1d, 3m, 1w
    m = re.match(r'^(\d+)\s*([smhdw])$', value, re.IGNORECASE)
    if m and fetched_at:
        n = int(m.group(1))
        unit = m.group(2).lower()
        deltas = {
            "s": timedelta(seconds=n),
            "m": timedelta(minutes=n),
            "h": timedelta(hours=n),
            "d": timedelta(days=n),
            "w": timedelta(weeks=n),
        }
        dt = fetched_at - deltas.get(unit, timedelta(0))
        return dt.isoformat()
    # 绝对时间格式（nitter 实际格式）：
    #   "Aug 20, 2026 · 1:04 AM UTC" → ISO（保留时分秒）
    #   "Aug 20, 2026 · 08:30:00"    → ISO（24h 制）
    #   "Aug 20, 2026"               → ISO 00:00:00
    #   "2026-08-20T08:30:00+00:00"  → ISO（已是 ISO）
    # 把 " · " 替换为空格，去掉 " UTC" 后缀，统一用空格分隔
    value_clean = value.replace(" · ", " ").replace("  ", " ")
    # 12h 制："Aug 20, 2026 1:04 AM UTC" → 去掉 UTC
    value_clean = re.sub(r'\s+UTC\s*$', '', value_clean)
    fmts = (
        "%b %d, %Y %I:%M %p",       # 12h: "Aug 20, 2026 1:04 AM"
        "%b %d, %Y %H:%M:%S",       # 24h: "Aug 20, 2026 08:30:00"
        "%b %d, %Y %H:%M",          # 24h 短: "Aug 20, 2026 08:30"
        "%b %d, %Y",                # 仅日期
        "%Y-%m-%dT%H:%M:%S%z",      # ISO with tz
        "%Y-%m-%d %H:%M:%S",        # ISO no tz
        "%Y-%m-%d",                 # 仅日期 ISO
    )
    for fmt in fmts:
        try:
            dt = datetime.strptime(value_clean, fmt)
            # nitter UTC 时间统一标 +00:00，便于跨 KOL 比较
            if fmt in ("%b %d, %Y %I:%M %p", "%b %d, %Y %H:%M:%S", "%b %d, %Y %H:%M", "%b %d, %Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()
        except ValueError:
            continue
    return value  # 原样保留，Agent 不依赖此字段做权重


def _fallback_regex_parse(html_text, handle, fetched_at, mirror):
    """正则兜底解析：当 HTMLParser 提取失败时，用正则提取所有 status 链接对应的推文。

    这是最稳定的信号——优先提取 id 和 url，正文尽量从 tweet-content 提取。
    """
    tweets = []
    seen_ids = set()
    # 找所有 timeline-item 片段
    items = re.split(r'class="timeline-item', html_text)
    for chunk in items[1:]:  # 跳过第一个（页面前导）
        m = _STATUS_RE.search(chunk[:5000])
        if not m:
            continue
        tid = m.group(1)
        if tid in seen_ids:
            continue
        seen_ids.add(tid)
        # 尝试提取正文
        text_match = re.search(r'class="[^"]*tweet-content[^"]*"[^>]*>(.*?)</div>', chunk, re.DOTALL)
        text = ""
        if text_match:
            text = html_module.unescape(re.sub(r'<[^>]+>', '', text_match.group(1))).strip()
        # 时间
        created = None
        time_m = re.search(r'<time[^>]*datetime="([^"]+)"', chunk) or re.search(r'title="([^"]+)"[^>]*class="tweet-date"', chunk)
        if time_m:
            created = _parse_created_at(time_m.group(1), fetched_at)
        url = f"{mirror.rstrip('/')}/{handle}/status/{tid}"
        tweets.append({
            "id": tid,
            "text": text,
            "url": url,
            "created_at": created,
        })
    return tweets


class NitterHtmlSource(TweetSource):
    """Nitter HTML 抓取 source。"""

    name = "nitter_html"

    def __init__(self, config):
        super().__init__(config)
        self.mirrors = config.get("mirrors", ["https://nitter.net"])
        self.max_pages = config.get("max_pages", 2)
        self.timeout = config.get("request_timeout", 10)

    def fetch_recent(self, handle, max_results, days_window):
        handle = handle.lstrip("@")
        fetched_at = datetime.now(_TZ_LOCAL)
        tweets = []
        seen_ids = set()
        used_mirror = None
        cursor = None
        error = None

        for page in range(self.max_pages):
            # 镜像 failover：第一页选定一个可用镜像，后续页沿用
            html_text = None
            for mirror in self.mirrors:
                html_text = _fetch_html(mirror, handle, self.timeout, cursor)
                if html_text and ("timeline" in html_text or _STATUS_RE.search(html_text)):
                    used_mirror = mirror
                    break
                time.sleep(0.3)
            if not html_text:
                error = f"all mirrors failed for {handle} (page {page})"
                break
            if not used_mirror:
                used_mirror = self.mirrors[0]

            # 解析
            parser = _NitterTimelineParser(handle)
            try:
                parser.feed(html_text)
                page_tweets = parser.tweets
            except Exception:
                page_tweets = []
            if not page_tweets:
                page_tweets = _fallback_regex_parse(html_text, handle, fetched_at, used_mirror)

            # 后处理：补全 url、created_at
            for t in page_tweets:
                if t["id"] in seen_ids:
                    continue
                seen_ids.add(t["id"])
                # url：parser 不存，外层用 mirror 拼
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
                # 兜底：正则找 Load more 链接
                more_m = re.search(r'href="[^"]*cursor=([^&"]+)', html_text)
                if more_m:
                    cursor = urllib.parse.unquote(more_m.group(1))
            if not cursor:
                break
            time.sleep(0.5)

        # 限制到 max_results
        tweets = tweets[:max_results]
        if not tweets and not error:
            error = f"no tweets found for {handle}"
        return {"ok": bool(tweets), "tweets": tweets, "error": error}


def _within_window(created_at_str, cutoff):
    """粗略判断 created_at 是否在窗口内（容忍解析失败，默认 True）。"""
    if not created_at_str:
        return True  # 无法解析则保留
    try:
        s = created_at_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_TZ_LOCAL)
        return dt >= cutoff
    except Exception:
        return True
