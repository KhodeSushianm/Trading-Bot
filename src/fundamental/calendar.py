# -*- coding: utf-8 -*-
"""موتور فاندامنتال — تقویم اقتصادی.

منبع: فید JSON هفتگی ForexFactory (رایگان، بدون کلید):
    https://nfs.faireconomy.media/ff_calendar_thisweek.json
هر رویداد شامل: country (کد ارز)، date (ISO با منطقه زمانی)، title، impact
(High/Medium/Low)، forecast و previous است.

چه چیزی می‌سازد:
  1) CalendarSnapshot — فهرست رویدادهای هفته با عنوان فارسی، دسته و قطبیت
  2) دروازه وتو — اگر رویداد پراثرِ ارزِ پایه یا مظنه در N دقیقه آینده باشد،
     سیگنال آن نماد ممنوع است (قانون بدون استثنا در طراحی پروژه)
  3) تفسیر به زبان ساده — «اگر بالاتر از انتظار باشد → دلار تقویت → ...»

⚠️ نکته صادقانه: فید فقط «همین هفته» را پوشش می‌دهد (شنبه تا جمعه).
در روزهای پایانی هفته ممکن است رویداد آینده‌ای در آن نباشد؛ این حالت
به‌صورت شفاف در گزارش ذکر می‌شود، نه اینکه وانمود کنیم خبری نیست.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Iterable, Optional

import requests

from .. import app_paths

SOURCE_NAME = "ForexFactory"
FF_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
CACHE_FILE = "calendar.json"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

IMPACT_FA = {"HIGH": "🔴 پراثر", "MEDIUM": "🟠 اثر متوسط", "LOW": "🟢 کم‌اثر"}
IMPACT_EMOJI = {"HIGH": "🔴", "MEDIUM": "🟠", "LOW": "🟢"}

# کد ارز → (نام فارسی کشور/منطقه، نام فارسی ارز)
CURRENCY_FA = {
    "USD": ("آمریکا", "دلار آمریکا"),
    "EUR": ("منطقه یورو", "یورو"),
    "GBP": ("بریتانیا", "پوند"),
    "JPY": ("ژاپن", "ین ژاپن"),
    "CHF": ("سوئیس", "فرانک سوئیس"),
    "CAD": ("کانادا", "دلار کانادا"),
    "AUD": ("استرالیا", "دلار استرالیا"),
    "NZD": ("نیوزیلند", "دلار نیوزیلند"),
    "CNY": ("چین", "یوان چین"),
    "SEK": ("سوئد", "کرون سوئد"),
    "NOK": ("نروژ", "کرون نروژ"),
    "MXN": ("مکزیک", "پزوی مکزیک"),
    "TRY": ("ترکیه", "لیر ترکیه"),
    "ZAR": ("آفریقای جنوبی", "رند"),
    "KRW": ("کره جنوبی", "وون"),
    "SGD": ("سنگاپور", "دلار سنگاپور"),
    "INR": ("هند", "روپیه هند"),
    "BRL": ("برزیل", "رئال برزیل"),
    "All": ("جهانی", "بازار جهانی"),
}

# عنوان انگلیسی → فارسی (رویدادهای پرتکرار؛ بقیه با قاعده ترجمه می‌شوند)
TITLE_FA = {
    "CPI m/m": "تورم ماهانه (CPI)",
    "CPI y/y": "تورم سالانه (CPI)",
    "Core CPI m/m": "تورم هسته ماهانه",
    "Core CPI y/y": "تورم هسته سالانه",
    "Final CPI y/y": "تورم سالانه (نهایی)",
    "Final Core CPI y/y": "تورم هسته سالانه (نهایی)",
    "Common CPI y/y": "تورم عمومی سالانه",
    "Median CPI y/y": "تورم میانه سالانه",
    "Trimmed CPI y/y": "تورم تعدیل‌شده سالانه",
    "National Core CPI y/y": "تورم هسته ملی سالانه",
    "French Final CPI m/m": "تورم ماهانه فرانسه (نهایی)",
    "German PPI m/m": "تورم تولیدکننده آلمان ماهانه",
    "German WPI m/m": "تورم عمده‌فروشی آلمان ماهانه",
    "PPI Input m/m": "تورم نهاده‌های تولید ماهانه",
    "IPPI m/m": "شاخص قیمت محصولات صنعتی ماهانه",
    "HPI y/y": "شاخص قیمت مسکن سالانه",
    "NHPI m/m": "شاخص قیمت مسکن جدید ماهانه",
    "New Home Prices m/m": "قیمت مسکن نوساز ماهانه",
    "Import Prices m/m": "قیمت واردات ماهانه",
    "Federal Funds Rate": "نرخ بهره فدرال رزرو",
    "FOMC Statement": "بیانیه کمیته بازار آزاد فدرال (FOMC)",
    "FOMC Press Conference": "کنفرانس مطبوعاتی فدرال رزرو",
    "FOMC Economic Projections": "پیش‌بینی‌های اقتصادی فدرال رزرو",
    "Official Bank Rate": "نرخ بهره رسمی بانک مرکزی",
    "MPC Official Bank Rate Votes": "رأی‌گیری کمیته سیاست پولی بر سر نرخ بهره",
    "Monetary Policy Summary": "خلاصه سیاست پولی",
    "Monetary Policy Statement": "بیانیه سیاست پولی",
    "BOJ Policy Rate": "نرخ بهره بانک مرکزی ژاپن",
    "BOJ Press Conference": "کنفرانس مطبوعاتی بانک مرکزی ژاپن",
    "ECB President Lagarde Speaks": "سخنرانی لاگارد (رئیس بانک مرکزی اروپا)",
    "German Buba President Nagel Speaks": "سخنرانی ناگل (رئیس بوندس‌بانک آلمان)",
    "FOMC Member Bowman Speaks": "سخنرانی بومن (عضو فدرال رزرو)",
    "FOMC Member Schmid Speaks": "سخنرانی اشمید (عضو فدرال رزرو)",
    "BOC Summary of Deliberations": "خلاصه مذاکرات بانک مرکزی کانادا",
    "Claimant Count Change": "تغییر شمار متقاضیان بیمه بیکاری",
    "ADP Weekly Employment Change": "اشتغال هفتگی ADP",
    "Average Earnings Index 3m/y": "شاخص میانگین درآمد (۳ ماهه سالانه)",
    "Unemployment Rate": "نرخ بیکاری",
    "GDP q/q": "رشد اقتصادی فصلی (GDP)",
    "Industrial Production m/m": "تولید صنعتی ماهانه",
    "Industrial Production y/y": "تولید صنعتی سالانه",
    "Core Retail Sales m/m": "خرده‌فروشی هسته ماهانه",
    "Retail Sales m/m": "خرده‌فروشی ماهانه",
    "Manufacturing Sales m/m": "فروش بخش تولید ماهانه",
    "Business Inventories m/m": "موجودی انبار بنگاه‌ها ماهانه",
    "Building Permits": "پروانه‌های ساخت",
    "Building Permits m/m": "پروانه‌های ساخت ماهانه",
    "Housing Starts": "شروع ساخت مسکن",
    "NAHB Housing Market Index": "شاخص بازار مسکن NAHB",
    "Empire State Manufacturing Index": "شاخص تولید امپایر استیت نیویورک",
    "German ZEW Economic Sentiment": "سنتیمنت اقتصادی ZEW آلمان",
    "Capacity Utilization Rate": "نرخ بهره‌برداری از ظرفیت تولید",
    "CB Leading Index m/m": "شاخص پیشرو کنفرانس بورد ماهانه",
    "MI Leading Index m/m": "شاخص پیشرو مؤسسه ملبورن ماهانه",
    "Current Account": "تراز جاری",
    "Italian Trade Balance": "تراز تجاری ایتالیا",
    "Core Machinery Orders m/m": "سفارش ماشین‌آلات هسته ماهانه",
    "Foreign Securities Purchases": "خرید اوراق بهادار توسط خارجی‌ها",
    "Foreign Direct Investment ytd/y": "سرمایه‌گذاری مستقیم خارجی (از ابتدای سال)",
    "Fixed Asset Investment ytd/y": "سرمایه‌گذاری در دارایی ثابت (از ابتدای سال)",
    "New Loans": "وام‌های جدید بانکی",
    "M2 Money Supply y/y": "نقدینگی M2 سالانه",
    "NBS Press Conference": "کنفرانس مطبوعاتی اداره آمار چین",
    "Crude Oil Inventories": "موجودی نفت خام",
    "Natural Gas Storage": "موجودی گاز طبیعی",
    "API Weekly Statistical Bulletin": "گزارش هفتگی مؤسسه نفت آمریکا",
    "GDT Price Index": "شاخص قیمت لبنیات GDT",
    "FPI m/m": "شاخص قیمت مواد غذایی ماهانه",
    "BusinessNZ Services Index": "شاخص خدمات BusinessNZ",
    "German 30-y Bond Auction": "حراج اوراق ۳۰ ساله آلمان",
    "ECOFIN Meetings": "جلسات وزیران اقتصاد و دارایی اتحادیه اروپا",
    "Eurogroup Meetings": "جلسات گروه یورو",
    "BRICS Summit": "نشست سران بریکس",
}

# دسته‌بندی (برای رنگ‌آمیزی گزارش و توضیح ساده)
_CATEGORIES: list[tuple[str, tuple[str, ...]]] = [
    ("نرخ بهره و بانک مرکزی", ("Rate", "FOMC", "MPC", "BOJ", "ECB", "Monetary Policy",
                              "Speaks", "Press Conference", "Statement", "Minutes",
                              "Votes", "Projections", "Bond Auction", "Deliberations")),
    ("تورم و قیمت‌ها", ("CPI", "PPI", "WPI", "HPI", "NHPI", "IPPI", "Price", "Inflation",
                     "Import Prices")),
    ("اشتغال و بازار کار", ("Employment", "Payroll", "Unemployment", "Jobless", "Claimant",
                        "Earnings", "Labour", "Labor", "Wage", "NFP")),
    ("رشد و فعالیت اقتصادی", ("GDP", "PMI", "Industrial Production", "Retail Sales",
                          "Manufacturing", "Services", "Sentiment", "ZEW", "IFO",
                          "Leading Index", "Capacity", "Business", "Trade", "Orders",
                          "Inventories", "Loans", "Money Supply", "Investment", "Account")),
    ("مسکن و ساخت‌وساز", ("Housing", "Home", "Building Permits", "NAHB", "Construction")),
    ("انرژی و کالا", ("Crude Oil", "Natural Gas", "GDT", "Gold", "FPI", "Commodity")),
]

# شاخص‌هایی که «عدد کمتر = خبر بهتر برای ارز» (برعکس بقیه)
_LOWER_IS_BETTER = ("Unemployment", "Claimant Count", "Jobless", "Initial Claims",
                    "Continuing Claims", "Budget Balance", "Trade Deficit")

# پسوند → معادل فارسی
_SUFFIX_FA = ((" ytd/y", " (از ابتدای سال)"), (" 3m/y", " (۳ ماههٔ سالانه)"),
              (" m/m", " (ماه‌به‌ماه)"), (" y/y", " (سال‌به‌سال)"),
              (" q/q", " (فصل‌به‌فصل)"), (" w/w", " (هفته‌به‌هفته)"))


@dataclass
class CalendarEvent:
    """یک رویداد تقویم اقتصادی."""

    when: datetime                 # همیشه UTC و timezone-aware
    country: str                   # کد ارز (USD/EUR/...) یا All
    title: str                     # عنوان اصلی انگلیسی
    title_fa: str                  # عنوان فارسی
    impact: str                    # HIGH | MEDIUM | LOW
    forecast: str = ""
    previous: str = ""
    category: str = "سایر"
    polarity: int = 0              # +1: عدد بالاتر = تقویت ارز | -1: برعکس | 0: بی‌طرف
    source: str = SOURCE_NAME

    @property
    def key(self) -> str:
        """کلید یکتا (برای جلوگیری از هشدار تکراری)."""
        return f"{self.country}|{self.when:%Y%m%dT%H%M}|{self.title}"

    @property
    def country_fa(self) -> str:
        return CURRENCY_FA.get(self.country, (self.country, self.country))[0]

    @property
    def currency_fa(self) -> str:
        return CURRENCY_FA.get(self.country, (self.country, self.country))[1]

    def affects(self, base: str, quote: str) -> bool:
        """آیا این رویداد روی جفت‌ارز base/quote اثر دارد؟"""
        return self.country in (base, quote, "All")

    def minutes_from(self, now: datetime) -> float:
        return (self.when - now).total_seconds() / 60.0

    def explain(self, symbols_cfg: Iterable[dict], now: datetime) -> str:
        """تفسیر یک‌خطی به زبان ساده: چه می‌شود اگر عدد بالاتر/پایین‌تر از انتظار باشد."""
        f = self.forecast.strip()
        p = self.previous.strip()
        nums = (f or p) and self.polarity != 0
        head = f"{IMPACT_EMOJI.get(self.impact, '⚪')} {self.when:%H:%M} — {self.country_fa}: {self.title_fa}"
        if not nums:
            if self.polarity == 0 and self.impact == "HIGH":
                return (f"{head}\n      🔎 رویداد پراثر ولی بدون عدد پیش‌بینی (مثل سخنرانی/بیانیه) — "
                        f"بازار به لحن و محتوای آن واکنش می‌دهد؛ نزدیک این ساعت معامله نکن")
            bits = [b for b in (f"پیش‌بینی {f}" if f else "", f"قبلی {p}" if p else "") if b]
            return head + ("\n      🔎 " + " | ".join(bits) if bits else "")

        better = "بالاتر" if self.polarity > 0 else "پایین‌تر"
        worse = "پایین‌تر" if self.polarity > 0 else "بالاتر"
        note = "" if self.polarity > 0 else " (برای این شاخص، عدد کمتر = خبر بهتر)"
        pairs = _affected_pairs(self.country, symbols_cfg)
        line = (f"{head}\n      🔎 پیش‌بینی {f or '—'} | قبلی {p or '—'} → "
                f"اگر عدد {better} از انتظار باشد {self.currency_fa} تقویت می‌شود"
                f" و اگر {worse} باشد ضعیف{note}")
        if pairs:
            # تقویت ارز پایه → جفت صعودی ؛ تقویت ارز مظنه → جفت نزولی (بدون وابستگی به قطبیت)
            pos = [s["name"] for s in pairs if s.get("base") == self.country]
            neg = [s["name"] for s in pairs if s.get("quote") == self.country]
            tips = []
            if pos:
                tips.append(f"{'، '.join(pos)} ↑ صعودی")
            if neg:
                tips.append(f"{'، '.join(neg)} ↓ نزولی")
            line += f"\n      💡 در صورت تقویت {self.currency_fa}: " + " | ".join(tips)
        return line


@dataclass
class CalendarSnapshot:
    """نتیجه دریافت تقویم اقتصادی."""

    events: list[CalendarEvent] = field(default_factory=list)
    fetched_at: Optional[datetime] = None
    source: str = SOURCE_NAME
    from_cache: bool = False
    stale: bool = False
    error: str = ""
    week_range: tuple[str, str] = ("", "")
    fetched: bool = False        # آیا دریافت زنده از منبع موفق بود؟

    @property
    def ok(self) -> bool:
        """دادهٔ قابل استفاده داریم؟ (زنده یا از کش — هر دو قابل قبول‌اند)."""
        return bool(self.events)

    @property
    def live(self) -> bool:
        """آیا این داده تازه از منبع گرفته شده (نه کش کهنه)؟"""
        return self.fetched and not self.error

    @property
    def high_impact(self) -> list[CalendarEvent]:
        return [e for e in self.events if e.impact == "HIGH"]


def _clean(s) -> str:
    return str(s or "").strip()


def _translate_title(title: str) -> str:
    """ترجمه عنوان: اول از جدول، بعد با قاعده (پسوند + عبارت ناشناخته)."""
    t = _clean(title)
    if t in TITLE_FA:
        return TITLE_FA[t]
    for suf, fa in _SUFFIX_FA:
        if t.endswith(suf):
            base = t[: -len(suf)]
            return (TITLE_FA.get(base, base) + fa) if base in TITLE_FA else f"{base}{fa}"
    return t


def _categorize(title: str) -> str:
    for cat, keys in _CATEGORIES:
        if any(k.lower() in title.lower() for k in keys):
            return cat
    return "سایر"


def _polarity(title: str) -> int:
    """+1 یعنی «عدد بالاتر = خبر خوب برای آن ارز»."""
    low = title.lower()
    if any(k.lower() in low for k in _LOWER_IS_BETTER):
        return -1
    if any(k in title for k in ("CPI", "PPI", "WPI", "HPI", "NHPI", "IPPI", "GDP", "PMI",
                                "Retail Sales", "Industrial Production", "Employment",
                                "Payroll", "Earnings", "Orders", "Sentiment", "ZEW", "IFO",
                                "Rate", "Leading Index", "Capacity", "Housing Starts",
                                "Building Permits", "Manufacturing", "Services")):
        return 1
    return 0


def parse_events(raw: list[dict]) -> list[CalendarEvent]:
    """تبدیل JSON خام ForexFactory به رویدادهای نرمال‌شده (قابل تست بدون اینترنت)."""
    out: list[CalendarEvent] = []
    for e in raw or []:
        ds = _clean(e.get("date"))
        if not ds:
            continue
        try:
            when = datetime.fromisoformat(ds.replace("Z", "+00:00"))
        except ValueError:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        when = when.astimezone(timezone.utc)
        title = _clean(e.get("title"))
        if not title:
            continue
        out.append(CalendarEvent(
            when=when,
            country=_clean(e.get("country")) or "All",
            title=title,
            title_fa=_translate_title(title),
            impact=_clean(e.get("impact")).upper() or "LOW",
            forecast=_clean(e.get("forecast")),
            previous=_clean(e.get("previous")),
            category=_categorize(title),
            polarity=_polarity(title),
        ))
    out.sort(key=lambda x: x.when)
    return out


def _affected_pairs(country: str, symbols_cfg: Iterable[dict]) -> list[dict]:
    return [s for s in symbols_cfg if s.get("base") == country or s.get("quote") == country]


# ── کش ─────────────────────────────────────────────────────────
def _read_cache(ttl_min: float) -> tuple[list[dict] | None, datetime | None, bool]:
    """خواندن کش. خروجی: (داده خام یا None، زمان ذخیره، آیا از TTL گذشته)."""
    p = app_paths.cache_dir() / CACHE_FILE
    try:
        with open(p, encoding="utf-8") as f:
            blob = json.load(f)
        raw = blob.get("events")
        ts = datetime.fromisoformat(blob["fetched_at"])
        stale = (datetime.now(timezone.utc) - ts).total_seconds() > ttl_min * 60
        return (raw if isinstance(raw, list) else None), ts, stale
    except Exception:
        return None, None, True


def _write_cache(raw: list[dict]) -> None:
    try:
        with open(app_paths.cache_dir() / CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({"fetched_at": datetime.now(timezone.utc).isoformat(), "events": raw},
                      f, ensure_ascii=False)
    except Exception:
        pass  # کش فقط بهینه‌سازی است — نبودنش نباید برنامه را متوقف کند


def fetch_calendar(cfg: dict | None = None,
                   on_log: Callable[[str], None] | None = None,
                   use_cache: bool = True,
                   timeout: int = 15) -> CalendarSnapshot:
    """دریافت تقویم اقتصادی (با کش محلی و زاپاس داده قدیمی در صورت قطعی).

    هرگز استثنا پرتاب نمی‌کند — در بدترین حالت snapshot خالی با error برمی‌گرداند.
    """
    fcfg = (cfg or {}).get("fundamental") or {}
    ttl = float(fcfg.get("cache_ttl_minutes", 30))
    log = on_log or (lambda _m: None)
    url = str(fcfg.get("source_url") or FF_URL)

    if use_cache:
        raw, ts, stale = _read_cache(ttl)
        if raw is not None and not stale:
            log(f"🏦 تقویم اقتصادی از کش محلی خوانده شد ({len(raw)} رویداد)")
            return _build(raw, fetched_at=ts, from_cache=True, stale=False)

    try:
        r = requests.get(url, headers={"User-Agent": _UA, "Accept": "application/json"},
                         timeout=timeout)
        r.raise_for_status()
        raw = r.json()
        if not isinstance(raw, list):
            raise ValueError("ساختار پاسخ تقویم نامعتبر است")
        _write_cache(raw)
        log(f"🏦 تقویم اقتصادی دریافت شد: {len(raw)} رویداد ({SOURCE_NAME})")
        return _build(raw, fetched_at=datetime.now(timezone.utc), from_cache=False, stale=False)
    except Exception as e:
        msg = f"{type(e).__name__}: {str(e)[:90]}"
        raw, ts, _ = _read_cache(ttl_min=10 ** 9)   # هر کشی، حتی کهنه، بهتر از هیچی است
        if raw:
            log(f"[!] تقویم اقتصادی زنده ناموفق بود ({msg[:70]}) — از کش قدیمی استفاده می‌شود")
            snap = _build(raw, fetched_at=ts, from_cache=True, stale=True, fetched=False)
            snap.error = msg
            return snap
        log(f"[!] تقویم اقتصادی در دسترس نیست: {msg[:90]}")
        snap = CalendarSnapshot()
        snap.error = msg
        return snap


def _build(raw: list[dict], fetched_at, from_cache: bool, stale: bool,
           fetched: bool = True) -> CalendarSnapshot:
    events = parse_events(raw)
    dates = sorted({e.when.date() for e in events})
    rng = (f"{dates[0]:%Y-%m-%d}", f"{dates[-1]:%Y-%m-%d}") if dates else ("", "")
    return CalendarSnapshot(events=events, fetched_at=fetched_at, from_cache=from_cache,
                            stale=stale, week_range=rng, fetched=fetched)


# ── پرس‌وجو ────────────────────────────────────────────────────
def upcoming_events(snap: CalendarSnapshot, now: datetime | None = None,
                    hours: float = 72.0, impacts: tuple[str, ...] = ("HIGH", "MEDIUM"),
                    countries: Iterable[str] | None = None,
                    limit: int | None = None) -> list[CalendarEvent]:
    """رویدادهای آینده در بازهٔ hours ساعت، فقط با اثر مشخص‌شده."""
    now = now or datetime.now(timezone.utc)
    end = now + timedelta(hours=hours)
    cset = {c.upper() for c in countries} if countries else None
    out = [e for e in snap.events
           if now <= e.when <= end
           and e.impact in impacts
           and (cset is None or e.country.upper() in cset or e.country == "All")]
    if limit:
        out = out[:limit]
    return out


def events_in_window(snap: CalendarSnapshot, start: datetime, end: datetime,
                     impacts: tuple[str, ...] = ("HIGH",)) -> list[CalendarEvent]:
    return [e for e in snap.events if start <= e.when <= end and e.impact in impacts]


def veto_for_symbol(snap: CalendarSnapshot, base: str, quote: str,
                    now: datetime, minutes: float = 30.0) -> list[CalendarEvent]:
    """دروازه وتو: رویدادهای پراثرِ نزدیک که سیگنال این نماد را ممنوع می‌کنند.

    فقط رویدادهای مربوط به ارز پایه یا مظنه (و رویدادهای جهانی «All») شمارش می‌شوند.
    """
    win_start = now - timedelta(minutes=15)      # رویدادی که تازه اعلام شده هم بازار را تکان می‌دهد
    win_end = now + timedelta(minutes=max(0.0, minutes))
    return [e for e in snap.events
            if e.impact == "HIGH" and win_start <= e.when <= win_end
            and (e.country in (base, quote) or e.country == "All")]


def next_high_impact(snap: CalendarSnapshot, base: str | None = None, quote: str | None = None,
                     now: datetime | None = None) -> Optional[CalendarEvent]:
    """نزدیک‌ترین رویداد پراثر آینده (اختیاراً فقط برای یک جفت‌ارز)."""
    now = now or datetime.now(timezone.utc)
    for e in snap.events:
        if e.when < now or e.impact != "HIGH":
            continue
        if base and not e.affects(base, quote or ""):
            continue
        return e
    return None
