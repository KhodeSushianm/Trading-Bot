/* موتور فاندامنتال — تقویم اقتصادی (پورت src/fundamental/calendar.py)
 *
 * منبع: فید JSON هفتگی ForexFactory (رایگان، بدون کلید).
 * ⚠️ همان نکتهٔ صادقانه: فید فقط «همین هفته» را پوشش می‌دهد.
 */
(function (O) {
  'use strict';

  O.CAL_SOURCE_NAME = 'ForexFactory';
  O.IMPACT_FA = { HIGH: '🔴 پراثر', MEDIUM: '🟠 اثر متوسط', LOW: '🟢 کم‌اثر' };
  O.IMPACT_EMOJI = { HIGH: '🔴', MEDIUM: '🟠', LOW: '🟢' };

  O.CURRENCY_FA = {
    USD: ['آمریکا', 'دلار آمریکا'], EUR: ['منطقه یورو', 'یورو'], GBP: ['بریتانیا', 'پوند'],
    JPY: ['ژاپن', 'ین ژاپن'], CHF: ['سوئیس', 'فرانک سوئیس'], CAD: ['کانادا', 'دلار کانادا'],
    AUD: ['استرالیا', 'دلار استرالیا'], NZD: ['نیوزیلند', 'دلار نیوزیلند'], CNY: ['چین', 'یوان چین'],
    SEK: ['سوئد', 'کرون سوئد'], NOK: ['نروژ', 'کرون نروژ'], MXN: ['مکزیک', 'پزوی مکزیک'],
    TRY: ['ترکیه', 'لیر ترکیه'], ZAR: ['آفریقای جنوبی', 'رند'], KRW: ['کره جنوبی', 'وون'],
    SGD: ['سنگاپور', 'دلار سنگاپور'], INR: ['هند', 'روپیه هند'], BRL: ['برزیل', 'رئال برزیل'],
    All: ['جهانی', 'بازار جهانی']
  };

  // عنوان انگلیسی → فارسی (رویدادهای پرتکرار؛ بقیه با قاعده ترجمه می‌شوند)
  O.TITLE_FA = {
    'CPI m/m': 'تورم ماهانه (CPI)', 'CPI y/y': 'تورم سالانه (CPI)',
    'Core CPI m/m': 'تورم هسته ماهانه', 'Core CPI y/y': 'تورم هسته سالانه',
    'Final CPI y/y': 'تورم سالانه (نهایی)', 'Final Core CPI y/y': 'تورم هسته سالانه (نهایی)',
    'Common CPI y/y': 'تورم عمومی سالانه', 'Median CPI y/y': 'تورم میانه سالانه',
    'Trimmed CPI y/y': 'تورم تعدیل‌شده سالانه', 'National Core CPI y/y': 'تورم هسته ملی سالانه',
    'French Final CPI m/m': 'تورم ماهانه فرانسه (نهایی)',
    'German PPI m/m': 'تورم تولیدکننده آلمان ماهانه',
    'German WPI m/m': 'تورم عمده‌فروشی آلمان ماهانه',
    'PPI Input m/m': 'تورم نهاده‌های تولید ماهانه',
    'IPPI m/m': 'شاخص قیمت محصولات صنعتی ماهانه',
    'HPI y/y': 'شاخص قیمت مسکن سالانه', 'NHPI m/m': 'شاخص قیمت مسکن جدید ماهانه',
    'New Home Prices m/m': 'قیمت مسکن نوساز ماهانه', 'Import Prices m/m': 'قیمت واردات ماهانه',
    'Federal Funds Rate': 'نرخ بهره فدرال رزرو',
    'FOMC Statement': 'بیانیه کمیته بازار آزاد فدرال (FOMC)',
    'FOMC Press Conference': 'کنفرانس مطبوعاتی فدرال رزرو',
    'FOMC Economic Projections': 'پیش‌بینی‌های اقتصادی فدرال رزرو',
    'Official Bank Rate': 'نرخ بهره رسمی بانک مرکزی',
    'MPC Official Bank Rate Votes': 'رأی‌گیری کمیته سیاست پولی بر سر نرخ بهره',
    'Monetary Policy Summary': 'خلاصه سیاست پولی',
    'Monetary Policy Statement': 'بیانیه سیاست پولی',
    'BOJ Policy Rate': 'نرخ بهره بانک مرکزی ژاپن',
    'BOJ Press Conference': 'کنفرانس مطبوعاتی بانک مرکزی ژاپن',
    'ECB President Lagarde Speaks': 'سخنرانی لاگارد (رئیس بانک مرکزی اروپا)',
    'German Buba President Nagel Speaks': 'سخنرانی ناگل (رئیس بوندس‌بانک آلمان)',
    'FOMC Member Bowman Speaks': 'سخنرانی بومن (عضو فدرال رزرو)',
    'FOMC Member Schmid Speaks': 'سخنرانی اشمید (عضو فدرال رزرو)',
    'BOC Summary of Deliberations': 'خلاصه مذاکرات بانک مرکزی کانادا',
    'Claimant Count Change': 'تغییر شمار متقاضیان بیمه بیکاری',
    'ADP Weekly Employment Change': 'اشتغال هفتگی ADP',
    'Average Earnings Index 3m/y': 'شاخص میانگین درآمد (۳ ماهه سالانه)',
    'Unemployment Rate': 'نرخ بیکاری', 'GDP q/q': 'رشد اقتصادی فصلی (GDP)',
    'Industrial Production m/m': 'تولید صنعتی ماهانه',
    'Industrial Production y/y': 'تولید صنعتی سالانه',
    'Core Retail Sales m/m': 'خرده‌فروشی هسته ماهانه',
    'Retail Sales m/m': 'خرده‌فروشی ماهانه',
    'Manufacturing Sales m/m': 'فروش بخش تولید ماهانه',
    'Business Inventories m/m': 'موجودی انبار بنگاه‌ها ماهانه',
    'Building Permits': 'پروانه‌های ساخت', 'Building Permits m/m': 'پروانه‌های ساخت ماهانه',
    'Housing Starts': 'شروع ساخت مسکن', 'NAHB Housing Market Index': 'شاخص بازار مسکن NAHB',
    'Empire State Manufacturing Index': 'شاخص تولید امپایر استیت نیویورک',
    'German ZEW Economic Sentiment': 'سنتیمنت اقتصادی ZEW آلمان',
    'Capacity Utilization Rate': 'نرخ بهره‌برداری از ظرفیت تولید',
    'CB Leading Index m/m': 'شاخص پیشرو کنفرانس بورد ماهانه',
    'MI Leading Index m/m': 'شاخص پیشرو مؤسسه ملبورن ماهانه',
    'Current Account': 'تراز جاری', 'Italian Trade Balance': 'تراز تجاری ایتالیا',
    'Core Machinery Orders m/m': 'سفارش ماشین‌آلات هسته ماهانه',
    'Foreign Securities Purchases': 'خرید اوراق بهادار توسط خارجی‌ها',
    'Foreign Direct Investment ytd/y': 'سرمایه‌گذاری مستقیم خارجی (از ابتدای سال)',
    'Fixed Asset Investment ytd/y': 'سرمایه‌گذاری در دارایی ثابت (از ابتدای سال)',
    'New Loans': 'وام‌های جدید بانکی', 'M2 Money Supply y/y': 'نقدینگی M2 سالانه',
    'NBS Press Conference': 'کنفرانس مطبوعاتی اداره آمار چین',
    'Crude Oil Inventories': 'موجودی نفت خام', 'Natural Gas Storage': 'موجودی گاز طبیعی',
    'API Weekly Statistical Bulletin': 'گزارش هفتگی مؤسسه نفت آمریکا',
    'GDT Price Index': 'شاخص قیمت لبنیات GDT', 'FPI m/m': 'شاخص قیمت مواد غذایی ماهانه',
    'BusinessNZ Services Index': 'شاخص خدمات BusinessNZ',
    'German 30-y Bond Auction': 'حراج اوراق ۳۰ ساله آلمان',
    'ECOFIN Meetings': 'جلسات وزیران اقتصاد و دارایی اتحادیه اروپا',
    'Eurogroup Meetings': 'جلسات گروه یورو', 'BRICS Summit': 'نشست سران بریکس'
  };

  var CATEGORIES = [
    ['نرخ بهره و بانک مرکزی', ['Rate', 'FOMC', 'MPC', 'BOJ', 'ECB', 'Monetary Policy', 'Speaks', 'Press Conference', 'Statement', 'Minutes', 'Votes', 'Projections', 'Bond Auction', 'Deliberations']],
    ['تورم و قیمت‌ها', ['CPI', 'PPI', 'WPI', 'HPI', 'NHPI', 'IPPI', 'Price', 'Inflation', 'Import Prices']],
    ['اشتغال و بازار کار', ['Employment', 'Payroll', 'Unemployment', 'Jobless', 'Claimant', 'Earnings', 'Labour', 'Labor', 'Wage', 'NFP']],
    ['رشد و فعالیت اقتصادی', ['GDP', 'PMI', 'Industrial Production', 'Retail Sales', 'Manufacturing', 'Services', 'Sentiment', 'ZEW', 'IFO', 'Leading Index', 'Capacity', 'Business', 'Trade', 'Orders', 'Inventories', 'Loans', 'Money Supply', 'Investment', 'Account']],
    ['مسکن و ساخت‌وساز', ['Housing', 'Home', 'Building Permits', 'NAHB', 'Construction']],
    ['انرژی و کالا', ['Crude Oil', 'Natural Gas', 'GDT', 'Gold', 'FPI', 'Commodity']]
  ];

  var LOWER_IS_BETTER = ['Unemployment', 'Claimant Count', 'Jobless', 'Initial Claims', 'Continuing Claims', 'Budget Balance', 'Trade Deficit'];
  var SUFFIX_FA = [[' ytd/y', ' (از ابتدای سال)'], [' 3m/y', ' (۳ ماههٔ سالانه)'], [' m/m', ' (ماه‌به‌ماه)'], [' y/y', ' (سال‌به‌سال)'], [' q/q', ' (فصل‌به‌فصل)'], [' w/w', ' (هفته‌به‌هفته)']];
  var POLARITY_POS = ['CPI', 'PPI', 'WPI', 'HPI', 'NHPI', 'IPPI', 'GDP', 'PMI', 'Retail Sales', 'Industrial Production', 'Employment', 'Payroll', 'Earnings', 'Orders', 'Sentiment', 'ZEW', 'IFO', 'Rate', 'Leading Index', 'Capacity', 'Housing Starts', 'Building Permits', 'Manufacturing', 'Services'];

  function clean(s) { return String(s == null ? '' : s).trim(); }

  O.translateTitle = function (title) {
    var t = clean(title);
    if (O.TITLE_FA[t]) return O.TITLE_FA[t];
    for (var i = 0; i < SUFFIX_FA.length; i++) {
      var suf = SUFFIX_FA[i][0];
      if (t.endsWith(suf)) {
        var base = t.slice(0, -suf.length);
        return O.TITLE_FA[base] ? O.TITLE_FA[base] + SUFFIX_FA[i][1] : base + SUFFIX_FA[i][1];
      }
    }
    return t;
  };

  O.categorize = function (title) {
    var low = String(title).toLowerCase();
    for (var i = 0; i < CATEGORIES.length; i++) {
      var keys = CATEGORIES[i][1];
      for (var j = 0; j < keys.length; j++) {
        if (low.indexOf(keys[j].toLowerCase()) >= 0) return CATEGORIES[i][0];
      }
    }
    return 'سایر';
  };

  O.polarity = function (title) {
    var low = String(title).toLowerCase();
    for (var i = 0; i < LOWER_IS_BETTER.length; i++) {
      if (low.indexOf(LOWER_IS_BETTER[i].toLowerCase()) >= 0) return -1;
    }
    for (i = 0; i < POLARITY_POS.length; i++) {
      if (title.indexOf(POLARITY_POS[i]) >= 0) return 1;
    }
    return 0;
  };

  // تاریخ ISO (مثل 2026-09-20T19:00:00-04:00) → millis UTC
  O.parseWhen = function (ds) {
    var s = clean(ds);
    if (!s) return null;
    if (s.endsWith('Z')) s = s.slice(0, -1) + '+00:00';
    var d = new Date(s);
    if (isNaN(d.getTime())) {
      // بدون منطقهٔ زمانی → UTC فرض شود (مثل datetime.fromisoformat + replace)
      if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(clean(ds))) d = new Date(clean(ds) + 'Z');
      if (isNaN(d.getTime())) return null;
    }
    return d.getTime();
  };

  // تبدیل JSON خام ForexFactory به رویدادهای نرمال‌شده
  O.parseEvents = function (raw) {
    var out = [];
    (raw || []).forEach(function (e) {
      var when = O.parseWhen(e.date);
      if (when === null) return;
      var title = clean(e.title);
      if (!title) return;
      out.push({
        when: when,
        country: clean(e.country) || 'All',
        title: title,
        title_fa: O.translateTitle(title),
        impact: (clean(e.impact).toUpperCase() || 'LOW'),
        forecast: clean(e.forecast),
        previous: clean(e.previous),
        category: O.categorize(title),
        polarity: O.polarity(title),
        source: O.CAL_SOURCE_NAME
      });
    });
    out.sort(function (a, b) { return a.when - b.when; });
    return out;
  };

  // ── توابع روی رویداد ────────────────────────────────────────
  O.evCountryFa = function (e) { return (O.CURRENCY_FA[e.country] || [e.country, e.country])[0]; };
  O.evCurrencyFa = function (e) { return (O.CURRENCY_FA[e.country] || [e.country, e.country])[1]; };
  O.evAffects = function (e, base, quote) { return e.country === base || e.country === quote || e.country === 'All'; };
  O.evMinutesFrom = function (e, nowMs) { return (e.when - nowMs) / 60000; };
  O.evKey = function (e) {
    var d = new Date(e.when);
    var p = function (n) { return String(n).padStart(2, '0'); };
    return e.country + '|' + d.getUTCFullYear() + p(d.getUTCMonth() + 1) + p(d.getUTCDate()) +
      'T' + p(d.getUTCHours()) + p(d.getUTCMinutes()) + '|' + e.title;
  };

  O.evExplain = function (e, symbolsCfg, nowMs) {
    var f = e.forecast.trim(), p = e.previous.trim();
    var nums = (f || p) && e.polarity !== 0;
    var head = (O.IMPACT_EMOJI[e.impact] || '⚪') + ' ' + O.hhmm(new Date(e.when)) +
      ' — ' + O.evCountryFa(e) + ': ' + e.title_fa;
    if (!nums) {
      if (e.polarity === 0 && e.impact === 'HIGH') {
        return head + '\n      🔎 رویداد پراثر ولی بدون عدد پیش‌بینی (مثل سخنرانی/بیانیه) — بازار به لحن و محتوای آن واکنش می‌دهد؛ نزدیک این ساعت معامله نکن';
      }
      var bits = [];
      if (f) bits.push('پیش‌بینی ' + f);
      if (p) bits.push('قبلی ' + p);
      return bits.length ? head + '\n      🔎 ' + bits.join(' | ') : head;
    }
    var better = e.polarity > 0 ? 'بالاتر' : 'پایین‌تر';
    var worse = e.polarity > 0 ? 'پایین‌تر' : 'بالاتر';
    var note = e.polarity > 0 ? '' : ' (برای این شاخص، عدد کمتر = خبر بهتر)';
    var pairs = symbolsCfg.filter(function (s) { return s.base === e.country || s.quote === e.country; });
    var line = head + '\n      🔎 پیش‌بینی ' + (f || '—') + ' | قبلی ' + (p || '—') +
      ' → اگر عدد ' + better + ' از انتظار باشد ' + O.evCurrencyFa(e) + ' تقویت می‌شود' +
      ' و اگر ' + worse + ' باشد ضعیف' + note;
    if (pairs.length) {
      var pos = pairs.filter(function (s) { return s.base === e.country; }).map(function (s) { return s.name; });
      var neg = pairs.filter(function (s) { return s.quote === e.country; }).map(function (s) { return s.name; });
      var tips = [];
      if (pos.length) tips.push(pos.join('، ') + ' ↑ صعودی');
      if (neg.length) tips.push(neg.join('، ') + ' ↓ نزولی');
      line += '\n      💡 در صورت تقویت ' + O.evCurrencyFa(e) + ': ' + tips.join(' | ');
    }
    return line;
  };

  // ── پرس‌وجو ─────────────────────────────────────────────────
  O.upcomingEvents = function (events, nowMs, hours, impacts, countries, limit) {
    var end = nowMs + hours * 3600e3;
    var cset = countries ? countries.map(function (c) { return c.toUpperCase(); }) : null;
    var out = events.filter(function (e) {
      return nowMs <= e.when && e.when <= end &&
        impacts.indexOf(e.impact) >= 0 &&
        (cset === null || cset.indexOf(e.country.toUpperCase()) >= 0 || e.country === 'All');
    });
    return limit ? out.slice(0, limit) : out;
  };

  // دروازه وتو: رویداد پراثر نزدیک (۱۵ دقیقه قبل تا N دقیقه بعد)
  O.vetoForSymbol = function (events, base, quote, nowMs, minutes) {
    var winStart = nowMs - 15 * 60000;
    var winEnd = nowMs + Math.max(0, minutes) * 60000;
    return events.filter(function (e) {
      return e.impact === 'HIGH' && winStart <= e.when && e.when <= winEnd &&
        (e.country === base || e.country === quote || e.country === 'All');
    });
  };

  O.nextHighImpact = function (events, base, quote, nowMs) {
    for (var i = 0; i < events.length; i++) {
      var e = events[i];
      if (e.when < nowMs || e.impact !== 'HIGH') continue;
      if (base && !O.evAffects(e, base, quote || '')) continue;
      return e;
    }
    return null;
  };
})(typeof ODIN !== 'undefined' ? ODIN : (globalThis.ODIN = {}));
