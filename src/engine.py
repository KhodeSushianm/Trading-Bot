# -*- coding: utf-8 -*-
"""موتور ربات — مستقل از رابط کاربری.

سه کار اصلی:
  run_cycle()           یک چرخه کامل (داده ← تحلیل ← تاییدیه TV ← تقویم ← اخبار
                        ← ⚖️ داور امتیازدهی ← سیگنال ← گزارش ← تلگرام ← لاگ فایل)
  run_briefing()        بریفینگ صبحگاهی (گزارش مستقل، قبل از باز شدن لندن)
  check_event_alerts()  هشدار ۳۰ دقیقه قبل از هر رویداد پراثر (با حافظهٔ «قبلاً فرستادم»)

  BotLoop()             زمان‌بند پس‌زمینه: هر سه کار بالا را در thread جدا مدیریت می‌کند

هم پنل گرافیکی و هم main.py (خط فرمان) از همین موتور استفاده می‌کنند.
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from . import app_paths
from .analysis.strength import currency_strength
from .analysis.technical import analyze_symbol
from .config import load_config
from .data import get_source
from .data.tradingview import fetch_tv_snapshot
from .fa import fa_num
from .fundamental.calendar import fetch_calendar, veto_for_symbol
from .fundamental.news import fetch_news
from .judge.scoring import JudgeContext, judge_all, judge_config
from .judge.session import market_status
from .notify import telegram
from .report.console import render_report
from .report.fundamental import render_briefing, render_event_alert
from .report.signal import render_judge_summary, render_signal

LogFn = Callable[[str], None]


def _noop(_: str) -> None:
    pass


# ══════════════════════════════════════════════════════════════
#  جمع‌آوری داده
# ══════════════════════════════════════════════════════════════
def _collect_market(cfg: dict, log: LogFn, with_tv: bool = True) -> dict:
    """گرفتن کندل‌ها + تحلیل تکنیکال + قدرت ارزها + تاییدیه تریدینگ‌ویو."""
    out = {"analyses": [], "datasets": {}, "ranking": [], "tv_map": {}, "tv_tf": "4h",
           "source_name": "—", "errors": 0}
    try:
        source = get_source(cfg)
        source.connect()
    except Exception as e:
        log(f"❌ اتصال به منبع داده ناموفق: {str(e)[:120]}")
        out["errors"] = 1
        return out
    out["source_name"] = source.name

    try:
        total = len(cfg["symbols"])
        for i, sym_cfg in enumerate(cfg["symbols"], 1):
            if total > 1:
                log(f"📡 دریافت و تحلیل {sym_cfg['name']} ({i}/{total})...")
            try:
                md = source.fetch(sym_cfg)
                if md is None:
                    out["errors"] += 1
                    continue
                out["datasets"][sym_cfg["name"]] = md
                out["analyses"].append(analyze_symbol(sym_cfg, md, cfg["analysis"]))
            except Exception as e:
                out["errors"] += 1
                log(f"[!] خطا در {sym_cfg['name']}: {str(e)[:100]}")
    finally:
        source.disconnect()

    if not out["analyses"]:
        log("❌ هیچ نمادی تحلیل نشد — اینترنت/تنظیمات را بررسی کنید")
        out["errors"] = max(out["errors"], 1)
        return out

    log(f"✅ تحلیل {len(out['analyses'])} نماد انجام شد")
    out["ranking"] = currency_strength(
        out["datasets"], lookback_h1=int(cfg["analysis"].get("strength_lookback_h1", 24)))

    tv_cfg = cfg.get("tradingview") or {}
    out["tv_tf"] = str(tv_cfg.get("timeframe", "4h"))
    if with_tv and tv_cfg.get("enabled", True):
        log("🔍 دریافت تاییدیه تریدینگ‌ویو...")
        try:
            out["tv_map"] = fetch_tv_snapshot(cfg["symbols"], timeframe=out["tv_tf"])
            log(f"✅ تاییدیه تریدینگ‌ویو برای {len(out['tv_map'])} نماد دریافت شد")
        except Exception as e:
            log(f"[!] تاییدیه تریدینگ‌ویو ناموفق: {str(e)[:90]}")
    return out


def _collect_fundamental(cfg: dict, log: LogFn) -> tuple:
    """تقویم اقتصادی + اخبار. هیچ‌وقت استثنا پرتاب نمی‌کند."""
    fcfg = cfg.get("fundamental") or {}
    ncfg = cfg.get("news") or {}
    cal_snap = news_snap = None
    if fcfg.get("enabled", True):
        try:
            cal_snap = fetch_calendar(cfg, on_log=log)
        except Exception as e:                       # لایهٔ اطمینان آخر
            log(f"[!] خطای غیرمنتظره در تقویم اقتصادی: {str(e)[:90]}")
    else:
        log("[i] موتور فاندامنتال (تقویم اقتصادی) در تنظیمات غیرفعال است")
    if ncfg.get("enabled", True):
        try:
            news_snap = fetch_news(cfg, on_log=log)
        except Exception as e:
            log(f"[!] خطای غیرمنتظره در موتور اخبار: {str(e)[:90]}")
    else:
        log("[i] موتور اخبار در تنظیمات غیرفعال است")
    return cal_snap, news_snap


def _horizon_hours(cfg: dict) -> float:
    """بازهٔ نمایش رویدادهای تقویم در گزارش."""
    return float((cfg.get("fundamental") or {}).get("horizon_hours", 48))


def _compute_vetoes(cfg: dict, cal_snap, analyses, now: datetime, log: LogFn) -> dict:
    """دروازه وتو: کدام نمادها به‌خاطر رویداد پراثرِ نزدیک، سیگنال نمی‌گیرند."""
    vetoes: dict[str, list] = {}
    if cal_snap is None or not cal_snap.ok:
        return vetoes
    minutes = float((cfg.get("fundamental") or {}).get("veto_minutes_before", 30))
    for a in analyses:
        evs = veto_for_symbol(cal_snap, a.base, a.quote, now, minutes=minutes)
        if evs:
            vetoes[a.symbol] = evs
    if vetoes:
        names = "، ".join(vetoes)
        log(f"🚫 وتوی خبری فعال برای: {names} (رویداد پراثر در {int(minutes)} دقیقهٔ آینده)")
    return vetoes


def _archive(text: str, filename: str = "reports.log") -> None:
    """بایگانی گزارش در فایل (برای مرور بعدی)."""
    try:
        with open(app_paths.logs_dir() / filename, "a", encoding="utf-8") as f:
            f.write(f"\n\n{'#' * 70}\n# {datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} UTC\n"
                    f"{'#' * 70}\n{text}\n")
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════
#  وضعیت سیگنال‌ها: جلوگیری از اسپم + ژورنال (پایهٔ مرحله ۴)
# ══════════════════════════════════════════════════════════════
SIGNAL_STATE_FILE = "sent_signals.json"
SIGNAL_JOURNAL = "signals.jsonl"


def _load_signal_state() -> dict:
    try:
        with open(app_paths.cache_dir() / SIGNAL_STATE_FILE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save_signal_state(state: dict, keep_days: int = 14) -> None:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=keep_days)).isoformat()
    pruned = {k: v for k, v in state.items()
              if isinstance(v, dict) and str(v.get("ts", "")) >= cutoff}
    try:
        with open(app_paths.cache_dir() / SIGNAL_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(pruned, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


def should_send_signal(state: dict, sig, jcfg: dict,
                       now: Optional[datetime] = None) -> tuple[bool, str]:
    """آیا این سیگنال را به تلگرام بفرستیم یا تکراری است؟

    حلقهٔ ربات هر ۱۵ دقیقه اجرا می‌شود؛ بدون این کنترل، یک ستاپِ چندساعته
    ده‌ها بار پشت‌هم ارسال می‌شد. قاعده:
      • بار اول → بفرست
      • در پنجرهٔ cooldown (پیش‌فرض ۱۸۰ دقیقه) → نفرست، مگر اینکه امتیاز
        حداقل `resend_score_gain` واحد بهتر شده باشد (یعنی مدارک قوی‌تر شده‌اند)
    """
    now = now or datetime.now(timezone.utc)
    key = f"{sig.symbol}|{sig.direction}"
    prev = state.get(key)
    cooldown = float(jcfg.get("resend_cooldown_minutes", 180))
    gain = int(jcfg.get("resend_score_gain", 2))
    if not isinstance(prev, dict):
        return True, ""
    try:
        last = datetime.fromisoformat(str(prev["ts"]))
    except Exception:
        return True, ""
    age_min = (now - last).total_seconds() / 60.0
    if age_min >= cooldown:
        return True, ""
    delta = sig.score - int(prev.get("score", 0))
    if delta >= gain:
        return True, f"امتیاز {fa_num(delta)} واحد بهتر از دفعهٔ قبل شد"
    return False, (f"همین سیگنال {fa_num(int(age_min))} دقیقه پیش فرستاده شد — "
                   f"تا {fa_num(int(cooldown - age_min))} دقیقهٔ دیگر تکرارش نمی‌کنیم")


def journal_signal(sig, sent: bool) -> None:
    """ثبت سیگنال در logs/signals.jsonl — مرحلهٔ ۴ نتیجه‌اش را پیگیری می‌کند."""
    try:
        with open(app_paths.logs_dir() / SIGNAL_JOURNAL, "a", encoding="utf-8") as f:
            f.write(json.dumps(sig.to_journal(sent=sent), ensure_ascii=False) + "\n")
    except Exception:
        pass


def _send_telegram(cfg: dict, text: str, log: LogFn, label: str = "گزارش") -> tuple[bool, str]:
    tg = cfg.get("telegram") or {}
    token = str(tg.get("bot_token") or "").strip()
    chat_id = str(tg.get("chat_id") or "").strip()
    if not (tg.get("send_reports", True) and token and chat_id):
        log(f"[i] تلگرام تنظیم نشده — {label} فقط در پنل/کنسول نمایش داده می‌شود")
        return False, "تنظیم نشده"
    log(f"📱 ارسال {label} به تلگرام...")
    ok, msg = telegram.send_message(token, chat_id, text)
    log(("✅ " if ok else "❌ ") + f"تلگرام: {msg}")
    return ok, msg


# ══════════════════════════════════════════════════════════════
#  چرخه تحلیل (گزارش دوره‌ای)
# ══════════════════════════════════════════════════════════════
def run_cycle(cfg: Optional[dict] = None, on_log: LogFn = _noop,
              now_override: Optional[datetime] = None) -> dict:
    """یک چرخه کامل تحلیل.

    Args:
        now_override: زمان فرضی برای داور/تقویم/سشن (حالت شبیه‌سازی).
                      دادهٔ بازار واقعی است، فقط «الان کی است» عوض می‌شود —
                      برای دیدن رفتار داور در روز کاری وقتی بازار بسته است.
                      در این حالت گزارش با برچسب ⚠️ شبیه‌سازی مشخص می‌شود.

    Returns:
        dict با کلیدهای: ok, report, errors, telegram, elapsed, vetoes,
                         calendar_ok, news_count, judgments, signals, simulated
    """
    t0 = time.time()
    cfg = cfg or load_config()
    result = {"ok": False, "report": "", "errors": 0, "telegram": (False, ""),
              "elapsed": 0.0, "vetoes": {}, "calendar_ok": False, "news_count": 0,
              "judgments": 0, "signals": []}

    def log(msg: str) -> None:
        on_log(f"[{datetime.now():%H:%M:%S}] {msg}")

    mkt = _collect_market(cfg, log)
    if not mkt["analyses"]:
        result["errors"] = max(mkt["errors"], 1)
        return result

    cal_snap, news_snap = _collect_fundamental(cfg, log)
    now = now_override or datetime.now(timezone.utc)
    simulated = now_override is not None
    if simulated:
        log(f"⚠️ حالت شبیه‌سازی: زمان فرضی {now:%Y-%m-%d %H:%M} UTC "
            f"(دادهٔ بازار واقعی است، ساعت داور عوض شده)")
    vetoes = _compute_vetoes(cfg, cal_snap, mkt["analyses"], now, log)

    # ── ⚖️ داور امتیازدهی (مرحله ۳) ───────────────────────────
    jcfg = judge_config(cfg)
    judgments, signals, judge_summary = [], [], ""
    if jcfg.get("enabled", True):
        ctx = JudgeContext(
            jcfg=jcfg, acfg=cfg["analysis"], symbols_cfg=cfg["symbols"],
            ranking=mkt["ranking"], tv_map=mkt["tv_map"],
            cal_snap=cal_snap, news_snap=news_snap, now=now,
            status=market_status(now),
            # منبع حقیقتِ پنجرهٔ وتو همان تنظیم مرحله ۲ است، نه یک عدد دوم
            event_veto_minutes=float((cfg.get("fundamental") or {})
                                     .get("veto_minutes_before", 30)),
        )
        judgments = judge_all(mkt["analyses"], mkt["datasets"], ctx)
        signals = [j.signal for j in judgments if j.signal]
        log(f"⚖️ داور: {len(signals)} سیگنال صادر شد 🎯" if signals
            else "⚖️ داور: هیچ سیگنالی صادر نشد (دلیل هر نماد در گزارش هست)")
        judge_summary = render_judge_summary(
            judgments, min_score=int(jcfg.get("min_score", 7)), now=now)
    else:
        log("[i] داور امتیازدهی در تنظیمات غیرفعال است")

    report = render_report(
        mkt["analyses"], mkt["ranking"], mkt["source_name"],
        tv_map=mkt["tv_map"], tv_tf=mkt["tv_tf"],
        cal_snap=cal_snap, news_snap=news_snap,
        symbols_cfg=cfg["symbols"], vetoes=vetoes,
        cal_horizon=_horizon_hours(cfg), judge_summary=judge_summary,
        now=now, simulated=simulated,
    )
    result.update(report=report, errors=mkt["errors"], ok=True, vetoes=vetoes,
                  calendar_ok=bool(cal_snap and cal_snap.ok),
                  news_count=len(news_snap.items) if news_snap else 0,
                  judgments=len(judgments), simulated=simulated)

    # ── ارسال سیگنال‌ها: جدا از گزارش، چون قابل اقدام‌اند ──────
    sent_signals = []
    if signals and simulated:
        log(f"⚠️ حالت شبیه‌سازی: {len(signals)} سیگنال ساخته شد ولی به تلگرام "
            f"ارسال نمی‌شود و در ژورنال ثبت نمی‌شود (فقط نمایشی است)")
        for sig in signals:
            sent_signals.append({"symbol": sig.symbol, "direction": sig.direction,
                                 "score": sig.score, "max_score": sig.max_score,
                                 "sent": False, "simulated": True,
                                 "text": render_signal(sig),
                                 "entry": sig.entry, "sl": sig.sl, "tp": sig.tp})
    elif signals:
        state = _load_signal_state()
        for sig in signals:
            go, why = should_send_signal(state, sig, jcfg, now=now)
            text = render_signal(sig)
            sent = False
            if go:
                sent, _msg = _send_telegram(cfg, text, log,
                                            label=f"🎯 سیگنال {sig.symbol}")
                if sent:
                    state[f"{sig.symbol}|{sig.direction}"] = {
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "score": sig.score,
                    }
            else:
                log(f"[i] سیگنال {sig.symbol} ({sig.direction}) ارسال نشد — {why}")
            journal_signal(sig, sent)      # پایهٔ ژورنال مرحله ۴
            sent_signals.append({"symbol": sig.symbol, "direction": sig.direction,
                                 "score": sig.score, "max_score": sig.max_score,
                                 "sent": sent, "text": text,
                                 "entry": sig.entry, "sl": sig.sl, "tp": sig.tp})
        _save_signal_state(state)
    result["signals"] = sent_signals

    # بخش فاندامنتال به‌صورت مستقل (برای تب جداگانه در پنل)
    fund_parts = []
    if cal_snap is not None:
        from .report.fundamental import render_calendar
        fund_parts.append(render_calendar(cal_snap, cfg["symbols"], now=now,
                                          horizon_hours=_horizon_hours(cfg)))
    if news_snap is not None:
        from .report.fundamental import render_news
        fund_parts.append(render_news(news_snap))
    result["fundamental_report"] = "\n".join(fund_parts)

    _archive(report)
    result["telegram"] = _send_telegram(cfg, report, log)
    result["elapsed"] = time.time() - t0
    log(f"🏁 چرخه تحلیل کامل شد ({result['elapsed']:.0f} ثانیه"
        + (f" — {len(vetoes)} نماد وتو شد" if vetoes else "") + ")")
    return result


# ══════════════════════════════════════════════════════════════
#  بریفینگ صبحگاهی
# ══════════════════════════════════════════════════════════════
def run_briefing(cfg: Optional[dict] = None, on_log: LogFn = _noop,
                 with_news: bool = True) -> dict:
    """🌅 ساخت (و ارسال) بریفینگ صبحگاهی."""
    t0 = time.time()
    cfg = cfg or load_config()
    result = {"ok": False, "report": "", "errors": 0, "telegram": (False, ""), "elapsed": 0.0}

    def log(msg: str) -> None:
        on_log(f"[{datetime.now():%H:%M:%S}] {msg}")

    log("🌅 ساخت بریفینگ صبحگاهی...")
    mkt = _collect_market(cfg, log)
    if not mkt["analyses"]:
        result["errors"] = max(mkt["errors"], 1)
        log("❌ بریفینگ ساخته نشد — دادهٔ بازار در دسترس نیست")
        return result

    cal_snap, news_snap = _collect_fundamental(cfg, log if with_news else _noop)
    if not with_news:
        news_snap = None

    bcfg = cfg.get("briefing") or {}
    text = render_briefing(
        mkt["analyses"], mkt["ranking"], cal_snap, news_snap, cfg["symbols"],
        source_name=mkt["source_name"],
        horizon_hours=float(bcfg.get("horizon_hours", 24)),
    )
    result.update(report=text, errors=mkt["errors"], ok=True)
    _archive(text, "briefings.log")
    result["telegram"] = _send_telegram(cfg, text, log, label="بریفینگ صبحگاهی")
    result["elapsed"] = time.time() - t0
    log(f"✅ بریفینگ آماده شد ({result['elapsed']:.0f} ثانیه)")
    return result


# ══════════════════════════════════════════════════════════════
#  هشدار رویداد پراثر
# ══════════════════════════════════════════════════════════════
def _load_alert_state() -> dict:
    try:
        with open(app_paths.sent_alerts_path(), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save_alert_state(state: dict, keep_days: int = 14) -> None:
    """ذخیره و پاک‌سازی ورودی‌های کهنه (تا فایل بی‌نهایت رشد نکند)."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=keep_days)).isoformat()
    pruned = {k: v for k, v in state.items() if str(v) >= cutoff}
    try:
        with open(app_paths.sent_alerts_path(), "w", encoding="utf-8") as f:
            json.dump(pruned, f, ensure_ascii=False)
    except Exception:
        pass


def check_event_alerts(cfg: Optional[dict] = None, cal_snap=None,
                       on_log: LogFn = _noop, now: Optional[datetime] = None,
                       dry_run: bool = False) -> list[dict]:
    """هشدار رویدادهای پراثرِ نزدیک (۳۰ دقیقه قبل) — هر رویداد فقط یک بار.

    Returns:
        فهرست رویدادهای هشدارداده‌شده: [{event, text, sent}]
    """
    cfg = cfg or load_config()
    fcfg = cfg.get("fundamental") or {}
    if not fcfg.get("enabled", True) or not fcfg.get("alerts_enabled", True):
        return []
    log = on_log

    if cal_snap is None:
        cal_snap = fetch_calendar(cfg, on_log=_noop)      # از کش محلی می‌آید → ارزان
    if not cal_snap.ok:
        return []

    now = now or datetime.now(timezone.utc)
    before = float(fcfg.get("alert_before_minutes", 30))
    grace = float(fcfg.get("alert_grace_minutes", 10))    # اگر برنامه تازه روشن شد
    covered = {c for s in cfg["symbols"] for c in (s.get("base"), s.get("quote"))}

    state = _load_alert_state()
    fired: list[dict] = []
    dirty = False
    for e in cal_snap.events:
        if e.impact != "HIGH":
            continue
        if e.country != "All" and e.country not in covered:
            continue
        mins = e.minutes_from(now)
        if not (-grace <= mins <= before):
            continue
        if state.get(e.key):
            continue                                       # قبلاً هشدار داده شده
        text = render_event_alert(e, cfg["symbols"], now=now)
        sent = False
        if not dry_run:
            sent, _msg = _send_telegram(cfg, text, log, label="هشدار رویداد")
            state[e.key] = datetime.now(timezone.utc).isoformat()
            dirty = True
        fired.append({"event": e, "text": text, "sent": sent, "minutes": mins})
        log(f"🚨 هشدار رویداد: «{e.title_fa}» ({e.country_fa}) — {int(round(mins))} دقیقه"
            + (" [پیش‌نمایش — ارسال نشد]" if dry_run else ""))
    if dirty:
        _save_alert_state(state)
    return fired


# ══════════════════════════════════════════════════════════════
#  زمان‌بند پس‌زمینه
# ══════════════════════════════════════════════════════════════
class BotLoop:
    """زمان‌بند سه‌کاره در thread پس‌زمینه (با قابلیت توقف امن).

    هر ۳۰ ثانیه بیدار می‌شود و بررسی می‌کند:
      ۱) آیا زمان چرخهٔ تحلیل رسیده؟          (هر interval_minutes)
      ۲) آیا هشداری برای رویداد پراثر لازم است؟ (هر ۶۰ ثانیه، با کش محلی)
      ۳) آیا زمان بریفینگ صبحگاهی رسیده؟       (ساعت‌های times_utc، روزی یک بار)
    """

    TICK_SEC = 30.0
    ALERT_CHECK_SEC = 60.0

    def __init__(self, on_log: LogFn = _noop,
                 on_report: Callable[[str], None] = lambda _: None,
                 on_briefing: Callable[[str], None] | None = None,
                 on_fundamental: Callable[[str], None] | None = None,
                 on_signal: Callable[[str], None] | None = None,
                 cfg_provider: Callable[[], dict] = load_config):
        self.on_log = on_log
        self.on_report = on_report
        self.on_briefing = on_briefing or on_report
        self.on_fundamental = on_fundamental or (lambda _: None)
        self.on_signal = on_signal or self.on_report
        self.cfg_provider = cfg_provider
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._once_running = False
        self._briefings_done: dict[str, set] = {}
        self.interval_min = 15.0
        self.state: dict = {"last_run": None, "next_run": None, "cycles": 0,
                            "last_error": None, "last_briefing": None,
                            "next_briefing": None, "alerts_sent": 0, "last_alert": None,
                            "last_vetoes": [], "calendar_ok": None, "news_count": 0,
                            "last_signals": [], "signals_total": 0, "last_signal": None}

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="bot-loop")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        t = self._thread
        if t is not None:
            t.join(timeout=8)
        self._thread = None
        self.state["next_run"] = None
        self.on_log("⏹ ربات متوقف شد")

    # ── اجرای دستی از پنل ─────────────────────────────────────
    def run_once_async(self) -> bool:
        """یک چرخه فوری در thread جدا (دکمه «اجرای یک‌بار»). اگر مشغول باشد False."""
        if self._once_running:
            return False
        threading.Thread(target=self._once, args=(run_cycle, "report"),
                         daemon=True, name="bot-once").start()
        return True

    def run_briefing_async(self) -> bool:
        """بریفینگ فوری (دکمه «🌅 بریفینگ» در پنل)."""
        if self._once_running:
            return False
        threading.Thread(target=self._once, args=(run_briefing, "briefing"),
                         daemon=True, name="bot-briefing").start()
        return True

    def _once(self, fn: Callable, kind: str) -> None:
        self._once_running = True
        try:
            res = fn(self.cfg_provider(), on_log=self.on_log)
            self._publish(res, kind)
            self.state["last_run"] = time.time()
            if kind == "briefing":
                self.state["last_briefing"] = time.time()
            self.state["cycles"] += 1
        except Exception as e:
            self.on_log(f"❌ خطا در اجرای دستی: {str(e)[:130]}")
            self.state["last_error"] = str(e)[:130]
        finally:
            self._once_running = False

    def _publish(self, res: dict, kind: str) -> None:
        """فرستادن نتیجهٔ یک چرخه/بریفینگ به رابط کاربری."""
        if kind == "briefing":
            if res.get("report"):
                self.on_briefing(res["report"])
            return
        if res.get("report"):
            self.on_report(res["report"])
        if res.get("fundamental_report"):
            self.on_fundamental(res["fundamental_report"])
        self.state["last_vetoes"] = sorted(res.get("vetoes") or {})
        self.state["calendar_ok"] = res.get("calendar_ok")
        self.state["news_count"] = res.get("news_count", 0)

        sigs = res.get("signals") or []
        self.state["last_signals"] = [
            {"symbol": x["symbol"], "direction": x["direction"], "score": x["score"],
             "max_score": x["max_score"], "sent": x["sent"]} for x in sigs]
        if sigs:
            self.state["last_signal"] = time.time()
            self.state["signals_total"] += len(sigs)
            # سیگنال‌ها در تب جداگانهٔ خودشان هم نمایش داده می‌شوند
            self.on_signal("\n\n".join(x["text"] for x in sigs))

    # ── حلقه اصلی ─────────────────────────────────────────────
    def _run(self) -> None:
        self.on_log("▶ ربات شروع به کار کرد — تحلیل خودکار + تقویم اقتصادی + اخبار فعال است")
        last_cycle = 0.0            # صفر = «هنوز اجرا نشده، همین حالا اجرا کن»
        last_alert = 0.0
        while not self._stop.is_set():
            try:
                cfg = self.cfg_provider()   # تنظیمات تازه هر بار (تغییر پنل بدون ری‌استارت)
                self.interval_min = float((cfg.get("loop") or {}).get("interval_minutes", 15))

                now = time.time()
                if last_cycle == 0.0 or now - last_cycle >= self.interval_min * 60:
                    if not self._once_running:
                        self._do_cycle(cfg)
                        last_cycle = time.time()
                    else:
                        last_cycle = now            # اجرای دستی در جریان است — از اول بشمار

                if time.time() - last_alert >= self.ALERT_CHECK_SEC:
                    last_alert = time.time()
                    self._do_alerts(cfg)

                self._maybe_briefing(cfg)
            except Exception as e:
                self.on_log(f"❌ خطای غیرمنتظره: {str(e)[:130]}")
                self.state["last_error"] = str(e)[:130]

            self.state["next_run"] = (last_cycle or time.time()) + self.interval_min * 60
            if self._stop.wait(min(self.TICK_SEC, max(5.0, self.interval_min * 60))):
                break
        self.on_log("⏹ ربات متوقف شد")

    def _do_cycle(self, cfg: dict) -> None:
        res = run_cycle(cfg, on_log=self.on_log)
        self._publish(res, "report")
        self.state["last_run"] = time.time()
        self.state["cycles"] += 1
        self.state["last_error"] = None if res.get("ok") else "آخرین چرخه ناموفق بود"
        # رویدادهای پراثرِ نزدیک، بلافاصله بعد از چرخه هم بررسی شوند
        self._do_alerts(cfg, cal_snap=None)

    def _do_alerts(self, cfg: dict, cal_snap=None) -> None:
        try:
            fired = check_event_alerts(cfg, cal_snap=cal_snap, on_log=self.on_log)
            if fired:
                self.state["alerts_sent"] += len(fired)
                self.state["last_alert"] = time.time()
        except Exception as e:
            self.on_log(f"[!] بررسی هشدار رویداد ناموفق: {str(e)[:100]}")

    # ── زمان‌بندی بریفینگ ─────────────────────────────────────
    @staticmethod
    def _parse_hhmm(s: str) -> Optional[tuple[int, int]]:
        try:
            hh, mm = str(s).split(":")[:2]
            hh, mm = int(hh), int(mm or 0)
            if 0 <= hh <= 23 and 0 <= mm <= 59:
                return hh, mm
        except Exception:
            pass
        return None

    def next_briefing_at(self, cfg: dict, now: Optional[datetime] = None) -> Optional[datetime]:
        """نزدیک‌ترین زمان بریفینگ بعدی (برای نمایش در پنل)."""
        bcfg = cfg.get("briefing") or {}
        if not bcfg.get("enabled", True):
            return None
        now = now or datetime.now(timezone.utc)
        times = [t for t in (bcfg.get("times_utc") or []) if self._parse_hhmm(t)]
        if not times:
            return None
        best = None
        for day_off in (0, 1):
            day = (now + timedelta(days=day_off)).date()
            for t in times:
                hh, mm = self._parse_hhmm(t)
                cand = datetime(day.year, day.month, day.day, hh, mm, tzinfo=timezone.utc)
                if cand > now and (best is None or cand < best):
                    best = cand
        return best

    def _maybe_briefing(self, cfg: dict) -> None:
        bcfg = cfg.get("briefing") or {}
        if not bcfg.get("enabled", True) or self._once_running:
            self.state["next_briefing"] = None
            return
        times = [t for t in (bcfg.get("times_utc") or []) if self._parse_hhmm(t)]
        if not times:
            return
        now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")
        # پاک‌سازی روزهای قبل (تا حافظه رشد نکند)
        for k in [k for k in self._briefings_done if k != today]:
            del self._briefings_done[k]
        done = self._briefings_done.setdefault(today, set())
        window = float(bcfg.get("catchup_window_minutes", 90))

        for t in times:
            if t in done:
                continue
            hh, mm = self._parse_hhmm(t)
            target = datetime(now.year, now.month, now.day, hh, mm, tzinfo=timezone.utc)
            if target <= now and (now - target).total_seconds() / 60.0 <= window:
                done.add(t)
                self.on_log(f"🌅 زمان بریفینگ صبحگاهی ({t} UTC) رسید — در حال ساخت...")
                res = run_briefing(cfg, on_log=self.on_log)
                self._publish(res, "briefing")
                self.state["last_briefing"] = time.time()
                break
        nxt = self.next_briefing_at(cfg, now)
        self.state["next_briefing"] = nxt.timestamp() if nxt else None
