# -*- coding: utf-8 -*-
"""تولید فیکسچرهای تست برابری (parity) موتور JS اندروید با موتور پایتون.

خروجی: tests/js/fixtures.json
اجرا:  python tests/js/gen_fixtures.py     (نیاز به اینترنت — دادهٔ زنده ضبط می‌شود)
سپس:   node tests/js/run_parity.js

ایده: هر چیزی که موتور اندروید (JS) محاسبه می‌کند، با ورودی یکسان روی
موتور دسکتاپ (پایتون — منبع حقیقت) هم اجرا و نتیجه ضبط می‌شود.
run_parity.js همان ورودی‌ها را به JS می‌دهد و خروجی‌ها را مقایسه می‌کند.

⚠️ fixtures.json دادهٔ زندهٔ ضبط‌شده دارد و در گیت ثبت نمی‌شود.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np          # noqa: E402
import pandas as pd         # noqa: E402
import requests             # noqa: E402

from src.analysis import indicators as ind                    # noqa: E402
from src.analysis.strength import currency_strength           # noqa: E402
from src.analysis.technical import analyze_symbol             # noqa: E402
from src.config import load_config                            # noqa: E402
from src.data.base import MarketData                          # noqa: E402
from src.data.tradingview import TVSnapshot                   # noqa: E402
from src.fundamental import news as news_mod                  # noqa: E402
from src.fundamental.calendar import (CalendarSnapshot,       # noqa: E402
                                      parse_events, upcoming_events, veto_for_symbol)
from src.journal.stats import compute_stats                   # noqa: E402
from src.journal.store import Journal                         # noqa: E402
from src.journal.tracker import resolve_open_signals          # noqa: E402
from src.judge.scoring import JudgeContext, judge_all, judge_config  # noqa: E402
from src.judge.session import market_status                   # noqa: E402

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
OUT = Path(__file__).resolve().parent / "fixtures.json"

FX: dict = {}
SHARED: dict = {}      # دادهٔ میان‌مرحله‌ای (datasets، snapshotها) برای استفادهٔ داخلی


def log(msg: str) -> None:
    print(msg, flush=True)


def http_get(url: str) -> str:
    r = requests.get(url, headers={"User-Agent": UA}, timeout=25)
    r.raise_for_status()
    return r.text


def df_from(candles: list[list]) -> pd.DataFrame:
    df = pd.DataFrame(candles, columns=["t", "Open", "High", "Low", "Close"])
    df.index = pd.to_datetime(df["t"], unit="ms")
    return df.drop(columns=["t"])


def candles_of(df: pd.DataFrame) -> list[list]:
    out = []
    for ts, row in df.iterrows():
        out.append([int(ts.timestamp() * 1000), float(row["Open"]), float(row["High"]),
                    float(row["Low"]), float(row["Close"])])
    return out


def nanless(arr) -> list:
    return [None if (v is None or pd.isna(v)) else float(v) for v in arr]


# ══════════════════════════════════════════════════════════════
def main() -> None:
    cfg = load_config()
    now_ms = int(time.time() * 1000)
    FX["nowMs"] = now_ms
    log(f"⏱ now = {datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} UTC")

    gen_indicator_fixtures()
    gen_fa_fixtures()
    gen_session_fixtures()
    gen_market_fixtures(cfg)
    gen_calendar_fixtures(cfg, now_ms)
    gen_tv_fixtures(cfg)
    gen_news_fixtures(cfg, now_ms)
    gen_judge_fixtures(cfg, now_ms)
    gen_journal_fixtures(now_ms)

    OUT.write_text(json.dumps(FX, ensure_ascii=False), encoding="utf-8")
    log(f"✅ fixtures.json نوشته شد ({OUT.stat().st_size / 1e6:.1f} MB)")


# ── اندیکاتورها (سری مصنوعی با بذر ثابت) ──────────────────────
def gen_indicator_fixtures() -> None:
    log("🧮 اندیکاتورها...")
    rng = np.random.default_rng(42)
    n = 320
    ret = rng.normal(0, 0.0016, n)
    close = 100 * np.exp(np.cumsum(ret))
    high = close * (1 + np.abs(rng.normal(0, 0.0011, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.0011, n)))
    op = np.roll(close, 1)
    op[0] = close[0]
    t0 = 1_700_000_000_000
    ohlc = [[t0 + i * 3_600_000, float(op[i]), float(high[i]), float(low[i]), float(close[i])]
            for i in range(n)]

    df = df_from(ohlc)
    series = {
        "ema50": ind.ema(df["Close"], 50),
        "ema200": ind.ema(df["Close"], 200),
        "rsi14": ind.rsi(df["Close"], 14),
        "atr14": ind.atr(df, 14),
        "adx14": ind.adx(df, 14),
    }
    lows, highs = ind.swing_levels(df, 5)
    sup, res = ind.nearest_levels(float(close[-1]), df, 5)

    # حالت‌های لبهٔ ewm با NaN (رفتار pandas باید مو به مو بازتولید شود)
    ewm_cases = []
    for x in ([1.0, np.nan, 2.0, 3.0], [np.nan, 5.0, 7.0], [4.0, np.nan, np.nan, 10.0],
              [1.0, 2.0, np.nan], [np.nan, np.nan, 1.0, np.nan, 2.0]):
        s = pd.Series(x)
        for alpha in (0.5, 1 / 14, 2 / 51):
            out = s.ewm(alpha=alpha, adjust=False).mean().tolist()
            ewm_cases.append({"x": [None if pd.isna(v) else v for v in x],
                              "alpha": alpha, "out": nanless(out)})

    FX["indicators"] = {
        "ohlc": ohlc,
        "closes": [float(v) for v in close],
        "series": {k: nanless(v.tolist()) for k, v in series.items()},
        "swings": {"lows": [float(v) for v in lows], "highs": [float(v) for v in highs]},
        "levels": {"support": sup, "resistance": res, "price": float(close[-1])},
        "ewm_cases": ewm_cases,
    }


# ── ابزار فارسی ───────────────────────────────────────────────
def gen_fa_fixtures() -> None:
    log("🔤 ابزار فارسی...")
    from src.fa import fa_countdown, fa_date, fa_num, fa_pips, fa_ratio
    from src.report.signal import fmt_price

    cases = []
    for v in ["+2", "1394", 7.5, -0.35, 180, "1.14856"]:
        cases.append({"fn": "fa_num", "args": [v], "out": fa_num(v)})
    for n in [2.0, 1.5, 0.6, 3.0, 11.0]:
        cases.append({"fn": "fa_ratio", "args": [n], "out": fa_ratio(n)})
    for v, pip, gold in [(0.0035, 0.0001, False), (120.5, 1.0, True), (0.152, 0.01, False),
                         (45.0, 1.0, False)]:
        cases.append({"fn": "fa_pips", "args": [v, pip, gold], "out": fa_pips(v, pip, gold)})
    for v, pip in [(1.14856, 0.0001), (156.854, 0.01), (4378.385, 1.0), (1.310724, 0.0001)]:
        cases.append({"fn": "fmt_price", "args": [v, pip], "out": fmt_price(v, pip)})
    for m in [25, 72, 1440, 2880, 59]:
        cases.append({"fn": "fa_countdown", "args": [m], "out": fa_countdown(m)})
    dt = datetime(2026, 9, 19, 14, 30, tzinfo=timezone.utc)   # شنبه
    cases.append({"fn": "fa_date", "args": ["2026-09-19T14:30Z", True], "out": fa_date(dt)})
    cases.append({"fn": "fa_date", "args": ["2026-09-19T14:30Z", False], "out": fa_date(dt, False)})
    FX["fa"] = cases


# ── سشن‌ها ────────────────────────────────────────────────────
def gen_session_fixtures() -> None:
    log("🕒 سشن‌ها...")
    stamps = [
        datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc),   # شنبه — بسته
        datetime(2026, 9, 20, 10, 0, tzinfo=timezone.utc),   # یکشنبه — بسته تا ۲۲
        datetime(2026, 9, 20, 22, 30, tzinfo=timezone.utc),  # یکشنبه — سیدنی باز
        datetime(2026, 9, 21, 8, 15, tzinfo=timezone.utc),   # دوشنبه — توکیو+لندن
        datetime(2026, 9, 23, 14, 30, tzinfo=timezone.utc),  # چهارشنبه — هم‌پوشانی
        datetime(2026, 9, 25, 21, 30, tzinfo=timezone.utc),  # جمعه — بسته از ۲۱
        datetime(2026, 9, 22, 6, 30, tzinfo=timezone.utc),   # سه‌شنبه — خلأ نقدینگی
    ]
    out = []
    for d in stamps:
        st = market_status(d)
        out.append({"ts": int(d.timestamp() * 1000), "open": st.open, "reason_fa": st.reason_fa,
                    "sessions": list(st.sessions), "overlap": st.overlap,
                    "liquid": st.liquid, "label": st.label})
    FX["session"] = out


# ── دادهٔ بازار زنده (Yahoo chart API — همان مسیری که اپ می‌رود) ──
def gen_market_fixtures(cfg: dict) -> None:
    log("📡 دادهٔ بازار...")
    symbols = {}
    chart_raw = {}
    datasets: dict[str, MarketData] = {}
    analyses = []

    for sym in cfg["symbols"]:
        name = sym["name"]
        y = sym.get("yahoo") or (name + "=X")
        raw = {}
        for key, interval, rng in (("h1", "1h", "60d"), ("m15", "15m", "5d")):
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{requests.utils.quote(y, safe='')}?range={rng}&interval={interval}"
            raw[key] = json.loads(http_get(url))
            time.sleep(0.4)

        def to_candles(blob) -> list[list]:
            res = blob["chart"]["result"][0]
            q = res["indicators"]["quote"][0]
            out = []
            for i, ts in enumerate(res["timestamp"]):
                o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
                if o is None or h is None or l is None or c is None:
                    continue                      # dropna
                out.append([int(ts * 1000), float(o), float(h), float(l), float(c)])
            return out[:-1] if len(out) > 1 else out   # drop_forming_candle

        h1c = to_candles(raw["h1"])
        m15c = to_candles(raw["m15"])
        h1 = df_from(h1c)
        m15 = df_from(m15c)
        h4 = (h1.resample("4h")
                .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"})
                .dropna())
        md = MarketData(symbol=name, m15=m15, h1=h1, h4=h4)
        datasets[name] = md
        a = analyze_symbol(sym, md, cfg["analysis"])
        analyses.append(a)

        symbols[name] = {
            "cfg": sym,
            "h1": h1c, "m15": m15c, "h4": candles_of(h4),
            "analysis": {
                "symbol": a.symbol, "fa_name": a.fa_name, "base": a.base, "quote": a.quote,
                "price": a.price, "pip": a.pip, "trend": a.trend, "h1_agrees": a.h1_agrees,
                "adx": a.adx, "rsi": a.rsi, "rsi_rising": a.rsi_rising, "atr": a.atr,
                "support": a.support, "resistance": a.resistance,
                "last_candle": int(a.last_candle.replace(tzinfo=timezone.utc).timestamp() * 1000)
                if a.last_candle else None,
                "verdict": a.verdict,
            },
        }
        # برای تست پارس chart در JS: دو نماد با پاسخ خام
        if name in ("EURUSD", "XAUUSD"):
            chart_raw[name] = {"raw": raw, "expH1": h1c, "expM15": m15c}
        log(f"  ✓ {name}: h1={len(h1c)} m15={len(m15c)} h4={len(h4)} → {a.verdict}")

    ranking = currency_strength(datasets, lookback_h1=int(cfg["analysis"].get("strength_lookback_h1", 24)))
    SHARED["datasets"] = datasets
    SHARED["analyses"] = analyses
    FX["symbols"] = symbols
    FX["chartRaw"] = chart_raw
    FX["ranking"] = [[c, float(v)] for c, v in ranking]


# ── تقویم اقتصادی ─────────────────────────────────────────────
def gen_calendar_fixtures(cfg: dict, now_ms: int) -> None:
    log("🏦 تقویم اقتصادی...")
    fcfg = cfg.get("fundamental") or {}
    url = fcfg.get("source_url") or "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    raw = json.loads(http_get(url))
    events = parse_events(raw)
    now = datetime.now(timezone.utc)
    cal_now_ms = int(now.timestamp() * 1000)

    ev_dump = []
    for e in events:
        ev_dump.append({
            "when": int(e.when.timestamp() * 1000), "country": e.country, "title": e.title,
            "title_fa": e.title_fa, "impact": e.impact, "forecast": e.forecast,
            "previous": e.previous, "category": e.category, "polarity": e.polarity,
            "key": e.key, "country_fa": e.country_fa, "currency_fa": e.currency_fa,
            "explain": e.explain(cfg["symbols"], now),
        })

    up48 = upcoming_events(CalendarSnapshot(events=events), now, hours=48.0)
    vetoes = {}
    for sym in cfg["symbols"]:
        evs = veto_for_symbol(CalendarSnapshot(events=events), sym["base"], sym["quote"],
                              now, minutes=float(fcfg.get("veto_minutes_before", 30)))
        vetoes[sym["name"]] = [e.key for e in evs]

    SHARED["cal_snap"] = CalendarSnapshot(events=events, fetched_at=now)
    FX["calendar"] = {
        "nowMs": cal_now_ms,
        "raw": raw, "events": ev_dump,
        "upcoming48": [e.key for e in up48],
        "vetoes": vetoes,
        "high_impact": [e.key for e in events if e.impact == "HIGH"],
    }


# ── تریدینگ‌ویو (پاسخ خام اسکنر ضبط می‌شود) ──────────────────
TF_SUFFIX = {"15m": "15", "1h": "60", "4h": "240"}


def rec_label(v):
    """آستانه‌های رسمی tradingview-ta برای Recommend.All."""
    if v is None:
        return None
    if v > 0.5:
        return "STRONG_BUY"
    if v > 0.1:
        return "BUY"
    if v >= -0.1:
        return "NEUTRAL"
    if v >= -0.5:
        return "SELL"
    return "STRONG_SELL"


def gen_tv_fixtures(cfg: dict) -> None:
    log("🔍 تریدینگ‌ویو...")
    tf = str((cfg.get("tradingview") or {}).get("timeframe", "4h")).lower()
    suf = TF_SUFFIX.get(tf, "240")
    cols = ["close", f"Recommend.All|{suf}", f"Recommend.MA|{suf}", f"Recommend.Other|{suf}",
            f"Buy.All|{suf}", f"Sell.All|{suf}", f"Neutral.All|{suf}", f"RSI|{suf}", f"ADX|{suf}"]

    by_screener: dict[str, list] = {}
    for sym in cfg["symbols"]:
        tv = sym.get("tv") or {}
        if not tv.get("symbol"):
            continue
        by_screener.setdefault(tv.get("screener", "forex"), []).append(
            {"name": sym["name"], "ticker": f"{tv.get('exchange', 'FX')}:{tv['symbol']}"})

    raw_all, tv_map = {}, {}
    for screener, items in by_screener.items():
        body = {"symbols": {"tickers": [x["ticker"] for x in items]}, "columns": cols}
        r = requests.post(f"https://scanner.tradingview.com/{screener}/scan",
                          json=body, headers={"User-Agent": UA, "Content-Type": "application/json"},
                          timeout=20)
        r.raise_for_status()
        raw_all[screener] = r.json()
        for row in r.json().get("data", []):
            hit = [x for x in items if x["ticker"] == row["s"]]
            if not hit:
                continue
            d = row.get("d", [])
            rec = rec_label(d[1] if len(d) > 1 else None)
            if not rec:
                continue
            tv_map[hit[0]["name"]] = TVSnapshot(
                symbol=hit[0]["name"], close=d[0],
                rsi=d[7] if len(d) > 7 else None, adx=d[8] if len(d) > 8 else None,
                recommendation=rec,
                buy=d[4] if len(d) > 4 else None, sell=d[5] if len(d) > 5 else None,
                neutral=d[6] if len(d) > 6 else None, timeframe=tf)
            # فیلدهای اضافه فقط برای مقایسهٔ متن مدرک (در TVSnapshot دسکتاپ نیستند)
            tv_map[hit[0]["name"]].recommend_ma = d[2] if len(d) > 2 else None
            tv_map[hit[0]["name"]].recommend_other = d[3] if len(d) > 3 else None

    SHARED["tv_map"] = tv_map
    FX["tv"] = {"raw": raw_all, "tf": tf, "suf": suf, "cols": cols,
                "map": {k: {"symbol": v.symbol, "close": v.close, "recommendation": v.recommendation,
                            "recommend_ma": v.recommend_ma, "recommend_other": v.recommend_other,
                            "buy": v.buy, "sell": v.sell, "neutral": v.neutral,
                            "rsi": v.rsi, "adx": v.adx, "timeframe": v.timeframe}
                        for k, v in tv_map.items()}}


# ── اخبار (XML خام ضبط می‌شود؛ پارس با feedparser = مرجع) ─────
def gen_news_fixtures(cfg: dict, now_ms: int) -> None:
    log("📰 اخبار...")
    import feedparser
    ncfg = cfg.get("news") or {}
    feeds = ncfg.get("feeds") or news_mod.DEFAULT_FEEDS
    news_now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    # now با دقت میلی‌ثانیه — دقیقاً همان مقدادی که سمت JS استفاده می‌شود
    now = datetime.fromtimestamp(news_now_ms / 1000, tz=timezone.utc)
    age = float(ncfg.get("max_age_hours", 30))
    min_score = int(ncfg.get("min_score", 2))
    per_feed = int(ncfg.get("max_items_per_feed", 12))
    total_max = int(ncfg.get("max_total", 18))

    feed_dump, seen, items_all = [], set(), []
    for f in feeds:
        name = str(f.get("name") or f.get("url") or "feed")
        url = str(f.get("url") or "")
        if not url:
            continue
        try:
            xml = http_get(url)
        except Exception as e:
            log(f"  [!] {name}: {e}")
            continue
        parsed = feedparser.parse(xml.encode("utf-8"))
        entries = list(getattr(parsed, "entries", []) or [])
        items = news_mod.parse_entries(entries, name, int(f.get("weight", 1)),
                                       now=now, max_age_hours=age, min_score=min_score)
        items.sort(key=lambda x: (x.published or now), reverse=True)
        items = items[:per_feed]
        fresh = [it for it in items if it.dedupe_key not in seen]
        for it in fresh:
            seen.add(it.dedupe_key)
        items_all.extend(fresh)
        feed_dump.append({"name": name, "weight": int(f.get("weight", 1)), "url": url,
                          "xml": xml, "nEntries": len(entries)})
        log(f"  ✓ {name}: {len(fresh)} خبر از {len(entries)} ورودی")

    items_all.sort(key=lambda x: (-x.score, x.age_minutes))
    items_all = items_all[:total_max]

    def item_dump(it):
        return {"title": it.title, "link": it.link, "source": it.source,
                "published": int(it.published.timestamp() * 1000) if it.published else None,
                "score": it.score, "direction": it.direction, "keywords": it.keywords,
                "breaking": it.breaking, "roundup": it.roundup, "summary": it.summary,
                "age_minutes": it.age_minutes, "dedupe_key": it.dedupe_key,
                "direction_fa": it.direction_fa(), "headline_fa": it.headline_fa(70)}

    # برای برابریِ پارس+امتیازدهی، یک بار هم «بدون فیلتر سن و حداقل امتیاز»
    # روی همان XML ضبط‌شده اجرا می‌شود (یکشنبه‌ها فیدها کهنه‌اند وگرنه).
    import feedparser as _fp
    parse_all = []
    for f in feed_dump:
        entries = list(getattr(_fp.parse(f["xml"].encode("utf-8")), "entries", []) or [])
        its = news_mod.parse_entries(entries, f["name"], f["weight"], now=now,
                                     max_age_hours=24 * 30, min_score=0)
        parse_all.append({"name": f["name"], "weight": f["weight"],
                          "items": [item_dump(i) for i in its[:40]]})

    snap = news_mod.NewsSnapshot(items=items_all, fetched_at=now)
    SHARED["news_snap"] = snap

    supports = {}
    for sym in cfg["symbols"]:
        for bias in ("buy", "sell"):
            v = news_mod.news_supports(snap, sym["base"], sym["quote"], bias,
                                       min_score=int((cfg.get("judge") or {}).get("news", {}).get("min_score", 4)))
            supports[f"{sym['name']}|{bias}"] = {
                "votes": v.votes, "verdict": v.verdict, "has_evidence": v.has_evidence,
                "support": [i.title for i in v.support[:2]],
                "contradict": [i.title for i in v.contradict[:2]]}

    FX["news"] = {"nowMs": news_now_ms, "feeds": feed_dump,
                  "items": [item_dump(i) for i in items_all],
                  "supports": supports, "parseAll": parse_all,
                  "config": {"max_age_hours": age, "min_score": min_score,
                             "max_items_per_feed": per_feed, "max_total": total_max}}

    # عنوان‌های دست‌ساز برای پوشش مسیرهای امتیازدهی جهت‌دار
    crafted = [
        ("USDJPY surges as Fed turns hawkish", ""),
        ("Gold rallies to two-week high on safe-haven demand", "bullion bids"),
        ("Dollar slips against the euro after weak US data", ""),
        ("Yen strengthens as BOJ conducts rate check", "possible intervention"),
        ("BREAKING: Sterling tumbles after dovish BOE surprise", ""),
        ("Silver soars as the Fed signals rate cuts", ""),
        ("Bitcoin jumps above resistance", "crypto rally"),
        ("Oil prices fall as OPEC output rises", ""),
        ("What to watch in the week ahead: Fed, BOJ and NFP", ""),
        ("Markets today: stocks, bonds and currencies recap", ""),
        ("Euro steadies as ECB's Lagarde speaks on inflation", ""),
        ("Canadian dollar weakens as BOC cuts rates", "loonie lower"),
        ("Aussie dollar gains after upbeat RBA commentary", ""),
        ("Treasury yields climb; dollar mixed", ""),
        ("US jobless claims fall; dollar firms against the yen", ""),
        ("Gold and dollar both rise in risk-off scramble", "flight to safety, war fears"),
        ("Kiwi slides vs greenback on dairy price drop", ""),
        ("FX wrap: EUR/USD, GBP/USD and USD/JPY technicals", ""),
        ("NFP beats forecasts; dollar rally extends", "payrolls strong"),
        ("China stimulus boosts yuan; Aussie rallies too", "PBOC eases"),
    ]
    st_cases = []
    for title, summary in crafted:
        score, direction, kws, breaking, roundup = news_mod.score_text(
            title, wide=f"{title}. {summary[:300]}" if summary else None)
        subj = news_mod.subject_spans(f"{title}. {summary}" if summary else title)
        st_cases.append({"title": title, "wide": (f"{title}. {summary[:300]}" if summary else None),
                         "score": score, "direction": direction, "keywords": kws,
                         "breaking": breaking, "roundup": roundup,
                         "subject": subj[0][0] if subj else None})
    FX["scoreText"] = st_cases


# ── داور (در دو زمان: الان + شبیه‌سازی وسط هفته) ─────────────
def pick_sim_now(now_ms: int) -> int:
    """چهارشنبهٔ ۱۴:۰۰ UTC همان هفته (یا اولین روز کاری بعدی در پوشش فید)."""
    base = datetime.fromtimestamp(now_ms / 1000, tz=timezone.utc)
    for delta in range(0, 8):
        d = base + timedelta(days=delta)
        if d.weekday() == 2:
            return int(d.replace(hour=14, minute=0, second=0, microsecond=0).timestamp() * 1000)
    d = base + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return int(d.replace(hour=14, minute=0, second=0, microsecond=0).timestamp() * 1000)


def judgment_dump(j) -> dict:
    sig = None
    if j.signal:
        s = j.signal
        sig = {"symbol": s.symbol, "direction": s.direction, "sid": s.sid,
               "score": s.score, "max_score": s.max_score, "stars": s.stars,
               "entry": s.entry, "sl": s.sl, "tp": s.tp, "pip": s.pip, "atr": s.atr,
               "risk_pips": s.risk_pips, "reward_pips": s.reward_pips, "rr": s.rr,
               "is_gold": s.is_gold, "session_fa": s.session_fa, "warnings": s.warnings,
               "sl_capped": s.sl_capped, "direction_fa": s.direction_fa,
               "journal": s.to_journal(sent=True)}
    return {"symbol": j.symbol, "direction": j.direction, "score": j.score,
            "max_score": j.max_score, "reject_reason": j.reject_reason,
            "reject_detail": j.reject_detail, "status_fa": j.status_fa,
            "price": j.price, "pip": j.pip,
            "vetoes": [{"key": v.key, "title_fa": v.title_fa, "detail_fa": v.detail_fa} for v in j.vetoes],
            "evidences": [{"key": e.key, "label_fa": e.label_fa, "points": e.points,
                           "max_points": e.max_points, "detail_fa": e.detail_fa,
                           "ok": e.ok, "unavailable": e.unavailable, "icon": e.icon}
                          for e in j.evidences],
            "warnings": j.warnings, "signal": sig}


def gen_judge_fixtures(cfg: dict, now_ms: int) -> None:
    log("⚖️ داور...")
    jcfg = judge_config(cfg)
    cal_snap = SHARED.get("cal_snap")
    news_snap = SHARED.get("news_snap")
    tv_map = SHARED.get("tv_map", {})
    datasets = SHARED["datasets"]
    analyses = SHARED["analyses"]
    ranking = [(c, v) for c, v in FX["ranking"]]

    out = {}
    for tag, ms in (("live", now_ms), ("sim", pick_sim_now(now_ms))):
        now = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
        ctx = JudgeContext(
            jcfg=jcfg, acfg=cfg["analysis"], symbols_cfg=cfg["symbols"],
            ranking=ranking, tv_map=tv_map, cal_snap=cal_snap, news_snap=news_snap,
            now=now, status=market_status(now),
            event_veto_minutes=float((cfg.get("fundamental") or {}).get("veto_minutes_before", 30)))
        judgments = judge_all(analyses, datasets, ctx)
        out[tag] = {"nowMs": ms, "judgments": [judgment_dump(j) for j in judgments]}
        sigs = [j for j in judgments if j.signal]
        log(f"  ✓ {tag}: {len(sigs)} سیگنال از {len(judgments)} نماد")
    FX["judge"] = out


# ── ژورنال (سنتتیک و قطعی) ────────────────────────────────────
def gen_journal_fixtures(now_ms: int) -> None:
    log("📔 ژورنال...")
    h = 3_600_000
    now = datetime.fromtimestamp(now_ms / 1000, tz=timezone.utc)

    # میله‌های M15 سنتتیک برای سه سناریو
    def bars(start_ms, seq):
        # seq: فهرست (high, low, close) با گام ۱۵ دقیقه از start
        # (خروجی ۵ ستونی: t, open, high, low, close — open همان high فرض می‌شود)
        out, t = [], start_ms
        for hh, ll, cc in seq:
            t += 900_000
            out.append([t, float(hh), float(hh), float(ll), float(cc)])
        return out

    datasets = {}
    # A: EURUSD BUY — هدف می‌خورد
    datasets["EURUSD"] = MarketData(symbol="EURUSD",
                                    m15=df_from(bars(now_ms - 6 * h, [(1.1510, 1.1480, 1.1500),
                                                                      (1.1560, 1.1495, 1.1555)])),
                                    h1=None, h4=None)
    # B: XAUUSD SELL — یک کندل هر دو سطح را می‌زند (محتاطانه = ضرر)
    datasets["XAUUSD"] = MarketData(symbol="XAUUSD",
                                    m15=df_from(bars(now_ms - 8 * h, [(4380.0, 4360.0, 4370.0),
                                                                      (4420.0, 4300.0, 4350.0)])),
                                    h1=None, h4=None)
    # C: GBPUSD BUY — منقضی (۶۰ ساعت، بدون برخورد)
    datasets["GBPUSD"] = MarketData(symbol="GBPUSD",
                                    m15=df_from(bars(now_ms - 61 * h, [(1.3510, 1.3490, 1.3500),
                                                                       (1.3520, 1.3495, 1.3510)])),
                                    h1=None, h4=None)
    # D: USDJPY BUY — هنوز باز
    datasets["USDJPY"] = MarketData(symbol="USDJPY",
                                    m15=df_from(bars(now_ms - 2 * h, [(156.90, 156.70, 156.80)])),
                                    h1=None, h4=None)

    sigs = [
        {"kind": "signal", "id": "EURUSD-BUY-A", "ts": (now - timedelta(hours=3)).isoformat(),
         "symbol": "EURUSD", "direction": "BUY", "entry": 1.1500, "sl": 1.1470, "tp": 1.1560,
         "pip": 0.0001, "atr": 0.0008, "risk_pips": 30.0, "reward_pips": 60.0, "rr": 2.0,
         "score": 8, "max_score": 11, "session": "لندن", "evidences": ["trend:2/2", "level:2/2", "news:0/1"], "sent": True},
        {"kind": "signal", "id": "XAUUSD-SELL-B", "ts": (now - timedelta(hours=5)).isoformat(),
         "symbol": "XAUUSD", "direction": "SELL", "entry": 4370.0, "sl": 4400.0, "tp": 4310.0,
         "pip": 1.0, "atr": 12.0, "risk_pips": 30.0, "reward_pips": 60.0, "rr": 2.0,
         "score": 9, "max_score": 11, "session": "نیویورک", "evidences": ["trend:2/2"], "sent": True},
        {"kind": "signal", "id": "GBPUSD-BUY-C", "ts": (now - timedelta(hours=60)).isoformat(),
         "symbol": "GBPUSD", "direction": "BUY", "entry": 1.3500, "sl": 1.3470, "tp": 1.3560,
         "pip": 0.0001, "atr": 0.0009, "risk_pips": 30.0, "reward_pips": 60.0, "rr": 2.0,
         "score": 7, "max_score": 11, "session": "لندن", "evidences": ["trend:1/2"], "sent": False},
        {"kind": "signal", "id": "USDJPY-BUY-D", "ts": (now - timedelta(hours=1)).isoformat(),
         "symbol": "USDJPY", "direction": "BUY", "entry": 156.80, "sl": 156.50, "tp": 157.40,
         "pip": 0.01, "atr": 0.09, "risk_pips": 30.0, "reward_pips": 60.0, "rr": 2.0,
         "score": 8, "max_score": 11, "session": "توکیو", "evidences": ["trend:2/2"], "sent": True},
        # یک بستهٔ قدیمی برای آمار
        {"kind": "signal", "id": "EURUSD-BUY-OLD", "ts": (now - timedelta(days=9)).isoformat(),
         "symbol": "EURUSD", "direction": "BUY", "entry": 1.1400, "sl": 1.1370, "tp": 1.1460,
         "pip": 0.0001, "atr": 0.0008, "risk_pips": 30.0, "reward_pips": 60.0, "rr": 2.0,
         "score": 10, "max_score": 11, "session": "لندن", "evidences": ["trend:2/2", "level:2/2"], "sent": True},
        {"kind": "outcome", "id": "EURUSD-BUY-OLD", "ts": (now - timedelta(days=8)).isoformat(),
         "outcome": "TP", "close_price": 1.1460, "r": 2.0, "note": ""},
    ]
    jsonl = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in sigs)

    tmp = OUT.parent / "_journal_tmp.jsonl"
    tmp.write_text(jsonl, encoding="utf-8")
    journal = Journal(path=tmp)
    jcfg = {"journal": {"enabled": True, "expiry_hours": 48, "conservative_both_touch": True}}
    resolved = resolve_open_signals(journal, datasets, now=now, cfg=jcfg)
    entries = journal.load()
    stats = compute_stats(entries, now)
    tmp.unlink(missing_ok=True)

    def entry_dump(e):
        return {"id": e.id, "ts": int(e.ts.timestamp() * 1000), "symbol": e.symbol,
                "direction": e.direction, "entry": e.entry, "sl": e.sl, "tp": e.tp,
                "pip": e.pip, "atr": e.atr, "risk_pips": e.risk_pips, "reward_pips": e.reward_pips,
                "rr": e.rr, "score": e.score, "max_score": e.max_score, "session": e.session,
                "evidences": e.evidences, "sent": e.sent, "outcome": e.outcome,
                "outcome_ts": int(e.outcome_ts.timestamp() * 1000) if e.outcome_ts else None,
                "close_price": e.close_price, "r": e.r, "note": e.note,
                "week_key": e.week_key, "evidence_keys": e.evidence_keys()}

    FX["journal"] = {
        "jsonl": jsonl,
        "bars": {k: candles_of(v.m15) for k, v in datasets.items()},
        "resolved": [{"id": e.id, "outcome": e.outcome, "r": e.r,
                      "close_price": e.close_price, "note": e.note} for e in resolved],
        "entries": [entry_dump(e) for e in entries],
        "stats": {"total": stats.total, "open_count": stats.open_count,
                  "overall": vars(stats.overall),
                  "by_symbol": {k: vars(v) for k, v in stats.by_symbol.items()},
                  "by_score": {k: vars(v) for k, v in stats.by_score.items()},
                  "by_evidence": {k: vars(v) for k, v in stats.by_evidence.items()},
                  "by_week": {k: vars(v) for k, v in stats.by_week.items()}},
    }

    # md5 (برای dedupe) — چند نمونه با یونیکد
    FX["md5"] = [{"s": t, "out": hashlib.md5(t.encode("utf-8")).hexdigest()}
                 for t in ["gold rises as dollar slips", "fed's powell says inflation 'too high'",
                           "eur/usd week ahead wrap", "طلا و دلار", ""]]


if __name__ == "__main__":
    main()
