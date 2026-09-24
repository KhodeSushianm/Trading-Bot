# -*- coding: utf-8 -*-
"""پلاگین‌های داور و سشن (فاز ۲) + قواعد داور (فاز ۴).

فاز ۴: هفت وتو و هشت شاهدِ داور به rule-pluginهای مستقل تبدیل شدند
(`odin.judge.veto@1` / `odin.judge.evidence@1`) و `compute_levels` به
پلاگین جداگانهٔ judge-risk (`odin.judge.risk@1`) رفت — دقیقاً مطابق جدول
قراردادهای سند معماری. judge-core حالا فقط `odin.judge.engine@1` را فراهم
می‌کند و در صورت حضور registry، قواعد را از آنجا مصرف می‌کند.

قاعدهٔ adapter: فقط delegation؛ منطق در src/judge/* دست‌نخورده است (بدنهٔ
هفت تابع وتو در فاز ۴، جابه‌جاییِ بایت‌به‌بایتِ همان بلوک‌های collect_vetoes
قبلی است). ترتیب ارزیابی قواعد با priority مانیفست‌ها پین شده و طلایی‌های
tests/test_plugins.py + باتری tests/golden/judge_rules_golden.json برابری
بایت‌به‌بایت مسیر registry با مسیر مستقیم را اثبات می‌کنند.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..core.manifest import PluginManifest


class JudgePlugin:
    """judge_config + judge_all — قرارداد odin.judge.engine@1.

    اگر context شامل registry باشد (build_default_registry از فاز ۴ آن را
    می‌گذارد)، judge_all قواعد وتو/شاهد/ریسک را از registry می‌گیرد و به
    scoring.judge_all تزریق می‌کند؛ در غیر این صورت delegation ساده به
    توابع پیش‌فرض — دقیقاً رفتار فاز ۲/۳a (fallback صادقانه).
    """

    def __init__(self, context: Optional[dict] = None):
        self._context: dict = dict(context or {})
        self._registry = self._context.get("registry")
        self._rules_cache: Optional[tuple] = None

    def judge_config(self, cfg: dict) -> dict:
        from ..judge.scoring import judge_config
        return judge_config(cfg)

    def judge_all(self, analyses: List[Any], datasets: Dict[str, Any],
                  ctx: Any) -> List[Any]:
        from ..judge.scoring import judge_all
        veto_rules, evidence_rules, risk_fn = self._rules()
        if veto_rules is None and evidence_rules is None and risk_fn is None:
            return judge_all(analyses, datasets, ctx)
        return judge_all(analyses, datasets, ctx, veto_rules=veto_rules,
                         evidence_rules=evidence_rules, risk_fn=risk_fn)

    def _rules(self) -> tuple:
        """(veto_rules, evidence_rules, risk_fn) از registry — یا سه‌تایی None.

        adapterهای قاعده stateless‌اند (delegation خالص، بدون هوک lifecycle)،
        پس اگر نمونهٔ lifecycle هنوز ساخته نشده باشد، مستقیم با factory ساخته
        می‌شوند. فیلتر providers(only_active) همان enable/disable را محترم
        می‌شمارد؛ فهرست خالی → None → fallback به قواعد پیش‌فرض scoring
        (رفتار امروز). نتیجه cache می‌شود — registry در عمر یک _Caps ثابت است.
        """
        if self._registry is None:
            return (None, None, None)
        if self._rules_cache is None:
            reg = self._registry

            def inst(rec):
                return (rec.instance if rec.instance is not None
                        else rec.factory(self._context))

            vetoes = [inst(r).rule for r in reg.providers("odin.judge.veto@1")]
            evidences = [inst(r).rule
                         for r in reg.providers("odin.judge.evidence@1")]
            risk_rec = reg.get("odin.judge.risk@1")
            risk_fn = (inst(risk_rec).compute_levels
                       if risk_rec is not None else None)
            # اصلاحیهٔ فاز ۷: وقتی registry هست، فهرست‌ها *همان‌طور که
            # هستند* رد می‌شوند — حتی خالی. پیش‌تر `vetoes or None` فهرست
            # خالی (همهٔ وتوها خاموش) را به None تبدیل می‌کرد و قواعد
            # پیش‌فرضِ scoring بی‌صدا برمی‌گشتند — خلافِ تنظیمات کاربر.
            self._rules_cache = (vetoes, evidences, risk_fn)
        return self._rules_cache


class RiskPlugin:
    """ریاضی SL/TP — قرارداد odin.judge.risk@1 (بدنه در src/judge/scoring)."""

    def compute_levels(self, direction: str, entry: float, atr: float,
                       support: Optional[float], resistance: Optional[float],
                       rcfg: dict) -> tuple:
        from ..judge.scoring import compute_levels
        return compute_levels(direction, entry, atr, support, resistance, rcfg)


class SessionPlugin:
    def market_status(self, now: Any) -> Any:
        from ..judge.session import market_status
        return market_status(now)


class VetoRuleAdapter:
    """adapter نازکِ یک قاعدهٔ وتو — delegation خالص به تابعِ scoring.

    به‌جای هفت کلاسِ هم‌شکل، هر قاعده یک نمونه از این کلاس است با veto_id و
    نام تابع (بدنهٔ منطق در src/judge/scoring دست‌نخورده می‌ماند).
    shape: odin.judge.veto@1 — rule(a, sym_cfg, md, ctx) → Veto|None.
    """

    def __init__(self, veto_id: str, fn_name: str):
        self.veto_id = veto_id
        self._fn_name = fn_name

    def rule(self, a: Any, sym_cfg: dict, md: Optional[Any],
             ctx: Any) -> Optional[Any]:
        from ..judge import scoring
        return getattr(scoring, self._fn_name)(a, sym_cfg, md, ctx)


class EvidenceRuleAdapter:
    """adapter نازکِ یک شاهد امتیاز — delegation خالص به توابع ev_*.

    shape: odin.judge.evidence@1 — rule(a, ctx, direction) → Evidence.
    حالت ctx_only برای ev_session است که امروز فقط (ctx) می‌گیرد؛ adapter
    همان shape یکدست را با نادیده‌گرفتن ورودی‌های اضافه فراهم می‌کند
    (وعدهٔ صریح §۲.۲ سند معماری — بدون تغییر رفتار).
    """

    def __init__(self, evidence_id: str, fn_name: str, ctx_only: bool = False):
        self.evidence_id = evidence_id
        self._fn_name = fn_name
        self._ctx_only = ctx_only

    def rule(self, a: Any, ctx: Any, direction: str) -> Any:
        from ..judge import scoring
        fn = getattr(scoring, self._fn_name)
        return fn(ctx) if self._ctx_only else fn(a, ctx, direction)


# (plugin-id, veto_id, نام تابع scoring, کلیدِ veto در judge) — ترتیب =
# ترتیب ارزیابیِ امروزِ collect_vetoes؛ priority مانیفست‌ها دقیقاً همان
# ترتیب را پین می‌کند. ستون چهارم (فاز ۷): کلیدِ *موجودِ* خاموش/روشنِ هر
# دروازه — به‌صورت dot-path به مانیفست bind می‌شود تا «غیرفعال» هم زیر
# مانیفست بیاید؛ DATA کلید ندارد (وتوی بدون استثنا) → config=None.
VETO_RULES: Tuple[Tuple[str, str, str, Optional[str]], ...] = (
    ("veto-data", "DATA", "veto_data", None),
    ("veto-weekend", "WEEKEND", "veto_weekend", "weekend"),
    ("veto-tf-conflict", "TF_CONFLICT", "veto_tf_conflict", "timeframe_conflict"),
    ("veto-range", "RANGE", "veto_range", "range_market"),
    ("veto-event", "EVENT", "veto_event", "high_impact_event"),
    ("veto-vol-spike", "VOL_SPIKE", "veto_vol_spike", "volatility_spike"),
    ("veto-breaking-news", "BREAKING_NEWS", "veto_breaking_news", "breaking_news"),
)

# (plugin-id, evidence_id, نام تابع, ctx_only) — ترتیب = جدول امتیازِ امروز
EVIDENCE_RULES: Tuple[Tuple[str, str, str, bool], ...] = (
    ("ev-trend", "TREND", "ev_trend", False),
    ("ev-level", "LEVEL", "ev_level", False),
    ("ev-fundamental", "FUNDAMENTAL", "ev_fundamental", False),
    ("ev-momentum", "MOMENTUM", "ev_momentum", False),
    ("ev-strength", "STRENGTH", "ev_strength", False),
    ("ev-news", "NEWS", "ev_news", False),
    ("ev-tv", "TV", "ev_tradingview", False),
    ("ev-session", "SESSION", "ev_session", True),
)


def plugins() -> List[Tuple[PluginManifest, Any]]:
    out: List[Tuple[PluginManifest, Any]] = [
        (PluginManifest(
            id="session", version="1.0.0",
            provides=["odin.session@1"],
            platforms=["desktop", "android"],
            stage="judge", priority=10, optional=True),
         lambda _ctx: SessionPlugin()),
        (PluginManifest(
            id="judge-core", version="1.0.0",
            provides=["odin.judge.engine@1"],
            # فاز ۷ — بازبینی انجام شد: bind به judge.enabled با حفظ مسیرِ
            # بدون guardِ judge_config: engine در آن نقطه (jcfg) وقتی پلاگین
            # خاموش است به cfg["judge"] برمی‌گردد که در load_config با همان
            # DEFAULTS ادغام شده (src/config.py) — بایت‌به‌بایت یکسان.
            # در JS هم cycleCtx.jcfg مستقیماً cfg.judge است. پس «خاموش =
            # پلاگین غایب» هیچ مسیر صادقی را نمی‌شکند.
            config={"section": "judge", "enabled_key": "enabled", "default": True},
            platforms=["desktop", "android"],
            stage="judge", priority=50, optional=True),
         lambda ctx: JudgePlugin(ctx if isinstance(ctx, dict) else None)),
        (PluginManifest(
            id="judge-risk", version="1.0.0",
            provides=["odin.judge.risk@1"],
            # فاز ۷: risk فقط درون judge_symbol مصرف می‌شود (مسیر judge) —
            # پس bind به judge.enabled امن است؛ مصرف‌کنندهٔ مستقیم
            # (panel/main/selftest) تابع scoring را صدا می‌زند، نه پلاگین را.
            config={"section": "judge", "enabled_key": "enabled", "default": True},
            platforms=["desktop", "android"],
            stage="judge", priority=60, optional=True),
         lambda _ctx: RiskPlugin()),
    ]

    # ── ۷ قاعدهٔ وتو — priority ۱۰..۷۰ = ترتیب ارزیابیِ امروز ──
    # فاز ۷: شش دروازهٔ کلیددار به judge.veto.* bind شدند (dot-path در
    # config-bridge). guardهای درونِ بدنه (vc.get) عمداً باقی‌اند: مصرف‌کنندهٔ
    # مسیر مستقیم (selftest/gen_fixtures/test_judge) بدون registry همان
    # کلیدها را می‌خواند — دو مسیر یک رفتار دارند (تست طلاییِ veto-off در
    # tests/test_plugins.py برابری‌شان را پین می‌کند).
    for i, (pid, vid, fname, cfg_key) in enumerate(VETO_RULES):
        out.append((
            PluginManifest(
                id=pid, version="1.0.0",
                provides=["odin.judge.veto@1"],
                config=({"section": "judge", "enabled_key": f"veto.{cfg_key}",
                         "default": True} if cfg_key else None),
                platforms=["desktop", "android"],
                stage="judge", priority=10 * (i + 1), optional=True),
            lambda _ctx, vid=vid, fname=fname: VetoRuleAdapter(vid, fname)))

    # ── ۸ شاهد امتیاز — priority ۱۰..۸۰ = ترتیب جدول امتیازِ امروز ──
    for i, (pid, eid, fname, ctx_only) in enumerate(EVIDENCE_RULES):
        out.append((
            PluginManifest(
                id=pid, version="1.0.0",
                provides=["odin.judge.evidence@1"],
                config=None,
                platforms=["desktop", "android"],
                stage="judge", priority=10 * (i + 1), optional=True),
            lambda _ctx, eid=eid, fname=fname, co=ctx_only:
                EvidenceRuleAdapter(eid, fname, co)))

    return out
