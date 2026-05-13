#!/usr/bin/env python3
"""
Batch voice-cloning TTS for VieNeu-TTS.

Input:
- voice/*.wav (reference voice audio, 3-5s recommended)
- voice/voice.txt (transcript of reference audio)
- text/*.txt (texts to synthesize)

Output:
- output/*.wav
"""

from __future__ import annotations

import argparse
import json
import tempfile
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Iterable

import numpy as np
import soundfile as sf
from audio_postprocess import PostProcessConfig, process_wav_file


def pick_reference_audio(voice_dir: Path) -> Path:
    exts = {".wav", ".mp3", ".flac", ".m4a", ".ogg"}
    audios = sorted(
        p for p in voice_dir.iterdir()
        if p.is_file() and p.suffix.lower() in exts
    )
    if not audios:
        raise FileNotFoundError(f"No audio file found in {voice_dir} (supported: {sorted(exts)})")
    return audios[0]


def read_ref_text(voice_dir: Path) -> str:
    preferred = voice_dir / "voice.txt"
    if preferred.exists():
        text = preferred.read_text(encoding="utf-8").strip()
        if text:
            return text
    txts = sorted(voice_dir.glob("*.txt"))
    for p in txts:
        text = p.read_text(encoding="utf-8").strip()
        if text:
            return text
    raise FileNotFoundError(f"No non-empty .txt found in {voice_dir} (expected voice.txt)")


@dataclass
class VoiceProfile:
    name: str
    profile_dir: Path
    ref_audio: Path
    ref_text: str


def discover_voice_profiles(voice_root: Path) -> list[VoiceProfile]:
    profiles: list[VoiceProfile] = []
    subdirs = sorted(p for p in voice_root.iterdir() if p.is_dir())
    for subdir in subdirs:
        try:
            ref_audio = pick_reference_audio(subdir)
            ref_text = read_ref_text(subdir)
        except FileNotFoundError:
            continue
        profiles.append(
            VoiceProfile(
                name=subdir.name,
                profile_dir=subdir,
                ref_audio=ref_audio,
                ref_text=ref_text,
            )
        )
    return profiles


def merge_wav_files(input_paths: Iterable[Path], output_path: Path) -> Path:
    ordered = list(input_paths)
    if not ordered:
        raise ValueError("No input audio files provided for merge.")

    merged_chunks = []
    sample_rate = None
    channels = None

    for wav_path in ordered:
        audio, sr = sf.read(str(wav_path), dtype="float32", always_2d=True)
        if sample_rate is None:
            sample_rate = sr
            channels = audio.shape[1]
        elif sr != sample_rate:
            raise ValueError(
                f"Sample rate mismatch in {wav_path.name}: {sr} != {sample_rate}"
            )
        elif audio.shape[1] != channels:
            raise ValueError(
                f"Channel mismatch in {wav_path.name}: {audio.shape[1]} != {channels}"
            )
        merged_chunks.append(audio)

    merged = np.concatenate(merged_chunks, axis=0)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output_path), merged, sample_rate)
    return output_path


def _highpass(signal: np.ndarray, sr: int, cutoff_hz: float) -> np.ndarray:
    rc = 1.0 / (2.0 * np.pi * cutoff_hz)
    dt = 1.0 / float(sr)
    alpha = rc / (rc + dt)
    out = np.zeros_like(signal)
    out[0] = signal[0]
    for i in range(1, signal.shape[0]):
        out[i] = alpha * (out[i - 1] + signal[i] - signal[i - 1])
    return out


def preprocess_reference_audio(input_path: Path, output_path: Path) -> Path:
    audio, sr = sf.read(str(input_path), dtype="float32", always_2d=True)
    mono = audio.mean(axis=1)
    mono = _highpass(mono, sr, 55.0)
    abs_mono = np.abs(mono)
    if abs_mono.size:
        thr = max(0.01, float(np.percentile(abs_mono, 65) * 0.28))
        idx = np.flatnonzero(abs_mono > thr)
        if idx.size > 0:
            start = max(0, int(idx[0]) - int(0.08 * sr))
            end = min(len(mono), int(idx[-1]) + int(0.08 * sr))
            mono = mono[start:end]
    peak = float(np.max(np.abs(mono))) if mono.size else 0.0
    if peak > 1e-6:
        mono = mono * (0.92 / peak)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output_path), mono, sr)
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch clone TTS with VieNeu-TTS backend")
    parser.add_argument("--project-root", type=Path, default=Path("VieNeu-TTS"))
    parser.add_argument("--voice-dir", type=Path, default=Path("voice"))
    parser.add_argument("--text-dir", type=Path, default=Path("text"))
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--voice-profile", type=str, default="")
    parser.add_argument("--combined-output", type=Path, default=Path("../source_full/audio/combined.wav"))
    parser.add_argument("--manifest-path", type=Path, default=Path("output/manifest.json"))
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--top-k", type=int, default=80)
    parser.add_argument("--max-chars", type=int, default=420)
    parser.add_argument("--device", type=str, default="auto", choices=["auto", "cpu", "cuda"])
    parser.add_argument("--postprocess", action="store_true")
    parser.add_argument("--noise-reduction", type=float, default=0.12)
    parser.add_argument("--highpass-hz", type=float, default=70.0)
    parser.add_argument("--lowpass-hz", type=float, default=10500.0)
    parser.add_argument("--target-peak-db", type=float, default=-1.5)
    parser.add_argument("--comp-threshold-db", type=float, default=-22.0)
    parser.add_argument("--comp-ratio", type=float, default=1.4)
    parser.add_argument("--make-up-gain-db", type=float, default=0.0)
    parser.add_argument("--presence-boost-db", type=float, default=0.4)
    parser.add_argument("--de-ess", type=float, default=0.30)
    parser.add_argument("--gate-strength", type=float, default=0.20)
    parser.add_argument("--preprocess-reference", action="store_true")
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    voice_dir = args.voice_dir.resolve()
    text_dir = args.text_dir.resolve()
    output_dir = args.output_dir.resolve()
    combined_output = args.combined_output.resolve()
    manifest_path = args.manifest_path.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not project_root.exists():
        raise FileNotFoundError(f"Project root not found: {project_root}")
    if not voice_dir.exists():
        raise FileNotFoundError(f"Voice dir not found: {voice_dir}")
    if not text_dir.exists():
        raise FileNotFoundError(f"Text dir not found: {text_dir}")

    # Make local source importable: VieNeu-TTS/src
    sys.path.insert(0, str(project_root / "src"))

    from vieneu import Vieneu  # pylint: disable=import-error

    profiles = discover_voice_profiles(voice_dir)
    if not profiles:
        raise FileNotFoundError(
            f"No valid voice profile found in {voice_dir}. "
            "Expected subfolders: voice/<profile_name>/ with audio + voice.txt"
        )

    selected: VoiceProfile | None = None
    if args.voice_profile:
        selected = next((p for p in profiles if p.name == args.voice_profile), None)
        if selected is None:
            names = ", ".join(p.name for p in profiles)
            raise FileNotFoundError(
                f"Voice profile '{args.voice_profile}' not found. Available: {names}"
            )
    else:
        selected = profiles[0]

    ref_audio = selected.ref_audio
    ref_text = selected.ref_text
    print(f"Reference text length: {len(ref_text)} chars")
    text_files = sorted(text_dir.glob("*.txt"))
    if not text_files:
        raise FileNotFoundError(f"No .txt files found in {text_dir}")

    print("=== VieNeu Batch Clone ===")
    print(f"Project root : {project_root}")
    print(f"Voice profile: {selected.name}")
    print(f"Reference wav: {ref_audio.name}")
    print(f"Text files   : {len(text_files)}")
    print(f"Output dir   : {output_dir}")

    # Deterministic production path:
    # - Use turbo family only.
    # - Auto-pick CUDA when available, otherwise CPU.
    # - Keep sampling conservative by default.
    temperature = max(0.01, min(1.2, args.temperature))
    top_k = max(1, min(100, args.top_k))
    runtime_device = args.device
    if runtime_device == "auto":
        try:
            import torch  # type: ignore
            runtime_device = "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            runtime_device = "cpu"
    if runtime_device == "cuda":
        mode_used = "standard_gpu"
        tts = Vieneu(
            mode="standard",
            backbone_repo="JayLL13/VoxCPM-1.5-VN",
            backbone_device="cuda",
            codec_repo="neuphonic/distill-neucodec",
            codec_device="cuda",
        )
    else:
        mode_used = "standard_cpu"
        tts = Vieneu(
            mode="standard",
            backbone_repo="JayLL13/VoxCPM-1.5-VN",
            backbone_device="cpu",
            codec_repo="neuphonic/distill-neucodec",
            codec_device="cpu",
        )

    generated_files: list[Path] = []
    post_cfg = PostProcessConfig(
        enable=bool(args.postprocess),
        noise_reduction=max(0.0, min(1.0, args.noise_reduction)),
        highpass_hz=max(20.0, min(250.0, args.highpass_hz)),
        lowpass_hz=max(6000.0, min(16000.0, args.lowpass_hz)),
        target_peak_db=max(-6.0, min(-0.1, args.target_peak_db)),
        comp_threshold_db=max(-36.0, min(-8.0, args.comp_threshold_db)),
        comp_ratio=max(1.0, min(8.0, args.comp_ratio)),
        make_up_gain_db=max(0.0, min(12.0, args.make_up_gain_db)),
        presence_boost_db=max(-3.0, min(6.0, args.presence_boost_db)),
        de_ess=max(0.0, min(1.0, args.de_ess)),
        gate_strength=max(0.0, min(1.0, args.gate_strength)),
    )
    try:
        print(
            f"Clone config -> mode={mode_used}, device={runtime_device}, "
            f"temperature={temperature:.2f}, top_k={top_k}"
        )
        ref_audio_for_encode = ref_audio
        with tempfile.TemporaryDirectory(prefix="vieneu_ref_") as td:
            if args.preprocess_reference:
                tmp_ref = Path(td) / "reference_clean.wav"
                ref_audio_for_encode = preprocess_reference_audio(ref_audio, tmp_ref)
                print(f"Reference preprocessed: {ref_audio_for_encode}")
            ref_codes = tts.encode_reference(str(ref_audio_for_encode))

            for idx, txt_file in enumerate(text_files, start=1):
                text = txt_file.read_text(encoding="utf-8").strip()
                if not text:
                    print(f"[{idx}/{len(text_files)}] Skip empty file: {txt_file.name}")
                    continue

                print(f"[{idx}/{len(text_files)}] Synthesizing: {txt_file.name}")
                audio = tts.infer(
                    text=text,
                    ref_codes=ref_codes,
                    ref_text=selected.ref_text,
                    temperature=temperature,
                    top_k=top_k,
                    max_chars=args.max_chars,
                )

                out_path = output_dir / f"{txt_file.stem}.wav"
                tts.save(audio, out_path)
                if post_cfg.enable:
                    process_wav_file(out_path, post_cfg)
                generated_files.append(out_path)
                print(f"  -> Saved: {out_path}")
    finally:
        close_fn = getattr(tts, "close", None)
        if callable(close_fn):
            close_fn()

    if not generated_files:
        raise RuntimeError("No audio file was generated from input text files.")

    merged_file = merge_wav_files(generated_files, combined_output)
    print(f"Merged audio saved: {merged_file}")

    manifest = {
        "reference_audio": str(ref_audio),
        "voice_profile": selected.name,
        "reference_text": ref_text,
        "mode": mode_used,
        "device": runtime_device,
        "temperature": temperature,
        "top_k": top_k,
        "postprocess": {
            "enabled": post_cfg.enable,
            "noise_reduction": post_cfg.noise_reduction,
            "highpass_hz": post_cfg.highpass_hz,
            "lowpass_hz": post_cfg.lowpass_hz,
            "target_peak_db": post_cfg.target_peak_db,
            "comp_threshold_db": post_cfg.comp_threshold_db,
            "comp_ratio": post_cfg.comp_ratio,
            "make_up_gain_db": post_cfg.make_up_gain_db,
            "presence_boost_db": post_cfg.presence_boost_db,
            "de_ess": post_cfg.de_ess,
            "gate_strength": post_cfg.gate_strength,
        },
        "reference_preprocess": bool(args.preprocess_reference),
        "inputs": [str(p) for p in text_files],
        "outputs": [str(p) for p in generated_files],
        "combined_output": str(merged_file),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Manifest saved: {manifest_path}")
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
