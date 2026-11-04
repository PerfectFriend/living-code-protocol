# TASK CONTRACT v2 — заявки от Кодеров к Художнику и Музыканту

Версия: 2026-11-02. Заменяет «проза после маркера в журнале» машиночитаемой заявкой-файлом.

## Механика

1. Кодер (или Продюсер) пишет в `agents/journal.md` одну строку:
   - `[TRIGGER_ARTIST] <project> | tasks/art-<YYYYMMDD-HHMM>.md`
   - `[TRIGGER_MUSICIAN] <project> | tasks/snd-<YYYYMMDD-HHMM>.md`
   Путь относительный от `Projects/<project>/`.
2. Сама заявка — файл `Projects/<project>/tasks/art-…md` (шаблон: `agents/templates/art-task.md`) или `snd-…md` (`agents/templates/snd-task.md`). Старый формат (текст после маркера, без файла) поддерживается как фолбэк.
3. Художник (LV-artist, каждые 2ч в :30) / Музыкант (LV-dj-musician, каждые 2ч в :40) берут самую свежую заявку без ответа, исполняют, затем:
   - переименовывают заявку в `<file>.done`;
   - дописывают в `journal.md`: `[ART_DONE] <project> | <путь к артефакту> | <что сделано>` (соответственно `[SND_DONE]`).
4. Артефакты сохраняются в `Projects/<project>/assets/` (графика) и `assets/sounds/` (аудио) с именами из заявки. Коммит артефактов в git проекта — в цикле кодера.
5. Отчёты ролей: `reports/artist-*.md`, `reports/musician-*.md`; доставка — deliver задания (telegram:-1004431090317:252).

## Гейты качества (обязательны)

- Генерация: primary — `image_generate` (Nano Banana 2 = `fal-ai/nano-banana-2` через Nous gateway, edit: `fal-ai/nano-banana-2/edit`, до 14 референсов; альтернатива на OpenRouter: `google/gemini-nano-banana-2.1` / `google/gemini-3-pro-image`). При HTTP 402 (нет баланса) — фолбэк на локальный ComfyUI (:8188), ошибку фиксировать в отчёте.
- UI/скриншоты: `ui_gate` через laya_bridge (сервис :8731) по **скриншоту**, а не тексту (VISTA); для Flutter/Capacitor — нативный рендер-скриншот.
- Графика: vision-проверка по чеклисту заявки.
- Аудио: ffmpeg ebur128 — музыка −14 LUFS, речь −16 LUFS; без клиппинга; длительность в допуске.
- Повторы генерации: максимум 3; далее — лучший вариант + примечание в отчёте.

## Шаблон заявки

См. `agents/templates/art-task.md` и `agents/templates/snd-task.md`.
