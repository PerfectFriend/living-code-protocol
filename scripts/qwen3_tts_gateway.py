#!/usr/bin/env python3
"""
Qwen3-TTS Gateway Integration for Hermes
Called by Hermes gateway for TTS generation using qwen_tts Python package.
"""

import sys
import os
import json
import tempfile
import subprocess
import argparse
from pathlib import Path

# Add the venv site-packages to path
VENV_PYTHON = "/home/thomas/.venv-tts11/bin/python"
VENV_SITE = "/home/thomas/.venv-tts11/lib/python3.11/site-packages"
sys.path.insert(0, VENV_SITE)

REFERENCE_AUDIO = "/tmp/reference.wav"
REFERENCE_TEXT = """Осколько она открытий, чудных, готовит просвещение дух и опыт сына шибактрудных и гений парадоксов друг, и  случай Бог изобретатель, и дивный сон, и дейсоздатель, и  полет мечты, и все такое. И пусть будет ничего другого. Ты должен склонировать этот голос как  это лом, чтобы использовать в будущем. Пожалуйста, сделай это хорошо. И отвечай мне пред только на этом  голосе, только использую этот голос в качестве источника для синтеза. Все прочие вареанты синтеза должны  быть уничтожены, чтобы не было такой возможности даже синтезировать что-то другим голосом, чтобы  в системе просто отсутствовали какие-то другие возможности синтеза голоса, кроме вот этого,  который я сейчас тебе мадиктовал."""

MODEL_NAME = "Qwen/Qwen3-TTS-12Hz-1.7B-Base"


def synthesize(text: str, output_path: str, language: str = "ru") -> bool:
    """Generate cloned speech using Qwen3-TTS."""
    try:
        from qwen_tts import Qwen3TTSModel
        import torch
        import soundfile as sf

        print(f"[Qwen3-TTS] Loading model {MODEL_NAME} on CPU...", file=sys.stderr)
        model = Qwen3TTSModel.from_pretrained(
            MODEL_NAME,
            device_map="cpu",
            dtype=torch.bfloat16,
        )
        print("[Qwen3-TTS] Model loaded", file=sys.stderr)

        print(f"[Qwen3-TTS] Generating speech for: {text[:50]}...", file=sys.stderr)
        wavs, sr = model.generate_voice_clone(
            text=text,
            ref_audio=REFERENCE_AUDIO,
            ref_text=REFERENCE_TEXT,
        )
        print(f"[Qwen3-TTS] Generated: {len(wavs)} segments, sr={sr}", file=sys.stderr)

        # Write WAV
        sf.write(output_path, wavs[0], sr)
        print(f"[Qwen3-TTS] Saved WAV to {output_path}", file=sys.stderr)

        # Convert to Opus/OGG for Telegram
        ogg_path = output_path.replace(".wav", ".ogg")
        subprocess.run([
            "ffmpeg", "-y", "-i", output_path,
            "-c:a", "libopus", "-b:a", "12k", "-vbr", "on",
            ogg_path
        ], check=True, capture_output=True)
        print(f"[Qwen3-TTS] Converted to OGG: {ogg_path}", file=sys.stderr)

        return True

    except Exception as e:
        print(f"[Qwen3-TTS] ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="Qwen3-TTS Gateway TTS")
    parser.add_argument("--text", required=True, help="Text to synthesize")
    parser.add_argument("--output", required=True, help="Output file path (wav)")
    parser.add_argument("--language", default="ru", help="Language code")
    parser.add_argument("--speaker", help="Speaker reference (ignored, uses fixed ref)")

    args = parser.parse_args()

    success = synthesize(args.text, args.output, args.language)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()