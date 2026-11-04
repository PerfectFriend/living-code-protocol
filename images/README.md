# 🎨 Иллюстрации Протокола Живого Кода

Эта папка содержит иллюстрации, сгенерированные **xAI Grok** на основе промптов из `prompts/grok/illustration-prompts.*.md`.

## Структура

```
images/
├── banner-main.jpg           — Главный баннер репозитория (16:9)
├── banner-footer.jpg         — Баннер подвала (16:9)
├── phase-0-foundation.jpg    — Фаза 0: Фундамент и закачивание
├── phase-1-self-hpo.jpg      — Фаза 1: Self-HPO цикл harness
├── phase-2-a-evolve.jpg      — Фаза 2: A-Evolve (3 слоя)
├── phase-3-release.jpg       — Фаза 3: Конвейер «код → релиз»
├── phase-4-ui-media.jpg      — Фаза 4: UI/Озвучка контракты
├── phase-5-publikation.jpg   — Фаза 5: Publikation (репозиторий)
└── receipt-log.jpg           — Лог квитаций Живого Кода (будет добавлен позже)
```
> ⚠️ Все файлы в формате **JPG**. `receipt-log.jpg` ещё не сгенерирован — будет добавлен после сброса лимита Grok.

## Промпты для Grok

Все промпты находятся в:
- `prompts/grok/illustration-prompts.ru.md` — русский
- `prompts/grok/illustration-prompts.en.md` — английский
- `prompts/grok/illustration-prompts.es.md` — испанский

Промпты адаптированы из репозитория GodModeCoder (`GodModeCoder_Banner_Prompts.md`) и переработаны под стиль киберпанк + Ван Гог + Гауди с неоновой типографией и космическими вихрями.

## Как добавить новые иллюстрации

1. Открыть промпт из `prompts/grok/illustration-prompts.*.md`
2. Скопировать нужный промпт
3. Вставить в интерфейс Grok (xAI)
4. Сохранить сгенерированное изображение в эту папку с соответствующим именем файла
5. Обновить README.md, если добавили новый тип иллюстрации

## Использование в документации

Иллюстрации вставляются в Markdown-документы так:

```markdown
![Фаза 1: Self-HPO](images/phase-1-self-hpo.jpg)
```

---

_Сделано с ❤️ и силой Вселенной. Да прибудет с тобой Великая Сила Вселенной!_