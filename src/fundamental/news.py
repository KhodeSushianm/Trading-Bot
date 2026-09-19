# -*- coding: utf-8 -*-
"""موتور اخبار — رصد فیدهای RSS رایگان فارکس با امتیازدهی جهت‌دار.

منابع (تست‌شده و رایگان، بدون کلید):
  ForexLive/investingLive  — فارکس‌محور، پرجزئیات
  Investing.com            — سه فید: فارکس، اقتصاد، طلا
  MarketWatch              — نبض بازار آمریکا
  Google News RSS          — زاپاس مقاوم؛ FXStreet را هم پوشش می‌دهد
                             (فید مستقیم FXStreet/DailyFX دسترسی رباتیک را می‌بندد)

هر خبر سه چیز می‌گیرد:
  1) امتیاز اهمیت (۰ تا ۶)
  2) جهت اثر روی ارزها: {USD: +1, JPY: -1, ...}
  3) برچسب «خبر فوری» برای موارد بازارتکان‌ده

قاعدهٔ کلیدی جهت‌دهی: «حرکت قیمت» (rally / slides / slumps) بر «کلیدواژهٔ سیاستی»
(hawkish / rate hike) اولویت دارد، چون اولی مستقیماً می‌گوید چه اتفاقی برای قیمت
افتاده و دومی فقط علت احتمالی است. بدون این قاعده، جملهٔ «ین پس از افزایش نرخ
بهرهٔ بانک ژاپن سقوط کرد» به‌اشتباه صعودی تفسیر می‌شود.

⚠️ نکته صادقانه: جهت‌دهی بر پایهٔ کلیدواژه است (heuristic)، نه درک واقعی متن.
خروجی آن «سرنخ» است نه «حکم قطعی»؛ به همین دلیل در داور امتیازدهی (مرحله ۳)
فقط ۱ امتیاز از ۱۰ وزن دارد و در گزارش هم با همین لحن ارائه می‌شود.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from time import mktime
from typing import Callable, Iterable, Optional

# ── فیدهای پیش‌فرض (اگر در config.yaml چیزی تعریف نشده باشد) ─────
DEFAULT_FEEDS: list[dict] = [
    {"name": "ForexLive", "url": "https://www.forexlive.com/feed", "weight": 2},
    {"name": "Investing.com — فارکس", "url": "https://www.investing.com/rss/news_25.rss", "weight": 1},
    {"name": "Investing.com — اقتصاد", "url": "https://www.investing.com/rss/news_1.rss", "weight": 1},
    {"name": "Investing.com — طلا", "url": "https://www.investing.com/rss/news_11.rss", "weight": 1},
    {"name": "FXStreet (از مسیر Google News)", "weight": 2,
     "url": "https://news.google.com/rss/search?when=1d&q=site:fxstreet.com&hl=en-US&gl=US&ceid=US:en"},
    # MarketWatch (mw_marketpulse) حذف شد: فیدش به‌روزرسانی نمی‌شود (ورودی‌های کهنه)
]

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# ── شناسایی ارزها در متن ───────────────────────────────────────
_CURRENCY_PATTERNS: dict[str, tuple[str, ...]] = {
    # «dollar» تنها وقتی USD است که صفت ملیتی قبلش نیامده باشد
    # (وگرنه «Canadian dollar weakens» به‌اشتباه به USD هم نسبت داده می‌شود)
    "USD": (r"(?<!canadian )(?<!australian )(?<!zealand )(?<!singapore )(?<!hong kong )"
            r"\bdollar(?:s)?\b",
            r"\busd\b", r"\bfed\b", r"\bfederal reserve\b", r"\bfomc\b",
            r"\bpowell\b", r"\bwall street\b", r"\btreasury yields?\b", r"\bunited states\b",
            r"\bus\b(?=\s+(?:economy|data|labor|consumer|dollar|stocks|treasur|jobless))"),
    "EUR": (r"\beuro(?:s)?\b", r"\beur\b", r"\becb\b", r"\blagarde\b", r"\beuro ?zone\b",
            r"\bgerman(?:y)?\b", r"\bfrance\b", r"\bfrench\b", r"\bitaly\b", r"\bitalian\b",
            r"\bspain\b", r"\bspanish\b", r"\bbundesbank\b"),
    "GBP": (r"\bsterling\b", r"\bpound(?:s)?\b", r"\bgbp\b", r"\bboe\b", r"\bbank of england\b",
            r"\bunited kingdom\b", r"\bbritain\b", r"\bbritish\b", r"\buk\b"),
    "JPY": (r"\byen\b", r"\bjpy\b", r"\bboj\b", r"\bbank of japan\b", r"\bjapan(?:ese)?\b",
            r"\bueda\b"),
    "CHF": (r"\bswiss franc\b", r"\bfranc(?:s)?\b", r"\bchf\b", r"\bsnb\b", r"\bswiss\b",
            r"\bswitzerland\b"),
    "CAD": (r"\bcanadian dollar\b", r"\bloonie\b", r"\bcad\b", r"\bboc\b", r"\bbank of canada\b",
            r"\bcanada\b", r"\bcanadian\b"),
    "AUD": (r"\baus(?:sie)? dollar\b", r"\baussie\b", r"\baud\b", r"\brba\b",
            r"\breserve bank of australia\b", r"\baustralia(?:n)?\b"),
    "NZD": (r"\bnzd\b", r"\bkiwi\b", r"\brbnz\b", r"\bnew zealand\b"),
    "CNY": (r"\byuan\b", r"\brenminbi\b", r"\bcny\b", r"\bpboc\b", r"\bchina\b", r"\bchinese\b"),
    "XAU": (r"\bgold\b", r"\bbullion\b", r"\bxau\b"),
    "OIL": (r"\bcrude oil\b", r"\bwti\b", r"\bbrent\b", r"\bopec\b", r"\boils?\b"),
}

# جفت‌ارزهای چسبیده (USDJPY / EURUSD / XAUUSD ...) — بدون مرز کلمه پیدا نمی‌شوند
_PAIR_CODES = ("USD|EUR|GBP|JPY|CHF|CAD|AUD|NZD|CNY|XAU|SEK|NOK|MXN|TRY|ZAR|SGD")
_PAIR_RE = re.compile(rf"\b({_PAIR_CODES})\s*/?\s*({_PAIR_CODES})\b", re.I)

CURRENCY_FA = {
    "USD": "دلار آمریکا", "EUR": "یورو", "GBP": "پوند", "JPY": "ین ژاپن",
    "CHF": "فرانک سوئیس", "CAD": "دلار کانادا", "AUD": "دلار استرالیا",
    "NZD": "دلار نیوزیلند", "CNY": "یوان چین", "XAU": "طلا", "OIL": "نفت",
}

# ── واژگان جهت‌دار ─────────────────────────────────────────────
# گروه ۱) «حرکت قیمت» — مستقیم می‌گوید قیمت چه کرد → اولویت دارد
_PRICE_BULL: list[tuple[str, int, str]] = [
    (r"\brall(?:y|ies|ied)\b", 2, "رالی/صعود"),
    (r"\bsurg(?:e|es|ed|ing)\b", 2, "جهش"),
    (r"\bsoars?\b", 2, "پرواز قیمت"),
    (r"\bjumps?\b", 2, "جهش"),
    (r"\bspikes?\b", 2, "جهش ناگهانی"),
    (r"\bclimbs?\b", 2, "صعود"),
    (r"\bstrengthens?\b|\bappreciat\w+\b", 2, "تقویت"),
    (r"\bgains?\b|\bextends? gains\b", 1, "افزایش"),
    (r"\badvances?\b", 1, "پیشروی"),
    (r"\brises?\b|\bhigher\b", 1, "بالا رفتن"),
    (r"\brebounds?\b|\brecovers\b", 1, "بازگشت/احیا"),
    (r"\btops\b|\bhits (?:new |multi-\w+ )?high", 1, "ثبت سقف"),
    (r"\bupside\b|\bskewed to the upside\b", 2, "تمایل به افزایش"),
    (r"\b(?:two|three|four|\d+)[-\s](?:week|month|day|year|session)[-\s]high\b", 2, "سقف چند دوره‌ای"),
]
_PRICE_BEAR: list[tuple[str, int, str]] = [
    (r"\bplung(?:e|es|ed|ing)\b", 2, "سقوط شدید"),
    (r"\btumbles?\b", 2, "سقوط"),
    (r"\bslumps?\b", 2, "افت شدید"),
    (r"\bsinks?\b", 2, "سقوط"),
    (r"\bselloff\b|\bsell[- ]off\b", 2, "فروش گسترده"),
    (r"\bcrash(?:es|ed|ing)?\b", 2, "سقوط بازار"),
    (r"\bslid(?:e|es|ing)\b|\bslips?\b", 2, "افت"),
    (r"\bweakens?\b|\bdeprecat\w+\b", 2, "ضعیف شدن"),
    (r"\bfalls?\b|\bdrop(?:s|ped)?\b|\blower\b|\bdeclin(?:e|es|ed)\b", 1, "کاهش"),
    (r"\bretraces?\b|\bpull(?:s|ed)? back\b|\bstalls?\b|\bstalling\b", 1, "عقب‌نشینی/توقف"),
    (r"\bunder pressure\b|\bpressured\b", 1, "تحت فشار"),
    (r"\bdownside\b|\bskewed to the downside\b", 2, "تمایل به کاهش"),
    (r"\b(?:two|three|four|\d+)[-\s](?:week|month|day|year|session)[-\s]low\b", 2, "کف چند دوره‌ای"),
    (r"\bhits (?:new |multi-\w+ )?low", 1, "ثبت کف"),
]

# گروه ۲) «کلان/سیاستی» — علت احتمالی؛ فقط وقتی حرکت قیمتی در متن نیست استفاده می‌شود
_MACRO_BULL: list[tuple[str, int, str]] = [
    (r"\bhawkish\b", 2, "هاوکیش (انقباضی)"),
    (r"\brate hike(?:s)?\b|\bhikes? rates?\b", 2, "افزایش نرخ بهره"),
    (r"\bhigher for longer\b", 2, "بهرهٔ بالا برای مدت طولانی"),
    (r"\b(?:beats?|tops?|above) (?:forecast|estimates?|expectations?|consensus)\b", 2, "بهتر از انتظار"),
    (r"\bstrong(?:er|ly)?\b|\bupbeat\b|\bresilien\w+\b", 1, "دادهٔ قوی"),
    (r"\btighten(?:ing)?\b", 1, "انقباض پولی"),
    (r"\bsafe[- ]haven (?:demand|buying|bid|flows?)\b|\bflight to safety\b", 2, "تقاضای پناهگاه امن"),
    (r"\bbid\b|\bsupport(?:s|ed)?\b", 1, "حمایت/تقاضا"),
]
_MACRO_BEAR: list[tuple[str, int, str]] = [
    (r"\bdovish\b", 2, "داویش (انبساطی)"),
    (r"\brate cut(?:s)?\b|\bcuts? rates?\b", 2, "کاهش نرخ بهره"),
    (r"\b(?:misses?|below|worse than) (?:forecast|estimates?|expectations?|consensus)\b", 2, "بدتر از انتظار"),
    (r"\bweak(?:ness|ens|ened|er)?\b|\bsoft(?:ens|ened|er)?\b", 2, "دادهٔ ضعیف"),
    (r"\brecession(?:ary| fears?)?\b", 2, "ترس از رکود"),
    (r"\bdisappoint\w+\b|\bunderwhelm\w+\b", 2, "ناامیدکننده"),
    (r"\beas(?:e|es|ing|ed)\b|\bstimulus\b", 1, "تسهیل پولی"),
    (r"\bintervention\b|\brate check\b", 2, "مداخلهٔ ارزی"),
    (r"\b(?:worst|weakest) (?:week|day|month|session|performance) since\b", 2, "بدترین بازه"),
    (r"\bunderperform(?:s|ed)?\b", 1, "عملکرد ضعیف"),
    (r"\btariffs?\b|\btrade war\b|\bsanctions?\b", 1, "جنگ تجاری/تحریم"),
]

# ریسک‌گریزی (ژئوپلیتیک/بحران) —独立 از دو گروه بالا
_RISK_OFF_RE = re.compile(
    r"\b(?:risk[- ]off|war|wars|attack(?:s|ed)?|strike[sd]?|missile|conflict|"
    r"escalat\w*|sanctions?|shutdown|default(?:s|ed)?|panic|safe[- ]haven|"
    r"flight to safety|geopolit\w+|crisis)\w*\b", re.I)

_BREAKING_RE = re.compile(r"^\s*(?:🚨\s*|\*\*\s*)?(?:breaking|urgent|just in|alert|flash)\b", re.I)
_BREAKING_ANY_RE = re.compile(r"\b(?:breaking news|urgent|just in|market alert)\b", re.I)

# مقالات «جمع‌بندی/پیش‌نگاه» — چندجهتی‌اند و برای جهت‌دهی قابل اتکا نیستند
_ROUNDUP_RE = re.compile(
    r"\b(?:wrap|round ?up|roundup|kickstart|what (?:to watch|we learned)|week ahead|"
    r"things to know|morning (?:briefing|call)|daily (?:brief|recap)|recap|look(?:ing)? ahead|"
    r"top stories|market(?:s)? today|tgif|weekly (?:review|preview))\b", re.I)

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s%$.,/-]", re.UNICODE)
_AGAINST_RE = re.compile(r"\b(?:against|versus|vs\.?|relative to)\b", re.I)

# دارایی‌هایی که «موضوع جمله» می‌توانند باشند ولی در پوشش ما نیستند.
# اگر سوژهٔ اصلی خبر یکی از این‌ها باشد، حرکت قیمت را به ارزهای پوشش‌داده‌شده
# نسبت نمی‌دهیم (مثلاً «Silver soars as the Fed...» ≠ تقویت دلار).
_UNTRACKED_ASSET_RE = re.compile(
    r"\b(?:silver|copper|platinum|palladium|bitcoin|btc|ethereum|eth|crypto\w*|"
    r"bonds?|treasur(?:y|ies)\w*|stocks?|equit\w+|shares?|s&?p ?500|nasdaq|"
    r"dow jones|nikkei|dax|ftse|hang seng)\b", re.I)

_ASSET_CODES = ("XAU", "OIL")

# مداخلهٔ ارزی ژاپن (rate check / intervention) همیشه در جهت تقویت ین است،
# نه در جهت «خبر بد» — این یک قاعدهٔ دامنه‌ای خاص فارکس است.
_JPY_INTERVENTION_RE = re.compile(
    r"\b(?:intervention|rate check|verbal intervention|buying (?:the )?yen|yen buying)\b", re.I)

_SAFE_HAVEN = ("USD", "JPY", "CHF", "XAU")


@dataclass
class NewsItem:
    """یک خبر امتیازدهی‌شده."""

    title: str
    link: str = ""
    source: str = ""
    published: Optional[datetime] = None
    score: int = 0
    direction: dict[str, int] = field(default_factory=dict)   # کد ارز → +1/-1
    keywords: list[str] = field(default_factory=list)
    breaking: bool = False
    roundup: bool = False
    summary: str = ""
    age_minutes: float = 0.0

    @property
    def dedupe_key(self) -> str:
        norm = _PUNCT_RE.sub("", self.title.lower())
        norm = _WS_RE.sub(" ", norm).strip()
        norm = re.sub(r"\s*[-–|]\s*[a-z ]{3,30}$", "", norm)   # حذف پسوند «- FXStreet»
        return hashlib.md5(norm.encode("utf-8")).hexdigest()[:16]

    def direction_fa(self) -> str:
        """مثال: «دلار آمریکا ↑ ، ین ژاپن ↓»"""
        bits = []
        for c, d in sorted(self.direction.items(), key=lambda x: (-abs(x[1]), x[0])):
            bits.append(f"{CURRENCY_FA.get(c, c)} {'↑' if d > 0 else '↓'}")
        return " ، ".join(bits)

    def headline_fa(self, width: int = 78) -> str:
        t = self.title if len(self.title) <= width else self.title[: width - 1] + "…"
        return ("🚨 " if self.breaking else "") + t


@dataclass
class NewsSnapshot:
    """نتیجه رصد اخبار."""

    items: list[NewsItem] = field(default_factory=list)
    fetched_at: Optional[datetime] = None
    feeds_ok: int = 0
    feeds_failed: int = 0
    stale_feeds: list[str] = field(default_factory=list)
    failed_names: list[str] = field(default_factory=list)
    raw_count: int = 0
    error: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.items)

    @property
    def breaking(self) -> list[NewsItem]:
        return [i for i in self.items if i.breaking]

    @property
    def directional(self) -> list[NewsItem]:
        """خبرهایی که جهت مشخص دارند و جمع‌بندی نیستند (قابل اتکا برای داور)."""
        return [i for i in self.items if i.direction and not i.roundup]


# ── شناسایی ارزها ──────────────────────────────────────────────
def currency_spans(text: str) -> list[tuple[str, int]]:
    """فهرست (کد ارز، موقعیت اولین اشاره) — برای قاعدهٔ «X در برابر Y»."""
    low = text.lower()
    spans: dict[str, int] = {}
    for code, pats in _CURRENCY_PATTERNS.items():
        for p in pats:
            m = re.search(p, low)
            if m:
                spans[code] = m.start()
                break
    for m in _PAIR_RE.finditer(text):
        for g in (m.group(1).upper(), m.group(2).upper()):
            if g in CURRENCY_FA or g == "XAU":
                spans.setdefault(g, m.start())
    return sorted(spans.items(), key=lambda x: x[1])


def detect_currencies(text: str) -> list[str]:
    return [c for c, _ in currency_spans(text)]


def subject_spans(text: str) -> list[tuple[str, int]]:
    """مثل currency_spans ولی دارایی‌های خارج از پوشش را با کد «OTHER» هم شامل می‌شود.

    کاربرد: فهمیدن «سوژهٔ اصلی جمله» — اگر زودترین اشاره یک داراییِ خارج از
    پوشش باشد (نقره، بیت‌کوین، اوراق...)، حرکت قیمت را به ارزها نسبت نمی‌دهیم.
    """
    spans = list(currency_spans(text))
    m = _UNTRACKED_ASSET_RE.search(text.lower())
    if m:
        spans.append(("OTHER", m.start()))
    spans.sort(key=lambda x: x[1])
    return spans


def _match_group(text: str, table: list[tuple[str, int, str]]) -> tuple[int, list[str]]:
    total, labels = 0, []
    for pat, w, fa in table:
        if re.search(pat, text):
            total += w
            labels.append(fa)
    return total, labels


def score_text(text: str, wide: str | None = None) -> tuple[int, dict[str, int], list[str], bool, bool]:
    """امتیازدهی جهت‌دار به متن یک خبر.

    Args:
        text: عنوان خبر — مبنای «جهت» است (تیتر، ادعای جهت‌دار را حمل می‌کند)
        wide: عنوان + خلاصه — فقط برای «شناسایی ارزها» استفاده می‌شود.
              خلاصهٔ ForexLive فهرستی از لینک‌های بی‌ربط است و اگر مبنای جهت
              قرار گیرد، جهت‌های متضاد تولید می‌کند.

    Returns:
        (امتیاز ۰..۶، جهت ارزها، کلیدواژه‌های فارسی، خبر فوری؟، جمع‌بندی/پرسشی؟)
    """
    title = text.strip()
    low = title.lower()
    wide_low = (wide or title).lower()

    price_bull, pb_kw = _match_group(low, _PRICE_BULL)
    price_bear, pbr_kw = _match_group(low, _PRICE_BEAR)
    macro_bull, mb_kw = _match_group(low, _MACRO_BULL)
    macro_bear, mbr_kw = _match_group(low, _MACRO_BEAR)

    spans = currency_spans(wide or title)
    currencies = [c for c, _ in spans]
    breaking = bool(_BREAKING_RE.match(title) or _BREAKING_ANY_RE.search(title))
    risk_off = bool(_RISK_OFF_RE.search(wide_low))
    # عنوان پرسشی یا جمع‌بندی هفته → چندجهتی است، جهت صادر نمی‌کنیم
    roundup = bool(_ROUNDUP_RE.search(low)) or title.endswith("?")
    kws = (pb_kw + pbr_kw + mb_kw + mbr_kw)[:4]

    if not currencies:
        return (1 if breaking else 0), {}, kws, breaking, roundup

    # ── جهت خالص: حرکت قیمت بر کلیدواژهٔ سیاستی اولویت دارد ──
    pa = price_bull - price_bear
    ma = macro_bull - macro_bear
    if pa != 0:
        net = 1 if pa > 0 else -1
    elif ma != 0:
        net = 1 if ma > 0 else -1
    else:
        net = 0

    direction: dict[str, int] = {}
    pair_fired = False
    subj = subject_spans(wide or title)
    subject = subj[0][0] if subj else None

    if subject == "OTHER":
        # سوژهٔ اصلی، داراییِ خارج از پوشش است (نقره/بیت‌کوین/اوراق...) → جهت صادر نمی‌کنیم
        net = 0
    elif roundup:
        net = 0                                   # صادقانه‌تر از حدس زدن
    elif net == 0:
        pass
    else:
        pair = _PAIR_RE.search(title)
        if pair and pair.group(1).upper() != pair.group(2).upper():
            # «USDJPY surges» → USD بالا، JPY پایین. قوی‌ترین و مطمئن‌ترین الگو.
            b, q = pair.group(1).upper(), pair.group(2).upper()
            direction = {b: net, q: -net}
            pair_fired = True
        else:
            against = _AGAINST_RE.search(title)
            if against and len(currencies) >= 2:
                idx = against.start()
                s_subj = [c for c, p in spans if p < idx]
                s_obj = [c for c, p in spans if p >= idx]
                if s_subj and s_obj:
                    for c in s_subj:
                        direction[c] = net
                    for c in s_obj:
                        direction[c] = -net
            if not direction:
                for c in currencies:
                    direction[c] = (1 if c in _SAFE_HAVEN else -1) if risk_off else net

        # اگر سوژهٔ جمله یک دارایی است (طلا/نفت) و الگوی جفت‌ارز هم پیدا نشد،
        # جهت را فقط به همان دارایی نسبت بده — نه به ارزهای اشارهٔ جانبی
        if not pair_fired and subject in _ASSET_CODES:
            direction = {c: v for c, v in direction.items() if c in _ASSET_CODES}

    # قاعدهٔ دامنه‌ای: مداخلهٔ ارزی/rate check ژاپن همیشه به نفع ین است
    if _JPY_INTERVENTION_RE.search(wide_low) and "JPY" in currencies:
        direction["JPY"] = 1
        if "USD" in direction:
            direction["USD"] = -1

    # ── امتیاز ──────────────────────────────────────────────
    score = 1                                        # مرتبط با بازار (ارز دارد)
    score += 2 if abs(pa) >= 2 else (1 if pa else 0)  # صراحت حرکت قیمت
    score += 1 if ma else 0                           # پشتوانهٔ کلان
    if risk_off:
        score += 1
    if breaking:
        score += 1
    if len(currencies) >= 2 and net != 0:
        score += 1
    if roundup:
        score = min(score, 2)                         # جمع‌بندی‌ها سقف کوتاه دارند
    return min(score, 6), direction, kws, breaking, roundup


# ── پارس فید ───────────────────────────────────────────────────
def _strip_html(s: str) -> str:
    s = _TAG_RE.sub(" ", str(s or ""))
    for a, b in (("&amp;", "&"), ("&quot;", '"'), ("&#39;", "'"), ("&apos;", "'"),
                 ("&nbsp;", " "), ("&rsquo;", "’"), ("&lsquo;", "‘"),
                 ("&ldquo;", "“"), ("&rdquo;", "”"), ("&#8217;", "’"), ("&#8220;", "“"),
                 ("&#8221;", "”"), ("&#8211;", "–"), ("&#8212;", "—"), ("&lt;", "<"),
                 ("&gt;", ">")):
        s = s.replace(a, b)
    return _WS_RE.sub(" ", s).strip()


def _to_dt(entry) -> Optional[datetime]:
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        st = entry.get(key)
        if st:
            try:
                return datetime.fromtimestamp(mktime(st), tz=timezone.utc)
            except Exception:
                continue
    for key in ("published", "updated"):
        v = entry.get(key)
        if v:
            try:
                d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
                return d.astimezone(timezone.utc) if d.tzinfo else d.replace(tzinfo=timezone.utc)
            except Exception:
                continue
    return None


def _source_name(entry, feed_name: str) -> str:
    src = entry.get("source") or {}
    if isinstance(src, dict) and src.get("title"):
        return str(src["title"]).strip()
    return feed_name


def _clean_title(title: str) -> str:
    t = _strip_html(title)
    for sep in (" - ", " | ", " – "):          # Google News: «عنوان - منبع»
        if sep in t:
            head, tail = t.rsplit(sep, 1)
            if head and len(tail) <= 32 and not tail.endswith("."):
                t = head.strip()
                break
    return t


def parse_entries(entries: Iterable[dict], feed_name: str, weight: int = 1,
                  now: datetime | None = None,
                  max_age_hours: float = 30.0,
                  min_score: int = 2) -> list[NewsItem]:
    """تبدیل ورودی‌های feedparser به NewsItem (قابل تست، بدون اینترنت)."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=max_age_hours)
    out: list[NewsItem] = []
    for e in entries or []:
        raw_title = str(e.get("title") or "")
        if not raw_title.strip():
            continue
        src = _source_name(e, feed_name)
        title = _clean_title(raw_title)
        summary = _strip_html(e.get("summary") or e.get("description") or "")
        pub = _to_dt(e)
        if pub is not None and pub < cutoff:
            continue                                        # خبر کهنه
        if pub is not None and pub > now + timedelta(minutes=30):
            pub = now                                       # ساعت آینده = خطای فید
        # جهت از «عنوان» و شناسایی ارزها از «عنوان + خلاصه» گرفته می‌شود
        score, direction, kws, breaking, roundup = score_text(title, wide=f"{title}. {summary[:300]}")
        score = min(6, score + (1 if weight >= 2 and score >= 3 else 0))
        if score < min_score:
            continue
        out.append(NewsItem(
            title=title, link=str(e.get("link") or ""), source=src, published=pub,
            score=score, direction=direction, keywords=kws, breaking=breaking,
            roundup=roundup, summary=summary[:200],
            age_minutes=((now - pub).total_seconds() / 60.0) if pub else 0.0,
        ))
    return out


def _http_get(url: str, timeout: int = 15) -> bytes:
    """درخواست با هدر مرورگری (بعضی فیدها به User-Agent پیش‌فرض پایتون ۴۰۳ می‌دهند)."""
    import requests
    r = requests.get(url, headers={"User-Agent": _UA, "Accept": "*/*",
                                   "Accept-Language": "en-US,en;q=0.9"}, timeout=timeout)
    r.raise_for_status()
    return r.content


def fetch_news(cfg: dict | None = None,
               on_log: Callable[[str], None] | None = None,
               max_age_hours: float | None = None) -> NewsSnapshot:
    """دریافت و امتیازدهی اخبار از همه فیدهای فعال. هرگز استثنا پرتاب نمی‌کند."""
    ncfg = (cfg or {}).get("news") or {}
    log = on_log or (lambda _m: None)
    if not ncfg.get("enabled", True):
        s = NewsSnapshot(error="غیرفعال در تنظیمات")
        log("[i] موتور اخبار در تنظیمات غیرفعال است")
        return s

    try:
        import feedparser
    except ImportError:
        log("[!] کتابخانه feedparser نصب نیست — موتور اخبار رد شد (pip install feedparser)")
        s = NewsSnapshot()
        s.error = "feedparser نصب نیست"
        return s

    feeds = ncfg.get("feeds") or DEFAULT_FEEDS
    now = datetime.now(timezone.utc)
    age = float(max_age_hours if max_age_hours is not None else ncfg.get("max_age_hours", 30))
    min_score = int(ncfg.get("min_score", 2))
    per_feed = int(ncfg.get("max_items_per_feed", 12))
    total_max = int(ncfg.get("max_total", 18))

    snap = NewsSnapshot(fetched_at=now)
    seen: set[str] = set()
    items_all: list[NewsItem] = []

    for f in feeds:
        name = str(f.get("name") or f.get("url") or "feed")
        url = str(f.get("url") or "")
        if not url:
            continue
        try:
            parsed = feedparser.parse(_http_get(url))
            entries = list(getattr(parsed, "entries", []) or [])
            if not entries:
                raise ValueError("فید خالی یا بدون ورودی بود")
            items = parse_entries(entries, name, int(f.get("weight", 1)),
                                  now=now, max_age_hours=age, min_score=min_score)
            items.sort(key=lambda x: (x.published or now), reverse=True)
            items = items[:per_feed]
            fresh = [it for it in items if it.dedupe_key not in seen]
            for it in fresh:
                seen.add(it.dedupe_key)
            items_all.extend(fresh)
            snap.feeds_ok += 1
            snap.raw_count += len(entries)
            if not fresh and entries:
                snap.stale_feeds.append(name)
                log(f"[i] {name}: همهٔ {len(entries)} ورودی کهنه یا تکراری بودند — رد شد")
            else:
                log(f"📰 {name}: {len(fresh)} خبر تازه (از {len(entries)} ورودی)")
        except Exception as e:
            snap.feeds_failed += 1
            snap.failed_names.append(name)
            log(f"[!] فید {name} ناموفق: {str(e)[:70]}")

    items_all.sort(key=lambda x: (-x.score, x.age_minutes))   # مهم‌ترین و تازه‌ترین اول
    snap.items = items_all[:total_max]
    if not snap.items:
        snap.error = "خبر مرتبطی در بازهٔ زمانی پیدا نشد"
        log(f"[!] موتور اخبار: {snap.error}")
    else:
        br = len(snap.breaking)
        log(f"✅ موتور اخبار: {len(snap.items)} خبر "
            f"({snap.feeds_ok} فید موفق، {snap.feeds_failed} ناموفق"
            + (f"، {br} فوری" if br else "") + ")")
    return snap


# ── پرس‌وجو برای داور ──────────────────────────────────────────
def market_movers(snap: NewsSnapshot, min_score: int = 4) -> list[NewsItem]:
    """خبرهایی که ارزش هشدار دادن دارند."""
    return [i for i in snap.items if i.score >= min_score or i.breaking]


@dataclass
class NewsVote:
    """نتیجهٔ سنجش اخبار نسبت به یک جفت‌ارز و یک جهت پیشنهادی."""

    bias: str
    votes: float = 0.0
    support: list = field(default_factory=list)       # خبرهای هم‌جهت
    contradict: list = field(default_factory=list)    # خبرهای خلاف‌جهت
    verdict: int = 0                                  # +1 تایید | 0 خنثی | −1 خلاف

    @property
    def has_evidence(self) -> bool:
        return bool(self.support or self.contradict)


def news_supports(snap: NewsSnapshot, base: str, quote: str, bias: str,
                  min_score: int = 4) -> NewsVote:
    """آیا اخبار، جهت پیشنهادی (bias=buy/sell) یک جفت‌ارز را تایید می‌کنند؟

    دو قاعدهٔ مهم برای صادقانه ماندن:
      • فقط خبرهایی که جهت مشخص دارند و «جمع‌بندی هفته» نیستند شمارش می‌شوند.
      • خبرهایی با «امضای جهت» یکسان فقط یک بار شمرده می‌شوند؛ سه سایت که یک
        روایت را تکرار کرده‌اند سه مدرک نیستند، یک مدرک‌اند.

    Returns:
        NewsVote با votes در بازهٔ −۲..+۲ (مثبت = به نفع خرید)
    """
    want = 1 if str(bias).lower().startswith("b") else -1
    vote = NewsVote(bias=bias)
    seen_sig: set[tuple] = set()
    raw = 0.0

    ranked = sorted(snap.items, key=lambda x: -x.score)
    for it in ranked:
        if it.roundup or it.score < min_score or not it.direction:
            continue
        sig = tuple(sorted(it.direction.items()))
        if sig in seen_sig:
            continue                                  # روایت تکراری — یک بار بیشتر نه
        seen_sig.add(sig)

        db, dq = it.direction.get(base, 0), it.direction.get(quote, 0)
        if db and dq:
            if db == dq:
                continue                              # هر دو یک‌جهت → برای «جفت» بی‌معنی
            pair_dir = db
        elif db:
            pair_dir = db
        elif dq:
            pair_dir = -dq
        else:
            continue

        w = 1.0 if it.score >= 5 else 0.6
        raw += want * pair_dir * w
        (vote.support if want * pair_dir > 0 else vote.contradict).append(it)

    vote.votes = round(max(-2.0, min(2.0, raw)), 2)
    vote.verdict = 1 if vote.votes >= 1 else (-1 if vote.votes <= -1 else 0)
    return vote
