#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抓取所有 KOL 头像 URL，输出到 data/kol_avatars.json。

为什么单独一个脚本：
  - 头像 URL 不随推文变化，只需抓一次后定期刷新
  - 不污染 collect_tweets.py 的推文流水
  - 前端可直接 fetch kol_avatars.json 按 handle 查找

数据来源：Nitter 个人主页 HTML 中的 <img> 标签，
  URL 形如：
    /pic/https%3A%2F%2Fpbs.twimg.com%2Fprofile_images%2F...%2F<file>.jpg
  解码后即原始 Twitter 头像 URL，前端可直连 Twitter 加载（需代理），
  或前端拼接成 nitter 镜像 URL（https://nitter.net/pic/...）走 nitter 代理。

输出格式：
  {
    "cz_binance": {
      "twitter": "https://pbs.twimg.com/profile_images/xxx/yyy.jpg",
      "nitter": "https://nitter.net/pic/https%3A%2F%2Fpbs.twimg.com%2Fprofile_images%2Fxxx%2Fyyy.jpg",
      "fetched_at": "2026-08-22T17:30:00+08:00"
    },
    ...
  }

用法：
  HTTPS_PROXY=http://127.0.0.1:7897 python3 scripts/fetch_avatars.py
  HTTPS_PROXY=http://127.0.0.1:7897 python3 scripts/fetch_avatars.py --handle cz_binance  # 单个测试
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.parse
from datetime import datetime, timedelta, timezone

# 项目根目录（脚本位于 bitkol/scripts/）
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "skills", "kol_briefing"))

try:
    from curl_cffi import requests as _crequests
except ImportError:
    print("[ERROR] curl_cffi 未安装，请先：pip install curl_cffi", file=sys.stderr)
    sys.exit(1)

_TZ_LOCAL = timezone(timedelta(hours=8))

# KOL 名单
KOL_LIST = os.path.join(ROOT, "data", "x_kol_list.jsonl")
AVATARS_OUT = os.path.join(ROOT, "data", "kol_avatars.json")

# Nitter 镜像（与 config.toml 保持一致，第一个为主）
MIRRORS = [
    "https://nitter.net",
    "https://nitter.poast.org",
    "https://nitter.privacydev.net",
]

# 头像 URL 正则：nitter 把外部图片代理成 /pic/<url-encoded>
# 优先匹配 profile_images，避免误取 banner
_AVATAR_RE = re.compile(
    r'/pic/(https?%3A%2F%2Fpbs\.twimg\.com%2Fprofile_images%2F[^"\']+)',
    re.IGNORECASE,
)


def _proxy_dict():
    """从环境变量构造 curl_cffi 代理参数。"""
    p = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") \
        or os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
    if not p:
        return None
    return {"http": p, "https": p}


def _fetch_avatar(handle, mirror, timeout=15):
    """抓单个 handle 的头像，返回 twitter URL 或 None。"""
    url = f"{mirror.rstrip('/')}/{handle}"
    proxies = _proxy_dict()
    try:
        r = _crequests.get(
            url,
            impersonate="firefox133",
            proxies=proxies,
            timeout=timeout,
            headers={"Accept": "text/html", "Accept-Language": "en,zh;q=0.9"},
        )
    except Exception as e:
        return None, f"请求失败: {type(e).__name__}: {e}"

    if r.status_code != 200 or not r.text:
        return None, f"HTTP {r.status_code} len={len(r.text or '')}"

    m = _AVATAR_RE.search(r.text)
    if not m:
        return None, "未匹配到头像 img"
    encoded = m.group(1)
    try:
        twitter_url = urllib.parse.unquote(encoded)
    except Exception:
        return None, "URL 解码失败"
    return {
        "twitter": twitter_url,
        "nitter": f"{mirror.rstrip('/')}/pic/{encoded}",
        "fetched_at": datetime.now(_TZ_LOCAL).isoformat(timespec="seconds"),
    }, None


def load_kols():
    """加载 KOL 名单，返回 [{handle, name, ...}, ...]。"""
    if not os.path.exists(KOL_LIST):
        print(f"[ERROR] KOL 名单不存在: {KOL_LIST}", file=sys.stderr)
        sys.exit(1)
    kols = []
    with open(KOL_LIST, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                kols.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return kols


def load_existing():
    """加载已存在的头像缓存（增量抓取时跳过已有 handle）。"""
    if not os.path.exists(AVATARS_OUT):
        return {}
    try:
        with open(AVATARS_OUT, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def main():
    ap = argparse.ArgumentParser(description="抓取所有 KOL 头像 URL")
    ap.add_argument("--handle", help="只抓单个 handle（调试用）")
    ap.add_argument("--force", action="store_true", help="强制重新抓取所有 handle")
    ap.add_argument("--mirror", default=None, help="指定单镜像（默认按 MIRRORS 顺序尝试）")
    args = ap.parse_args()

    kols = load_kols()
    if args.handle:
        kols = [k for k in kols if k["handle"].lower() == args.handle.lower()]
        if not kols:
            print(f"[ERROR] 未在 KOL 名单中找到 handle: {args.handle}", file=sys.stderr)
            sys.exit(1)

    # force 模式只影响「是否跳过已有 handle」，不能清空整个缓存（否则会丢失其他 KOL 的头像）
    existing = load_existing()
    result = dict(existing)
    mirrors = [args.mirror] if args.mirror else MIRRORS

    print(f"[load] {len(kols)} KOLs, 已有头像 {len(existing)}, force={args.force}, 镜像: {mirrors}")

    failed = []
    for i, k in enumerate(kols, 1):
        handle = k["handle"]
        # 非 force 时跳过已有；force 时不跳过（重新抓）
        if not args.force and handle in existing and existing[handle].get("twitter"):
            print(f"[{i}/{len(kols)}] @{handle} 已有，跳过")
            continue

        avatar = None
        err = None
        for mirror in mirrors:
            avatar, err = _fetch_avatar(handle, mirror)
            if avatar:
                break
            time.sleep(0.5)

        if avatar:
            result[handle] = avatar
            print(f"[{i}/{len(kols)}] @{handle} ({k.get('name','')}) OK -> {avatar['twitter'][:80]}...")
        else:
            failed.append(handle)
            print(f"[{i}/{len(kols)}] @{handle} FAIL: {err}")
        time.sleep(1.0)  # 缓解 nitter rate limit

    # 写入
    os.makedirs(os.path.dirname(AVATARS_OUT), exist_ok=True)
    with open(AVATARS_OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n[done] 写入 {AVATARS_OUT}, 共 {len(result)} 个头像")
    if failed:
        print(f"[failed] {len(failed)}: {', '.join(failed)}")


if __name__ == "__main__":
    main()
