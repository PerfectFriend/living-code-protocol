# Laya на GPU этого узла: что проверено, где стена

Статус: **отложено. Рабочий путь — CPU (torch). GPU через Vulkan не достигнут, но и не опровергнут:**
упёрлись в оперативную память узла, а не в поддержку Vulkan.

Решение владельца (27 сен 2026): остаёмся на CPU, тёплые 30–90 мс на `ui_gate`/`triage`/`verdict`
устраивают; GPU заводить только если появится задача на длинные входы или массовые прогоны.

## Железо и стек (проверено)

| Что | Значение |
|---|---|
GPU | AMD Radeon 780M, `gfx1103` (HawkPoint/Phoenix), `c4:00.0`, renderD128
Драйвер | Mesa 26.0.8, **Vulkan 1.4.335 через RADV** (`AMD Radeon 780M Graphics (RADV PHOENIX)`) ✓
OpenGL | 4.6 (radeonsi, ACO)
ROCm | отсутствует (`rocminfo` нет) → ROCm-путь для этого чипсета закрыт
OpenCL | ICD нет вообще (`/etc/OpenCL/vendors` не существует)
torch | 2.14.0+cpu — ускорителей не видит (`cuda/xpu/mps` = False)
RAM | 15 ГБ всего, ~6 ГБ уходит в shared под iGPU, реально свободно 4–5 ГБ

Вывод по стеку: на этом чипсете из ускорителей доступен **только Vulkan (RADV)**; резерв — rusticl OpenCL.

## Почему модель вообще портируема

`Laya` = `ModernBertForMaskedLM` (22 слоя, hidden 768, 12 голов, vocab 256k, max_pos 8192,
чередование full/sliding attention с окном 128, RoPE, gelu) + голова `DecisionModel`:
2-слойный `TransformerEncoder` (norm_first), `type_emb`, и **`scorer`** — `LayerNorm→Linear(768,768)→GELU→Linear(768,1)`,
применяемый к скрытым состояниям **в позициях маркеров-масок**. Решение = `masked_fill` + softmax по маркерам;
`act_head` работает по pooled `[CLS]` + 4 признака.

Экзотических операторов нет — только MatMul/LayerNorm/GELU/softmax/gather. Поэтому граф переносим
в любой трансформерный рантайм, а readout (сборка входа `build_sequence`, температурные корзины,
пороговые решения) остаётся в Python и пересборки движка не требует.

## Что сделано и подтверждено

1. **`orchestration/tools/laya_export_onnx.py`** — экспорт `DecisionModel` в ONNX со сверкой численности.
   - Классический (torchscript) экспортёр **непригоден**: вшивает статические формы
     (на другой длине падает `Reshape`: `{87,3,768} → {83,36,64}`) и даёт мусор в `act_logits` (Δ ≈ 62).
   - Рабочий путь — **dynamo-экспортёр** с явными `torch.export.Dim` осями (batch/seq/markers), opset 18.
     Требуется `onnxscript` (дописал в venv laya).
   - **`nn.TransformerEncoderLayer` идёт fused-ядром `aten::_transformer_encoder_layer_fwd`, которое ONNX не знает** —
     перед экспортом обязателен `torch.backends.mha.set_fastpath_enabled(False)`.
   - Артефакт: `models/laya-onnx/laya.onnx` (3 МБ граф) + `laya.onnx.data` (1.29 ГБ, внешние данные).
2. **Численность сверена против torch** (ONNX Runtime, CPU EP):

   | Кейс | \|Δlogits\| | \|Δact\| | \|Δp\| | argmax |
   |---|---|---|---|---|
   | плохой UI (83 токена) | 3.8e-06 | 1.2e-04 | 1.4e-06 | совпал |
   | хороший UI (87 токенов) | 3.9e-06 | 2.4e-04 | 9.5e-07 | совпал |
   | длинный вход (1266 токенов) | 4.8e-06 | 1.2e-03 | 8.1e-07 | совпал |

   Экспорт верен: расхождение на уровне float-шума, решения идентичны.
3. **Замер скорости (тёплые прогоны, CPU)**: torch 110 мс / ORT 142 мс (короткий), torch 114 / ORT 98 (средний),
   **torch 2921 мс / ORT 4917 мс (1266 токенов)**.
   → **ORT-CPU медленнее torch-CPU**, поэтому ONNX на CPU смысла не имеет: он ценен только как заготовка под GPU.
4. **IREE видит наше Vulkan-устройство**: `iree-run-module --list_devices` → `vulkan://00000000-c400-0000-0000-000000000000`.
   Вендор IREE 3.11.0rc20260316 в `venvs/iree` (500 МБ).

## Стена

`iree-import-onnx laya.onnx` на fp32-весах (1.29 ГБ) **раздувается до 5.6 ГБ RSS и гибнет от OOM-killer**
(дважды, в т.ч. под `systemd-run -p MemoryMax=6000M`). Свободной памяти на узле 4–5 ГБ при живом десктопе.

Что это **не** значит: что Vulkan/IREE не умеют эту модель. Блокер — только память на этапе импорта.

## Следующий шаг, когда освободится память (рецепт)

1. Экспорт в **fp16** (веса 645 МБ → импорт ориентировочно ~2.8 ГБ, что уже влезает):
   ```bash
   venvs/laya/bin/python orchestration/tools/laya_export_onnx.py --dtype fp16 --exporter dynamo
   ```
   Скрипт уже умеет `--dtype fp16`: сначала снимает эталон fp32, потом переводит модель в half,
   наружу отдаёт `float()` — readout остаётся тем же. Проверять: совпадение `argmax` с fp32-эталоном
   (числа могут разойтись на ~1e-2 — это допустимо для fp16).
2. Импорт и компиляция под Vulkan (обязательно **по одному процессу**, иначе OOM):
   ```bash
   B=~/LivingCode/venvs/iree/bin
   cd ~/LivingCode/models/laya-onnx
   $B/iree-import-onnx laya_fp16.onnx -o laya.mlir
   $B/iree-compile --iree-hal-target-backends=vulkan-spirv laya.mlir -o laya_vulkan.vmfb
   ```
3. Прогон и замер: `iree-run-module --device=vulkan --module=laya_vulkan.vmfb --function=main …`
   Сравнивать на **длинных** входах (≥1000 токенов) — именно там CPU упирается (2.9 с и хуже).

Запускать тяжёлое — только через `systemd-run --user -p MemoryMax=…`, чтобы OOM убивал задачу,
а не рабочий стол: `nohup`-процессы не переживают остановку бэкенда Hermes, а два процесса по 3 ГБ
роняют и Плазму, и Hermes.

## Тупики, которые не надо повторять

- **llama.cpp/GGUF + Vulkan — мимо.** llama.cpp отдаёт pooled-эмбеддинги, а Laya решает по **логитам
  в позициях маркеров**. Readout через этот интерфейс не вытащить.
- **ONNX Runtime как GPU-путь на AMD/Linux — мимо.** В ORT есть CUDA/TensorRT/ROCm/MIGraphX/DML/OpenVINO,
  но **Vulkan EP не существует**; доступные у нас провайдеры — `AzureExecutionProvider`, `CPUExecutionProvider`.
- Azure EP настроен и доступен (`ort.get_available_providers()`), но это облако, не локальный GPU.

## Что даёт больше, чем GPU, на этом узле (дешевле и без риска)

1. **Тёплый сервис вместо CLI**: `laya-serve` (есть в пакете, поддерживает `LAYA_DEVICE`, `LAYA_THREADS`,
   эндпоинт `/systemone`). Сейчас каждый вызов `laya_bridge.py` платит загрузку чекпоинта — от 4.6 с
   (пусто) до **100 с** (нагруженная машина). В сервисе остаются чистые 30–90 мс.
2. **Батчить `score`**: сейчас мост делает до 30 последовательных `predict` (по одному на строку);
   строки можно подать одним forward с паддингом и attention-mask (вопрос — один), это ~10×.
3. **Ограничить длину входа**: 1000 симв. → 0.33 с, 4000 → 1.98 с, 8000 → 4.93 с. Для гейта и триажа
   достаточно ~1500–2000 символов; снизить `--max-chars` для этих режимов.
4. **int8-квантизация энкодера** для CPU — обычно 1.5–3× на таком размере.
