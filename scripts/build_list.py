#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build final KOL list (JSONL + Markdown) from fetched follower data.

Input : <项目根>/data/raw/followers_raw.json, <项目根>/data/raw/extra_raw.jsonl
Output: <项目根>/data/x_kol_list.jsonl, <项目根>/data/x_kol_list.md
"""
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
DATA_DIR = PROJECT_ROOT / "data"

FETCH_DATE = "2026-08-22"

# Load follower data
raw = json.load(open(RAW_DIR / "followers_raw.json", encoding="utf-8"))
extra = []
for line in open(RAW_DIR / "extra_raw.jsonl", encoding="utf-8"):
    line = line.strip()
    if line:
        try:
            d = json.loads(line)
            if d.get("code") == 200 and "user" in d:
                u = d["user"]
                extra.append({
                    "handle": u.get("screen_name", "").lower(),
                    "name": u.get("name", ""),
                    "screen_name": u.get("screen_name", ""),
                    "followers": u.get("followers"),
                    "bio": u.get("description", ""),
                    "verified": (u.get("verification") or {}).get("verified", False),
                    "url": u.get("url", ""),
                })
        except Exception:
            pass

by_handle = {}
for r in raw:
    if r.get("followers") is not None:
        by_handle[r["handle"].lower()] = r
for r in extra:
    by_handle[r["handle"].lower()] = r

# Curated metadata: handle -> (中文名, category, type, track, focus, source, note)
# category: crypto | us_stock | both
CURATED = [
    # ---- 加密 · 知名人物 ----
    ("cz_binance", "CZ 赵长鹏", "crypto", "个人-创始人", "交易所", "币安创始人，加密行业最具影响力的华人领袖", "知名人物", ""),
    ("justinsuntron", "孙宇晨", "crypto", "个人-创始人", "公链/项目", "TRON 波场创始人，活跃的加密意见领袖", "知名人物", ""),
    ("heyibinance", "何一", "crypto", "个人-创始人", "交易所", "币安联合创始人，币圈'一姐'", "知名人物", ""),
    ("bitfish", "神鱼", "crypto", "个人-创始人", "矿业/托管", "F2Pool、Cobo 联合创始人，资深矿工", "知名人物", "handle 为 @bitfish（DiscusFish）"),
    ("doveywan", "万卉 Dovey Wan", "crypto", "个人-投资人", "VC/宏观", "Primitive Ventures 创始合伙人，知名女性加密投资人", "知名人物", ""),
    ("myantokengeek", "孟岩", "crypto", "个人-研究者", "技术/通证经济", "区块链技术布道者、通证经济研究者", "知名人物", ""),
    ("jiangzhuoer", "江卓尔", "crypto", "个人-矿工/投资人", "矿业/周期", "BTC.TOP 创始人，知名比特币投资者", "知名人物", ""),
    ("0xtodd", "0xTodd", "crypto", "个人-投研", "以太坊/策略", "知名加密投研，热衷研究，Long BTC", "知名人物", ""),
    ("hebi555", "何币", "crypto", "个人-投研", "空投/交易", "华语头部投研 KOL，影响力大", "Biteye华语KOL榜", ""),
    ("sanyi_eth_", "sanyi.eth", "crypto", "个人-交易", "交易", "华语交易赛道头部 KOL", "Biteye华语KOL榜", ""),
    ("thankucrypto", "allincrypto 熬鹰资本", "crypto", "个人-交易", "交易", "交易赛道头部 KOL", "Biteye华语KOL榜", ""),
    ("greta0086", "Greta008", "crypto", "个人-空投/研究", "空投", "空投赛道头部 KOL", "Biteye华语KOL榜", ""),
    ("rocky_bitcoin", "Rocky", "crypto", "个人-研究", "RWA", "RWA 赛道 KOL", "Biteye华语KOL榜", ""),
    ("_forab", "AB Kuai.Dong", "crypto", "个人-综合", "综合", "币安广场签约 KOL，华语影响力排名 44", "Biteye华语KOL榜", ""),
    ("wenxue600", "链上达人", "crypto", "个人-空投", "空投", "空投赛道 KOL，华语影响力榜 120 名", "Biteye华语KOL榜", ""),
    ("enheng456", "EnHeng 嗯哼", "crypto", "个人-交易", "BNB/交易", "BNB 信仰者，实盘分享", "Biteye华语KOL榜", ""),
    ("kuigas", "丰密", "crypto", "个人-空投", "空投", "33 DAO、Kui Club 成员，空投赛道 KOL", "Biteye华语KOL榜", ""),
    ("zf_lab", "追风Lab.eth", "crypto", "个人-空投", "空投", "空投赛道 KOL", "Biteye华语KOL榜", ""),
    ("dekuking1", "0x易经", "crypto", "个人-交易", "交易", "交易赛道 KOL", "Biteye华语KOL榜", ""),
    ("ice_frog666666", "冰蛙", "crypto", "个人-空投", "空投", "空投赛道 KOL", "Biteye华语KOL榜", ""),
    ("wy_mask", "无颜", "crypto", "个人-空投", "空投", "空投赛道 KOL", "Biteye华语KOL榜", ""),
    ("super4defi", "benmo.eth", "crypto", "个人-DeFi", "DeFi", "DeFi 赛道 KOL", "Biteye华语KOL榜", ""),
    ("hexiecs", "冷静冷静再冷静", "crypto", "个人-交易", "交易", "交易赛道 KOL", "Biteye华语KOL榜", ""),
    ("wangfeng_0128", "小隐新十年（Feng Wang）", "crypto", "个人-RWA", "RWA", "RWA 赛道 KOL", "Biteye华语KOL榜", ""),
    ("dotyyds1234", "憨巴龙王", "crypto", "个人-交易", "交易", "交易赛道 KOL", "Biteye华语KOL榜", ""),
    ("0xkevin00", "0xkevin", "crypto", "个人-AI", "AI", "AI 赛道 KOL", "Biteye华语KOL榜", ""),
    ("vida_bwe", "Vida", "crypto", "个人-交易", "交易", "交易赛道 KOL", "Biteye华语KOL榜", ""),
    ("wuhuoqiu", "Lao Bai", "crypto", "个人-RWA", "RWA/综合", "RWA 赛道 KOL，华语影响力榜", "Biteye华语KOL榜", ""),
    ("cyclestudies", "百万Eric", "crypto", "个人-交易", "交易", "Day Trader，交易赛道 KOL", "Biteye华语KOL榜", ""),
    ("mindaoyang", "Mindao", "crypto", "个人-DeFi", "DeFi/公链", "dForce 创始人，DeFi 研究者", "Biteye华语KOL榜", ""),
    ("defiteddy2020", "DeFi Teddy", "crypto", "个人-创始人", "RWA/DeFi", "Biteye/XHunt 创始人", "Biteye华语KOL榜", ""),
    ("tmel0211", "Haotian", "crypto", "个人-技术", "AI/技术科普", "硬核技术科普，Amber 顾问、IOSG 特邀研究员", "Biteye华语KOL榜", ""),
    ("daidaibtc", "带带带比特", "crypto", "个人-交易", "交易", "交易赛道 KOL", "Biteye华语KOL榜", ""),
    ("btc_alert_", "ALERT的会所", "crypto", "个人-交易", "交易", "交易赛道 KOL", "Biteye华语KOL榜", ""),
    ("nake13", "Zhixiong Pan", "crypto", "个人-AI", "AI", "AI 赛道 KOL", "Biteye华语KOL榜", ""),
    ("xingxingjun8888", "星星菌", "crypto", "个人-AI", "AI", "AI 赛道 KOL", "Biteye华语KOL榜", ""),
    ("0xbeyondlee", "解构师 Beyond", "crypto", "个人-可视化", "信息可视化", "信息可视化博主，华语影响力榜 89 名", "Biteye华语KOL榜", ""),
    ("raccoonhkg", "Raccoon Chan 小浣熊", "crypto", "个人-DeFi", "DeFi", "DeFi 赛道 KOL", "Biteye华语KOL榜", ""),
    ("butaidongjiaoyi", "如果我不懂", "crypto", "个人-交易", "交易", "交易赛道 KOL", "Biteye华语KOL榜", ""),
    ("0xning0x", "NingNing", "crypto", "个人-AI/研究", "AI/投研", "AI 赛道 KOL", "Biteye华语KOL榜", ""),
    ("mscryptojiayi", "jiayi 加一", "crypto", "个人-RWA", "RWA", "RWA 赛道 KOL", "Biteye华语KOL榜", ""),
    ("22333d", "3D 加密频道", "crypto", "个人-DeFi", "DeFi", "DeFi 赛道 KOL", "Biteye华语KOL榜", ""),
    ("bocaibocai_", "菠菜菠菜", "crypto", "个人-RWA", "RWA", "RWA 赛道 KOL", "Biteye华语KOL榜", ""),
    ("alvin0617", "alvin617.eth", "crypto", "个人-综合", "半导体/AI/ETF", "CryptoWesearch，加密+科技股交叉", "Biteye华语KOL榜", ""),
    ("alacheng", "头雁", "crypto", "个人-AI", "AI", "AI 赛道 KOL", "Biteye华语KOL榜", ""),
    ("bclaobai", "老白｜LaoBai", "crypto", "个人-空投", "空投", "空投赛道 KOL（粉丝略低于2万，接近门槛）", "Biteye华语KOL榜", "followers 19.8k，略低于2万"),
    # ---- 加密 · 媒体/官方 ----
    ("wublockchain", "吴说区块链", "crypto", "媒体", "深度报道", "中文加密深度媒体，行业影响力大", "知名媒体", ""),
    ("techflowpost", "TechFlow 深潮", "crypto", "媒体", "资讯/深度", "华语加密媒体", "知名媒体", ""),
    ("odailychina", "Odaily星球日报", "crypto", "媒体", "资讯/深度", "华语加密媒体", "知名媒体", ""),
    ("foresight_news", "Foresight News", "crypto", "媒体", "资讯/深度", "华语加密媒体（前瞻新闻）", "知名媒体", ""),
    ("chaincatcher_", "ChainCatcher", "crypto", "媒体", "资讯/深度", "华语加密媒体（链捕手）", "知名媒体", ""),
    ("biteyecn", "Biteye", "crypto", "媒体/研究", "投研", "华语加密投研媒体", "Biteye华语KOL榜", ""),
    ("jinsefinance", "金色财经", "crypto", "媒体", "资讯", "华语区块链媒体", "知名媒体", ""),
    ("chainfeeds", "ChainFeeds", "crypto", "媒体", "资讯聚合", "加密行业资讯聚合媒体", "知名媒体", ""),
    ("okxchinese", "OKX中文", "crypto", "官方", "交易所", "欧易 OKX 官方华语账号", "知名官方", ""),
    ("binancezh", "币安Binance华语", "crypto", "官方", "交易所", "币安官方华语账号", "知名官方", ""),
    ("imtokenofficial", "imToken", "crypto", "官方", "钱包", "imToken 钱包官方", "知名官方", ""),
    ("cobo_global", "Cobo", "crypto", "官方", "托管/钱包", "神鱼联合创立的托管与钱包基础设施", "知名官方", ""),
    ("f2pool", "f2pool 鱼池", "crypto", "官方", "矿池", "比特币矿池官方，2013 年成立", "知名官方", ""),
    # ---- 美股（含加密×美股交叉）----
    ("lidangzzz", "立党", "both", "个人-投资", "SP500/纳指/AI", "全网劝人买 SP500 和纳指 100 的代表性大 V", "知名人物", "加密与美股双覆盖"),
    ("svwang1", "硅谷王川", "us_stock", "个人-投资", "美股/宏观/科技", "知名美股投资自媒体，长文深度分析", "知名人物", "handle 为 @Svwang1"),
    ("bboczeng", "勃勃OC", "both", "个人-交易", "半导体/科技股", "半导体、芯片、大盘与交易机会", "Biteye美股50人榜", "加密背景，也谈美股"),
    ("xiaomustock", "川沐｜Trumoo", "both", "个人-投研", "财报/AI/半导体", "财报、估值、基本面、AI/半导体产业链", "Biteye美股50人榜+Biteye华语榜", "两个榜单均上榜"),
    ("qinbafrank", "qinbafrank", "us_stock", "个人-期权", "期权/AI算力", "期权、交易策略、AI 算力相关美股", "Biteye美股50人榜", ""),
    ("bitfool1", "比特傻", "both", "个人-基本面", "财报/半导体", "财报、估值、基本面、半导体机会", "Biteye美股50人榜", ""),
    ("blockchainrese6", "老陌", "us_stock", "个人-大盘", "大盘/ETF/半导体", "大盘、ETF、半导体、风险资产联动", "Biteye美股50人榜", ""),
    ("doctormbitcoin", "Bitcoin女博士", "us_stock", "个人-大盘", "大盘/ETF/科技股", "大盘、ETF、科技股、风险资产联动", "Biteye美股50人榜", ""),
    ("tj_research", "投资TALK君", "us_stock", "个人-财报", "财报/期权", "财报、估值、基本面、期权/交易策略", "Biteye美股50人榜", ""),
    ("lianyanshe", "链研社", "both", "个人-研究", "财报/期权/AI", "财报、估值、期权交易、AI 科技股", "Biteye美股50人榜", ""),
    ("oragnes", "比特币橙子Trader", "both", "个人-交易", "宏观/流动性", "宏观、流动性、大盘、加密相关美股", "Biteye美股50人榜", ""),
    ("xingpt", "XinGPT", "us_stock", "个人-研究", "AI/半导体", "AI 产业链、半导体周期，硬核数据流", "Biteye美股50人榜", ""),
    ("jackli727", "零下二度", "us_stock", "个人-宏观", "宏观/期权", "宏观、流动性、期权、交易策略", "Biteye美股50人榜", ""),
    ("diaomao2023", "交易员小帅", "us_stock", "个人-交易", "大盘/ETF", "大盘、ETF、宏观流动性、交易节奏", "Biteye美股50人榜", ""),
    ("junshao_666", "Crypto_君少", "us_stock", "个人-交易", "宏观/大盘", "宏观、流动性、大盘、风险资产联动", "Biteye美股50人榜", ""),
    ("hibtc37", "37度", "us_stock", "个人-基本面", "财报/期权", "财报、估值、基本面、期权", "Biteye美股50人榜", ""),
    ("shawnchen_eth", "MichaelTurtle", "us_stock", "个人-大盘", "大盘/ETF", "大盘、ETF、财报、基本面", "Biteye美股50人榜", ""),
    ("yiqifacai", "一起发财", "us_stock", "个人-研究", "半导体/宏观", "半导体、宏观流动性、科技股", "Biteye美股50人榜", ""),
]

rows = []
missing = []
for handle, name, cat, typ, track, focus, source, note in CURATED:
    key = handle.lower()
    if key not in by_handle:
        missing.append(handle)
        continue
    d = by_handle[key]
    f = d.get("followers")
    if f is None:
        missing.append(handle)
        continue
    rows.append({
        "name": name,
        "handle": d.get("screen_name", handle),
        "url": f"https://x.com/{d.get('screen_name', handle)}",
        "followers": f,
        "followers_fetched_at": FETCH_DATE,
        "category": cat,
        "type": typ,
        "track": track,
        "focus": focus,
        "bio": d.get("bio", ""),
        "source": source,
        "note": note,
    })

rows.sort(key=lambda r: -r["followers"])

# ---- Output JSONL ----
with open(DATA_DIR / "x_kol_list.jsonl", "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

# ---- Output Markdown ----
with open(DATA_DIR / "x_kol_list.md", "w", encoding="utf-8") as f:
    f.write(f"# x.com 中文加密 & 美股 KOL 清单（{FETCH_DATE} 抓取粉丝数）\n\n")
    f.write(f"> 共 {len(rows)} 个账号，粉丝数均 ≥ 2 万（除个别标注外）。粉丝数来自 fxtwitter API，抓取日期 {FETCH_DATE}。\n\n")
    f.write("## 一、加密货币 KOL\n\n")
    f.write("| 中文名 | Handle | 粉丝数 | 类型 | 方向 | 简介 |\n|---|---|---|---|---|---|\n")
    for r in rows:
        if r["category"] in ("crypto", "both"):
            f.write(f"| {r['name']} | [@{r['handle']}]({r['url']}) | {r['followers']:,} | {r['type']} | {r['track']} | {r['focus']} |\n")
    f.write("\n## 二、美股 KOL\n\n")
    f.write("| 中文名 | Handle | 粉丝数 | 类型 | 方向 | 简介 |\n|---|---|---|---|---|---|\n")
    for r in rows:
        if r["category"] in ("us_stock", "both"):
            f.write(f"| {r['name']} | [@{r['handle']}]({r['url']}) | {r['followers']:,} | {r['type']} | {r['track']} | {r['focus']} |\n")
    f.write("\n## 三、说明\n\n")
    f.write("- 数据来源：Biteye《华语加密 KOL 影响力图鉴》（2025-09-24 快照）、Biteye《X 美股投资交易 50 位大咖「去噪」清单》、公开知名人物/媒体清单。\n")
    f.write("- 粉丝数为 2026-08-22 通过 fxtwitter API 实测，会随账号变动而变化，建议定期用 `scripts/fetch_followers.py` 刷新。\n")
    f.write("- 已剔除粉丝不足 2 万的知名账号：李笑来(@lixiaolai 6.5k)、赵东(@zhaodong1982 5.2k)、PANews(@PANewsLab 11.9k)、华尔街见闻(@WallStreetCN 账号异常) 等。\n")

print(f"OK: {len(rows)} rows written. Missing: {missing}")
print(f"Files: {DATA_DIR / 'x_kol_list.jsonl'}, {DATA_DIR / 'x_kol_list.md'}")
