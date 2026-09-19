# -*- coding: utf-8 -*-
"""سیستم طراحی (Design Tokens) — تم تاریک مونوکروم، سبک Fluent ویندوز ۱۱.

قانون رنگ (تصمیم کاربر):
  همه‌چیز **سیاه و سفید** است. تنها استثنا دو رنگ معنایی‌اند:
    سبز → خرید / موفقیت        قرمز → فروش / وتو / خطا
  هیچ رنگ سوم (آبی، بنفش، کهربایی…) در رابط وجود ندارد.
  «هشدار/احتیاط» هم با آیکون و وزن متن متمایز می‌شود، نه با رنگ جدید.

چرا زمینه «مشکیِ مطلق» نیست؟
  #000000 روی نمایشگرهای OLED هاله (smear) می‌سازد و کنتراست متن سفید رویش
  برای خواندن طولانی خسته‌کننده است. پس از یک سیاهِ بسیار تیره با ته‌رنگ
  خنثی استفاده می‌شود — همان کاری که ویندوز ۱۱ و Fluent می‌کنند.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Theme:
    """توکن‌های رنگ یک تم. فعلاً فقط DARK ساخته می‌شود (انتخاب کاربر)."""

    name: str

    # لایه‌های سطح (از پایین به بالا) — عمق با روشنیِ تدریجی ساخته می‌شود، نه سایهٔ سنگین
    bg: str = "#0B0B0D"
    bg_alt: str = "#0F0F12"
    card: str = "#151519"
    card_hover: str = "#1A1A1F"
    raised: str = "#202026"
    input_bg: str = "#0E0E11"

    # خطوط موئی (hairline) — مرز اصلی طراحی مینیمال
    border: str = "#26262C"
    border_strong: str = "#34343C"
    divider: str = "#1E1E23"

    # متن — سه سطح سلسله‌مراتب
    text: str = "#F4F4F7"
    text_2: str = "#9E9EA8"
    text_3: str = "#63636D"

    # رنگ‌های معنایی — تنها رنگ‌های مجاز رابط
    green: str = "#3ECF8E"
    green_text: str = "#5CE0A6"
    green_tint: str = "#10251C"
    red: str = "#FF5D5D"
    red_text: str = "#FF7A7A"
    red_tint: str = "#2B1416"

    # سفیدِ خالص برای لحظه‌های تأکید (لوگو، عدد بزرگ داشبورد)
    accent_ink: str = "#FFFFFF"

    # اندازه‌ها
    radius_card: int = 14
    radius_ctrl: int = 9
    radius_pill: int = 999

    extra: dict = field(default_factory=dict)

    # ── دسترسی سریع ──────────────────────────────────────────
    def rgba(self, hex_color: str, alpha: float) -> str:
        """تبدیل #RRGGBB + آلفا به rgba() برای QSS."""
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"rgba({r}, {g}, {b}, {alpha:.2f})"


DARK = Theme(name="dark")


# ══════════════════════════════════════════════════════════════
#  مقیاس تایپوگرافی
# ══════════════════════════════════════════════════════════════
class Type:
    """اندازهٔ قلم‌ها به پیکسل. سلسله‌مراتب شفاف و کم‌تعداد."""
    DISPLAY = 30      # نام کاربر در Splash
    TITLE = 20        # عنوان صفحه
    SECTION = 14      # عنوان کارت/بخش
    BODY = 13         # متن اصلی
    CAPTION = 11      # برچسب‌ها و راهنماها
    STAT = 26         # عدد بزرگ کارت آمار
    MONO = 12         # اعداد/قیمت‌ها در جدول‌ها


# ══════════════════════════════════════════════════════════════
#  فاصله‌گذاری (spacing scale)
# ══════════════════════════════════════════════════════════════
class Space:
    XS = 4
    SM = 8
    MD = 12
    LG = 16
    XL = 24
    XXL = 32


# ══════════════════════════════════════════════════════════════
# StyleSheet
# ══════════════════════════════════════════════════════════════
def build_qss(fam: str, t: Theme = DARK) -> str:
    """QSS کامل رابط بر پایهٔ توکن‌ها.

    نکتهٔ مهم: QSS نمی‌تواند «انیمیشن» بدهد؛ انیمیشن‌ها در effects.py با
    QPropertyAnimation ساخته می‌شوند. QSS فقط حالت‌های ایستا و hover است.
    """
    mono = '"Cascadia Mono", "Consolas", "Courier New"'
    return f"""
/* ── پایه ───────────────────────────────────────────────────── */
* {{
    font-family: "{fam}";
    outline: none;
}}
QMainWindow, QWidget#app {{
    background-color: {t.bg};
    color: {t.text};
    font-size: {Type.BODY}px;
}}
QToolTip {{
    background-color: {t.raised};
    color: {t.text};
    border: 1px solid {t.border_strong};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: {Type.CAPTION}px;
}}

/* ── سربرگ ─────────────────────────────────────────────────── */
QFrame#header {{
    background-color: {t.bg};
    border-bottom: 1px solid {t.divider};
}}
QLabel#appname {{
    color: {t.accent_ink};
    font-size: 16px;
    font-weight: 700;
    letter-spacing: 0.2px;
}}
QLabel#appsub {{
    color: {t.text_3};
    font-size: {Type.CAPTION}px;
}}
QFrame#greetchip {{
    background-color: {t.card};
    border: 1px solid {t.border};
    border-radius: {t.radius_pill}px;
    padding: 4px 12px;
}}
QLabel#greetchip_txt {{
    color: {t.text_2};
    font-size: {Type.CAPTION}px;
}}
QLabel#clock {{
    color: {t.text_3};
    font-size: {Type.CAPTION}px;
    font-family: {mono};
}}

/* ── ریل ناوبری ────────────────────────────────────────────── */
QFrame#navrail {{
    background-color: {t.bg_alt};
    border-left: 1px solid {t.divider};   /* در RTL، ریل سمت راست است و مرزش چپ */
}}
QToolButton#navitem {{
    background: transparent;
    border: none;
    border-radius: {t.radius_ctrl}px;
    color: {t.text_2};
    font-size: {Type.BODY}px;
    font-weight: 600;
    padding: 10px 12px;
    text-align: right;
}}
QToolButton#navitem:hover {{
    background-color: {t.card_hover};
    color: {t.text};
}}
QToolButton#navitem[active="true"] {{
    background-color: {t.card};
    color: {t.accent_ink};
}}
QToolButton#navitem[badge="true"] {{
    color: {t.red_text};
}}
/* نوار نشانگر فعال — یک خط باریک سفید کنار آیتم فعال */
QFrame#navindicator {{
    background-color: {t.accent_ink};
    border-radius: 2px;
}}

/* ── عنوان صفحه ────────────────────────────────────────────── */
QLabel#pagetitle {{
    color: {t.accent_ink};
    font-size: {Type.TITLE}px;
    font-weight: 700;
}}
QLabel#pagesub {{
    color: {t.text_3};
    font-size: {Type.CAPTION}px;
}}

/* ── کارت‌ها ───────────────────────────────────────────────── */
QFrame#card {{
    background-color: {t.card};
    border: 1px solid {t.border};
    border-radius: {t.radius_card}px;
}}
QFrame#card_flat {{
    background-color: transparent;
    border: 1px solid {t.border};
    border-radius: {t.radius_card}px;
}}
QLabel#cardtitle {{
    color: {t.text};
    font-size: {Type.SECTION}px;
    font-weight: 700;
}}
QLabel#cardsub {{
    color: {t.text_3};
    font-size: {Type.CAPTION}px;
}}
QFrame#cardline {{
    background-color: {t.divider};
    max-height: 1px;
    border: none;
}}

/* ── کارت آمار ─────────────────────────────────────────────── */
QFrame#stat {{
    background-color: {t.bg_alt};
    border: 1px solid {t.border};
    border-radius: {t.radius_ctrl}px;
}}
QLabel#statnum {{
    color: {t.accent_ink};
    font-size: {Type.STAT}px;
    font-weight: 700;
    font-family: {mono};
}}
QLabel#statnum[tone="green"] {{ color: {t.green_text}; }}
QLabel#statnum[tone="red"]   {{ color: {t.red_text}; }}
QLabel#statlabel {{
    color: {t.text_3};
    font-size: {Type.CAPTION}px;
}}

/* ── وضعیت ─────────────────────────────────────────────────── */
QFrame#statuspill {{
    border-radius: {t.radius_pill}px;
    padding: 5px 14px;
    font-weight: 700;
    font-size: {Type.BODY}px;
    border: 1px solid {t.border_strong};
    background-color: {t.card};
    color: {t.text_2};
}}
QFrame#statuspill[state="ok"] {{
    background-color: {t.green_tint};
    border-color: {t.rgba(t.green, 0.35)};
    color: {t.green_text};
}}
QFrame#statuspill[state="err"] {{
    background-color: {t.red_tint};
    border-color: {t.rgba(t.red, 0.35)};
    color: {t.red_text};
}}
QFrame#statuspill[state="busy"] {{
    background-color: {t.raised};
    border-color: {t.border_strong};
    color: {t.accent_ink};
}}
QLabel#statuspill_txt {{ background: transparent; border: none; }}

/* ── دکمه‌ها ───────────────────────────────────────────────── */
QPushButton {{
    border-radius: {t.radius_ctrl}px;
    padding: 9px 18px;
    font-size: {Type.BODY}px;
    font-weight: 600;
    border: 1px solid transparent;
    background-color: {t.raised};
    color: {t.text};
}}
QPushButton:hover {{ background-color: {t.card_hover}; border-color: {t.border_strong}; }}
QPushButton:pressed {{ background-color: {t.card}; }}
QPushButton:disabled {{ color: {t.text_3}; background-color: {t.bg_alt}; border-color: {t.border}; }}

/* اصلی: سفیدِ خالص روی سیاه — امضای تم مونوکروم */
QPushButton#primary {{
    background-color: {t.accent_ink};
    color: #0A0A0B;
    border: none;
    font-weight: 700;
}}
QPushButton#primary:hover {{ background-color: #E4E4E8; }}
QPushButton#primary:pressed {{ background-color: #CFCFD4; }}
QPushButton#primary:disabled {{ background-color: {t.raised}; color: {t.text_3}; }}

/* معنایی: فقط برای اقدامهای خرید/فروش/توقف */
QPushButton#green {{
    background-color: {t.rgba(t.green, 0.16)};
    color: {t.green_text};
    border: 1px solid {t.rgba(t.green, 0.40)};
}}
QPushButton#green:hover {{ background-color: {t.rgba(t.green, 0.24)}; }}
QPushButton#red {{
    background-color: {t.rgba(t.red, 0.14)};
    color: {t.red_text};
    border: 1px solid {t.rgba(t.red, 0.40)};
}}
QPushButton#red:hover {{ background-color: {t.rgba(t.red, 0.22)}; }}

/* شبح: فقط مرز، برای اقدامهای ثانویه */
QPushButton#ghost {{
    background: transparent;
    border: 1px solid {t.border_strong};
    color: {t.text_2};
}}
QPushButton#ghost:hover {{ color: {t.text}; border-color: {t.text_3}; background: {t.card_hover}; }}

/* ظریف: بدون مرز، برای لینک‌مانندها */
QPushButton#subtle {{
    background: transparent;
    border: none;
    color: {t.text_3};
    padding: 6px 10px;
}}
QPushButton#subtle:hover {{ color: {t.text}; background: {t.card_hover}; }}

/* ── ورودی‌ها ──────────────────────────────────────────────── */
QLineEdit {{
    background-color: {t.input_bg};
    border: 1px solid {t.border};
    border-radius: {t.radius_ctrl}px;
    padding: 9px 12px;
    color: {t.text};
    font-size: {Type.BODY}px;
    selection-background-color: {t.raised};
}}
QLineEdit:hover {{ border-color: {t.border_strong}; }}
QLineEdit:focus {{ border-color: {t.accent_ink}; }}
QLineEdit:disabled {{ color: {t.text_3}; }}

QCheckBox {{ spacing: 8px; color: {t.text_2}; font-size: {Type.BODY}px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border-radius: 4px;
    border: 1px solid {t.border_strong};
    background: {t.input_bg};
}}
QCheckBox::indicator:hover {{ border-color: {t.text_3}; }}
QCheckBox::indicator:checked {{
    background: {t.accent_ink};
    border-color: {t.accent_ink};
    image: none;
}}

/* ── ناحیهٔ متن گزارش‌ها ───────────────────────────────────── */
QPlainTextEdit {{
    background-color: {t.bg_alt};
    border: 1px solid {t.border};
    border-radius: {t.radius_ctrl}px;
    padding: 12px;
    color: {t.text_2};
    font-size: {Type.MONO + 1}px;
    line-height: 1.5;
    selection-background-color: {t.raised};
}}
QPlainTextEdit:focus {{ border-color: {t.border_strong}; }}
/* نمای داخلی برای فهرست‌های داخل کارت‌ها.
   ⚠️ background باید SOLID باشد، نه transparent: با پس‌زمینهٔ شفاف،
   QPlainTextEdit روی بعضی پلتفرم‌ها متن را تا اولین repaint کامل (درگ/resize)
   رسم نمی‌کند — همان باگ «صفحه سیاه تا درگ». */
QPlainTextEdit#plain {{
    background-color: {t.bg_alt};
    border: 1px solid {t.divider};
    border-radius: 10px;
    padding: 12px;
    color: {t.text_2};
}}
QPlainTextEdit#plain:focus {{ border-color: {t.border_strong}; }}

/* ── اسکرول‌بار مینیمال ────────────────────────────────────── */
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 4px; }}
QScrollBar::handle:vertical {{
    background: {t.border_strong};
    border-radius: 4px;
    min-height: 32px;
}}
QScrollBar::handle:vertical:hover {{ background: {t.text_3}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: 8px; margin: 4px; }}
QScrollBar::handle:horizontal {{ background: {t.border_strong}; border-radius: 4px; min-width: 32px; }}

/* ── برچسب‌های متنی ────────────────────────────────────────── */
QLabel#sectiontitle {{ color: {t.text}; font-size: {Type.SECTION}px; font-weight: 700; }}
QLabel#sectionsub {{ color: {t.text_3}; font-size: {Type.CAPTION}px; }}
QLabel#hint {{ color: {t.text_3}; font-size: {Type.CAPTION}px; }}
QLabel#label {{ color: {t.text_2}; font-size: {Type.BODY}px; }}
QLabel#strong {{ color: {t.text}; font-size: {Type.BODY}px; font-weight: 600; }}
QLabel#mono {{ color: {t.text_2}; font-family: {mono}; font-size: {Type.MONO}px; }}

/* ── Toast (اعلان شناور) ───────────────────────────────────── */
QFrame#toast {{
    background-color: {t.raised};
    border: 1px solid {t.border_strong};
    border-radius: {t.radius_card}px;
}}
QLabel#toast_title {{ color: {t.accent_ink}; font-size: {Type.BODY}px; font-weight: 700; }}
QLabel#toast_body {{ color: {t.text_2}; font-size: {Type.CAPTION}px; }}

/* ── Splash ────────────────────────────────────────────────── */
QWidget#splash {{ background: transparent; }}
QLabel#splash_name {{
    color: {t.accent_ink};
    font-size: {Type.DISPLAY}px;
    font-weight: 800;
    letter-spacing: 0.5px;
}}
QLabel#splash_sub {{ color: {t.text_3}; font-size: {Type.BODY}px; }}
QLabel#splash_ver {{ color: {t.text_3}; font-size: {Type.CAPTION}px; font-family: {mono}; }}
"""
