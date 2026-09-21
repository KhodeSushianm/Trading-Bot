#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""کارت تصویری سیگنال (v0.19.0) — همزادِ js/sharecard.js اندروید.

دو لایه:
  build_share_spec(sig, version) → dict با **دقیقاً همان رشته‌های** نسخهٔ JS
      (تست test_sharecard.py با وکتورهای مشترک قفلش کرده — هر دو پلتفرم
      یک تصویر یکسان تولید می‌کنند)
  render_card_pixmap(spec)       → QPixmap ۱۰۸۰×۱۳۵۰ با QPainter
      (واردکردن PySide6 تنبل است تا ماژول در CI بدون Qt هم import شود)

sig: dict یا آبجکت با فیلدهای signal داور:
  symbol, fa_name, direction, stars, score, max_score, entry, sl, tp,
  pip, is_gold, rr, now (datetime), session_fa
"""
from __future__ import annotations

from datetime import datetime, timezone

from src.fa import (fa_num, fa_pips, fa_ratio, jalali_fa, hhmm_teh)
from src.report.signal import fmt_price

CW, CH = 1080, 1350        # نسبت ۴:۵ — بهینهٔ اینستاگرام/تلگرام

BRAND = "ODIN ASSISTANT"
BRAND_SUB = "دستیار تحلیل فارکس و طلا — غیرخودکار"
FOOTER_NAME = "سازنده: Sushian Khoshkhani"
FOOTER_TG = "@Khode_Sushian"
DISCLAIMER = "این یک پیشنهاد است، نه دستور معامله — مسئولیت هر معامله با خودت است."


def _get(s, key, default=None):
    if isinstance(s, dict):
        return s.get(key, default)
    return getattr(s, key, default)


def build_share_spec(sig, version: str = "0.19.0") -> dict:
    """spec کارت — کلیدها/رشته‌ها دقیقاً مثل O.buildShareSpec در JS."""
    pip = float(_get(sig, "pip", 0.0001) or 0.0001)
    entry = float(_get(sig, "entry"))
    sl = float(_get(sig, "sl"))
    tp = float(_get(sig, "tp"))
    score = _get(sig, "score", 0)
    max_score = _get(sig, "max_score", 11) or 11
    stars = int(_get(sig, "stars", 0) or 0)
    is_gold = bool(_get(sig, "is_gold"))
    direction = "SELL" if str(_get(sig, "direction")).upper().startswith("S") else "BUY"
    symbol = str(_get(sig, "symbol"))
    now = _get(sig, "now") or datetime.now(timezone.utc)
    if isinstance(now, str):
        now = datetime.fromisoformat(now)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    return {
        "w": CW, "h": CH,
        "brand": BRAND,
        "brandSub": BRAND_SUB,
        "dir": direction,
        "dirLabel": "سیگنال خرید" if direction == "BUY" else "سیگنال فروش",
        "pair": symbol[:3] + "/" + symbol[3:] if len(symbol) == 6 else symbol,
        "faName": str(_get(sig, "fa_name", "") or ""),
        "stars": max(0, min(5, stars)),
        "scoreFa": f"{fa_num(score)} از {fa_num(max_score)}",
        "scorePct": max(0.0, min(1.0, (score or 0) / max_score)),
        "entry": fmt_price(entry, pip),
        "sl": fmt_price(sl, pip),
        "tp": fmt_price(tp, pip),
        "slDist": fa_pips(abs(entry - sl), pip, is_gold),
        "tpDist": fa_pips(abs(tp - entry), pip, is_gold),
        "rr": "ریسک به ریسک ۱:" + fa_ratio(float(_get(sig, "rr", 2.0) or 0)),
        "jalali": jalali_fa(now),
        "timeTeh": fa_num(hhmm_teh(now)) + " تهران",
        "session": str(_get(sig, "session_fa", "") or ""),
        "disclaimer": DISCLAIMER,
        "footerName": FOOTER_NAME,
        "footerTg": FOOTER_TG,
        "version": "v" + str(version),
    }


# ══════════════════════════════════════════════════════════════
#  رندر QPixmap (همان چیدمان renderShareCanvas در JS)
# ══════════════════════════════════════════════════════════════
def render_card_pixmap(spec: dict):
    from PySide6.QtCore import QPointF, Qt, QRectF
    from PySide6.QtGui import (QBrush, QColor, QFont, QFontDatabase, QLinearGradient,
                               QPainter, QPainterPath, QPen, QPixmap, QRadialGradient)

    W, H = int(spec.get("w") or CW), int(spec.get("h") or CH)
    pm = QPixmap(W, H)
    pm.fill(QColor("#101013"))
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.TextAntialiasing, True)

    buy = spec["dir"] == "BUY"
    ACC = QColor("#7BE0B0") if buy else QColor("#FF9A9A")
    ACC_BG = QColor(123, 224, 176, 30) if buy else QColor(255, 154, 154, 30)
    TEXT = QColor("#FFFFFF")
    DIM = QColor(255, 255, 255, 158)
    FAINT = QColor(255, 255, 255, 107)
    TILE = QColor("#26262B")
    TILE_B = QColor("#33333A")
    AMBER = QColor("#E8B84B")
    LINE = QColor(255, 255, 255, 36)

    # پس‌زمینهٔ گرادیان + هالهٔ جهت
    g = QLinearGradient(0, 0, W * 0.4, H)
    g.setColorAt(0, QColor("#1A1A1F")); g.setColorAt(0.55, QColor("#101013")); g.setColorAt(1, QColor("#0A0A0D"))
    p.fillRect(0, 0, W, H, QBrush(g))
    rg = QRadialGradient(W * 0.78, 60, W * 0.75)
    halo = QColor(123, 224, 176, 26) if buy else QColor(255, 154, 154, 26)
    rg.setColorAt(0, halo); rg.setColorAt(1, QColor(0, 0, 0, 0))
    p.fillRect(QRectF(0, 0, W, H * 0.5), QBrush(rg))

    def font(weight: int, size: int, family: str = "Vazirmatn") -> QFont:
        f = QFont(family, size)
        try:
            f.setWeight(QFont.Weight(weight))     # PySide6: enum، نه int خام
        except (ValueError, AttributeError):
            f.setWeight(QFont.Bold if weight >= 600 else QFont.Normal)
        return f

    P = 64
    right = W - P

    # ── سربرگ: لوگو + برند ──
    lx, ly, lr = right - 34, P + 34, 26
    pen = QPen(TEXT, 7); pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    p.drawLine(int(lx), int(ly - lr - 12), int(lx), int(ly - lr + 2))
    p.drawLine(int(lx), int(ly + lr - 2), int(lx), int(ly + lr + 12))
    p.drawLine(int(lx - lr - 12), int(ly), int(lx - lr + 2), int(ly))
    p.drawLine(int(lx + lr - 2), int(ly), int(lx + lr + 12), int(ly))
    p.setPen(QPen(TEXT, 6))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QPointF(lx, ly), lr, lr)
    # نیم‌دایرهٔ پرِ سمت راست (مثل لوگوی اپ) — Qt: زاویه ۱/۱۶ درجه، CCW مثبت
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(TEXT))
    p.drawPie(QRectF(lx - lr, ly - lr, lr * 2, lr * 2), 90 * 16, -180 * 16)
    p.setPen(QPen(TEXT, 7))
    p.setBrush(Qt.NoBrush)

    p.setPen(TEXT)
    p.setFont(font(700, 25))
    p.drawText(QRectF(0, P + 8, right - 92, 48), Qt.AlignRight | Qt.AlignVCenter, spec["brand"])
    p.setPen(FAINT)
    p.setFont(font(400, 15))
    p.drawText(QRectF(0, P + 52, right - 92, 30), Qt.AlignRight | Qt.AlignVCenter, spec["brandSub"])

    # ── قرص جهت ──
    y = P + 128
    p.setFont(font(700, 24))
    fm_w = p.fontMetrics().horizontalAdvance(spec["dirLabel"])
    pill_w = fm_w + 130
    pill = QRectF(right - pill_w, y, pill_w, 76)
    path = QPainterPath(); path.addRoundedRect(pill, 38, 38)
    p.fillPath(path, QBrush(ACC_BG))
    p.setPen(QPen(ACC, 2.5)); p.setBrush(Qt.NoBrush)
    p.drawPath(path)
    ax, ay = right - pill_w + 44, y + 38
    pen = QPen(ACC, 5); pen.setCapStyle(Qt.RoundCap); pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    if buy:
        p.drawLine(int(ax), int(ay + 14), int(ax), int(ay - 14))
        p.drawLine(int(ax - 10), int(ay - 4), int(ax), int(ay - 14)); p.drawLine(int(ax), int(ay - 14), int(ax + 10), int(ay - 4))
    else:
        p.drawLine(int(ax), int(ay - 14), int(ax), int(ay + 14))
        p.drawLine(int(ax - 10), int(ay + 4), int(ax), int(ay + 14)); p.drawLine(int(ax), int(ay + 14), int(ax + 10), int(ay + 4))
    p.setPen(ACC)
    p.setFont(font(700, 24))
    p.drawText(QRectF(right - pill_w, y, pill_w - 34, 76), Qt.AlignRight | Qt.AlignVCenter, spec["dirLabel"])

    # ── نماد + نام فارسی ──
    y += 116
    p.setPen(TEXT)
    p.setFont(font(800, 58))
    p.drawText(QRectF(0, y - 20, right, 110), Qt.AlignRight | Qt.AlignVCenter, spec["pair"])
    p.setPen(DIM)
    p.setFont(font(400, 17))
    p.drawText(QRectF(0, y + 84, right, 40), Qt.AlignRight | Qt.AlignVCenter, spec["faName"])

    # ── ستاره‌ها ──
    def star(cx, cy, r, filled):
        path = QPainterPath()
        import math
        for i in range(10):
            rad = r if i % 2 == 0 else r * 0.46
            a = -math.pi / 2 + i * math.pi / 5
            pt = QPointF(cx + math.cos(a) * rad, cy + math.sin(a) * rad)
            if i == 0:
                path.moveTo(pt)
            else:
                path.lineTo(pt)
        path.closeSubpath()
        if filled:
            p.fillPath(path, QBrush(AMBER))
        else:
            p.setPen(QPen(QColor(232, 184, 75, 115), 3))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
    for i in range(5):
        star(right - 26 - i * 52, y + 150, 21, i < spec["stars"])

    # ── امتیاز ──
    y += 200
    p.setPen(DIM)
    p.setFont(font(500, 18))
    p.drawText(QRectF(0, y - 26, right, 34), Qt.AlignRight | Qt.AlignVCenter,
               "امتیاز پشتوانه: " + spec["scoreFa"])
    bar_y, bar_h = y + 8, 16
    bp = QPainterPath(); bp.addRoundedRect(QRectF(P, bar_y, W - 2 * P, bar_h), 8, 8)
    p.fillPath(bp, QBrush(TILE))
    pct = float(spec.get("scorePct") or 0)
    if pct > 0.02:
        fw = (W - 2 * P) * pct
        fp = QPainterPath(); fp.addRoundedRect(QRectF(P + (W - 2 * P) - fw, bar_y, fw, bar_h), 8, 8)
        p.fillPath(fp, QBrush(ACC))

    # ── سه کاشی سطح ──
    y = bar_y + 62
    gap, th = 20, 178
    tw = (W - 2 * P - 2 * gap) / 3
    tiles = [
        ("هدف (TP)", spec["tp"], spec["tpDist"], QColor("#7BE0B0")),
        ("حد ضرر (SL)", spec["sl"], spec["slDist"], QColor("#FF9A9A")),
        ("ورود", spec["entry"], "قیمت فعلی", TEXT),
    ]
    for ti, (cap, val, sub, col) in enumerate(tiles):
        tx = right - (ti + 1) * tw - ti * gap
        tp = QPainterPath(); tp.addRoundedRect(QRectF(tx, y, tw, th), 26, 26)
        p.fillPath(tp, QBrush(TILE))
        p.setPen(QPen(TILE_B, 1.5)); p.setBrush(Qt.NoBrush)
        p.drawPath(tp)
        p.setPen(FAINT); p.setFont(font(500, 15))
        p.drawText(QRectF(tx, y + 16, tw, 30), Qt.AlignCenter, cap)
        p.setPen(col)
        p.setFont(font(700, 26, "Consolas"))
        p.drawText(QRectF(tx, y + 58, tw, 52), Qt.AlignCenter, val)
        p.setPen(DIM); p.setFont(font(400, 13))
        p.drawText(QRectF(tx, y + 122, tw, 30), Qt.AlignCenter, sub)

    # ── rr + سشن ──
    y += th + 42
    p.setPen(DIM); p.setFont(font(500, 19))
    rr_txt = spec["rr"] + (("  ·  سشن: " + spec["session"]) if spec.get("session") else "")
    p.drawText(QRectF(0, y - 26, right, 36), Qt.AlignRight | Qt.AlignVCenter, rr_txt)

    # ── تاریخ ──
    y += 52
    p.setPen(TEXT); p.setFont(font(700, 19))
    p.drawText(QRectF(0, y - 26, right, 36), Qt.AlignRight | Qt.AlignVCenter,
               spec["jalali"] + "  ·  ساعت " + spec["timeTeh"])

    # ── سلب مسئولیت ──
    y += 76
    p.setPen(QPen(LINE, 1.5))
    p.drawLine(P, int(y - 30), right, int(y - 30))
    p.setPen(FAINT); p.setFont(font(400, 16))
    p.drawText(QRectF(P, y - 22, W - 2 * P, 32), Qt.AlignRight | Qt.AlignVCenter, spec["disclaimer"])

    # ── فوتر ──
    fy = H - 74
    p.setPen(QPen(LINE, 1.5))
    p.drawLine(P, int(fy - 42), right, int(fy - 42))
    p.setPen(TEXT); p.setFont(font(700, 17))
    p.drawText(QRectF(0, fy - 22, right, 32), Qt.AlignRight | Qt.AlignVCenter, spec["footerName"])
    p.setPen(FAINT); p.setFont(font(400, 14))
    p.drawText(QRectF(0, fy + 12, right, 30), Qt.AlignRight | Qt.AlignVCenter,
               "خرید لایسنس و پشتیبانی — تلگرام")
    p.setPen(QColor("#7BE0B0")); p.setFont(font(700, 18))
    p.drawText(QRectF(P, fy - 22, W - 2 * P, 32), Qt.AlignLeft | Qt.AlignVCenter, spec["footerTg"])
    p.setPen(FAINT); p.setFont(font(400, 14))
    p.drawText(QRectF(P, fy + 12, W - 2 * P, 30), Qt.AlignLeft | Qt.AlignVCenter,
               spec["brand"] + " " + spec["version"])

    p.end()
    return pm
