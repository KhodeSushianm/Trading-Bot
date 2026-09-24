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
from .config import load_config
from .core.bus import EventBus, Events
from .core.lifecycle import LifecycleManager, PluginState
from .core.pipeline import STAGES, PipelineRunner, StageResult
from .fa import fa_num
from .judge.scoring import JudgeContext      # نوعِ مشترکِ ctx داور (قراردادِ فراخوانی)
from .plugins import build_default_registry
from .plugins.data import select_market_provider

# ── معماری پلاگین (فاز ۳) ─────────────────────────────────────
# هستهٔ engine دیگر هیچ فیچری را مستقیم import نمی‌کند: نه RSI، نه Yahoo،
# نه News، نه TradingView. قابلیت‌ها از طریق registry و «قرارداد»شان مصرف
# می‌شوند (_caps). تنها import فیچرگونهٔ باقی‌مانده JudgeContext است — نوعِ
# دادهٔ مشترکِ قرارداد داور، نه خودِ منطق داوری.
# رویدادهای BUS افزودنی‌اند: بدون listener هیچ اثر رفتاری ندارند.
BUS = EventBus()


class _Caps:
    """دسترسی قابلیت‌محور به پلاگین‌ها — نمونه‌ها تنبل (lazy) ساخته می‌شوند.

    هر فراخوانی عمومی engine یک _Caps می‌سازد (ساخت registry ~۱ میلی‌ثانیه،
    بدون هیچ I/O شبکه‌ای)؛ نمونهٔ هر پلاگین فقط در اولین مصرف initialize
    می‌شود. پلاگین غیرفعال/خراب → None (مصرف‌کننده همان guardهای فعلیِ
    enabled/try-except را دارد → unavailable صادقانه، نه کرش).
    """

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.reg, self.info = build_default_registry(cfg)
        self._lm = LifecycleManager(
            context=self.info["context"],
            on_failure=lambda f: BUS.emit(Events.PLUGIN_FAILED, f))
        self._cache: dict = {}

    def instance_for(self, rec):
        """نمونهٔ زندهٔ یک رکورد (initialize در اولین مصرف)."""
        if rec is None:
            return None
        if rec.instance is None:
            if rec.state is PluginState.RESOLVED:
                self._lm.initialize(rec)
            if rec.state is PluginState.FAILED:
                raise RuntimeError(rec.error or "پلاگین مقداردهی نشد")
        return rec.instance

    def _get(self, contract: str):
        if contract in self._cache:
            return self._cache[contract]
        inst = self.instance_for(self.reg.get(contract))
        self._cache[contract] = inst
        return inst

    # دسترسی نام‌دار به قراردادها (هسته فقط همین نام‌ها را می‌شناسد)
    @property
    def technical(self):  return self._get("odin.analysis.technical@1")

    @property
    def tv(self):         return self._get("odin.data.tv@1")

    @property
    def strength(self):   return self._get("odin.analysis.strength@1")

    @property
    def session(self):    return self._get("odin.session@1")

    @property
    def calendar(self):   return self._get("odin.fundamental.calendar@1")

    @property
    def news(self):       return self._get("odin.fundamental.news@1")

    @property
    def judge(self):      return self._get("odin.judge.engine@1")

    @property
    def journal(self):    return self._get("odin.journal@1")

    @property
    def notify(self):     return self._get("odin.notify@1")

    @property
    def alerts(self):     return self._get("odin.alerts.price@1")

    @property
    def report(self):     return self._get("odin.report@1")


def _caps(cfg: dict) -> _Caps:
    return _Caps(cfg)


def _safe_render(caps: _Caps, kind: str, payload: dict,
                 log: LogFn, default: str = "") -> str:
    """رندر گزارش با Failure Isolation (سخت‌گیری فاز ۷).

    پلاگین report غایب/خراب → لاگ صادقانهٔ فارسی + مقدار پیش‌فرض؛ هرگز
    استثنا بیرون نمی‌رود (یک گزارشِ از‌دست‌رفته نباید چرخه را بیندازد).
    مسیر سالم بایت‌به‌بایت همان caps.report.render است.
    """
    rep = caps.report
    if rep is None:
        log(f"[!] پلاگین گزارش در دسترس نیست — «{kind}» خالی رندر شد (unavailable)")
        return default
    try:
        return rep.render(kind, payload)
    except Exception as e:                          # noqa: BLE001 — قرنطینهٔ رندر
        log(f"[!] رندر «{kind}» ناموفق: {str(e)[:90]}")
        return default

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
    caps = _caps(cfg)
    try:
        rec = select_market_provider(caps.reg, cfg)
        source = caps.instance_for(rec)
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
                if caps.technical is None:            # سخت‌گیری فاز ۷
                    raise RuntimeError("پلاگین تحلیل تکنیکال در دسترس نیست")
                out["analyses"].append(caps.technical.analyze_symbol(
                    sym_cfg, md, cfg["analysis"]))
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
    if caps.strength is not None:
        out["ranking"] = caps.strength.currency_strength(
            out["datasets"], lookback_h1=int(cfg["analysis"].get("strength_lookback_h1", 24)))
    else:                                             # سخت‌گیری فاز ۷
        log("[!] پلاگین قدرت ارزها در دسترس نیست — رتبه‌بندی خالی می‌ماند (unavailable)")

    tv_cfg = cfg.get("tradingview") or {}
    out["tv_tf"] = str(tv_cfg.get("timeframe", "4h"))
    if with_tv and tv_cfg.get("enabled", True):
        log("🔍 دریافت تاییدیه تریدینگ‌ویو...")
        if caps.tv is None:                           # سخت‌گیری فاز ۷
            log("[!] پلاگین تریدینگ‌ویو در دسترس نیست — تاییدیه خالی می‌ماند (unavailable)")
        else:
            try:
                out["tv_map"] = caps.tv.fetch_tv_snapshot(cfg["symbols"], timeframe=out["tv_tf"])
                log(f"✅ تاییدیه تریدینگ‌ویو برای {len(out['tv_map'])} نماد دریافت شد")
            except Exception as e:
                log(f"[!] تاییدیه تریدینگ‌ویو ناموفق: {str(e)[:90]}")
    return out


def _collect_fundamental(cfg: dict, log: LogFn) -> tuple:
    """تقویم اقتصادی + اخبار. هیچ‌وقت استثنا پرتاب نمی‌کند."""
    fcfg = cfg.get("fundamental") or {}
    ncfg = cfg.get("news") or {}
    caps = _caps(cfg)
    cal_snap = news_snap = None
    if fcfg.get("enabled", True):
        if caps.calendar is None:                     # سخت‌گیری فاز ۷
            log("[!] پلاگین تقویم اقتصادی در دسترس نیست — رد شد (unavailable)")
        else:
            try:
                cal_snap = caps.calendar.fetch_calendar(cfg, on_log=log)
            except Exception as e:                   # لایهٔ اطمینان آخر
                log(f"[!] خطای غیرمنتظره در تقویم اقتصادی: {str(e)[:90]}")
    else:
        log("[i] موتور فاندامنتال (تقویم اقتصادی) در تنظیمات غیرفعال است")
    if ncfg.get("enabled", True):
        if caps.news is None:                         # سخت‌گیری فاز ۷
            log("[!] پلاگین موتور اخبار در دسترس نیست — رد شد (unavailable)")
        else:
            try:
                news_snap = caps.news.fetch_news(cfg, on_log=log)
            except Exception as e:
                log(f"[!] خطای غیرمنتظره در موتور اخبار: {str(e)[:90]}")
    else:
        log("[i] موتور اخبار در تنظیمات غیرفعال است")
    return cal_snap, news_snap


def _pct(v) -> str:
    return f"{fa_num(f'{v * 100:.0f}')}٪" if v is not None else "—"


def _rfmt(v) -> str:
    return f"{fa_num(f'{v:+.2f}')}" if v is not None else "—"


def _horizon_hours(cfg: dict) -> float:
    """بازهٔ نمایش رویدادهای تقویم در گزارش."""
    return float((cfg.get("fundamental") or {}).get("horizon_hours", 48))


def _compute_vetoes(cfg: dict, cal_snap, analyses, now: datetime, log: LogFn) -> dict:
    """دروازه وتو: کدام نمادها به‌خاطر رویداد پراثرِ نزدیک، سیگنال نمی‌گیرند."""
    vetoes: dict[str, list] = {}
    if cal_snap is None or not cal_snap.ok:
        return vetoes
    minutes = float((cfg.get("fundamental") or {}).get("veto_minutes_before", 30))
    caps = _caps(cfg)
    if caps.calendar is None:      # سخت‌گیری فاز ۷: قرارداد «هرگز استثنا نه»
        return vetoes
    for a in analyses:
        evs = caps.calendar.veto_for_symbol(cal_snap, a.base, a.quote, now,
                                            minutes=minutes)
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
    """ارسال از طریق پلاگین notify (فاز ۳).

    بدنهٔ واقعی بایت‌به‌بایت به src/plugins/notify.py منتقل شد؛ این wrapper
    فقط امضای تاریخی را برای مصرف‌کننده‌ها (BotLoop/panel/تست‌ها) نگه
    می‌دارد. رفتار سه مسیر (تنظیم‌نشده/موفق/شکست) با میخ‌های
    tests/test_engine_switch.py پین شده است.
    """
    notifier = _caps(cfg).notify
    if notifier is None:
        # هرگز نباید برسد (notify به config bind نیست) — صداقت: مثل مسیر تنظیم‌نشده
        log(f"[i] تلگرام تنظیم نشده — {label} فقط در پنل/کنسول نمایش داده می‌شود")
        return False, "تنظیم نشده"
    return notifier.send(cfg, text, log, label=label)


# ══════════════════════════════════════════════════════════════
#  چرخه تحلیل (گزارش دوره‌ای)
# ══════════════════════════════════════════════════════════════
def run_cycle(cfg: Optional[dict] = None, on_log: LogFn = _noop,
              now_override: Optional[datetime] = None,
              on_alert: Optional[Callable[[list], None]] = None) -> dict:
    """یک چرخه کامل تحلیل.

    Args:
        now_override: زمان فرضی برای داور/تقویم/سشن (حالت شبیه‌سازی).
                      دادهٔ بازار واقعی است، فقط «الان کی است» عوض می‌شود —
                      برای دیدن رفتار داور در روز کاری وقتی بازار بسته است.
                      در این حالت گزارش با برچسب ⚠️ شبیه‌سازی مشخص می‌شود.

    Returns:
        dict با کلیدهای: ok, report, errors, telegram, elapsed, vetoes,
                         calendar_ok, news_count, judgments, signals, simulated

    فاز ۳b: بدنهٔ چرخه روی PipelineRunner اجرا می‌شود — همان ۱۱ مرحلهٔ
    نام‌دار با همان ترتیب مو‌به‌موی قبلی (STAGES در فاز ۱ از همین کد
    رونویسی شد). early-exit امروز = StageResult(stop=True) در journal_pre.
    رویدادهای stage.start/stage.done افزودنی‌اند (بدون listener صفر اثر)؛
    ۱۲ رویداد استاندارد قبلی سرِ همان نقطه‌های خود منتشر می‌شوند.
    خطای پیش‌بینی‌نشدهٔ هر مرحله → قرنطینه (unavailable + plugin.failed +
    لاگ صادقانه) و ادامهٔ چرخه — codification همان Failure Isolation؛
    همهٔ مسیرهای قابل‌دسترسِ امروز از قبل guard داخلی دارند، پس طلاییِ
    tests/test_engine_switch.py بدون تغییر سبز می‌ماند.
    """
    t0 = time.time()
    cfg = cfg or load_config()
    caps = _caps(cfg)
    result = {"ok": False, "report": "", "errors": 0, "telegram": (False, ""),
              "elapsed": 0.0, "vetoes": {}, "calendar_ok": False, "news_count": 0,
              "judgments": 0, "signals": []}

    def log(msg: str) -> None:
        on_log(f"[{datetime.now():%H:%M:%S}] {msg}")

    # ── context مشترک بین مراحل (CycleContext وعده‌داده‌شده در فاز ۱) ──
    C: dict = {"mkt": None, "now": None, "simulated": False, "journal": None,
               "stats": None, "resolved": [], "cal_snap": None, "news_snap": None,
               "vetoes": {}, "jcfg": {}, "judgments": [], "signals": [],
               "judge_summary": "", "report": "", "sent_signals": [],
               "fired_alerts": []}

    runner = PipelineRunner(registry=caps.reg, bus=BUS, log=log, stages=STAGES)

    # ── ۱) collect_market ─────────────────────────────────────
    def stage_collect_market(_ctx):
        C["mkt"] = _collect_market(cfg, log)
        BUS.emit(Events.MARKET_COLLECTED,
                 {"analyses": len(C["mkt"]["analyses"]), "errors": C["mkt"]["errors"]})

    # ── ۲) journal_pre (عمداً *قبل* از بررسی موفقیت داده + early-exit) ──
    def stage_journal_pre(_ctx):
        mkt = C["mkt"]
        C["now"] = now_override or datetime.now(timezone.utc)
        C["simulated"] = now_override is not None
        if C["simulated"]:
            log(f"⚠️ حالت شبیه‌سازی: زمان فرضی {C['now']:%Y-%m-%d %H:%M} UTC "
                f"(دادهٔ بازار واقعی است، ساعت داور عوض شده)")

        # ── 📔 ژورنال: بستن خودکار سیگنال‌های باز از روی کندل‌ها ──
        # عمداً *قبل* از بررسی موفقیت داده آمده: اگر منبع داده کاملاً قطع باشد هم
        # سیگنال‌های باز باید منقضی/بسته شوند، وگرنه ژورنال برای همیشه می‌خوابد
        # و کارنامه خوش‌بینانه می‌ماند.
        # ⚠️ در حالت شبیه‌سازی (--as-of) هرگز نتیجه ثبت نمی‌شود: زمان فرضی برای
        # «دیدن» است، نه برای نوشتن در سند صداقت. فقط آمارِ موجود خوانده می‌شود.
        journal, stats, resolved = None, None, []
        if (cfg.get("journal") or {}).get("enabled", True):
            if caps.journal is None:                      # سخت‌گیری فاز ۷
                log("[!] پلاگین ژورنال در دسترس نیست — ژورنال این چرخه رد شد (unavailable)")
            else:
                journal = caps.journal.open()
                if C["simulated"]:
                    log("[i] حالت شبیه‌سازی: ژورنال فقط خوانده می‌شود، نتیجه‌ای ثبت نمی‌شود")
                try:
                    if not C["simulated"]:
                        resolved = caps.journal.resolve_open_signals(
                            journal, mkt["datasets"], now=C["now"], cfg=cfg, on_log=log)
                except Exception as e:
                    log(f"[!] پیگیری ژورنال ناموفق: {str(e)[:90]}")
                try:
                    stats = caps.journal.compute_stats(journal.load(), C["now"])
                except Exception as e:
                    log(f"[!] محاسبهٔ آمار ژورنال ناموفق: {str(e)[:90]}")
        else:
            log("[i] ژورنال در تنظیمات غیرفعال است")
        C["journal"], C["stats"], C["resolved"] = journal, stats, resolved
        result["resolved"] = [{"symbol": e.symbol, "direction": e.direction,
                               "outcome": e.outcome, "r": e.r} for e in resolved]
        result["stats"] = stats
        BUS.emit(Events.JOURNAL_RESOLVED, {"resolved": len(resolved)})
        if stats is not None and journal is not None:
            result["journal_report"] = _safe_render(
                caps, "stats", {"stats": stats, "open_entries": journal.open_entries(),
                                "now": C["now"]}, log)

        if not mkt["analyses"]:
            result["errors"] = max(mkt["errors"], 1)
            return StageResult(stage="journal_pre", stop=True)   # early-exit امروز

    # ── ۳) collect_fundamental ────────────────────────────────
    def stage_collect_fundamental(_ctx):
        C["cal_snap"], C["news_snap"] = _collect_fundamental(cfg, log)
        BUS.emit(Events.FUNDAMENTAL_COLLECTED,
                 {"calendar_ok": bool(C["cal_snap"] and C["cal_snap"].ok),
                  "news_items": len(C["news_snap"].items) if C["news_snap"] else 0})

    # ── ۴) compute_vetoes ─────────────────────────────────────
    def stage_compute_vetoes(_ctx):
        C["vetoes"] = _compute_vetoes(cfg, C["cal_snap"], C["mkt"]["analyses"],
                                      C["now"], log)
        BUS.emit(Events.VETOES_COMPUTED, {"vetoes": sorted(C["vetoes"])})

    # ── ۵) judge ──────────────────────────────────────────────
    def stage_judge(_ctx):
        # فاز ۷: judge-core به judge.enabled bind است — وقتی خاموش است پلاگین
        # غایب است ولی jcfg هنوز لازم است (min_score برای رندر/ضداسپم).
        # cfg["judge"] در load_config با همان DEFAULTS ادغام شده (src/config.py)
        # → fallback بایت‌به‌بایت یکسان است.
        jcfg = (caps.judge.judge_config(cfg) if caps.judge is not None
                else (cfg.get("judge") or {}))
        C["jcfg"] = jcfg
        judgments, signals, judge_summary = [], [], ""
        if jcfg.get("enabled", True):
            if caps.judge is None or caps.session is None:   # سخت‌گیری فاز ۷
                log("[!] پلاگین داور/سشن در دسترس نیست — قضاوتی در این چرخه انجام نشد (unavailable)")
            else:
                ctx = JudgeContext(
                    jcfg=jcfg, acfg=cfg["analysis"], symbols_cfg=cfg["symbols"],
                    ranking=C["mkt"]["ranking"], tv_map=C["mkt"]["tv_map"],
                    cal_snap=C["cal_snap"], news_snap=C["news_snap"], now=C["now"],
                    status=caps.session.market_status(C["now"]),
                    # منبع حقیقتِ پنجرهٔ وتو همان تنظیم مرحلهٔ ۲ است، نه یک عدد دوم
                    event_veto_minutes=float((cfg.get("fundamental") or {})
                                             .get("veto_minutes_before", 30)),
                    # S3: دروازهٔ توافق فقط min_agree را از اینجا می‌خواند
                    strategies_cfg=cfg.get("strategies") or {},
                )
                judgments = caps.judge.judge_all(C["mkt"]["analyses"], C["mkt"]["datasets"], ctx)
                signals = [j.signal for j in judgments if j.signal]
                BUS.emit(Events.JUDGE_DONE,
                         {"judgments": len(judgments), "signals": len(signals)})
                for _sg in signals:
                    BUS.emit(Events.SIGNAL_CREATED,
                             {"symbol": _sg.symbol, "direction": _sg.direction,
                              "score": _sg.score})
                log(f"⚖️ داور: {len(signals)} سیگنال صادر شد 🎯" if signals
                    else "⚖️ داور: هیچ سیگنالی صادر نشد (دلیل هر نماد در گزارش هست)")
                judge_summary = _safe_render(
                    caps, "judge_summary",
                    {"judgments": judgments,
                     "min_score": int(jcfg.get("min_score", 7)),
                     "now": C["now"]}, log)
        else:
            log("[i] داور امتیازدهی در تنظیمات غیرفعال است")
        C["judgments"], C["signals"], C["judge_summary"] = judgments, signals, judge_summary

    # ── ۶) render ─────────────────────────────────────────────
    def stage_render(_ctx):
        journal_line = ""
        if C["stats"] is not None:
            o = C["stats"].overall
            journal_line = (
                f"📊 کارنامه تا الان: بسته {fa_num(o.closed)} "
                f"(برد {fa_num(o.wins)} / باخت {fa_num(o.losses)} / منقضی {fa_num(o.expired)})"
                f" | نرخ برد {_pct(o.hit_rate)} | میانگین R {_rfmt(o.avg_r)}"
                f" | باز {fa_num(C['stats'].open_count)}"
                + (f" | بسته‌شدهٔ این چرخه: {fa_num(len(C['resolved']))}" if C["resolved"] else ""))

        C["report"] = _safe_render(caps, "console", {
            "analyses": C["mkt"]["analyses"], "ranking": C["mkt"]["ranking"],
            "source_name": C["mkt"]["source_name"],
            "tv_map": C["mkt"]["tv_map"], "tv_tf": C["mkt"]["tv_tf"],
            "cal_snap": C["cal_snap"], "news_snap": C["news_snap"],
            "symbols_cfg": cfg["symbols"], "vetoes": C["vetoes"],
            "cal_horizon": _horizon_hours(cfg), "judge_summary": C["judge_summary"],
            "now": C["now"], "simulated": C["simulated"], "journal_line": journal_line,
        }, log)
        BUS.emit(Events.REPORT_RENDERED, {"kind": "console", "length": len(C["report"])})
        result.update(report=C["report"], errors=C["mkt"]["errors"], ok=True,
                      vetoes=C["vetoes"],
                      calendar_ok=bool(C["cal_snap"] and C["cal_snap"].ok),
                      news_count=len(C["news_snap"].items) if C["news_snap"] else 0,
                      judgments=len(C["judgments"]), simulated=C["simulated"])

    # ── ۷) dispatch_signals ───────────────────────────────────
    def stage_dispatch_signals(_ctx):
        # ارسال سیگنال‌ها: جدا از گزارش، چون قابل اقدام‌اند
        sent_signals = C["sent_signals"]
        signals = C["signals"]
        if signals and C["simulated"]:
            log(f"⚠️ حالت شبیه‌سازی: {len(signals)} سیگنال ساخته شد ولی به تلگرام "
                f"ارسال نمی‌شود و در ژورنال ثبت نمی‌شود (فقط نمایشی است)")
            for sig in signals:
                sent_signals.append({"symbol": sig.symbol, "direction": sig.direction,
                                     "score": sig.score, "max_score": sig.max_score,
                                     "sent": False, "simulated": True,
                                     "text": _safe_render(caps, "signal", {"s": sig}, log),
                                     "entry": sig.entry, "sl": sig.sl, "tp": sig.tp})
        elif signals:
            state = _load_signal_state()
            for sig in signals:
                go, why = should_send_signal(state, sig, C["jcfg"], now=C["now"])
                text = _safe_render(caps, "signal", {"s": sig}, log)
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
                BUS.emit(Events.SIGNAL_SENT, {"symbol": sig.symbol, "sent": sent})
                journal_signal(sig, sent)      # پایهٔ ژورنال مرحله ۴
                sent_signals.append({"symbol": sig.symbol, "direction": sig.direction,
                                     "score": sig.score, "max_score": sig.max_score,
                                     "sent": sent, "text": text,
                                     "entry": sig.entry, "sl": sig.sl, "tp": sig.tp,
                                     # v0.19.0 — فیلدهای کارت سیگنال (popup/اشتراک تصویر/نمودار)
                                     "pip": sig.pip, "is_gold": bool(getattr(sig, "is_gold", False)),
                                     "rr": sig.rr, "stars": getattr(sig, "stars", 0),
                                     "session_fa": getattr(sig, "session_fa", ""),
                                     "fa_name": getattr(sig, "fa_name", ""),
                                     "now": C["now"].isoformat()})
            _save_signal_state(state)
        result["signals"] = sent_signals

    # ── ۸) price_alerts ───────────────────────────────────────
    def stage_price_alerts(_ctx):
        fired_alerts = []
        try:
            fired_alerts = caps.alerts.check_alerts(C["mkt"].get("analyses") or [], now=C["now"])
            for fa_ in fired_alerts:
                _sym = fa_["symbol"]
                _dir = "بالاتر از" if fa_["dir"] == "above" else "پایین‌تر از"
                log(f"هشدار قیمت: {_sym} به {fa_['_price']} رسید ({_dir} {fa_['price']})")
                _txt = (f"هشدار قیمت — {_sym}\n"
                        f"{_sym} به سطح {fa_['price']} رسید ({_dir})\n"
                        f"قیمت فعلی: {fa_['_price']} — ساعت {datetime.now(timezone.utc).astimezone():%H:%M}")
                _send_telegram(cfg, _txt, log, label=f"هشدار قیمت {_sym}")
            if fired_alerts and on_alert is not None:
                on_alert(fired_alerts)
        except Exception as e:
            log(f"[!] بررسی هشدار قیمت ناموفق: {str(e)[:100]}")
        C["fired_alerts"] = fired_alerts
        result["alerts_fired"] = fired_alerts
        BUS.emit(Events.ALERTS_FIRED, {"fired": len(fired_alerts)})

    # ── ۹) chart_cache ────────────────────────────────────────
    def stage_chart_cache(_ctx):
        # کش نمودار (v0.19.0) — برای ChartDialog پنل، مثل chart.<SYM> اندروید
        try:
            import json as _json
            _cdir = app_paths.data_dir()
            _cdir.mkdir(parents=True, exist_ok=True)
            for _sym, _md in (C["mkt"].get("datasets") or {}).items():
                _rows = {"h1": [], "h4": []}
                for _tf in ("h1", "h4"):
                    _df = getattr(_md, _tf, None)
                    if _df is None or len(_df) == 0:
                        continue
                    _tail = _df.tail(360 if _tf == "h1" else 140)
                    for _ts, _row in _tail.iterrows():
                        _rows[_tf].append({
                            "t": int(_ts.timestamp() * 1000),
                            "o": float(_row["Open"]), "h": float(_row["High"]),
                            "l": float(_row["Low"]), "c": float(_row["Close"])})
                (_cdir / f"chart_{_sym}.json").write_text(
                    _json.dumps(_rows, separators=(",", ":")), encoding="utf-8")
        except Exception as e:
            log(f"[i] ذخیرهٔ کش نمودار ناموفق: {str(e)[:80]}")

    # ── ۱۰) dashboard ─────────────────────────────────────────
    def stage_dashboard(_ctx):
        # دادهٔ ساختاریافته برای داشبورد پنل
        result["ranking"] = list(C["mkt"]["ranking"])
        upcoming = []
        if C["cal_snap"] is not None and C["cal_snap"].ok:
            for e in caps.calendar.upcoming_events(C["cal_snap"], C["now"],
                                                   hours=_horizon_hours(cfg), limit=6):
                upcoming.append({"title_fa": e.title_fa, "country_fa": e.country_fa,
                                 "country": e.country, "impact": e.impact,
                                 "when": e.when.isoformat(),
                                 "minutes": int(round(e.minutes_from(C["now"])))})
        result["upcoming"] = upcoming
        result["symbols_summary"] = [
            {"symbol": a.symbol, "verdict": a.verdict, "trend": a.trend,
             "adx": round(a.adx, 1), "rsi": round(a.rsi, 1), "price": a.price,
             "pip": a.pip, "support": a.support, "resistance": a.resistance}
            for a in C["mkt"]["analyses"]]

        # بخش فاندامنتال به‌صورت مستقل (برای تب جداگانه در پنل)
        fund_parts = []
        if C["cal_snap"] is not None:
            fund_parts.append(_safe_render(
                caps, "calendar", {"snap": C["cal_snap"], "symbols_cfg": cfg["symbols"],
                                   "now": C["now"], "horizon_hours": _horizon_hours(cfg)}, log))
        if C["news_snap"] is not None:
            fund_parts.append(_safe_render(caps, "news", {"snap": C["news_snap"]}, log))
        result["fundamental_report"] = "\n".join(fund_parts)

    # ── ۱۱) archive_notify ────────────────────────────────────
    def stage_archive_notify(_ctx):
        _archive(C["report"])
        result["telegram"] = _send_telegram(cfg, C["report"], log)
        BUS.emit(Events.TELEGRAM_SENT, {"label": "گزارش", "ok": result["telegram"][0]})
        result["elapsed"] = time.time() - t0
        log(f"🏁 چرخه تحلیل کامل شد ({result['elapsed']:.0f} ثانیه"
            + (f" — {len(C['vetoes'])} نماد وتو شد" if C["vetoes"] else "") + ")")
        BUS.emit(Events.CYCLE_END, {"ok": True, "signals": len(C["sent_signals"])})

    # ── ثبت مراحل با ترتیب قطعی و اجرای pipeline ───────────────
    for _prio, (_name, _fn) in enumerate((
            ("collect_market", stage_collect_market),
            ("journal_pre", stage_journal_pre),
            ("collect_fundamental", stage_collect_fundamental),
            ("compute_vetoes", stage_compute_vetoes),
            ("judge", stage_judge),
            ("render", stage_render),
            ("dispatch_signals", stage_dispatch_signals),
            ("price_alerts", stage_price_alerts),
            ("chart_cache", stage_chart_cache),
            ("dashboard", stage_dashboard),
            ("archive_notify", stage_archive_notify)), start=1):
        runner.add(_name, _fn, priority=10 * _prio)

    BUS.emit(Events.CYCLE_START, {"simulated": now_override is not None})
    runner.run(C)          # early-exit → stop در journal_pre (بقیه اجرا نمی‌شوند)
    return result


# ══════════════════════════════════════════════════════════════
#  بریفینگ صبحگاهی
# ══════════════════════════════════════════════════════════════
def run_briefing(cfg: Optional[dict] = None, on_log: LogFn = _noop,
                 with_news: bool = True) -> dict:
    """🌅 ساخت (و ارسال) بریفینگ صبحگاهی."""
    t0 = time.time()
    cfg = cfg or load_config()
    caps = _caps(cfg)
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
    text = _safe_render(caps, "briefing", {
        "analyses": mkt["analyses"], "ranking": mkt["ranking"],
        "cal_snap": cal_snap, "news_snap": news_snap,
        "symbols_cfg": cfg["symbols"],
        "source_name": mkt["source_name"],
        "horizon_hours": float(bcfg.get("horizon_hours", 24)),
    }, log)
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
    caps = _caps(cfg)

    if caps.calendar is None:      # سخت‌گیری فاز ۷: unavailable، نه کرش
        return []
    if cal_snap is None:
        # از کش محلی می‌آید → ارزان
        cal_snap = caps.calendar.fetch_calendar(cfg, on_log=_noop)
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
        text = _safe_render(caps, "event_alert",
                            {"event": e, "symbols_cfg": cfg["symbols"],
                             "now": now}, log)
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
#  گزارش‌های ژورنال (کارنامه / خلاصهٔ شبانه)
# ══════════════════════════════════════════════════════════════
def run_journal_report(cfg: Optional[dict] = None, on_log: LogFn = _noop,
                       kind: str = "stats") -> dict:
    """📊 کارنامهٔ دقت یا 🌙 خلاصهٔ شبانه را می‌سازد و به تلگرام می‌فرستد.

    kind: "stats" | "nightly"
    """
    t0 = time.time()
    cfg = cfg or load_config()
    result = {"ok": False, "report": "", "telegram": (False, ""), "elapsed": 0.0,
              "stats": None}

    def log(msg: str) -> None:
        on_log(f"[{datetime.now():%H:%M:%S}] {msg}")

    caps = _caps(cfg)
    if caps.journal is None:       # سخت‌گیری فاز ۷
        log("[!] پلاگین ژورنال در دسترس نیست — گزارش ساخته نشد (unavailable)")
        return result
    jr = caps.journal.open()
    try:
        entries = jr.load()
    except Exception as e:
        log(f"[!] خواندن ژورنال ناموفق: {str(e)[:90]}")
        return result
    now = datetime.now(timezone.utc)
    stats = caps.journal.compute_stats(entries, now)
    if kind == "nightly":
        text = _safe_render(caps, "nightly",
                            {"entries": entries, "stats": stats, "now": now}, log)
        label = "🌙 خلاصهٔ شبانه"
    else:
        text = _safe_render(caps, "stats", {"stats": stats,
                                            "open_entries": jr.open_entries(),
                                            "now": now}, log)
        label = "📊 کارنامهٔ دقت"
    result.update(report=text, ok=True, stats=stats)
    _archive(text, "journal.log")
    result["telegram"] = _send_telegram(cfg, text, log, label=label)
    result["elapsed"] = time.time() - t0
    log(f"✅ {label} آماده شد ({result['elapsed']:.0f} ثانیه)")
    return result


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
                 on_journal: Callable[[str], None] | None = None,
                 cfg_provider: Callable[[], dict] = load_config,
                 on_alert: Callable[[list], None] | None = None,
                 on_signal_card: Callable[[list], None] | None = None):
        self.on_log = on_log
        self.on_report = on_report
        self.on_briefing = on_briefing or on_report
        self.on_fundamental = on_fundamental or (lambda _: None)
        self.on_signal = on_signal or self.on_report
        self.on_journal = on_journal or self.on_report
        self.on_alert = on_alert or (lambda _: None)
        self.on_signal_card = on_signal_card or (lambda _: None)
        self._journal_done: set[str] = set()
        self.cfg_provider = cfg_provider
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._once_running = False
        self._cycle_lock = threading.Lock()   # جلوگیری از هم‌پوشانی دو چرخه
        self._briefings_done: dict[str, set] = {}
        self.interval_min = 15.0
        self.state: dict = {"last_run": None, "next_run": None, "cycles": 0,
                            "last_error": None, "last_briefing": None,
                            "next_briefing": None, "alerts_sent": 0, "last_alert": None,
                            "last_vetoes": [], "calendar_ok": None, "news_count": 0,
                            "last_signals": [], "signals_total": 0, "last_signal": None,
                            "ranking": [], "upcoming": [], "symbols_summary": [],
                            "journal_report": "", "resolved": []}

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
        with self._cycle_lock:
            if self._once_running:
                return False
            self._once_running = True
        threading.Thread(target=self._once, args=(run_cycle, "report"),
                         daemon=True, name="bot-once").start()
        return True

    def run_journal_async(self, kind: str = "stats") -> bool:
        """کارنامه/خلاصهٔ شبانه دستی (دکمهٔ صفحهٔ کارنامه)."""
        if self._once_running:
            return False

        def _go():
            res = run_journal_report(self.cfg_provider(), on_log=self.on_log, kind=kind)
            if res.get("report"):
                self.on_journal(res["report"])
        threading.Thread(target=_go, daemon=True, name="bot-journal").start()
        return True

    def run_briefing_async(self) -> bool:
        """بریفینگ فوری (دکمه «🌅 بریفینگ» در پنل)."""
        if self._once_running:
            return False
        threading.Thread(target=self._once, args=(run_briefing, "briefing"),
                         daemon=True, name="bot-briefing").start()
        return True

    def _once(self, fn: Callable, kind: str) -> None:
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

        for key in ("ranking", "upcoming", "symbols_summary"):
            self.state[key] = res.get(key) or ({} if key == "symbols_summary" else [])
        if res.get("journal_report"):
            self.state["journal_report"] = res["journal_report"]
            self.on_journal(res["journal_report"])
        if res.get("resolved"):
            self.state["resolved"] = res["resolved"]

        sigs = res.get("signals") or []
        self.state["last_signals"] = [
            {"symbol": x["symbol"], "direction": x["direction"], "score": x["score"],
             "max_score": x["max_score"], "sent": x["sent"]} for x in sigs]
        if sigs:
            self.state["last_signal"] = time.time()
            self.state["signals_total"] += len(sigs)
            # سیگنال‌ها در تب جداگانهٔ خودشان هم نمایش داده می‌شوند
            self.on_signal("\n\n".join(x["text"] for x in sigs))
            # v0.19.0 — کارت ساختاریافته برای popup متحرک / اشتراک تصویر
            self.on_signal_card(list(sigs))
        if res.get("alerts_fired"):
            self.state.setdefault("price_alerts_fired", 0)
            self.state["price_alerts_fired"] += len(res["alerts_fired"])

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
                    with self._cycle_lock:
                        busy = self._once_running
                    if not busy:
                        self._do_cycle(cfg)
                        last_cycle = time.time()
                    else:
                        last_cycle = now            # اجرای دستی در جریان است — از اول بشمار

                if time.time() - last_alert >= self.ALERT_CHECK_SEC:
                    last_alert = time.time()
                    self._do_alerts(cfg)

                self._maybe_briefing(cfg)
                self._maybe_journal(cfg)
            except Exception as e:
                self.on_log(f"❌ خطای غیرمنتظره: {str(e)[:130]}")
                self.state["last_error"] = str(e)[:130]

            self.state["next_run"] = (last_cycle or time.time()) + self.interval_min * 60
            if self._stop.wait(min(self.TICK_SEC, max(5.0, self.interval_min * 60))):
                break
        self.on_log("⏹ ربات متوقف شد")

    def _do_cycle(self, cfg: dict) -> None:
        res = run_cycle(cfg, on_log=self.on_log, on_alert=self.on_alert)
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

    def _maybe_journal(self, cfg: dict) -> None:
        """زمان‌بندی 🌙 خلاصهٔ شبانه و 📊 گزارش هفتگی دقت."""
        jcfg = cfg.get("journal") or {}
        if not jcfg.get("enabled", True) or self._once_running:
            return
        now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")

        def _due(spec: dict, default_time: str, default_catchup: float) -> bool:
            if not spec.get("enabled", True):
                return False
            hm = self._parse_hhmm(str(spec.get("time_utc", default_time)))
            if not hm:
                return False
            target = now.replace(hour=hm[0], minute=hm[1], second=0, microsecond=0)
            return target <= now and \
                (now - target).total_seconds() / 60.0 <= float(
                    spec.get("catchup_window_minutes", default_catchup))

        n = jcfg.get("nightly") or {}
        if f"nightly:{today}" not in self._journal_done and _due(n, "21:30", 60):
            self._journal_done.add(f"nightly:{today}")
            self.on_log("🌙 زمان خلاصهٔ شبانه رسید — در حال ساخت…")
            res = run_journal_report(cfg, on_log=self.on_log, kind="nightly")
            if res.get("report"):
                self.on_journal(res["report"])

        w = jcfg.get("weekly") or {}
        day = int(w.get("day_utc", 6))          # 0=دوشنبه … 6=یکشنبه
        if (now.weekday() == day
                and f"weekly:{today}" not in self._journal_done
                and _due(w, "20:00", 120)):
            self._journal_done.add(f"weekly:{today}")
            self.on_log("📊 زمان گزارش هفتگی دقت رسید — در حال ساخت…")
            res = run_journal_report(cfg, on_log=self.on_log, kind="stats")
            if res.get("report"):
                self.on_journal(res["report"])

        for k in [k for k in self._journal_done if not k.endswith(today)]:
            self._journal_done.discard(k)

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
