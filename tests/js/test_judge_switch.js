#!/usr/bin/env node
/* میخ‌های رفتاری قواعد داور JS — فاز ۶b (۷ وتو + ۸ شاهد + risk → rule-plugin).
 *
 * اجرا:  node tests/js/test_judge_switch.js   (آفلاین، قطعی، بدون شبکه)
 *
 * انضباط «اول میخ، بعد چکش» (آینهٔ tests/test_judge_rules.py فاز ۴):
 *   • این تست‌ها روی judge.js *فعلی* (فقط API عمومیِ امروز) نوشته و سبز
 *     شده‌اند (کامیت میخ‌ها).
 *   • سپس سوییچ ۶b انجام می‌شود (استخراج بایت‌به‌بایتِ ۷ تابع وتو +
 *     export شاهدها + پارامترهای تزریق اختیاری + ۱۵ rule-plugin در
 *     plugins.js) و **همین تست‌ها بدون هیچ تغییری** باید سبز بمانند.
 *   • بخش‌های مشروط (registry/adapters): قبل از سوییچ skip، بعد از سوییچ
 *     فعال — همان الگوی فاز ۳/۶.
 *
 * طلایی: tests/js/golden/judge_rules_js_golden.json — ۵۸ سناریوی داوری +
 * ۶ حالت ریاضی ریسک. نتایج با باتری پایتون (judge_rules_golden.json)
 * یکسان است (parity دو موتور با run_parity اثبات شده) — EURUSD BUY 11/11،
 * SELL 11/11، low 5/11، capped 11/10/8، sid/ریاضی ریسک بایت‌به‌بایت.
 */
'use strict';

const fs = require('fs');
const path = require('path');

const gen = require('./golden/gen_judge_rules_golden.js');

let COUNT = 0;
function A(cond, msg) {
  if (!cond) throw new Error(msg);
  COUNT++;
}

const O = gen.createVm();
const BAT = gen.buildBattery(O);

function firstDiffPath(a, b, p) {
  p = p || '';
  if (a === b) return null;
  if (a === null || b === null || typeof a !== 'object' || typeof b !== 'object') return p || '(root)';
  if (Array.isArray(a) !== Array.isArray(b)) return p || '(root)';
  const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
  for (const k of Array.from(keys).sort()) {
    const d = firstDiffPath(a[k], b[k], p ? p + '.' + k : k);
    if (d) return d;
  }
  return null;
}

function stable(v) { return gen.stableStringify(v); }

// ══════════════════════════════════════════════════════════════
function testGoldenBattery() {
  A(fs.existsSync(gen.GOLDEN_PATH),
    'فایل طلایی وجود ندارد — اول node tests/js/golden/gen_judge_rules_golden.js');
  const golden = JSON.parse(fs.readFileSync(gen.GOLDEN_PATH, 'utf8'));
  if (stable(BAT) !== stable(golden)) {
    const at = firstDiffPath(BAT, golden);
    throw new Error('باتری با طلایی فرق دارد — اولین اختلاف در: ' + at);
  }
  A(true, 'باتری طلاییِ کامل (وتو/شاهد/داوری/ریسک — ۵۸ سناریو) بایت‌به‌بایت مطابقت کرد');
}

// ── پین‌های خوانای انسانی ─────────────────────────────────────
const VETO_TITLES = {
  DATA: '⚠️ دادهٔ ناکافی',
  WEEKEND: '🔒 بازار بسته است',
  TF_CONFLICT: '🔀 تضاد جهت بین تایم‌فریم‌ها',
  RANGE: '😴 بازار بی‌روند (رنج)',
  EVENT: '📅 رویداد پراثر تقویم',
  VOL_SPIKE: '📈 جهش غیرعادی نوسان',
  BREAKING_NEWS: '🚨 خبر فوری'
};

function testVetoPins() {
  const order = ['DATA', 'WEEKEND', 'TF_CONFLICT', 'RANGE', 'EVENT', 'VOL_SPIKE', 'BREAKING_NEWS'];
  order.forEach((key) => {
    const j = BAT.veto_single[key];
    A(j.vetoes.length === 1 && j.vetoes[0].key === key, key + ' باید تنها شلیک شود');
    A(j.vetoes[0].title_fa === VETO_TITLES[key], key + ': عنوان فارسی دقیق');
    A(j.reject_reason === 'VETO' && j.signal === null && j.status_fa === '🚫 وتو شد',
      key + ': reject=VETO + status_fa');
  });
  A(BAT.veto_multi.all_except_data.vetoes.map((v) => v.key).join(',')
    === 'WEEKEND,TF_CONFLICT,RANGE,EVENT,VOL_SPIKE,BREAKING_NEWS',
    'ترتیب چندوتو (همه جز DATA) = ترتیب ارزیابی امروز');
  A(BAT.veto_multi.with_data.vetoes.map((v) => v.key).join(',')
    === 'DATA,WEEKEND,EVENT,VOL_SPIKE,BREAKING_NEWS',
    'ترتیب با DATA (TF/RANGE به گارد verdict می‌خورند)');
  const t = BAT.veto_toggles;
  A(t.weekend_off_saturday.vetoes.length === 0 && t.weekend_off_saturday.signal !== null
    && t.weekend_off_saturday.score === 10,
    'veto.weekend=false → شنبه بدون وتو سیگنال می‌دهد (۱۰/۱۱ — فقط سشن صفر)');
  A(t.weekend_off_saturday.evidences[7].points === 0
    && t.weekend_off_saturday.evidences[7].detail_fa === 'شنبه — بازار فارکس بسته است 🔒',
    'شاهد سشنِ بازار بسته: ۰ با دلیل صادقانه');
  // S3 (بازضبطِ مستند): پینِ toggle سرِ جایش است (وتو غایب) ولی ADX=14
  // زیر آستانهٔ trend_pullback است → دروازهٔ توافق صادقانه رد می‌کند
  // (آینهٔ اصلاحِ مستند در test_judge_rules.py)
  A(t.range_off_low_adx.vetoes.length === 0
    && t.range_off_low_adx.reject_reason === 'NO_STRATEGY'
    && t.range_off_low_adx.evidences[0].points === 1,
    'veto.range_market=false → ADX پایین وتو ندارد؛ S3: دروازهٔ توافق رد می‌کند');
  A(BAT.veto_clean.length === 0, 'ستاپ سالم → بدون وتو');
}

// (نام سناریو، کلید شاهد، امتیاز، max، ok، unavailable)
const EV_PINS = [
  ['trend_medium', 'trend', 1, 2, true, false],
  ['level_buy_near', 'level', 1, 2, true, false],
  ['level_buy_far', 'level', 0, 2, false, false],
  ['level_buy_unavailable', 'level', 0, 2, false, true],
  ['level_sell_close', 'level', 2, 2, true, false],
  ['fund_high_soon', 'fundamental', 0, 2, false, false],
  ['fund_med_soon', 'fundamental', 1, 2, true, false],
  ['fund_cal_failed', 'fundamental', 0, 2, false, true],
  ['fund_cal_off', 'fundamental', 0, 2, false, true],
  ['mom_buy_oversold', 'momentum', 0, 1, false, false],
  ['mom_buy_high', 'momentum', 0, 1, false, false],
  ['mom_buy_not_rising', 'momentum', 0, 1, false, false],
  ['mom_sell_confirm', 'momentum', 1, 1, true, false],
  ['mom_sell_overbought', 'momentum', 0, 1, false, false],
  ['mom_sell_low', 'momentum', 0, 1, false, false],
  ['str_buy_contra', 'strength', 0, 1, false, false],
  ['str_sell_aligned', 'strength', 1, 1, true, false],
  ['str_empty', 'strength', 0, 1, false, true],
  ['str_missing', 'strength', 0, 1, false, true],
  ['news_supports_sell', 'news', 1, 1, true, false],
  ['news_contra', 'news', 0, 1, false, false],
  ['news_neutral', 'news', 0, 1, false, false],
  ['news_unavailable', 'news', 0, 1, false, true],
  ['tv_match_sell', 'tv', 1, 1, true, false],
  ['tv_neutral', 'tv', 0, 1, false, false],
  ['tv_opposite', 'tv', 0, 1, false, false],
  ['tv_unavailable', 'tv', 0, 1, false, true],
  ['sess_overlap', 'session', 1, 1, true, false],
  ['sess_liquid', 'session', 1, 1, true, false],
  ['sess_thin', 'session', 0, 1, false, false],
  ['sess_closed', 'session', 0, 1, false, false]
];

function testEvidencePins() {
  const ev = BAT.evidence_judgments;
  EV_PINS.forEach(([name, key, pts, max, okc, un]) => {
    const e = ev[name].evidences.filter((x) => x.key === key)[0];
    A(!!e, name + ': شاهد «' + key + '» باید حاضر باشد');
    A(e && e.points === pts && e.max_points === max && e.ok === okc && e.unavailable === un,
      name + ': امتیاز/حالت شاهد «' + key + '» — ' + (e ? e.points + '/' + e.max_points + ' ok=' + e.ok + ' un=' + e.unavailable : '?')
      + ' (انتظار ' + pts + '/' + max + ' ok=' + okc + ' un=' + un + ')');
  });
  A(ev.news_contra.evidences.filter((x) => x.key === 'news')[0].detail_fa.indexOf('⚠️') === 0,
    'خبر خلاف جهت با ⚠️ شروع می‌شود (سرچشمهٔ warnings)');
  A(ev.tv_opposite.evidences.filter((x) => x.key === 'tv')[0].detail_fa.indexOf('⚠️') === 0,
    'TV خلاف جهت با ⚠️ شروع می‌شود');
  A(ev.fund_cal_off.evidences.filter((x) => x.key === 'fundamental')[0].detail_fa
    === 'موتور فاندامنتال خاموش است — نمی‌توانیم تاییدش کنیم، پس امتیازی نمی‌گیرد',
    'متنِ calSnap=null دقیقاً همان متن پایتون است');
  A(ev.sess_closed.evidences[7].detail_fa === 'شنبه — بازار فارکس بسته است 🔒',
    'متن سشن بسته');
  A(ev.level_sell_close.evidences.filter((x) => x.key === 'level')[0].label_fa
    === 'واکنش به سطح کلیدی (مقاومت)', 'برچسب سطحِ SELL = مقاومت');
}

function testJudgePathPins() {
  const b = BAT.judge_full.buy;
  A(b.score === 11 && b.max_score === 11, 'BUY طلایی ۱۱/۱۱');
  A(b.evidences.map((e) => e.key).join(',')
    === 'trend,level,fundamental,momentum,strength,news,tv,session',
    'ترتیب ۸ شاهد = فهرست ثابت امروز');
  A(b.evidences.every((e) => e.ok), 'در BUY طلایی همهٔ شاهدها امتیاز گرفتند');
  A(b.signal.stars === 5 && b.signal.rr === 2.0 && b.signal.sl_capped === false,
    'ستاره/RR/بدون سقف');
  A(b.signal.sl < b.signal.entry && b.signal.entry < b.signal.tp, 'BUY: SL < ورود < TP');
  A(b.signal.sid === 'EURUSD-BUY-20260923140000-1.149', 'sid قطعی (همان قالب پایتون)');
  A(b.signal.journal.kind === 'signal' && b.signal.journal.sent === true
    && b.signal.journal.score === 11, 'رکورد ژورنال سیگنال');
  const s = BAT.judge_full.sell;
  A(s.direction === 'SELL' && s.score === 11 && s.signal.tp < s.signal.entry && s.signal.entry < s.signal.sl,
    'SELL طلایی ۱۱/۱۱: TP < ورود < SL');

  const ls = BAT.judge_low_score.low_score;
  A(ls.reject_reason === 'LOW_SCORE' && ls.score === 5 && ls.max_score === 11,
    'LOW_SCORE: ۵/۱۱');
  A(ls.reject_detail === 'امتیاز ۵ از ۱۱ — زیر آستانهٔ ۷ است، پس سیگنال صادر نمی‌شود',
    'متن LOW_SCORE (ارقام فارسی — همان متن پایتون)');
  A(ls.warnings.length === 2, 'دو هشدار ⚠️ (خبر + TV) به warnings منتقل شد');

  const ns = BAT.judge_no_setup;
  A(ns.trend_none.reject_detail === 'جهت روند نامشخص است', 'NO_SETUP/trend-none');
  A(ns.h1_disagree.reject_detail === 'تایم‌فریم ۱ ساعته با ۴ ساعته هم‌جهت نیست', 'NO_SETUP/h1');
  A(ns.range_no_veto.reject_detail === 'بازار بی‌روند است (ADX=14 زیر 20)', 'NO-setup/range');
  A(ns.bullish_rsi_high.reject_detail.indexOf('روند صعودی است ولی RSI=55') === 0, 'NO_SETUP/bullish-rsi');
  A(ns.bearish_rsi_low.reject_detail.indexOf('روند نزولی است ولی RSI=40') === 0, 'NO_SETUP/bearish-rsi');

  const cp = BAT.judge_capped;
  A(cp.map((j) => j.symbol).join(',') === 'EURUSD,GBPUSD,USDJPY', 'capped: نمادها به ترتیب ورودی');
  A(cp[0].signal !== null && cp[1].reject_reason === 'CAPPED' && cp[2].reject_reason === 'CAPPED',
    'بهترین می‌ماند، بقیه CAPPED');
  // S3 (بازضبطِ مستند): a3 برای ماندن در intentِ «سه آماده» rsi=38 گرفت
  // (منطقهٔ tp) → momentum +1 → ۸→۹ (همان پایتون)
  A(cp[1].score === 10 && cp[2].score === 9, 'امتیازهای capped (۱۰ و ۹ — همان پایتون)');
  A(cp[1].reject_detail === 'امتیاز ۱۰ از ۱۱ کافی بود، ولی سقف ۱ سیگنال در هر چرخه پر شده — بهترین‌ها اولویت دارند',
    'متن CAPPED (همان متن پایتون)');

  const mx = BAT.judge_all_mixed;
  A(mx.map((j) => j.reject_reason || 'SIGNAL').join(',') === 'SIGNAL,VETO,NO_SETUP,LOW_SCORE',
    'judgeAll: ۴ سرنوشت متفاوت');
  A(mx[0].score === 10 && mx[0].evidences.filter((e) => e.key === 'news')[0].unavailable,
    'بدون موتور خبر: ۱۰/۱۱ با شاهد صادقانهٔ unavailable');

  const rm = BAT.risk_math;
  const rc = O.CONFIG.judge.risk;
  const atr = 0.0010;
  const buf = (+rc.level_buffer_atr) * atr;
  A(Math.abs(rm.buy_level.sl - (1.1486 - buf)) < 1e-12, 'BUY سطحی: SL = حمایت − بافر');
  A(Math.abs(rm.buy_level.tp - (1.1490 + rm.buy_level.risk * (+rc.reward_risk))) < 1e-12,
    'TP = ورود + risk×RR');
  A(rm.sell_level.sl > 1.1490 && rm.sell_level.tp < 1.1490, 'SELL: SL بالا، TP پایین');
  A(rm.buy_far_capped.capped === true
    && Math.abs((1.1490 - rm.buy_far_capped.sl) - (+rc.max_sl_atr) * atr) < 1e-12,
    'سطح دور → سقف max_sl_atr×ATR');
  A(rm.buy_tight_floor.capped === false
    && Math.abs((1.1490 - rm.buy_tight_floor.sl) - (+rc.min_sl_atr) * atr) < 1e-12,
    'سطح خیلی نزدیک → کف min_sl_atr×ATR');
  A(Math.abs((1.1490 - rm.buy_no_level.sl) - (+rc.sl_atr_multiplier) * atr) < 1e-12,
    'بدون سطح → SL بر پایهٔ ATR');
  A(rm.atr_zero_guard.risk > 0 && rm.atr_zero_guard.sl !== 1.1490,
    'ATR=0 → گارد: ریسک صفر نمی‌شود');
}

// ══════════════════════════════════════════════════════════════
//  بخش مشروط — بعد از سوییچ ۶b فعال می‌شود (بدون تغییر این فایل)
// ══════════════════════════════════════════════════════════════
function testRegistryRulesWhenPresent() {
  if (typeof O.buildDefaultRegistry !== 'function' || !O.VETO_RULES) {
    A(true, 'rule-pluginهای داور JS هنوز نیامده‌اند (قبل از سوییچ ۶b) — بخش مشروط skip شد');
    return;
  }
  const cfg = JSON.parse(JSON.stringify(O.CONFIG));
  const built = O.buildDefaultRegistry(cfg, 'android');
  const reg = built.registry || built[0];
  const info = built.info || built[1];

  // ── ترتیب/شناسه‌ها — دقیقاً جدول قراردادهای سند (همان idهای پایتون) ──
  const vetoIds = reg.providers('odin.judge.veto@1').map((r) => r.id);
  A(vetoIds.join(',') === 'veto-data,veto-weekend,veto-tf-conflict,veto-range,veto-event,veto-vol-spike,veto-breaking-news',
    'providers(veto@1): ۷ قاعده با ترتیب priority = ترتیب ارزیابی امروز: ' + vetoIds);
  const evIds = reg.providers('odin.judge.evidence@1').map((r) => r.id);
  A(evIds.join(',') === 'ev-trend,ev-level,ev-fundamental,ev-momentum,ev-strength,ev-news,ev-tv,ev-session',
    'providers(evidence@1): ۸ شاهد با ترتیب جدول امتیاز: ' + evIds);

  // ── bindingهای نقطه‌ای (آینهٔ فاز ۷ پایتون) ──
  const cfgOff = JSON.parse(JSON.stringify(O.CONFIG));
  cfgOff.judge.veto.weekend = false;
  const b2 = O.buildDefaultRegistry(cfgOff, 'android');
  const reg2 = b2.registry || b2[0];
  A(reg2.byId('veto-weekend').enabled === false && reg2.byId('veto-data').enabled === true,
    'judge.veto.weekend=false → فقط veto-weekend غیرفعال (veto-data کلید ندارد)');
  A(reg2.providers('odin.judge.veto@1').length === 6, 'شش قاعدهٔ فعال باقی می‌ماند');

  // ── adapter == فراخوانی مستقیم (هر ۱۵ قاعده، دو ctx/دو جهت) ──
  const lm = O.core.createLifecycle({ context: info.context });
  const instOf = (id) => {
    const rec = reg.byId(id);
    if (rec.instance == null) lm.initialize(rec);
    return rec.instance;
  };
  const a = gen.makeAnalysis();
  const md = gen.makeMd(O, 'EURUSD');
  const ctxWed = gen.makeCtx(O);
  const ctxSat = gen.makeCtx(O, { nowMs: gen.FIXED_SAT, calSnap: gen.nearCal(gen.FIXED_SAT), newsSnap: gen.breakingNews() });
  const directVetoFn = {
    'veto-data': O.vetoData, 'veto-weekend': O.vetoWeekend, 'veto-tf-conflict': O.vetoTfConflict,
    'veto-range': O.vetoRange, 'veto-event': O.vetoEvent, 'veto-vol-spike': O.vetoVolSpike,
    'veto-breaking-news': O.vetoBreakingNews
  };
  Object.keys(directVetoFn).forEach((pid) => {
    const inst = instOf(pid);
    A(typeof inst.vetoId === 'string' && inst.vetoId.length > 0, pid + ': vetoId حاضر است');
    [ctxWed, ctxSat].forEach((c, i) => {
      const direct = directVetoFn[pid](a, {}, md, c);
      const got = inst.rule(a, {}, md, c);
      A(stable(got) === stable(direct), pid + ': adapter == فراخوانی مستقیم (ctx#' + i + ')');
    });
  });
  const directEv = {
    'ev-trend': (x, c, d) => O.evTrend(x, c), 'ev-level': (x, c, d) => O.evLevel(x, c, d),
    'ev-fundamental': (x, c, d) => O.evFundamental(x, c), 'ev-momentum': (x, c, d) => O.evMomentum(x, c, d),
    'ev-strength': (x, c, d) => O.evStrength(x, c, d), 'ev-news': (x, c, d) => O.evNews(x, c, d),
    'ev-tv': (x, c, d) => O.evTradingView(x, c, d), 'ev-session': (x, c, d) => O.evSession(c)
  };
  Object.keys(directEv).forEach((pid) => {
    const inst = instOf(pid);
    A(typeof inst.evidenceId === 'string' && inst.evidenceId.length > 0, pid + ': evidenceId حاضر است');
    ['BUY', 'SELL'].forEach((d) => {
      A(stable(inst.rule(a, ctxWed, d)) === stable(directEv[pid](a, ctxWed, d)),
        pid + ': adapter == مستقیم (' + d + ')');
    });
  });

  // ── باتری کامل از مسیر registry == طلاییِ مسیر مستقیم (بایت‌به‌بایت) ──
  const JudgeCtor = instOf('judge-core').constructor;
  const jp = new JudgeCtor(info.context);
  const pluginBat = gen.buildBattery(O, {
    judgeSymbolFn: (x, symCfg, m, c) => jp.judgeAll([x], { [x.symbol]: m }, c)[0],
    judgeAllFn: (list, datasets, c) => jp.judgeAll(list, datasets, c)
  });
  if (stable(pluginBat) !== stable(BAT)) {
    throw new Error('باتریِ مسیر rule-plugin با مسیر مستقیم/طلایی فرق دارد — '
      + firstDiffPath(pluginBat, BAT));
  }
  A(true, 'باتری کامل ۶۶ سناریویی از مسیر registry == مسیر مستقیم (بایت‌به‌بایت)');

  // ── veto-off: مسیر پلاگین (binding) == مسیر مستقیم (guard بدنه) ──
  const b3 = O.buildDefaultRegistry(cfgOff, 'android');
  const info3 = b3.info || b3[1];
  const jp3 = new JudgeCtor(info3.context);
  const ctxSatOff = gen.makeCtx(O, {
    nowMs: gen.FIXED_SAT,
    jcfg: { veto: Object.assign(JSON.parse(JSON.stringify(O.CONFIG.judge.veto)), { weekend: false }) }
  });
  const viaPlugin = jp3.judgeAll([a], { EURUSD: md }, ctxSatOff)[0];
  // S3: مسیر مستقیم هم strategyRules می‌گیرد — registry از S3 استراتژی‌ها
  // را هم تزریق می‌کند؛ برابری دو مسیر فقط با تزریقِ متناظر معنا دارد
  const viaDirect = O.judgeAll([a], { EURUSD: md }, ctxSatOff,
    undefined, undefined, undefined, gen.defaultStrategyRules(O))[0];
  A(stable(gen.judgmentDump(O, viaPlugin)) === stable(gen.judgmentDump(O, viaDirect)),
    'veto.weekend=false: مسیر پلاگین == مسیر مستقیم (شنبه سیگنال می‌دهد)');
  A(viaPlugin.signal !== null && viaPlugin.vetoes.length === 0,
    'binding خاموش → وتو غایب و سیگنال صادر (بدون زنده‌شدنِ بی‌صدا)');

  // ── همهٔ کلیدهای وتو خاموش → فقط veto-data (اصلاحیهٔ _rules آینهٔ پایتون) ──
  const cfgAll = JSON.parse(JSON.stringify(O.CONFIG));
  Object.keys(cfgAll.judge.veto).forEach((k) => { cfgAll.judge.veto[k] = false; });
  const b4 = O.buildDefaultRegistry(cfgAll, 'android');
  const reg4 = b4.registry || b4[0];
  A(reg4.providers('odin.judge.veto@1').map((r) => r.id).join(',') === 'veto-data',
    'همه خاموش → فقط veto-data فعال می‌ماند');
  const jp4 = new JudgeCtor(b4.info.context);
  const ctxAll = gen.makeCtx(O, {
    nowMs: gen.FIXED_SAT,
    jcfg: { veto: Object.assign(JSON.parse(JSON.stringify(O.CONFIG.judge.veto)),
      { weekend: false, high_impact_event: false, timeframe_conflict: false, range_market: false, volatility_spike: false, breaking_news: false }) }
  });
  const allPlugin = jp4.judgeAll([a], { EURUSD: md }, ctxAll)[0];
  const allDirect = O.judgeAll([a], { EURUSD: md }, ctxAll,
    undefined, undefined, undefined, gen.defaultStrategyRules(O))[0];
  A(stable(gen.judgmentDump(O, allPlugin)) === stable(gen.judgmentDump(O, allDirect)),
    'همه‌خاموش: مسیر پلاگین == مسیر مستقیم (قواعد پیش‌فرض بی‌صدا برنگشتند)');
}

// ══════════════════════════════════════════════════════════════
function testStrategyGatePins() {
  // S3: پین‌های خوانای دروازهٔ توافق — آینهٔ test_strategy_gate پایتون
  const g = BAT.strategy_gate;

  A(g.no_agreement.reject_reason === 'NO_STRATEGY' && g.no_agreement.signal === null
    && g.no_agreement.score >= 7,
    'امتیاز ≥ ۷ ولی صفر استراتژیِ هم‌جهت → NO_STRATEGY (دروازه مستقل از امتیاز)');
  A(g.no_agreement.status_fa === '🎯 استراتژی موافق نیست', 'status_fa دروازه');
  A(g.no_agreement.strategies.map((v) => v.direction).join(',') === 'NONE,NONE,NONE',
    'هر سه استراتژی صادقانه NONE و ثبت شدند');

  A(g.carry_only.reject_reason === 'NO_STRATEGY'
    && g.carry_only.reject_detail.indexOf('(پیشنهاددهنده: ۰)') >= 0,
    'تنها-carry: n_prop=0 → رد (D1=R2) + جزئیاتِ شمارِ پیشنهاددهنده');
  const cv = g.carry_only.strategies.filter((v) => v.key === 'carry')[0];
  A(cv.direction === 'BUY' && cv.proposes === false,
    'carry هم‌جهت ولی proposes=false — فقط توافق');

  A(g.min_agree_2.reject_reason === 'NO_STRATEGY'
    && g.min_agree_2.reject_detail.indexOf('حداقل لازم: ۲') >= 0,
    'min_agree=2 از ctx.strategiesCfg خوانده می‌شود');

  A(g.fail_closed_empty.reject_reason === 'NO_STRATEGY'
    && g.fail_closed_empty.strategies.length === 0
    && g.fail_closed_empty.reject_detail.indexOf('هیچ استراتژیِ فعالی در دسترس نیست') === 0,
    'فهرست خالی → fail-closed صادقانه (D3)');

  A(g.broken_rule_isolated.signal !== null && g.broken_rule_isolated.strategies.length === 2
    && g.broken_rule_isolated.strategies[0].name_fa === 'استراتژیِ خطاداده'
    && g.broken_rule_isolated.signal.journal.strategies.join(',') === 'trend_pullback',
    'قاعدهٔ خطاداده مانعِ سیگنال نیست (Failure Isolation) + placeholder + ژورنالِ موافق');

  A(g.broken_rule_only.reject_reason === 'NO_STRATEGY'
    && g.broken_rule_only.strategies[0].name_fa === 'استراتژیِ خطاداده',
    'فقط قاعدهٔ خطاداده → ردِ صادقانه');

  A(g.opt_out_min_agree_0.signal !== null && g.opt_out_min_agree_0.strategies.length === 3
    && g.opt_out_min_agree_0.signal.journal.strategies.length === 0,
    'min_agree=0 → دروازه خاموش (opt-out) + ارزیابی صادقانه باقی است');

  A(g.pass_full.signal !== null
    && g.pass_full.signal.journal.strategies.join(',') === 'trend_pullback',
    'مسیر سالم: سیگنال + کلیدِ موافق در ژورنال');
  const tv = g.pass_full.strategies.filter((v) => v.key === 'trend_pullback')[0];
  A(tv.direction === 'BUY' && tv.proposes === true && tv.strength > 0 && tv.strength <= 1
    && tv.name_fa === 'روند + پولبک',
    'verdict کاملِ استراتژیِ موافق (نام/جهت/قدرت/proposes)');

  // LOW_SCORE مقدم بر دروازه است و استراتژی‌ها را ارزیابی نمی‌کند
  A(BAT.judge_low_score.low_score.reject_reason === 'LOW_SCORE'
    && BAT.judge_low_score.low_score.strategies.length === 0,
    'LOW_SCORE مقدم بر NO_STRATEGY (کمترین جابه‌جاییِ آمار)');
}

// ══════════════════════════════════════════════════════════════
// v0.29 (فاز ۳+۴): طرحِ رکوردِ ژورنال — فیلدهای تازه باید *واقعاً* در
// JSONِ نوشته‌شده حاضر باشند.
//
// چرا این بررسی لازم است: یک باگِ واقعی حینِ توسعه گرفته شد. judge.js به
// O.JOURNAL_RULES_VERSION ارجاع داده بود که در journal.js تعریف می‌شود و
// *بعد از* judge.js بارگذاری می‌شود → undefined → و JSON.stringify کلیدِ
// undefined را بی‌صدا حذف می‌کند. نتیجه: رکوردهای ژورنال بدون
// rules_version نوشته می‌شدند، یعنی همان چیزی که فاز ۴ آمده بود رفع کند.
// طلایی‌ها این را نمی‌گرفتند چون خودشان هم از همان مسیر تولید می‌شوند.
function testJournalRecordSchema() {
  const sig = {
    sid: 'EURUSD-BUY-20260923140000-1.1', now: 0, symbol: 'EURUSD',
    direction: 'BUY', entry: 1.1, sl: 1.09, tp: 1.12, pip: 0.0001,
    atr: 0.001, risk_pips: 100, reward_pips: 200, rr: 2, score: 9,
    max_score: 11, session_fa: 'لندن', evidences: [], warnings: [],
    strategies: [], entry_ts: Date.UTC(2026, 8, 23, 13, 45), spread_pips: 1.5
  };
  // رفت‌وبرگشتِ واقعیِ JSON — همان کاری که appendRec روی گوشی می‌کند
  const rec = JSON.parse(JSON.stringify(O.signalToJournal(sig, true)));

  A(rec.rules_version === O.JOURNAL_RULES_VERSION,
    'رکوردِ ژورنال باید rules_version=' + O.JOURNAL_RULES_VERSION +
    ' داشته باشد (واقعی: ' + rec.rules_version + ') — undefined یعنی ' +
    'JSON.stringify بی‌صدا حذفش کرده');
  A(typeof rec.entry_ts === 'string',
    'entry_ts باید به ISO رشته شود (واقعی: ' + rec.entry_ts + ')');
  A(rec.entry_ts === new Date(sig.entry_ts).toISOString(),
    'entry_ts = ISOِ همان لحظهٔ قیمتِ اجرا');
  A(rec.spread_pips === 1.5,
    'spread_pips در رکورد حاضر است (واقعی: ' + rec.spread_pips + ')');

  // رفت‌وبرگشت از طریق Journal واقعی: بازخوانی باید همان را بدهد
  const mem = {};
  const jr = new O.Journal({ get: (k) => mem[k] || '', set: (k, v) => { mem[k] = v; } });
  jr.appendRec(rec);
  const back = jr.load()[0];
  A(back.rules_version === O.JOURNAL_RULES_VERSION,
    'Entry.rules_version از فایل بازخوانی شد (' + back.rules_version + ')');
  A(O.entryRules(back) === O.JOURNAL_RULES_VERSION,
    'O.entryRules نسخهٔ جاری را برمی‌گرداند');
  A(back.spread_pips === 1.5, 'Entry.spread_pips بازخوانی شد');
  A(back.entry_ts === sig.entry_ts,
    'Entry.entry_ts به ms بازخوانی شد (' + back.entry_ts + ')');

  // رکوردِ قدیمی (بدون فیلدهای v0.29) → نسخهٔ LEGACY، بدون حدس
  jr.appendRec({ kind: 'signal', id: 'legacy-1', ts: new Date(0).toISOString(),
    symbol: 'EURUSD', direction: 'BUY', entry: 1.1, sl: 1.09, tp: 1.12,
    pip: 0.0001, risk_pips: 100, rr: 2, score: 8 });
  const legacy = jr.load().filter((e) => e.id === 'legacy-1')[0];
  A(legacy.rules_version === null,
    'رکوردِ قدیمی rules_version ندارد → null (نه صفر، نه نسخهٔ جاری)');
  A(O.entryRules(legacy) === O.LEGACY_RULES_VERSION,
    'O.entryRules رکوردِ بی‌فیلد را LEGACY=' + O.LEGACY_RULES_VERSION +
    ' می‌شمارد (واقعی: ' + O.entryRules(legacy) + ')');
  A(legacy.entry_ts === null && legacy.spread_pips === 0 && legacy.net_r === null,
    'رکوردِ قدیمی: entry_ts=null · spread=0 · net_r=null (بدون عددِ ساختگی)');
}

// ══════════════════════════════════════════════════════════════
function main() {
  const tests = [testGoldenBattery, testVetoPins, testEvidencePins,
    testJudgePathPins, testStrategyGatePins, testRegistryRulesWhenPresent,
    testJournalRecordSchema];
  const fails = [];
  tests.forEach((t) => {
    try { t(); } catch (e) { fails.push(t.name + ': ' + (e && e.message || e)); }
  });
  if (fails.length) {
    console.log('❌ JUDGE-SWITCH TESTS FAILED');
    fails.forEach((f) => console.log('  •', f));
    process.exit(1);
  }
  console.log('✅ JUDGE-SWITCH TESTS OK — ' + COUNT + ' بررسی پاس؛ میخ‌های رفتاری '
    + 'داور JS (۶۶ سناریوی طلایی + پین‌های متنی/امتیازی + دروازهٔ توافق S3 '
    + '+ بخش مشروط registry + طرحِ رکوردِ ژورنال v0.29) سبز‌اند');
  process.exit(0);
}

main();
