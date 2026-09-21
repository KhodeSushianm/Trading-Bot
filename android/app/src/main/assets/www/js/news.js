/* موتور اخبار — پورت دقیق src/fundamental/news.py
 *
 * هر خبر: امتیاز اهمیت (۰..۶) + جهت اثر روی ارزها + برچسب فوری.
 * قاعدهٔ کلیدی: «حرکت قیمت» بر «کلیدواژهٔ سیاستی» اولویت دارد.
 * ⚠️ جهت‌دهی بر پایهٔ کلیدواژه است (سرنخ، نه حکم قطعی) — در داور فقط
 *    ۱ امتیاز از ۱۱ وزن دارد.
 *
 * پارس RSS/Atom با regex انجام می‌شود (بدون DOMParser) تا در WebView و
 * محیط تست Node یکسان کار کند.
 */
(function (O) {
  'use strict';

  O.NEWS_CURRENCY_FA = {
    USD: 'دلار آمریکا', EUR: 'یورو', GBP: 'پوند', JPY: 'ین ژاپن',
    CHF: 'فرانک سوئیس', CAD: 'دلار کانادا', AUD: 'دلار استرالیا',
    NZD: 'دلار نیوزیلند', CNY: 'یوان چین', XAU: 'طلا', OIL: 'نفت'
  };

  // ── شناسایی ارزها در متن (الگوها روی متن lowercase اجرا می‌شوند) ──
  var CURRENCY_PATTERNS = {
    USD: [
      '(?<!canadian )(?<!australian )(?<!zealand )(?<!singapore )(?<!hong kong )\\bdollar(?:s)?\\b',
      '\\busd\\b', '\\bfed\\b', '\\bfederal reserve\\b', '\\bfomc\\b',
      '\\bpowell\\b', '\\bwall street\\b', '\\btreasury yields?\\b', '\\bunited states\\b',
      '\\bus\\b(?=\\s+(?:economy|data|labor|consumer|dollar|stocks|treasur|jobless))'
    ],
    EUR: ['\\beuro(?:s)?\\b', '\\beur\\b', '\\becb\\b', '\\blagarde\\b', '\\beuro ?zone\\b',
      '\\bgerman(?:y)?\\b', '\\bfrance\\b', '\\bfrench\\b', '\\bitaly\\b', '\\bitalian\\b',
      '\\bspain\\b', '\\bspanish\\b', '\\bbundesbank\\b'],
    GBP: ['\\bsterling\\b', '\\bpound(?:s)?\\b', '\\bgbp\\b', '\\bboe\\b', '\\bbank of england\\b',
      '\\bunited kingdom\\b', '\\bbritain\\b', '\\bbritish\\b', '\\buk\\b'],
    JPY: ['\\byen\\b', '\\bjpy\\b', '\\bboj\\b', '\\bbank of japan\\b', '\\bjapan(?:ese)?\\b', '\\bueda\\b'],
    CHF: ['\\bswiss franc\\b', '\\bfranc(?:s)?\\b', '\\bchf\\b', '\\bsnb\\b', '\\bswiss\\b', '\\bswitzerland\\b'],
    CAD: ['\\bcanadian dollar\\b', '\\bloonie\\b', '\\bcad\\b', '\\bboc\\b', '\\bbank of canada\\b', '\\bcanada\\b', '\\bcanadian\\b'],
    AUD: ['\\baus(?:sie)? dollar\\b', '\\baussie\\b', '\\baud\\b', '\\brba\\b', '\\breserve bank of australia\\b', '\\baustralia(?:n)?\\b'],
    NZD: ['\\bnzd\\b', '\\bkiwi\\b', '\\brbnz\\b', '\\bnew zealand\\b'],
    CNY: ['\\byuan\\b', '\\brenminbi\\b', '\\bcny\\b', '\\bpboc\\b', '\\bchina\\b', '\\bchinese\\b'],
    XAU: ['\\bgold\\b', '\\bbullion\\b', '\\bxau\\b'],
    OIL: ['\\bcrude oil\\b', '\\bwti\\b', '\\bbrent\\b', '\\bopec\\b', '\\boils?\\b']
  };
  // از پیش ساخته شوند (RegExp گران است)
  var CURRENCY_RE = {};
  Object.keys(CURRENCY_PATTERNS).forEach(function (code) {
    CURRENCY_RE[code] = CURRENCY_PATTERNS[code].map(function (p) { return new RegExp(p); });
  });

  var PAIR_CODES = 'USD|EUR|GBP|JPY|CHF|CAD|AUD|NZD|CNY|XAU|SEK|NOK|MXN|TRY|ZAR|SGD';
  var PAIR_RE = new RegExp('\\b(' + PAIR_CODES + ')\\s*/?\\s*(' + PAIR_CODES + ')\\b', 'gi');

  // ── واژگان جهت‌دار: [الگو، وزن، برچسب فارسی] ────────────────
  var PRICE_BULL = [
    ['\\brall(?:y|ies|ied)\\b', 2, 'رالی/صعود'],
    ['\\bsurg(?:e|es|ed|ing)\\b', 2, 'جهش'],
    ['\\bsoars?\\b', 2, 'پرواز قیمت'],
    ['\\bjumps?\\b', 2, 'جهش'],
    ['\\bspikes?\\b', 2, 'جهش ناگهانی'],
    ['\\bclimbs?\\b', 2, 'صعود'],
    ['\\bstrengthens?\\b|\\bappreciat\\w+\\b', 2, 'تقویت'],
    ['\\bgains?\\b|\\bextends? gains\\b', 1, 'افزایش'],
    ['\\badvances?\\b', 1, 'پیشروی'],
    ['\\brises?\\b|\\bhigher\\b', 1, 'بالا رفتن'],
    ['\\brebounds?\\b|\\brecovers\\b', 1, 'بازگشت/احیا'],
    ['\\btops\\b|\\bhits (?:new |multi-\\w+ )?high', 1, 'ثبت سقف'],
    ['\\bupside\\b|\\bskewed to the upside\\b', 2, 'تمایل به افزایش'],
    ['\\b(?:two|three|four|\\d+)[-\\s](?:week|month|day|year|session)[-\\s]high\\b', 2, 'سقف چند دوره‌ای']
  ];
  var PRICE_BEAR = [
    ['\\bplung(?:e|es|ed|ing)\\b', 2, 'سقوط شدید'],
    ['\\btumbles?\\b', 2, 'سقوط'],
    ['\\bslumps?\\b', 2, 'افت شدید'],
    ['\\bsinks?\\b', 2, 'سقوط'],
    ['\\bselloff\\b|\\bsell[- ]off\\b', 2, 'فروش گسترده'],
    ['\\bcrash(?:es|ed|ing)?\\b', 2, 'سقوط بازار'],
    ['\\bslid(?:e|es|ing)\\b|\\bslips?\\b', 2, 'افت'],
    ['\\bweakens?\\b|\\bdeprecat\\w+\\b', 2, 'ضعیف شدن'],
    ['\\bfalls?\\b|\\bdrop(?:s|ped)?\\b|\\blower\\b|\\bdeclin(?:e|es|ed)\\b', 1, 'کاهش'],
    ['\\bretraces?\\b|\\bpull(?:s|ed)? back\\b|\\bstalls?\\b|\\bstalling\\b', 1, 'عقب‌نشینی/توقف'],
    ['\\bunder pressure\\b|\\bpressured\\b', 1, 'تحت فشار'],
    ['\\bdownside\\b|\\bskewed to the downside\\b', 2, 'تمایل به کاهش'],
    ['\\b(?:two|three|four|\\d+)[-\\s](?:week|month|day|year|session)[-\\s]low\\b', 2, 'کف چند دوره‌ای'],
    ['\\bhits (?:new |multi-\\w+ )?low', 1, 'ثبت کف']
  ];
  var MACRO_BULL = [
    ['\\bhawkish\\b', 2, 'هاوکیش (انقباضی)'],
    ['\\brate hike(?:s)?\\b|\\bhikes? rates?\\b', 2, 'افزایش نرخ بهره'],
    ['\\bhigher for longer\\b', 2, 'بهرهٔ بالا برای مدت طولانی'],
    ['\\b(?:beats?|tops?|above) (?:forecast|estimates?|expectations?|consensus)\\b', 2, 'بهتر از انتظار'],
    ['\\bstrong(?:er|ly)?\\b|\\bupbeat\\b|\\bresilien\\w+\\b', 1, 'دادهٔ قوی'],
    ['\\btighten(?:ing)?\\b', 1, 'انقباض پولی'],
    ['\\bsafe[- ]haven (?:demand|buying|bid|flows?)\\b|\\bflight to safety\\b', 2, 'تقاضای پناهگاه امن'],
    ['\\bbid\\b|\\bsupport(?:s|ed)?\\b', 1, 'حمایت/تقاضا']
  ];
  var MACRO_BEAR = [
    ['\\bdovish\\b', 2, 'داویش (انبساطی)'],
    ['\\brate cut(?:s)?\\b|\\bcuts? rates?\\b', 2, 'کاهش نرخ بهره'],
    ['\\b(?:misses?|below|worse than) (?:forecast|estimates?|expectations?|consensus)\\b', 2, 'بدتر از انتظار'],
    ['\\bweak(?:ness|ens|ened|er)?\\b|\\bsoft(?:ens|ened|er)?\\b', 2, 'دادهٔ ضعیف'],
    ['\\brecession(?:ary| fears?)?\\b', 2, 'ترس از رکود'],
    ['\\bdisappoint\\w+\\b|\\bunderwhelm\\w+\\b', 2, 'ناامیدکننده'],
    ['\\beas(?:e|es|ing|ed)\\b|\\bstimulus\\b', 1, 'تسهیل پولی'],
    ['\\bintervention\\b|\\brate check\\b', 2, 'مداخلهٔ ارزی'],
    ['\\b(?:worst|weakest) (?:week|day|month|session|performance) since\\b', 2, 'بدترین بازه'],
    ['\\bunderperform(?:s|ed)?\\b', 1, 'عملکرد ضعیف'],
    ['\\btariffs?\\b|\\btrade war\\b|\\bsanctions?\\b', 1, 'جنگ تجاری/تحریم']
  ];
  var TABLES = [PRICE_BULL, PRICE_BEAR, MACRO_BULL, MACRO_BEAR].map(function (t) {
    return t.map(function (row) { return [new RegExp(row[0]), row[1], row[2]]; });
  });

  var RISK_OFF_RE = /\b(?:risk[- ]off|war|wars|attack(?:s|ed)?|strike[sd]?|missile|conflict|escalat\w*|sanctions?|shutdown|default(?:s|ed)?|panic|safe[- ]haven|flight to safety|geopolit\w+|crisis)\w*\b/i;
  var BREAKING_RE = /^\s*(?:🚨\s*|\*\*\s*)?(?:breaking|urgent|just in|alert|flash)\b/i;
  var BREAKING_ANY_RE = /\b(?:breaking news|urgent|just in|market alert)\b/i;
  var ROUNDUP_RE = /\b(?:wrap|round ?up|roundup|kickstart|what (?:to watch|we learned)|week ahead|things to know|morning (?:briefing|call)|daily (?:brief|recap)|recap|look(?:ing)? ahead|top stories|market(?:s)? today|tgif|weekly (?:review|preview))\b/i;
  var UNTRACKED_ASSET_RE = /\b(?:silver|copper|platinum|palladium|bitcoin|btc|ethereum|eth|crypto\w*|bonds?|treasur(?:y|ies)\w*|stocks?|equit\w+|shares?|s&?p ?500|nasdaq|dow jones|nikkei|dax|ftse|hang seng)\b/i;
  var AGAINST_RE = /\b(?:against|versus|vs\.?|relative to)\b/i;
  var JPY_INTERVENTION_RE = /\b(?:intervention|rate check|verbal intervention|buying (?:the )?yen|yen buying)\b/i;
  var SAFE_HAVEN = ['USD', 'JPY', 'CHF', 'XAU'];
  var ASSET_CODES = ['XAU', 'OIL'];

  // ── شناسایی ارزها ────────────────────────────────────────────
  O.currencySpans = function (text) {
    var low = text.toLowerCase();
    var spans = {};
    Object.keys(CURRENCY_RE).forEach(function (code) {
      for (var i = 0; i < CURRENCY_RE[code].length; i++) {
        var m = low.match(CURRENCY_RE[code][i]);
        if (m) { spans[code] = m.index; break; }
      }
    });
    var re = new RegExp(PAIR_RE.source, 'gi');
    var pm;
    while ((pm = re.exec(text)) !== null) {
      [pm[1].toUpperCase(), pm[2].toUpperCase()].forEach(function (g) {
        if (O.NEWS_CURRENCY_FA[g] || g === 'XAU') {
          if (!(g in spans)) spans[g] = pm.index;
        }
      });
    }
    return Object.keys(spans).map(function (c) { return [c, spans[c]]; })
      .sort(function (a, b) { return a[1] - b[1]; });
  };

  O.subjectSpans = function (text) {
    var spans = O.currencySpans(text);
    var m = text.toLowerCase().match(UNTRACKED_ASSET_RE);
    if (m) spans.push(['OTHER', m.index]);
    spans.sort(function (a, b) { return a[1] - b[1]; });
    return spans;
  };

  function matchGroup(text, table) {
    var total = 0, labels = [];
    table.forEach(function (row) {
      if (row[0].test(text)) { total += row[1]; labels.push(row[2]); }
    });
    return [total, labels];
  }

  // ── امتیازدهی جهت‌دار به متن یک خبر ─────────────────────────
  O.scoreText = function (text, wide) {
    var title = text.trim();
    var low = title.toLowerCase();
    var wideLow = (wide || title).toLowerCase();

    var pb = matchGroup(low, TABLES[0]);
    var pbr = matchGroup(low, TABLES[1]);
    var mb = matchGroup(low, TABLES[2]);
    var mbr = matchGroup(low, TABLES[3]);
    var priceBull = pb[0], priceBear = pbr[0], macroBull = mb[0], macroBear = mbr[0];

    var spans = O.currencySpans(wide || title);
    var currencies = spans.map(function (x) { return x[0]; });
    var breaking = BREAKING_RE.test(title) || BREAKING_ANY_RE.test(title);
    var riskOff = RISK_OFF_RE.test(wideLow);
    var roundup = ROUNDUP_RE.test(low) || title.endsWith('?');
    var kws = pb[1].concat(pbr[1], mb[1], mbr[1]).slice(0, 4);

    if (!currencies.length) return { score: breaking ? 1 : 0, direction: {}, keywords: kws, breaking: breaking, roundup: roundup };

    // جهت خالص: حرکت قیمت بر کلیدواژهٔ سیاستی اولویت دارد
    var pa = priceBull - priceBear, ma = macroBull - macroBear;
    var net = pa !== 0 ? (pa > 0 ? 1 : -1) : (ma !== 0 ? (ma > 0 ? 1 : -1) : 0);

    var direction = {}, pairFired = false;
    var subj = O.subjectSpans(wide || title);
    var subject = subj.length ? subj[0][0] : null;

    if (subject === 'OTHER') {
      net = 0;                        // سوژه، دارایی خارج از پوشش است → جهت نمی‌دهیم
    } else if (roundup) {
      net = 0;                        // جمع‌بندی چندجهتی — صادقانه‌تر از حدس زدن
    } else if (net !== 0) {
      PAIR_RE.lastIndex = 0;
      var pair = PAIR_RE.exec(title);
      if (pair && pair[1].toUpperCase() !== pair[2].toUpperCase()) {
        var b = pair[1].toUpperCase(), q = pair[2].toUpperCase();
        direction[b] = net; direction[q] = -net;
        pairFired = true;
      } else {
        var against = title.match(AGAINST_RE);
        if (against && currencies.length >= 2) {
          var idx = against.index;
          var sSubj = spans.filter(function (x) { return x[1] < idx; }).map(function (x) { return x[0]; });
          var sObj = spans.filter(function (x) { return x[1] >= idx; }).map(function (x) { return x[0]; });
          if (sSubj.length && sObj.length) {
            sSubj.forEach(function (c) { direction[c] = net; });
            sObj.forEach(function (c) { direction[c] = -net; });
          }
        }
        if (!Object.keys(direction).length) {
          currencies.forEach(function (c) {
            direction[c] = riskOff ? (SAFE_HAVEN.indexOf(c) >= 0 ? 1 : -1) : net;
          });
        }
      }
      // سوژهٔ دارایی (طلا/نفت) بدون الگوی جفت → جهت فقط برای همان دارایی
      if (!pairFired && ASSET_CODES.indexOf(subject) >= 0) {
        var filtered = {};
        Object.keys(direction).forEach(function (c) {
          if (ASSET_CODES.indexOf(c) >= 0) filtered[c] = direction[c];
        });
        direction = filtered;
      }
    }

    // قاعدهٔ دامنه‌ای: مداخلهٔ ارزی ژاپن همیشه به نفع ین است
    if (JPY_INTERVENTION_RE.test(wideLow) && currencies.indexOf('JPY') >= 0) {
      direction['JPY'] = 1;
      if ('USD' in direction) direction['USD'] = -1;
    }

    var score = 1;
    score += Math.abs(pa) >= 2 ? 2 : (pa !== 0 ? 1 : 0);
    if (ma) score += 1;
    if (riskOff) score += 1;
    if (breaking) score += 1;
    if (currencies.length >= 2 && net !== 0) score += 1;
    if (roundup) score = Math.min(score, 2);
    return { score: Math.min(score, 6), direction: direction, keywords: kws, breaking: breaking, roundup: roundup };
  };

  // ── پارس فید (RSS 2.0 و Atom — بدون DOMParser) ───────────────
  var TAG_RE = /<[^>]+>/g;
  var WS_RE = /\s+/g;
  var PUNCT_RE = /[^\w\s%$.,/-]/g;

  var ENTITIES = [
    ['&amp;', '&'], ['&quot;', '"'], ['&#39;', "'"], ['&apos;', "'"], ['&nbsp;', ' '],
    ['&rsquo;', '’'], ['&lsquo;', '‘'], ['&ldquo;', '“'], ['&rdquo;', '”'],
    ['&#8217;', '’'], ['&#8220;', '“'], ['&#8221;', '”'], ['&#8211;', '–'],
    ['&#8212;', '—'], ['&lt;', '<'], ['&gt;', '>']
  ];

  O.decodeEntities = function (s) {
    s = String(s == null ? '' : s);
    ENTITIES.forEach(function (e) { s = s.split(e[0]).join(e[1]); });
    s = s.replace(/&#x([0-9a-f]+);/gi, function (_, h) { return String.fromCodePoint(parseInt(h, 16)); });
    s = s.replace(/&#(\d+);/g, function (_, d) { return String.fromCodePoint(+d); });
    return s;
  };

  O.stripHtml = function (s) {
    s = String(s == null ? '' : s).replace(TAG_RE, ' ');
    s = O.decodeEntities(s);
    return s.replace(WS_RE, ' ').trim();
  };

  function inner(block, tag) {
    var re = new RegExp('<' + tag + '(?:\\s[^>]*)?>([\\s\\S]*?)</' + tag + '>', 'i');
    var m = block.match(re);
    if (!m) return null;
    var v = m[1];
    var cd = v.match(/^\s*<!\[CDATA\[([\s\S]*?)\]\]>\s*$/);
    return cd ? cd[1] : v;
  }

  function parseDate(s) {
    if (!s) return null;
    s = String(s).trim();
    var t = Date.parse(s);
    if (!isNaN(t)) return t;
    return null;
  }

  O.parseFeedXml = function (xml) {
    var out = [];
    var blocks = xml.match(/<item[\s>][\s\S]*?<\/item>/gi) || [];
    var atom = false;
    if (!blocks.length) {
      blocks = xml.match(/<entry[\s>][\s\S]*?<\/entry>/gi) || [];
      atom = blocks.length > 0;
    }
    blocks.forEach(function (blk) {
      var titleRaw = inner(blk, 'title') || '';
      var link = '';
      var lm = blk.match(/<link[^>]*href=["']([^"']+)["'][^>]*\/?>/i);   // Atom
      if (atom && lm) link = lm[1];
      else {
        var lt = inner(blk, 'link');
        link = lt ? O.stripHtml(lt) : '';
      }
      var desc = inner(blk, 'description') || inner(blk, 'summary') || inner(blk, 'content:encoded') || inner(blk, 'content') || '';
      var pub = parseDate(inner(blk, 'pubDate')) || parseDate(inner(blk, 'dc:date')) ||
        parseDate(inner(blk, 'published')) || parseDate(inner(blk, 'updated'));
      var src = null;
      var sm = blk.match(/<source[^>]*>([\s\S]*?)<\/source>/i);
      if (sm) src = O.stripHtml(sm[1]);
      out.push({ title: titleRaw, link: link, description: desc, published: pub, source: src });
    });
    return out;
  };

  O.cleanTitle = function (title) {
    var t = O.stripHtml(title);
    var seps = [' - ', ' | ', ' – '];
    for (var i = 0; i < seps.length; i++) {
      var sep = seps[i];
      var idx = t.lastIndexOf(sep);
      if (idx >= 0) {
        var head = t.slice(0, idx), tail = t.slice(idx + sep.length);
        if (head && tail.length <= 32 && !tail.endsWith('.')) { t = head.trim(); break; }
      }
    }
    return t;
  };

  O.dedupeKey = function (title) {
    var norm = title.toLowerCase().replace(PUNCT_RE, '');
    norm = norm.replace(WS_RE, ' ').trim();
    norm = norm.replace(/\s*[-–|]\s*[a-z ]{3,30}$/, '');
    return O.md5(norm).slice(0, 16);
  };

  // ورودی‌های خام فید → NewsItem (معادل parse_entries پایتون)
  O.parseEntries = function (entries, feedName, weight, nowMs, maxAgeHours, minScore) {
    var cutoff = nowMs - maxAgeHours * 3600e3;
    var out = [];
    (entries || []).forEach(function (e) {
      var rawTitle = String(e.title || '');
      if (!rawTitle.trim()) return;
      var src = (e.source && String(e.source).trim()) || feedName;
      var title = O.cleanTitle(rawTitle);
      // فیدها description را HTML-escape می‌کنند (مثل Google News)؛
      // feedparser اول unescape می‌کند و بعد _strip_html تگ‌ها را می‌زد —
      // همان دو مرحله اینجا بازتولید می‌شود.
      var summary = O.stripHtml(O.decodeEntities(e.description || ''));
      var pub = e.published;
      if (pub != null && pub < cutoff) return;                     // خبر کهنه
      if (pub != null && pub > nowMs + 30 * 60000) pub = nowMs;    // ساعت آینده = خطای فید
      var r = O.scoreText(title, title + '. ' + summary.slice(0, 300));
      var score = Math.min(6, r.score + (weight >= 2 && r.score >= 3 ? 1 : 0));
      if (score < minScore) return;
      out.push({
        title: title, link: String(e.link || ''), source: src, published: pub,
        score: score, direction: r.direction, keywords: r.keywords,
        breaking: r.breaking, roundup: r.roundup,
        summary: summary.slice(0, 200),
        age_minutes: pub != null ? (nowMs - pub) / 60000 : 0
      });
    });
    return out;
  };

  // ── ابزار NewsItem ───────────────────────────────────────────
  O.newsDirectionFa = function (it) {
    var entries = Object.keys(it.direction).map(function (c) { return [c, it.direction[c]]; });
    entries.sort(function (a, b) { return (Math.abs(b[1]) - Math.abs(a[1])) || (a[0] < b[0] ? -1 : 1); });
    return entries.map(function (x) {
      return (O.NEWS_CURRENCY_FA[x[0]] || x[0]) + ' ' + (x[1] > 0 ? '↑' : '↓');
    }).join(' ، ');
  };

  O.headlineFa = function (it, width) {
    width = width || 78;
    var t = it.title.length <= width ? it.title : it.title.slice(0, width - 1) + '…';
    return (it.breaking ? '🚨 ' : '') + t;
  };

  // ── سنجش اخبار برای داور (پورت news_supports) ────────────────
  O.newsSupports = function (snap, base, quote, bias, minScore) {
    var want = String(bias).toLowerCase().startsWith('b') ? 1 : -1;
    var vote = { bias: bias, votes: 0, support: [], contradict: [], verdict: 0 };
    var seenSig = {};
    var raw = 0;

    var ranked = snap.items.slice().sort(function (a, b) { return b.score - a.score; });
    ranked.forEach(function (it) {
      if (it.roundup || it.score < minScore || !Object.keys(it.direction).length) return;
      var sig = Object.keys(it.direction).sort()
        .map(function (k) { return k + ':' + it.direction[k]; }).join(',');
      if (seenSig[sig]) return;                 // روایت تکراری — یک بار بیشتر نه
      seenSig[sig] = true;

      var db = it.direction[base] || 0, dq = it.direction[quote] || 0;
      var pairDir;
      if (db && dq) {
        if (db === dq) return;                  // هر دو یک‌جهت → برای «جفت» بی‌معنی
        pairDir = db;
      } else if (db) pairDir = db;
      else if (dq) pairDir = -dq;
      else return;

      var w = it.score >= 5 ? 1.0 : 0.6;
      raw += want * pairDir * w;
      (want * pairDir > 0 ? vote.support : vote.contradict).push(it);
    });

    vote.votes = Math.round(Math.max(-2, Math.min(2, raw)) * 100) / 100;
    vote.verdict = vote.votes >= 1 ? 1 : (vote.votes <= -1 ? -1 : 0);
    vote.has_evidence = !!(vote.support.length || vote.contradict.length);
    return vote;
  };

  // خبرهای فوریِ مرتبط با یک جفت‌ارز (برای وتو)
  O.breakingNewsFor = function (snap, base, quote, minScore) {
    if (!snap || !snap.items) return [];
    return snap.items.filter(function (it) {
      if (!it.breaking || it.score < minScore) return false;
      return base in it.direction || quote in it.direction || 'XAU' in it.direction;
    });
  };
})(typeof ODIN !== 'undefined' ? ODIN : (globalThis.ODIN = {}));
