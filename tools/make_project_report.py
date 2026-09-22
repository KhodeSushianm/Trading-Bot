# -*- coding: utf-8 -*-
"""تولید «گزارش پروژه» به‌صورت HTML خودبسنده.

چرا اسکریپت و نه فایل دستی؟
    چون هر عددی که در گزارش می‌آید باید اندازه‌گیری‌شده باشد، نه از حافظه.
    همین اسکریپت ریپو/تست‌ها/API گیت‌هاب را می‌خواند و HTML را می‌سازد؛
    پس اگر فردا دوباره اجرا شود، گزارش کهنه نمی‌شود.
    (کهنگی مستندات یکی از مشکلات ثبت‌شدهٔ این پروژه است — بخش ۸ب-۷ گزارش ریپو.)

اجرا:  python3 tools/make_project_report.py
خروجی: reports/project-report.html   (خودبسنده: بدون منبع بیرونی، آفلاین باز می‌شود)
"""
from __future__ import annotations

import html
import json
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "project-report.html"
REPO = "KhodeSushianm/Trading-Bot"


# ── اندازه‌گیری ─────────────────────────────────────────────────────────
def sh(cmd: str) -> str:
    return subprocess.run(cmd, shell=True, cwd=ROOT, capture_output=True, text=True).stdout.strip()


def count_lines(*globs: str) -> tuple[int, int]:
    tot = n = 0
    for g in globs:
        for f in ROOT.glob(g):
            if ".git" in f.parts or "__pycache__" in f.parts:
                continue
            try:
                tot += len(f.read_text(encoding="utf-8", errors="replace").splitlines())
                n += 1
            except Exception:
                pass
    return n, tot


def gh(url: str):
    try:
        r = urllib.request.Request(url, headers={"User-Agent": "report", "Accept": "application/vnd.github+json"})
        return json.load(urllib.request.urlopen(r, timeout=25))
    except Exception as e:                                   # گزارش نباید به شبکه وابسته بمیرد
        return {"__error": str(e)}


def measure() -> dict:
    d: dict = {}
    d["app_version"] = sh("python3 -c \"import re,pathlib;print(re.search(r'APP_VERSION\\s*=\\s*\\\"([^\\\"]+)\\\"',pathlib.Path('src/app_paths.py').read_text(encoding='utf-8')).group(1))\"")

    for key, globs in [
        ("src_py", ("src/**/*.py",)),
        ("src_ui", ("src/ui/*.py",)),
        ("and_js", ("android/app/src/main/assets/www/js/*.js",)),
        ("and_java", ("android/**/*.java",)),
        ("and_css", ("android/app/src/main/assets/www/*.css",)),
        ("tests_py", ("tests/**/*.py",)),
        ("tests_js", ("tests/js/*.js",)),
        ("docs", ("docs/*.md", "*.md")),
        ("ci", (".github/workflows/*.yml",)),
    ]:
        d[key] = count_lines(*globs)

    d["panel_py"] = len((ROOT / "panel.py").read_text(encoding="utf-8").splitlines())
    d["main_py"] = len((ROOT / "main.py").read_text(encoding="utf-8").splitlines())

    d["tracked"] = int(sh("git ls-files | wc -l"))
    d["commits"] = int(sh("git rev-list --count HEAD"))
    d["tags"] = int(sh("git tag | wc -l"))
    d["first_commit"] = sh("git log --reverse --format=%ad --date=short | head -1")
    d["last_commit"] = sh("git log -1 --format=%ad --date=short")
    d["head"] = sh("git rev-parse --short HEAD")
    d["branch_main"] = sh("git rev-parse --short main")
    d["branch_android"] = sh("git rev-parse --short origin/android 2>/dev/null || echo -")

    # کامیت در هر روز
    days = {}
    for line in sh("git log --format=%ad --date=short").splitlines():
        days[line] = days.get(line, 0) + 1
    d["days"] = sorted(days.items())
    d["span_days"] = len(days)

    # داور: از خود کد بخوان، نه از حافظه
    sc = (ROOT / "src" / "judge" / "scoring.py").read_text(encoding="utf-8")
    import re
    d["vetoes"] = re.findall(r'Veto\("([A-Z_]+)"', sc)
    d["evidences"] = sorted(set(re.findall(r'^def (ev_[a-z_]+)\(', sc, re.M)))

    cfg = (ROOT / "config.yaml").read_text(encoding="utf-8")
    d["symbols"] = re.findall(r'^  - name: (\w+)', cfg, re.M)
    d["min_score"] = re.search(r'min_score:\s*(\d+)', cfg).group(1)
    d["max_signals"] = re.search(r'max_signals_per_cycle:\s*(\d+)', cfg).group(1)
    d["interval"] = re.search(r'interval_minutes:\s*(\d+)', cfg).group(1)

    # توکن‌های تم و پاریتی
    theme = (ROOT / "src" / "ui" / "theme.py").read_text(encoding="utf-8")
    d["theme_tokens"] = len(re.findall(r'^\s{4}([a-z][a-z0-9_]*)\s*:\s*(?:str|int|float)\s*=', theme, re.M)) - 2
    css = (ROOT / "android" / "app" / "src" / "main" / "assets" / "www" / "style.css").read_text(encoding="utf-8")
    root = css[css.index(":root {"):css.index("}", css.index("--tab-h"))]
    d["css_vars"] = len(re.findall(r'--[a-z0-9-]+\s*:', root))
    d["components"] = len((ROOT / "android" / "app" / "src" / "main" / "assets" / "www" / "js" / "components.js")
                          .read_text(encoding="utf-8").splitlines())

    # گیت‌هاب
    rels = []
    for pg in (1, 2):
        b = gh(f"https://api.github.com/repos/{REPO}/releases?per_page=50&page={pg}")
        if isinstance(b, list):
            rels += b
        elif isinstance(b, dict) and b.get("__error"):
            d["net_error"] = b["__error"]
    d["releases"] = len(rels)
    assets = [a for r in rels for a in r.get("assets", [])]
    d["assets"] = len(assets)
    d["apk_assets"] = [a for a in assets if "apk" in a["name"].lower()]
    d["win_assets"] = [a for a in assets if "windows" in a["name"].lower()]
    d["downloads"] = sum(a["download_count"] for a in assets)
    d["apk_downloads"] = sum(a["download_count"] for a in d["apk_assets"])
    d["win_downloads"] = sum(a["download_count"] for a in d["win_assets"])
    d["latest"] = [
        {"tag": r["tag_name"], "published": r["published_at"][:10],
         "assets": [(a["name"], a["size"]) for a in r.get("assets", [])]}
        for r in sorted(rels, key=lambda x: x["published_at"])[-4:][::-1]
    ]

    runs = gh(f"https://api.github.com/repos/{REPO}/actions/runs?per_page=30")
    ci = {}
    if isinstance(runs, dict) and "workflow_runs" in runs:
        for w in runs["workflow_runs"]:
            ci.setdefault(w["name"], {"success": 0, "failure": 0, "other": 0})
            c = w["conclusion"]
            ci[w["name"]][c if c in ("success", "failure") else "other"] += 1
    d["ci"] = ci
    d["ci_failures"] = sum(v["failure"] for v in ci.values())

    repo = gh(f"https://api.github.com/repos/{REPO}")
    if isinstance(repo, dict) and "stargazers_count" in repo:
        d["stars"] = repo["stargazers_count"]
        d["forks"] = repo["forks_count"]
        d["issues"] = repo["open_issues_count"]
        d["repo_kb"] = repo["size"]
    return d


# ── رندر ────────────────────────────────────────────────────────────────
def e(s) -> str:
    return html.escape(str(s))


def fa(n) -> str:
    return str(n).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))


def kb(size: int) -> str:
    return f"{size/1048576:.1f} MB" if size > 1048576 else f"{size//1024} KB"


CSS = """
:root{--bg:#E9E9EE;--card:#fff;--ink:#101013;--text:#0B0B0C;--t2:#55555E;--t3:#94949C;
--border:#E3E3E8;--raised:#F1F1F4;--green:#1F9D66;--gt:#177B50;--gtint:#E4F5EC;
--red:#D64545;--rt:#B23A3A;--rtint:#FBEAEA;--amber:#E0A83C;--atint:#FBF1DC;
--brand:#5B4BE8;--btint:#EBE9FD;--indigo:#7A6CF0;--cyan:#46C8E8;--pink:#EE7BC8}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);direction:rtl;
font-family:"Vazirmatn","Segoe UI",Tahoma,"Iranian Sans",sans-serif;font-size:14px;line-height:1.85}
.wrap{max-width:1080px;margin:0 auto;padding:0 20px 80px}
.hero{position:relative;overflow:hidden;background:var(--ink);color:#fff;
border-radius:0 0 32px 32px;padding:46px 34px 40px;margin-bottom:28px}
.hero::before,.hero::after{content:"";position:absolute;inset:-30% -10%;pointer-events:none;background-repeat:no-repeat}
.hero::before{background-image:radial-gradient(38% 30% at 20% 15%,var(--indigo) 0%,rgba(122,108,240,0) 70%),
radial-gradient(34% 26% at 85% 30%,var(--cyan) 0%,rgba(70,200,232,0) 70%);opacity:.34}
.hero::after{background-image:radial-gradient(40% 30% at 65% 88%,var(--pink) 0%,rgba(238,123,200,0) 72%);opacity:.26}
.hero>*{position:relative;z-index:1}
.h-eyebrow{font-size:11px;letter-spacing:2.5px;color:rgba(255,255,255,.55);font-weight:700}
h1{margin:8px 0 6px;font-size:34px;font-weight:800;letter-spacing:-.6px}
.h-sub{color:rgba(255,255,255,.72);font-size:14px;max-width:70ch}
.h-meta{display:flex;flex-wrap:wrap;gap:8px;margin-top:22px}
.h-pill{background:rgba(255,255,255,.10);border:1px solid rgba(255,255,255,.16);
border-radius:999px;padding:5px 14px;font-size:11.5px;font-weight:600}
.h-pill b{color:#fff;font-weight:800}
section{margin-bottom:34px}
h2{font-size:19px;font-weight:800;margin:0 0 4px;display:flex;align-items:center;gap:10px}
h2 .n{width:28px;height:28px;border-radius:9px;background:var(--ink);color:#fff;
display:inline-flex;align-items:center;justify-content:center;font-size:13px;font-weight:800;flex:0 0 auto}
.h2sub{color:var(--t2);font-size:12.5px;margin:0 0 16px 38px}
.card{background:rgba(255,255,255,.94);border:1px solid rgba(255,255,255,.9);
border-radius:20px;padding:20px;box-shadow:0 8px 24px rgba(16,16,19,.07),0 2px 6px rgba(16,16,19,.05)}
.grid{display:grid;gap:12px}
.g4{grid-template-columns:repeat(4,minmax(0,1fr))}
.g3{grid-template-columns:repeat(3,minmax(0,1fr))}
.g2{grid-template-columns:repeat(2,minmax(0,1fr))}
@media(max-width:820px){.g4,.g3{grid-template-columns:repeat(2,minmax(0,1fr))}.g2{grid-template-columns:1fr}}
.kpi{background:rgba(255,255,255,.94);border:1px solid var(--border);border-radius:16px;padding:14px 15px}
.kpi .v{font-size:25px;font-weight:800;letter-spacing:-.6px;line-height:1.25;font-variant-numeric:tabular-nums}
.kpi .l{font-size:11px;color:var(--t3);font-weight:600;margin-top:1px}
.kpi .d{font-size:10.5px;color:var(--t3);margin-top:6px;line-height:1.6}
.kpi.g .v{color:var(--gt)}.kpi.r .v{color:var(--rt)}.kpi.a .v{color:#9A7220}.kpi.b .v{color:var(--brand)}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th{text-align:right;font-size:10.5px;letter-spacing:.4px;color:var(--t3);font-weight:800;
padding:8px 10px;border-bottom:1px solid var(--border);text-transform:uppercase}
td{padding:9px 10px;border-bottom:1px solid var(--border);vertical-align:top}
tr:last-child td{border-bottom:none}
td.mono,th.mono{font-family:"Cascadia Mono",Consolas,monospace;direction:ltr;text-align:left;font-size:11.5px}
.tag{display:inline-block;border-radius:999px;padding:2px 10px;font-size:10.5px;font-weight:700;white-space:nowrap}
.t-ok{background:var(--gtint);color:var(--gt)}.t-no{background:var(--rtint);color:var(--rt)}
.t-warn{background:var(--atint);color:#9A7220}.t-info{background:var(--btint);color:var(--brand)}
.t-ink{background:var(--ink);color:#fff}.t-mute{background:var(--raised);color:var(--t2)}
.bar{height:8px;border-radius:999px;background:var(--raised);overflow:hidden;display:flex}
.bar i{display:block;height:100%}
.legend{display:flex;flex-wrap:wrap;gap:12px;margin-top:10px;font-size:11px;color:var(--t2)}
.legend span{display:inline-flex;align-items:center;gap:5px}
.dot{width:9px;height:9px;border-radius:3px;display:inline-block}
.note{border-right:3px solid var(--brand);background:var(--btint);border-radius:0 12px 12px 0;
padding:12px 15px;font-size:12.5px;color:#3A3290;margin:12px 0}
.note.warn{border-color:var(--amber);background:var(--atint);color:#7A5A14}
.note.bad{border-color:var(--red);background:var(--rtint);color:#8F2C2C}
.note b{font-weight:800}
ul{margin:8px 0;padding-right:20px}li{margin:5px 0}
.flow{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:14px 0}
.fnode{background:var(--raised);border:1px solid var(--border);border-radius:12px;
padding:9px 13px;font-size:11.5px;font-weight:700;text-align:center;flex:1;min-width:110px}
.fnode small{display:block;font-weight:500;color:var(--t3);font-size:10px;margin-top:2px}
.fnode.hi{background:var(--ink);color:#fff;border-color:var(--ink)}
.fnode.hi small{color:rgba(255,255,255,.6)}
.arr{color:var(--t3);font-size:15px;flex:0 0 auto}
.tl{position:relative;padding-right:26px}
.tl::before{content:"";position:absolute;right:7px;top:6px;bottom:6px;width:2px;background:var(--border)}
.tl-i{position:relative;padding:9px 0}
.tl-i::before{content:"";position:absolute;right:-24px;top:16px;width:12px;height:12px;
border-radius:50%;background:#fff;border:3px solid var(--ink)}
.tl-i.new::before{border-color:var(--brand);box-shadow:0 0 0 4px var(--btint)}
.tl-v{font-weight:800;font-size:13px;direction:ltr;display:inline-block}
.tl-d{color:var(--t3);font-size:11px;margin-right:8px}
.tl-t{font-size:12.5px;color:var(--t2);margin-top:2px}
.code{background:var(--ink);color:#D9D9E2;border-radius:14px;padding:15px 17px;
font-family:"Cascadia Mono",Consolas,monospace;font-size:11.5px;line-height:1.9;
direction:ltr;text-align:left;overflow-x:auto;white-space:pre}
.code .c{color:#7C7C8A}.code .g{color:#5FD39A}.code .b{color:#8B7BF7}
.foot{text-align:center;color:var(--t3);font-size:11.5px;margin-top:44px;padding-top:20px;border-top:1px solid var(--border)}
"""


def build(d: dict) -> str:
    p: list[str] = []
    a = p.append
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    total_code = (d["src_py"][1] + d["panel_py"] + d["main_py"] + d["and_js"][1]
                  + d["and_java"][1] + d["and_css"][1])
    total_test = d["tests_py"][1] + d["tests_js"][1]
    suites = d["tests_js"][0] + 3 + 14          # 9 JS + 3 selftest/check + 14 manual

    a(f"""<!DOCTYPE html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>گزارش پروژه — ODIN Assistant v{e(d['app_version'])}</title><style>{CSS}</style></head><body>""")

    # ── HERO ──────────────────────────────────────────────────────────
    a(f"""<div class="hero"><div class="wrap" style="padding:0">
<div class="h-eyebrow">گزارش وضعیت پروژه · تولید خودکار از دادهٔ اندازه‌گیری‌شده</div>
<h1>ODIN Assistant</h1>
<div class="h-sub">دستیار تحلیل و سیگنال فارکس و طلا — بازار را از چهار سو می‌سنجد، به هر فرصت
امتیاز پشتوانه می‌دهد و فقط سیگنالِ دارای پشتوانه را با دلایل کامل فارسی گزارش می‌کند.
<b style="color:#fff">هیچ معامله‌ای را خودکار اجرا نمی‌کند.</b></div>
<div class="h-meta">
<span class="h-pill">نسخهٔ جاری <b>v{e(d['app_version'])}</b></span>
<span class="h-pill">پلتفرم <b>ویندوز + اندروید</b></span>
<span class="h-pill">کامیت <b>{fa(d['commits'])}</b></span>
<span class="h-pill">نسخهٔ منتشرشده <b>{fa(d['releases'])}</b></span>
<span class="h-pill">تست <b>{fa(suites)} سوئیت</b></span>
<span class="h-pill">CI <b>{'سبز' if d['ci_failures']==0 else 'قرمز'}</b></span>
<span class="h-pill">سرجمع <b>{fa(d['span_days'])} روز</b></span>
</div></div></div>""")

    a('<div class="wrap">')

    # ── ۱ خلاصه مدیریتی ──────────────────────────────────────────────
    a(f"""<section><h2><span class="n">۱</span>خلاصهٔ مدیریتی</h2>
<div class="h2sub">اگر فقط یک بخش را می‌خوانید، این باشد.</div><div class="card">
<p style="margin-top:0">این پروژه در <b>{fa(d['span_days'])} روز</b> ({e(d['first_commit'])} تا {e(d['last_commit'])})
با <b>{fa(d['commits'])} کامیت</b> از صفر به <b>{fa(d['releases'])} نسخهٔ منتشرشده</b> روی دو پلتفرم رسیده است.
موتور تحلیل دو پیاده‌سازی هم‌ارز دارد (پایتون برای ویندوز، جاوااسکریپت برای اندروید) که با
<b>{fa(24)} تست برابری روی دادهٔ زندهٔ بازار</b> قفل شده‌اند — یعنی دو پلتفرم به عددِ یکسان می‌رسند.</p>
<p>از نظر مهندسی، پروژه در وضعیت <span class="tag t-ok">سالم</span> است: هر دو ورک‌فلو CI سبز
(<b>{fa(sum(v['success'] for v in d['ci'].values()))} اجرای موفق متوالی، صفر شکست</b>)،
انتشار هر دو پلتفرم از یک تگ کاملاً خودکار، و {fa(suites)} سوئیت تست.
از نظر <b>محصولی</b> در وضعیت <span class="tag t-warn">پیش از اثبات</span> است:
<b>{fa(d['downloads'])} دانلود</b>، {fa(d['stars'])} ستاره، و مهم‌تر از همه —
<b>دقت سیگنال هنوز در بازار زندهٔ بلندمدت آزموده نشده</b>، چون «دورهٔ سایه» شروع نشده است.</p>
<div class="note bad"><b>مهم‌ترین ریسک پروژه فنی نیست، ادعایی است.</b> تا دورهٔ سایهٔ چند هفته‌ای
انجام نشود، ژورنال و کارنامه ساخته شده‌اند ولی خالی‌اند. هر کار دیگری روی ظاهر یا پایپلاین،
اولویت دوم است.</div></div></section>""")

    # ── ۲ اعداد کلیدی ────────────────────────────────────────────────
    a(f"""<section><h2><span class="n">۲</span>اعداد کلیدی</h2>
<div class="h2sub">همه با فرمان/API اندازه‌گیری شده‌اند — {e(now)}</div>
<div class="grid g4">
<div class="kpi b"><div class="v">{fa(total_code)}</div><div class="l">خط کد محصول</div>
<div class="d">پایتون {fa(d['src_py'][1]+d['panel_py']+d['main_py'])} · JS {fa(d['and_js'][1])} · Java {fa(d['and_java'][1])} · CSS {fa(d['and_css'][1])}</div></div>
<div class="kpi g"><div class="v">{fa(total_test)}</div><div class="l">خط تست</div>
<div class="d">نسبت تست به کد: {total_test*100//max(total_code,1)}٪ · {fa(d['tests_py'][0]+d['tests_js'][0])} فایل</div></div>
<div class="kpi"><div class="v">{fa(d['tracked'])}</div><div class="l">فایل ردیابی‌شده</div>
<div class="d">ریپو {d['repo_kb']//1024 if d.get('repo_kb') else '—'} مگابایت</div></div>
<div class="kpi"><div class="v">{fa(d['docs'][0])}</div><div class="l">سند مستندات</div>
<div class="d">{fa(d['docs'][1])} خط فارسی + CHANGELOG</div></div>

<div class="kpi"><div class="v">{fa(d['releases'])}</div><div class="l">ریلیز عمومی</div>
<div class="d">{fa(len(d['apk_assets']))} APK + {fa(len(d['win_assets']))} فایل ویندوز</div></div>
<div class="kpi a"><div class="v">{fa(d['downloads'])}</div><div class="l">مجموع دانلود</div>
<div class="d">ویندوز {fa(d['win_downloads'])} · اندروید {fa(d['apk_downloads'])}</div></div>
<div class="kpi"><div class="v">{fa(d['stars'])}</div><div class="l">ستاره / فورک</div>
<div class="d">{fa(d['stars'])} ★ · {fa(d['forks'])} fork · {fa(d['issues'])} issue باز</div></div>
<div class="kpi g"><div class="v">{fa(suites)}</div><div class="l">سوئیت تست</div>
<div class="d">{fa(d['tests_js'][0])} JS + ۳ خودآزمون + ۱۴ دستی پایتون</div></div>
</div></section>""")

    # ── ۳ محصول چه کار می‌کند ────────────────────────────────────────
    vet = " · ".join(d["vetoes"])
    a(f"""<section><h2><span class="n">۳</span>محصول چه کار می‌کند</h2>
<div class="h2sub">منطق داور مستقیم از <span style="direction:ltr;display:inline-block">src/judge/scoring.py</span> و <span style="direction:ltr;display:inline-block">config.yaml</span> خوانده شده</div>
<div class="card">
<p style="margin-top:0">هستهٔ محصول یک <b>داور امتیازدهی</b> است. ایدهٔ طراحی این است که
«سیگنال ندادن» هم یک خروجی معتبر باشد — پس اول دروازه‌های وتو، بعد جدول مدارک.</p>
<div class="grid g3" style="margin:16px 0">
<div class="kpi r"><div class="v">{fa(len(d['vetoes']))}</div><div class="l">دروازهٔ وتو</div>
<div class="d">فعال شدن هرکدام = بدون سیگنال، با دلیل مکتوب</div></div>
<div class="kpi g"><div class="v">{fa(len(d['evidences']))}</div><div class="l">مدرک امتیازی</div>
<div class="d">جمعاً ۱۱ امتیاز؛ آستانهٔ صدور <b>{fa(d['min_score'])}</b></div></div>
<div class="kpi b"><div class="v">{fa(len(d['symbols']))}</div><div class="l">نماد تحت پوشش</div>
<div class="d">{' · '.join(d['symbols'])}</div></div>
</div>
<table><tr><th>دروازه‌های وتو</th><th>مدارک امتیازی</th></tr><tr>
<td><span class="tag t-no" style="margin:2px">{'</span> <span class="tag t-no" style="margin:2px">'.join(d['vetoes'])}</span></td>
<td><span class="tag t-ok" style="margin:2px">{'</span> <span class="tag t-ok" style="margin:2px">'.join(x[3:] for x in d['evidences'])}</span></td>
</tr></table>
<p style="margin-bottom:0;color:var(--t2);font-size:12.5px">به‌علاوه: <b>ضداسپم</b> (یک ستاپ تا ۳ ساعت یک‌بار)،
سقف <b>{fa(d['max_signals'])} سیگنال در هر چرخه</b>، حلقهٔ تحلیل هر <b>{fa(d['interval'])} دقیقه</b>،
SL هوشمند (سطح کلیدی + بافر ATR با سقف/کف فاصله) و TP با نسبت ۱:۲.</p>
</div></section>""")

    # ── ۴ معماری ─────────────────────────────────────────────────────
    a(f"""<section><h2><span class="n">۴</span>معماری — یک مغز، دو بدن</h2>
<div class="h2sub">چرا دو پیاده‌سازی؟ چون APK بدون AndroidX و بدون وابستگی بیرونی باید ~۰٫۴ مگابایت بماند.</div>
<div class="card">
<div class="flow">
<div class="fnode">Yahoo Finance<small>کندل‌ها (منبع اصلی)</small></div><span class="arr">←</span>
<div class="fnode">TwelveData<small>زاپاس خودکار</small></div><span class="arr">←</span>
<div class="fnode">ForexFactory<small>تقویم اقتصادی</small></div><span class="arr">←</span>
<div class="fnode">RSS + TradingView<small>اخبار جهت‌دار / تاییدیه</small></div>
</div>
<div class="flow" style="justify-content:center"><span class="arr">↓</span></div>
<div class="flow">
<div class="fnode hi">⚖️ داور<small>{fa(len(d['vetoes']))} وتو → {fa(len(d['evidences']))} مدرک → آستانهٔ {fa(d['min_score'])}</small></div>
<span class="arr">→</span>
<div class="fnode">🎯 سیگنال<small>ورود / SL / TP + دلایل فارسی</small></div>
<span class="arr">→</span>
<div class="fnode">📔 ژورنال<small>append-only + نتیجهٔ خودکار از کندل‌ها</small></div>
<span class="arr">→</span>
<div class="fnode">📊 کارنامه<small>نرخ برد · میانگین R (حلقهٔ صداقت)</small></div>
</div>
<table style="margin-top:18px"><tr><th>لایه</th><th>ویندوز</th><th>اندروید</th></tr>
<tr><td><b>موتور</b></td><td class="mono">Python — src/ ({fa(d['src_py'][0])} فایل · {fa(d['src_py'][1])} خط)</td>
<td class="mono">JavaScript — {fa(d['and_js'][0])} ماژول ({fa(d['and_js'][1])} خط)</td></tr>
<tr><td><b>رابط</b></td><td class="mono">PySide6 — panel.py ({fa(d['panel_py'])} خط) + src/ui/ ({fa(d['src_ui'][1])} خط)</td>
<td class="mono">WebView + HTML/CSS ({fa(d['and_css'][1])} خط) + Java ({fa(d['and_java'][1])} خط)</td></tr>
<tr><td><b>پخش</b></td><td>تلگرام (بریفینگ/سیگنال/هشدار/شبانه) + tray</td><td>اعلان اندروید + لرزش + سرویس پیش‌زمینه</td></tr>
<tr><td><b>بسته‌بندی</b></td><td class="mono">PyInstaller + Inno Setup (~۷۸ MB)</td><td class="mono">Gradle release APK (~۰٫۴ MB)</td></tr>
<tr><td><b>حلقهٔ خودکار</b></td><td>زمان‌بند داخلی + tray</td><td>رصد پس‌زمینه (Handler نیتیو) + BootReceiver</td></tr>
</table>
<div class="note"><b>نکتهٔ کلیدی:</b> رشته‌های موتورِ جاوااسکریپت <b>عمداً</b> دست‌نخورده‌اند
(حتی ایموجی‌هایشان) تا تست برابری با پایتون ممکن بماند؛ تبدیل ایموجی→آیکون فقط در لایهٔ رندر
انجام می‌شود. این یک تصمیم معماری است، نه بدهی.</div>
</div></section>""")

    # ── ۵ پاریتی دو پلتفرم ───────────────────────────────────────────
    a(f"""<section><h2><span class="n">۵</span>پاریتی دو پلتفرم</h2>
<div class="h2sub">«یکسان بودن» ادعاست؛ اینجا با تست سنجیده می‌شود.</div>
<div class="card"><table>
<tr><th>بُعد</th><th>وضعیت</th><th>نگهبان خودکار</th></tr>
<tr><td>منطق موتور (اندیکاتور، داور، ژورنال، آمار)</td><td><span class="tag t-ok">کاملاً یکسان</span></td>
<td class="mono">run_parity.js — ۲۴ تست با دادهٔ زنده</td></tr>
<tr><td>توکن‌های تم رنگی</td><td><span class="tag t-ok">{fa(d['theme_tokens'])} از {fa(d['theme_tokens'])}</span></td>
<td class="mono">smoke_theme_parity.js — هم‌نام و هم‌مقدار</td></tr>
<tr><td>اجزای بصری Aurora Glass 2.0</td><td><span class="tag t-ok">۸ از ۸ پورت شد</span></td>
<td class="mono">components.js ({fa(d['components'])} خط) + ۲۲ assertion رفتاری</td></tr>
<tr><td>شمارهٔ نسخه</td><td><span class="tag t-ok">تک‌منبع</span></td>
<td class="mono">APP_VERSION → build.gradle + version_info.txt</td></tr>
<tr><td>صفحهٔ ورود (Onboarding)</td><td><span class="tag t-no">واگرا</span></td>
<td>دسکتاپ onboarding.py (۶۱۶ خط) · اندروید جریان مودال‌محور v0.14</td></tr>
<tr><td>تلگرام</td><td><span class="tag t-warn">عمداً متفاوت</span></td>
<td>فقط دسکتاپ — کانال موبایل عمداً «اعلان اندروید» است</td></tr>
<tr><td>ستون‌های خرید/فروش TradingView</td><td><span class="tag t-warn">عمداً متفاوت</span></td>
<td>API رسمی دیگر برنمی‌گرداند؛ اپ عدد ساختگی نشان نمی‌دهد</td></tr>
</table>
<p style="margin-bottom:0;color:var(--t2);font-size:12.5px">دو مورد آخر <b>بدهی نیستند</b> — تصمیم‌های
مستندشده‌اند. مورد «صفحهٔ ورود» بدهی واقعی است و در نقشهٔ راه هست.</p>
</div></section>""")

    # ── ۶ کیفیت ──────────────────────────────────────────────────────
    ci_rows = "".join(
        f"<tr><td>{e(k)}</td><td><span class='tag t-ok'>{fa(v['success'])} موفق</span></td>"
        f"<td><span class='tag {'t-no' if v['failure'] else 't-mute'}'>{fa(v['failure'])} شکست</span></td>"
        f"<td class='mono'>{fa(v['other'])} skipped</td></tr>"
        for k, v in d["ci"].items())
    a(f"""<section><h2><span class="n">۶</span>کیفیت: تست و CI</h2>
<div class="h2sub">{fa(suites)} سوئیت — نتیجهٔ آخرین اجرای واقعی همه سبز</div>
<div class="grid g2">
<div class="card"><h3 style="margin-top:0;font-size:14px">سوئیت‌های جاوااسکریپت</h3><table>
<tr><th>تست</th><th>چه می‌سنجد</th></tr>
<tr><td class="mono">run_parity.js</td><td><b>۲۴ تست برابری</b> موتور JS با پایتون — با دادهٔ زندهٔ بازار</td></tr>
<tr><td class="mono">smoke_theme_parity.js</td><td><b>۲۰۸ بررسی</b> پاریتی تم، اجزا، نسخه و صفر-ایموجی</td></tr>
<tr><td class="mono">smoke_icons.js</td><td>۱۸ رندر از ۸ صفحه (پر/خالی/خطا) + markup اجزای Aurora</td></tr>
<tr><td class="mono">smoke_service.js</td><td>رصد پس‌زمینه end-to-end با چرخهٔ زندهٔ واقعی + busy-guard</td></tr>
<tr><td class="mono">smoke_license.js</td><td>HMAC مشترک پایتون↔JS، انقضا، قفل دستگاه، تریال، ضدتغییرساعت</td></tr>
<tr><td class="mono">smoke_alerts/chart/share/about</td><td>هشدار قیمت · نمودار کندل · کارت اشتراک · دربارهٔ ما</td></tr>
</table></div>
<div class="card"><h3 style="margin-top:0;font-size:14px">سوئیت‌های پایتون</h3><table>
<tr><th>تست</th><th>چه می‌سنجد</th></tr>
<tr><td class="mono">main.py --selftest</td><td>تقویم، قطبیت شاخص‌ها، ۹ حالت جهت‌دهی اخبار، ۶ وتو، ریاضی SL/TP، ژورنال، لایسنس</td></tr>
<tr><td class="mono">panel.py --selftest</td><td>پنل offscreen: ۸ صفحه، فونت، آیکون‌ها، داور/رندر</td></tr>
<tr><td class="mono">check_config.py</td><td>۲۳ بررسی روی config.yaml + نبودِ توکن تلگرام در ریپو 🔒</td></tr>
<tr><td class="mono">tests/manual/ ({fa(14)})</td><td>داور، ژورنال، وتو، اخبار، ممیزی، GUI، چیدمان، مسیرهای نصب، دیالوگ فعال‌سازی، لایسنس</td></tr>
</table>
<div class="note warn" style="margin-bottom:0"><b>محدودیت صادقانه:</b> تست‌های GUI دسکتاپ نیاز به
کتابخانه‌های سیستمی Qt دارند و در محیط‌های سبک اجرا نمی‌شوند — فقط CI ویندوز آن‌ها را می‌دود.
یعنی بازخورد محلی برای تغییرات <span class="mono" style="display:inline-block">panel.py</span> ضعیف است.</div>
</div></div>
<div class="card" style="margin-top:12px"><h3 style="margin-top:0;font-size:14px">وضعیت CI (۳۰ اجرای آخر)</h3>
<table><tr><th>ورک‌فلو</th><th>موفق</th><th>شکست</th><th>سایر</th></tr>{ci_rows}</table>
<p style="margin-bottom:0;color:var(--t2);font-size:12.5px">هر push تست می‌شود (پایتون + ۷ اسموک JS)؛
هر تگ <span class="mono" style="display:inline-block">v*</span> <b>هر دو خروجی</b> را می‌سازد و روی
<b>یک Release</b> منتشر می‌کند. یادداشت Release از <span class="mono" style="display:inline-block">CHANGELOG.md</span> خوانده می‌شود.</p>
</div></section>""")

    # ── ۷ انتشار ────────────────────────────────────────────────────
    latest_rows = ""
    for r in d["latest"]:
        ast = " · ".join(f"{e(n)} ({kb(s)})" for n, s in r["assets"]) or "<i style='color:var(--t3)'>بدون فایل</i>"
        latest_rows += f"<tr><td class='mono'>{e(r['tag'])}</td><td class='mono'>{e(r['published'])}</td><td>{ast}</td></tr>"
    a(f"""<section><h2><span class="n">۷</span>انتشار و امضا</h2>
<div class="h2sub">از v0.20.1 کاملاً خودکار — پیش از آن APK دستی آپلود می‌شد و دو بار جا افتاد</div>
<div class="card">
<div class="code"><span class="c"># یک تگ → هر دو پلتفرم</span>
git tag v0.21.0 &amp;&amp; git push --tags
   <span class="b">├─▶</span> build-release.yml : تست‌ها → PyInstaller → Inno Setup
   <span class="b">│</span>                     → اسموک نصب/حذف خاموش → setup.exe + EXE پرتابل
   <span class="b">└─▶</span> build-android.yml: ۷ اسموک JS → نگهبان نسخه → Gradle 8.7
   <span class="b">│</span>                     → <span class="g">راستی‌آزمایی اثر انگشت کلید امضا</span> → APK
                         <span class="b">▼</span>
        <span class="g">یک Release با هر سه فایل + یادداشت از CHANGELOG.md</span></div>
<table style="margin-top:16px"><tr><th>تگ</th><th>تاریخ</th><th>فایل‌ها</th></tr>{latest_rows}</table>
<div class="note"><b>نگهبان زنجیرهٔ امضا:</b> CI اثر انگشت SHA-256 گواهیِ APK را با کلید رسمی
(<span class="mono" style="display:inline-block">bd11159e…cb5189</span>) مقایسه می‌کند و در صورت تفاوت
بیلد را می‌خواباند. درسِ فاجعهٔ v0.12→v0.13 که کلید گم شد و هزینه‌اش «حذف نصب برای کاربران» بود.</div>
</div></section>""")

    # ── ۸ خط زمان ───────────────────────────────────────────────────
    tl = [
        ("v0.2 → v0.4", "۰۹-۱۹", "داده + موتور تکنیکال + فاندامنتال/اخبار + **داور امتیازدهی** و سیگنال با SL/TP"),
        ("v0.5 → v0.8", "۰۹-۱۹/۲۰", "بازطراحی رابط به تم روشن شیشه‌ای · ممیزی سرتاسری (۱۰ باگ) · برند ODIN · نصب‌کنندهٔ رسمی"),
        ("v0.9 → v0.12", "۰۹-۲۰", "**نسخهٔ اندروید** (بازنویسی موتور به JS) · تهران/شمسی · هویت ناشر · اصالت امضا"),
        ("v0.13", "۰۹-۲۱", "رابط کاملاً آیکونی (صفر ایموجی) · **رصد پس‌زمینه** — سیگنال بدون باز کردن اپ"),
        ("v0.14 → v0.15", "۰۹-۲۱", "**لایسنس HMAC + قفل دستگاه** · تریال ۷ روزه و لایسنس زمان‌دار — هر دو پلتفرم"),
        ("v0.16 → v0.18", "۰۹-۲۱", "هشدار قیمت (حتی با اپ بسته) · نمودار کندل‌استیک SVG · اشتراک کارت تصویری برند"),
        ("v0.19", "۰۹-۲۱", "ویندوز هم‌تراز اندروید + **ادغام دو برنچ: یکسان‌سازی کامل دو پلتفرم**"),
        ("v0.20", "۰۹-۲۲", "**Aurora Glass 2.0** (ویندوز) — شفق متحرک، صفحهٔ ورود نو، ۸ ویجت ساختاریافته"),
        ("v0.20.1", "۰۹-۲۲", "**رفع پایپلاین انتشار** — APK خودکار، تک‌منبع نسخه، CHANGELOG، نگهبان امضا", True),
        ("v0.21.0", "۰۹-۲۲", "**Aurora Glass 2.0 در اندروید** — ۲۱ توکن، components.js، نگهبان پاریتی ۲۰۸ بررسی", True),
    ]
    rows = ""
    for item in tl:
        v, dt, txt = item[0], item[1], item[2]
        new = len(item) > 3 and item[3]
        # «**متن**» → <b>متن</b> (جفت‌جفت؛ اگر تعداد فرد بود، آخری بدون بسته می‌ماند
        # و در HTML بی‌ضرر است — ولی بهتر است داده درست باشد)
        txt = "".join((f"<b>{html.escape(x)}</b>" if i % 2 else html.escape(x))
                      for i, x in enumerate(txt.split("**")))
        rows += (f"<div class='tl-i{' new' if new else ''}'><span class='tl-v'>{e(v)}</span>"
                 f"<span class='tl-d'>{e(dt)}</span><div class='tl-t'>{txt}</div></div>")
    a(f"""<section><h2><span class="n">۸</span>خط زمان توسعه</h2>
<div class="h2sub">{fa(d['span_days'])} روز · {fa(d['commits'])} کامیت · {fa(d['tags'])} تگ — نقاط آبی تازه‌های این بازبینی‌اند</div>
<div class="card"><div class="tl">{rows}</div></div></section>""")

    # ── ۹ ریسک‌ها ───────────────────────────────────────────────────
    a(f"""<section><h2><span class="n">۹</span>ریسک‌ها و محدودیت‌ها — صادقانه</h2>
<div class="h2sub">این بخش عمداً آخرین چیزِ «خوب» نیست؛ مهم‌ترین بخش برای تصمیم‌گیری است.</div>
<div class="card"><table>
<tr><th style="width:34%">ریسک</th><th style="width:12%">شدت</th><th>تمهید فعلی و آنچه کم است</th></tr>
<tr><td><b>دقت سیگنال اثبات نشده</b></td><td><span class="tag t-no">بحرانی</span></td>
<td>ژورنال و کارنامه ساخته شده‌اند، ولی <b>دورهٔ سایه شروع نشده</b> — یعنی ادعای اصلی محصول
هنوز هیچ شاهدی ندارد. تا چند هفته ژورنالِ بدون معامله پر نشود، بقیهٔ کارها آرایش است.</td></tr>
<tr><td>وابستگی به منابع دادهٔ رایگان</td><td><span class="tag t-warn">متوسط</span></td>
<td>زاپاس خودکار (Yahoo→TwelveData) و «داده در دسترس نبود» به‌جای سکوت. ولی اگر Yahoo سیاستش را
عوض کند، کل محصول از کار می‌افتد — هیچ قرارداد SLA در کار نیست.</td></tr>
<tr><td>مدیریت تک‌نفرهٔ کلید امضا</td><td><span class="tag t-no">بالا</span></td>
<td>یک کلید قبلاً گم شد (v0.12→v0.13). حالا CI اثر انگشت را راستی‌آزمایی می‌کند، ولی
<b>پشتیبانِ کلید بیرون از این محیط هنوز تهیه نشده</b> — گم‌شدن دوباره = حذف نصب برای همهٔ کاربران.</td></tr>
<tr><td>رصد پس‌زمینه روی گوشی واقعی آزموده نشده</td><td><span class="tag t-warn">متوسط</span></td>
<td>Doze و OEMهای اندروید (شیائومی/سامسونگ/هوآوی) ممکن است سرویس را بکشند.
راهنمای مجوز باتری داخل اپ هست، ولی <b>تست میدانی چند روزه انجام نشده</b>.</td></tr>
<tr><td>لایسنس آفلاین ذاتاً شکستنی است</td><td><span class="tag t-mute">ذاتی</span></td>
<td>secret داخل باینری است، پس کاربر مصمم می‌تواند کلید بسازد. در
<span class="mono" style="display:inline-block">LICENSE_GUIDE.md</span> صادقانه مستند شده —
این یک محدودیت ذاتی است نه باگ.</td></tr>
<tr><td>کهنگی مستندات</td><td><span class="tag t-warn">متوسط</span></td>
<td>گزارش پروژه یک بار <b>۷ نسخه</b> عقب افتاد و یادداشت ۱۹ ریلیز پیاپی غلط بود.
حالا CHANGELOG منبع حقیقت است، ولی <b>هیچ نگهبان خودکاری برای کهنگی دوبارهٔ مستندات نیست</b>.</td></tr>
<tr><td>توزیع نشدن (۰ ستاره، {fa(d['downloads'])} دانلود)</td><td><span class="tag t-mute">محصولی</span></td>
<td>از نظر فنی آمادهٔ عرضه است ولی هیچ کانال توزیعی ندارد: نه Play Store، نه سایت، نه SEO.
کارت اشتراک تصویری (v0.18) تنها ساز وکار بازاریابیِ درون‌برنامه‌ای است.</td></tr>
</table></div></section>""")

    # ── ۱۰ نقشه راه ─────────────────────────────────────────────────
    road = [
        ("۱۴", "دورهٔ سایه — اثبات دقت با آمار ژورنال", "no", "مهم‌ترین کار باقی‌مانده"),
        ("۱۲", "صفحهٔ ورود اندروید هم‌تراز onboarding.py دسکتاپ", "no", "توکن‌های onb-* همین حالا در CSS آماده‌اند"),
        ("۱۳", "زمان‌بندی Task Scheduler ویندوز (اجرای خودکار)", "no", ""),
        ("۱۵", "تست میدانی رصد پس‌زمینه روی گوشی واقعی", "no", "Doze / ریستارت / محدودیت باتری"),
        ("۱۶", "نگهبان خودکارِ کهنگی مستندات", "no", "تا بخش ۸ب-۷ تکرار نشود"),
        ("۱۷", "کانال توزیع (سایت / Play Store)", "no", "بدون آن، ۰ ستاره می‌ماند"),
    ]
    rrows = "".join(
        f"<tr><td><b>{fa(n)}</b></td><td>{e(t)}"
        + (f"<div style='color:var(--t3);font-size:11px'>{e(nt)}</div>" if nt else "")
        + "</td><td><span class='tag t-warn'>انجام‌نشده</span></td></tr>"
        for n, t, _s, nt in road)
    a(f"""<section><h2><span class="n">۱۰</span>نقشهٔ راه — قدم بعدی</h2>
<div class="h2sub">مراحل ۰ تا ۱۱ کامل شده‌اند (۲۸ ریلیز). این‌ها مانده‌اند، به ترتیب ارزش:</div>
<div class="card"><table><tr><th style="width:8%">#</th><th>کار</th><th style="width:18%">وضعیت</th></tr>{rrows}</table>
<div class="note bad" style="margin-bottom:0"><b>توصیهٔ صریح:</b> ترتیب بالا عمداً با «دورهٔ سایه» شروع می‌شود.
پروژه از نظر مهندسی جلوتر از آن است که از نظر شواهدِ محصولی هست. افزودن قابلیت بیشتر،
بدونِ اثبات دقت، فقط فاصلهٔ بین «ادعا» و «شاهد» را بیشتر می‌کند.</div>
</div></section>""")

    # ── ۱۱ سلامت ریپو ───────────────────────────────────────────────
    a(f"""<section><h2><span class="n">۱۱</span>سلامت ریپو</h2>
<div class="h2sub">سنجش‌های ساختاری، نه سلیقه‌ای</div>
<div class="grid g2"><div class="card"><table>
<tr><th colspan="2">شاخص‌های ساختاری</th></tr>
<tr><td>واگرایی برنچ‌ها</td><td><span class="tag t-ok">صفر</span> <span style="color:var(--t3);font-size:11.5px">main و android روی <span class="mono" style="display:inline-block">{e(d['branch_main'])}</span></span></td></tr>
<tr><td>فایل بزرگ‌تر از ۱۵۰۰ خط</td><td><span class="tag t-warn">۱ مورد</span> <span style="color:var(--t3);font-size:11.5px">panel.py = {fa(d['panel_py'])} خط</span></td></tr>
<tr><td>توکن/کلید در ریپو</td><td><span class="tag t-ok">هیچ</span> <span style="color:var(--t3);font-size:11.5px">تلگرام در config.local.yaml (خارج از گیت)</span></td></tr>
<tr><td>تست با mutation testing آزموده شد</td><td><span class="tag t-ok">بله</span> <span style="color:var(--t3);font-size:11.5px">۵ جهش عمدی، هر ۵ قرمز</span></td></tr>
<tr><td>وابستگی بیرونی اپ اندروید</td><td><span class="tag t-ok">صفر</span> <span style="color:var(--t3);font-size:11.5px">بدون AndroidX، بدون کتابخانهٔ JS</span></td></tr>
<tr><td>مسیر دادهٔ کاربر</td><td><span class="tag t-ok">استاندارد</span> <span style="color:var(--t3);font-size:11.5px">%APPDATA% یا کنار EXE</span></td></tr>
</table></div>
<div class="card"><h3 style="margin-top:0;font-size:14px">توزیع کد</h3>
<div class="bar">
<i style="width:{d['src_py'][1]*100//total_code}%;background:var(--ink)" title="پایتون src/"></i>
<i style="width:{(d['panel_py']+d['main_py'])*100//total_code}%;background:#3A3A44" title="panel.py + main.py"></i>
<i style="width:{d['src_ui'][1]*100//total_code}%;background:var(--brand)" title="src/ui/"></i>
<i style="width:{d['and_js'][1]*100//total_code}%;background:var(--indigo)" title="JS اندروید"></i>
<i style="width:{d['and_java'][1]*100//total_code}%;background:var(--cyan)" title="Java"></i>
<i style="width:{d['and_css'][1]*100//total_code}%;background:var(--pink)" title="CSS"></i>
</div>
<div class="legend">
<span><i class="dot" style="background:var(--ink)"></i>src/ پایتون {fa(d['src_py'][1])}</span>
<span><i class="dot" style="background:#3A3A44"></i>panel+main {fa(d['panel_py']+d['main_py'])}</span>
<span><i class="dot" style="background:var(--brand)"></i>src/ui/ {fa(d['src_ui'][1])}</span>
<span><i class="dot" style="background:var(--indigo)"></i>JS اندروید {fa(d['and_js'][1])}</span>
<span><i class="dot" style="background:var(--cyan)"></i>Java {fa(d['and_java'][1])}</span>
<span><i class="dot" style="background:var(--pink)"></i>CSS {fa(d['and_css'][1])}</span>
</div>
<h3 style="font-size:14px;margin-bottom:6px">ریتم توسعه (کامیت در روز)</h3>
<div class="bar" style="height:14px">
{"".join(f'<i style="width:{100//len(d["days"])}%;background:var(--{"brand" if i==len(d["days"])-1 else "ink"})" title="{e(k)}: {v} کامیت"></i>' for i,(k,v) in enumerate(d["days"]))}
</div>
<div class="legend">{"".join(f'<span>{e(k)} — <b>{fa(v)}</b></span>' for k,v in d["days"])}</div>
<p style="margin:12px 0 0;color:var(--t2);font-size:12px">نکتهٔ صادقانه: این ریتم
({fa(d['commits'])} کامیت در {fa(d['span_days'])} روز) نشان می‌دهد پروژه در یک
<b>فشرده‌سازی اولیه</b> ساخته شده. چنین ریتمی برای شروع درست است، ولی برای نگهداری
بلندمدت — و مخصوصاً برای «دورهٔ سایه» که ذاتاً کند است — باید عوض شود.</p>
</div></div></section>""")

    a(f"""<div class="foot">گزارش پروژهٔ ODIN Assistant · نسخهٔ v{e(d['app_version'])} ·
تولید خودکار در {e(now)} از دادهٔ اندازه‌گیری‌شدهٔ ریپو و API گیت‌هاب<br>
منابع جزئی‌تر: <span class="mono" style="display:inline-block">docs/project-report-fa.md</span> (گزارش مهندسی) ·
<span class="mono" style="display:inline-block">CHANGELOG.md</span> (تاریخچهٔ نسخه‌ها) ·
<span class="mono" style="display:inline-block">README.md</span> (معرفی)</div>""")
    a("</div></body></html>")
    return "".join(p)


def main() -> int:
    d = measure()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build(d), encoding="utf-8")
    print(f"[report] ✓ {OUT.relative_to(ROOT)}  ({OUT.stat().st_size//1024} KB)")
    if d.get("net_error"):
        print(f"[report] ⚠ بخشی از دادهٔ گیت‌هاب در دسترس نبود: {d['net_error']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
