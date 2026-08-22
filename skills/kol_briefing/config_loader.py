#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""配置加载（TOML）。Python 3.11+ 用 tomllib，旧版用兼容 fallback。

被 scripts/collect_tweets.py 与 scripts/prep_briefing_input.py 共用。
"""


def load_config(config_path):
    """读取 TOML 配置文件，返回 dict。"""
    text = config_path.read_text(encoding="utf-8")
    try:
        import tomllib
        return tomllib.loads(text)
    except ImportError:
        return _toml_fallback(text)


def _toml_fallback(text):
    """极简 TOML 解析 fallback（Python <3.11 无 tomllib 时用）。

    仅支持本项目用到的：section、key=value、字符串/数字/布尔/数组（含多行数组）。
    不支持多行字符串与复杂转义。
    """
    # 先把多行数组合并为单行：当某行含 [ 但未闭合 ]，持续拼接后续行直到闭合
    collapsed = []
    buf = ""
    depth = 0
    for raw in text.splitlines():
        line = raw
        in_str = False
        for ch in line:
            if ch == '"':
                in_str = not in_str
            elif not in_str:
                if ch == "[":
                    depth += 1
                elif ch == "]":
                    depth -= 1
        buf += " " + line.strip() if buf else line.strip()
        if depth <= 0:
            collapsed.append(buf)
            buf = ""
            depth = max(depth, 0)
    if buf:
        collapsed.append(buf)

    config = {}
    cur = config
    for raw in collapsed:
        in_str = False
        cut = len(raw)
        for i, ch in enumerate(raw):
            if ch == '"':
                in_str = not in_str
            elif ch == "#" and not in_str:
                cut = i
                break
        line = raw[:cut].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]") and "=" not in line:
            section = line[1:-1].strip()
            parts = section.split(".")
            cur = config
            for p in parts:
                cur = cur.setdefault(p, {})
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip().strip('"')
        val = val.strip()
        if val.startswith('"') and val.endswith('"'):
            v = val[1:-1]
        elif val.startswith("[") and val.endswith("]"):
            inner = val[1:-1]
            v = [
                x.strip().strip('"')
                for x in inner.split(",")
                if x.strip()
            ]
        elif val.lower() in ("true", "false"):
            v = val.lower() == "true"
        else:
            try:
                v = int(val)
            except ValueError:
                try:
                    v = float(val)
                except ValueError:
                    v = val
        cur[key] = v
    return config
