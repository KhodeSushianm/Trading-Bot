# -*- coding: utf-8 -*-
"""حل‌کنندهٔ وابستگی‌ها — مرتب‌سازی توپولوژیک (Kahn) روی requires/provides (فاز ۱).

دو قانون رفتاری (تصویب‌شده در Preview فاز ۱):
  ۱) وابستگی مفقود → پلاگینِ وابسته `disabled_reason` فارسی می‌گیرد و از
     زنجیرهٔ اجرا خارج می‌شود — بدون استثنا، بدون کرش. (مصرف‌کننده مقدار
     unavailable می‌بیند = امتیاز صادقانهٔ ۰؛ همان فلسفهٔ فعلی پروژه.)
  ۲) حلقهٔ وابستگی → CircularDependencyError با مسیر کامل حلقه. این باگ
     «باید» پرسروصدا باشد: حلقه یعنی طراحی مانیفست غلط است، نه شرایط
     محیطی — پس fail-loud (همان درس نگهبان‌های v0.19.1/v0.20.0).

خروجی resolve: فهرست رکوردها به ترتیبی که هر پلاگین بعد از همهٔ
وابستگی‌های سختِ فعالش بیاید؛ tie-break با (priority، ترتیب ثبت) تا
خروجی کاملاً قطعی باشد. رکوردهای مرتب‌شده وضعیت RESOLVED می‌گیرند.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from .lifecycle import PluginState
from .registry import PluginRecord


class CircularDependencyError(RuntimeError):
    """حلقه در گراف وابستگی پلاگین‌ها — با مسیر حلقه در پیام فارسی."""


def resolve(records: List[PluginRecord]) -> List[PluginRecord]:
    """ترتیب‌دهی توپولوژیک + علامت‌گذاری RESOLVED / disabled_reason.

    رکوردهای ورودی که از قبل enabled نیستند (کاربر/config خاموش کرده) در
    گراف «نبود» تلقی می‌شوند — یعنی وابستگی به پلاگین غیرفعال هم مفقود
    حساب می‌شود (و دلیل فارسی می‌گیرد).
    """
    # رکوردهای شرکت‌کننده: فقط enabled و بدون disable قبلی
    pool: Dict[str, PluginRecord] = {
        r.id: r for r in records if r.enabled and not r.disabled_reason
    }

    # نگاشت قرارداد → فراهم‌کننده‌های فعال (ممکن است چندتایی باشد)
    providers: Dict[str, List[str]] = {}
    for r in pool.values():
        for cid in r.manifest.provides:
            providers.setdefault(cid, []).append(r.id)

    # ۱) حذف تدریجیِ پلاگین‌هایی با وابستگی مفقود (waterfall) — چون
    #    غیرفعال‌شدن A ممکن است وابستگی B را هم مفقود کند.
    changed = True
    while changed:
        changed = False
        for r in list(pool.values()):
            missing = [cid for cid in r.manifest.requires
                       if cid not in providers or not providers[cid]]
            if missing:
                rec = pool.pop(r.id)
                rec.disabled_reason = (
                    f"وابستگی فراهم نشد: {', '.join(missing)} — پلاگین غیرفعال "
                    f"می‌ماند تا قابلیتِ فراهم‌کننده فعال شود (unavailable، نه کرش)")
                for cid in rec.manifest.provides:      # فراهم‌کنندگی‌اش را هم بردار
                    if cid in providers and rec.id in providers[cid]:
                        providers[cid].remove(rec.id)
                changed = True

    # ۲) گراف وابستگی بین بازماندگان: A → B یعنی B باید قبل از A بیاید
    deps: Dict[str, set] = {pid: set() for pid in pool}
    for pid, r in pool.items():
        for cid in r.manifest.requires:
            for provider_id in providers.get(cid, []):
                if provider_id != pid:
                    deps[pid].add(provider_id)

    # ۳) Kahn با صف مرتب (priority، order، id) برای خروجی قطعی
    def sort_key(pid: str):
        r = pool[pid]
        return (r.manifest.priority, r.order, pid)

    indeg = {pid: len(d) for pid, d in deps.items()}
    ready = sorted([pid for pid, n in indeg.items() if n == 0], key=sort_key)
    out: List[PluginRecord] = []
    while ready:
        pid = ready.pop(0)
        out.append(pool[pid])
        for other, d in deps.items():
            if pid in d:
                d.remove(pid)
                indeg[other] -= 1
                if indeg[other] == 0:
                    ready.append(other)
        ready.sort(key=sort_key)

    # ۴) باقی‌مانده = حلقه → پرسروصدا با مسیر
    if len(out) != len(pool):
        stuck = sorted(set(pool) - {r.id for r in out}, key=sort_key)
        path = _find_cycle(stuck, deps)
        raise CircularDependencyError(
            "حلقهٔ وابستگی بین پلاگین‌ها: " + " → ".join(path)
            + " — مانیفست‌ها را اصلاح کنید (requires نباید حلقه بسازد)")

    for r in out:
        if r.state is PluginState.REGISTERED:
            r.state = PluginState.RESOLVED
    return out


def _find_cycle(stuck: List[str], deps: Dict[str, set]) -> List[str]:
    """یک حلقهٔ واقعی را از میان گره‌های گیرکرده پیدا می‌کند (برای پیام خطا)."""
    seen = set()
    stack: List[str] = []

    def dfs(node: str) -> Optional[List[str]]:
        if node in stack:
            i = stack.index(node)
            return stack[i:] + [node]
        if node in seen:
            return None
        seen.add(node)
        stack.append(node)
        for nxt in sorted(deps.get(node, ())):
            if nxt in set(stuck):
                found = dfs(nxt)
                if found:
                    return found
        stack.pop()
        return None

    for n in stuck:
        cycle = dfs(n)
        if cycle:
            return cycle
    return stuck + ["..."]
