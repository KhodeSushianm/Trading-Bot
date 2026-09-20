# -*- coding: utf-8 -*-
"""سیستم طراحی — تم روشنِ شیشه‌ای (Glassmorphism) با لهجهٔ سیاهِ پرکنتراست.

الگو: داشبوردهای مدرن ۲۰۲۶ (مانند رفرنس iDraft):
  • پس‌زمینهٔ خاکستریِ محو + یک پنل شیشه‌ای نیمه‌شفاف روی آن
  • سایدبار به‌شکل **کارت شناور سفید** با آیتم فعال = **پیِل مشکی**
  • کارت‌های سفید با سایهٔ نرم + **کارت‌های مشکیِ پرکنتراست** برای تأکید
  • گوشه‌های خیلی گرد، دکمه‌های دایره‌ای و پیِل‌شکل
  • نمودار خطی و حلقهٔ پیشرفت به‌جای جدول‌های خشک

قانون رنگ (همچنان مونوکروم):
  همه‌چیز سیاه/سفید/خاکستری است؛ تنها سبز (خرید/موفقیت) و قرمز (فروش/وتو)
  به‌عنوان رنگ معنایی مجازند.

⚠️ چرا «شفافیت واقعی/بلور» با QGraphicsBlurEffect پیاده نشده؟
  بلور زنده روی کانتینر همان خانواده باگی است که قبلاً «صفحه سیاه تا درگ» را
  ساخت (اثرهای گرافیکیِ باقی‌مانده/کش‌شده). به‌جایش پس‌زمینه به‌صورت
  **گرادیان‌های proceduralِ ازقبل‌نرم** کشیده می‌شود (ذاتاً smooth، بدون pass بلور)
  و شیشه با یک لایهٔ سفید نیمه‌شفاف ساده ساخته می‌شود. صفر اثر گرافیکی.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Theme:
    """توکن‌های رنگ تم روشن شیشه‌ای."""

    name: str = "light-glass"

    # پس‌زمینه و شیشه
    bg: str = "#E7E7EC"              # پایهٔ خاکستری محو
    bg_alt: str = "#F2F2F5"          # سطح دوم (insetها)
    glass: str = "#FFFFFF"           # رنگ لایهٔ شیشه (با آلفا استفاده می‌شود)
    glass_alpha: float = 0.55

    # سطح‌ها
    card: str = "#FFFFFF"            # کارت سفید
    card_hover: str = "#F7F7F9"
    raised: str = "#EDEDF0"          # کاشی/ورودی خاکستری روشن
    input_bg: str = "#FAFAFC"
    ink_card: str = "#101013"        # کارت مشکی پرکنتراست
    ink_tile: str = "#26262B"        # کاشی داخل کارت مشکی

    # مرزها
    border: str = "#E3E3E8"
    border_strong: str = "#D2D2D9"
    divider: str = "#ECECF0"

    # جوهر (متن) — در تم روشن، «لهجه» سیاه است
    text: str = "#0B0B0C"
    text_2: str = "#55555E"
    text_3: str = "#94949C"
    accent_ink: str = "#0B0B0C"      # برای آیکون‌ها/لوگو روی سطح روشن
    on_ink: str = "#FFFFFF"          # متن/آیکون روی کارت مشکی

    # رنگ‌های معنایی — تنها رنگ‌های مجاز
    green: str = "#1F9D66"
    green_text: str = "#177B50"
    green_tint: str = "#E4F5EC"
    red: str = "#D64545"
    red_text: str = "#B23A3A"
    red_tint: str = "#FBEAEA"

    # شعاع‌ها — بزرگ‌تر از قبل، مطابق رفرنس
    radius_card: int = 22
    radius_ctrl: int = 12
    radius_pill: int = 999

    extra: dict = field(default_factory=dict)

    def rgba(self, hex_color: str, alpha: float) -> str:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"rgba({r}, {g}, {b}, {alpha:.2f})"


DARK = Theme()          # نام تاریخی حفظ شد تا importهای قبلی نشکنند
LIGHT = DARK


class Type:
    DISPLAY = 30
    GREET = 26          # «سلام سوشیان!»
    TITLE = 20
    SECTION = 15
    BODY = 13
    CAPTION = 11
    STAT = 30           # عدد بزرگ داخل کارت مشکی
    MONO = 12


class Space:
    XS = 4
    SM = 8
    MD = 12
    LG = 16
    XL = 24
    XXL = 32


def build_qss(fam: str, t: Theme = DARK, check_img: str = "") -> str:
    """QSS کامل تم روشن شیشه‌ای.

    `check_img`: مسیر مطلق PNG تیک سفید برای چک‌باکس انتخاب‌شده
    (QSS به فایل تصویر نیاز دارد؛ گلیف متنی در indicator ممکن نیست).
    """
    check_rule = (f'image: url("{check_img}");' if check_img else '')
    mono = '"Cascadia Mono", "Consolas", "Courier New"'
    return f"""
* {{ font-family: "{fam}"; outline: none; }}

/* پس‌زمینه توسط paintEvent خودِ central کشیده می‌شود (گرادیان + شیشه)؛
   لذا همهٔ لایه‌های میانی شفاف‌اند تا آن زیر دیده شود. */
QMainWindow, QWidget#app, QStackedWidget#pages, QWidget#page {{
    background: transparent;
    color: {t.text};
    font-size: {Type.BODY}px;
}}
QToolTip {{
    background-color: {t.ink_card}; color: {t.on_ink};
    border: none; border-radius: 10px; padding: 8px 12px;
    font-size: {Type.CAPTION}px;
}}

/* ── هدر ─────────────────────────────────────────────────── */
QFrame#header {{ background: transparent; border: none; }}
QLabel#greet {{ color: {t.text}; font-size: {Type.GREET}px; font-weight: 800; }}
QLabel#appsub {{ color: {t.text_3}; font-size: {Type.CAPTION}px; }}
/* ساعت ارقام فارسی دارد؛ خانوادهٔ mono روی ویندوز برای گلیف‌های فارسی
   قابل اتکا نیست → فونت برنامه (Vazirmatn) کافی است. */
QLabel#clock {{ color: {t.text_3}; font-size: {Type.CAPTION}px; }}

/* ── سایدبار شناور ───────────────────────────────────────── */
QFrame#navcard {{ background: transparent; border: none; }}
QToolButton#navitem {{
    background: transparent; border: none;
    border-radius: {t.radius_pill}px;
    color: {t.text_2}; font-size: {Type.BODY}px; font-weight: 600;
    padding: 10px 14px; text-align: right;
}}
QToolButton#navitem:hover {{ background-color: {t.raised}; color: {t.text}; }}
QToolButton#navitem[active="true"] {{
    background-color: {t.ink_card}; color: {t.on_ink}; font-weight: 700;
}}
QToolButton#navitem[badge="true"] {{ color: {t.red_text}; }}
QLabel#navsection {{
    color: {t.text_3}; font-size: {Type.CAPTION - 1}px; font-weight: 700;
    letter-spacing: 1px;
}}

/* ── عنوان صفحه ──────────────────────────────────────────── */
QLabel#pagetitle {{ color: {t.text}; font-size: {Type.TITLE}px; font-weight: 800; }}
QLabel#pagesub {{ color: {t.text_3}; font-size: {Type.CAPTION}px; }}

/* اسکرول‌-area شفاف داشبورد (ضد سرریز چیدمان در پنجره‌های کوچک) */
QScrollArea#pagescroll {{ background: transparent; border: none; }}
QScrollArea#pagescroll > QWidget > QWidget {{ background: transparent; }}

/* ── کارت‌ها (بدنه توسط SoftCard کشیده می‌شود؛ QSS فقط محتوای متنی) ── */
QLabel#cardtitle {{ color: {t.text}; font-size: {Type.SECTION}px; font-weight: 700; }}
QLabel#cardsub {{ color: {t.text_3}; font-size: {Type.CAPTION}px; }}
QLabel#ink_title {{ color: {t.on_ink}; font-size: {Type.SECTION}px; font-weight: 700; }}
QLabel#ink_sub {{ color: {t.rgba("#FFFFFF", 0.55)}; font-size: {Type.CAPTION}px; }}
QLabel#ink_num {{ color: {t.on_ink}; font-size: {Type.STAT}px; font-weight: 800; }}
QLabel#ink_cap {{ color: {t.rgba("#FFFFFF", 0.55)}; font-size: {Type.CAPTION}px; }}

/* ── کاشی‌های خاکستری داخل کارت مشکی (مثل 28/14/11 رفرنس) ─── */
QFrame#inktile {{
    background-color: {t.ink_tile};
    border: none; border-radius: 14px;
}}
QLabel#tile_num {{ color: {t.on_ink}; font-size: 20px; font-weight: 800; }}
QLabel#tile_cap {{ color: {t.rgba("#FFFFFF", 0.5)}; font-size: {Type.CAPTION - 1}px; }}

/* ── کارت آمار روشن ──────────────────────────────────────── */
QLabel#statnum {{ color: {t.text}; font-size: 24px; font-weight: 800; }}
QLabel#statnum[tone="green"] {{ color: {t.green_text}; }}
QLabel#statnum[tone="red"]   {{ color: {t.red_text}; }}
QLabel#statlabel {{ color: {t.text_3}; font-size: {Type.CAPTION}px; }}

/* ── وضعیت ───────────────────────────────────────────────── */
QFrame#statuspill {{
    border-radius: {t.radius_pill}px; padding: 6px 16px;
    font-weight: 700; font-size: {Type.BODY}px;
    background-color: {t.raised}; color: {t.text_2}; border: none;
}}
QFrame#statuspill[state="ok"]   {{ background-color: {t.green_tint}; color: {t.green_text}; }}
QFrame#statuspill[state="err"]  {{ background-color: {t.red_tint};  color: {t.red_text}; }}
QFrame#statuspill[state="busy"] {{ background-color: {t.ink_card};  color: {t.on_ink}; }}
QLabel#statuspill_txt {{ background: transparent; border: none; }}
/* وقتی قرص وضعیت داخل کارت مشکی است، پس‌زمینهٔ روشن جیغ می‌زند */
QFrame#statuspill[onink="true"] {{
    background-color: rgba(255, 255, 255, 0.14); color: {t.on_ink};
}}
QFrame#statuspill[onink="true"][state="ok"]  {{ background-color: rgba(62, 207, 142, 0.22); color: #7BE0B0; }}
QFrame#statuspill[onink="true"][state="err"] {{ background-color: rgba(255, 93, 93, 0.22); color: #FF9A9A; }}

/* ── دکمه‌ها ─────────────────────────────────────────────── */
QPushButton {{
    border-radius: {t.radius_pill}px; padding: 10px 20px;
    font-size: {Type.BODY}px; font-weight: 600; border: none;
    background-color: {t.raised}; color: {t.text};
}}
QPushButton:hover {{ background-color: {t.border}; }}
QPushButton:pressed {{ background-color: {t.border_strong}; }}
QPushButton:disabled {{ color: {t.text_3}; background-color: {t.bg_alt}; }}

/* اصلی = پیِل مشکی (مثل + Create رفرنس) */
QPushButton#primary {{ background-color: {t.ink_card}; color: {t.on_ink}; font-weight: 700; }}
QPushButton#primary:hover {{ background-color: #26262B; }}
QPushButton#primary:disabled {{ background-color: {t.raised}; color: {t.text_3}; }}

QPushButton#green {{ background-color: {t.green_tint}; color: {t.green_text}; }}
QPushButton#green:hover {{ background-color: #D3EEE1; }}
QPushButton#red {{ background-color: {t.red_tint}; color: {t.red_text}; }}
QPushButton#red:hover {{ background-color: #F6DCDC; }}

/* دایره‌ای (مثل آیکون‌های هدر رفرنس) */
QPushButton#circle {{
    background-color: {t.card}; color: {t.text_2};
    border: 1px solid {t.border}; border-radius: {t.radius_pill}px;
}}
QPushButton#circle:hover {{ color: {t.text}; border-color: {t.border_strong}; }}

QPushButton#ghost {{ background: transparent; color: {t.text_2}; border: 1px solid {t.border_strong}; }}
QPushButton#ghost:hover {{ color: {t.text}; background: {t.card}; }}
QPushButton#subtle {{ background: transparent; color: {t.text_3}; padding: 6px 10px; }}
QPushButton#subtle:hover {{ color: {t.text}; background: {t.raised}; }}

/* ── ورودی‌ها ────────────────────────────────────────────── */
QLineEdit {{
    background-color: {t.input_bg}; border: 1px solid {t.border};
    border-radius: {t.radius_ctrl}px; padding: 10px 14px;
    color: {t.text}; font-size: {Type.BODY}px;
    selection-background-color: {t.raised};
}}
QLineEdit:hover {{ border-color: {t.border_strong}; }}
QLineEdit:focus {{ border-color: {t.ink_card}; }}
QCheckBox {{ spacing: 8px; color: {t.text_2}; }}
QCheckBox::indicator {{
    width: 18px; height: 18px; border-radius: 6px;
    border: 1.5px solid {t.border_strong}; background: {t.card};
}}
QCheckBox::indicator:checked {{
    background: {t.ink_card}; border-color: {t.ink_card}; {check_rule}
}}

/* ── نماهای متنی ─────────────────────────────────────────── */
QPlainTextEdit {{
    background-color: {t.card}; border: 1px solid {t.border};
    border-radius: {t.radius_ctrl}px; padding: 14px;
    color: {t.text_2}; font-size: {Type.MONO + 1}px;
    selection-background-color: {t.raised};
}}
QPlainTextEdit#plain {{
    background-color: {t.bg_alt}; border: 1px solid {t.divider};
    border-radius: 14px; padding: 14px; color: {t.text_2};
}}
QPlainTextEdit#plain:focus {{ border-color: {t.border_strong}; }}

/* ── اسکرول‌بار ──────────────────────────────────────────── */
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 4px; }}
QScrollBar::handle:vertical {{ background: {t.border_strong}; border-radius: 4px; min-height: 32px; }}
QScrollBar::handle:vertical:hover {{ background: {t.text_3}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 8px; margin: 4px; }}
QScrollBar::handle:horizontal {{ background: {t.border_strong}; border-radius: 4px; min-width: 32px; }}

/* ── برچسب‌ها ────────────────────────────────────────────── */
QLabel#sectiontitle {{ color: {t.text}; font-size: {Type.SECTION}px; font-weight: 700; }}
QLabel#sectionsub {{ color: {t.text_3}; font-size: {Type.CAPTION}px; }}
QLabel#hint {{ color: {t.text_3}; font-size: {Type.CAPTION}px; }}
QLabel#label {{ color: {t.text_2}; font-size: {Type.BODY}px; }}
QLabel#strong {{ color: {t.text}; font-size: {Type.BODY}px; font-weight: 600; }}
QLabel#mono {{ color: {t.text_2}; font-family: {mono}; font-size: {Type.MONO}px; }}

/* ── Toast به سبک منوی تیرهٔ رفرنس ───────────────────────── */
QFrame#toast {{
    background-color: {t.ink_card}; border: none; border-radius: 14px;
}}
QLabel#toast_title {{ color: {t.on_ink}; font-size: {Type.BODY}px; font-weight: 700; }}
QLabel#toast_body {{ color: {t.rgba("#FFFFFF", 0.6)}; font-size: {Type.CAPTION}px; }}

/* ── Splash: کارت مشکی روی شیشه (کنتراست برند) ───────────── */
QWidget#splash {{ background: transparent; }}
QLabel#splash_name {{ color: {t.on_ink}; font-size: {Type.DISPLAY}px; font-weight: 800; }}
QLabel#splash_sub {{ color: {t.rgba("#FFFFFF", 0.6)}; font-size: {Type.BODY}px; }}
QLabel#splash_ver {{ color: {t.rgba("#FFFFFF", 0.45)}; font-size: {Type.CAPTION}px; font-family: {mono}; }}
"""
