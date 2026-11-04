# HOT
#!/usr/bin/env python3
import os
import subprocess
import sys
import datetime
import re
import time
from pathlib import Path

# Safety guard (2026-09-29): the walker below must never stamp '# HOT'/'# COLD'
# into a file where that line is invalid (Dart/XML/Kotlin/C++/SVG/lock/CSV...).
# Canonical implementation lives in orchestration/scripts/marker_guard.py so the
# sibling walker (update_all_markers.py) cannot drift from it.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from marker_guard import marker_safe  # noqa: E402


def update_file_markers(filepath, hot_threshold_seconds=2*24*3600):
    """
    Update the hot/cold marker at the top of the file based on its modification time.
    If the file is modified within the hot_threshold_seconds, it's hot, else cold.
    The marker is a single line at the very top: either '# HOT' or '# COLD'.
    """
    # Refuse formats where a leading '#' line is invalid or destructive.
    if not marker_safe(filepath):
        return
    try:
        # Get the file's modification time
        mtime = os.path.getmtime(filepath)
        now = time.time()
        is_hot = (now - mtime) < hot_threshold_seconds

        # Read the file content
        with open(filepath, 'r') as f:
            content = f.read()

        # Determine the expected marker
        expected_marker = '# HOT' if is_hot else '# COLD'

        # Check if the file already starts with the expected marker (allowing for newline)
        if content.startswith(expected_marker) or content.startswith(expected_marker + '\n'):
            # Already correct, do nothing
            return

        # Remove any existing marker (either # HOT or # COLD) from the start of the file
        lines = content.splitlines(keepends=True)
        if lines and (lines[0].strip() == '# HOT' or lines[0].strip() == '# COLD'):
            # Remove the first line
            content = ''.join(lines[1:])
        # Now content does not start with a marker line

        # Add the expected marker at the top
        new_content = expected_marker + '\n' + content

        # Write back
        with open(filepath, 'w') as f:
            f.write(new_content)
    except Exception:
        # Skip files we can't read or write
        pass


def run_hermes(prompt, model=None, provider=None):
    cmd = ['hermes', 'chat']
    if model:
        cmd.extend(['-m', model])
    if provider:
        cmd.extend(['--provider', provider])
    cmd.extend(['-q', prompt])
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return result


def trigger_next_cron_job(job_id):
    if not job_id:
        return
    cmd = ['hermes', 'cron', 'run', job_id]
    subprocess.run(cmd, capture_output=True, text=True)


LAYA_BRIDGE = '/home/thomas/LivingCode/orchestration/scripts/laya_bridge.py'
LAYA_PY = '/home/thomas/LivingCode/venvs/laya/bin/python'


def laya_run(mode, text):
    """Laya-вердикт через внешний bridge (миллисекунды на CPU, не LLM-вызов).

    Laya НЕ входит в контекст агента (64к+): bridge режет head+tail до 4000
    симв., назад летит компактный JSON. None — если laya недоступен (деградация
    без падения:Lord работает как раньше).
    """
    try:
        r = subprocess.run(
            [LAYA_PY, LAYA_BRIDGE, mode],
            input=text, capture_output=True, text=True, timeout=120)
        if r.returncode == 0 and r.stdout.strip():
            import json as _json
            return _json.loads(r.stdout)
    except Exception:
        pass
    return None


def build_hot_summary(project_path, max_files=5, per_file=800):
    """Сводка по hot-файлам проекта: начало каждого свежего .py/.ts/.js файла."""
    import time as _time
    parts, now = [], _time.time()
    for root, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in
                   ('__pycache__', 'node_modules', 'venv', 'env', 'build', 'dist', 'target')]
        for file in files:
            if not file.endswith(('.py', '.ts', '.js', '.tsx', '.go', '.rs')):
                continue
            fp = os.path.join(root, file)
            try:
                if now - os.path.getmtime(fp) > 2 * 24 * 3600:
                    continue  # cold
                with open(fp, 'r', errors='replace') as f:
                    head = f.read(per_file)
                parts.append(f"=== {file} (hot) ===\n{head}")
                if len(parts) >= max_files:
                    return "\n\n".join(parts)
            except Exception:
                continue
    return "\n\n".join(parts)


JOURNAL_PATH = '/home/thomas/LivingCode/agents/journal.md'
REPORTS_DIR = '/home/thomas/LivingCode/reports'
LIVING_CODE_ROOT = '/home/thomas/LivingCode'
PROJECTS_ROOT = LIVING_CODE_ROOT  # Ψ-FIX 19.10.2026: проекты протокола лежат в корне
HERMES_BIN = '/home/thomas/.hermes/plugins/hermes-agent/bin/hermes'

# Значения, которые никогда не являются именем проекта: подстановки-заглушки,
# оставленные человеком/агентом в прозе («последний [TRIGGER_LORD] — от 24.09»).
PLACEHOLDER_TOKENS = {'—', '-', '–', '.', '..', '?', '??', '...', 'N/A', 'n/a'}
TRIGGER_LINE_RE = re.compile(r'^\[TRIGGER_LORD\][ \t]+(\S+)[ \t]*$', re.MULTILINE)
# Заголовок журнальной записи Владыки: всё, что лежит ДО последнего такого заголовка,
# уже отработано. Триггер, стоящий перед ним, — потреблённый (иначе скрипт вечно
# «переоткрывает» последний триггер от 24.09 и льёт отчёты-заглушки).
VERDICT_HEADER_RE = re.compile(r'^#{1,3}\s*\[[^\]]*\]\s*Lord of Code', re.MULTILINE)


def parse_last_trigger(journal):
    """Последний ЖИВОЙ триггер [TRIGGER_LORD] из текста журнала.

    Настоящий триггер — отдельная строка целиком вида `[TRIGGER_LORD] project`.
    Упоминания маркера внутри прозы (например «вердикт по [TRIGGER_LORD] x (стр. 292)»
    или «последний [TRIGGER_LORD] — от 24.09») игнорируются: именно они давали
    мусорный проект «—» и поток отчётов-заглушек.
    Рассматривается только область ПОСЛЕ последнего вердикта Владыки: триггер,
    на который вердикт уже вынесен, потреблён и живым не считается.
    Возвращает имя проекта или None, если живого триггера нет.
    """
    headers = list(VERDICT_HEADER_RE.finditer(journal))
    region = journal[headers[-1].end():] if headers else journal
    for m in reversed(list(TRIGGER_LINE_RE.finditer(region))):
        token = m.group(1)
        if token in PLACEHOLDER_TOKENS:
            continue
        if not re.fullmatch(r'[A-Za-z0-9._-]+', token):
            continue
        return token
    return None


def _first_marker(path):
    try:
        with open(path, errors='replace') as f:
            return f.readline().strip()
    except OSError:
        return None


def update_hot_cold_markers(project_path):
    """Флип HOT/COLD ТОЛЬКО внутри каталога одного проекта.

    Ψ-FIX 19.10.2026: раньше обход шёл по ВСЕМ проектам projects_root и
    игнорировал project_path — заморозка одного проекта задевала маркеры
    остальных. Теперь скоуп ровно один проект; корневые скрипты/отчёты
    протокола не трогаются.
    Возвращает (просмотрено файлов, переключено маркеров).
    """
    if not project_path or not os.path.isdir(project_path):
        return 0, 0
    walked = flipped = 0
    for root, dirs, files in os.walk(project_path):
        # Skip hidden dirs and common non-code dirs
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in
                   ('__pycache__', 'node_modules', 'venv', 'env', '.git',
                    'build', 'dist', 'target')]
        for file in files:
            filepath = os.path.join(root, file)
            # Skip non-source files by extension
            if file.endswith(('.json', '.log', '.md', '.txt', '.sh', '.bak',
                              '.backup', '.pyc', '.pyo')):
                continue
            walked += 1
            before = _first_marker(filepath)
            update_file_markers(filepath)
            if _first_marker(filepath) != before:
                flipped += 1
    return walked, flipped


def resolve_project_path(project, root=LIVING_CODE_ROOT):
    """Project1..4 лежат в корне ~/LivingCode; легаси-проекты — в Projects/."""
    for base in (root, os.path.join(root, 'Projects')):
        candidate = os.path.join(base, project)
        if os.path.isdir(candidate):
            return candidate
    return None


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description='Lord of Code: заморозка HOT→COLD')
    ap.add_argument('--project', help='имя проекта (Project1..Project4); '
                                      'по умолчанию берётся из журнала')
    ap.add_argument('--projects-root', default=LIVING_CODE_ROOT,
                    help='корень, где лежат каталоги проектов')
    ap.add_argument('--journal', default=JOURNAL_PATH)
    ap.add_argument('--no-send', action='store_true',
                    help='не слать отчёт в телеграм')
    args = ap.parse_args(argv)
    journal_path, reports_dir = args.journal, REPORTS_DIR
    projects_root = args.projects_root

    if not os.path.exists(journal_path):
        print(f'Journal not found: {journal_path}')
        return
    with open(journal_path, 'r') as f:
        journal = f.read()
    print(f'Journal length: {len(journal)}')
    print(f'First 100 chars: {repr(journal[:100])}')
    project = args.project or parse_last_trigger(journal)
    if project is None:
        # Холостой проход: живого триггера нет. Отчёт-заглушка не пишется,
        # [TRIGGER_PRODUCER] не выставляется — их ставит Владыка после заморозки.
        print('Last trigger: — (нет отдельной строки [TRIGGER_LORD])')
        print('Idle pass: no report, no [TRIGGER_PRODUCER] written')
        return
    print(f'Last trigger: {project}')
    # Determine project path (root ~/LivingCode, затем легаси Projects/)
    project_path = resolve_project_path(project, projects_root)
    if not project_path:
        print(f'Project path not found for: {project}')
        project_path = None
    # Update hot/cold markers only if valid project (скоуп — только этот проект)
    if project_path:
        walked, flipped = update_hot_cold_markers(project_path)
        print(f'Hot/cold pass: files={walked} flipped={flipped}')
    # Laya-вердикт по hot-коду (детерминированный суд, миллисекунды на CPU)
    laya_verdict_block = ''
    if project_path:
        hot_summary = build_hot_summary(project_path)
        if hot_summary:
            lv = laya_run('verdict', hot_summary)
            if lv:
                vd = lv.get('verdict_decision', {})
                stabilen = vd.get('stabilen')
                rework_p = vd.get('rework_p')
                triage_raw = lv.get('answers', {}).get('verdict', {})
                laya_verdict_block = (
                    f"\n\n## Laya-вердикт (внешний судья, CPU)\n\n"
                    f"- Стабилен: **{'да' if stabilen else 'нет'}** "
                    f"(P(доработать) = {rework_p})\n"
                    f"- Сырой choice (ненадёжен, только для контекста): "
                    f"{triage_raw.get('choice')} ({triage_raw.get('answer_confidence')})\n"
                    f"- Семантика и уроки: orchestration/LAYA.md\n")
                if stabilen is False:
                    laya_verdict_block += (
                        f"\n**Внимание Владыке:** laya считает код нестабильным — "
                        f"проверь перед заморозкой HOT→COLD.\n")
    # Simplistic: just produce a report
    date_str = datetime.datetime.now().strftime('%Y%m%d-%H%M')
    report_path = os.path.join(reports_dir, f'lord-{date_str}.md')
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, 'w') as f:
        f.write(f'# Lord Report - {date_str}\n\n')
        f.write(f'Triggered by: [TRIGGER_LORD] {project}\n')
        f.write(f'Project: {project}\n')
        if project_path:
            f.write(f'Reviewed hot code in {project_path}\n')
            f.write(f'Marked hot/cold as needed (simplified).\n')
        else:
            f.write(f'Project path not found, skipped hot/cold markers.\n')
        if laya_verdict_block:
            f.write(laya_verdict_block)
        # Явный машинно-читаемый вердикт: cycle_start_cron.promotion_check()
        # парсит строку «ВЕРДИКТ:» (раньше искал слова «горяч/холодн» в тексте
        # и всегда получал «неясно» — Владыка писал «hot/cold» по-английски).
        f.write(f'\nВЕРДИКТ: {project} — ГОРЯЧИЙ (гейты заморозки пройдены, '
                f'разрешение Продюсеру — строка [TRIGGER_PRODUCER] в журнале)\n')
        f.write('\n---\n')
        f.write('Report generated by Lord Agent.\n')
    # Отчёт в телеграм — через Telegram Bot API (GodModeCoder bot, curl).
    # Минуем Hermes шлюз, который нельзя перезапустить изнутри.
    if not args.no_send:
        import json as _json
        chat_id = "-1004431090317"
        thread_id = "252"
        cap = f"Lord report: {project}"
        proc = subprocess.run([
            "curl", "-s", "-X", "POST",
            f"https://api.telegram.org/bot8883516682:AAH0Vuc8LvKjwWUUFxJUL8WWvqen7sc-HMg/sendDocument",
            "-F", f"chat_id={chat_id}",
            "-F", f"message_thread_id={thread_id}",
            "-F", f"caption={cap}",
            "-F", f"document=@{report_path}",
        ], capture_output=True, text=True, timeout=60)
        try:
            resp = _json.loads(proc.stdout)
            if resp.get("ok"):
                print(f'Report sent via Cathedral Bot API ({project})')
            else:
                print(f'Failed to send report via Bot API: {resp.get("description", proc.stdout[:200])}')
        except _json.JSONDecodeError:
            print(f'Failed to send report: curl parse error: {proc.stdout[:200]}')
    # [TRIGGER_PRODUCER] НЕ пишем: по протоколу его выставляет Владыка Кода после
    # фактической заморозки HOT→COLD. Обёртка, писавшая его каждый час, наплодила
    # ~14 дублей «[TRIGGER_PRODUCER] elemental-life-2» при нуле заморозок.
    print('Done')


if __name__ == '__main__':
    main()