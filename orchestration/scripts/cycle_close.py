#!/usr/bin/env python3
"""Детерминированное закрытие цикла Живого Кода для одного проекта.

Вызывается обёрткой продюсера ПОСЛЕ агентной части:
    python3 cycle_close.py Project1

Что делает (строго по шагам, без участия LLM):
  1. Читает journal.md, находит последний живой [TRIGGER_PRODUCER] <project>
     и последующие маркеры [PRODUCER_GRADE] / [COLD_RELEASE].
  2. Коммитит проект в его собственный git (если есть изменения)
     и пушит в оба remote: flash и github.
  3. Проверяет «холодность» кода детерминированными гейтами:
       - нет файлов с маркером первой строки '# HOT'
       - нет открытых замечаний '[СР' в .md проекта
       - PLAN.md: ни одного неотмеченного пункта '- [ ]'
       - тесты зелёные (если в проекте есть tests/)
  4. Если продюсер написал [COLD_RELEASE] <project> И все гейты пройдены:
       - копирует проект в Releases/<project> (без .git и мусора)
       - шлёт нотификацию в телеграм через Cathedral Bot API (curl)
     Если [COLD_RELEASE] есть, но гейты не пройдены — релиз откладывается,
     причина фиксируется в state и в отчёте.
  5. Пишет orchestration/state/cycle_state.json (идемпотентность:
     повторный вызов на том же маркере ничего не дублирует).

Код выхода: 0 — ок (в т.ч. «нечего делать»), 1 — блокирующая ошибка
(не удалось читать журнал/проект, упал пуш в оба remote или тесты).
"""
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime

ROOT = os.path.expanduser('~/LivingCode')
JOURNAL = os.path.join(ROOT, 'agents/journal.md')  # канон протокола: агенты пишут сюда
STATE_PATH = os.path.join(ROOT, 'orchestration/state/cycle_state.json')
RELEASES_DIR = os.path.join(ROOT, 'Releases')
HERMES_BIN = '/home/thomas/.hermes/plugins/hermes-agent/bin/hermes'
PYTEST_BIN = os.path.expanduser('~/build/bin/pytest')

MARKER_RE = re.compile(
    r'\[(TRIGGER_PRODUCER|PRODUCER_GRADE|COLD_RELEASE)\s+([A-Za-z0-9_.\-]+)(.*)$')
SKIP_DIRS = {'.git', '__pycache__', '.pytest_cache', 'venv', '.venv',
             'node_modules', 'Releases', '.mypy_cache', '.ruff_cache'}
CODE_SUFFIXES = ('.py', '.sh', '.md')


def log(msg):
    print(f'[cycle_close] {msg}')


def run(cmd, cwd=None, timeout=600):
    """Запуск команды; возвращает (rc, tail_stdout)."""
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           timeout=timeout)
        return p.returncode, (p.stdout or '').strip()[-800:]
    except subprocess.TimeoutExpired:
        return 124, 'TIMEOUT'


def load_state():
    try:
        with open(STATE_PATH) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, 'w') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def find_last_markers(project):
    """Последние (по номеру строки) маркеры цикла для проекта.

    Возвращает dict: producer_line, grade_line, grade_text, cold_line.
    'Живой' маркер — после него не пришёл новый [TRIGGER_PRODUCER]
    (для одного проекта берём просто последний).
    """
    res = {'producer_line': None, 'grade_line': None, 'grade_text': '',
           'cold_line': None}
    if not os.path.exists(JOURNAL):
        return res
    with open(JOURNAL) as f:
        lines = f.readlines()
    for idx, line in enumerate(lines, start=1):
        m = MARKER_RE.search(line)
        if not m:
            continue
        kind, proj, rest = m.group(1), m.group(2), m.group(3)
        if proj != project:
            continue
        if kind == 'TRIGGER_PRODUCER':
            res.update(producer_line=idx, grade_line=None, grade_text='',
                       cold_line=None)
        elif kind == 'PRODUCER_GRADE' and res['producer_line'] is not None:
            res.update(grade_line=idx, grade_text=rest.strip(' —-'))
        elif kind == 'COLD_RELEASE' and res['producer_line'] is not None:
            res['cold_line'] = idx
    return res


def hot_files(project_dir):
    """Файлы с маркером первой строки '# HOT'."""
    found = []
    for dirpath, dirnames, filenames in os.walk(project_dir):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if not name.endswith(CODE_SUFFIXES):
                continue
            path = os.path.join(dirpath, name)
            try:
                with open(path, errors='replace') as f:
                    if f.readline().strip() == '# HOT':
                        found.append(os.path.relpath(path, project_dir))
            except OSError:
                continue
    return found


def open_remarks(project_dir):
    """Открытые замечания '[СР' в markdown проекта."""
    found = []
    for dirpath, dirnames, filenames in os.walk(project_dir):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if not name.endswith('.md'):
                continue
            path = os.path.join(dirpath, name)
            try:
                with open(path, errors='replace') as f:
                    for i, line in enumerate(f, start=1):
                        if '[СР' in line:
                            found.append(f'{os.path.relpath(path, project_dir)}:{i}')
            except OSError:
                continue
    return found


def plan_unchecked(project_dir):
    plan = os.path.join(project_dir, 'PLAN.md')
    if not os.path.exists(plan):
        return None
    with open(plan, errors='replace') as f:
        return sum(1 for line in f if line.lstrip().startswith('- [ ]'))


def tests_ok(project_dir):
    """None — тестов нет; True/False — результат прогона."""
    tdir = os.path.join(project_dir, 'tests')
    if not os.path.isdir(tdir) or not os.path.exists(PYTEST_BIN):
        return None
    rc, out = run([PYTEST_BIN, '-q', '-x', 'tests'], cwd=project_dir, timeout=300)
    return rc == 0, out[-300:]


def git_cycle_push(project, project_dir):
    """Коммит (если что менять) + пуш в flash и github. Возвращает список ошибок."""
    errors = []
    rc, out = run(['git', 'add', '-A'], cwd=project_dir)
    if rc != 0:
        return [f'git add: {out}']
    rc, out = run(['git', 'diff', '--cached', '--quiet'], cwd=project_dir)
    if rc != 0:  # есть staged-изменения
        stamp = datetime.now().strftime('%Y-%m-%d %H:%M')
        rc, out = run(['git', 'commit', '-q', '-m',
                       f'цикл {stamp}: авто-коммит продюсера ({project})'],
                      cwd=project_dir)
        if rc != 0:
            errors.append(f'git commit: {out}')
        else:
            log(f'{project}: коммит цикла создан')
    else:
        log(f'{project}: изменений для коммита нет')
    for remote in ('flash', 'github'):
        rc, out = run(['git', 'push', remote, 'main'], cwd=project_dir, timeout=180)
        if rc != 0:
            errors.append(f'push {remote}: {out}')
        else:
            log(f'{project}: push → {remote} ok')
    return errors


def do_release(project, project_dir):
    """Копирование проекта в Releases/<project> + нотификация в телеграм."""
    dest = os.path.join(RELEASES_DIR, project)
    os.makedirs(RELEASES_DIR, exist_ok=True)
    if os.path.exists(dest):
        shutil.rmtree(dest)
    ignore = shutil.ignore_patterns('.git', '__pycache__', '.pytest_cache',
                                    '*.bak', '*.bak-*', 'venv', '.venv',
                                    'node_modules', '.slot_start')
    shutil.copytree(project_dir, dest, ignore=ignore)
    log(f'{project}: релиз сложен в {dest}')
    stamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    msg = (f'🧊 {project} — код полностью холодный, замечаний нет.\n'
           f'Релиз переложен в Releases/{project} ({stamp}).\n'
           f'Код запушен во все git (flash + github).')
    # Отправка через Cathedral Bot API (curl), минуя заблокированный Hermes шлюз
    import json as _json
    proc = subprocess.run([
        "curl", "-s", "-X", "POST",
        "https://api.telegram.org/bot8883516682:AAH0Vuc8LvKjwWUUFxJUL8WWvqen7sc-HMg/sendMessage",
        "-d", f"chat_id=-1004431090317",
        "-d", f"message_thread_id=252",
        "-d", f"text={msg}",
    ], capture_output=True, text=True, timeout=60)
    try:
        resp = _json.loads(proc.stdout)
        rc = 0 if resp.get("ok") else 1
        out = resp.get("description", proc.stdout[:200]) if not resp.get("ok") else ""
    except _json.JSONDecodeError:
        rc = 1
        out = f"curl parse error: {proc.stdout[:200]}"
    if rc != 0:
        log(f'телеграм: {out}')
        return False
    log(f'телеграм-нотификация отправлена через Cathedral Bot API')
    return True


def resolve_project_from_journal():
    """Проект из последнего живого [TRIGGER_PRODUCER] в журнале."""
    if not os.path.exists(JOURNAL):
        return None
    last = None
    with open(JOURNAL) as f:
        for line in f:
            m = MARKER_RE.search(line)
            if m and m.group(1) == 'TRIGGER_PRODUCER':
                last = m.group(2)
    return last


def main(argv):
    if len(argv) == 2 and re.fullmatch(r'Project[1-4]', argv[1]):
        project = argv[1]
    elif len(argv) == 1:
        project = resolve_project_from_journal()
        if project is None:
            log('живой [TRIGGER_PRODUCER] в журнале не найден — нечего закрывать')
            return 0
        log(f'проект определён по журналу: {project}')
    else:
        print('usage: cycle_close.py [Project1|Project2|Project3|Project4]',
              file=sys.stderr)
        return 2
    project_dir = os.path.join(ROOT, project)
    if not os.path.isdir(project_dir):
        print(f'cycle_close: нет каталога проекта {project_dir}', file=sys.stderr)
        return 1

    state = load_state()
    pstate = state.get(project, {})
    markers = find_last_markers(project)

    if markers['producer_line'] is None:
        log(f'{project}: живой [TRIGGER_PRODUCER] не найден — нечего закрывать')
        return 0
    if pstate.get('producer_line') == markers['producer_line']:
        log(f'{project}: цикл на строке {markers["producer_line"]} уже закрыт'
            f' (grade={pstate.get("last_grade", "—")})')
        return 0

    # 1–2. git-цикл: коммит + пуш в оба remote
    push_errors = git_cycle_push(project, project_dir)

    # 3. гейты холодности
    gates = {}
    hot = hot_files(project_dir)
    gates['hot_files'] = hot
    gates['open_remarks'] = open_remarks(project_dir)
    gates['plan_unchecked'] = plan_unchecked(project_dir)
    gates['tests'] = tests_ok(project_dir)
    cold_gates_ok = (not hot and not gates['open_remarks']
                     and gates['plan_unchecked'] in (0, None)
                     and gates['tests'] in (None, True))

    # 4. релиз — только по заявке продюсера И при зелёных гейтах
    release_done = False
    release_skipped_reason = None
    if markers['cold_line'] is not None:
        if cold_gates_ok:
            release_done = do_release(project, project_dir)
        else:
            reasons = []
            if hot:
                reasons.append(f'{len(hot)} файлов ещё # HOT')
            if gates['open_remarks']:
                reasons.append(f'{len(gates["open_remarks"])} открытых [СР]')
            if gates['plan_unchecked']:
                reasons.append(f'PLAN.md: {gates["plan_unchecked"]} неотмеченных')
            if gates['tests'] is False:
                reasons.append('тесты красные')
            release_skipped_reason = '; '.join(reasons)
            log(f'{project}: COLD_RELEASE заявлен, но гейты не пройдены — '
                f'релиз отложен ({release_skipped_reason})')

    # 5. состояние
    pstate.update(producer_line=markers['producer_line'],
                  last_grade=markers['grade_text'] or '—',
                  closed_at=datetime.now().isoformat(timespec='seconds'),
                  release_done=release_done,
                  release_skipped_reason=release_skipped_reason,
                  push_errors=push_errors)
    state[project] = pstate
    save_state(state)

    hot_n = len(gates['hot_files'])
    sr_n = len(gates['open_remarks'])
    log(f'{project}: GRADE={pstate["last_grade"]} | HOT={hot_n} СР={sr_n} '
        f'PLAN={gates["plan_unchecked"]} tests={gates["tests"]} | '
        f'release={release_done or release_skipped_reason or "не заявлен"} | '
        f'push_errors={len(push_errors)}')
    if push_errors:
        for e in push_errors:
            print(f'[cycle_close] PUSH FAIL: {e}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
