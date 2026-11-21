#!/usr/bin/env python3
"""check_roster.py — CI-гейт реестра ролей Протокола Живого Кода (Фаза 1).

По образцу check-divisions.sh из The Agency: скрипт ПАДАЕТ (exit 1) при разрыве
непрерывности. Source of truth — orchestration/roster.json.

Проверки:
  1. Каждая роль roster.json существует в живом jobs.json (по cron_id).
  2. Каждая роль с no_agent=True имеет script, и скрипт существует на диске
     (крон без скрипта = разрыв непрерывности — как wrapper_auditor 18 авг).
  3. Каждая роль pinned на разрешённую модель белого списка протокола
     (приказ 24.10.2026: единственная удалённая модель — minimax-m3.1-flash).
  4. Крон без пина модели (drift_skip) — предупреждение, не падение.

Использование: check_roster.py [--update]  (--update перезаписывает roster.json с диска)
"""
import json
import pathlib
import sys
import datetime

ORC = pathlib.Path.home() / "LivingCode/orchestration"
ROSTER = ORC / "roster.json"
HERMES_JOBS = pathlib.Path.home() / ".hermes/cron/jobs.json"

# 04.11.2026 решением владельца: ВСЕ NEMOTRON под жёстким баном (саботаж —
# уничтожены локальные проекты и GitHub). Основная пара протокола —
# mistralai/mistral-large-4-1t-a52b (nvidia). Любой nemotron в jobs.json —
# ошибка ростера. Локальная Laya остаётся судьёй (logprobs).
PROTOCOL_MODEL = "mistralai/mistral-large-4-1t-a52b"
PROTOCOL_PROVIDER = "nvidia"
BANNED_MODEL_SUBSTRINGS = ("nemotron",)
ALLOWED_PAIRS = frozenset({
    (PROTOCOL_MODEL, PROTOCOL_PROVIDER),
})


def build_roster() -> dict:
    """Собрать roster.json с живого jobs.json: роль → {cron_id, имя, скрипт, модель, статус}."""
    jobs = json.loads(HERMES_JOBS.read_text(encoding="utf-8"))["jobs"]
    roster = {}
    for j in jobs:
        name = str(j.get("name", ""))
        if not (name.startswith("LV") or name.startswith(("Профессор", "Искатель", "Topic"))):
            continue
        roster[name] = {
            "cron_id": j["id"],
            "enabled": bool(j.get("enabled")),
            "no_agent": bool(j.get("no_agent")),
            "script": j.get("script"),
            "model": j.get("model"),
            "provider": j.get("provider"),
            "pinned": bool(j.get("pinned")),
            "workdir": j.get("workdir"),
        }
    return {"_generated": datetime.datetime.now().astimezone().isoformat(), "roles": roster}


def check(roster: dict) -> tuple[list[str], list[str]]:
    """(errors, warnings): расхождения roster.json с диском и живым jobs.json."""
    errors, warnings = [], []
    roles = roster.get("roles", {})
    # N=0 rule (план v3): пустой ростер = разрыв непрерывности, а не «всё ок»
    if not roles:
        errors.append("N=0: ростер пуст — реестр ролей потерян (правило N=0 ⇒ не проверено)")
    jobs = json.loads(HERMES_JOBS.read_text(encoding="utf-8"))["jobs"]
    live = {j["id"]: j for j in jobs}
    live_names = {str(j.get("name", "")) for j in jobs}

    for name, r in roles.items():
        cid = r.get("cron_id")
        if cid not in live:
            errors.append(f"разрыв: роль '{name}' ссылается на крон {cid}, которого нет в jobs.json")
            continue
        if not r.get("enabled"):
            continue  # paused-роль рой не запускает — её скрипт может быть в восстановлении
        j = live[cid]
        if name not in live_names:
            errors.append(f"разрыв: роль '{name}' переименована в jobs.json (там её нет)")
        script = r.get("script")
        if r.get("no_agent") and not script:
            errors.append(f"разрыв: no_agent-роль '{name}' без script (крон запустится в никуда)")
        if script:
            sp = pathlib.Path.home() / ".hermes/scripts" / script
            if not sp.exists():
                errors.append(f"разрыв: скрипт роли '{name}' не существует: {script}")
        model, provider = r.get("model"), r.get("provider")
        if model and any(b in model.lower() for b in BANNED_MODEL_SUBSTRINGS):
            errors.append(f"БАН NEMOTRON у '{name}': {model} — запрещена решением владельца 04.11.2026 (саботаж)")
        elif model and (model, provider) not in ALLOWED_PAIRS:
            errors.append(f"модель/провайдер вне белого списка у '{name}': {model} ({provider})")
        # Пин в Hermes = сами значения model/provider в задаче (_job_route_pinned):
        # поле pinned не хранится. no_agent-роли ходят через собственный движок —
        # им пин не нужен; агент-модовым (no_agent=False) без model/provider нельзя.
        if not r.get("no_agent") and r.get("enabled") and not (model and provider):
            warnings.append(f"агент-модель-роль '{name}' без model/provider — уйдёт на главный default (drift_skip)")

    # Обратное направление: LV-кроны в jobs.json, которых нет в roster.json
    for j in jobs:
        name = str(j.get("name", ""))
        if (name.startswith("LV") or name.startswith(("Профессор", "Искатель", "Topic"))) and name not in roster.get("roles", {}):
            warnings.append(f"живой крон '{name}' ({j['id'][:12]}) отсутствует в roster.json — запусти --update")
    return errors, warnings


def main() -> None:
    update = "--update" in sys.argv
    if update or not ROSTER.exists():
        roster = build_roster()
        ROSTER.write_text(json.dumps(roster, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"roster.json записан: {len(roster['roles'])} ролей")
        if not update:
            return  # первая генерация — только создать
    roster = json.loads(ROSTER.read_text(encoding="utf-8"))
    errors, warnings = check(roster)
    # Фаза 0 плана v3 (2026-11-04): stale-score rule — если условия протокола ушли
    # от снимка, старые оценки протухли. Предупреждение, не падение.
    try:
        import subprocess as _sp
        _r = _sp.run([sys.executable, str(ORC / "scripts" / "condition_snapshot.py"), "check"],
                     capture_output=True, text=True, timeout=30)
        if _r.returncode != 0:
            warnings.append("CONDITION_STALE: условия изменились со снимка state/condition_snapshot.json — "
                            "старые scores протухли; после приёмки правки: condition_snapshot.py snapshot")
    except Exception:
        pass
    for w in warnings:
        print(f"⚠️  {w}")
    for e in errors:
        print(f"⛔ {e}")
    print(f"\nИтог: {len(roster.get('roles', {}))} ролей, ошибок: {len(errors)}, предупреждений: {len(warnings)}")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
