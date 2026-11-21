#!/usr/bin/env python3
"""Тест: таймаут модели обязан быть enforced (21.11.2026).

Проверяем ровно тот сценарий, который вешал слоты: дочерний процесс
(«агент») держит собственного внука, который наследует stdout и живёт
долго. Старый subprocess.run(capture_output=True) вис на communicate()
до 3600s. Новый _run_group_timeout обязан вернуть rc=124 быстро.
"""
import sys, time, os
sys.path.insert(0, "/home/thomas/LivingCode/orchestration/scripts")
from living_code_agent_wrapper import _run_group_timeout

cmd = ["/bin/bash", "-c", "sleep 600 & sleep 600"]  # внук держит stdout
t0 = time.time()
r = _run_group_timeout(cmd, 5)
dt = time.time() - t0
print(f"rc={r.returncode} elapsed={dt:.1f}s stderr={r.stderr.strip()[:120]}")
assert r.returncode == 124, f"ожидался rc=124, получен {r.returncode}"
assert dt < 20, f"таймаут не enforced: ждали {dt:.1f}s"
# и что группа реально мертва: 'sleep 600' больше не живёт
out = os.popen("pgrep -f 'slee[p] 600' | wc -l").read().strip()
print("оставшихся sleep-процессов:", out)
assert out == "0", f"внуки выжили после SIGKILL: {out}"
print("PASS: таймаут enforced, группа убита")
