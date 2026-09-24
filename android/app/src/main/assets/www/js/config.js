/* پیکربندی — پورت config.yaml (منبع حقیقت همان فایل در نسخهٔ دسکتاپ است).
 * بخش‌هایی که در موبایل معنا ندارند (تلگرام، حلقهٔ خودکار) حذف شده‌اند:
 * این اپ معاملهٔ خودکار نمی‌کند. «تازه‌سازی خودکار» اندروید (اختیاری) فقط
 * تحلیل را تکرار می‌کند، آن هم فقط وقتی اپ باز و بازار فعال است. */
(function (O) {
  'use strict';

  O.CONFIG = {
    symbols: [
      { name: 'EURUSD', fa: 'یورو به دلار آمریکا', yahoo: 'EURUSD=X', tv: { screener: 'forex', exchange: 'FX', symbol: 'EURUSD' }, base: 'EUR', quote: 'USD', pip: 0.0001 },
      { name: 'GBPUSD', fa: 'پوند به دلار آمریکا', yahoo: 'GBPUSD=X', tv: { screener: 'forex', exchange: 'FX', symbol: 'GBPUSD' }, base: 'GBP', quote: 'USD', pip: 0.0001 },
      { name: 'USDJPY', fa: 'دلار آمریکا به ین ژاپن', yahoo: 'USDJPY=X', tv: { screener: 'forex', exchange: 'FX', symbol: 'USDJPY' }, base: 'USD', quote: 'JPY', pip: 0.01 },
      { name: 'USDCAD', fa: 'دلار آمریکا به دلار کانادا', yahoo: 'USDCAD=X', tv: { screener: 'forex', exchange: 'FX', symbol: 'USDCAD' }, base: 'USD', quote: 'CAD', pip: 0.0001 },
      { name: 'AUDUSD', fa: 'دلار استرالیا به دلار آمریکا', yahoo: 'AUDUSD=X', tv: { screener: 'forex', exchange: 'FX', symbol: 'AUDUSD' }, base: 'AUD', quote: 'USD', pip: 0.0001 },
      { name: 'USDCHF', fa: 'دلار آمریکا به فرانک سوئیس', yahoo: 'USDCHF=X', tv: { screener: 'forex', exchange: 'FX', symbol: 'USDCHF' }, base: 'USD', quote: 'CHF', pip: 0.0001 },
      // طلا: Yahoo اسپات ندارد و فیوچرز GC=F را می‌دهد — اختلاف جزئی طبیعی است
      { name: 'XAUUSD', fa: 'طلا به دلار آمریکا (انس)', yahoo: 'GC=F', tv: { screener: 'cfd', exchange: 'OANDA', symbol: 'XAUUSD' }, base: 'XAU', quote: 'USD', pip: 1.0 }
    ],

    analysis: {
      ema_fast: 50, ema_slow: 200,
      adx_period: 14, adx_min_trend: 20, adx_strong: 25,
      rsi_period: 14, atr_period: 14,
      swing_window: 5, strength_lookback_h1: 24
    },

    history: {
      yahoo_h1_days: 60, yahoo_m15_days: 5,
      drop_forming_candle: true
    },

    tradingview: { enabled: true, timeframe: '4h' },

    fundamental: {
      enabled: true,
      source_url: 'https://nfs.faireconomy.media/ff_calendar_thisweek.json',
      cache_ttl_minutes: 30,
      horizon_hours: 48,
      veto_minutes_before: 30
    },

    news: {
      enabled: true,
      max_age_hours: 30,
      min_score: 2,
      max_items_per_feed: 12,
      max_total: 18,
      feeds: [
        { name: 'ForexLive', url: 'https://www.forexlive.com/feed', weight: 2 },
        { name: 'Investing.com — فارکس', url: 'https://www.investing.com/rss/news_25.rss', weight: 1 },
        { name: 'Investing.com — اقتصاد', url: 'https://www.investing.com/rss/news_1.rss', weight: 1 },
        { name: 'Investing.com — طلا', url: 'https://www.investing.com/rss/news_11.rss', weight: 1 },
        { name: 'FXStreet (از مسیر Google News)', weight: 2, url: 'https://news.google.com/rss/search?when=1d&q=site:fxstreet.com&hl=en-US&gl=US&ceid=US:en' }
      ]
    },

    briefing: { enabled: true, horizon_hours: 24 },

    // مقادیر پیش‌فرض داور (با DEFAULTS در src/judge/scoring.py یکی است)
    judge: {
      enabled: true,
      min_score: 7,
      max_signals_per_cycle: 3,
      resend_cooldown_minutes: 180,
      resend_score_gain: 2,
      veto: {
        weekend: true, high_impact_event: true, timeframe_conflict: true,
        range_market: true, volatility_spike: true, breaking_news: true
      },
      fundamental: { clean_high_hours: 6, clean_med_hours: 2 },
      news: { min_score: 4, breaking_min_score: 5 },
      volatility: { spike_multiplier: 2.0, lookback_bars: 100 },
      level: { close_atr: 0.5, near_atr: 1.5 },
      risk: {
        sl_atr_multiplier: 1.5, max_sl_atr: 3.0, min_sl_atr: 0.6,
        level_buffer_atr: 0.3, reward_risk: 2.0, max_risk_percent: 1.0
      }
    },

    journal: { enabled: true, expiry_hours: 48, conservative_both_touch: true },

    ui: { user_name: 'سوشیان', animations: true },

    // فراخوانی‌های سیستم پلاگین (فاز ۷) — پیش‌فرض خالی: فعال/غیرفعالِ
    // پلاگین‌ها با همان کلیدهای فیچریِ بالا (news.enabled و ...) کار می‌کند.
    // override صریحِ هر پلاگین: plugins['<id>'] = { enabled: false }
    // (اولویت: override ← کلید فیچری ← پیش‌فرض مانیفست ← true).
    // فهرست idها و توضیح کامل در config.yaml دسکتاپ (منبع حقیقت).
    plugins: {}
  };

  // ادغام عمیق تنظیمات کاربر (از حافظهٔ گوشی) با پیش‌فرض‌ها
  O.deepFill = function (base, over) {
    var out = {};
    var k;
    for (k in base) out[k] = base[k];
    for (k in (over || {})) {
      var v = over[k];
      if (v && typeof v === 'object' && !Array.isArray(v) && out[k] && typeof out[k] === 'object' && !Array.isArray(out[k])) {
        out[k] = O.deepFill(out[k], v);
      } else {
        out[k] = v;
      }
    }
    return out;
  };
})(typeof ODIN !== 'undefined' ? ODIN : (globalThis.ODIN = {}));
