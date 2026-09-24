#!/usr/bin/env node
/* میخ‌های pipeline ناهمگام JS (۶c — v0.28) + توالی رویدادهای چرخه.
 *
 * اجرا:  node tests/js/test_pipeline_events.js   (آفلاین، قطعی، بدون شبکه)
 *
 * دو بخش:
 *  A) واحدِ core.createPipelineAsync — آینهٔ رفتاریِ createPipeline همگام:
 *     ترتیب (priority, order) · stop (پرش از بقیهٔ مراحل) · unavailable
 *     (ادامهٔ pipeline) · قرنطینهٔ خطا (throw *و* promise ردشده) با همان
 *     لاگ فارسی و plugin.failed · payload رویدادهای stage.* · و پینِ
 *     «هم‌رفتاری با نسخهٔ همگام» روی هندلرهای همگام (خروجی + رویدادها
 *     بایت‌به‌بایت یکی).
 *  B) توالی رویدادهای چرخهٔ سرویس بعد از سوییچ cycleCore به مراحل نام‌دار —
 *     آینهٔ tests/test_pipeline_switch.py پایتون: چرخهٔ کامل = ۳۱ رویداد
 *     (۱۱ مرحله × start/done + ۹ استاندارد) و early-exit = دقیقاً ۷ رویداد
 *     با stop=true در journal_pre و بدون cycle.end (هم‌ترازی کانونیکال).
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const HERE = __dirname;
const ROOT = path.resolve(HERE, '..', '..');
const WWW = path.join(ROOT, 'android', 'app', 'src', 'main', 'assets', 'www');
const JS = path.join(WWW, 'js');

let COUNT = 0;
function A(cond, msg) {
  if (!cond) throw new Error(msg);
  COUNT++;
}

function loadCore() {
  const ctx = { console, Date, JSON, Math, Object, Array, Promise };
  ctx.globalThis = ctx;
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(path.join(JS, 'core.js'), 'utf8'), ctx, { filename: 'core.js' });
  return ctx.ODIN.core;
}

function stable(v) {
  if (v === null || typeof v !== 'object') return JSON.stringify(v);
  if (Array.isArray(v)) return '[' + v.map(stable).join(',') + ']';
  return '{' + Object.keys(v).sort().map((k) => JSON.stringify(k) + ':' + stable(v[k])).join(',') + '}';
}

// ══════════════════════════════════════════════════════════════
//  بخش A — واحدِ createPipelineAsync
// ══════════════════════════════════════════════════════════════
async function testAsyncUnit() {
  const core = loadCore();
  A(typeof core.createPipelineAsync === 'function',
    'core.createPipelineAsync باید وجود داشته باشد (۶c)');
  const STAGES3 = ['collect_market', 'journal_pre', 'judge'];

  function harness(stages) {
    const events = [];
    const logs = [];
    const bus = core.createBus();
    ['stage.start', 'stage.done', 'plugin.failed'].forEach((n) => {
      bus.on(n, (p) => events.push([n, p]));
    });
    const pipe = core.createPipelineAsync({ bus: bus, log: (m) => logs.push(m), stages: stages || STAGES3 });
    return { pipe, events, logs, bus };
  }

  // ۱) ترتیب اجرا: handlerهای sync و promise درهم — ترتیب (priority, order)
  {
    const h = harness();
    const seen = [];
    h.pipe.add('collect_market', () => { seen.push('a'); }, 10);
    h.pipe.add('collect_market', () => Promise.resolve().then(() => { seen.push('b'); }), 5);
    h.pipe.add('collect_market', () => { seen.push('c'); }, 10);
    const res = await h.pipe.run({});
    A(seen.join(',') === 'b,a,c', 'ترتیب (priority, order) باید حفظ شود — ' + seen.join(','));
    A(res.ok === true && res.stoppedAt === null && res.stages.length === 3,
      'اجرای سالم: هر ۳ مرحله، بدون stop');
    A(res.stage('journal_pre') !== null && res.stage('nope') === null,
      'res.stage(name) مثل نسخهٔ همگام');
  }

  // ۲) مقدارِ آخرین handler در StageResult.value (sync و promise یکسان)
  {
    const h = harness();
    h.pipe.add('judge', () => 'x');
    h.pipe.add('judge', () => Promise.resolve('y'));
    const res = await h.pipe.run({});
    A(res.stage('judge').value === 'y', 'value = خروجی آخرین handler (promise)');
  }

  // ۳) stop: بقیهٔ handlerهای مرحله و مراحل بعدی هرگز اجرا نمی‌شوند
  {
    const h = harness();
    const seen = [];
    h.pipe.add('journal_pre', () => { seen.push('j1'); return core.stageResult({ stage: 'journal_pre', stop: true, value: 'V' }); });
    h.pipe.add('journal_pre', () => { seen.push('j2-نباید'); });
    h.pipe.add('judge', () => { seen.push('judge-نباید'); });
    const res = await h.pipe.run({});
    A(seen.join(',') === 'j1', 'stop: handlerهای بعدی و مراحل بعدی skip شدند');
    A(res.stoppedAt === 'journal_pre' && res.stages.length === 2,
      'stoppedAt + فقط مراحلِ تا-stop اجرا شدند');
    A(res.stage('journal_pre').stop === true && res.stage('journal_pre').value === 'V',
      'StageResult.stop/value در stop');
    const done = h.events.filter((e) => e[0] === 'stage.done').map((e) => e[1]);
    A(done.length === 2 && done[1].stage === 'journal_pre' && done[1].stop === true
      && done[1].ok === true && done[1].unavailable === false,
      'payload رویداد stage.done در stop: {stage, ok:true, unavailable:false, stop:true}');
    A(!h.events.some((e) => e[1] && e[1].stage === 'judge'),
      'پس از stop هیچ stage.start برای مرحلهٔ بعد منتشر نشد (آینهٔ پایتون)');
  }

  // ۴) unavailable: بقیهٔ مرحله skip ولی pipeline ادامه دارد (res.ok true می‌ماند)
  {
    const h = harness();
    const seen = [];
    h.pipe.add('collect_market', () => { seen.push('m1'); return core.stageResult({ stage: 'collect_market', unavailable: true, error: 'E', value: 42 }); });
    h.pipe.add('collect_market', () => { seen.push('m2-نباید'); });
    h.pipe.add('judge', () => { seen.push('judge'); });
    const res = await h.pipe.run({});
    A(seen.join(',') === 'm1,judge', 'unavailable: skip درون‌مرحله‌ای، ادامهٔ pipeline');
    const cm = res.stage('collect_market');
    A(cm.unavailable === true && cm.error === 'E' && cm.value === 42 && cm.ok === true,
      'StageResult unavailable/error/value/ok');
    A(res.ok === true && res.stoppedAt === null,
      'unavailable ≠ stop و ≠ خرابی — res.ok دست‌نخورده (آینهٔ همگام)');
  }

  // ۵) قرنطینهٔ throw: لاگ فارسی + plugin.failed + res.ok=false + ادامه
  {
    const h = harness();
    const seen = [];
    h.pipe.add('judge', () => { throw new Error('boom-1'); });
    h.pipe.add('judge', () => { seen.push('after-throw-نباید'); });
    const res = await h.pipe.run({});
    const sr = res.stage('judge');
    A(sr.ok === false && sr.unavailable === true && sr.error === 'boom-1',
      'قرنطینه: ok=false/unavailable/error');
    A(seen.length === 0, 'handlerهای بعد از throw در همان مرحله skip شدند');
    A(res.ok === false, 'res.ok=false با قرنطینه');
    A(h.logs.length === 1 && h.logs[0].indexOf('[!]') === 0
      && h.logs[0].indexOf('stage:judge') >= 0 && h.logs[0].indexOf('boom-1') >= 0,
      'لاگ فارسی قرنطینه (همان متن نسخهٔ همگام): ' + JSON.stringify(h.logs));
    const failed = h.events.filter((e) => e[0] === 'plugin.failed');
    A(failed.length === 1 && failed[0][1].plugin_id === 'stage:judge'
      && failed[0][1].phase === 'run' && failed[0][1].error === 'boom-1',
      'plugin.failed با payload همان makeFailure همگام');
    const done = h.events.filter((e) => e[0] === 'stage.done' && e[1].stage === 'judge')[0];
    A(done && done[1].ok === false && done[1].unavailable === true && done[1].stop === false,
      'stage.done پس از قرنطینه: ok=false/unavailable=true/stop=false');
  }

  // ۶) قرنطینهٔ promise ردشده — همان مسیرِ throw (رفتارِ مخصوص async)
  {
    const h = harness();
    h.pipe.add('collect_market', () => Promise.reject(new Error('boom-2')));
    h.pipe.add('judge', () => 'ran');
    const res = await h.pipe.run({});
    A(res.stage('collect_market').error === 'boom-2'
      && res.stage('collect_market').ok === false,
      'promise ردشده → قرنطینه (همان throw)');
    A(res.stage('judge').value === 'ran' && res.ok === false,
      'مراحل بعد از قرنطینه اجرا می‌شوند؛ res.ok=false می‌ماند');
    A(h.events.some((e) => e[0] === 'plugin.failed' && e[1].error === 'boom-2'),
      'plugin.failed برای promise ردشده');
  }

  // ۷) توالی رویدادها در اجرای سالم دو مرحله‌ای
  {
    const h = harness(['collect_market', 'judge']);
    h.pipe.add('collect_market', () => 1);
    h.pipe.add('judge', () => 2);
    await h.pipe.run({});
    const seq = h.events.map((e) => e[0] + ':' + (e[1].stage || ''));
    A(seq.join('|') === 'stage.start:collect_market|stage.done:collect_market|stage.start:judge|stage.done:judge',
      'توالی رویدادهای stage.* قطعی است: ' + seq.join('|'));
  }

  // ۸) هم‌رفتاری با نسخهٔ همگام روی هندلرهای همگام (پینِ قویِ آینه)
  {
    const mk = (create) => {
      const events = [];
      const bus = core.createBus();
      ['stage.start', 'stage.done', 'plugin.failed'].forEach((n) => {
        bus.on(n, (p) => events.push([n, n === 'plugin.failed'
          ? { plugin_id: p.plugin_id, phase: p.phase, error: p.error }   // at غیرقطعی است
          : p]));
      });
      const pipe = create({ bus: bus, log: () => {}, stages: STAGES3 });
      pipe.add('collect_market', () => 'm', 10);
      pipe.add('journal_pre', (c) => core.stageResult({ stage: 'journal_pre', stop: true, value: 'S' }));
      pipe.add('judge', () => 'never');
      return { pipe, events };
    };
    const sync = mk(core.createPipeline);
    const async_ = mk(core.createPipelineAsync);
    const resSync = sync.pipe.run({});
    const resAsync = await async_.pipe.run({});
    const norm = (r) => stable({
      ok: r.ok, stoppedAt: r.stoppedAt,
      stages: r.stages.map((x) => ({ stage: x.stage, ok: x.ok, value: x.value, stop: x.stop, unavailable: x.unavailable, error: x.error }))
    });
    A(norm(resSync) === norm(resAsync),
      'خروجی async == sync بایت‌به‌بایت (روی هندلرهای همگام)');
    A(stable(sync.events) === stable(async_.events),
      'رویدادهای async == sync بایت‌به‌بایت');
  }

  // ۹) مرحلهٔ ناشناخته — همان پیام فارسی نسخهٔ همگام
  {
    const h = harness();
    let msgA = null, msgS = null;
    try { h.pipe.add('nope', () => {}); } catch (e) { msgA = e.message; }
    const s = core.createPipeline({ stages: STAGES3 });
    try { s.add('nope', () => {}); } catch (e) { msgS = e.message; }
    A(msgA !== null && msgA === msgS, 'add روی مرحلهٔ ناشناخته: همان پیام همگام');
  }

  // ۱۰) onlyStages — زیرمجموعهٔ قطعی
  {
    const h = harness();
    const seen = [];
    ['collect_market', 'journal_pre', 'judge'].forEach((st) => h.pipe.add(st, () => { seen.push(st); }));
    const res = await h.pipe.run({}, ['judge', 'collect_market']);
    A(seen.join(',') === 'judge,collect_market', 'onlyStages با ترتیب داده‌شده اجرا می‌شود');
    A(res.stages.map((x) => x.stage).join(',') === 'judge,collect_market', 'stages = همان فهرست');
  }

  // ۱۱) handlerهای registry (هوک run پلاگین STARTED) — آینهٔ همگام
  {
    const busA = core.createBus();
    const reg = core.createRegistry({ knownStages: STAGES3 });
    const man = core.manifest({ id: 'p1', version: '1.0.0', provides: ['odin.session@1'], stage: 'judge', priority: 10 }, STAGES3);
    const rec = reg.register(man, () => ({ run: (c) => { c.hooked = (c.hooked || 0) + 1; } }));
    rec.instance = rec.factory({});
    rec.state = core.STATES.STARTED;
    const pipe = core.createPipelineAsync({ bus: busA, registry: reg, stages: STAGES3 });
    const ctx = {};
    await pipe.run(ctx);
    A(ctx.hooked === 1, 'هوک run پلاگینِ STARTED در async هم صدا زده می‌شود');
  }
}

// ══════════════════════════════════════════════════════════════
async function main() {
  await testAsyncUnit();
  // بخش B (توالی رویدادهای چرخه) در کامیت سوییچ (C2) فعال می‌شود
  console.log('✅ PIPELINE-EVENTS TESTS OK — ' + COUNT + ' بررسی پاس؛ '
    + 'createPipelineAsync آینهٔ رفتاریِ createPipeline است (ترتیب/stop/unavailable/'
    + 'قرنطینهٔ throw و promise-ردشده/رویدادها/هم‌رفتاری بایت‌به‌بایت)');
  process.exit(0);
}

main().catch((e) => {
  console.error('❌ PIPELINE-EVENTS TESTS FAILED:', e && e.message || e);
  process.exit(1);
});
