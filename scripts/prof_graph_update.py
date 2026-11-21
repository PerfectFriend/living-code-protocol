#!/usr/bin/env python3
"""Профессор 2026-09-27: добавить 12 изученных тем в knowledge-graph.json."""
import json
import os
import shutil
from collections import OrderedDict

PATH = "/home/thomas/LivingCode/knowledge-base/knowledge-graph.json"
shutil.copy2(PATH, PATH + ".bak-professor-20260927")

with open(PATH, encoding="utf-8") as f:
    g = json.load(f)

NEW = [
    ("kb:meta-project-ot", "Meta Project OT — план AI-native и его отмена", 10, 1.6162,
     "Meta-Project-OT-AI-Native-2026.md",
     {"org": "Meta", "considered_cut_pct": 60, "actual_cut_pct": 10, "laid_off": 8000,
      "waves_planned": 2, "cancelled": "2-я волна (ноябрь 2026)", "provenance": "EXTRACTED"}),
    ("kb:eu-cra-24h", "EU Cyber Resilience Act — отчётность 24/72/14 (с 11.09.2026)", 10, 1.4990,
     "EU-Cyber-Resilience-Act-24h-Reporting-2026.md",
     {"early_warning_h": 24, "full_notification_h": 72, "final_report_days": 14,
      "oss_steward_deadline": "2027-12-11", "signatories": 100, "provenance": "EXTRACTED"}),
    ("kb:google-ai-responsibility", "Google: AI Responsibility (≈90 чел.) выведена из DeepMind", 10, 1.4212,
     "Google-AI-Responsibility-Out-Of-DeepMind-2026.md",
     {"team_size": 90, "from": "DeepMind", "to": "Global Affairs", "effective": "2026-09",
      "hassabis_role": "chairman", "provenance": "EXTRACTED"}),
    ("kb:deepseek-v4-pro", "DeepSeek V4 Pro — 1.6T MoE / 49B active / 1M контекст / MIT", 9, 1.2461,
     "DeepSeek-V4-Pro-MoE-Agentic-Coding-2026.md",
     {"params_total_b": 1600, "params_active_b": 49, "context_tokens": 1000000,
      "gdpval_aa_elo": 1554, "swe_verified": 80.6, "terminal_bench_2": 67.9,
      "mcp_atlas": 73.6, "toolathlon": 51.8, "vram_gb_fp4_fp8": 320,
      "license": "MIT", "provenance": "EXTRACTED"}),
    ("kb:checkstyle", "Checkstyle 14.1.0 — Java-анализатор как CI-гейт", 9, 1.0680,
     "Checkstyle-Java-Static-Analysis-2026.md",
     {"repo": "checkstyle/checkstyle", "stars": 9575, "forks": 4254, "issues": 760,
      "license": "LGPL-2.1", "release": "14.1.0", "pushed": "2026-09-26", "provenance": "EXTRACTED"}),
    ("kb:anthropic-mhs", "Anthropic Model Hardware Standard (MHS)", 9, 1.0355,
     "Anthropic-Model-Hardware-Standard-MHS-2026.md",
     {"primitives": ["read", "write"], "transport": "MCP", "model_agnostic": True,
      "partners": ["AWS Strands Robots", "HF LeRobot", "Raspberry Pi", "Automata", "Universal Robots"],
      "provenance": "EXTRACTED"}),
    ("kb:ai-debt-jpmorgan", "Долги ИИ-компаний vs Treasuries (JPMorgan/Cembalest)", 8, 0.9049,
     "AI-Debt-Hyperscaler-JPMorgan-2026.md",
     {"debt_usd_b": 320, "long_duration_usd_b": 303, "share_of_new_ust_pct": 68,
      "issuers": ["Oracle", "Microsoft", "Amazon", "Alphabet", "Meta", "NVIDIA"],
      "gs_forecast_2027_usd_b": 340, "provenance": "EXTRACTED"}),
    ("kb:quantum-laser-quera", "QuEra + Claude: калибровка лазера квантового компьютера", 8, 0.9020,
     "AI-Quantum-Laser-Calibration-QuEra-Anthropic-2026.md",
     {"success_trials": "695/700", "fast_fix_s": 6, "hard_fix_s": "10-14",
      "human_fix_min": "5-10", "noise_reduction_x": 5,
      "artifact": "детерминированный контроллер по решениям ИИ", "provenance": "EXTRACTED"}),
    ("kb:microduck-rl", "microduck_rl — sim2real RL-пайплайн (MuJoCo/PPO/ONNX)", 7, 0.8382,
     "Microduck-RL-Sim2Real-Pipeline-2026.md",
     {"repo": "pollen-robotics/microduck_rl", "stars": 2281, "forks": 490,
      "runtime_repo": "pollen-robotics/microduck", "runtime_stars": 8813,
      "license": "Apache-2.0", "control_hz": 50, "servos": 15,
      "soc": "Rockchip RK3566", "train_hours": "1-2 @4096 envs",
      "playbook": "AGENTS.md", "provenance": "EXTRACTED"}),
    ("kb:vphone-cli", "Lakr233/vphone-cli — виртуальный iPhone на Apple Silicon", 7, 0.8333,
     "VPhone-CLI-Virtual-iPhone-2026.md",
     {"repo": "Lakr233/vphone-cli", "stars": 14480, "forks": 1698, "license": "MIT",
      "language": "Swift 6.0", "requires": "macOS 15+, SIP/AMFI off, PV=3",
      "guest_ios": "26", "version": "v0.1.2", "provenance": "EXTRACTED"}),
    ("kb:korea-ai-for-all", "Южная Корея «AI for All» — бесплатный ИИ 51 млн жителей", 6, 0.7515,
     "South-Korea-AI-for-All-2026.md",
     {"population_m": 51, "consortia": ["SK Telecom", "KT", "Kakao"],
      "gpus_nvidia_b200": 512, "budget_krw_trn": 10.1, "budget_usd_b": 7.2,
      "free_until": 2028, "law": "AI Basic Act (в силе с 01.2026)", "provenance": "EXTRACTED"}),
    ("kb:tamagotchi-ring", "Tamagotchi Ring — инженерный предел миниатюризации", 5, 0.6940,
     "Tamagotchi-Ring-Engineering-2026.md",
     {"size_mm": "28x23x35", "display_mm": 14.2, "components": 64, "dev_years": 2,
      "price_jpy": 7700, "price_usd": 48, "ship": "февраль 2027", "provenance": "EXTRACTED"}),
]

existing = {n["id"] for n in g["nodes"]}
added = []
for nid, label, prio, score, fname, props in NEW:
    if nid in existing:
        continue
    g["nodes"].append(OrderedDict([
        ("id", nid),
        ("label", label),
        ("type", "topic"),
        ("priority", prio),
        ("laya_score", score),
        ("status", "studied"),
        ("studied", "2026-09-27"),
        ("file", "knowledge-base/" + fname),
        ("props", props),
    ]))
    added.append(nid)

EDGES = [
    ("kb:meta-project-ot", "protocol:auditor", "validates", "Meta: агенты и кодинг-инструменты НЕ дали ожидаемого роста производительности → самоотчёт роя требует артефактного замера"),
    ("kb:meta-project-ot", "protocol:journal", "mandates", "анти-паттерн: контроль активности (клавиатура/мышь) вместо контроля артефактов"),
    ("kb:eu-cra-24h", "protocol:auditor", "defines_sla_for", "24ч предупреждение / 72ч детали / 14 дней финальный отчёт — внешний шаблон SLA для наших инцидентов"),
    ("kb:eu-cra-24h", "kb:google-ai-responsibility", "converges_with", "оба кейса про институционализацию ИИ-безопасности в 2026 (регулятор + орг-перестановка)"),
    ("kb:google-ai-responsibility", "protocol:auditor", "proves_need_for", "независимость аудитора определяется тем, в чьём подчинении он оказался, а не фактом отделения"),
    ("kb:deepseek-v4-pro", "kb:compaction-deception", "mitigates", "1M контекста позволяет не сжимать длинные сессии — обход класса ошибок compaction-summary deception"),
    ("kb:deepseek-v4-pro", "artifact:local-llm", "not_deployable_on", "320 GB FP4+FP8 — вне бюджета AMD iGPU/64GB DDR5, только API"),
    ("kb:checkstyle", "protocol:auditor", "tool_of", "машинное число нарушений вместо словесного «analyze clean» (наш класс 9 vs 10 issue)"),
    ("kb:checkstyle", "artifact:project-elemental-life-2", "applicable_to", "JVM/Android-проекты роя: config/checkstyle.xml + exit-code гейт в CI"),
    ("kb:anthropic-mhs", "protocol:unfreeze", "provides_pattern_for", "LLM один раз → детерминированный скрипт-драйвер; теги физических ограничений вместо magic numbers"),
    ("kb:anthropic-mhs", "kb:quantum-laser-quera", "converges_with", "оба: LLM-исследование компилируется в фиксированный контроллер/скрипт"),
    ("kb:quantum-laser-quera", "protocol:auditor", "provides_metric_template", "метрика «695/700 восстановлений за <6 сек» вместо бинарного «работает/не работает»"),
    ("kb:ai-debt-jpmorgan", "artifact:local-llm", "justifies", "рост долгового финансирования ИИ → удешевление внешнего инференса не гарантировано, локальный путь — страховка"),
    ("kb:microduck-rl", "protocol:professor", "provides_pattern_for", "AGENTS.md как distilled playbook: уроки проектом, а не дамп логов"),
    ("kb:microduck-rl", "kb:anthropic-mhs", "converges_with", "обучение (дорого, шумно) отделено от рантайма (фиксирован) — тот же принцип «LLM → скрипт»"),
    ("kb:microduck-rl", "protocol:snapshot", "supports", "domain randomization/backlash = тестирование с возмущениями, наш реальный класс гонок в Учебнике"),
    ("kb:vphone-cli", "artifact:local-llm", "not_applicable", "требует Apple Silicon + macOS 15 + отключённый SIP — на Linux-хосте и на машине с ключами неприемлемо"),
    ("kb:vphone-cli", "protocol:unfreeze", "provides_pattern_for", "CLI-конвейер: одна высокоуровневая команда + идемпотентные перезапускаемые шаги"),
    ("kb:korea-ai-for-all", "protocol:professor", "context_for", "ИИ как общественная услуга без лимитов → цена массового инференса уходит вниз, но неравномерно"),
    ("kb:korea-ai-for-all", "kb:eu-cra-24h", "converges_with", "национальные режимы регулирования ИИ 2026 (Корея — AI Basic Act, ЕС — CRA)"),
    ("kb:tamagotchi-ring", "protocol:auditor", "illustrates", "осознанно декоративный элемент — оправданное решение, а не забытый стаб; и «функция важнее формы» при бюджете"),
    ("artifact:wiki", "kb:meta-project-ot", "indexes"),
    ("artifact:wiki", "kb:eu-cra-24h", "indexes"),
    ("artifact:wiki", "kb:google-ai-responsibility", "indexes"),
    ("artifact:wiki", "kb:deepseek-v4-pro", "indexes"),
    ("artifact:wiki", "kb:checkstyle", "indexes"),
    ("artifact:wiki", "kb:anthropic-mhs", "indexes"),
    ("artifact:wiki", "kb:ai-debt-jpmorgan", "indexes"),
    ("artifact:wiki", "kb:quantum-laser-quera", "indexes"),
    ("artifact:wiki", "kb:microduck-rl", "indexes"),
    ("artifact:wiki", "kb:vphone-cli", "indexes"),
    ("artifact:wiki", "kb:korea-ai-for-all", "indexes"),
    ("artifact:wiki", "kb:tamagotchi-ring", "indexes"),
]
have = {(e.get("from"), e.get("to"), e.get("rel")) for e in g["edges"]}
for f, t, rel, *why in EDGES:
    key = (f, t, rel)
    if key in have:
        continue
    e = OrderedDict([("from", f), ("to", t), ("rel", rel)])
    if why:
        e["why"] = why[0]
    g["edges"].append(e)
    have.add(key)

g["meta"]["updated"] = "2026-09-27"
g["meta"]["last_pass"] = "professor-2026-09-27: 12 тем по 🔴, laya-score priority 10→5, все с живыми источниками"
with open(PATH, "w", encoding="utf-8") as f:
    json.dump(g, f, ensure_ascii=False, indent=2)
    f.write("\n")

print("добавлено узлов:", len(added))
print("всего узлов:", len(g["nodes"]), "| всего рёбер:", len(g["edges"]))
print("новые id:", ", ".join(added))
