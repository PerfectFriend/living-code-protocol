#!/usr/bin/env python3
"""topic252_to_textbook.py — разобрать очередь топика 252 в записи Учебника.

Запуск (крон каждые 15 минут):
  python3 topic252_to_textbook.py            # обработать всё необработанное
  python3 topic252_to_textbook.py --limit 5
  python3 topic252_to_textbook.py --dry-run  # ничего не писать, показать план
Нет новых сообщений → печатает NO_NEW_MESSAGES (и отчёт не отправляется).

Что делает на каждое сообщение:
  1. classify(text)  → раздел Учебника (эвристика по ключевым словам)
  2. пишет <Topic>.md в vault (frontmatter textbook-entry, status 🟢)
  3. добавляет строку в Учебник.md под нужный `### N. <name>`
  4. дописывает дайджест со ВСЕМИ ссылками в ~/.hermes/cron/topic252_digest.md

Пути переопределяются env: TEXTBOOK_VAULT, TOPIC252_DIGEST, TOPIC252_DB.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from topic252_queue import (DB_PATH, URL_RE, mark_processed, pending,  # noqa: E402
                            stats)
from textbook_lock import TextbookLock  # noqa: E402

# --------------------------------------------------------------------- конфиг
DEFAULT_VAULTS = [
    Path.home() / "Документы" / "ObsidianVault",   # русская локаль (текущий хост)
    Path.home() / "Documents" / "ObsidianVault",   # старый путь
]


def resolve_vault() -> Path:
    env = os.environ.get("TEXTBOOK_VAULT")
    if env:
        p = Path(env).expanduser()
        if p.is_dir():
            return p
        raise SystemExit(f"TEXTBOOK_VAULT={env} не существует")
    for p in DEFAULT_VAULTS:
        if p.is_dir():
            return p
    raise SystemExit("vault не найден: нет ни ~/Документы/ObsidianVault, "
                     "ни ~/Documents/ObsidianVault — задай TEXTBOOK_VAULT")


VAULT = resolve_vault()
INDEX = VAULT / "Учебник.md"
DIGEST = Path(os.environ.get(
    "TOPIC252_DIGEST", str(Path.home() / ".hermes" / "cron" / "topic252_digest.md")
)).expanduser()

# Ключевые слова по НОМЕРАМ разделов (структура Учебника). Заголовки берутся
# из самого файла — так маппинг не может «разъехаться» с `### N. ...`.
SECTION_KEYWORDS: dict[str, list[str]] = {
    "1": ["graph", "граф", "эволюц", "evolution", "node", "пульс"],
    "2": ["obsidian", "обсидиан", "vault", "dataview", "bases", "canvas"],
    "3": ["mcp", "model context protocol", "agent integration", "tool use", "плагин"],
    "4": ["rocm", "directml", "amd", "780m", "radeon", "igpu", "vulkan"],
    "5": ["yolo", "surveillance", "видеонаблюд", "rtsp", "камер", "детекц"],
    "5b": ["dhcp", "аренд", "lease", "сеть", "network", "arp", "роутер"],
    "6": ["paranoidx", "p2p", "simplex", "sovereign", "суверен", "tor", "vpn"],
    "7": ["windows", "msys", "powershell", "wsl"],
    "8": ["книг", "literature", "алгоритм", "classic", "cs fundamentals"],
    "9": ["hermes", "cron", "skill", "скилл", "gateway", "session"],
    "10": ["awesome", "github collection", "curated list", "подборка"],
    "11": ["design", "дизайн", "figma", "ui", "css"],
    "12": ["second brain", "zettelkasten", "заметк", "second brain"],
    "13": ["vllm", "inference", "sglang", "batching", "kv cache"],
    "14": ["autonomous", "агент", "agent", "orchestration", "swarm", "роё"],
    "15": ["quant", "квантов", "gguf", "awq", "gptq", "int4", "сжати"],
    "16": ["rag", "retrieval", "embedding", "вектор", "векторн", "chunk"],
    "17": ["lora", "qlora", "fine-tun", "файнтюн", "дообуч"],
    "18": ["spec-driven", "spec kit", "спецификац", "spec"],
    "19": ["ai engineering", "stack", "фреймворк", "framework"],
    "20": ["marketing", "маркетинг", "growth", "реклам", "seo", "воронк"],
    "21": ["mastery", "концепц", "concept"],
    "22": ["advanced spec", "harness"],
    "23": ["marketing deep", "growth automation"],
    "24": ["neo kim", "21"],
    "25": ["godmodemarketing", "godmode"],
    "27": ["mindset", "психолог", "мышлен", "дисциплин"],
    "29": ["last30days", "chinese platform", "cn"],
}

MISC_HEADER = "### Разное / Misc (priority: 5)"
MISC_KEYWORDS = ["misc", "разное"]


# ------------------------------------------------------------------- разборка
def parse_sections(index_text: str) -> dict[str, tuple[int, str]]:
    """{номер раздела: (line_no0, полная строка заголовка)} — первое вхождение."""
    out: dict[str, tuple[int, str]] = {}
    for i, line in enumerate(index_text.splitlines()):
        m = re.match(r"^###\s+([0-9]+[a-z]?)\.\s*(.+)$", line.strip())
        if not m:
            continue
        num, rest = m.group(1), m.group(2)
        if num in out:          # дубликаты номеров в файле — берём первый
            continue
        out[num] = (i, line.rstrip())
    return out


def classify(text: str, sections: dict[str, tuple[int, str]]) -> tuple[str, str]:
    """→ (номер раздела, строка заголовка для вставки)."""
    low = (text or "").lower()
    best_num, best_hits = None, 0
    for num, kws in SECTION_KEYWORDS.items():
        if num not in sections:
            continue
        hits = sum(1 for kw in kws if kw in low)
        if hits > best_hits:
            best_num, best_hits = num, hits
    if best_num is None:
        for num, (_, header) in sections.items():
            hl = header.lower()
            if any(kw in hl for kw in MISC_KEYWORDS) or "unknown" in hl:
                return num, header
        return "", MISC_HEADER
    return best_num, sections[best_num][1]


def slugify(text: str, max_len: int = 80) -> str:
    s = re.sub(URL_RE, " ", text or "")
    s = re.sub(r"[#*_`>\[\]()]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r'[<>:"/\\|?*\n\r\t]', "", s)
    if not s:
        s = "Topic252 message"
    return s[:max_len].strip(" .-—")


def title_for(text: str, urls: list[str]) -> str:
    """Человеческий заголовок: первая осмысленная строка или домен ссылки."""
    for line in (text or "").splitlines():
        line = line.strip()
        if line and not line.startswith("http") and len(line) > 3:
            return slugify(re.sub(URL_RE, "", line).strip() or line, 90)
    if urls:
        host = re.sub(r"^https?://(www\.)?", "", urls[0]).split("/")[0]
        return f"{host} — из топика 252"
    return slugify(text, 90)


def unique_filename(name: str) -> str:
    fname = f"{name}.md"
    i = 2
    while (VAULT / fname).exists():
        fname = f"{name} — {i}.md"
        i += 1
    return fname


ENTRY_TMPL = """---
type: textbook-entry
topic: "{topic}"
status: "🟢 Изучено"
learned: "{learned}"
source: "{source}"
tags: ["#topic252", "#telegram", "{tag}"]
---

# {topic}

## Raw (источник)
{raw}

## Key Insights
- Разбор из Telegram-топика 252 (автопарсер). Тезисы ниже — из текста сообщения.
{insights}

## Links
{links}

## Code Patterns
```bash
# очередь топика 252
python3 ~/.hermes/scripts/topic252_queue.py stats
echo "текст https://ссылка" | python3 ~/.hermes/scripts/topic252_fetch.py manual
python3 ~/.hermes/scripts/topic252_to_textbook.py
```

## Applied To
- Skill: textbook-learning-pipeline (раздел: {section_header})
- File changed: Учебник.md (индекс)

## Next Steps
- [ ] Углубить тему по первоисточникам из Links
- [ ] Проверить применимость в текущих проектах
"""


def write_entry(topic: str, text: str, urls: list[str], section_header: str,
                author: str, ts: str) -> str:
    fname = unique_filename(slugify(topic, 90))
    learned = datetime.now().strftime("%Y-%m-%d %H:%M")
    bullets = []
    for line in (text or "").splitlines():
        line = line.strip(" -•*\t")
        if len(line) > 25 and not line.startswith("http"):
            bullets.append(f"- {line}")
        if len(bullets) >= 6:
            break
    if not bullets:
        bullets = ["- (короткое сообщение, тезисы не выделены)"]
    links = "\n".join(f"- {u}" for u in urls) if urls else "- (ссылок в сообщении нет)"
    num = re.match(r"^###\s+([0-9]+[a-z]?)\.", section_header)
    tag = f"#{'section' + num.group(1) if num else 'misc'}"
    body = ENTRY_TMPL.format(
        topic=topic.replace('"', "'"), learned=learned,
        source=urls[0] if urls else "telegram:-1004431090317:252",
        tag=tag, raw=text.strip() or "(пусто)",
        insights="\n".join(bullets), links=links,
        section_header=section_header,
    )
    (VAULT / fname).write_text(body, encoding="utf-8")
    return fname


def patch_textbook(fname: str, topic: str, section_header: str, date_str: str) -> bool:
    """Вставить строку индекса в конец блока нужного раздела.

    ВАЖНО: якоримся НЕ на заголовок раздела (однажды это уже съело §20),
    а на границы блока: от строки заголовка до следующего `### ` / конца файла.
    Использует TextbookLock для предотвращения гонок записи.
    """
    def _transform(text: str) -> str:
        if fname in text:
            print(f"  = {fname} уже в индексе — пропуск")
            return text  # No change
        lines = text.splitlines()
        start = None
        for i, line in enumerate(lines):
            if line.rstrip() == section_header.rstrip():
                start = i
                break
        if start is None:                       # раздела ещё нет — создаём в конце
            entry_line = (f"- [x] [{topic}]({fname}) — 🟢 #topic252:{date_str}")
            new_text = text.rstrip() + f"\n\n{MISC_HEADER}\n{entry_line}\n"
            print(f"  + раздел отсутствовал, создан Misc с записью {fname}")
            return new_text
        end = len(lines)
        for j in range(start + 1, len(lines)):
            if lines[j].startswith("### "):
                end = j
                break
        # найти последнюю непустую строку блока, чтобы вставить сразу под ней
        ins = end
        for j in range(end - 1, start, -1):
            if lines[j].strip():
                ins = j + 1
                break
        entry_line = f"- [x] [{topic}]({fname}) — 🟢 #topic252:{date_str}"
        lines.insert(ins, entry_line)
        return "\n".join(lines) + "\n"
    
    with TextbookLock(str(INDEX)) as lock:
        new_text = lock.read_write(_transform)
        # Check if anything changed
        return new_text != lock.read()


def append_digest(rows: list[dict]) -> None:
    DIGEST.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    parts = [f"\n## {stamp} — разобрано {len(rows)} сообщ.\n"]
    for r in rows:
        parts.append(f"### {r['topic']}")
        parts.append(f"- запись: `{r['fname']}` | раздел: {r['section']}")
        parts.append(f"- автор: {r['author'] or 'n/a'} | msg: {r['tg_msg_id']}")
        if r["urls"]:
            parts.append("- ссылки:")
            parts.extend(f"  - {u}" for u in r["urls"])
        else:
            parts.append("- ссылок нет")
        parts.append("")
    with DIGEST.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(parts) + "\n")


# ---------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    index_text = INDEX.read_text(encoding="utf-8") if INDEX.exists() else ""
    sections = parse_sections(index_text)
    rows = pending(args.limit)
    if not rows:
        print("NO_NEW_MESSAGES")
        print(stats())
        return 0

    date_str = datetime.now().strftime("%Y-%m-%d")
    done: list[dict] = []
    for r in rows:
        text = r["text"]
        urls = json.loads(r["urls"] or "[]")
        num, header = classify(text, sections)
        topic = title_for(text, urls)
        print(f"[{r['id']}] §{num or 'misc'} — {topic}")
        print(f"    urls: {urls or '—'}")
        if args.dry_run:
            continue
        fname = write_entry(topic, text, urls, header, r["author"], r["ts"])
        patch_textbook(fname, topic, header, date_str)
        mark_processed(r["id"], fname)
        done.append({"topic": topic, "fname": fname, "section": header,
                     "author": r["author"], "tg_msg_id": r["tg_msg_id"],
                     "urls": urls})

    if args.dry_run:
        print(f"DRY-RUN: {len(rows)} сообщений к разбору, ничего не записано")
        return 0

    append_digest(done)
    print(f"\n✅ Разобрано {len(done)}. Дайджест: {DIGEST}")
    print(stats())
    return 0


if __name__ == "__main__":
    sys.exit(main())
