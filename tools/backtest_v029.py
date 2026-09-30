# -*- coding: utf-8 -*-
"""بازپخشِ تاریخیِ سیگنال‌های ODIN با قواعدِ v0.29 — ابزارِ تصمیم، نه محصول.

چرا این فایل وجود دارد
----------------------
تا پیش از v0.29 ژورنال عددِ خوش‌بینانه تولید می‌کرد و هیچ راهی نبود بفهمیم
لایهٔ خروج (هدفِ ثابتِ ۲R، حد ضررِ بی‌حرکت، انقضای ۴۸ ساعت) درست است یا نه.
دورهٔ سایهٔ تازه ۴ تا ۸ هفته طول می‌کشد. این ابزار همان پرسش را روی
دادهٔ **واقعیِ گذشته** تقریب می‌زند تا قبل از انتظارِ چند هفته‌ای، جهتِ درست
را پیدا کنیم.

⚠️ این یک محصول نیست و در اپ نمی‌رود. یک ابزارِ یک‌بارمصرفِ تحلیل است.

چه چیزی صادقانه نیست (بخوانید)
------------------------------
۱) **پنجرهٔ داده محدود است.** یاهو برای کندلِ ۱۵ دقیقه فقط ~۶۰ روز نگه
   می‌دارد. پس «۶ ماه» ممکن نیست؛ آنچه هست ~۸۰ روز تقویمی است.
۲) **فقط هستهٔ تکنیکال.** تقویمِ اقتصادی، اخبارِ جهت‌دار و تاییدیهٔ
   تریدینگ‌ویو برای گذشته قابلِ بازیابی نیستند. یعنی:
     • ۴ امتیاز از ۱۱ (fundamental 2 + news 1 + tv 1) همیشه صفر است
     • دو وتوی high_impact_event و breaking_news هرگز فعال نمی‌شوند
   → این **سیستمِ تولید نیست**؛ یک زیرمجموعهٔ خوش‌تعریفِ آن است. نتیجه
     دربارهٔ «هندسهٔ خروج» معتبر است، دربارهٔ «آیا داورِ کامل خوب است» نه.
   به‌همین دلیل آستانهٔ امتیاز **جاروب** می‌شود (۴ تا ۷) نه یک عددِ ثابت.
۳) **اسپرد برآورد است**، نه اسپردِ واقعیِ بروکرِ شما (همان جدولِ config.yaml).
۴) **ابهامِ درون‌کندلی با بدبینی حل می‌شود.** وقتی یک کندلِ ۱۵ دقیقه‌ای هم
   هدف را لمس کرده و هم حد ضرر را، ترتیبش قابلِ دانستن نیست → بدترین حالت
   فرض می‌شود. همان قاعدهٔ ``conservative_both_touch`` که در تولید هست،
   اینجا به همهٔ سیاست‌های خروج تعمیم یافته. پس نتایج **کرانِ پایین**‌اند.
۵) **نمونه مستقل نیست.** ۷ نماد که ۶ تایشان دلاری است و سقفِ ریسکِ
   همبسته هم وجود ندارد. N مؤثر گزارش می‌شود و باید به آن نگاه کرد نه به N.

اجرا
----
    python tools/backtest_v029.py                # اجرای کامل + گزارش
    python tools/backtest_v029.py --cache-only   # فقط گرفتنِ داده (کش)
    python tools/backtest_v029.py --from-cache   # بدونِ شبکه، از کش
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import yfinance as yf                                    # noqa: E402

from src.analysis.strength import currency_strength      # noqa: E402
from src.analysis.technical import analyze_symbol        # noqa: E402
from src.config import load_config                       # noqa: E402
from src.data.base import MarketData                     # noqa: E402
from src.judge.scoring import (DEFAULTS, JudgeContext,   # noqa: E402
                               _deep_fill, judge_symbol)
from src.judge.session import market_status              # noqa: E402

CACHE = ROOT / "tools" / "_backtest_cache.json"
REPORT = ROOT / "tools" / "backtest_report.md"

H1, M15 = 60, 15          # دقیقه
WARMUP_H1_BARS = 400      # > 210 که EMA200 معتبر باشد
WARMUP_H4_BARS = 400


# ══════════════════════════════════════════════════════════════
#  داده
# ══════════════════════════════════════════════════════════════
def dl(ticker: str, interval: str, period: str):
    """دقیقاً هم‌نرمال‌سازیِ ``src/data/yahoo_source.py::_download``.

    مهم: ``tz_localize(None)`` — یعنی نمایهٔ naive-UTC. (همین باعث شد باگِ
    منطقهٔ زمانیِ v0.29 در مسیرِ واقعیِ تولید هم رخ بدهد، نه فقط در تئوری.)
    تنها تفاوت: کندلِ در حالِ تشکیل را *نمی‌اندازیم* — آن را در برشِ
    زمانیِ هر نقطهٔ تصمیم انجام می‌دهیم تا دقیقاً رفتارِ تولید بازسازی شود.
    """
    df = yf.download(ticker, period=period, interval=interval,
                     progress=False, auto_adjust=True)
    if df is None or df.empty:
        raise SystemExit(f"❌ داده‌ای برای {ticker} {interval} نیامد")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["Open", "High", "Low", "Close"]].dropna()
    if df.index.tz is not None:
        df.index = df.index.tz_convert("UTC").tz_localize(None)
    return df


def fetch_all(symbols: list) -> dict:
    out = {}
    for s in symbols:
        t0 = time.time()
        h1 = dl(s["yahoo"], "1h", "730d")
        m15 = dl(s["yahoo"], "15m", "60d")
        h4 = (h1.resample("4h")
                .agg({"Open": "first", "High": "max",
                      "Low": "min", "Close": "last"}).dropna())
        out[s["name"]] = {"h1": h1, "h4": h4, "m15": m15}
        print(f"  ✓ {s['name']:<8} H1={len(h1):>5}  H4={len(h4):>4}  "
              f"M15={len(m15):>5}  ({time.time() - t0:.1f}s)")
    return out


def to_cache(d: dict) -> dict:
    return {k: {tf: {"index": [t.isoformat() for t in v[tf].index],
                     "cols": {c: [float(x) for x in v[tf][c]]
                              for c in ("Open", "High", "Low", "Close")}}
                for tf in ("h1", "h4", "m15")}
            for k, v in d.items()}


def from_cache(raw: dict) -> dict:
    out = {}
    for sym, tfs in raw.items():
        out[sym] = {}
        for tf, blob in tfs.items():
            idx = pd.DatetimeIndex([datetime.fromisoformat(t) for t in blob["index"]])
            out[sym][tf] = pd.DataFrame(blob["cols"], index=idx)
    return out


# ══════════════════════════════════════════════════════════════
#  برشِ زمانی — بازسازیِ «چه چیزی در لحظهٔ T قابلِ دانستن بود»
# ══════════════════════════════════════════════════════════════
def slice_at(df: pd.DataFrame, t: datetime, interval_min: int, warmup: int):
    """کندل‌های بسته‌شده تا لحظهٔ t، به‌همینِ warmup تا.

    در تولید ``drop_forming_candle`` آخرین کندل را می‌اندازد. در لحظهٔ t،
    کندلِ در حالِ تشکیل نمایه‌اش ``floor(t, interval)`` است؛ پس آخرین کندلِ
    *بسته‌شده* نمایه‌اش ``floor(t) − interval`` است.
    """
    fl = t.replace(minute=(t.minute // interval_min) * interval_min,
                   second=0, microsecond=0)
    last_ok = fl - timedelta(minutes=interval_min)
    sub = df[df.index <= last_ok]
    return sub.tail(warmup) if len(sub) else sub


# ══════════════════════════════════════════════════════════════
#  سیاست‌های خروج
# ══════════════════════════════════════════════════════════════
@dataclass
class ExitResult:
    policy: str
    outcome: str          # TP | SL | BE | EXPIRED
    r: float              # ناخالص
    mfe_r: float = 0.0
    mae_r: float = 0.0
    bars_held: int = 0
    partial_taken: bool = False


def simulate(bars, direction: str, entry: float, sl: float, tp: float,
             risk: float, atr: float, expiry_bars: int, spread: float) -> dict:
    """یک معامله را روی کندل‌های M15 با چهار سیاستِ خروج جلو می‌برد.

    bars: فهرست (high, low) — فقط کندل‌های **پس از** ورود.
    ⚠️ ابهامِ درون‌کندلی همیشه به بدترین حالت حل می‌شود (همان فلسفهٔ
    ``conservative_both_touch``). یعنی نتایج کرانِ پایین‌اند.

    هزینه: ورود taker (نصفِ اسپرد) · هدف maker (بدون جریمه) · استاپ و
    سر‌به‌سر و انقضا taker. همان مدلِ ``tracker._net_r``.
    """
    sgn = 1.0 if direction == "BUY" else -1.0
    out = {}

    def _touch_tp(h, l):
        return (h >= tp) if direction == "BUY" else (l <= tp)

    def _touch_sl(h, l, slvl):
        return (l <= slvl) if direction == "BUY" else (h >= slvl)

    # ── MFE/MAE تا *لحظهٔ خروج*، نه تا انقضا ────────────────────
    # این دقیقاً کاری است که tracker._scan_bars در تولید می‌کند: اسکن تا
    # نخستین برخورد، و همان کندلِ خروج هم شامل می‌شود. نسخهٔ اولِ این
    # اسکریپت اشتباه کلِ پنجرهٔ ۴۸ ساعته را می‌پیمود و MAE تا −۵٫۸R
    # می‌داد که بی‌معنی بود (معامله در ۱−R بسته شده، پس هرگز بیشتر از
    # آن ندیده). خروجِ مرجع = سیاستِ A (همان تولیدِ فعلی).
    _i_exit = expiry_bars
    for _i, (h, l) in enumerate(bars[:expiry_bars]):
        if _touch_sl(h, l, sl) or _touch_tp(h, l):
            _i_exit = _i
            break
    mfe, mae = 0.0, 0.0
    for h, l in bars[:_i_exit + 1]:
        fav = sgn * (h - entry) / risk
        adv = sgn * (l - entry) / risk
        mfe = max(mfe, fav)
        mae = min(mae, adv)
    mfe = max(0.0, mfe)          # قراردادِ استاندارد: mfe ≥ ۰
    mae = min(0.0, mae)          # و mae ≤ ۰

    def net(gross: float, taker_exits: int) -> float:
        if spread <= 0 or risk <= 0:
            return gross
        return gross - (0.5 + 0.5 * taker_exits) * spread / risk

    # ── سیاست A: هدفِ ثابتِ ۲R (تولیدِ فعلی) ──────────────────
    res = None
    for i, (h, l) in enumerate(bars[:expiry_bars]):
        hit_tp = _touch_tp(h, l)
        hit_sl = _touch_sl(h, l, sl)
        if hit_tp and hit_sl:
            res = ("SL", -1.0, i, 1); break          # بدبینانه
        if hit_tp:
            res = ("TP", sgn * (tp - entry) / risk, i, 1); break
        if hit_sl:
            res = ("SL", -1.0, i, 1); break
    if res is None:
        h, l = bars[min(expiry_bars, len(bars)) - 1] if bars else (entry, entry)
        c = (h + l) / 2
        res = ("EXPIRED", sgn * (c - entry) / risk, expiry_bars, 1)
    out["A_static_2R"] = ExitResult("A", res[0], res[1], mfe, mae, res[2])

    # ── سیاست B: سر‌به‌سر در ۱R ───────────────────────────────
    cur_sl, armed, res = sl, False, None
    for i, (h, l) in enumerate(bars[:expiry_bars]):
        trig = entry + sgn * risk
        hit_trig = (h >= trig) if direction == "BUY" else (l <= trig)
        eff_sl = entry if armed else cur_sl
        hit_sl = (l <= eff_sl) if direction == "BUY" else (h >= eff_sl)
        hit_tp = (h >= tp) if direction == "BUY" else (l <= tp)
        if hit_sl and (hit_tp or hit_trig):
            # بدبینانه: استاپ اول خورده
            r = 0.0 if armed else -1.0
            res = ("BE" if armed else "SL", r, i, 1); break
        if hit_trig and not armed:
            armed = True                              # از کندلِ بعد مؤثر
            if hit_tp:
                res = ("TP", sgn * (tp - entry) / risk, i, 1); break
            continue
        if hit_tp:
            res = ("TP", sgn * (tp - entry) / risk, i, 1); break
        if hit_sl:
            res = ("BE" if armed else "SL", 0.0 if armed else -1.0, i, 1); break
    if res is None:
        h, l = bars[min(expiry_bars, len(bars)) - 1] if bars else (entry, entry)
        res = ("EXPIRED", sgn * (((h + l) / 2) - entry) / risk, expiry_bars, 1)
    out["B_breakeven_1R"] = ExitResult("B", res[0], res[1], mfe, mae, res[2])

    # ── سیاست C: برداشتِ ۵۰٪ در ۱R + سر‌به‌سر روی باقی ─────────
    armed, took, res = False, False, None
    for i, (h, l) in enumerate(bars[:expiry_bars]):
        trig = entry + sgn * risk
        hit_trig = (h >= trig) if direction == "BUY" else (l <= trig)
        eff_sl = entry if armed else sl
        hit_sl = (l <= eff_sl) if direction == "BUY" else (h >= eff_sl)
        hit_tp = (h >= tp) if direction == "BUY" else (l <= tp)
        if hit_sl and (hit_tp or hit_trig):
            r = (0.5 * 1.0 + 0.0) if armed else -1.0
            res = ("BE" if armed else "SL", r, i, 1); break
        if hit_trig and not armed:
            armed = took = True
            if hit_tp:
                res = ("TP", 0.5 * 1.0 + 0.5 * sgn * (tp - entry) / risk, i, 1); break
            continue
        if hit_tp:
            r = (0.5 * 1.0 + 0.5 * sgn * (tp - entry) / risk) if took \
                else sgn * (tp - entry) / risk
            res = ("TP", r, i, 1); break
        if hit_sl:
            r = (0.5 * 1.0) if took else -1.0
            res = ("BE" if took else "SL", r, i, 1); break
    if res is None:
        h, l = bars[min(expiry_bars, len(bars)) - 1] if bars else (entry, entry)
        base = sgn * (((h + l) / 2) - entry) / risk
        res = ("EXPIRED", (0.5 * 1.0 + 0.5 * base) if took else base, expiry_bars, 1)
    out["C_partial_1R"] = ExitResult("C", res[0], res[1], mfe, mae, res[2],
                                     partial_taken=took)

    # ── سیاست D: دنباله‌روِ ATR (چاندلیه، ۲×ATR) ──────────────
    if atr > 0:
        best, res = entry, None
        for i, (h, l) in enumerate(bars[:expiry_bars]):
            best = max(best, h) if direction == "BUY" else min(best, l)
            trail = (best - sgn * 2.0 * atr)
            eff_sl = trail if (sgn * (trail - sl) > 0) else sl   # هرگز بدتر نشو
            hit_sl = (l <= eff_sl) if direction == "BUY" else (h >= eff_sl)
            hit_tp = (h >= tp) if direction == "BUY" else (l <= tp)
            if hit_sl and hit_tp:
                res = ("SL", sgn * (eff_sl - entry) / risk, i, 1); break
            if hit_tp:
                res = ("TP", sgn * (tp - entry) / risk, i, 1); break
            if hit_sl:
                res = ("TRAIL", sgn * (eff_sl - entry) / risk, i, 1); break
        if res is None:
            h, l = bars[min(expiry_bars, len(bars)) - 1] if bars else (entry, entry)
            res = ("EXPIRED", sgn * (((h + l) / 2) - entry) / risk, expiry_bars, 1)
        out["D_trail_2ATR"] = ExitResult("D", res[0], res[1], mfe, mae, res[2])

    for k, v in out.items():
        taker = 0 if v.outcome == "TP" else 1
        v.__dict__["net_r"] = net(v.r, taker)
    return out


# ══════════════════════════════════════════════════════════════
#  حلقهٔ اصلی
# ══════════════════════════════════════════════════════════════
def run(data: dict, cfg: dict, verbose: bool = True) -> list:
    acfg = cfg["analysis"]
    syms = cfg["symbols"]
    jcfg = _deep_fill(DEFAULTS, cfg.get("judge"))
    # ⚠️ آستانه را عمداً به ۱ پایین می‌آوریم — نه برای تقلب، بلکه چون
    # judge_symbol دروازهٔ استراتژی را *بعد از* آستانهٔ امتیاز ارزیابی
    # می‌کند. با آستانهٔ تولید (۷) و سقفِ ۷ امتیازِ این بازپخش، ۱۰۷۰ از
    # ۱۰۸۳ نامزد LOW_SCORE رد می‌شدند و j.strategies هرگز پر نمی‌شد →
    # دروازهٔ توافق غیرقابلِ سنجش بود (نخستین اجرا n_prop=0 برای ۹۹٫۸٪
    # داد که یک مصنوعِ اسکریپت بود نه واقعیت).
    # حالا هر نامزدی که وتو نشود، امتیازِ *واقعی* و نظرِ هر سه استراتژی را
    # ثبت می‌کند؛ آستانه و دروازه بعداً post-hoc جاروب می‌شوند. این
    # سخت‌گیرانه‌تر است نه آسان‌تر: هیچ سیگنالی را که داور رد می‌کرد
    # «قابل‌قبول» حساب نمی‌کنیم، فقط اطلاعاتِ بیشتری نگه می‌داریم.
    jcfg["min_score"] = 1
    scfg_root = cfg.get("strategies") or {}
    spread_cfg = (jcfg.get("risk") or {}).get("spread") or {}
    per_sym = spread_cfg.get("per_symbol") or {}
    def_spread = float(spread_cfg.get("default_pips", 0.0))

    # استراتژی‌ها از مسیرِ registry — همان که تولید استفاده می‌کند
    from src.plugins.strategies import plugins as strat_plugins
    strategy_rules = []
    # ⚠️ StrategyAdapter(key, cfg) خودِ cfg["strategies"][key] را بیرون
    # می‌کشد — پس باید **کلِ config** داده شود، نه زیربخشِ استراتژی.
    # (نخستین اجرا این را اشتباه داشت: _scfg خالی شد → carry بدونِ جدول
    # نرخ → همیشه بی‌نظر → دروازهٔ توافق تقریباً همه را رد کرد. باگ از
    # اسکریپت بود نه از سیستم.)
    for _man, fac in strat_plugins():
        strategy_rules.append(fac({"cfg": cfg}))
    if verbose:
        print(f"  استراتژی‌های تزریق‌شده: {[getattr(r, 'key', '?') for r in strategy_rules]}")

    # پنجرهٔ تصمیم: اشتراکِ M15 همهٔ نمادها
    m15_starts = [data[s["name"]]["m15"].index[0] for s in syms]
    m15_ends = [data[s["name"]]["m15"].index[-1] for s in syms]
    t_begin, t_end = max(m15_starts), min(m15_ends)
    if verbose:
        print(f"  پنجرهٔ بازپخش: {t_begin} → {t_end} "
              f"({(t_end - t_begin).days} روز)")

    # نقاط تصمیم: هر ساعتِ رُند
    points = pd.date_range(t_begin.ceil("h"), t_end, freq="1h")
    expiry_hours = float((cfg.get("journal") or {}).get("expiry_hours", 48))
    expiry_bars = int(expiry_hours * 4)

    trades = []
    t0 = time.time()
    for n, T in enumerate(points):
        T = T.to_pydatetime()
        # برشِ داده «تا آنچه در T قابلِ دانستن بود»
        cuts = {}
        ok = True
        for s in syms:
            nm = s["name"]
            h1 = slice_at(data[nm]["h1"], T, H1, WARMUP_H1_BARS)
            h4 = slice_at(data[nm]["h4"], T, 4 * H1, WARMUP_H4_BARS)
            m15 = slice_at(data[nm]["m15"], T, M15, 240)
            if len(h1) < 210 or len(h4) < 210 or len(m15) < 24:
                ok = False
                break
            cuts[nm] = MarketData(symbol=nm, m15=m15, h1=h1, h4=h4)
        if not ok:
            continue

        # رتبهٔ قدرتِ ارزها — از همان دادهٔ تاریخی، پس بازتولیدپذیر است
        try:
            ranking = currency_strength(cuts, lookback_h1=int(acfg.get("strength_lookback_h1", 24)))
        except Exception:
            ranking = []

        ctx = JudgeContext(jcfg=jcfg, acfg=acfg, symbols_cfg=syms,
                           ranking=ranking, tv_map={}, cal_snap=None,
                           news_snap=None, now=T.replace(tzinfo=timezone.utc),
                           status=market_status(T.replace(tzinfo=timezone.utc)),
                           event_veto_minutes=30.0, strategies_cfg=scfg_root)

        for s in syms:
            nm = s["name"]
            md = cuts[nm]
            try:
                a = analyze_symbol(s, md, acfg)
                j = judge_symbol(a, s, md, ctx, strategy_rules=strategy_rules)
            except Exception as e:
                if verbose:
                    print(f"    [!] {nm} @{T}: {type(e).__name__}: {e}")
                continue
            if j.reject_reason in ("VETO", "DATA", "NO_SETUP", "DISABLED"):
                continue
            if j.direction not in ("BUY", "SELL"):
                continue
            # همهٔ نامزدها ثبت می‌شوند تا جاروبِ آستانه ممکن شود
            agreeing = [v for v in (j.strategies or [])
                        if v.get("direction") == j.direction]
            n_prop = sum(1 for v in agreeing if v.get("proposes"))
            pip = float(s["pip"])
            risk_pips = (j.signal.risk_pips if j.signal else
                         abs(a.price - (a.support or a.price)) / pip)
            if j.signal is None:
                # LOW_SCORE / NO_STRATEGY / CAPPED — سطوح را برای بازپخش بساز
                from src.judge.scoring import compute_levels
                sl, tp, risk, _ = compute_levels(j.direction, a.exec_price or a.price,
                                                 a.atr, a.support, a.resistance,
                                                 jcfg["risk"])
                entry = a.exec_price or a.price
                atr = a.atr
                reject = j.reject_reason
                score = j.score
            else:
                sl, tp = j.signal.sl, j.signal.tp
                entry = j.signal.entry
                risk = abs(entry - sl)
                atr = a.atr
                reject = ""
                score = j.signal.score
            if risk <= 0:
                continue
            exec_ts = a.exec_ts
            m15_all = data[nm]["m15"]
            fwd = m15_all[m15_all.index >= exec_ts.replace(tzinfo=None)] \
                if exec_ts is not None else m15_all.iloc[0:0]
            bars = [(float(r.High), float(r.Low)) for _, r in fwd.iterrows()]
            if len(bars) < 4:
                continue
            spread = float(per_sym.get(nm, def_spread))
            pol = simulate(bars, j.direction, entry, sl, tp, risk, atr,
                           expiry_bars, spread * pip)
            # ── حالتِ معکوس: همان ستاپ در جهتِ مخالف ─────────────
            # آزمونِ مستقیمِ این فرضیه که «سیگنال تأخیری است»: اگر خلافِ
            # جهتِ پیشنهادی سودده‌تر باشد، یعنی ورودها *بعد از* تمام‌شدنِ
            # حرکت صادر می‌شوند. سطوح برای جهتِ مخالف از نو ساخته می‌شوند
            # (حمایت↔مقاومت جابه‌جا می‌شود) تا مقایسه منصفانه باشد.
            from src.judge.scoring import compute_levels as _cl
            opp = "SELL" if j.direction == "BUY" else "BUY"
            try:
                osl, otp, orisk, _oc = _cl(opp, entry, atr, a.support,
                                           a.resistance, jcfg["risk"])
            except Exception:
                osl, otp, orisk = None, None, 0.0
            pol_opp = (simulate(bars, opp, entry, osl, otp, orisk, atr,
                                expiry_bars, spread * pip)
                       if (orisk and orisk > 0) else {})
            trades.append({
                "ts": T.isoformat(), "symbol": nm, "direction": j.direction,
                "score": int(score), "reject": reject,
                "n_agree": len(agreeing), "n_prop": int(n_prop),
                "entry": entry, "sl": sl, "tp": tp, "risk": risk,
                "risk_pips": risk / pip, "session": ctx.status.label,
                # v0.29.1: تشخیصی — برای آزمودنِ وزنِ هر مدرک
                "evidences": {e.key: e.points for e in (j.evidences or [])},
                "ev_max": {e.key: e.max_points for e in (j.evidences or [])},
                "adx": float(a.adx), "rsi": float(a.rsi),
                "atr_pips": (atr / pip) if pip else 0.0,
                "hour_utc": T.hour,
                "opp_dir": opp,
                "opp_risk_pips": (orisk / pip) if (pip and orisk) else 0.0,
                "policies": {k: {"outcome": v.outcome, "r": v.r,
                                 "net_r": v.__dict__.get("net_r", v.r),
                                 "mfe_r": v.mfe_r, "mae_r": v.mae_r,
                                 "bars_held": v.bars_held,
                                 "partial": v.partial_taken}
                             for k, v in pol.items()},
                "opp_policies": {k: {"outcome": v.outcome, "r": v.r,
                                     "net_r": v.__dict__.get("net_r", v.r)}
                                 for k, v in pol_opp.items()},
            })
        if verbose and (n + 1) % 100 == 0:
            print(f"    … {n + 1}/{len(points)} نقطهٔ تصمیم، "
                  f"{len(trades)} نامزد ({time.time() - t0:.0f}s)")

    if verbose:
        print(f"  ✅ {len(trades)} نامزد در {len(points)} نقطهٔ تصمیم "
              f"({time.time() - t0:.0f}s)")
    return trades


# ══════════════════════════════════════════════════════════════
#  تحلیل
# ══════════════════════════════════════════════════════════════
POLICY_FA = {
    "A_static_2R": "A · هدفِ ثابتِ ۲R (تولیدِ فعلی)",
    "B_breakeven_1R": "B · سر‌به‌سر در ۱R",
    "C_partial_1R": "C · برداشتِ ۵۰٪ در ۱R + سر‌به‌سر",
    "D_trail_2ATR": "D · دنباله‌روِ ۲×ATR",
}


def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return (None, None)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (c - h, c + h)


def median(v):
    if not v:
        return None
    s = sorted(v)
    n = len(s)
    m = n // 2
    return s[m] if n % 2 else (s[m - 1] + s[m]) / 2


def pctile(v, q):
    """صدکِ q (۰..۱) با درون‌یابیِ خطی — نه «میانهٔ نیمهٔ بالا»."""
    if not v:
        return None
    s = sorted(v)
    if len(s) == 1:
        return s[0]
    idx = q * (len(s) - 1)
    lo, hi = int(math.floor(idx)), int(math.ceil(idx))
    if lo == hi:
        return s[lo]
    return s[lo] + (s[hi] - s[lo]) * (idx - lo)


def select(trades, min_score, gate, cooldown_min=180, max_per_point=3):
    """اعمالِ آستانه + دروازهٔ استراتژی + کول‌داون + سقفِ هر چرخه."""
    out, last = [], {}
    by_point = {}
    for t in trades:
        if t["score"] < min_score:
            continue
        if gate and t["n_prop"] < 1:
            continue
        by_point.setdefault(t["ts"], []).append(t)
    for ts in sorted(by_point):
        cands = sorted(by_point[ts], key=lambda x: -x["score"])
        picked = 0
        for t in cands:
            key = (t["symbol"], t["direction"])
            prev = last.get(key)
            if prev and (datetime.fromisoformat(ts) - prev) < timedelta(minutes=cooldown_min):
                continue
            if picked >= max_per_point:
                break
            out.append(t)
            last[key] = datetime.fromisoformat(ts)
            picked += 1
    return out


def stats_of(sel, policy):
    rs = [t["policies"][policy]["r"] for t in sel]
    ns = [t["policies"][policy]["net_r"] for t in sel]
    n = len(rs)
    if n == 0:
        return None
    wins = sum(1 for t in sel if t["policies"][policy]["outcome"] == "TP")
    return {"n": n, "wins": wins, "wr": wins / n,
            "avg_r": sum(rs) / n, "avg_net_r": sum(ns) / n,
            "total_r": sum(rs), "total_net_r": sum(ns),
            "ci": wilson(wins, n)}


def effective_n(sel):
    """N مؤثر: سیگنال‌های هم‌زمانِ هم‌جهت یک ارز = یک شرط.

    یک خوشه = همهٔ سیگنال‌های باز در یک بازهٔ ۴۸ ساعته که ارزِ مشترک
    (base یا quote) و جهتِ یکسان نسبت به آن ارز دارند. این تقریبِ محافظه‌کارانه
    است، نه دقیق.
    """
    ev = []
    for t in sel:
        ev.append((datetime.fromisoformat(t["ts"]), t["symbol"], t["direction"]))
    ev.sort()
    clusters, used = 0, set()
    for i, (t0, sym, d) in enumerate(ev):
        if i in used:
            continue
        clusters += 1
        used.add(i)
        cur = set(sym)
        for j in range(i + 1, len(ev)):
            if j in used:
                continue
            tj, sj, _ = ev[j]
            if (tj - t0) > timedelta(hours=48):
                break
            if set(sj) & cur:
                used.add(j)
                cur |= set(sj)
    return clusters


def fa_pct(v):
    return "—" if v is None else f"{v * 100:.0f}٪"


def fa_r(v):
    return "—" if v is None else f"{v:+.2f}"


# ══════════════════════════════════════════════════════════════
#  گزارش
# ══════════════════════════════════════════════════════════════
def build_report(trades: list, cfg: dict) -> str:
    L = []
    A = L.append
    syms = [s["name"] for s in cfg["symbols"]]
    spread_cfg = (cfg.get("judge", {}).get("risk") or {}).get("spread") or {}
    per_sym = spread_cfg.get("per_symbol") or {}

    ts_all = sorted({t["ts"] for t in trades})
    A("# 📊 بازپخشِ تاریخیِ v0.29 — نتیجه")
    A("")
    A(f"> تولیدشده: {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC")
    A(f"> پنجره: {ts_all[0][:10]} → {ts_all[-1][:10]} "
      f"({(datetime.fromisoformat(ts_all[-1]) - datetime.fromisoformat(ts_all[0])).days} روز)")
    A(f"> نقاطِ تصمیم: {len(ts_all)} (ساعتی) · نمادها: {len(syms)} · "
      f"نامزدهای خام: {len(trades)}")
    A("")
    A("## ⚠️ پیش از خواندنِ عددها")
    A("")
    A("۱. **فقط هستهٔ تکنیکال.** تقویم/اخبار/تریدینگ‌ویو برای گذشته قابلِ")
    A("   بازیابی نیستند → ۴ امتیاز از ۱۱ همیشه صفر و دو وتو غیرفعال.")
    A("   این **سیستمِ تولید نیست**، زیرمجموعهٔ خوش‌تعریفی از آن است.")
    A("   نتیجه دربارهٔ *هندسهٔ خروج* معتبر است، نه دربارهٔ داورِ کامل.")
    A(f"۲. **پنجره فقط {len(ts_all)} ساعت است** — یاهو کندلِ ۱۵ دقیقه را")
    A("   بیش از ~۶۰ روز نگه نمی‌دارد. «۶ ماه» ممکن نبود.")
    A("۳. **ابهامِ درون‌کندلی بدبینانه حل شده** → عددها کرانِ پایین‌اند.")
    A("۴. **اسپرد برآورد است** نه اسپردِ واقعیِ بروکرِ شما.")
    A("۵. **نمونه مستقل نیست** — N مؤثر را ببینید، نه N را.")
    A("")

    # ── خطِ پایه: همهٔ نامزدها، بدونِ هیچ گزینشی ───────────────
    A("## ۰) خطِ پایه — همهٔ نامزدها بدونِ گزینش")
    A("")
    A("این مهم‌ترین عددِ گزارش است. اگر سیستم لبه داشته باشد، گزینشِ بر")
    A("پایهٔ امتیاز باید آن را **بالای** این خط ببرد.")
    A("")
    oc = {}
    for t in trades:
        k = t["policies"]["A_static_2R"]["outcome"]
        oc[k] = oc.get(k, 0) + 1
    n_all = len(trades)
    tp, sl_, ex = oc.get("TP", 0), oc.get("SL", 0), oc.get("EXPIRED", 0)
    rs = [t["policies"]["A_static_2R"]["r"] for t in trades]
    ns = [t["policies"]["A_static_2R"]["net_r"] for t in trades]
    decisive = tp / (tp + sl_) if (tp + sl_) else None
    A(f"| سنجه | مقدار |")
    A(f"|---|---|")
    A(f"| نامزدها | {n_all} |")
    A(f"| هدف خورد (TP) | {tp} ({tp / n_all:.1%}) |")
    A(f"| حد ضرر (SL) | {sl_} ({sl_ / n_all:.1%}) |")
    A(f"| منقضی | {ex} ({ex / n_all:.1%}) |")
    A(f"| **نرخ بردِ قطعی** (TP ÷ (TP+SL)) | **{fa_pct(decisive)}** |")
    A(f"| expectancy ناخالص | {fa_r(sum(rs) / n_all)}R |")
    A(f"| expectancy خالص | {fa_r(sum(ns) / n_all)}R |")
    A("")
    A(f"> 🔎 **خطِ پایهٔ نظری:** برای هدفِ ۲R و حدِ ضررِ ۱R، یک راهِ")
    A(f"> تصادفیِ بی‌لبه نرخِ بردِ قطعیِ **۳۳٫۳٪** می‌دهد (۱ ÷ ۳).")
    A(f"> عددِ اندازه‌گیری‌شده: **{fa_pct(decisive)}**.")
    if decisive is not None:
        d = decisive - 1 / 3
        verdict = ("عملاً روی خطِ پایه است — یعنی **گزینشِ امتیاز، در این"
                   " پیکربندی، لبهٔ جهت‌دار اضافه نمی‌کند**"
                   if abs(d) < 0.03 else
                   ("بالاتر از خطِ پایه — نشانهٔ لبه" if d > 0
                    else "پایین‌تر از خطِ پایه — نشانهٔ *ضدِ* لبه"))
        A(f"> اختلاف: {d * 100:+.1f} نقطهٔ درصد → {verdict}.")
    A("")

    # ── جاروبِ آستانه × دروازه ────────────────────────────────
    A("## ۱) جاروبِ آستانهٔ امتیاز × دروازهٔ استراتژی")
    A("")
    A("چون سقفِ امتیاز در این بازپخش ۷ است (نه ۱۱)، آستانهٔ تولید (۷) یعنی")
    A("«هر پنج مدرکِ تکنیکال کامل». برای دیدنِ حساسیت، همهٔ آستانه‌ها آمده.")
    A("")
    for policy in ("A_static_2R",):
        A(f"**سیاستِ خروج: {POLICY_FA[policy]}**")
        A("")
        A("| آستانه | دروازه | N | نرخ برد | expectancy ناخالص | خالص | CI ۹۵٪ نرخ برد | N مؤثر |")
        A("|---|---|---|---|---|---|---|---|")
        for ms in (4, 5, 6, 7):
            for gate in (False, True):
                sel = select(trades, ms, gate)
                st = stats_of(sel, policy)
                if not st:
                    A(f"| {ms} | {'روشن' if gate else 'خاموش'} | ۰ | — | — | — | — | — |")
                    continue
                lo, hi = st["ci"]
                en = effective_n(sel)
                A(f"| {ms} | {'روشن' if gate else 'خاموش'} | {st['n']} | "
                  f"{fa_pct(st['wr'])} | {fa_r(st['avg_r'])}R | "
                  f"{fa_r(st['avg_net_r'])}R | [{lo * 100:.0f}٪, {hi * 100:.0f}٪] | {en} |")
        A("")

    # ── تشخیصِ دروازهٔ استراتژی ───────────────────────────────
    A("### توزیعِ توافقِ استراتژی‌ها (تشخیصِ دروازه)")
    A("")
    A("| n_prop (پیشنهاددهندهٔ هم‌جهت) | تعداد نامزد |")
    A("|---|---|")
    for k in sorted({t["n_prop"] for t in trades}):
        A(f"| {k} | {sum(1 for t in trades if t['n_prop'] == k)} |")
    A("")
    A("| n_agree (کلِ هم‌جهت‌ها) | تعداد نامزد |")
    A("|---|---|")
    for k in sorted({t["n_agree"] for t in trades}):
        A(f"| {k} | {sum(1 for t in trades if t['n_agree'] == k)} |")
    A("")

    # ── مقایسهٔ سیاست‌های خروج ────────────────────────────────
    A("## ۲) مقایسهٔ چهار سیاستِ خروج")
    A("")
    A("روی همان مجموعهٔ سیگنال (آستانهٔ ۵، دروازه خاموش — تا نمونه بزرگ‌تر")
    A("باشد؛ چون آستانهٔ ۷ در این بازپخش خیلی سخت‌گیرانه است).")
    A("")
    BASE_MS, BASE_GATE = 5, False
    sel = select(trades, BASE_MS, BASE_GATE)
    A(f"نمونه: **{len(sel)} سیگنال** · N مؤثر: **{effective_n(sel)}**")
    A("")
    A("| سیاست | نرخ برد | expectancy ناخالص | **خالص** | مجموع R | بهترین؟ |")
    A("|---|---|---|---|---|---|")
    rows = []
    for p in POLICY_FA:
        st = stats_of(sel, p)
        if st:
            rows.append((p, st))
    best = max(rows, key=lambda r: r[1]["avg_net_r"]) if rows else None
    for p, st in rows:
        mark = "✅" if best and p == best[0] else ""
        A(f"| {POLICY_FA[p]} | {fa_pct(st['wr'])} | {fa_r(st['avg_r'])}R | "
          f"**{fa_r(st['avg_net_r'])}R** | {st['total_net_r']:+.1f}R | {mark} |")
    A("")

    # ── MFE/MAE ───────────────────────────────────────────────
    A("## ۳) نوسانِ درونِ معامله — دادهٔ لازم برای تصمیم")
    A("")
    p0 = "A_static_2R"
    mfes = [t["policies"][p0]["mfe_r"] for t in sel]
    maes = [t["policies"][p0]["mae_r"] for t in sel]
    A(f"| سنجه | مقدار |")
    A(f"|---|---|")
    A(f"| میانهٔ MFE (بیشینهٔ سودِ دیده‌شده) | {fa_r(median(mfes))}R |")
    A(f"| میانهٔ MAE (بیشینهٔ زیانِ دیده‌شده) | {fa_r(median(maes))}R |")
    A(f"| صدکِ ۷۵ MFE | {fa_r(pctile(mfes, 0.75))}R |")
    A(f"| صدکِ ۲۵ MAE | {fa_r(pctile(maes, 0.25))}R |")
    A(f"| صدکِ ۱۰ MAE (بدترین حرارت) | {fa_r(pctile(maes, 0.10))}R |")
    A("")
    reach = {}
    for lvl in (0.5, 1.0, 1.5, 2.0):
        reach[lvl] = sum(1 for m in mfes if m >= lvl) / len(mfes) if mfes else 0
    A("**سهمِ معامله‌هایی که حداقل تا این سطح به نفع ما رفتند:**")
    A("")
    A("| سطح | سهم |")
    A("|---|---|")
    for lvl, v in reach.items():
        A(f"| ≥ {lvl:.1f}R | {fa_pct(v)} |")
    A("")
    A("→ اگر سهمِ «≥۲٫۰R» پایین باشد، هدفِ ۲R زیادی دور است و سیاست‌های")
    A("  B/C/D باید بهتر از A باشند. اگر بالا باشد، A درست است.")
    A("")

    # دو نیمهٔ معادلهٔ سر‌به‌سر
    losers = [t for t in sel if t["policies"][p0]["outcome"] == "SL"]
    winners = [t for t in sel if t["policies"][p0]["outcome"] == "TP"]
    ls = sum(1 for t in losers if t["policies"][p0]["mfe_r"] >= 1.0)
    wd = sum(1 for t in winners if t["policies"][p0]["mae_r"] <= -1.0)
    A("**دو نیمهٔ معادلهٔ «سر‌به‌سر در ۱R» — باید با هم خوانده شوند:**")
    A("")
    A(f"- از {len(losers)} باخت، **{ls} مورد** ({fa_pct(ls / len(losers) if losers else None)})")
    A(f"  اول به ۱R+ رسیده بودند → سر‌به‌سر نجاتشان می‌داد")
    A(f"- از {len(winners)} برد، **{wd} مورد** ({fa_pct(wd / len(winners) if winners else None)})")
    A(f"  وسطِ راه ۱R علیه‌شان رفت → سر‌به‌سر همان‌ها را می‌کُشت")
    A("")

    # ── تفکیک‌ها ──────────────────────────────────────────────
    A("## ۴) تفکیک‌ها (سیاستِ A)")
    A("")
    A("### به تفکیک نماد")
    A("")
    A("| نماد | N | نرخ برد | expectancy خالص |")
    A("|---|---|---|---|")
    for nm in syms:
        sub = [t for t in sel if t["symbol"] == nm]
        st = stats_of(sub, p0)
        A(f"| {nm} | {len(sub)} | {fa_pct(st['wr']) if st else '—'} | "
          f"{fa_r(st['avg_net_r']) + 'R' if st else '—'} |")
    A("")
    A("### به تفکیک جهت")
    A("")
    A("| جهت | N | نرخ برد | expectancy خالص |")
    A("|---|---|---|---|")
    for d in ("BUY", "SELL"):
        sub = [t for t in sel if t["direction"] == d]
        st = stats_of(sub, p0)
        A(f"| {d} | {len(sub)} | {fa_pct(st['wr']) if st else '—'} | "
          f"{fa_r(st['avg_net_r']) + 'R' if st else '—'} |")
    A("")
    A("### به تفکیک امتیاز")
    A("")
    A("| امتیاز | N | نرخ برد | expectancy خالص |")
    A("|---|---|---|---|")
    for sc in sorted({t["score"] for t in sel}):
        sub = [t for t in sel if t["score"] == sc]
        st = stats_of(sub, p0)
        A(f"| {sc} | {len(sub)} | {fa_pct(st['wr']) if st else '—'} | "
          f"{fa_r(st['avg_net_r']) + 'R' if st else '—'} |")
    A("")
    A("> اگر امتیازِ بالاتر نرخِ بردِ بهتری نمی‌دهد، جدولِ امتیاز وزنِ غلط")
    A("> دارد — این همان آزمونی است که خودِ کارنامه هم پیشنهاد می‌دهد.")
    A("")

    # ── همبستگی ───────────────────────────────────────────────
    A("## ۵) همبستگی و N مؤثر")
    A("")
    n_raw = len(sel)
    n_eff = effective_n(sel)
    A(f"- سیگنال‌ها: **{n_raw}**")
    A(f"- خوشه‌های مستقلِ تقریبی: **{n_eff}** "
      f"(نسبت {n_eff / n_raw:.0%})" if n_raw else "- نمونه خالی")
    if n_raw:
        lo, hi = wilson(sum(1 for t in sel if t["policies"][p0]["outcome"] == "TP"), n_raw)
        lo2, hi2 = wilson(int(round((sum(1 for t in sel if t["policies"][p0]["outcome"] == "TP") / n_raw) * n_eff)), n_eff)
        A(f"- CI ۹۵٪ نرخ برد اگر همه مستقل بودند: [{lo * 100:.0f}٪, {hi * 100:.0f}٪]")
        A(f"- CI ۹۵٪ با N مؤثر = {n_eff}: **[{lo2 * 100:.0f}٪, {hi2 * 100:.0f}٪]** ← این واقع‌بینانه است")
        A("")
        A("> اگر این بازه از صفر تا ۱۰۰٪ را پوشش می‌دهد، یعنی این نمونه")
        A("> **هیچ چیزی را اثبات نمی‌کند** — نه سودآوری را، نه زیان‌دهی را.")
    A("")
    A("---")
    A("")
    A("*این گزارش یک برآوردِ بدبینانه روی دادهٔ واقعی است، نه وعده. هیچ")
    A("سیستمی سود را تضمین نمی‌کند.*")
    return "\n".join(L) + "\n"


# ══════════════════════════════════════════════════════════════
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-only", action="store_true")
    ap.add_argument("--from-cache", action="store_true")
    ap.add_argument("--out", default=str(REPORT))
    args = ap.parse_args()

    cfg = load_config(str(ROOT / "config.yaml"))
    syms = cfg["symbols"]

    print("═" * 64)
    print("بازپخشِ تاریخیِ v0.29")
    print("═" * 64)

    if args.from_cache and CACHE.exists():
        print("📦 خواندن از کش…")
        data = from_cache(json.loads(CACHE.read_text(encoding="utf-8")))
    else:
        print("🌐 گرفتنِ داده از Yahoo (H1 دو سال + M15 شصت روز)…")
        data = fetch_all(syms)
        CACHE.write_text(json.dumps(to_cache(data)), encoding="utf-8")
        print(f"  💾 کش: {CACHE.name} ({CACHE.stat().st_size / 1e6:.1f} MB)")
        if args.cache_only:
            return 0

    print()
    print("⏳ حلقهٔ بازپخش (ساعت‌به‌ساعت، بدونِ نگاه به آینده)…")
    trades = run(data, cfg)
    if not trades:
        print("❌ هیچ نامزدی تولید نشد")
        return 1

    (ROOT / "tools" / "_backtest_trades.json").write_text(
        json.dumps(trades, ensure_ascii=False), encoding="utf-8")
    print(f"  💾 {len(trades)} نامزد در tools/_backtest_trades.json")

    print()
    print("📝 ساختِ گزارش…")
    rep = build_report(trades, cfg)
    Path(args.out).write_text(rep, encoding="utf-8")
    print(f"  ✅ {args.out}")
    print()
    print(rep)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
