#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Batch-fetch X user info (followers, name, bio) via fxtwitter API.

Output: <项目根>/data/raw/followers_raw.json
"""
import json, time, urllib.request, sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = PROJECT_ROOT / "data" / "raw" / "followers_raw.json"

# Candidate handles: crypto + US stock Chinese KOLs
HANDLES = [
    # --- 知名加密人物/机构 ---
    "cz_binance", "heyibinance", "justinsuntron", "lixiaolai",
    "shenyongcrypto", "bitfish1", "maomao_okc", "jiangzhuoer",
    "zhaodong1982", "winterwinter", "wangfeng_0129", "wangfeng_0128",
    # --- 加密媒体/机构号 ---
    "wublockchain", "TheBlockBeats", "PANewsLab", "OdailyChina",
    "TechFlowPost", "Foresight_News", "ChainCatcher_", "8btc_news",
    "binancezh", "bitgetzh", "okxchinese",
    # --- Biteye 华语KOL榜单 ---
    "KuiGas", "Ice_Frog666666", "wenxue600", "ZF_lab", "WY_mask",
    "JiamigouCn", "bclaobai", "hebi555", "sanyi_eth_", "Greta0086",
    "thankUcrypto", "xiaomucrypto", "dotyyds1234", "DekuKing1",
    "hexiecs", "daidaibtc", "Vida_BWE", "CycleStudies",
    "butaidongjiaoyi", "BTC_Alert_", "cmdefi", "Luoyaoyuan1",
    "ZKSgu", "mrblocktw", "0xanonnnn", "ViNc2453", "Super4DeFi",
    "22333D", "RaccoonHKG", "mindaoyang", "BiteyeCN", "0xKevin00",
    "xingxingjun8888", "tmel0211", "0xNing0x", "alacheng",
    "0xjacobzhao", "nake13", "ZaggyGoKrazy", "starzqeth",
    "bocaibocai_", "KiwiCryptoBig", "Honglin_lawyer", "Wuhuoqiu",
    "DeFiTeddy2020", "punk8185", "unaiyang", "Rocky_Bitcoin",
    "mscryptojiayi", "_FORAB", "Alvin0617", "BTW0205",
    "CryptoPainter_X", "EnHeng456", "0xBeyondLee",
    # --- 美股中文KOL (Biteye 美股50人榜单中的中文账号) ---
    "0xxsmart", "_wmoon", "amy6tina", "bboczeng", "bitfool1",
    "blockchainrese6", "btcbears", "diaomao2023", "doctormbitcoin",
    "hibtc37", "jackli727", "junshao_666", "kelseyweb3vc",
    "lianyanshe", "oragnes", "qinbafrank", "shawnchen_eth",
    "ssslumdunk", "tj_research", "xiaomustock", "xingpt", "yiqifacai",
    # --- 其他知名美股/投资中文KOL ---
    "lidangzzz", "svwang1", "svwang", "wallstreetcn", "chendatouzi",
]

def fetch(handle):
    url = f"https://api.fxtwitter.com/{handle}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
        if data.get("code") != 200 or "user" not in data:
            return {"handle": handle, "error": data.get("message", "no user")}
        u = data["user"]
        return {
            "handle": handle,
            "name": u.get("name", ""),
            "screen_name": u.get("screen_name", handle),
            "followers": u.get("followers"),
            "following": u.get("following"),
            "tweets": u.get("tweets"),
            "joined": u.get("joined"),
            "bio": u.get("description", ""),
            "verified": (u.get("verification") or {}).get("verified", False),
            "url": u.get("url", ""),
        }
    except Exception as e:
        return {"handle": handle, "error": str(e)}

results = []
for i, h in enumerate(HANDLES):
    r = fetch(h)
    results.append(r)
    print(f"[{i+1}/{len(HANDLES)}] {h}: followers={r.get('followers')} name={r.get('name','')[:30]} err={r.get('error','')}", flush=True)
    time.sleep(0.6)

OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
with open(OUT_PATH, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

ok = [r for r in results if "followers" in r and r["followers"] is not None]
ok.sort(key=lambda r: -r["followers"])
print("\n=== >=20k followers ===")
for r in ok:
    if r["followers"] >= 20000:
        print(f"{r['followers']:>10,}  @{r['screen_name']:<22} {r['name'][:40]}")
print(f"\nTotal fetched OK: {len(ok)}/{len(HANDLES)}")
