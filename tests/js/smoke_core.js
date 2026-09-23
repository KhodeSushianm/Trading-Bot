/* اسموک‌تست هستهٔ پلاگین JS (فاز ۵) — آینهٔ tests/test_core.py برای js/core.js.
 *
 * اجرا: node tests/js/smoke_core.js   (آفلاین، بدون DOM، بدون شبکه)
 *
 * دو لایه (الگو از smoke_theme_parity):
 *   ۱) رفتاری: همان ۸ بخش test_core.py با همان سناریوهای پلاگین ساختگی —
 *      contracts/manifest/registry/resolver/lifecycle/config-bridge/bus/pipeline.
 *      معناها باید یکی باشد: ترتیب قطعی، آبشارِ وابستگیِ مفقود (دلیل فارسی)،
 *      حلقه پرسروصدا، قرنطینهٔ خطا، گذار نامعتبر پرسروصدا، emit بدون استثنا،
 *      stop/unavailable در pipeline.
 *   ۲) پاریتیِ سورس: فهرست‌های مشترک (STAGES/EVENTS/CONTRACTS/STATES/
 *      ALLOWED) مستقیماً از سورس پایتون (src/core/*) استخراج و با JS
 *      مقایسه می‌شوند — اگر کسی در پایتون تغییر داد، اینجا بی‌صدا رد نمی‌شود.
 *
 * نگهبان‌ها: core.js باید ES5 خالص بماند (WebView قدیمی) · از فاز ۶ فقط
 * plugins.js/app.js/data.js (لایهٔ پلاگین + ارکستراتورها) O.core را مصرف
 * می‌کنند · index.html باید core.js را *پیش از همه* بار کند.
 */
'use strict';

const fs = require('fs');
const vm = require('vm');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
const WWW = path.join(ROOT, 'android', 'app', 'src', 'main', 'assets', 'www');
const CORE_JS = path.join(WWW, 'js', 'core.js');

let failures = 0;
let checks = 0;
function ok(cond, msg) {
  checks++;
  if (!cond) { failures++; console.log('  ✗ ' + msg); }
  return !!cond;
}
function group(title) { console.log('\n── ' + title + ' ' + '─'.repeat(Math.max(0, 56 - title.length))); }

function read(f, what) {
  if (!fs.existsSync(f)) { console.error('✗ فایل پیدا نشد: ' + what + ' → ' + f); process.exit(2); }
  return fs.readFileSync(f, 'utf8');
}

// ── بارگذاری core.js در vm (بدون DOM — خودبسنده است) ─────────────
const ctx = { console, Date, JSON, Math, Object, Array };
ctx.globalThis = ctx;
vm.createContext(ctx);
vm.runInContext(read(CORE_JS, 'core.js'), ctx, { filename: 'core.js' });
const O = ctx.ODIN;

if (!ok(!!O && !!O.core, 'O.core باید پس از بارگذاری core.js وجود داشته باشد')) {
  console.error('✗ SMOKE CORE FAILED — core.js بارگذاری نشد');
  process.exit(1);
}
const core = O.core;

// ── ابزار تست (آینهٔ FakeInstance/_mk/expect_raise در test_core.py) ──
function FakeInstance(trace, name, failOn) {
  this.trace = trace;
  this.name = name;
  this.failOn = failOn || '';
}
FakeInstance.prototype.initialize = function () {
  if (this.failOn === 'initialize') throw new Error('boom-init');
  this.trace.push(this.name + ':init');
};
FakeInstance.prototype.start = function () {
  if (this.failOn === 'start') throw new Error('boom-start');
  this.trace.push(this.name + ':start');
};
FakeInstance.prototype.run = function () {
  if (this.failOn === 'run') throw new Error('boom-run');
  this.trace.push(this.name + ':run');
  return this.name;
};

function _mk(pid, provides, requires, stage, priority, config, factory) {
  return {
    id: pid, version: '1.0.0', provides: provides,
    requires: requires || [], stage: stage || 'collect_market',
    priority: (priority !== undefined ? priority : 100),
    config: config || null, factory: factory || null
  };
}

function expectThrow(errName, fn, msg, substr) {
  try {
    fn();
  } catch (e) {
    ok(e && e.name === errName, msg + ' — نام خطا «' + (e && e.name) + '» (انتظار: ' + errName + ')');
    if (substr) {
      ok(String(e.message).indexOf(substr) >= 0,
        msg + ' — پیام باید «' + substr + '» داشته باشد، داشت: «' + String(e.message).slice(0, 60) + '»');
    }
    return e;
  }
  ok(false, msg + ' — هیچ خطایی پرتاب نشد');
  return null;
}

function arrEq(a, b) {
  return Array.isArray(a) && Array.isArray(b) && a.length === b.length
    && a.every((x, i) => x === b[i]);
}

// ══════════════════════════════════════════════════════════════
group('۱) contracts — شناسه‌ها و اعتبارسنج ساختاری');
{
  const ids = Object.keys(core.CONTRACTS);
  ok(ids.length === 15, 'باید ۱۵ قرارداد باشد، ' + ids.length + ' است');
  ok(ids.every((cid) => core.isValidContractId(cid)), 'همهٔ شناسه‌های قرارداد باید معتبر باشند');
  ok(!core.isValidContractId('odin.foo@1'), 'قرارداد ثبت‌نشده باید نامعتبر باشد');
  ok(core.isWellformedContractId('odin.foo@1'), 'شکل صحیح ولی ناشناخته → wellformed');
  ok(!core.isWellformedContractId('bogus'), 'شناسهٔ بی‌شکل باید رد شود');

  // معادلِ Protocol ساختاری: fake کامل قبول، ناقص رد
  const fakeOk = { connect() {}, disconnect() {}, fetch() {} };
  ok(core.validateProvider('odin.data.market@1', fakeOk),
    'fake کامل باید validateProvider را پاس کند');
  ok(!core.validateProvider('odin.data.market@1', { connect() {} }),
    'fake ناقص (بدون fetch/disconnect) نباید قرارداد را ارضا کند');
  ok(!core.validateProvider('odin.naamoshakhas@1', fakeOk),
    'قرارداد ناشناخته → validateProvider باید false بدهد (نه استثنا)');
}

// ══════════════════════════════════════════════════════════════
group('۲) manifest — اعتبارسنجی با پیام‌های فارسی (آینهٔ manifest.py)');
{
  const m = core.manifest(_mk('good-plugin', ['odin.session@1']), core.STAGES);
  ok(m.id === 'good-plugin' && m.priority === 100 && m.optional === true,
    'مانیفست معتبر + پیش‌فرض‌ها (priority=100, optional=true)');
  ok(arrEq(m.platforms, ['desktop', 'android']), 'platforms پیش‌فرض = هر دو');

  expectThrow('InvalidManifestError',
    () => core.manifest(_mk('Bad ID!', ['odin.session@1'])),
    'id با فاصله/حرف بزرگ باید رد شود', 'شناسهٔ پلاگین نامعتبر');
  expectThrow('InvalidManifestError',
    () => core.manifest({ id: 'x', version: '1.0', provides: ['odin.session@1'], stage: 'judge' }),
    'نسخهٔ غیر-semver باید رد شود', 'semver');
  expectThrow('InvalidManifestError',
    () => core.manifest({ id: 'x', version: '1.0.0', provides: [], stage: 'judge' }),
    'provides خالی باید رد شود', 'provides خالی است');
  expectThrow('InvalidManifestError',
    () => core.manifest(_mk('x', ['odin.unknown@1'])),
    'قرارداد ناشناخته باید رد شود — هسته فقط CONTRACTS را می‌شناسد', 'قرارداد ناشناخته');
  expectThrow('InvalidManifestError',
    () => core.manifest(_mk('x', ['odin.session@1'], ['odin.session@1'])),
    'وابستگی به قراردادِ خودش باید رد شود', 'نمی‌تواند به قرارداد خودش');
  expectThrow('InvalidManifestError',
    () => core.manifest({ id: 'x', version: '1.0.0', provides: ['odin.session@1'], stage: 'judge', platforms: ['ios'] }),
    'پلتفرم نامعتبر باید رد شود', 'پلتفرم نامعتبر');
  expectThrow('InvalidManifestError',
    () => core.manifest({ id: 'x', version: '1.0.0', provides: ['odin.session@1'], stage: '' }),
    'stage خالی باید رد شود', 'خالی است');
  expectThrow('InvalidManifestError',
    () => core.manifest({ id: 'x', version: '1.0.0', provides: ['odin.session@1'], stage: 'nonexistent' }, core.STAGES),
    'مرحلهٔ ناشناخته (با knownStages) باید رد شود', 'مرحلهٔ ناشناخته');
  expectThrow('InvalidManifestError',
    () => core.manifest(_mk('x', ['odin.session@1'], null, 'judge', 100, { default: true })),
    'config بدون section/enabled_key باید رد شود', 'کلید «section» ندارد');
  expectThrow('InvalidManifestError',
    () => core.manifest(_mk('x', ['odin.session@1'], null, 'judge', 1.5)),
    'priority غیرصحیح باید رد شود', 'priority');
}

// ══════════════════════════════════════════════════════════════
group('۳) registry — ثبت/ترتیب قطعی/enable-disable/status');
{
  const reg = core.createRegistry({ knownStages: core.STAGES });
  reg.register(_mk('data-yahoo', ['odin.data.market@1'], null, 'collect_market', 20));
  reg.register(_mk('data-auto', ['odin.data.market@1'], null, 'collect_market', 10));
  reg.register(_mk('analysis', ['odin.analysis.technical@1']));

  ok(reg.all().length === 3, 'سه پلاگین باید ثبت شوند');
  const got = reg.get('odin.data.market@1');
  ok(got !== null && got.id === 'data-auto',
    'get() باید بالاترین اولویت (عدد کوچک‌تر) را برگرداند');
  ok(arrEq(reg.providers('odin.data.market@1').map((r) => r.id), ['data-auto', 'data-yahoo']),
    'ترتیب قطعی providers = (priority، سپس ثبت)');

  reg.disable('data-auto');
  ok(reg.get('odin.data.market@1').id === 'data-yahoo', 'پلاگین غیرفعال نباید از get() برگردد');
  reg.enable('data-auto');
  ok(reg.get('odin.data.market@1').id === 'data-auto', 'enable باید برگرداند');

  expectThrow('DuplicatePluginError',
    () => reg.register(_mk('data-yahoo', ['odin.data.market@1'])),
    'ثبت id تکراری باید خطا بدهد', 'قبلاً ثبت شده است');
  ok(reg.get('odin.notify@1') === null, 'قرارداد بدون فراهم‌کننده → null (نه استثنا)');

  const st = {};
  reg.status().forEach((s) => { st[s.id] = s; });
  ok(st['analysis'].state === 'registered', 'status() باید وضعیت فعلی را بدهد');
  ok('disabled_reason' in st['analysis'] && st['analysis'].enabled === true,
    'کلیدهای statusDict باید snake_case پایتون بمانند (دادهٔ بین‌موتوری)');
  expectThrow('InvalidManifestError',
    () => reg.register(_mk('bad-stage', ['odin.session@1'], null, 'nope')),
    'ثبت با stage نامعتبر (knownStages) باید رد شود', 'مرحلهٔ ناشناخته');
  ok(reg.byId('no-such') === null && reg.enable('no-such') === false,
    'byId/enable ناشناخته → null/false (بدون استثنا)');
}

// ══════════════════════════════════════════════════════════════
group('۴) resolver — توپولوژیک قطعی + آبشار + حلقهٔ پرسروصدا');
{
  const reg = core.createRegistry({ knownStages: core.STAGES });
  const recS = reg.register(_mk('session', ['odin.session@1']));
  const recC = reg.register(_mk('calendar', ['odin.fundamental.calendar@1'], ['odin.session@1']));
  const order = core.resolveOrder(reg.all());
  ok(arrEq(order.map((r) => r.id), ['session', 'calendar']),
    'ترتیب توپولوژیک: فراهم‌کننده قبل از وابسته');
  ok(recS.state === 'resolved' && recC.state === 'resolved',
    'resolveOrder باید وضعیت RESOLVED بگذارد');

  // وابستگی مفقود → disabled با دلیل فارسی، بدون استثنا
  const reg2 = core.createRegistry({ knownStages: core.STAGES });
  const recTv = reg2.register(_mk('tv-user', ['odin.report@1'], ['odin.data.tv@1']));
  const order2 = core.resolveOrder(reg2.all());
  ok(order2.indexOf(recTv) < 0, 'پلاگین با وابستگی مفقود نباید در زنجیره باشد');
  ok(typeof recTv.disabledReason === 'string' && recTv.disabledReason.indexOf('odin.data.tv@1') >= 0
     && recTv.disabledReason.indexOf('وابستگی فراهم نشد') === 0,
    'دلیل فارسی/شفاف: «وابستگی فراهم نشد: …» — داشت: «' + recTv.disabledReason + '»');
  ok(reg2.isActive(recTv) === false, 'پلاگین وابسته‌مفقود باید inactive باشد');

  // آبشاری: افتادن A باید B (وابسته به A) را هم بیندازد
  const reg3 = core.createRegistry({ knownStages: core.STAGES });
  reg3.register(_mk('a-x', ['odin.data.tv@1'], ['odin.session@1']));   // session نیست
  const recB = reg3.register(_mk('b-x', ['odin.report@1'], ['odin.data.tv@1']));
  const order3 = core.resolveOrder(reg3.all());
  ok(order3.length === 0 && !!recB.disabledReason,
    'غیرفعال‌شدن آبشاری باید هر دو را بیندازد');

  // پلاگین enabled=false از دید وابسته‌ها «نبود» است
  const reg4 = core.createRegistry({ knownStages: core.STAGES });
  const recOff = reg4.register(_mk('off-session', ['odin.session@1']));
  const recDep = reg4.register(_mk('dep-x', ['odin.analysis.technical@1'], ['odin.session@1']));
  reg4.disable('off-session');
  core.resolveOrder(reg4.all());
  ok(recOff.enabled === false, 'پلاگین خاموش نباید resolve شود');
  ok(!!recDep.disabledReason, 'وابستهٔ پلاگین خاموش باید دلیل بگیرد');

  // حلقه → پرسروصدا با نام هر دو
  const reg5 = core.createRegistry({ knownStages: core.STAGES });
  reg5.register(_mk('loop-a', ['odin.session@1'], ['odin.data.market@1']));
  reg5.register(_mk('loop-b', ['odin.data.market@1'], ['odin.session@1']));
  const e = expectThrow('CircularDependencyError', () => core.resolveOrder(reg5.all()),
    'حلقهٔ وابستگی باید پرسروصدا باشد', 'حلقهٔ وابستگی بین پلاگین‌ها');
  if (e) {
    ok(String(e.message).indexOf('loop-a') >= 0 && String(e.message).indexOf('loop-b') >= 0,
      'پیام حلقه باید مسیر/نام‌ها را داشته باشد: ' + e.message);
  }

  // چند فراهم‌کننده + tie-break قطعی (priority، سپس ترتیب ثبت، سپس id)
  const reg6 = core.createRegistry({ knownStages: core.STAGES });
  reg6.register(_mk('zzz-later', ['odin.session@1'], null, 'judge', 50));
  reg6.register(_mk('aaa-first', ['odin.report@1'], null, 'judge', 50));
  ok(arrEq(core.resolveOrder(reg6.all()).map((r) => r.id), ['zzz-later', 'aaa-first']),
    'tie-break هم‌اولویت‌ها = ترتیب ثبت (zzz-later زودتر ثبت شده — order بر id مقدم است)');
}

// ══════════════════════════════════════════════════════════════
group('۵) lifecycle — ماشین حالت + قرنطینه + گذار نامعتبر پرسروصدا');
{
  const trace = [];
  const reg = core.createRegistry({ knownStages: core.STAGES });
  const good = reg.register(_mk('life-good', ['odin.session@1'], null, 'collect_market', 100, null,
    () => new FakeInstance(trace, 'good')));
  const bad = reg.register(_mk('life-bad', ['odin.analysis.technical@1'], null, 'collect_market', 100, null,
    () => new FakeInstance(trace, 'bad', 'initialize')));
  core.resolveOrder(reg.all());

  const failuresSeen = [];
  const lm = core.createLifecycle({ onFailure: (f) => failuresSeen.push(f) });
  const failures = lm.initializeAll([good, bad], true);

  ok(good.state === 'started', 'پلاگین سالم باید STARTED شود');
  ok(bad.state === 'failed', 'پلاگین خراب باید قرنطینه (FAILED) شود');
  ok(arrEq(trace, ['good:init', 'good:start']), 'بدِ خراب نباید trace بگذارد: ' + JSON.stringify(trace));
  ok(failures.length === 1 && failures[0].plugin_id === 'life-bad' && failures[0].phase === 'initialize',
    'رکورد خطا باید دقیق باشد (plugin_id/phase با کلیدهای پایتون)');
  ok(typeof failures[0].at === 'string' && failures[0].at.length > 0, 'زمان خطا (at) ثبت می‌شود');
  ok(String(bad.error).indexOf('boom-init') >= 0, 'جزئیات خطا باید روی رکورد بماند');
  ok(failuresSeen.length === 1
     && core.failureFaMessage(failuresSeen[0]).indexOf('[!] پلاگین «life-bad» در initialize خطا داد') === 0,
    'پیام فارسی قرنطینه: ' + core.failureFaMessage(failuresSeen[0] || { plugin_id: '?', phase: '?', error: '' }));

  // گذار نامعتبر = باگ چارچوب → پرسروصدا
  const reg2 = core.createRegistry({ knownStages: core.STAGES });
  const fresh = reg2.register(_mk('fresh', ['odin.session@1']));
  expectThrow('InvalidTransitionError', () => lm.start(fresh),
    'start روی REGISTERED باید InvalidTransitionError بدهد', 'مجاز نیست');

  // stop → dispose (dispose نمونه را رها می‌کند)
  ok(lm.stop(good) === null && good.state === 'stopped', 'stop باید کار کند');
  ok(lm.dispose(good) === null && good.state === 'disposed' && good.instance === null,
    'dispose باید نمونه را رها کند');

  // FAILED قرنطینه است: بازگشت خودکار ندارد — initialize مجدد فقط
  // دوباره قرنطینه می‌کند (بدون استثنا) ولی وضعیت failed می‌ماند؛
  // start روی FAILED = گذار نامعتبر = پرسروصدا
  const reQ = lm.initialize(bad);
  ok(reQ !== null && bad.state === 'failed',
    'initialize مجدد روی FAILED → قرنطینهٔ مجدد (بازگشت خودکار نیست)');
  expectThrow('InvalidTransitionError', () => lm.start(bad),
    'start روی FAILED باید پرسروصدا رد شود (قرنطینه بازگشت ندارد)', 'مجاز نیست');

  // گزارشگرِ خطای خراب هم چرخه را نمی‌اندازد
  const reg3 = core.createRegistry({ knownStages: core.STAGES });
  const rec3 = reg3.register(_mk('boom3', ['odin.session@1'], null, 'judge', 100, null,
    () => { throw new Error('factory-boom'); }));
  core.resolveOrder(reg3.all());
  const lm3 = core.createLifecycle({ onFailure: () => { throw new Error('reporter-boom'); } });
  ok(lm3.initialize(rec3) !== null && rec3.state === 'failed',
    'خطای factory + گزارشگرِ خراب → قرنطینه بدون استثنا');
}

// ══════════════════════════════════════════════════════════════
group('۶) config-bridge — چهار سطح اولویت (کلیدهای *موجود*)');
{
  const mNews = _mk('fundamental-news', ['odin.fundamental.news@1'], null, 'collect_fundamental',
    100, { section: 'news', enabled_key: 'enabled', default: true });
  const cfg = { news: { enabled: true, min_score: 2 } };

  ok(core.pluginEnabled(cfg, mNews) === true, 'news.enabled=true → فعال');
  const off = { news: { enabled: false, min_score: 2 } };
  ok(core.pluginEnabled(off, mNews) === false, 'news.enabled=false → غیرفعال');
  const over = { news: { enabled: false }, plugins: { 'fundamental-news': { enabled: true } } };
  ok(core.pluginEnabled(over, mNews) === true, 'override صریح plugins باید برنده شود');

  const mDef = _mk('x-def', ['odin.session@1'], null, 'judge', 100,
    { section: 'not_in_cfg', enabled_key: 'enabled', default: false });
  ok(core.pluginEnabled(cfg, mDef) === false, 'بخش مفقود → پیش‌فرض مانیفست');
  const mNone = _mk('x-none', ['odin.session@1']);
  ok(core.pluginEnabled(cfg, mNone) === true, 'بدون اتصال config → فعال');
  ok(core.pluginEnabled(null, mNone) === true, 'cfg=null هم نباید بشکند');

  const sec = core.pluginConfig(cfg, _mk('n', ['odin.fundamental.news@1'], null, 'collect_fundamental',
    100, { section: 'news', enabled_key: 'enabled' }));
  ok(sec && typeof sec === 'object' && sec.min_score === 2, 'pluginConfig باید بخش config را بدهد');
  ok(Object.keys(core.pluginConfig(cfg, mNone)).length === 0, 'بدون section → object خالی');

  // applyConfigState روی registry
  const reg = core.createRegistry({ knownStages: core.STAGES });
  reg.register(mNews);
  reg.register(mNone);
  const state = core.applyConfigState(reg, off);
  ok(state['fundamental-news'] === false && reg.byId('fundamental-news').enabled === false,
    'applyConfigState باید پلاگین را طبق config خاموش کند');
  ok(state['x-none'] === true, 'بدون اتصال → روشن می‌ماند');
}

// ══════════════════════════════════════════════════════════════
group('۷) event bus — همگام، ترتیب ثبت، ایزولاسیون کامل');
{
  const bus = core.createBus();
  const seen = [];
  const l1 = function () { throw new Error('bad-listener'); };
  const l2 = function (p) { seen.push(['l2', p]); };

  bus.on(core.EVENTS.JUDGE_DONE, l1);
  const off = bus.on(core.EVENTS.JUDGE_DONE, l2);
  ok(bus.listenerCount(core.EVENTS.JUDGE_DONE) === 2, 'دو listener ثبت شد');

  const errors = bus.emit(core.EVENTS.JUDGE_DONE, { score: 9 });
  ok(errors.length === 1 && errors[0][0] === l1 && String(errors[0][1]).indexOf('bad-listener') >= 0,
    'خطای listener باید جمع شود، نه پرتاب');
  ok(seen.length === 1 && seen[0][0] === 'l2' && seen[0][1].score === 9,
    'listener خراب نباید سالم را بشکند (ترتیب ثبت)');

  off();
  ok(bus.listenerCount(core.EVENTS.JUDGE_DONE) === 1, 'unsubscribe باید کم کند');
  ok(arrEq(bus.emit('event.naamoshakhas'), []), 'رویداد ناشناخته → بدون خطا');
  ok(core.EVENTS_ALL.every((e) => typeof e === 'string')
     && new Set(core.EVENTS_ALL).size === core.EVENTS_ALL.length,
    'نام رویدادها باید string و یکتا باشند');
  ok(core.EVENTS_ALL.length === 20, '۲۰ رویداد استاندارد (همان Events.ALL پایتون)');
}

// ══════════════════════════════════════════════════════════════
group('۸) pipeline — ترتیب/خطا→unavailable+ادامه/stop/هوک پلاگین');
{
  const reg = core.createRegistry({ knownStages: core.STAGES });
  const trace = [];
  const rec = reg.register(_mk('judge-plugin', ['odin.judge.engine@1'], null, 'judge', 100, null,
    () => new FakeInstance(trace, 'judge')));
  core.resolveOrder(reg.all());
  const lm = core.createLifecycle({});
  lm.initializeAll([rec], true);
  ok(rec.state === 'started', 'پلاگین pipeline باید STARTED باشد');

  const bus = core.createBus();
  const stagesSeen = [];
  bus.on(core.EVENTS.STAGE_DONE, (p) => stagesSeen.push(p.stage));

  const runner = core.createPipeline({ registry: reg, bus });
  const order = [];
  runner.add('collect_market', () => { order.push('m1'); return 'm1'; }, 20);
  runner.add('collect_market', () => { order.push('m0'); return 'm0'; }, 10);
  runner.add('render', () => { throw new Error('render-boom'); });
  expectThrow('ValueError', () => runner.add('naamoshakhas', () => null),
    'add با مرحلهٔ ناشناخته باید رد شود', 'مرحلهٔ ناشناخته');

  const logs = [];
  const res = runner.run({}, null);
  ok(arrEq(order, ['m0', 'm1']), 'اولویت smaller-first رعایت نشد: ' + JSON.stringify(order));
  const cm = res.stage('collect_market');
  ok(cm !== null && cm.ok === true && cm.value === 'm1', 'مرحلهٔ سالم باید ok باشد');

  const rd = res.stage('render');
  ok(rd !== null && rd.unavailable === true && rd.ok === false
     && String(rd.error).indexOf('render-boom') >= 0,
    'خطای مرحله → unavailable (نه کرش)');
  ok(res.stage('dashboard') !== null, 'مراحل بعد از خطا هم باید اجرا شوند');
  ok(res.ok === false, 'خطای مرحله باید res.ok را false کند (بدون شکستن بقیه)');
  ok(stagesSeen.indexOf('judge') >= 0, 'رویداد stage.done برای judge باید منتشر شود');
  ok(arrEq(trace, ['judge:init', 'judge:start', 'judge:run']),
    'هوک run پلاگینِ مرحله باید در جریان pipeline صدا شود: ' + JSON.stringify(trace));

  // خروج زودهنگام (early-exit امروزِ cycleCore/run_cycle)
  const r2 = core.createPipeline({});
  r2.add('journal_pre', () => core.stageResult({ stage: 'journal_pre', stop: true, value: 'no-analyses' }));
  const res2 = r2.run({});
  ok(res2.stoppedAt === 'journal_pre', 'stop=true باید pipeline را زود ببندد');
  ok(res2.stage('judge') === null, 'بعد از stop هیچ مرحله‌ای نباید اجرا شود');
  const jp = res2.stage('journal_pre');
  ok(jp !== null && jp.stop === true && jp.value === 'no-analyses',
    'value/stop مرحلهٔ stop باید منتقل شود');
  ok(res2.stages.length === 2 && res2.stages[0].stage === 'collect_market',
    'pipeline از اولین مرحله (collect_market) شروع می‌شود و در journal_pre می‌ایستد');

  // unavailable صریح (دادهٔ جعلی نه — صادقانه)
  const r3 = core.createPipeline({});
  r3.add('collect_fundamental', () => core.stageResult({
    stage: 'collect_fundamental', unavailable: true, error: 'no-calendar' }));
  r3.add('judge', () => 'judged');
  const res3 = r3.run({});
  const cf = res3.stage('collect_fundamental');
  ok(cf.unavailable === true && cf.error === 'no-calendar' && cf.ok === true,
    'unavailable صریح → ok می‌ماند (خطا نیست، داده نیست)');
  ok(res3.stage('judge') !== null && res3.stoppedAt === null,
    'unavailable نباید pipeline را متوقف کند (فقط stop می‌بندد)');

  // هندلر صریح *قبل از* هوک پلاگینِ همان مرحله (ترتیب پایتون)
  const trace2 = [];
  const reg4 = core.createRegistry({ knownStages: core.STAGES });
  const rec4 = reg4.register(_mk('hooky', ['odin.session@1'], null, 'judge', 1, null,
    () => ({ run: () => { trace2.push('plugin'); } })));
  core.resolveOrder(reg4.all());
  const lm4 = core.createLifecycle({});
  lm4.initializeAll([rec4], true);
  const r4 = core.createPipeline({ registry: reg4 });
  r4.add('judge', () => { trace2.push('explicit'); }, 999);
  r4.run({});
  ok(arrEq(trace2, ['explicit', 'plugin']),
    'هندلر صریح باید پیش از هوک پلاگین اجرا شود (priority≠۱ هم): ' + JSON.stringify(trace2));

  // ترتیب STAGES == ترتیب چرخهٔ فعلی (مرجع: run_cycle در src/engine.py)
  ok(core.STAGES[0] === 'collect_market' && core.STAGES[1] === 'journal_pre'
     && core.STAGES[2] === 'collect_fundamental'
     && core.STAGES[core.STAGES.length - 1] === 'archive_notify',
    'ترتیب مراحل باید با چرخهٔ فعلی یکی باشد (فاندامنتال بعد از early-exit)');
  ok(core.STAGES.length === 11 && core.SCHEDULER_STAGES.length === 3,
    '۱۱ مرحلهٔ چرخه + ۳ مرحلهٔ زمان‌بند');
}

// ══════════════════════════════════════════════════════════════
group('۹) پاریتیِ سورس — فهرست‌ها مستقیماً از src/core/*.py استخراج می‌شوند');
{
  const pipelinePy = read(path.join(ROOT, 'src', 'core', 'pipeline.py'), 'pipeline.py');
  const busPy = read(path.join(ROOT, 'src', 'core', 'bus.py'), 'bus.py');
  const contractsPy = read(path.join(ROOT, 'src', 'core', 'contracts.py'), 'contracts.py');
  const lifecyclePy = read(path.join(ROOT, 'src', 'core', 'lifecycle.py'), 'lifecycle.py');

  function extractTuple(src, name) {
    const start = src.indexOf(name + ': tuple = (');
    if (start < 0) return null;
    const end = src.indexOf('\n)', start);   // بستنِ تورنت در ستون صفر — «)» داخل کامنت‌های فارسی گمراه‌کننده است
    const body = src.slice(start, end);
    return (body.match(/"([a-z_]+)"/g) || []).map((s) => s.slice(1, -1));
  }

  const pyStages = extractTuple(pipelinePy, 'STAGES');
  const pySched = extractTuple(pipelinePy, 'SCHEDULER_STAGES');
  ok(pyStages !== null && arrEq(Array.from(core.STAGES), pyStages),
    'STAGES باید بایت‌به‌بایت همان pipeline.py باشد');
  ok(pySched !== null && arrEq(Array.from(core.SCHEDULER_STAGES), pySched),
    'SCHEDULER_STAGES باید همان pipeline.py باشد');

  // Events: نام=مقدار از کلاس Events (خطوط «    NAME = "value"»)
  const evBody = busPy.slice(busPy.indexOf('class Events:'), busPy.indexOf('class EventBus:'));
  const pyEvents = {};
  const evRe = /^ {4}([A-Z_]+) = "([a-z.]+)"$/gm;
  let em;
  while ((em = evRe.exec(evBody)) !== null) pyEvents[em[1]] = em[2];
  ok(Object.keys(pyEvents).length === 20,
    '۲۰ رویداد از bus.py استخراج شد؟ ' + Object.keys(pyEvents).length);
  ok(Object.keys(core.EVENTS).every((k) => core.EVENTS[k] === pyEvents[k])
     && Object.keys(core.EVENTS).length === Object.keys(pyEvents).length,
    'EVENTS باید نام‌به‌نام و مقدار‌به‌مقدار همان bus.py باشد');

  // ALL tuple → ترتیب EVENTS_ALL (پس‌زدنِ خودِ «ALL = (« تا نام ALL جزء فهرست نیفتد)
  const allStart = evBody.indexOf('ALL = (');
  const allBody = evBody.slice(allStart + 'ALL = ('.length, evBody.indexOf(')', allStart));
  const pyAll = (allBody.match(/[A-Z_]{3,}/g) || []).map((n) => pyEvents[n]);
  ok(arrEq(Array.from(core.EVENTS_ALL), pyAll),
    'EVENTS_ALL باید همان ترتیب Events.ALL پایتون باشد');

  // CONTRACTS keys از contracts.py
  const cStart = contractsPy.indexOf('CONTRACTS: Dict[str, type] = {');
  const cBody = contractsPy.slice(cStart, contractsPy.indexOf('}', cStart));
  const pyContracts = (cBody.match(/"([a-z0-9.]+@\d+)":/g) || []).map((s) => s.slice(1, -2));
  ok(pyContracts.length === 15 && pyContracts.every((cid) => cid in core.CONTRACTS)
     && Object.keys(core.CONTRACTS).length === 15,
    'CONTRACTS باید دقیقاً همان ۱۵ کلید contracts.py باشد');

  // STATES از کلاس PluginState
  const stBody = lifecyclePy.slice(lifecyclePy.indexOf('class PluginState'),
    lifecyclePy.indexOf('# گذارهای مجاز'));
  const pyStates = {};
  const stRe = /^ {4}([A-Z]+) = "([a-z]+)"$/gm;
  let sm;
  while ((sm = stRe.exec(stBody)) !== null) pyStates[sm[1]] = sm[2];
  ok(Object.keys(pyStates).length === 7
     && Object.keys(core.STATES).every((k) => core.STATES[k] === pyStates[k]),
    'STATES باید همان PluginState پایتون باشد (۷ وضعیت)');

  // ALLOWED از _ALLOWED
  const alBody = lifecyclePy.slice(lifecyclePy.indexOf('_ALLOWED: Dict'),
    lifecyclePy.indexOf('\n\n', lifecyclePy.indexOf('_ALLOWED: Dict')));
  const alRe = /PluginState\.([A-Z]+): \(([^)]*)\)/g;
  let am;
  let alCount = 0;
  while ((am = alRe.exec(alBody)) !== null) {
    alCount++;
    const from = pyStates[am[1]];
    const to = (am[2].match(/PluginState\.([A-Z]+)/g) || []).map((s) => pyStates[s.replace('PluginState.', '')]);
    ok(arrEq(core.ALLOWED_TRANSITIONS[from] || [], to),
      'گذارهای ' + from + ' باید همان _ALLOWED پایتون باشد');
  }
  ok(alCount === 7, 'هر ۷ ردیف _ALLOWED از lifecycle.py استخراج شد؟ ' + alCount);
}

// ══════════════════════════════════════════════════════════════
group('۱۰) نگهبان‌ها — ES5 · مصرف‌کننده‌های مجاز · ترتیب بارگذاری در index.html');
{
  const src = read(CORE_JS, 'core.js');

  // ES5 خالص: بعد از حذف کامنت‌ها و رشته‌ها، هیچ ساختار ES6 نماند
  const stripped = src
    .replace(/\/\*[\s\S]*?\*\//g, ' ')
    .replace(/(^|[^:'"`\\])\/\/[^\n]*/g, '$1 ')
    .replace(/'(?:[^'\\]|\\.)*'/g, "''")
    .replace(/"(?:[^"\\]|\\.)*"/g, '""');
  ok(!/=>/.test(stripped), 'core.js نباید arrow function داشته باشد (ES5 برای WebView قدیمی)');
  ok(!/\bconst\b/.test(stripped), 'core.js نباید const داشته باشد');
  ok(!/\blet\b/.test(stripped), 'core.js نباید let داشته باشد');
  ok(!/\bclass\b/.test(stripped), 'core.js نباید class داشته باشد');
  ok(stripped.indexOf('`') < 0, 'core.js نباید template literal داشته باشد');

  // inert: فقط O.core اضافه می‌کند — هیچ کلید دیگری به ODIN نمی‌چسباند
  const keys = Object.keys(O);
  ok(keys.length === 1 && keys[0] === 'core',
    'core.js باید فقط O.core را تعریف کند (بدون side-effect) — یافت: ' + JSON.stringify(keys));

  // مصرف‌کننده‌های O.core — فاز ۶ رسید: فقط لایهٔ پلاگین + ارکستراتورها
  // (plugins.js/app.js/data.js). هیچ ماژول دیگری (UI/فیچر) اجازهٔ مصرف
  // مستقیم ندارد — این فهرست همان «بلوک ثبتِ پلاگین» فاز ۶ است.
  const ALLOWED_CORE_CONSUMERS = ['app.js', 'data.js', 'plugins.js'];
  const jsDir = path.join(WWW, 'js');
  const consumers = [];
  fs.readdirSync(jsDir).filter((f) => f.endsWith('.js') && f !== 'core.js').forEach((f) => {
    const code = read(path.join(jsDir, f), f)
      .replace(/\/\*[\s\S]*?\*\//g, ' ')
      .replace(/(^|[^:'"`\\])\/\/[^\n]*/g, '$1 ');
    if (/O\.core\b/.test(code)) consumers.push(f);
  });
  ok(consumers.length > 0
     && consumers.every((f) => ALLOWED_CORE_CONSUMERS.indexOf(f) >= 0)
     && ALLOWED_CORE_CONSUMERS.every((f) => consumers.indexOf(f) >= 0),
    'مصرف‌کننده‌های O.core باید دقیقاً plugins.js/app.js/data.js باشند — یافت: '
    + JSON.stringify(consumers));

  // index.html: core.js باید *اولین* اسکریپت باشد (ثبت پلاگین‌ها در فاز ۶
  // به بودنِ O.core در زمان اجرای ماژول‌ها نیاز دارد)
  const idx = read(path.join(WWW, 'index.html'), 'index.html');
  const firstScript = (idx.match(/<script src="js\/([^"]+)"><\/script>/) || [])[1];
  ok(firstScript === 'core.js',
    'اولین اسکریپت index.html باید js/core.js باشد — یافت: ' + firstScript);
  ok((idx.match(/<script src="js\/core\.js"><\/script>/g) || []).length === 1,
    'core.js باید دقیقاً یک‌بار بار شود');
}

// ══════════════════════════════════════════════════════════════
console.log('\n' + '═'.repeat(56));
if (failures) {
  console.log('✗ SMOKE CORE FAILED — ' + failures + ' از ' + checks + ' بررسی شکست خورد');
  process.exit(1);
}
console.log('✅ SMOKE CORE OK — ' + checks + ' بررسی پاس؛ هستهٔ پلاگین JS آینهٔ '
  + 'src/core/ پایتون است (رفتار + فهرست‌های مشترک از سورس) و ES5/مصرف‌کننده‌های مجاز/اولین-اسکریپت ماند');
