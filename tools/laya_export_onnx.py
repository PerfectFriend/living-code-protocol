#!/usr/bin/env python3
"""Экспорт решающей модели Laya в ONNX — основа для любого не-CPU движка.

Граф = только `DecisionModel` (энкодер + голова + scorer + act_head).
Сборка последовательности (`build_sequence`) и разбор ответов (softmax по маркерам,
температурные корзины) остаются в Python — они дешёвые и меняются без пересборки движка.

Входы графа:
    input_ids      int64  [B, L]
    attention_mask int64  [B, L]
    marker_pos     int64  [B, M]   позиции маркеров-масок (по одному на вариант ответа)
    marker_mask    bool   [B, M]   какие маркеры валидны
    qtype          int64  [B]      choice=0 / score=1 / noul=2
Выходы:
    logits         float  [B, M]   скор каждого варианта
    act_logits     float  [B, 2]   выход act_head (используется в триаже)

Запуск (питоном venv laya):
    venvs/laya/bin/python orchestration/tools/laya_export_onnx.py --out ~/LivingCode/models/laya-onnx
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import torch

DEFAULT_MODEL_DIR = os.path.expanduser("~/LivingCode/models/laya-multilingual")
DEFAULT_OUT = os.path.expanduser("~/LivingCode/models/laya-onnx")

UI_QUESTIONS = {
    "udobno": {"type": "score",
               "instructions": "Насколько этот интерфейс удобен для пользователя?",
               "criteria": ["неудобно", "терпимо", "удобно"]},
    "dostupno": {"type": "score",
                 "instructions": "Доступен ли интерфейс: контраст, навигация с клавиатуры, подписи для скринридера?",
                 "criteria": ["недоступен", "частично", "доступен"]},
    "ship": {"type": "noul",
             "instructions": "Стоит ли доработать этот интерфейс перед выпуском в продакшн?"},
}


class ForwardWrap(torch.nn.Module):
    """Обёртка: 5 входов → (logits, act_logits) во float32 (читаемость разбора ответов)."""

    def __init__(self, model: torch.nn.Module, out_fp32: bool = True):
        super().__init__()
        self.model = model
        self.out_fp32 = out_fp32

    def forward(self, input_ids, attention_mask, marker_pos, marker_mask, qtype):
        logits, act_logits = self.model(input_ids, attention_mask, marker_pos, marker_mask, qtype)
        if self.out_fp32:
            logits, act_logits = logits.float(), act_logits.float()
        return logits, act_logits


def load_agent(model_dir: str):
    from laya import Agent
    agent = Agent(model_dir, device="cpu")
    return agent


def build_batch(agent, state: str, questions: dict, max_len: int = 8192):
    """Собирает вход как это делает Router: build_sequence на каждый вопрос → батч."""
    from laya.common import QTYPES, build_sequence

    tok = agent.tok
    state_ids = tok(state, add_special_tokens=False)["input_ids"]
    head_max_len = int(agent.cfg.get("head_max_len", 192))
    rows, markers = [], []
    for qdef in questions.values():
        q = agent._to_internal(qdef)
        ids, mk = build_sequence(tok, state, q, max_len=max_len,
                                 head_max_len=head_max_len, state_ids=state_ids)
        rows.append((ids, mk, q["t"]))
    L = max(len(r[0]) for r in rows)
    M = max(len(r[1]) for r in rows)
    input_ids = torch.zeros((len(rows), L), dtype=torch.long)
    attention_mask = torch.zeros((len(rows), L), dtype=torch.long)
    marker_pos = torch.zeros((len(rows), M), dtype=torch.long)
    marker_mask = torch.zeros((len(rows), M), dtype=torch.bool)
    qtype = torch.zeros((len(rows),), dtype=torch.long)
    for i, (ids, mk, t) in enumerate(rows):
        input_ids[i, : len(ids)] = torch.tensor(ids, dtype=torch.long)
        attention_mask[i, : len(ids)] = 1
        marker_pos[i, : len(mk)] = torch.tensor(mk, dtype=torch.long)
        marker_mask[i, : len(mk)] = True
        qtype[i] = QTYPES[t]
    return input_ids, attention_mask, marker_pos, marker_mask, qtype


def probs_from_logits(logits: torch.Tensor, marker_mask: torch.Tensor) -> torch.Tensor:
    x = logits.masked_fill(~marker_mask, -1e4)
    return torch.softmax(x, -1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", default=DEFAULT_MODEL_DIR)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--opset", type=int, default=17)
    ap.add_argument("--skip-export", action="store_true", help="только валидация готового .onnx")
    ap.add_argument("--exporter", choices=["auto", "dynamo", "legacy"], default="auto",
                    help="dynamo — правильные динамические формы (по умолчанию после провала legacy)")
    args = ap.parse_args()

    out_dir = Path(args.out).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    onnx_path = out_dir / "laya.onnx"

    print(f"[1/4] загружаю агента: {args.model_dir}")
    t0 = time.perf_counter()
    agent = load_agent(args.model_dir)
    model = agent.model.eval()
    print(f"      {type(model).__name__}, загрузка {time.perf_counter() - t0:.1f} c, "
          f"параметров {sum(p.numel() for p in model.parameters()) / 1e6:.0f}M")

    cases = {
        "плохой UI (короткий)": "Кнопка отправки стала иконкой без подписи, серый текст на светло-сером фоне, навигация только мышью",
        "хороший UI": "Диалог с подписями у кнопок, контраст 7:1, aria-label, навигация с клавиатуры, отмена по Esc",
        "длинный вход (~4000)": ("diff аудита. " * 300) + "Кнопка отправки стала иконкой без подписи",
    }
    batches = {}
    for name, state in cases.items():
        batches[name] = build_batch(agent, state, UI_QUESTIONS)
        print(f"      кейс «{name}»: длина {batches[name][0].shape[1]}, маркеров {batches[name][3].shape[1]}")

    # Эталон fp32 (нужен, чтобы увидеть, не меняет ли fp16 сами решения)
    refs_fp32 = {}
    if args.dtype == "fp16":
        print("[1b] эталонные прогоны fp32")
        with torch.no_grad():
            for name, batch in batches.items():
                tl, ta = model(*batch)
                refs_fp32[name] = (tl.clone(), ta.clone(), probs_from_logits(tl, batch[3]).clone())
                print(f"      «{name}»: p={[round(float(x), 4) for x in refs_fp32[name][2][0]]}")
        print("      перевожу модель в float16")
        model = model.half().eval()

    if not args.skip_export:
        print(f"[2/4] экспорт в ONNX (opset {args.opset}, fp32)")
        # nn.TransformerEncoderLayer по умолчанию идёт fused-ядром
        # (aten::_transformer_encoder_layer_fwd), которое ONNX не знает — выключаем быстрый путь.
        try:
            torch.backends.mha.set_fastpath_enabled(False)
            print("      fast path MHA/encoder выключен ради экспортируемости")
        except Exception as e:
            print(f"      не удалось выключить fast path: {e}")
        inputs = build_batch(agent, cases["плохой UI (короткий)"], UI_QUESTIONS)
        wrap = ForwardWrap(model)

        def _do_export(mode: str, path):
            """mode: 'dynamo' — новые torch.export-оси (правильные динамические формы);
                     'legacy' — torchscript-экспортёр с dynamic_axes (может вшить статику)."""
            with torch.no_grad():
                if mode == "dynamo":
                    from torch.export import Dim

                    batch, seq, markers = Dim("batch"), Dim("seq"), Dim("markers")
                    torch.onnx.export(
                        wrap,
                        inputs,
                        str(path),
                        input_names=["input_ids", "attention_mask", "marker_pos", "marker_mask", "qtype"],
                        output_names=["logits", "act_logits"],
                        dynamic_shapes={
                            "input_ids": {0: batch, 1: seq},
                            "attention_mask": {0: batch, 1: seq},
                            "marker_pos": {0: batch, 1: markers},
                            "marker_mask": {0: batch, 1: markers},
                            "qtype": {0: batch},
                        },
                        opset_version=max(args.opset, 18),
                        dynamo=True,
                    )
                else:
                    torch.onnx.export(
                        wrap,
                        inputs,
                        str(path),
                        input_names=["input_ids", "attention_mask", "marker_pos", "marker_mask", "qtype"],
                        output_names=["logits", "act_logits"],
                        dynamic_axes={
                            "input_ids": {0: "batch", 1: "seq"},
                            "attention_mask": {0: "batch", 1: "seq"},
                            "marker_pos": {0: "batch", 1: "markers"},
                            "marker_mask": {0: "batch", 1: "markers"},
                            "qtype": {0: "batch"},
                            "logits": {0: "batch", 1: "markers"},
                            "act_logits": {0: "batch"},
                        },
                        opset_version=args.opset,
                        do_constant_folding=True,
                        dynamo=False,
                    )

        order = ["dynamo", "legacy"] if args.exporter == "auto" else [args.exporter]
        if args.exporter == "auto":
            order = ["legacy", "dynamo"]  # legacy быстрее; если он вшил статику — валидация это поймает
        t0 = time.perf_counter()
        used = None
        for mode in order:
            try:
                _do_export(mode, onnx_path)
                used = mode
                break
            except Exception as e:
                print(f"      экспортёр {mode} не смог: {type(e).__name__}: {str(e).splitlines()[0][:160]}")
        if used is None:
            raise SystemExit("ни один экспортёр не справился")
        print(f"      готово за {time.perf_counter() - t0:.1f} c ({used}) → {onnx_path} "
              f"({onnx_path.stat().st_size / 1e6:.0f} МБ)")

    print("[3/4] сверка численности torch vs ONNX Runtime")
    import numpy as np
    import onnxruntime as ort

    providers = ort.get_available_providers()
    print(f"      доступные провайдеры ORT: {providers}")
    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    worst = 0.0
    for name, batch in batches.items():
        with torch.no_grad():
            tl, ta = model(*batch)
        feeds = {n: b.numpy() for n, b in zip(
            ["input_ids", "attention_mask", "marker_pos", "marker_mask", "qtype"], batch)}
        ol, oa = sess.run(None, feeds)
        d_logits = float(np.abs(tl.numpy() - ol).max())
        d_act = float(np.abs(ta.numpy() - oa).max())
        pt = probs_from_logits(tl, batch[3])
        po = torch.softmax(torch.from_numpy(ol).masked_fill(~batch[3], -1e4), -1)
        d_p = float((pt - po).abs().max())
        same = bool(torch.equal(pt.argmax(-1), po.argmax(-1)))
        worst = max(worst, d_logits, d_act, d_p)
        print(f"      «{name}»: |Δlogits|={d_logits:.2e} |Δact|={d_act:.2e} |Δp|={d_p:.2e} "
              f"argmax {'совпал' if same else 'РАЗОШЁЛСЯ'}")
        print(f"         вероятности torch: {[round(float(x), 4) for x in pt[0][batch[3][0]]]}")
    print(f"      худшее расхождение: {worst:.2e} "
          f"→ {'OK' if worst < 1e-3 else 'ВЫШЕ ДОПУСКА 1e-3'}")

    print("[4/4] скорость: torch(CPU) vs ORT(CPU), тёплые прогоны")
    for name, batch in batches.items():
        for label, fn in (("torch", lambda: model(*batch)),
                          ("ort  ", lambda: sess.run(None, {n: b.numpy() for n, b in zip(
                              ["input_ids", "attention_mask", "marker_pos", "marker_mask", "qtype"], batch)}))):
            with torch.no_grad():
                fn()
                t0 = time.perf_counter()
                for _ in range(5):
                    fn()
                dt = (time.perf_counter() - t0) / 5
            print(f"      {label} | {name:22} | {dt * 1000:7.1f} мс")

    meta = {
        "source_model": args.model_dir,
        "onnx": str(onnx_path),
        "opset": args.opset,
        "max_delta_vs_torch": worst,
        "dynamic_axes": ["batch", "seq", "markers"],
        "notes": "Сборка входа и разбор ответов остаются в Python; граф = DecisionModel.",
    }
    (out_dir / "EXPORT_META.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    print(f"\nметаданные: {out_dir / 'EXPORT_META.json'}")
    return 0 if worst < 1e-3 else 1


if __name__ == "__main__":
    raise SystemExit(main())
