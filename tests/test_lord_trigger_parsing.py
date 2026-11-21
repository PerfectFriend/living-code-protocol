"""Тесты парсера триггеров Lord of Code.

Дефект 2026-09-29: `lord_of_code.py` искал `\\[TRIGGER_LORD\\]\\s*(\\S+)` по всему
тексту журнала, поэтому ловил не только настоящие строки-триггеры, но и УПОМИНАНИЯ
маркера внутри прозы (в т.ч. в записях самого Владыки: «последний [TRIGGER_LORD] —
от 24.09»). Последнее такое упоминание давало проект `—`, и каждый час рождался
отчёт-заглушка `# Lord Report ... Project: —` + в журнал дописывалась мусорная
строка `[TRIGGER_PRODUCER] —`.

Правило: настоящий триггер — только ОТДЕЛЬНАЯ строка вида `[TRIGGER_LORD] project`.
"""
import sys
from pathlib import Path

SCRIPTS = Path('/home/thomas/LivingCode/orchestration/scripts')
sys.path.insert(0, str(SCRIPTS))

from lord_of_code import parse_last_trigger, main, update_hot_cold_markers  # noqa: E402


def test_ignores_prose_mention_with_dash():
    """Упоминание маркера внутри прозы не является триггером."""
    journal = (
        'Протокол: последний [TRIGGER_LORD] — от 24.09, новых нет,\n'
        'поэтому часовой проход холостой: ~20 отчётов-заглушек.\n'
    )
    assert parse_last_trigger(journal) is None


def test_detects_standalone_trigger_line():
    assert parse_last_trigger('[TRIGGER_LORD] superguard\n') == 'superguard'


def test_detects_standalone_trigger_with_trailing_spaces():
    assert parse_last_trigger('[TRIGGER_LORD]   cybertarot  \n') == 'cybertarot'


def test_last_standalone_line_wins():
    journal = '[TRIGGER_LORD] superguard\n\n[TRIGGER_LORD] elemental-life-2\n'
    assert parse_last_trigger(journal) == 'elemental-life-2'


def test_prose_mention_after_standalone_does_not_override():
    """Реальный сценарий поломки: standalone-триггер, а после него проза с «—».

    Фикстура НЕ содержит заголовка вердикта — проверяется ровно одно свойство:
    прозаическое упоминание маркера не перебивает настоящую строку-триггер.
    (Отдельно, test_trigger_before_last_verdict_is_stale: с заголовком вердикта
    тот же триггер считается потреблённым и даёт None.)
    """
    journal = (
        '[TRIGGER_LORD] elemental-life-2\n'
        '\n'
        '## [2026-09-29 21:28] реплика аудитора: разбирал [TRIGGER_LORD] elemental-life-2 (стр. 292)\n'
        'Протокол: последний [TRIGGER_LORD] — от 24.09, новых нет.\n'
    )
    assert parse_last_trigger(journal) == 'elemental-life-2'


def test_placeholder_tokens_are_not_triggers():
    for bad in ('—', '-', '.', '..', '?', 'N/A'):
        assert parse_last_trigger(f'[TRIGGER_LORD] {bad}\n') is None


def test_trigger_before_last_verdict_is_stale():
    """Триггер, на который Владыка уже вынес вердикт, потреблён."""
    journal = (
        '[TRIGGER_LORD] elemental-life-2\n'
        '\n'
        '## [2026-09-29 21:28] Lord of Code — вердикт по [TRIGGER_LORD] elemental-life-2 (стр. 292)\n'
        'Вердикт: НЕ ЗАМОРОЖЕН.\n'
    )
    assert parse_last_trigger(journal) is None


def test_live_trigger_after_last_verdict_is_detected():
    journal = (
        '[TRIGGER_LORD] elemental-life-2\n'
        '## [2026-09-29 21:28] Lord of Code — вердикт по [TRIGGER_LORD] elemental-life-2 (стр. 292)\n'
        'Вердикт: НЕ ЗАМОРОЖЕН.\n'
        '\n'
        '[TRIGGER_LORD] cybertarot\n'
    )
    assert parse_last_trigger(journal) == 'cybertarot'


def test_empty_journal_returns_none():
    assert parse_last_trigger('') is None


def test_main_is_idle_without_trigger(tmp_path):
    """Холостой проход: ни отчёта-заглушки, ни мусорной строки в журнале."""
    journal = tmp_path / 'journal.md'
    original = 'Протокол: последний [TRIGGER_LORD] — от 24.09, новых нет.\n'
    journal.write_text(original, encoding='utf-8')
    reports = tmp_path / 'reports'
    reports.mkdir()
    projects = tmp_path / 'Projects'
    projects.mkdir()

    main(journal_path=str(journal), reports_dir=str(reports),
         projects_root=str(projects), do_send=False)

    assert list(reports.iterdir()) == []
    assert journal.read_text(encoding='utf-8') == original


def test_main_does_not_emit_producer_for_unknown_project(tmp_path):
    """Триггер на несуществующий проект: без заглушки и без [TRIGGER_PRODUCER]."""
    journal = tmp_path / 'journal.md'
    original = '[TRIGGER_LORD] no-such-project-xyz\n'
    journal.write_text(original, encoding='utf-8')
    reports = tmp_path / 'reports'
    reports.mkdir()
    projects = tmp_path / 'Projects'
    projects.mkdir()

    main(journal_path=str(journal), reports_dir=str(reports),
         projects_root=str(projects), do_send=False)

    assert '[TRIGGER_PRODUCER]' not in journal.read_text(encoding='utf-8')


def test_main_does_not_emit_producer_for_real_project(tmp_path):
    """[TRIGGER_PRODUCER] пишет Владыка после заморозки, а не скрипт-обёртка."""
    journal = tmp_path / 'journal.md'
    journal.write_text('[TRIGGER_LORD] demo\n', encoding='utf-8')
    reports = tmp_path / 'reports'
    reports.mkdir()
    projects = tmp_path / 'Projects'
    (projects / 'demo').mkdir(parents=True)
    (projects / 'demo' / 'a.py').write_text('print(1)\n', encoding='utf-8')

    main(journal_path=str(journal), reports_dir=str(reports),
         projects_root=str(projects), do_send=False)

    text = journal.read_text(encoding='utf-8')
    assert '[TRIGGER_PRODUCER]' not in text
    assert list(reports.iterdir()), 'отчёт по настоящему триггеру должен появиться'


# --- Изоляция маркерного прохода -------------------------------------------
# Эмпирический RED (29.09 22:41): прогон тестов вызвал update_hot_cold_markers,
# захардкоженный корень обошёл ЖИВОЕ дерево Projects/ и вписал '# HOT' первой
# строкой в linux/flutter/generated_plugins.cmake проекта elemental-life-2.

def test_marker_walker_honors_projects_root(tmp_path):
    """Обход идёт по переданному корню и не выходит за него."""
    root = tmp_path / 'Projects'
    (root / 'proj').mkdir(parents=True)
    (root / 'proj' / 'a.py').write_text('print(1)\n', encoding='utf-8')
    outside = tmp_path / 'control.py'
    outside.write_text('print(2)\n', encoding='utf-8')

    update_hot_cold_markers(str(root / 'proj'), projects_root=str(root))

    assert (root / 'proj' / 'a.py').read_text(encoding='utf-8').startswith('# HOT\n')
    assert outside.read_text(encoding='utf-8') == 'print(2)\n'


def test_marker_walker_skips_markdown_and_json(tmp_path):
    """Ведущая '# HOT' в .md/.json — тот самый мусор; такие файлы не трогаем."""
    root = tmp_path / 'Projects'
    (root / 'proj').mkdir(parents=True)
    md = root / 'proj' / 'README.md'
    md.write_text('# Title\n', encoding='utf-8')
    js = root / 'proj' / 'STATE.json'
    js.write_text('{"a": 1}\n', encoding='utf-8')

    update_hot_cold_markers(str(root / 'proj'), projects_root=str(root))

    assert md.read_text(encoding='utf-8') == '# Title\n'
    assert js.read_text(encoding='utf-8') == '{"a": 1}\n'
