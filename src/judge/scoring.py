# -*- coding: utf-8 -*-
"""داور امتیازدهی (Confluence Judge) — مرحله ۳.

هر نماد از دو لایه رد می‌شود:

  ۱) **دروازه‌های وتو** (بدون استثنا) — اگر یکی فعال باشد، سیگنال صادر نمی‌شود
     حتی اگر امتیاز کامل باشد:
       🔒 بازار بسته (شنبه/یکشنبه)
       📅 رویداد پراثر تقویم در ۳۰ دقیقه آینده        (از مرحله ۲)
       🔀 تضاد جهت بین تایم‌فریم ۴ ساعته و ۱ ساعته
       😴 بازار بی‌روند (ADX زیر آستانه)
       📈 جهش غیرعادی نوسان
       🚨 خبر فوریِ مرتبط با این نماد
       ⚠️ دادهٔ ناکافی

  ۲) **جدول امتیاز** (حداکثر ۱۱) — سیگنال فقط اگر ≥ آستانه (پیش‌فرض ۷):
       هم‌راستایی روند H4+H1              +۲ (یا +۱ اگر ADX فقط متوسط باشد)
       پولبک/واکنش به سطح کلیدی            +۲
       پنجرهٔ فاندامنتال پاک               +۲
       تایید مومنتوم (RSI)                 +۱
       هم‌جهتی جریان قدرت ارزها             +۱
       تایید خبری                          +۱
       هم‌جهتی امتیاز تکنیکال تریدینگ‌ویو    +۱
       زمان‌بندی مناسب (سشن لندن/نیویورک)   +۱

⚠️ **دو تصمیم صادقانه که باید بدانی:**

  • طرح اولیه می‌گفت «۷ از ۱۰»، ولی جمع همان جدول ۱۱ می‌شود. به‌جای دست‌کاری
    وزن‌ها، حداکثر به‌صورت پویا محاسبه و «X از ۱۱» نمایش داده می‌شود و آستانه
    در config قابل تنظیم است.

  • مدرک «تأیید فاندامنتال» در طرح اولیه «واگرایی نرخ بهره» بود. برای آن به
    منبع نرخ بهره نیاز است: FRED کلید می‌خواهد، ویکی‌پدیا ۴۰۳ می‌داد و فید
    هفتگی ForexFactory فقط رویدادهای همین هفته را دارد (پس بیشتر ارزها در بیشتر
    هفته‌ها دادهٔ نرخ ندارند). به‌جای وانمود کردن، این مدرک با
    **«پنجرهٔ فاندامنتال پاک»** (نبود رویداد پراثر/متوسط پیش‌رو) پر شده که
    با دادهٔ موجود، واقعی و قابل اتکاست. واگرایی نرخ بهره در
    `docs/step3-judge-signals-fa.md` §۸ به‌عنوان کار باقی‌مانده مستند شده.

  • وتوی «اسپرد غیرعادی» هم با دادهٔ وب ممکن نیست (بدون بروکر، اسپرد نداریم).
    جایش **«جهش غیرعادی نوسان»** نشسته: اگر ATR یک‌ساعتهٔ فعلی بیشتر از
    ۲ برابر میانگین ۱۰۰ کندل اخیر باشد، بازار غیرعادی است و سیگنال وتو می‌شود.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional

from ..analysis import indicators as ind
from ..analysis.technical import SymbolAnalysis
from ..data.base import MarketData
from ..fundamental.calendar import CalendarSnapshot, upcoming_events, veto_for_symbol
from ..fa import fa_num, fa_ratio
from ..fundamental.news import NewsSnapshot, news_supports
from .session import MarketStatus, market_status

# ── مقادیر پیش‌فرض (با config.yaml ادغام می‌شوند) ───────────────
DEFAULTS: dict = {
    "enabled": True,
    "min_score": 7,
    "max_signals_per_cycle": 3,
    "resend_cooldown_minutes": 180,
    "resend_score_gain": 2,
    "veto": {
        "weekend": True,
        "high_impact_event": True,
        "timeframe_conflict": True,
        "range_market": True,
        "volatility_spike": True,
        "breaking_news": True,
    },
    "fundamental": {"clean_high_hours": 6, "clean_med_hours": 2},
    "news": {"min_score": 4, "breaking_min_score": 5},
    "volatility": {"spike_multiplier": 2.0, "lookback_bars": 100},
    "level": {"close_atr": 0.5, "near_atr": 1.5},
    "risk": {
        "sl_atr_multiplier": 1.5,      # اگر سطح کلیدی در دسترس نبود
        "max_sl_atr": 3.0,             # سقف فاصلهٔ حد ضرر (جلوگیری از ریسک بزرگ)
        "min_sl_atr": 0.6,             # کف فاصله (جلوگیری از استاپ خوردن با نویز)
        "level_buffer_atr": 0.3,       # حد ضرر کمی آن‌سوی سطح
        "reward_risk": 2.0,            # نسبت سود به ریسک هدف
        "max_risk_percent": 1.0,       # فقط برای نمایش در پیام
        # v0.29: برآوردِ اسپرد برای Rِ خالص. صریحاً «برآورد» است چون ODIN
        # به بروکر وصل نیست. پیش‌فرضِ خالی = 0.0 = R خالص == R ناخالص.
        "spread": {"enabled": True, "default_pips": 0.0,
                   "warn_at_risk_fraction": 0.25, "per_symbol": {}},
    },
}

TREND_FA = {"bullish": "صعودی 📈", "bearish": "نزولی 📉", "none": "نامشخص ❔"}
DIR_FA = {"BUY": "خرید 🟢", "SELL": "فروش 🔴"}
DIR_EMOJI = {"BUY": "🟢", "SELL": "🔴"}
TV_DIR = {"STRONG_BUY": 2, "BUY": 1, "NEUTRAL": 0, "SELL": -1, "STRONG_SELL": -2}


def _deep_fill(base: dict, over: Optional[dict]) -> dict:
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_fill(out[k], v)
        else:
            out[k] = v
    return out


def judge_config(cfg: dict) -> dict:
    """ادغام تنظیمات کاربر با مقادیر پیش‌فرض داور."""
    return _deep_fill(DEFAULTS, (cfg or {}).get("judge"))


# ══════════════════════════════════════════════════════════════
#  ساختارهای داده
# ══════════════════════════════════════════════════════════════
@dataclass
class Evidence:
    """یک مدرک در جدول امتیاز."""

    key: str
    label_fa: str
    points: int
    max_points: int
    detail_fa: str
    ok: bool = False            # آیا امتیازی گرفت؟
    unavailable: bool = False   # دادهٔ این مدرک در دسترس نبود (صادقانه: ۰ امتیاز)

    @property
    def icon(self) -> str:
        if self.points > 0:
            return "✅"
        if self.unavailable:
            return "❔"
        return "➖"


@dataclass
class Veto:
    """یک دروازهٔ وتو که فعال شده."""

    key: str
    title_fa: str
    detail_fa: str


@dataclass
class Signal:
    """سیگنال قابل ارسال."""

    symbol: str
    fa_name: str
    direction: str              # BUY | SELL
    score: int
    max_score: int
    stars: int
    entry: float
    sl: float
    tp: float
    pip: float
    atr: float
    risk_pips: float
    reward_pips: float
    rr: float
    is_gold: bool
    session_fa: str
    now: datetime
    evidences: list[Evidence] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sl_capped: bool = False
    sid: str = ""             # شناسهٔ یکتای ژورنال (مرحله ۴ نتیجه را به آن گره می‌زند)
    # S3 (v0.26): verdict کامل همهٔ استراتژی‌های فعال (dict) — موافق‌ها و
    # مخالف‌ها، برای صداقتِ پیام («چرا این سیگنال صادر شد» حالا استراتژی هم
    # دارد). ژورنال فقط کلیدِ موافق‌ها را نگه می‌دارد (فشرده و کافی برای
    # «نرخ برد به تفکیک استراتژی» در آینده).
    strategies: list = field(default_factory=list)
    # v0.29 (فاز ۱+۲): زمانِ بسته‌شدنِ کندلی که `entry` از آن آمده.
    # `now` دیوارساعتِ لحظهٔ صدور است (برای نمایش/کول‌داون/هفتهٔ آمار)؛
    # `entry_ts` لحظهٔ واقعیِ خودِ قیمت است (برای شروعِ اسکنِ نتیجه).
    # پیش‌تر این دو یکی فرض می‌شدند و تا یک ساعت اختلاف داشتند — همان باگِ
    # «ورودِ کهنه». None = دادهٔ زمانی نبود → tracker رفتارِ قبلی را نگه می‌دارد.
    entry_ts: Optional[datetime] = None
    # v0.29 (فاز ۳): برآوردِ اسپرد (پیپ) — ژورنال نگهش می‌دارد تا tracker
    # بتواند Rِ *خالص* را کنارِ Rِ ناخالص بنویسد. صفر = هزینه مدل نمی‌شود.
    spread_pips: float = 0.0

    @property
    def direction_fa(self) -> str:
        return DIR_FA.get(self.direction, self.direction)

    def to_journal(self, sent: bool = True) -> dict:
        """رکورد JSON برای ژورنال.

        ژورنال به سبک event-source فقط append می‌شود: این رکورد با
        ``kind="signal"`` نوشته می‌شود و نتیجهٔ آن بعداً به‌صورت رکورد جداگانهٔ
        ``kind="outcome"`` با همان ``id`` الحاق می‌شود. بنابراین فایل هرگز
        بازنویسی نمی‌شود و خرابی وسط کار چیزی را از بین نمی‌برد.
        """
        return {
            "kind": "signal",
            "id": self.sid,
            "ts": self.now.isoformat(),
            # v0.29: زمانِ خودِ قیمتِ ورود (نه دیوارساعتِ صدور). رکوردهای
            # قدیمی این کلید را ندارند → None → رفتارِ قبلی (سازگار).
            "entry_ts": self.entry_ts.isoformat() if self.entry_ts else None,
            "symbol": self.symbol,
            "direction": self.direction,
            "entry": round(self.entry, 6),
            "sl": round(self.sl, 6),
            "tp": round(self.tp, 6),
            "pip": self.pip,
            "atr": round(self.atr, 6),
            "risk_pips": round(self.risk_pips, 1),
            "reward_pips": round(self.reward_pips, 1),
            "rr": self.rr,
            # v0.29 (فاز ۳): برای Rِ خالص. رکوردهای قدیمی ندارند → 0.0 →
            # R خالص == R ناخالص (سازگار، بدون حدس).
            "spread_pips": round(float(self.spread_pips or 0.0), 3),
            "score": self.score,
            "max_score": self.max_score,
            "session": self.session_fa,
            "evidences": [f"{e.key}:{e.points}/{e.max_points}" for e in self.evidences],
            # S3: کلیدِ استراتژی‌های هم‌جهت (رکوردهای قدیمیِ ژورنال این کلید را
            # ندارند — tracker/stats فقط کلیدهای شناخته‌شده را می‌خوانند، پس
            # append-only و backward-compatible می‌ماند)
            "strategies": [v["key"] for v in self.strategies
                           if v.get("direction") == self.direction],
            "sent": sent,
        }


@dataclass
class Judgment:
    """نتیجهٔ داوری یک نماد — چه سیگنال بدهد چه ندهد، دلیلش روشن است."""

    symbol: str
    fa_name: str
    direction: Optional[str]
    score: int = 0
    max_score: int = 11
    evidences: list[Evidence] = field(default_factory=list)
    vetoes: list[Veto] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    signal: Optional[Signal] = None
    reject_reason: str = ""        # NO_SETUP | VETO | LOW_SCORE | NO_STRATEGY | CAPPED | DISABLED
    reject_detail: str = ""
    price: float = 0.0
    pip: float = 0.0001
    # S3 (v0.26): verdict استراتژی‌ها (dict — همان shape طلاییِ دو زبان).
    # فقط وقتی پر می‌شود که دروازهٔ توافق اجرا شده باشد (strategy_rules
    # تزریق شده و امتیاز از آستانه گذشته) — ردشدگی‌های VETO/NO_SETUP/
    # LOW_SCORE عمداً استراتژی‌ها را ارزیابی نمی‌کنند (ارزیابیِ زودهنگام
    # در گزارش «نظرِ بی‌مورد» نشان می‌داد).
    strategies: list = field(default_factory=list)

    @property
    def status_fa(self) -> str:
        if self.signal:
            return "✅ سیگنال صادر شد"
        return {
            "VETO": "🚫 وتو شد",
            "LOW_SCORE": "⏳ امتیاز ناکافی",
            "NO_SETUP": "❔ ستاپی شکل نگرفته",
            "NO_STRATEGY": "🎯 استراتژی موافق نیست",
            "CAPPED": "🔢 به سقف تعداد سیگنال رسید",
            "DISABLED": "⚙️ داور خاموش است",
        }.get(self.reject_reason, "—")


@dataclass
class JudgeContext:
    """هر چیزی که داور برای یک چرخه لازم دارد."""

    jcfg: dict
    acfg: dict
    symbols_cfg: list[dict]
    ranking: list[tuple[str, float]] = field(default_factory=list)
    tv_map: dict = field(default_factory=dict)
    cal_snap: Optional[CalendarSnapshot] = None
    news_snap: Optional[NewsSnapshot] = None
    now: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: MarketStatus = field(default_factory=lambda: market_status(datetime.now(timezone.utc)))
    # پنجرهٔ وتوی رویداد پراثر — از fundamental.veto_minutes_before مرحله ۲ می‌آید
    # تا دو موتور یک عدد را دو جور تفسیر نکنند
    event_veto_minutes: float = 30.0
    # S3 (v0.26): تنظیمات دروازهٔ توافق استراتژی‌ها — فقط min_agree از اینجا
    # خوانده می‌شود (scfg هر استراتژی در adapter خودش bind شده، مثل فاز ۴).
    # پیش‌فرض خالی = min_agree ۱ (همان config.yaml).
    strategies_cfg: dict = field(default_factory=dict)


# ══════════════════════════════════════════════════════════════
#  دروازه‌های وتو
# ══════════════════════════════════════════════════════════════
def _volatility_ratio(md: MarketData, acfg: dict, lookback: int) -> tuple[float, float]:
    """(ATR فعلی / میانگین ATR، میانگین). برای وتوی جهش نوسان."""
    try:
        s = ind.atr(md.h1, int(acfg.get("atr_period", 14))).dropna()
        if len(s) < 20:
            return 0.0, 0.0
        cur = float(s.iloc[-1])
        hist = s.iloc[-(lookback + 1):-1]
        mean = float(hist.mean()) if len(hist) else 0.0
        return (cur / mean if mean > 0 else 0.0), mean
    except Exception:
        return 0.0, 0.0


def _breaking_news_for(news_snap, base: str, quote: str, min_score: int) -> list:
    """خبرهای فوریِ مرتبط با این جفت‌ارز."""
    if news_snap is None or not news_snap.ok:
        return []
    out = []
    for it in news_snap.items:
        if not it.breaking or it.score < min_score:
            continue
        if base in it.direction or quote in it.direction or "XAU" in it.direction:
            out.append(it)
    return out


# ── ۷ قاعدهٔ وتو (فاز ۴) ────────────────────────────────────────
# هر دروازه یک تابع مستقل با shape قرارداد odin.judge.veto@1 است:
# (a, sym_cfg, md, ctx) → Veto|None. بدنهٔ هر تابع، جابه‌جاییِ بایت‌به‌بایتِ
# همان بلوک از collect_vetoes قبلی است — فقط مرز عوض شده، نه منطق.
# دو مسیر مصرف دارند:
#   ۱) مستقیم: collect_vetoes با پیش‌فرض _VETO_RULES (رفتار امروز)
#   ۲) rule-plugin: adapterهای نازک در src/plugins/judge.py (ثبت در registry)

def veto_data(a: SymbolAnalysis, sym_cfg: dict, md: Optional[MarketData],
              ctx: JudgeContext) -> Optional[Veto]:
    """⚠️ دادهٔ ناکافی — تعداد کندل‌ها برای EMA200 کافی نیست."""
    if a.verdict == "DATA":
        return Veto("DATA", "⚠️ دادهٔ ناکافی",
                    "تعداد کندل‌ها برای محاسبهٔ EMA200 کافی نیست — تحلیل قابل اتکا نیست")
    return None


def veto_weekend(a: SymbolAnalysis, sym_cfg: dict, md: Optional[MarketData],
                 ctx: JudgeContext) -> Optional[Veto]:
    """🔒 بازار بسته است (شنبه/یکشنبه و جمعه بعد از ۲۱ UTC)."""
    vc = ctx.jcfg["veto"]
    if vc.get("weekend", True) and not ctx.status.open:
        return Veto("WEEKEND", "🔒 بازار بسته است", ctx.status.reason_fa)
    return None


def veto_tf_conflict(a: SymbolAnalysis, sym_cfg: dict, md: Optional[MarketData],
                     ctx: JudgeContext) -> Optional[Veto]:
    """🔀 تضاد جهت بین تایم‌فریم ۴ ساعته و ۱ ساعته."""
    vc = ctx.jcfg["veto"]
    if vc.get("timeframe_conflict", True) and a.verdict != "DATA" and not a.h1_agrees:
        return Veto("TF_CONFLICT", "🔀 تضاد جهت بین تایم‌فریم‌ها",
                    f"روند ۴ ساعته {TREND_FA[a.trend]} است ولی ۱ ساعته هم‌جهت نیست "
                    f"— طبق قوانین، معامله در تضاد تایم‌فریم ممنوع است")
    return None


def veto_range(a: SymbolAnalysis, sym_cfg: dict, md: Optional[MarketData],
               ctx: JudgeContext) -> Optional[Veto]:
    """😴 بازار بی‌روند — ADX زیر analysis.adx_min_trend."""
    vc = ctx.jcfg["veto"]
    acfg = ctx.acfg
    adx_min = float(acfg.get("adx_min_trend", 20))
    if vc.get("range_market", True) and a.verdict != "DATA" and a.adx < adx_min:
        return Veto("RANGE", "😴 بازار بی‌روند (رنج)",
                    f"ADX={a.adx:.0f} زیر آستانهٔ {adx_min:.0f} است — استراتژی روندی "
                    f"در بازار رنج کار نمی‌کند")
    return None


def veto_event(a: SymbolAnalysis, sym_cfg: dict, md: Optional[MarketData],
               ctx: JudgeContext) -> Optional[Veto]:
    """📅 رویداد پراثر تقویم در پنجرهٔ وتو (fundamental.veto_minutes_before)."""
    vc = ctx.jcfg["veto"]
    base, quote = a.base, a.quote
    if vc.get("high_impact_event", True) and ctx.cal_snap is not None:
        evs = veto_for_symbol(ctx.cal_snap, base, quote, ctx.now,
                              minutes=float(ctx.event_veto_minutes))
        if evs:
            names = "، ".join(f"«{e.title_fa}» ({e.country_fa})" for e in evs[:2])
            soon = min(evs, key=lambda e: abs(e.minutes_from(ctx.now)))
            mins = int(round(soon.minutes_from(ctx.now)))
            when = f"{fa_num(abs(mins))} دقیقه {'بعد' if mins >= 0 else 'پیش'}"
            return Veto("EVENT", "📅 رویداد پراثر تقویم",
                        f"{names} — {when}. نوسان خبری غیرقابل پیش‌بینی است")
    return None


def veto_vol_spike(a: SymbolAnalysis, sym_cfg: dict, md: Optional[MarketData],
                   ctx: JudgeContext) -> Optional[Veto]:
    """📈 جهش غیرعادی نوسان — ATR فعلی در برابر میانگین کندل‌های اخیر."""
    vc = ctx.jcfg["veto"]
    acfg = ctx.acfg
    if vc.get("volatility_spike", True) and md is not None:
        vol = ctx.jcfg["volatility"]
        lookback = int(vol.get("lookback_bars", 100))
        ratio, mean = _volatility_ratio(md, acfg, lookback)
        mult = float(vol.get("spike_multiplier", 2.0))
        if ratio and ratio > mult:
            return Veto("VOL_SPIKE", "📈 جهش غیرعادی نوسان",
                         f"ATR یک‌ساعتهٔ فعلی {fa_num(f'{ratio:.1f}')} برابر میانگین "
                         f"{fa_num(lookback)} کندل اخیر است (آستانهٔ وتو: "
                         f"{fa_num(f'{mult:.1f}')} برابر). در این شرایط اسپرد وید می‌شود و "
                         f"حد ضرر قابل اتکا نیست")
    return None


def veto_breaking_news(a: SymbolAnalysis, sym_cfg: dict, md: Optional[MarketData],
                       ctx: JudgeContext) -> Optional[Veto]:
    """🚨 خبر فوریِ مرتبط با جفت‌ارز."""
    vc = ctx.jcfg["veto"]
    base, quote = a.base, a.quote
    if vc.get("breaking_news", True):
        brs = _breaking_news_for(ctx.news_snap, base, quote,
                                 int(ctx.jcfg["news"].get("breaking_min_score", 5)))
        if brs:
            b = brs[0]
            return Veto("BREAKING_NEWS", "🚨 خبر فوری",
                         f"«{b.headline_fa(70)}» — تا آرام‌شدن بازار صبر کن")
    return None


# ترتیب ارزیابی = دقیقاً ترتیب دروازه‌ها در collect_vetoes قبلی (میخِ
# tests/test_judge_rules.py). مسیر rule-plugin هم همین ترتیب را با priority
# مانیفست‌ها پین می‌کند (طلاییِ providers در tests/test_plugins.py).
_VETO_RULES: tuple = (veto_data, veto_weekend, veto_tf_conflict, veto_range,
                      veto_event, veto_vol_spike, veto_breaking_news)


def collect_vetoes(a: SymbolAnalysis, sym_cfg: dict, md: Optional[MarketData],
                   ctx: JudgeContext, rules: Optional[list] = None) -> list[Veto]:
    """همهٔ دروازه‌های وتو را به‌ترتیب بررسی می‌کند.

    rules: فهرست callable با shape (a, sym_cfg, md, ctx)→Veto|None.
    None = هفت قاعدهٔ پیش‌فرض (_VETO_RULES) — بایت‌به‌بایت رفتار امروز.
    """
    v: list[Veto] = []
    for rule in (_VETO_RULES if rules is None else rules):
        veto = rule(a, sym_cfg, md, ctx)
        if veto is not None:
            v.append(veto)
    return v


# ══════════════════════════════════════════════════════════════
#  جدول امتیاز
# ══════════════════════════════════════════════════════════════
def ev_trend(a: SymbolAnalysis, ctx: JudgeContext, direction: str) -> Evidence:
    """هم‌راستایی روند H4 و H1 (+۲ اگر قوی، +۱ اگر متوسط)."""
    strong = a.adx >= float(ctx.acfg.get("adx_strong", 25))
    pts = 2 if strong else 1
    return Evidence(
        "trend", "هم‌راستایی روند ۴ ساعته و ۱ ساعته", pts, 2,
        f"روند {TREND_FA[a.trend]} و تایم‌فریم ۱ ساعته هم تایید می‌کند؛ "
        f"ADX={a.adx:.0f} → {'روند قوی' if strong else 'روند متوسط'}",
        ok=True)


def ev_level(a: SymbolAnalysis, ctx: JudgeContext, direction: str) -> Evidence:
    """پولبک/واکنش به سطح کلیدی (+۲ چسبیده، +۱ نزدیک)."""
    lc = ctx.jcfg["level"]
    level = a.support if direction == "BUY" else a.resistance
    kind = "حمایت" if direction == "BUY" else "مقاومت"
    if not level or a.atr <= 0:
        return Evidence("level", f"واکنش به سطح کلیدی ({kind})", 0, 2,
                        f"سطح {kind} نزدیکی پیدا نشد — این مدرک قابل بررسی نیست",
                        unavailable=True)
    dist = abs(a.price - level)
    ratio = dist / a.atr
    if ratio <= float(lc.get("close_atr", 0.5)):
        pts, word = 2, "قیمت چسبیده به سطح است (واکنش تازه)"
    elif ratio <= float(lc.get("near_atr", 1.5)):
        pts, word = 1, "قیمت نزدیک سطح است"
    else:
        pts, word = 0, "قیمت از سطح فاصله گرفته (دیر رسیده‌ایم)"
    return Evidence("level", f"واکنش به سطح کلیدی ({kind})", pts, 2,
                    f"{kind} {level:.5g} در فاصلهٔ {fa_num(f'{ratio:.1f}')} برابر ATR — {word}",
                    ok=pts > 0)


def ev_fundamental(a: SymbolAnalysis, ctx: JudgeContext, direction: str) -> Evidence:
    """پنجرهٔ فاندامنتال پاک (+۲ بدون رویداد، +۱ با رویداد متوسط)."""
    fc = ctx.jcfg["fundamental"]
    if ctx.cal_snap is None or not ctx.cal_snap.ok:
        why = "تقویم در دسترس نبود" if ctx.cal_snap is not None else "موتور فاندامنتال خاموش است"
        return Evidence("fundamental", "پنجرهٔ فاندامنتال پاک", 0, 2,
                        f"{why} — نمی‌توانیم تاییدش کنیم، پس امتیازی نمی‌گیرد",
                        unavailable=True)
    hi_h = float(fc.get("clean_high_hours", 6))
    md_h = float(fc.get("clean_med_hours", 2))
    highs = upcoming_events(ctx.cal_snap, ctx.now, hours=hi_h, impacts=("HIGH",))
    rel_hi = [e for e in highs if e.affects(a.base, a.quote)]
    meds = upcoming_events(ctx.cal_snap, ctx.now, hours=md_h, impacts=("MEDIUM",))
    rel_md = [e for e in meds if e.affects(a.base, a.quote)]

    if rel_hi:
        e = min(rel_hi, key=lambda x: x.minutes_from(ctx.now))
        hrs = e.minutes_from(ctx.now) / 60.0
        return Evidence("fundamental", "پنجرهٔ فاندامنتال پاک", 0, 2,
                        f"رویداد پراثر «{e.title_fa}» ({e.country_fa}) تا "
                        f"{fa_num(f'{hrs:.1f}')} ساعت دیگر — ورود به معامله قبل از آن ریسک دارد",
                        ok=False)
    if rel_md:
        e = min(rel_md, key=lambda x: x.minutes_from(ctx.now))
        return Evidence("fundamental", "پنجرهٔ فاندامنتال پاک", 1, 2,
                        f"رویداد پراثری تا {fa_num(f'{hi_h:.0f}')} ساعت آینده نیست؛ فقط "
                        f"«{e.title_fa}» (اثر متوسط) تا "
                        f"{fa_num(f'{e.minutes_from(ctx.now)/60:.1f}')} ساعت دیگر", ok=True)
    return Evidence("fundamental", "پنجرهٔ فاندامنتال پاک", 2, 2,
                    f"هیچ رویداد پراثری تا {fa_num(f'{hi_h:.0f}')} ساعت آینده روی "
                    f"{a.base}/{a.quote} نیست — مسیر برای معامله باز است", ok=True)


def ev_momentum(a: SymbolAnalysis, ctx: JudgeContext, direction: str) -> Evidence:
    """تایید مومنتوم با RSI (+۱)."""
    if direction == "BUY":
        if a.rsi_rising and 30 <= a.rsi < 50:
            return Evidence("momentum", "تایید مومنتوم (RSI)", 1, 1,
                            f"RSI={a.rsi:.0f} و رو به بالا ↗️ — پولبک در حال برگشت است "
                            f"(بهترین نقطهٔ ورود)", ok=True)
        if a.rsi < 30:
            return Evidence("momentum", "تایید مومنتوم (RSI)", 0, 1,
                            f"RSI={a.rsi:.0f} در اشباع فروش است — هنوز تایید برگشت نیامده؛ "
                            f"ممکن است «کف‌گیری» ادامه داشته باشد")
        return Evidence("momentum", "تایید مومنتوم (RSI)", 0, 1,
                        f"RSI={a.rsi:.0f} {'رو به بالا نیست' if not a.rsi_rising else 'بالای ۵۰ است'} "
                        f"— مومنتوم، ورود را تایید نمی‌کند")
    if not a.rsi_rising and 50 < a.rsi <= 70:
        return Evidence("momentum", "تایید مومنتوم (RSI)", 1, 1,
                        f"RSI={a.rsi:.0f} و رو به پایین ↘️ — اصلاح رو به بالا در روند نزولی "
                        f"(بهترین نقطهٔ ورود فروش)", ok=True)
    if a.rsi > 70:
        return Evidence("momentum", "تایید مومنتوم (RSI)", 0, 1,
                        f"RSI={a.rsi:.0f} در اشباع خرید است — هنوز تایید برگشت نیامده")
    return Evidence("momentum", "تایید مومنتوم (RSI)", 0, 1,
                    f"RSI={a.rsi:.0f} — مومنتوم، ورود فروش را تایید نمی‌کند")


def ev_strength(a: SymbolAnalysis, ctx: JudgeContext, direction: str) -> Evidence:
    """هم‌جهتی با جریان قدرت ارزها (+۱)."""
    if not ctx.ranking:
        return Evidence("strength", "هم‌جهتی جریان قدرت ارزها", 0, 1,
                        "رتبه‌بندی قدرت ارزها محاسبه نشد", unavailable=True)
    order = [c for c, _ in ctx.ranking]
    if a.base not in order or a.quote not in order:
        return Evidence("strength", "هم‌جهتی جریان قدرت ارزها", 0, 1,
                        f"{a.base} یا {a.quote} در جدول قدرت ارزها نیست", unavailable=True)
    rb, rq = order.index(a.base), order.index(a.quote)
    n = len(order)
    want = f"{a.base} قوی‌تر از {a.quote}" if direction == "BUY" else f"{a.quote} قوی‌تر از {a.base}"
    aligned = (rb < rq) if direction == "BUY" else (rq < rb)
    return Evidence("strength", "هم‌جهتی جریان قدرت ارزها", 1 if aligned else 0, 1,
                    f"رتبهٔ {a.base}: {fa_num(rb + 1)} از {fa_num(n)} | "
                    f"رتبهٔ {a.quote}: {fa_num(rq + 1)} از {fa_num(n)} → "
                    + (f"جریان قدرت به نفع {direction_fa_short(direction)} است ✅" if aligned
                       else f"جریان قدرت خلاف جهت است (برای {want} باید برعکس می‌بود)"),
                    ok=aligned)


def direction_fa_short(direction: str) -> str:
    return "خرید" if direction == "BUY" else "فروش"


def ev_news(a: SymbolAnalysis, ctx: JudgeContext, direction: str) -> Evidence:
    """تایید خبری (+۱)."""
    if ctx.news_snap is None or not ctx.news_snap.ok:
        return Evidence("news", "تایید خبری", 0, 1,
                        "موتور اخبار در دسترس نبود — این مدرک بررسی نشد", unavailable=True)
    vote = news_supports(ctx.news_snap, a.base, a.quote,
                         "buy" if direction == "BUY" else "sell",
                         min_score=int(ctx.jcfg["news"].get("min_score", 4)))
    if vote.verdict > 0:
        titles = "؛ ".join(f"«{i.headline_fa(48)}»" for i in vote.support[:2])
        return Evidence("news", "تایید خبری", 1, 1,
                        f"اخبار جهت {direction_fa_short(direction)} را تایید می‌کند "
                        f"({fa_num(f'{vote.votes:+g}')} رأی): {titles}", ok=True)
    if vote.verdict < 0:
        titles = "؛ ".join(f"«{i.headline_fa(48)}»" for i in vote.contradict[:2])
        return Evidence("news", "تایید خبری", 0, 1,
                        f"⚠️ اخبار خلاف جهت است ({fa_num(f'{vote.votes:+g}')} رأی): {titles}")
    return Evidence("news", "تایید خبری", 0, 1,
                    "اخبار سیگنال روشنی برای این نماد ندارد (خنثی)")


def ev_tradingview(a: SymbolAnalysis, ctx: JudgeContext, direction: str) -> Evidence:
    """هم‌جهتی امتیاز تکنیکال تریدینگ‌ویو (+۱)."""
    tv = ctx.tv_map.get(a.symbol)
    if tv is None:
        return Evidence("tv", "هم‌جهتی با تریدینگ‌ویو", 0, 1,
                        "تاییدیهٔ تریدینگ‌ویو در دسترس نبود", unavailable=True)
    want = 1 if direction == "BUY" else -1
    got = TV_DIR.get(tv.recommendation, 0)
    if got == want:
        return Evidence("tv", "هم‌جهتی با تریدینگ‌ویو", 1, 1,
                        f"امتیاز تکنیکال رسمی تریدینگ‌ویو «{tv.recommendation}» است "
                        f"({fa_num(tv.buy)} خرید/{fa_num(tv.sell)} فروش/"
                        f"{fa_num(tv.neutral)} خنثی) — هم‌جهت با ما ✅", ok=True)
    if got == 0:
        return Evidence("tv", "هم‌جهتی با تریدینگ‌ویو", 0, 1,
                        f"تریدینگ‌ویو خنثی است ({fa_num(tv.buy)} خرید/{fa_num(tv.sell)} فروش/"
                        f"{fa_num(tv.neutral)} خنثی) — کمکی به تایید نمی‌کند")
    return Evidence("tv", "هم‌جهتی با تریدینگ‌ویو", 0, 1,
                    f"⚠️ تریدینگ‌ویو «{tv.recommendation}» می‌گوید — خلاف جهت تحلیل ما")


def ev_session(ctx: JudgeContext) -> Evidence:
    """زمان‌بندی مناسب — سشن لندن یا نیویورک (+۱)."""
    st = ctx.status
    if not st.open:
        return Evidence("session", "زمان‌بندی مناسب (سشن)", 0, 1, st.reason_fa)
    if st.overlap:
        return Evidence("session", "زمان‌بندی مناسب (سشن)", 1, 1,
                        f"سشن {st.label} — بیشترین نقدینگی و کمترین اسپرد هفته", ok=True)
    if st.liquid:
        return Evidence("session", "زمان‌بندی مناسب (سشن)", 1, 1,
                        f"سشن {st.label} — نقدینگی خوب برای جفت‌ارزهای ما", ok=True)
    return Evidence("session", "زمان‌بندی مناسب (سشن)", 0, 1,
                    f"سشن {st.label} — نقدینگی کمتر، حرکت‌ها کم‌جان‌تر و اسپرد نسبتاً بیشتر")


def _ev_session_rule(a: SymbolAnalysis, ctx: JudgeContext, direction: str) -> Evidence:
    """shape یکدستِ قواعد شاهد برای ev_session (فاز ۴) — a/direction نادیده.

    ev_session امروز فقط (ctx) می‌گیرد؛ این wrapper نازک اجازه می‌دهد در
    فهرست قواعد با همان shape هفت شاهد دیگر (a, ctx, direction) بنشیند —
    بدون هیچ تغییر رفتاری (وعدهٔ صریح §۲.۲ سند معماری).
    """
    return ev_session(ctx)


# ترتیب جدول امتیاز = دقیقاً فهرست امروزِ judge_symbol (میخِ
# tests/test_judge_rules.py). مسیر rule-plugin هم همین ترتیب را با priority
# مانیفست‌ها پین می‌کند (طلاییِ providers در tests/test_plugins.py).
_EVIDENCE_RULES: tuple = (ev_trend, ev_level, ev_fundamental, ev_momentum,
                          ev_strength, ev_news, ev_tradingview, _ev_session_rule)


# ══════════════════════════════════════════════════════════════
#  محاسبهٔ ورود / حد ضرر / هدف
# ══════════════════════════════════════════════════════════════
def spread_pips_for(symbol: str, rcfg: dict) -> float:
    """برآوردِ اسپردِ این نماد (پیپ) — برای محاسبهٔ Rِ خالص.

    ⚠️ صادقانه: ODIN به هیچ بروکری وصل نیست، پس اسپردِ *واقعیِ* کاربر را
    نمی‌داند. این عدد از ``judge.risk.spread`` در config می‌آید و یک
    **برآوردِ محافظه‌کارانه** است که کاربر باید با بروکرِ خودش تنظیم کند.

    ``spread.enabled=false`` یا نبودِ بخش → ``0.0`` → Rِ خالص دقیقاً برابرِ
    Rِ ناخالص می‌شود (رفتارِ پیش از v0.29، بدون تغییر). هیچ‌وقت عددِ
    ساختگی حدس زده نمی‌شود.
    """
    sp = (rcfg or {}).get("spread") or {}
    if not sp.get("enabled", True):
        return 0.0
    per = sp.get("per_symbol") or {}
    raw = per.get(symbol, sp.get("default_pips", 0.0))
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return 0.0
    return v if v > 0 else 0.0


def compute_levels(direction: str, entry: float, atr: float,
                   support: Optional[float], resistance: Optional[float],
                   rcfg: dict) -> tuple[float, float, float, bool]:
    """حد ضرر و هدف را حساب می‌کند.

    حد ضرر: کمی آن‌سوی سطح کلیدی (حمایت برای خرید، مقاومت برای فروش).
            اگر سطح در دسترس نبود، بر پایهٔ ATR.
            همیشه بین `min_sl_atr` و `max_sl_atr` برابر ATR نگه داشته می‌شود —
            نه آن‌قدر تنگ که با نویز بخورد، نه آن‌قدر باز که ریسک بزرگ شود.
    هدف:    `reward_risk` برابرِ ریسک (پیش‌فرض ۱:۲).

    Returns: (sl, tp, risk_in_price_units, sl_capped)
    """
    sign = 1 if direction == "BUY" else -1
    if atr <= 0:
        # ATR صفر/منفی یعنی دادهٔ نوسان خراب است؛ بدون این guard حد ضرر و هدف
        # دقیقاً روی قیمت ورود می‌نشستند (ریسک صفر) و سیگنال بی‌معنی می‌شد.
        atr = abs(entry) * 0.001 or float(rcfg.get("fallback_atr", 0.0)) or 1e-9
    buf = float(rcfg.get("level_buffer_atr", 0.3)) * atr
    level = support if direction == "BUY" else resistance
    capped = False

    if level is not None and atr > 0:
        sl = level - sign * buf                 # BUY: زیر حمایت | SELL: بالای مقاومت
    else:
        sl = entry - sign * float(rcfg.get("sl_atr_multiplier", 1.5)) * atr

    max_d = float(rcfg.get("max_sl_atr", 3.0)) * atr
    min_d = float(rcfg.get("min_sl_atr", 0.6)) * atr
    dist = abs(entry - sl)
    if atr > 0 and dist > max_d:
        sl = entry - sign * max_d
        capped = True
    elif atr > 0 and dist < min_d:
        sl = entry - sign * min_d

    risk = abs(entry - sl)
    tp = entry + sign * risk * float(rcfg.get("reward_risk", 2.0))
    return sl, tp, risk, capped


# ══════════════════════════════════════════════════════════════
#  داوری
# ══════════════════════════════════════════════════════════════
def _no_setup_reason(a: SymbolAnalysis, ctx: JudgeContext) -> str:
    """چرا ستاپی شکل نگرفته — توضیح صادقانه به‌جای سکوت."""
    if a.trend == "none":
        return "جهت روند نامشخص است"
    if not a.h1_agrees:
        return "تایم‌فریم ۱ ساعته با ۴ ساعته هم‌جهت نیست"
    adx_min = float(ctx.acfg.get("adx_min_trend", 20))
    if a.adx < adx_min:
        return f"بازار بی‌روند است (ADX={a.adx:.0f} زیر {adx_min:.0f})"
    if a.trend == "bullish":
        return (f"روند صعودی است ولی RSI={a.rsi:.0f} در منطقهٔ پولبک نیست "
                f"(برای ستاپ خرید باید زیر ۴۵ باشد) — یعنی یا دیر رسیده‌ایم "
                f"یا اصلاح هنوز تمام نشده")
    return (f"روند نزولی است ولی RSI={a.rsi:.0f} در منطقهٔ اصلاح رو به بالا نیست "
            f"(برای ستاپ فروش باید بالای ۵۵ باشد)")


# ══════════════════════════════════════════════════════════════
#  دروازهٔ توافق استراتژی‌ها (S3 — v0.26؛ تصمیم مالک: D1=R2, D3=fail-closed)
# ══════════════════════════════════════════════════════════════
_STRAT_DIR_FA = {"BUY": "خرید", "SELL": "فروش", "NONE": "بی‌نظر"}


def _strategy_verdicts(a: SymbolAnalysis, md: Optional[MarketData],
                       ctx: JudgeContext, strategy_rules: list) -> list:
    """ارزیابی صادقانهٔ همهٔ استراتژی‌های تزریق‌شده → فهرست dict.

    Failure Isolation (قاعدهٔ موجود): استراتژیِ خطاداده = «نظر ندارد»
    (NONE با دلیل صادقانه) — هرگز کرش، هرگز دادهٔ جعلی. خروجی dict است
    (نه StrategyVerdict) تا دو موتور shape یکسانِ سریال‌شده داشته باشند.
    """
    out: list = []
    for rule in strategy_rules:
        key = str(getattr(rule, "key", "") or "strategy")
        try:
            v = rule.evaluate(a, md, ctx)
            out.append(v.to_dict() if hasattr(v, "to_dict") else dict(v))
        except Exception:
            out.append({"key": key, "name_fa": "استراتژیِ خطاداده",
                        "direction": "NONE", "strength": 0.0, "proposes": True,
                        "reasons_fa": ["ارزیابی خطا داد؛ نظر صادقانه‌ای نداریم"],
                        "detail_fa": f"{key}: ارزیابی خطا داد"})
    return out


def _no_strategy_reason(direction: str, verdicts: list, min_agree: int,
                        n_total: int, n_prop: int) -> str:
    """دلیل فارسیِ ردِ NO_STRATEGY — صادقانه و کامل (D2/D3)."""
    if not verdicts:
        return ("هیچ استراتژیِ فعالی در دسترس نیست — سیگنال بدون پشتوانهٔ "
                "استراتژی صادر نمی‌شود (دروازهٔ توافق، صادقانه)")
    dir_fa = _STRAT_DIR_FA.get(direction, direction)
    parts = ["«" + str(v.get("name_fa", v.get("key", "?"))) + "» "
             + _STRAT_DIR_FA.get(v.get("direction"), str(v.get("direction")))
             for v in verdicts]
    return (f"توافقِ استراتژی‌ها کافی نیست — هم‌جهت با {dir_fa}: "
            f"{fa_num(n_total)} (پیشنهاددهنده: {fa_num(n_prop)}) از "
            f"{fa_num(len(verdicts))}؛ حداقل لازم: {fa_num(min_agree)} هم‌جهت "
            f"+ {fa_num(1)} پیشنهاددهنده. " + "؛ ".join(parts))


def judge_symbol(a: SymbolAnalysis, sym_cfg: dict, md: Optional[MarketData],
                 ctx: JudgeContext, veto_rules: Optional[list] = None,
                 evidence_rules: Optional[list] = None,
                 risk_fn: Optional[Callable] = None,
                 strategy_rules: Optional[list] = None) -> Judgment:
    """داوری کامل یک نماد. هرگز استثنا پرتاب نمی‌کند.

    veto_rules / evidence_rules / risk_fn (فاز ۴): تزریق *اختیاری* قواعد —
    callableهایی با shape قراردادها (odin.judge.veto@1 / evidence@1 / risk@1).
    None = توابع پیش‌فرض همین ماژول — بایت‌به‌بایت رفتار امروز. مسیر
    rule-plugin (JudgePlugin + registry) همان قواعد را از registry تزریق
    می‌کند؛ طلایی‌های tests/test_plugins.py برابری بایت‌به‌بایت دو مسیر را
    اثبات می‌کنند. scoring عمداً core/plugins را import نمی‌کند — قواعد فقط
    callableاند (استقلال لایهٔ فیچر از چارچوب).

    strategy_rules (S3 — v0.26): همان الگو برای دروازهٔ توافق — فهرستِ
    providerهای odin.strategy@1 (evaluate(a, md, ctx)). None = دروازه خاموش
    (بایت‌به‌بایت رفتار v0.25)؛ فهرستِ خالی = fail-closed صادقانه (D3).
    """
    j = Judgment(symbol=a.symbol, fa_name=a.fa_name, direction=None,
                 max_score=11, price=a.price, pip=a.pip)

    # ۱) وتوها — همیشه اول، چون بدون استثنا هستند
    j.vetoes = collect_vetoes(a, sym_cfg, md, ctx, rules=veto_rules)

    # ۲) آیا اصلاً ستاپی هست که داوری شود؟
    if a.verdict == "BUY_SETUP":
        j.direction = "BUY"
    elif a.verdict == "SELL_SETUP":
        j.direction = "SELL"

    if j.vetoes:
        j.reject_reason = "VETO"
        j.reject_detail = "؛ ".join(v.title_fa for v in j.vetoes)
        return j
    if j.direction is None:
        j.reject_reason = "NO_SETUP"
        j.reject_detail = _no_setup_reason(a, ctx)
        return j

    # ۳) جدول امتیاز
    j.evidences = [rule(a, ctx, j.direction) for rule in
                   (_EVIDENCE_RULES if evidence_rules is None else evidence_rules)]
    j.max_score = sum(e.max_points for e in j.evidences)
    j.score = sum(e.points for e in j.evidences)

    # ۴) هشدارها (مانع صدور نیستند، ولی باید بدانی)
    for e in j.evidences:
        if e.detail_fa.startswith("⚠️"):
            j.warnings.append(e.detail_fa.lstrip("⚠️ ").strip())
    # ۵) آستانه
    if j.score < int(ctx.jcfg.get("min_score", 7)):
        j.reject_reason = "LOW_SCORE"
        j.reject_detail = (f"امتیاز {fa_num(j.score)} از {fa_num(j.max_score)} — زیر "
                           f"آستانهٔ {fa_num(int(ctx.jcfg.get('min_score', 7)))} است، "
                           f"پس سیگنال صادر نمی‌شود")
        return j

    # ۵ب) دروازهٔ توافق استراتژی‌ها (S3 — v0.26)
    # strategy_rules=None → بایت‌به‌بایت رفتار v0.25 (مسیر مستقیم/ارثی).
    # فهرست خالی (همهٔ استراتژی‌ها خاموش) → fail-closed با دلیلِ صادقانه (D3).
    # min_agree<=0 → دروازه خاموش (opt-out صریحِ کاربر) ولی استراتژی‌ها
    # صادقانه ارزیابی و نمایش داده می‌شوند. ترتیب رد: LOW_SCORE مقدم است —
    # پروندهٔ امتیازِ کم همان LOW_SCORE می‌ماند (کمترین جابه‌جاییِ آمار).
    if strategy_rules is not None:
        j.strategies = _strategy_verdicts(a, md, ctx, strategy_rules)
        min_agree = int((getattr(ctx, "strategies_cfg", None) or {}).get("min_agree", 1))
        if min_agree > 0:
            agreeing = [v for v in j.strategies if v.get("direction") == j.direction]
            n_prop = sum(1 for v in agreeing if v.get("proposes"))
            if n_prop < 1 or len(agreeing) < min_agree:
                j.reject_reason = "NO_STRATEGY"
                j.reject_detail = _no_strategy_reason(
                    j.direction, j.strategies, min_agree, len(agreeing), n_prop)
                return j

    # ۶) ساخت سیگنال
    rcfg = ctx.jcfg["risk"]
    # v0.29 (فاز ۲): مبنای معامله قیمتِ *اجرا* است (بستهٔ M15 — آنچه کاربر
    # در عمل می‌تواند با آن وارد شود)، نه لنگرِ تحلیل (بستهٔ H1). حمایت/مقاومت
    # و ev_level عمداً روی `a.price` می‌مانند تا امتیازدهی و وتوها
    # بایت‌به‌بایت دست‌نخورده بمانند؛ سطوح، قیمت‌های مطلقِ بازارند و با
    # قیمتِ اجرای تازه درست‌تر هم جفت می‌شوند.
    # None (تحلیلِ دستیِ تست‌ها، یا نبودِ M15) → صادقانه همان `a.price`،
    # یعنی رفتارِ پیش از v0.29. هرگز صفرِ ساختگی.
    exec_p = getattr(a, "exec_price", None)
    if exec_p is None:
        exec_p = a.price
    _levels = compute_levels if risk_fn is None else risk_fn
    sl, tp, risk, capped = _levels(j.direction, exec_p, a.atr,
                                   a.support, a.resistance, rcfg)
    if capped:
        cap = float(rcfg.get("max_sl_atr", 3.0))
        j.warnings.append(f"حد ضرر از سطح کلیدی دور بود و به سقف "
                          f"{fa_num(f'{cap:.1f}')}×ATR محدود شد")
    opp = a.resistance if j.direction == "BUY" else a.support
    if opp is not None and abs(opp - exec_p) < abs(tp - exec_p):
        kind = "مقاومت" if j.direction == "BUY" else "حمایت"
        j.warnings.append(f"{kind} {opp:.5g} سر راه هدف است — رسیدن به هدف سخت‌تر "
                          f"از چیزی است که نسبت ۱:{fa_ratio(float(rcfg.get('reward_risk', 2.0)))} "
                          f"پیشنهاد می‌دهد")

    pip = a.pip or 0.0001
    # v0.29 (فاز ۳): هزینهٔ معامله — صریح و قابلِ دیدن، نه پنهان در آمار
    spread_pips = spread_pips_for(a.symbol, rcfg)
    risk_pips_v = risk / pip if pip else 0.0
    warn_frac = float((rcfg.get("spread") or {})
                      .get("warn_at_risk_fraction", 0.25))
    if spread_pips > 0 and risk_pips_v > 0 and \
            (spread_pips / 2.0) / risk_pips_v >= warn_frac:
        j.warnings.append(
            f"⚠️ اسپردِ برآوردی ({fa_num(f'{spread_pips:.1f}')} پیپ) نسبت به "
            f"ریسکِ این معامله ({fa_num(f'{risk_pips_v:.1f}')} پیپ) بزرگ است — "
            f"بخشِ قابل‌توجهی از سود را هزینه می‌خورد. حد ضررِ تنگ‌تر از این "
            f"روی این نماد توصیه نمی‌شود")
    j.signal = Signal(
        symbol=a.symbol, fa_name=a.fa_name, direction=j.direction,
        sid=f"{a.symbol}-{j.direction}-{ctx.now:%Y%m%d%H%M%S}-{round(exec_p, 6)}",
        score=j.score, max_score=j.max_score,
        stars=max(1, min(5, round(j.score / j.max_score * 5))) if j.max_score else 1,
        entry=exec_p, sl=sl, tp=tp, pip=pip, atr=a.atr,
        risk_pips=risk / pip, reward_pips=abs(tp - exec_p) / pip,
        rr=float(rcfg.get("reward_risk", 2.0)),
        is_gold=bool(pip >= 0.5), session_fa=ctx.status.label, now=ctx.now,
        evidences=j.evidences, warnings=j.warnings, sl_capped=capped,
        strategies=j.strategies,
        entry_ts=getattr(a, "exec_ts", None),
        spread_pips=spread_pips,
    )
    return j


def judge_all(analyses: list[SymbolAnalysis], datasets: dict, ctx: JudgeContext,
              veto_rules: Optional[list] = None,
              evidence_rules: Optional[list] = None,
              risk_fn: Optional[Callable] = None,
              strategy_rules: Optional[list] = None) -> list[Judgment]:
    """داوری همهٔ نمادها + اعمال سقف تعداد سیگنال در هر چرخه.

    پارامترهای قواعد، pass-through به judge_symbol اند (فاز ۴ + S3) —
    None = رفتار بایت‌به‌بایتِ امروز.
    """
    out = [judge_symbol(a, {}, datasets.get(a.symbol), ctx,
                        veto_rules=veto_rules, evidence_rules=evidence_rules,
                        risk_fn=risk_fn, strategy_rules=strategy_rules)
           for a in analyses]
    cap = int(ctx.jcfg.get("max_signals_per_cycle", 3))
    ready = sorted([j for j in out if j.signal], key=lambda j: -j.score)
    for j in ready[cap:]:
        j.reject_reason = "CAPPED"
        j.reject_detail = (f"امتیاز {fa_num(j.score)} از {fa_num(j.max_score)} کافی بود، "
                           f"ولی سقف {fa_num(cap)} سیگنال در هر چرخه پر شده — "
                           f"بهترین‌ها اولویت دارند")
        j.signal = None
    return out
