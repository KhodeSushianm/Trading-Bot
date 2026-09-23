#!/usr/bin/env node
/* تست برابری (parity) موتور JS اندروید با موتور پایتون.
 *
 * پیش‌نیاز: python tests/js/gen_fixtures.py  (فیکسچرهای زنده را ضبط می‌کند)
 * اجرا:     node tests/js/run_parity.js
 *
 * همهٔ ماژول‌های JS اپ (همان فایل‌هایی که داخل APK بسته‌بندی می‌شوند)
 * بارگذاری و در برابر خروجی ضبط‌شدهٔ پایتون مقایسه می‌شوند:
 *   اندیکاتورها · ابزار فارسی · md5 · سشن‌ها · پارس Yahoo · باز نمونهٔ H4
 *   تحلیل تکنیکال · قدرت ارزها · تقویم · تریدینگ‌ویو · اخبار · داور (live+sim)
 *   ژورنال (tracker + stats)
 */
'use strict';

const fs = require('fs');
const path = require('path');

const HERE = __dirname;
const JS_DIR = path.join(HERE, '..', '..', 'android', 'app', 'src', 'main', 'assets', 'www', 'js');
const FIX = JSON.parse(fs.readFileSync(path.join(HERE, 'fixtures.json'), 'utf8'));

// ── بارگذاری ماژول‌های اپ (بدون DOM) ─────────────────────────
const FILES = ['core.js', 'plugins.js', 'md5.js', 'fa.js', 'icons.js', 'license.js', 'config.js', 'indicators.js', 'session.js', 'technical.js',
  'calendar.js', 'news.js', 'judge.js', 'journal.js', 'data.js', 'alerts.js', 'chart.js', 'sharecard.js', 'briefing.js', 'components.js', 'ui.js', 'app.js'];
for (const f of FILES) {
  const code = fs.readFileSync(path.join(JS_DIR, f), 'utf8');
  try {
    (0, eval)(code);           // global scope → globalThis.ODIN ساخته می‌شود
  } catch (e) {
    console.error(`❌ خطای بارگذاری ${f}: ${e.message}`);
    process.exit(1);
  }
}
const O = globalThis.ODIN;

// ── مقایسه‌گر ─────────────────────────────────────────────────
let pass = 0;
const fails = [];
const TOL = 1e-9;

function numEq(a, b, tol) {
  if (Number.isNaN(a) && (b === null || Number.isNaN(b))) return true;
  if (a === null && Number.isNaN(b)) return true;
  if (typeof a !== 'number' || typeof b !== 'number') return false;
  return Math.abs(a - b) <= (tol || TOL) * Math.max(1, Math.abs(b));
}

function deepEq(p, exp, act, tol, skipPaths) {
  if (skipPaths && skipPaths.some(sp => p.startsWith(sp))) return true;
  if (exp === null || act === null || exp === undefined || act === undefined) {
    if ((exp === null || exp === undefined) && (act === null || act === undefined || (typeof act === 'number' && Number.isNaN(act)))) return true;
    fails.push(`${p}: expected ${JSON.stringify(exp)} got ${JSON.stringify(act)}`);
    return false;
  }
  if (typeof exp === 'number' || typeof act === 'number' || Number.isNaN(exp) || Number.isNaN(act)) {
    if (!numEq(typeof exp === 'number' ? exp : null, typeof act === 'number' ? act : null, tol)) {
      fails.push(`${p}: expected ${exp} got ${act}`);
      return false;
    }
    return true;
  }
  if (typeof exp === 'string' || typeof exp === 'boolean') {
    if (exp !== act) { fails.push(`${p}: expected ${JSON.stringify(exp)} got ${JSON.stringify(act)}`); return false; }
    return true;
  }
  if (Array.isArray(exp)) {
    if (!Array.isArray(act)) { fails.push(`${p}: expected array got ${typeof act}`); return false; }
    if (exp.length !== act.length) { fails.push(`${p}: length ${exp.length} != ${act.length}`); return false; }
    let ok = true;
    for (let i = 0; i < exp.length; i++) ok = deepEq(`${p}[${i}]`, exp[i], act[i], tol, skipPaths) && ok;
    return ok;
  }
  if (typeof exp === 'object') {
    if (typeof act !== 'object') { fails.push(`${p}: expected object got ${typeof act}`); return false; }
    let ok = true;
    const keys = new Set([...Object.keys(exp), ...Object.keys(act)]);
    for (const k of keys) {
      if (!(k in exp)) { fails.push(`${p}.${k}: unexpected key in actual`); ok = false; continue; }
      if (!(k in act)) { fails.push(`${p}.${k}: missing in actual`); ok = false; continue; }
      ok = deepEq(`${p}.${k}`, exp[k], act[k], tol, skipPaths) && ok;
    }
    return ok;
  }
  if (exp !== act) { fails.push(`${p}: ${exp} != ${act}`); return false; }
  return true;
}

function check(name, fn) {
  const before = fails.length;
  try {
    fn();
  } catch (e) {
    fails.push(`${name}: EXCEPTION ${e && e.stack || e}`);
  }
  if (fails.length === before) { pass++; console.log(`  ✅ ${name}`); }
  else console.log(`  ❌ ${name} (${fails.length - before} اختلاف)`);
}

async function acheck(name, fn) {
  const before = fails.length;
  try {
    await fn();
  } catch (e) {
    fails.push(`${name}: EXCEPTION ${e && e.stack || e}`);
  }
  if (fails.length === before) { pass++; console.log(`  ✅ ${name}`); }
  else console.log(`  ❌ ${name} (${fails.length - before} اختلاف)`);
}

// ابزار ساخت کندل از آرایهٔ [t,o,h,l,c]
const C = arr => arr.map(r => ({ t: r[0], o: r[1], h: r[2], l: r[3], c: r[4] }));

// ── ماک HTTP (همه درخواست‌ها از فیکسچر ضبط‌شده پاسخ می‌گیرند) ──
const mocks = {};
O.http = async function (url, opts) {
  const key = (opts && opts.method === 'POST') ? 'POST:' + url : url;
  const hit = mocks[key] || mocks[url];
  if (!hit) throw new Error('no mock for ' + key);
  return hit;
};

(async function main() {
  console.log('🧪 تست برابری JS ↔ Python — موتور اندروید\n');

  // ── ۱) md5 ────────────────────────────────────────────────
  check('md5', () => {
    FIX.md5.forEach((c, i) => {
      const got = O.md5(c.s);
      if (got !== c.out) fails.push(`md5[${i}] "${c.s.slice(0, 30)}": ${got} != ${c.out}`);
    });
  });

  // ── ۲) ابزار فارسی ────────────────────────────────────────
  check('fa', () => {
    const map = { fa_num: O.faNum, fa_ratio: O.faRatio, fa_pips: O.faPips, fmt_price: O.fmtPrice, fa_countdown: O.faCountdown };
    FIX.fa.forEach((c, i) => {
      let got;
      if (c.fn === 'fa_date') got = O.faDate(new Date(c.args[0]), c.args[1]);
      else got = map[c.fn](...c.args);
      if (String(got) !== c.out) fails.push(`fa[${i}] ${c.fn}(${JSON.stringify(c.args)}): "${got}" != "${c.out}"`);
    });
  });

  // ── ۳) ewm و اندیکاتورها ─────────────────────────────────
  check('ewm edge cases (NaN)', () => {
    FIX.indicators.ewm_cases.forEach((c, i) => {
      const x = c.x.map(v => v === null ? NaN : v);
      const out = O.ewmAF(x, c.alpha);
      deepEq(`ewm[${i}]`, c.out, out.map(v => Number.isNaN(v) ? null : v), 1e-12);
    });
  });

  const ohlc = C(FIX.indicators.ohlc);
  const closes = FIX.indicators.closes;
  check('ema50/ema200', () => {
    deepEq('ema50', FIX.indicators.series.ema50, O.ema(closes, 50));
    deepEq('ema200', FIX.indicators.series.ema200, O.ema(closes, 200));
  });
  check('rsi14', () => deepEq('rsi14', FIX.indicators.series.rsi14, O.rsi(closes, 14)));
  check('atr14', () => deepEq('atr14', FIX.indicators.series.atr14, O.atr(ohlc, 14)));
  check('adx14', () => deepEq('adx14', FIX.indicators.series.adx14, O.adx(ohlc, 14)));
  check('swing levels + nearest', () => {
    const sw = O.swingLevels(ohlc, 5);
    deepEq('swings', FIX.indicators.swings, sw);
    const lv = O.nearestLevels(FIX.indicators.levels.price, ohlc, 5);
    deepEq('levels', FIX.indicators.levels.support, lv.support);
    deepEq('levels', FIX.indicators.levels.resistance, lv.resistance);
  });

  // ── ۴) سشن‌ها ─────────────────────────────────────────────
  check('market sessions', () => {
    FIX.session.forEach((s, i) => {
      const st = O.marketStatus(new Date(s.ts));
      deepEq(`session[${i}]`, { open: s.open, reason_fa: s.reason_fa, sessions: s.sessions, overlap: s.overlap, liquid: s.liquid, label: s.label },
        { open: st.open, reason_fa: st.reason_fa, sessions: st.sessions, overlap: st.overlap, liquid: st.liquid, label: st.label });
    });
  });

  // ── ۵) پارس پاسخ خام Yahoo + باز نمونهٔ H4 ────────────────
  for (const name of Object.keys(FIX.chartRaw)) {
    const fx = FIX.chartRaw[name];
    const symCfg = O.CONFIG.symbols.filter(s => s.name === name)[0];
    mocks['https://query1.finance.yahoo.com/v8/finance/chart/' + encodeURIComponent(symCfg.yahoo) + '?range=60d&interval=1h'] =
      { status: 200, text: JSON.stringify(fx.raw.h1) };
    mocks['https://query1.finance.yahoo.com/v8/finance/chart/' + encodeURIComponent(symCfg.yahoo) + '?range=5d&interval=15m'] =
      { status: 200, text: JSON.stringify(fx.raw.m15) };
    await acheck(`yahoo parse ${name}`, async () => {
      const md = await O.fetchYahooSymbol(symCfg, O.CONFIG.history);
      if (!md) { fails.push(`${name}: fetchYahooSymbol returned null`); return; }
      const h1 = md.h1.map(x => [x.t, x.o, x.h, x.l, x.c]);
      const m15 = md.m15.map(x => [x.t, x.o, x.h, x.l, x.c]);
      deepEq(`${name}.h1`, fx.expH1, h1, 1e-12);
      deepEq(`${name}.m15`, fx.expM15, m15, 1e-12);
    });
  }
  check('resample H1→H4', () => {
    const h4 = O.resample4h(C(FIX.symbols.EURUSD.h1)).map(x => [x.t, x.o, x.h, x.l, x.c]);
    deepEq('h4', FIX.symbols.EURUSD.h4, h4, 1e-12);
  });

  // ── ۶) تحلیل تکنیکال + قدرت ارزها ─────────────────────────
  const datasets = {};
  const analyses = [];
  check('analyzeSymbol (۷ نماد)', () => {
    for (const name of Object.keys(FIX.symbols)) {
      const fx = FIX.symbols[name];
      const md = { symbol: name, h1: C(fx.h1), m15: C(fx.m15), h4: C(fx.h4) };
      datasets[name] = md;
      const a = O.analyzeSymbol(fx.cfg, md, O.CONFIG.analysis);
      const act = Object.assign({}, a, { last_candle: a.last_candle ? a.last_candle.getTime() : null });
      deepEq(`analysis.${name}`, fx.analysis, act, 1e-9);
      analyses.push(a);
    }
  });
  check('currencyStrength', () => {
    const r = O.currencyStrength(datasets, O.CONFIG.analysis.strength_lookback_h1);
    deepEq('ranking', FIX.ranking, r.map(x => [x[0], x[1]]), 1e-12);
  });

  // ── ۷) تقویم اقتصادی ──────────────────────────────────────
  let calEvents = [];
  check('calendar parse + explain', () => {
    calEvents = O.parseEvents(FIX.calendar.raw);
    const act = calEvents.map(e => ({
      when: e.when, country: e.country, title: e.title, title_fa: e.title_fa,
      impact: e.impact, forecast: e.forecast, previous: e.previous,
      category: e.category, polarity: e.polarity, key: O.evKey(e),
      country_fa: O.evCountryFa(e), currency_fa: O.evCurrencyFa(e),
      explain: O.evExplain(e, O.CONFIG.symbols, FIX.nowMs)
    }));
    deepEq('events', FIX.calendar.events, act);
  });
  check('calendar upcoming/veto', () => {
    const up = O.upcomingEvents(calEvents, FIX.calendar.nowMs, 48, ['HIGH', 'MEDIUM']).map(O.evKey);
    deepEq('upcoming48', FIX.calendar.upcoming48, up);
    const vetoes = {};
    O.CONFIG.symbols.forEach(s => {
      vetoes[s.name] = O.vetoForSymbol(calEvents, s.base, s.quote, FIX.calendar.nowMs,
        O.CONFIG.fundamental.veto_minutes_before).map(O.evKey);
    });
    deepEq('vetoes', FIX.calendar.vetoes, vetoes);
  });

  // ── ۸) تریدینگ‌ویو ────────────────────────────────────────
  let tvMap = {};
  Object.keys(FIX.tv.raw).forEach(scr => {
    mocks['POST:https://scanner.tradingview.com/' + scr + '/scan'] =
      { status: 200, text: JSON.stringify(FIX.tv.raw[scr]) };
  });
  await acheck('tradingview scan → tvMap', async () => {
    tvMap = await O.fetchTvSnapshot(O.CONFIG.symbols, FIX.tv.tf);
    deepEq('tvMap', FIX.tv.map, tvMap, 1e-12);
  });

  // ── ۹) اخبار ──────────────────────────────────────────────
  let newsItems = [];
  check('news parse + scoring + merge', () => {
    const nc = FIX.news.config;
    const seen = {};
    let all = [];
    FIX.news.feeds.forEach(f => {
      const entries = O.parseFeedXml(f.xml);
      if (entries.length !== f.nEntries) {
        fails.push(`feed ${f.name}: entries ${entries.length} != ${f.nEntries} (feedparser)`);
      }
      let items = O.parseEntries(entries, f.name, f.weight, FIX.news.nowMs, nc.max_age_hours, nc.min_score);
      items.sort((a, b) => (b.published || FIX.nowMs) - (a.published || FIX.nowMs));
      items = items.slice(0, nc.max_items_per_feed);
      const fresh = items.filter(it => {
        const k = O.dedupeKey(it.title);
        if (seen[k]) return false;
        seen[k] = true;
        return true;
      });
      all = all.concat(fresh);
    });
    all.sort((a, b) => (b.score - a.score) || (a.age_minutes - b.age_minutes));
    newsItems = all.slice(0, nc.max_total);
    const act = newsItems.map(it => ({
      title: it.title, link: it.link, source: it.source, published: it.published,
      score: it.score, direction: it.direction, keywords: it.keywords,
      breaking: it.breaking, roundup: it.roundup, summary: it.summary,
      age_minutes: it.age_minutes, dedupe_key: O.dedupeKey(it.title),
      direction_fa: O.newsDirectionFa(it), headline_fa: O.headlineFa(it, 70)
    }));
    deepEq('news.items', FIX.news.items, act, 1e-9);
  });
  check('newsSupports', () => {
    const snap = { items: newsItems, ok: newsItems.length > 0 };
    Object.keys(FIX.news.supports).forEach(k => {
      const [sym, bias] = k.split('|');
      const s = O.CONFIG.symbols.filter(x => x.name === sym)[0];
      const v = O.newsSupports(snap, s.base, s.quote, bias, O.CONFIG.judge.news.min_score);
      const act = {
        votes: v.votes, verdict: v.verdict, has_evidence: v.has_evidence,
        support: v.support.slice(0, 2).map(i => i.title),
        contradict: v.contradict.slice(0, 2).map(i => i.title)
      };
      deepEq(`supports.${k}`, FIX.news.supports[k], act, 1e-9);
    });
  });
  check('news parseAll (بدون فیلتر سن)', () => {
    FIX.news.parseAll.forEach(fx => {
      const feed = FIX.news.feeds.filter(f => f.name === fx.name)[0];
      const entries = O.parseFeedXml(feed.xml);
      const items = O.parseEntries(entries, fx.name, fx.weight, FIX.news.nowMs, 24 * 30, 0)
        .slice(0, 40)
        .map(it => ({
          title: it.title, link: it.link, source: it.source, published: it.published,
          score: it.score, direction: it.direction, keywords: it.keywords,
          breaking: it.breaking, roundup: it.roundup, summary: it.summary,
          age_minutes: it.age_minutes, dedupe_key: O.dedupeKey(it.title),
          direction_fa: O.newsDirectionFa(it), headline_fa: O.headlineFa(it, 70)
        }));
      deepEq(`parseAll.${fx.name}`, fx.items, items, 1e-9);
    });
  });
  check('news dedupeKey (پین قطعی غیرASCII)', () => {
    // درس parity زندهٔ فاز ۴: «Pokémon» — \w جاوااسکریپت ASCII-only است و
    // نویسه‌هایی مثل é/پ را حذف می‌کرد، برخلاف \w یونیکدِ پایتون. این پین
    // مستقل از دادهٔ زنده، هم‌ترازی دو موتور را برای عنوان‌های غیرلاتین
    // (فارسی/ترکی/لهجه‌دار) قفل می‌کند.
    FIX.news.dedupe.forEach(c => {
      deepEq(`dedupeKey «${c.title.slice(0, 28)}»`, c.key, O.dedupeKey(c.title));
    });
    // é حرف است نه نقطه‌گذاری: «Pokémon» و «Pokemon» خبرِ *متفاوت‌اند* و
    // نباید با هم ادغام شوند (dedupe کاذب = خبر گم‌شده در اندروید).
    const pok = FIX.news.dedupe.filter(c => /^Pok.?mon rally extends$/.test(c.title));
    if (pok.length === 2) {
      const k1 = O.dedupeKey(pok[0].title), k2 = O.dedupeKey(pok[1].title);
      if (k1 === k2) fails.push('dedupeKey: «Pokémon» و «Pokemon» ادغام شدند (é حذف شده)');
    } else {
      fails.push(`پینِ جفت Pokémon/Pokemon در fixtures نیست (${pok.length})`);
    }
  });
  check('scoreText (عنوان‌های دست‌ساز)', () => {
    FIX.scoreText.forEach((c, i) => {
      const r = O.scoreText(c.title, c.wide || undefined);
      deepEq(`scoreText[${i}] ${c.title.slice(0, 28)}`, {
        score: c.score, direction: c.direction, keywords: c.keywords,
        breaking: c.breaking, roundup: c.roundup
      }, {
        score: r.score, direction: r.direction, keywords: r.keywords,
        breaking: r.breaking, roundup: r.roundup
      });
    });
  });

  // ── ۱۰) داور (live = اکنون، sim = چهارشنبه ۱۴:۰۰) ─────────
  const calSnap = { events: calEvents, ok: calEvents.length > 0 };
  const newsSnap = { items: newsItems, ok: newsItems.length > 0 };
  for (const tag of ['live', 'sim']) {
    const fxj = FIX.judge[tag];
    check(`judge ${tag}`, () => {
      const nowMs = fxj.nowMs;
      const ctx = {
        jcfg: O.CONFIG.judge, acfg: O.CONFIG.analysis, symbolsCfg: O.CONFIG.symbols,
        ranking: O.currencyStrength(datasets, O.CONFIG.analysis.strength_lookback_h1),
        tvMap: tvMap, calSnap: calSnap, newsSnap: newsSnap,
        nowMs: nowMs, status: O.marketStatus(new Date(nowMs)),
        eventVetoMinutes: O.CONFIG.fundamental.veto_minutes_before
      };
      const js = O.judgeAll(analyses, datasets, ctx);
      const act = js.map(j => {
        let sig = null;
        if (j.signal) {
          const s = j.signal;
          sig = {
            symbol: s.symbol, direction: s.direction, sid: s.sid, score: s.score,
            max_score: s.max_score, stars: s.stars, entry: s.entry, sl: s.sl, tp: s.tp,
            pip: s.pip, atr: s.atr, risk_pips: s.risk_pips, reward_pips: s.reward_pips,
            rr: s.rr, is_gold: s.is_gold, session_fa: s.session_fa, warnings: s.warnings,
            sl_capped: s.sl_capped, direction_fa: O.DIR_FA[s.direction],
            journal: (function () {
              const rec = O.signalToJournal(s, true);
              rec.ts = Date.parse(rec.ts);   // مقایسهٔ معنایی زمان
              return rec;
            })()
          };
        }
        return {
          symbol: j.symbol, direction: j.direction, score: j.score, max_score: j.max_score,
          reject_reason: j.reject_reason, reject_detail: j.reject_detail,
          status_fa: O.judgmentStatusFa(j), price: j.price, pip: j.pip,
          vetoes: j.vetoes, evidences: j.evidences, warnings: j.warnings, signal: sig
        };
      });
      // انتظارات پایتون را هم‌شکل کن (ts ژورنال → ms؛ detail_fa مدرک tv استثنا)
      const exp = fxj.judgments.map(j => {
        const jj = JSON.parse(JSON.stringify(j));
        if (jj.signal && jj.signal.journal) jj.signal.journal.ts = Date.parse(jj.signal.journal.ts);
        return jj;
      });
      // مقایسه با استثنا: رشتهٔ جزئیات مدرک «tv» (شمارش‌ها در API جدید null هستند
      // و موبایل به‌جایش MA/Osc را نشان می‌دهد — تفاوت عمدی و مستند است)
      for (let i = 0; i < exp.length; i++) {
        (exp[i].evidences || []).forEach((e, k) => {
          if (e.key === 'tv' && act[i].evidences && act[i].evidences[k] && act[i].evidences[k].key === 'tv') {
            act[i].evidences[k].detail_fa = e.detail_fa;   // فقط رشته پوشش داده شود
          }
        });
        deepEq(`judge.${tag}[${exp[i].symbol}]`, exp[i], act[i], 1e-9);
      }
    });
  }

  // ── ۱۱) ژورنال: tracker + stats ───────────────────────────
  check('journal resolve + stats', () => {
    const mem = {};
    const storage = { get: k => mem[k] || '', set: (k, v) => { mem[k] = String(v); }, del: k => { delete mem[k]; } };
    storage.set('journal.jsonl', FIX.journal.jsonl);
    const journal = new O.Journal(storage);
    const jds = {};
    Object.keys(FIX.journal.bars).forEach(sym => { jds[sym] = { m15: C(FIX.journal.bars[sym]) }; });
    const cfg = { journal: { enabled: true, expiry_hours: 48, conservative_both_touch: true } };
    const resolved = O.resolveOpenSignals(journal, jds, FIX.nowMs, cfg);
    const actRes = resolved.map(e => ({ id: e.id, outcome: e.outcome, r: e.r, close_price: e.close_price, note: e.note }));
    deepEq('resolved', FIX.journal.resolved, actRes, 1e-9);

    const entries = journal.load();
    const actEntries = entries.map(e => ({
      id: e.id, ts: e.ts, symbol: e.symbol, direction: e.direction, entry: e.entry,
      sl: e.sl, tp: e.tp, pip: e.pip, atr: e.atr, risk_pips: e.risk_pips,
      reward_pips: e.reward_pips, rr: e.rr, score: e.score, max_score: e.max_score,
      session: e.session, evidences: e.evidences, sent: e.sent, outcome: e.outcome,
      outcome_ts: e.outcome_ts, close_price: e.close_price, r: e.r, note: e.note,
      week_key: O.entryWeekKey(e), evidence_keys: O.entryEvidenceKeys(e)
    }));
    deepEq('entries', FIX.journal.entries, actEntries, 1e-9);

    const st = O.computeStats(entries, FIX.nowMs);
    // پایتون rateها را به‌صورت @property دارد (در vars() نیستند) — از JS حذف کن
    const strip = b => ({ closed: b.closed, wins: b.wins, losses: b.losses, expired: b.expired, r_sum: b.r_sum });
    const stripMap = m => Object.fromEntries(Object.keys(m).map(k => [k, strip(m[k])]));
    const actStats = {
      total: st.total, open_count: st.open_count, overall: strip(st.overall),
      by_symbol: stripMap(st.by_symbol), by_score: stripMap(st.by_score),
      by_evidence: stripMap(st.by_evidence), by_week: stripMap(st.by_week)
    };
    deepEq('stats', FIX.journal.stats, actStats, 1e-9);
    // نرخ‌های محاسبه‌شده هم با تعریف پایتون بررسی شود
    const pyRate = (w, l, c) => (w + l) ? w / (w + l) : null;
    const o = st.overall, eo = FIX.journal.stats.overall;
    const expHit = pyRate(eo.wins, eo.losses, eo.closed);
    if (expHit !== null && Math.abs(o.hit_rate - expHit) > 1e-12) fails.push('hit_rate mismatch');
    if (Math.abs(o.closed_win_rate - eo.wins / eo.closed) > 1e-12) fails.push('closed_win_rate mismatch');
    if (Math.abs(o.avg_r - eo.r_sum / eo.closed) > 1e-12) fails.push('avg_r mismatch');
  });

  // ── جمع‌بندی ───────────────────────────────────────────────
  console.log(`\n${'═'.repeat(52)}`);
  if (!fails.length) {
    console.log(`✅ همهٔ ${pass} تست برابری پاس شد — موتور JS با پایتون هم‌نتیجه است`);
    process.exit(0);
  }
  console.log(`❌ ${fails.length} اختلاف در ${pass} تست پاس‌شده:`);
  fails.slice(0, 800).forEach(f => console.log('   • ' + f));
  if (fails.length > 800) console.log(`   … و ${fails.length - 800} مورد دیگر`);
  process.exit(1);
})();
