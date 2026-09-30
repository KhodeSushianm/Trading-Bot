#!/usr/bin/env node
/* میخ‌های پاریتیِ استراتژی‌ها — S2 (آینهٔ ES5 == اوراکل پایتون).
 *
 * اجرا:  node tests/js/test_strategies_switch.js   (آفلاین، قطعی، بدون شبکه)
 *
 * انضباط «اول میخ، بعد چکش» (الگوی test_judge_switch.js):
 *   • طلایی: tests/js/golden/strategies_golden.json — ۷۸ سناریوی ساختگیِ
 *     قطعی که با tests/js/gen_strategies_golden.py از ماژول‌های *پایتون*
 *     (اوراکل) ضبط شده‌اند (ورودی + verdict کامل).
 *   • این تست همان ورودی‌ها را در JS بازسازی می‌کند (NaN→__NaN__،
 *     time→nowMs، news_snap→newsSnap) و js/strategies.js را می‌سنجد:
 *     خروجی باید بایت‌به‌بایت با طلایی یکی باشد (فارسی/ZWNJ/قالب
 *     اعداد/floatهای IEEE754).
 *   • مسیر registry (strategy-*×۳ در plugins.js) باید == مسیر مستقیم ==
 *     طلایی باشد + enable/disable از هر دو مسیر (کلید فیچری + override).
 *   • S3 (وصل‌شدن داور) باید همین فایل را بدون تغییر سبز نگه دارد؛
 *     میخ‌های متأثرِ چرخه/داور جداگانه و با دلیلِ مستند بازضبط می‌شوند.
 *
 * پین‌های inline: shape قرارداد · proposes · قطعیت · فهرست کلیدها از سورس
 * پایتون · برابری pyTruth محلی با core.pyBool · میلهٔ با مهرِ زمانیِ خراب ·
 * ES5 بودن strategies.js · نبودِ O.core در آن (پینِ مصرف‌کننده‌های مجاز) ·
 * جایگاه اسکریپت در index.html · بخش strategies در O.CONFIG.
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const HERE = __dirname;
const ROOT = path.resolve(HERE, '..', '..');
const WWW = path.join(ROOT, 'android', 'app', 'src', 'main', 'assets', 'www');
const JS = path.join(WWW, 'js');
const GOLDEN_PATH = path.join(HERE, 'golden', 'strategies_golden.json');

let COUNT = 0;
function A(cond, msg) {
  if (!cond) throw new Error(msg);
  COUNT++;
}

// ── VM: همان فهرستِ هارنس داور + strategies.js (به ترتیب index.html) ──
function fileList() {
  const pre = ['core.js', 'plugins.js'].filter((f) => fs.existsSync(path.join(JS, f)));
  return pre.concat(['md5.js', 'fa.js', 'icons.js', 'license.js', 'config.js',
    'indicators.js', 'session.js', 'technical.js', 'calendar.js', 'news.js',
    'judge.js', 'strategies.js']);
}
function createVm() {
  const ctx = { console, Date, Math, JSON };
  ctx.globalThis = ctx;
  vm.createContext(ctx);
  for (const f of fileList()) {
    vm.runInContext(fs.readFileSync(path.join(JS, f), 'utf8'), ctx, { filename: f });
  }
  return ctx.ODIN;
}
const O = createVm();

// ── ابزار مقایسهٔ بایت‌به‌بایت (کلیدهای مرتب؛ NaN متمایز از null) ──
function stableStringify(v) {
  if (v === null) return 'null';
  if (v === undefined) return 'undefined';
  if (typeof v === 'number') return (v !== v) ? '"__NaN__"' : JSON.stringify(v);
  if (typeof v !== 'object') return JSON.stringify(v);
  if (Array.isArray(v)) return '[' + v.map(stableStringify).join(',') + ']';
  return '{' + Object.keys(v).sort()
    .map((k) => JSON.stringify(k) + ':' + stableStringify(v[k])).join(',') + '}';
}
function firstDiffPath(a, b, p) {
  p = p || '';
  if (a === b) return null;
  if (typeof a === 'number' && typeof b === 'number' && a !== a && b !== b) return null;
  if (a === null || b === null || typeof a !== 'object' || typeof b !== 'object') return p || '(root)';
  if (Array.isArray(a) !== Array.isArray(b)) return p || '(root)';
  const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
  for (const k of Array.from(keys).sort()) {
    const d = firstDiffPath(a[k], b[k], p ? p + '.' + k : k);
    if (d) return d;
  }
  return null;
}

// ── بازسازی ورودی‌ها از سریال‌سازیِ طلایی ─────────────────────────
function decode(v) {                       // "__NaN__" → NaN (بازگشتی)
  if (v === '__NaN__') return NaN;
  if (Array.isArray(v)) return v.map(decode);
  if (v && typeof v === 'object') {
    const out = {};
    Object.keys(v).forEach((k) => { out[k] = decode(v[k]); });
    return out;
  }
  return v;
}
const CAMEL = { trend_pullback: 'trendPullback', london_breakout: 'londonBreakout', carry: 'carry' };

function buildMd(h1) {
  if (h1 === null || h1 === undefined) return null;
  return { h1: h1.map((r) => ({ t: r[0], o: r[1], h: r[2], l: r[3], c: r[4] })) };
}
function buildCtx(c) {
  if (c === null || c === undefined) return null;
  return {
    nowMs: c.now_ms,
    ranking: c.ranking,
    newsSnap: c.news_snap
      ? { items: c.news_snap.items, ok: c.news_snap.items.length > 0 }
      : null
  };
}
function runScenario(s) {
  const inp = s.input;
  return O.strategies[CAMEL[s.strategy]].evaluate(
    decode(inp.a), buildMd(decode(inp.h1)), decode(inp.scfg), buildCtx(inp.ctx));
}

// ══════════════════════════════════════════════════════════════
function testGoldenBattery() {
  A(fs.existsSync(GOLDEN_PATH),
    'فایل طلایی وجود ندارد — اول python tests/js/gen_strategies_golden.py');
  const golden = JSON.parse(fs.readFileSync(GOLDEN_PATH, 'utf8'));
  const scenarios = golden.scenarios;
  A(scenarios.length === golden.meta.count && scenarios.length >= 70,
    'طلایی باید دست‌کم ۷۰ سناریو داشته باشد — یافت: ' + scenarios.length);

  const byDir = { BUY: 0, SELL: 0, NONE: 0 };
  const byStrategy = {};
  scenarios.forEach((s) => {
    const got = runScenario(s);
    const exp = decode(s.expected);
    if (stableStringify(got) !== stableStringify(exp)) {
      const at = firstDiffPath(got, exp);
      throw new Error('سناریوی «' + s.name + '» با طلایی فرق دارد — اولین اختلاف: ' + at
        + '\n    JS : ' + stableStringify(got).slice(0, 220)
        + '\n    طلایی: ' + stableStringify(exp).slice(0, 220));
    }
    byDir[exp.direction]++;
    byStrategy[s.strategy] = (byStrategy[s.strategy] || 0) + 1;
    COUNT++;
  });
  A(byDir.BUY > 0 && byDir.SELL > 0 && byDir.NONE > 0,
    'باتری باید هر سه جهت را پوشش دهد — ' + JSON.stringify(byDir));
  A(byStrategy.trend_pullback && byStrategy.london_breakout && byStrategy.carry,
    'هر سه استراتژی باید سناریو داشته باشند — ' + JSON.stringify(byStrategy));
  A(true, 'باتری طلاییِ کامل (' + scenarios.length + ' سناریو) بایت‌به‌بایت == اوراکل پایتون');
  return scenarios;
}

// ── پین‌های inline ──────────────────────────────────────────────
function testVerdictShape(scenarios) {
  const SHAPE = ['detail_fa', 'direction', 'key', 'name_fa', 'proposes',
    'reasons_fa', 'strength'];   // مرتب — مقایسه با Object.keys().sort()
  scenarios.forEach((s) => {
    const v = runScenario(s);
    A(Object.keys(v).sort().join(',') === SHAPE.join(','),
      'shape قرارداد odin.strategy@1 باید دقیق باشد (' + s.name + ')');
    A(['BUY', 'SELL', 'NONE'].indexOf(v.direction) >= 0, 'direction معتبر (' + s.name + ')');
    A(typeof v.strength === 'number' && v.strength >= 0 && v.strength <= 1,
      'strength در [0,1] (' + s.name + ')');
    A(v.proposes === (s.strategy !== 'carry'),
      'carry فقط «توافق» است (proposes=false) و دو استراتژی دیگر منبعِ جهت‌اند (' + s.name + ')');
    if (v.direction === 'NONE') {
      A(v.reasons_fa.length === 1 && v.strength === 0,
        'NONE = یک دلیل صادقانه + strength صفر (' + s.name + ')');
      A(v.detail_fa === v.name_fa + ': ' + v.reasons_fa[0],
        'detail_fa NONE باید همان دلیل باشد (' + s.name + ')');
    }
  });
}

function testDeterminism(scenarios) {
  scenarios.slice(0, 24).forEach((s) => {
    const v1 = stableStringify(runScenario(s));
    const v2 = stableStringify(runScenario(s));
    A(v1 === v2, 'استراتژی باید قطعی باشد — ' + s.name);
  });
}

function testKeyListFromPythonSource() {
  // فهرست کلیدها/idها از سورس پایتون استخراج می‌شود (الگوی smoke_core) —
  // اگر STRATEGY_RULES عوض شد، اینجا بی‌صدا سبز نمی‌ماند.
  const src = fs.readFileSync(path.join(ROOT, 'src', 'plugins', 'strategies.py'), 'utf8');
  const m = src.match(/STRATEGY_RULES[^=]*=\s*\[([\s\S]*?)\n\]/);
  A(!!m, 'STRATEGY_RULES در src/plugins/strategies.py پیدا نشد');
  const pairs = [];
  const re = /\("([^"]+)",\s*"([^"]+)"\)/g;
  let g;
  while ((g = re.exec(m[1])) !== null) pairs.push([g[1], g[2]]);
  A(pairs.length === 3, 'سه جفت (plugin_id, key) انتظار است — یافت: ' + pairs.length);
  A(stableStringify(O.STRATEGY_KEYS) === stableStringify(pairs.map((p) => p[1])),
    'O.STRATEGY_KEYS باید == کلیدهای STRATEGY_RULES پایتون باشد');
  pairs.forEach((p) => {
    A(!!O.strategyFor(p[1]) && typeof O.strategyFor(p[1]).evaluate === 'function',
      'strategyFor(\'' + p[1] + '\') باید ماژولِ evaluateدار بدهد');
  });
  let threw = false;
  try { O.strategyFor('nope'); } catch (e) { threw = true; }
  A(threw, 'استراتژیِ ناشناخته باید پرسروصدا throw شود (نه undefined بی‌صدا)');
}

function testPyTruthParity() {
  // کپیِ محلیِ pyTruth (strategies.js) باید با O.core.pyBool یکی باشد —
  // دلیل کپی: پینِ «مصرف‌کننده‌های مجاز O.core» در smoke_core.
  const src = fs.readFileSync(path.join(JS, 'strategies.js'), 'utf8');
  const mOwn = src.match(/function hasOwn\(o, k\) \{[^\n]*\}/);
  const mT = src.match(/function pyTruth\(v\) \{[\s\S]*?\n {2}\}/);
  A(!!mOwn && !!mT, 'pyTruth/hasOwn محلی در strategies.js پیدا نشد');
  // vm جدا: core.js (برای pyBool) + توابع استخراج‌شده (با وابستگیِ hasOwn)
  const ctx2 = { console };
  ctx2.globalThis = ctx2;
  vm.createContext(ctx2);
  vm.runInContext(fs.readFileSync(path.join(JS, 'core.js'), 'utf8'), ctx2, { filename: 'core.js' });
  vm.runInContext(mOwn[0] + '\n' + mT[0], ctx2, { filename: 'extract' });
  const cases = [NaN, 0, -0, 1, -1, '', 'a', [], [0], {}, { k: 1 }, null,
    undefined, true, false, Infinity, function () { }];
  cases.forEach((v, i) => {
    A(ctx2.pyTruth(v) === ctx2.ODIN.core.pyBool(v),
      'pyTruth محلی باید == core.pyBool باشد — مورد ' + i + ': ' + String(v));
  });
}

function testBadTimestampBar() {
  // میلهٔ با مهرِ زمانیِ خراب (t=null) باید شمرده نشود — بقیهٔ Range سالم
  // (JS-only: در پایتون NaT از utc_of رد می‌شود؛ اینجا dateOfMs).
  const golden = JSON.parse(fs.readFileSync(GOLDEN_PATH, 'utf8'));
  const s = golden.scenarios.filter((x) => x.name === 'lb_buy_golden')[0];
  A(!!s, 'سناریوی lb_buy_golden در طلایی نیست');
  const clean = runScenario(s);
  const rows = s.input.h1.map((r) => ({ t: r[0], o: r[1], h: r[2], l: r[3], c: r[4] }));
  rows.unshift({ t: null, o: 9.9, h: 9.9, l: 0.1, c: 9.9 });
  rows.push({ t: NaN, o: 9.9, h: 9.9, l: 0.1, c: 9.9 });
  const withBad = O.strategies.londonBreakout.evaluate(
    decode(s.input.a), { h1: rows }, decode(s.input.scfg), buildCtx(s.input.ctx));
  A(stableStringify(withBad) === stableStringify(clean),
    'میلهٔ با t=null/NaN باید بی‌اثر باشد (ردِ صادقانه، نه کرش/تغییر)');
}

function testRegistryPath(scenarios) {
  // ثبت سه پلاگین strategy-* + ترتیب priority + adapter==ماژول==طلایی
  const built = O.buildDefaultRegistry(O.CONFIG, 'android');
  const ids = built.registry.all().map((r) => r.id);
  ['strategy-trend-pullback', 'strategy-london-breakout', 'strategy-carry'].forEach((pid) => {
    A(ids.indexOf(pid) >= 0, 'پلاگین «' + pid + '» باید در registry JS ثبت شود');
  });
  const provs = built.registry.providers('odin.strategy@1');
  A(provs.length === 3, 'odin.strategy@1 باید ۳ فراهم‌کننده داشته باشد — ' + provs.length);
  A(stableStringify(provs.map((p) => p.id)) ===
    stableStringify(['strategy-trend-pullback', 'strategy-london-breakout', 'strategy-carry']),
    'ترتیب فراهم‌کنندگان = priority اعلامی (۱۰/۲۰/۳۰) — آینهٔ پایتون');

  // adapter == ماژول (scfg پیش‌فرضِ config.js == SCFG_* طلایی — هم‌مقدار با config.yaml)
  const names = { trend_pullback: 'tp_buy_golden', london_breakout: 'lb_buy_golden', carry: 'carry_audjpy_buy' };
  provs.forEach((rec) => {
    const key = rec.manifest.config.enabled_key.split('.')[0];
    const s = scenarios.filter((x) => x.name === names[key])[0];
    A(!!s, 'سناریوی نمایندهٔ ' + key + ' در طلایی نیست');
    const inst = (rec.instance !== null && rec.instance !== undefined)
      ? rec.instance : rec.factory(built.info.context);
    const viaReg = inst.evaluate(decode(s.input.a), buildMd(decode(s.input.h1)), buildCtx(s.input.ctx));
    const direct = runScenario(s);
    A(stableStringify(viaReg) === stableStringify(direct),
      'adapter «' + rec.id + '» باید بایت‌به‌بایت == ماژول باشد');
    A(stableStringify(viaReg) === stableStringify(decode(s.expected)),
      'adapter «' + rec.id + '» باید بایت‌به‌بایت == طلایی پایتون باشد');
  });

  // enable/disable — کلید فیچری (dot-path فاز ۷)
  // کپیِ عمیق با JSON (نه deepFill — آن ارجاعِ توکار را نگه می‌دارد و جهش
  // به O.CONFIG اصلی نشت می‌کرد)
  const cfgOff = JSON.parse(JSON.stringify(O.CONFIG));
  cfgOff.strategies.carry.enabled = false;
  const built2 = O.buildDefaultRegistry(cfgOff, 'android');
  A(stableStringify(built2.registry.providers('odin.strategy@1').map((p) => p.id)) ===
    stableStringify(['strategy-trend-pullback', 'strategy-london-breakout']),
    'strategies.carry.enabled=false باید پلاگین را از فراهم‌کننده‌ها حذف کند');

  // enable/disable — plugins override صریح (برنده بر کلید فیچری)
  const cfgOv = JSON.parse(JSON.stringify(O.CONFIG));
  cfgOv.plugins = { 'strategy-london-breakout': { enabled: false } };
  const built3 = O.buildDefaultRegistry(cfgOv, 'android');
  A(stableStringify(built3.registry.providers('odin.strategy@1').map((p) => p.id)) ===
    stableStringify(['strategy-trend-pullback', 'strategy-carry']),
    'plugins override صریح باید برنده شود (فاز ۷)');

  // لاگ ثبت — فارسی و شامل استراتژی‌ها (آینهٔ میخ D پایتون)
  A(built.info.log.some((l) => l.indexOf('strategy-') >= 0),
    'لاگ ثبت پلاگین‌ها باید استراتژی‌ها را نشان دهد');
}

function testConfigMirror() {
  // O.CONFIG.strategies — پورت config.yaml (منبع حقیقت YAML است؛ این پین
  // هم‌مقداریِ فعلی را قفل می‌کند تا واگرایی بی‌صدا نماند)
  const st = O.CONFIG.strategies;
  A(!!st, 'O.CONFIG.strategies باید وجود داشته باشد');
  A(st.min_agree === 1, 'min_agree پیش‌فرض = ۱ (آینهٔ config.yaml)');
  A(st.trend_pullback.enabled === true && st.trend_pullback.adx_min === 30
    && stableStringify(st.trend_pullback.rsi_buy) === '[30,45]'
    && stableStringify(st.trend_pullback.rsi_sell) === '[55,70]',
    'trend_pullback باید آینهٔ config.yaml باشد');
  const lb = st.london_breakout;
  A(lb.enabled === true && lb.asia_start_hour === 0 && lb.asia_end_hour === 7
    && lb.london_open_hour === 7 && lb.trade_window_hours === 4
    && lb.asia_min_bars === 5 && lb.min_range_atr === 0.5
    && lb.max_range_atr === 3.0 && lb.breakout_margin_atr === 0.15,
    'london_breakout باید آینهٔ config.yaml باشد');
  const ca = st.carry;
  A(ca.enabled === true && ca.min_diff === 1.5 && ca.news_min_score === 4,
    'carry باید آینهٔ config.yaml باشد');
  // ── v0.29: این نگهبان پیش‌تر مقادیر را *هاردکد* کرده بود ──────────
  // یعنی ادعای «آینهٔ config.yaml» را داشت ولی هرگز YAML را نمی‌خواند؛
  // فقط با عدد‌های ثابتِ خودش مقایسه می‌کرد. نتیجه: وقتی مالک نرخ را در
  // config.yaml به‌روز می‌کرد، این تست یا بی‌صدا بی‌ربط می‌شد یا (اگر
  // js/config.js هم عوض شده بود) قرمزِ گمراه‌کننده می‌داد. حالا واقعاً
  // YAML را می‌خواند → نگهبانِ هم‌عددیِ دو موتور، خودنگهدار.
  // v0.29.1: آستانه‌های ADX هم باید آینهٔ config.yaml باشند. این دو عدد
  // بر پایهٔ بازپخشِ تاریخی عوض شدند (adx_min_trend 20→30 · adx_strong 25→40)
  // و در *دو* فایل زندگی می‌کنند؛ واگرایی یعنی گوشی و اوراکل دو داورِ
  // متفاوت دارند. همان الگوی پارسِ YAML که پایین‌تر برای جدول نرخ هست.
  const yamlRaw = fs.readFileSync(path.join(ROOT, 'config.yaml'), 'utf8')
    .split('\n').filter((l) => !/^\s*#/.test(l));
  function yamlNum(re, label) {
    const line = yamlRaw.find((l) => re.test(l));
    A(!!line, label + ' در config.yaml پیدا نشد');
    const m = line && line.match(/:\s*([0-9.]+)/);
    A(!!m, label + ' مقدارِ عددی ندارد: ' + line);
    return m ? parseFloat(m[1]) : NaN;
  }
  const yAdxMin = yamlNum(/^ {2}adx_min_trend:/, 'analysis.adx_min_trend');
  const yAdxStrong = yamlNum(/^ {2}adx_strong:/, 'analysis.adx_strong');
  const an = O.CONFIG.analysis;
  A(an.adx_min_trend === yAdxMin,
    'analysis.adx_min_trend باید == config.yaml باشد — js:' + an.adx_min_trend
    + ' yaml:' + yAdxMin);
  A(an.adx_strong === yAdxStrong,
    'analysis.adx_strong باید == config.yaml باشد — js:' + an.adx_strong
    + ' yaml:' + yAdxStrong);
  A(yAdxStrong > yAdxMin,
    'adx_strong (' + yAdxStrong + ') باید از adx_min_trend (' + yAdxMin
    + ') بزرگ‌تر باشد — وگرنه ev_trend به همه ۲ امتیازِ مجانی می‌دهد');
  A(st.trend_pullback.adx_min === yAdxMin,
    'strategies.trend_pullback.adx_min باید هم‌عدد با analysis.adx_min_trend '
    + 'باشد — strategy:' + st.trend_pullback.adx_min + ' analysis:' + yAdxMin);

  const yaml = fs.readFileSync(path.join(ROOT, 'config.yaml'), 'utf8')
    .split('\n')
    // کامنت‌ها حذف — وگرنه عددِ ذکرشده در متنِ توضیحی، نرخ خوانده می‌شود
    // (همین اتفاق حینِ توسعه افتاد: کامنتِ «AUD از 4.35 به 4.60» پارس شد)
    .filter((l) => !/^\s*#/.test(l));
  const iRates = yaml.findIndex((l) => /^ {4}rates:\s*$/.test(l));
  A(iRates >= 0, 'بلوکِ strategies.carry.rates در config.yaml پیدا نشد');
  const yAsOf = (yaml.slice(iRates).find((l) => /^ {6}as_of:/.test(l)) || '')
    .match(/as_of:\s*"?([^"\s]+)"?/);
  A(!!yAsOf, 'as_of در config.yaml پیدا نشد');
  const iVals = yaml.findIndex((l, i) => i > iRates && /^ {6}values:\s*$/.test(l));
  A(iVals > iRates, 'values: در config.yaml پیدا نشد');
  const yVals = {};
  for (let i = iVals + 1; i < yaml.length; i++) {
    const m = yaml[i].match(/^ {8}([A-Z]{3}):\s*(.+?)\s*$/);
    if (!m) break;                       // پایانِ بلوک (کلیدِ هم‌سطح یا خالی)
    yVals[m[1]] = (m[2] === 'null') ? null : parseFloat(m[2]);
  }
  A(Object.keys(yVals).length === 8,
    '۸ ارز باید از config.yaml پارس شود — ' + Object.keys(yVals).length + ' تا: '
    + JSON.stringify(Object.keys(yVals)));
  A(ca.rates.as_of === yAsOf[1],
    'as_of باید == config.yaml باشد — js:' + ca.rates.as_of + ' yaml:' + yAsOf[1]);
  Object.keys(yVals).forEach((c) => {
    const a = ca.rates.values[c], b = yVals[c];
    const same = (a === null || b === null) ? (a === b) : (Math.abs(a - b) < 1e-9);
    A(same, 'نرخِ ' + c + ' باید == config.yaml باشد — js:' + a + ' yaml:' + b
      + ' (واگرایی یعنی گوشی و اوراکل یک کریِ متفاوت حساب می‌کنند)');
  });
  A(ca.rates.values.XAU === null && yVals.XAU === null,
    'XAU باید null بماند (طلا نرخ بهره ندارد → carry روی طلا بی‌نظر)');
  ['USD', 'EUR', 'GBP', 'JPY', 'AUD', 'CAD', 'CHF', 'XAU'].forEach((c) => {
    A(ca.rates.bias[c] === 'neutral', 'bias پیش‌فرض همه neutral است (' + c + ')');
  });
}

function testGuards() {
  const src = fs.readFileSync(path.join(JS, 'strategies.js'), 'utf8');

  // ES5 خالص (همان نگهبان smoke_core برای core.js)
  const stripped = src
    .replace(/\/\*[\s\S]*?\*\//g, ' ')
    .replace(/(^|[^:'"`\\])\/\/[^\n]*/g, '$1 ')
    .replace(/'(?:[^'\\]|\\.)*'/g, "''")
    .replace(/"(?:[^"\\]|\\.)*"/g, '""');
  A(!/=>/.test(stripped), 'strategies.js نباید arrow function داشته باشد (ES5)');
  A(!/\bconst\b/.test(stripped), 'strategies.js نباید const داشته باشد');
  A(!/\blet\b/.test(stripped), 'strategies.js نباید let داشته باشد');
  A(!/\bclass\b/.test(stripped), 'strategies.js نباید class داشته باشد');
  A(stripped.indexOf('`') < 0, 'strategies.js نباید template literal داشته باشد');

  // مصرف‌کننده‌های مجاز O.core — strategies.js نباید O.core را مصرف کند
  // (پینِ smoke_core: فقط plugins/app/data)
  A(!/O\.core\b/.test(stripped),
    'strategies.js نباید O.core را مستقیم مصرف کند (پین مصرف‌کننده‌های smoke_core)');

  // semver نقل‌قولی‌شده ممنوع (نگهبان بررسی ۷ smoke_theme_parity)
  A(!/'\d+\.\d+\.\d+'/.test(src) && !/"\d+\.\d+\.\d+"/.test(src),
    'strategies.js نباید semver نقل‌قولی‌شده داشته باشد');

  // index.html — یک تگ، بعد از judge.js (هم‌لایه‌ای) و قبل از journal.js
  const idx = fs.readFileSync(path.join(WWW, 'index.html'), 'utf8');
  A((idx.match(/<script src="js\/strategies\.js"><\/script>/g) || []).length === 1,
    'index.html باید دقیقاً یک تگ js/strategies.js داشته باشد');
  const iJudge = idx.indexOf('<script src="js/judge.js">');
  const iStrat = idx.indexOf('<script src="js/strategies.js">');
  const iJournal = idx.indexOf('<script src="js/journal.js">');
  A(iJudge >= 0 && iStrat > iJudge && iStrat < iJournal,
    'strategies.js باید بعد از judge.js و قبل از journal.js بار شود');
}

// ══════════════════════════════════════════════════════════════
const scenarios = testGoldenBattery();
testVerdictShape(scenarios);
testDeterminism(scenarios);
testKeyListFromPythonSource();
testPyTruthParity();
testBadTimestampBar();
testRegistryPath(scenarios);
testConfigMirror();
testGuards();

console.log('════════════════════════════════════════════════════════');
console.log('✅ STRATEGIES-SWITCH TESTS OK — ' + COUNT + ' بررسی پاس؛ '
  + 'آینهٔ JS سه استراتژی بایت‌به‌بایت == اوراکل پایتون (طلایی ' + scenarios.length
  + ' سناریو) + مسیر registry + enable/disable + پین‌های ساختاری سبز‌اند');
process.exit(0);
