#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
import time
import hashlib
import os
import shutil
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
import torch

from audio_postprocess import PostProcessConfig, process_wav_file
from run_vieneu_batch_clone import (
    discover_voice_profiles,
)


TTS_CACHE_VERSION = 2


def _env_bool(name: str, default: bool) -> bool:
    raw = str(os.environ.get(name) or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _coerce_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raw = str(value).strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float, low: float, high: float) -> float:
    raw = str(os.environ.get(name) or "").strip()
    try:
        value = float(raw) if raw else default
    except ValueError:
        value = default
    return max(low, min(high, value))


class WarmRuntime:
    def __init__(self) -> None:
        self.tts = None
        self.mode_used = ""
        self.runtime_device = ""
        self.model_key = "voxcpm_vn"
        self._file_hash_cache: dict[str, tuple[int, int, str]] = {}
        self._prompt_cache: dict[str, Any] = {}
        self.model_catalog: dict[str, dict[str, str]] = {
            "voxcpm_vn": {
                "label": "VoxCPM 1.5 VN (Clone)",
                "runtime_mode": "voxcpm",
                "backbone_repo": "JayLL13/VoxCPM-1.5-VN",
            },
        }

    def list_models(self) -> list[dict[str, str]]:
        out = []
        for key, cfg in self.model_catalog.items():
            out.append(
                {
                    "key": key,
                    "label": cfg["label"],
                    "selected": "true" if key == self.model_key else "false",
                }
            )
        return out

    def set_model(self, model_key: str) -> None:
        if model_key not in self.model_catalog:
            raise ValueError(f"Unsupported model key: {model_key}")
        if model_key == self.model_key and self.tts is not None:
            return
        self.model_key = model_key
        self._close_tts()

    def _close_tts(self) -> None:
        if self.tts is None:
            return
        close_fn = getattr(self.tts, "close", None)
        if callable(close_fn):
            close_fn()
        self.tts = None
        self._prompt_cache.clear()

    def ensure_loaded(self, device: str) -> None:
        runtime_device = device
        if runtime_device == "auto":
            try:
                runtime_device = "cuda" if torch.cuda.is_available() else "cpu"
            except Exception:
                runtime_device = "cpu"
        if self.tts is not None:
            if self.runtime_device == runtime_device:
                return
            self._close_tts()
        # VoxCPM uses torchaudio.load internally. On this Windows runtime,
        # torchaudio's torchcodec path can fail due missing FFmpeg DLLs.
        # Patch load() to a stable soundfile implementation.
        import torchaudio  # pylint: disable=import-error

        def _safe_torchaudio_load(path: str):
            audio, sr = sf.read(path, dtype="float32", always_2d=True)
            return torch.from_numpy(audio.T), sr

        torchaudio.load = _safe_torchaudio_load  # type: ignore[assignment]

        if runtime_device == "cuda":
            cuda_available = bool(torch.cuda.is_available())
            cuda_version = getattr(torch.version, "cuda", None)
            if not cuda_available or not cuda_version:
                raise RuntimeError(
                    "CUDA TTS runtime is required, but this Python environment is using CPU-only torch. "
                    f"torch={getattr(torch, '__version__', 'unknown')}, cuda_available={cuda_available}, cuda_version={cuda_version}. "
                    "Reinstall the TTS runtime with CUDA torch, then restart the web backend."
                )
        model_cfg = self.model_catalog[self.model_key]
        if model_cfg["runtime_mode"] != "voxcpm":
            raise RuntimeError(f"Unsupported runtime mode: {model_cfg['runtime_mode']}")
        from voxcpm import VoxCPM  # pylint: disable=import-error

        if runtime_device == "cuda":
            try:
                torch.set_float32_matmul_precision("high")
            except Exception:
                pass
            try:
                torch.backends.cuda.matmul.allow_tf32 = True
                torch.backends.cudnn.allow_tf32 = True
                torch.backends.cudnn.benchmark = True
            except Exception:
                pass

        use_torch_compile = str(os.environ.get("SPAM_TTS_TORCH_COMPILE") or "").strip().lower() in {"1", "true", "yes", "on"}
        self.tts = VoxCPM.from_pretrained(
            hf_model_id=model_cfg["backbone_repo"],
            load_denoiser=False,
            optimize=(runtime_device == "cuda" and use_torch_compile),
        )
        self.mode_used = "voxcpm"
        self.runtime_device = runtime_device

    @staticmethod
    def _normalize_text_for_tts(raw: str) -> str:
        text = raw.replace("\ufeff", "")
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{2,}", "\n", text)
        text = text.replace("…", ".")
        text = text.replace("“", "\"").replace("”", "\"")
        text = text.replace("’", "'").replace("`", "'")
        text = re.sub(r"\s+([,.!?;:])", r"\1", text)
        text = re.sub(r"([,.!?;:])([^\s\n])", r"\1 \2", text)
        return text.strip()

    @classmethod
    def _read_text_file_safe(cls, path: Path) -> str:
        raw = path.read_bytes()
        decoders = ("utf-8", "utf-8-sig", "cp1258", "cp1252", "latin-1")
        decoded = ""
        for enc in decoders:
            try:
                decoded = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if not decoded:
            decoded = raw.decode("utf-8", errors="replace")
        # Recover common mojibake pattern: UTF-8 bytes interpreted as latin/cp1252.
        if decoded.count("Ã") + decoded.count("áº") + decoded.count("Ä‘") > 6:
            try:
                repaired = decoded.encode("latin-1", errors="ignore").decode("utf-8", errors="ignore")
                if repaired:
                    decoded = repaired
            except Exception:
                pass
        return cls._normalize_text_for_tts(decoded)

    def _sha256_file(self, path: Path) -> str:
        stat = path.stat()
        cache_key = str(path.resolve())
        cached = self._file_hash_cache.get(cache_key)
        if cached and cached[0] == stat.st_mtime_ns and cached[1] == stat.st_size:
            return cached[2]
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        value = digest.hexdigest()
        self._file_hash_cache[cache_key] = (stat.st_mtime_ns, stat.st_size, value)
        return value

    def _build_tts_cache_key(
        self,
        text: str,
        selected: Any,
        settings: dict[str, Any],
    ) -> str:
        payload = {
            "version": TTS_CACHE_VERSION,
            "text": text,
            "voice_profile": selected.name,
            "reference_audio_sha256": self._sha256_file(Path(selected.ref_audio)),
            "reference_text": selected.ref_text,
            "mode": self.mode_used,
            "model_key": self.model_key,
            "device": self.runtime_device,
            "settings": settings,
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _get_prompt_cache(self, selected: Any) -> Any:
        assert self.tts is not None
        ref_audio = Path(selected.ref_audio)
        cache_payload = {
            "version": TTS_CACHE_VERSION,
            "mode": self.mode_used,
            "model_key": self.model_key,
            "device": self.runtime_device,
            "reference_audio": str(ref_audio.resolve()),
            "reference_audio_sha256": self._sha256_file(ref_audio),
            "reference_text": selected.ref_text,
        }
        encoded = json.dumps(cache_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        cache_key = hashlib.sha256(encoded).hexdigest()
        if cache_key not in self._prompt_cache:
            self._prompt_cache[cache_key] = self.tts.tts_model.build_prompt_cache(
                prompt_text=selected.ref_text,
                prompt_wav_path=str(ref_audio),
            )
        return self._prompt_cache[cache_key]

    def _generate_with_prompt_cache(
        self,
        text: str,
        selected: Any,
        inference_timesteps: int,
        max_len: int,
        cfg_value: float,
        retry_badcase: bool,
        retry_badcase_max_times: int,
    ) -> np.ndarray:
        assert self.tts is not None
        from voxcpm.model.utils import next_and_close  # pylint: disable=import-error

        target_text = re.sub(r"\s+", " ", text.replace("\n", " ")).strip()
        prompt_cache = self._get_prompt_cache(selected)
        with torch.inference_mode():
            generate_result = self.tts.tts_model._generate_with_prompt_cache(
                target_text=target_text,
                prompt_cache=prompt_cache,
                min_len=2,
                max_len=max_len,
                inference_timesteps=inference_timesteps,
                cfg_value=cfg_value,
                retry_badcase=retry_badcase,
                retry_badcase_max_times=retry_badcase_max_times,
                retry_badcase_ratio_threshold=6.0,
                streaming=False,
            )
            wav, _, _ = next_and_close(generate_result)
        return wav.squeeze(0).cpu().numpy()

    def synth(self, payload: dict[str, Any]) -> dict[str, Any]:
        voice_dir = Path(payload["voice_dir"]).resolve()
        text_dir = Path(payload["text_dir"]).resolve()
        output_dir = Path(payload["output_dir"]).resolve()
        combined_output = Path(payload["combined_output"]).resolve()
        manifest_path = Path(payload["manifest_path"]).resolve()

        voice_profile = payload.get("voice_profile") or ""
        requested_model = payload.get("model_key") or self.model_key
        self.set_model(requested_model)
        temperature = float(payload.get("temperature", 0.1))
        top_k = int(payload.get("top_k", 10))
        max_chars = int(payload.get("max_chars", 256))
        io_workers = max(1, min(6, int(payload.get("io_workers", 2))))
        inference_timesteps = max(4, min(20, int(payload.get("inference_timesteps", 8))))
        cfg_value = max(0.5, min(4.0, float(payload.get("cfg_value", _env_float("SPAM_TTS_CFG_VALUE", 2.0, 0.5, 4.0)))))
        retry_badcase = _coerce_bool(payload.get("retry_badcase"), _env_bool("SPAM_TTS_RETRY_BADCASE", True))
        retry_badcase_max_times = max(1, min(3, int(payload.get("retry_badcase_max_times", 1)))) if retry_badcase else 0
        max_len_scale = _env_float("SPAM_TTS_MAX_LEN_SCALE", 2.9, 2.2, 3.4)
        max_len_padding = max(40, min(140, int(os.environ.get("SPAM_TTS_MAX_LEN_PADDING", "70") or 70)))
        postprocess = _coerce_bool(payload.get("postprocess"), True)
        anti_leak_trim = _coerce_bool(payload.get("anti_leak_trim"), True)
        anti_leak_max_ms = max(80, min(1200, int(payload.get("anti_leak_max_ms", 900))))
        head_pre_roll_ms = max(0, min(40, int(payload.get("head_pre_roll_ms", 10))))
        tail_keep_ms = max(20, min(250, int(payload.get("tail_keep_ms", 100))))
        cache_enabled = _coerce_bool(payload.get("cache_enabled"), True)
        cache_root = Path(
            payload.get("cache_root")
            or Path(payload.get("project_root", ".")).resolve().parents[1] / "projects_workspace" / "runtime" / "tts_cache"
        ).resolve()
        if not self.mode_used:
            self.mode_used = "voxcpm"
        if not self.runtime_device:
            requested_device = str(payload.get("device", "auto")).strip().lower()
            if requested_device == "auto":
                try:
                    requested_device = "cuda" if torch.cuda.is_available() else "cpu"
                except Exception:
                    requested_device = "cpu"
            self.runtime_device = requested_device

        profiles = discover_voice_profiles(voice_dir)
        if not profiles:
            raise FileNotFoundError(f"No valid voice profile found in {voice_dir}")

        selected = profiles[0]
        if voice_profile:
            found = next((p for p in profiles if p.name == voice_profile), None)
            if found is None:
                names = ", ".join(p.name for p in profiles)
                raise FileNotFoundError(f"Voice profile '{voice_profile}' not found. Available: {names}")
            selected = found

        text_files = sorted(
            p for p in text_dir.iterdir()
            if p.is_file() and p.suffix.lower() == ".txt"
        )
        if not text_files:
            raise FileNotFoundError(f"No .txt files found in {text_dir}")

        output_dir.mkdir(parents=True, exist_ok=True)
        if manifest_path.exists():
            manifest_path.unlink(missing_ok=True)
        if combined_output.exists():
            combined_output.unlink(missing_ok=True)

        cfg = PostProcessConfig(
            enable=postprocess,
            noise_reduction=max(0.0, min(1.0, float(payload.get("noise_reduction", 0.12)))),
            highpass_hz=max(20.0, min(250.0, float(payload.get("highpass_hz", 70.0)))),
            lowpass_hz=max(6000.0, min(16000.0, float(payload.get("lowpass_hz", 10500.0)))),
            target_peak_db=max(-6.0, min(-0.1, float(payload.get("target_peak_db", -1.5)))),
            comp_threshold_db=max(-36.0, min(-8.0, float(payload.get("comp_threshold_db", -22.0)))),
            comp_ratio=max(1.0, min(8.0, float(payload.get("comp_ratio", 1.4)))),
            make_up_gain_db=max(0.0, min(12.0, float(payload.get("make_up_gain_db", 0.0)))),
            presence_boost_db=max(-3.0, min(6.0, float(payload.get("presence_boost_db", 0.4)))),
            de_ess=max(0.0, min(1.0, float(payload.get("de_ess", 0.30)))),
            gate_strength=max(0.0, min(1.0, float(payload.get("gate_strength", 0.20)))),
        )

        generated_files: list[Path] = []
        cache_hits = 0
        cache_misses = 0
        logs = [
            f"mode={self.mode_used}",
            f"device={self.runtime_device}",
            f"voice={selected.name}",
            f"text_files={len(text_files)}",
            f"io_workers={io_workers}",
            f"inference_timesteps={inference_timesteps}",
            f"cfg_value={cfg_value}",
            f"retry_badcase={retry_badcase}",
            f"retry_badcase_max_times={retry_badcase_max_times}",
            f"max_len_scale={max_len_scale}",
            f"max_len_padding={max_len_padding}",
            f"cache_enabled={cache_enabled}",
        ]

        infer_texts: list[str] = []
        valid_files: list[Path] = []
        for idx, txt_file in enumerate(text_files, start=1):
            text = self._read_text_file_safe(txt_file)
            if not text:
                logs.append(f"[{idx}/{len(text_files)}] skip empty {txt_file.name}")
                continue
            infer_texts.append(text)
            valid_files.append(txt_file)

        if not infer_texts:
            raise RuntimeError("All input text files are empty.")

        failed_files: list[str] = []
        if self.mode_used != "voxcpm":
            raise RuntimeError(f"Unsupported mode for synth: {self.mode_used}")
        sample_rate: int | None = None
        pause_sequence_ms_by_index: dict[int, int] = {}
        trim_applied = 0
        generated_by_index: dict[int, Path] = {}
        cache_items: list[dict[str, Any]] = []

        key_settings = {
            "inference_timesteps": inference_timesteps,
            "cfg_value": cfg_value,
            "retry_badcase": retry_badcase,
            "retry_badcase_max_times": retry_badcase_max_times,
            "max_len_scale": max_len_scale,
            "max_len_padding": max_len_padding,
            "temperature": max(0.01, min(1.2, temperature)),
            "top_k": max(1, min(100, top_k)),
            "max_chars": max_chars,
            "postprocess": {
                "enabled": cfg.enable,
                "noise_reduction": cfg.noise_reduction,
                "highpass_hz": cfg.highpass_hz,
                "lowpass_hz": cfg.lowpass_hz,
                "target_peak_db": cfg.target_peak_db,
                "comp_threshold_db": cfg.comp_threshold_db,
                "comp_ratio": cfg.comp_ratio,
                "make_up_gain_db": cfg.make_up_gain_db,
                "presence_boost_db": cfg.presence_boost_db,
                "de_ess": cfg.de_ess,
                "gate_strength": cfg.gate_strength,
            },
            "anti_leak_trim": anti_leak_trim,
            "anti_leak_max_ms": anti_leak_max_ms,
            "head_pre_roll_ms": head_pre_roll_ms,
            "tail_keep_ms": tail_keep_ms,
            "denoise": False,
            "normalize": False,
        }

        def _write_and_postprocess(
            out_path: Path,
            wav_arr: np.ndarray,
            sr: int,
            post_cfg: PostProcessConfig,
        ) -> int:
            t0 = time.perf_counter()
            sf.write(str(out_path), wav_arr, sr)
            if post_cfg.enable:
                process_wav_file(out_path, post_cfg)
            return int((time.perf_counter() - t0) * 1000)

        with ThreadPoolExecutor(max_workers=io_workers) as io_pool:
            pending: dict[Any, tuple[int, Path, int, int, int]] = {}
            max_pending = max(2, io_workers * 2)
            for idx, (txt_file, text) in enumerate(zip(valid_files, infer_texts), start=1):
                try:
                    dynamic_max_len = max(180, min(1800, int(len(text) * max_len_scale) + max_len_padding))
                    cache_key = self._build_tts_cache_key(
                        text,
                        selected,
                        {**key_settings, "dynamic_max_len": dynamic_max_len},
                    )
                    cache_path = cache_root / f"v{TTS_CACHE_VERSION}" / f"{cache_key}.wav"
                    out_path = output_dir / f"{txt_file.stem}.wav"
                    pause_ms = _suggest_pause_ms_from_text(text)
                    pause_sequence_ms_by_index[idx] = pause_ms
                    if cache_enabled and cache_path.exists():
                        shutil.copy2(cache_path, out_path)
                        generated_by_index[idx] = out_path
                        cache_hits += 1
                        cache_items.append({
                            "input": str(txt_file),
                            "output": str(out_path),
                            "cache_key": cache_key,
                            "cache_path": str(cache_path),
                            "cache_hit": True,
                        })
                        logs.append(
                            f"[{idx}/{len(valid_files)}] cache hit {out_path.name} "
                            f"(chars={len(text)}, key={cache_key[:12]})"
                        )
                        continue
                    cache_misses += 1
                    if self.tts is None:
                        self.ensure_loaded(payload.get("device", "auto"))
                    assert self.tts is not None
                    if sample_rate is None:
                        sample_rate = int(getattr(getattr(self.tts, "tts_model", None), "sample_rate", 44100))
                    t0 = time.perf_counter()
                    wav = self._generate_with_prompt_cache(
                        text=text,
                        selected=selected,
                        inference_timesteps=inference_timesteps,
                        max_len=dynamic_max_len,
                        cfg_value=cfg_value,
                        retry_badcase=retry_badcase,
                        retry_badcase_max_times=retry_badcase_max_times,
                    )
                    infer_ms = int((time.perf_counter() - t0) * 1000)
                    wav_arr = np.asarray(wav, dtype=np.float32)
                    wav_arr, trimmed_ms = _smart_trim_edges(
                        wav_arr,
                        sample_rate,
                        enable_head_trim=anti_leak_trim,
                        max_head_trim_ms=anti_leak_max_ms,
                        head_pre_roll_ms=head_pre_roll_ms,
                        tail_keep_ms=tail_keep_ms,
                    )
                    trim_applied += 1 if trimmed_ms > 0 else 0
                    future = io_pool.submit(_write_and_postprocess, out_path, wav_arr, sample_rate, cfg)
                    pending[future] = (idx, out_path, len(text), dynamic_max_len, infer_ms, cache_key, cache_path)
                    if len(pending) >= max_pending:
                        done, _not_done = wait(set(pending.keys()), return_when=FIRST_COMPLETED)
                        for fut in done:
                            file_idx, saved_path, text_chars, max_len_used, infer_ms_used, saved_cache_key, saved_cache_path = pending.pop(fut)
                            try:
                                io_ms = fut.result()
                                if cache_enabled:
                                    saved_cache_path.parent.mkdir(parents=True, exist_ok=True)
                                    shutil.copy2(saved_path, saved_cache_path)
                                generated_by_index[file_idx] = saved_path
                                cache_items.append({
                                    "input": str(valid_files[file_idx - 1]),
                                    "output": str(saved_path),
                                    "cache_key": saved_cache_key,
                                    "cache_path": str(saved_cache_path),
                                    "cache_hit": False,
                                })
                                logs.append(
                                    f"[{file_idx}/{len(valid_files)}] saved {saved_path.name} "
                                    f"(chars={text_chars}, max_len={max_len_used}, infer_ms={infer_ms_used}, io_ms={io_ms})"
                                )
                            except Exception as exc:  # pylint: disable=broad-except
                                failed_files.append(saved_path.with_suffix(".txt").name)
                                logs.append(f"[{file_idx}/{len(valid_files)}] failed {saved_path.name}: {exc}")
                except Exception as exc:  # pylint: disable=broad-except
                    failed_files.append(txt_file.name)
                    logs.append(f"[{idx}/{len(valid_files)}] failed {txt_file.name}: {exc}")
            if pending:
                done, _not_done = wait(set(pending.keys()))
                for fut in done:
                    file_idx, saved_path, text_chars, max_len_used, infer_ms_used, saved_cache_key, saved_cache_path = pending.pop(fut)
                    try:
                        io_ms = fut.result()
                        if cache_enabled:
                            saved_cache_path.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(saved_path, saved_cache_path)
                        generated_by_index[file_idx] = saved_path
                        cache_items.append({
                            "input": str(valid_files[file_idx - 1]),
                            "output": str(saved_path),
                            "cache_key": saved_cache_key,
                            "cache_path": str(saved_cache_path),
                            "cache_hit": False,
                        })
                        logs.append(
                            f"[{file_idx}/{len(valid_files)}] saved {saved_path.name} "
                            f"(chars={text_chars}, max_len={max_len_used}, infer_ms={infer_ms_used}, io_ms={io_ms})"
                        )
                    except Exception as exc:  # pylint: disable=broad-except
                        failed_files.append(saved_path.with_suffix(".txt").name)
                        logs.append(f"[{file_idx}/{len(valid_files)}] failed {saved_path.name}: {exc}")

        for idx in sorted(generated_by_index.keys()):
            generated_files.append(generated_by_index[idx])

        if not generated_files:
            tail = "\n".join(logs[-12:])
            raise RuntimeError(f"No audio file was generated from input text files.\n{tail}")
        if failed_files:
            raise RuntimeError(f"Failed files: {', '.join(failed_files)}")

        pause_sequence_ms = [pause_sequence_ms_by_index.get(i, 220) for i in sorted(generated_by_index.keys())]
        merged_file = _merge_wav_files_with_pauses(generated_files, combined_output, pause_sequence_ms)
        manifest = {
            "reference_audio": str(selected.ref_audio),
            "voice_profile": selected.name,
            "reference_text": selected.ref_text,
            "mode": self.mode_used,
            "model_key": self.model_key,
            "device": self.runtime_device,
            "temperature": max(0.01, min(1.2, temperature)),
            "top_k": max(1, min(100, top_k)),
            "io_workers": io_workers,
            "inference_timesteps": inference_timesteps,
            "cfg_value": cfg_value,
            "retry_badcase": retry_badcase,
            "retry_badcase_max_times": retry_badcase_max_times,
            "max_len_scale": max_len_scale,
            "max_len_padding": max_len_padding,
            "anti_leak_trim": anti_leak_trim,
            "anti_leak_max_ms": anti_leak_max_ms,
            "anti_leak_trim_applied_files": trim_applied,
            "head_pre_roll_ms": head_pre_roll_ms,
            "tail_keep_ms": tail_keep_ms,
            "postprocess": {
                "enabled": cfg.enable,
                "noise_reduction": cfg.noise_reduction,
                "highpass_hz": cfg.highpass_hz,
                "lowpass_hz": cfg.lowpass_hz,
                "target_peak_db": cfg.target_peak_db,
                "comp_threshold_db": cfg.comp_threshold_db,
                "comp_ratio": cfg.comp_ratio,
                "make_up_gain_db": cfg.make_up_gain_db,
                "presence_boost_db": cfg.presence_boost_db,
                "de_ess": cfg.de_ess,
                "gate_strength": cfg.gate_strength,
            },
            "reference_preprocess": False,
            "inputs": [str(p) for p in text_files],
            "outputs": [str(p) for p in generated_files],
            "combined_output": str(merged_file),
            "merge_mode": "streaming",
            "cache": {
                "enabled": cache_enabled,
                "root": str(cache_root),
                "hits": cache_hits,
                "misses": cache_misses,
                "items": sorted(cache_items, key=lambda item: item.get("input", "")),
            },
        }
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"manifest": manifest, "logs": logs}


def _reply(obj: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=True) + "\n")
    sys.stdout.flush()


def _suggest_pause_ms_from_text(text: str) -> int:
    compact = (text or "").strip()
    if not compact:
        return 220
    if compact.endswith(","):
        return 140
    if compact.endswith(";") or compact.endswith(":"):
        return 260
    if compact.endswith(".") or compact.endswith("!") or compact.endswith("?"):
        return 340
    return 220


def _moving_average_abs(signal: np.ndarray, win: int) -> np.ndarray:
    if signal.size == 0:
        return signal
    win = max(1, min(win, signal.size))
    kernel = np.ones(win, dtype=np.float32) / float(win)
    return np.convolve(np.abs(signal), kernel, mode="same")


def _find_first_speech_idx(env: np.ndarray, threshold: float, run_len: int) -> int | None:
    if env.size == 0:
        return None
    mask = env > threshold
    if not np.any(mask):
        return None
    run_len = max(1, run_len)
    streak = np.convolve(mask.astype(np.int32), np.ones(run_len, dtype=np.int32), mode="same")
    idx = np.flatnonzero(streak >= run_len)
    if idx.size == 0:
        idx = np.flatnonzero(mask)
        if idx.size == 0:
            return None
    return int(idx[0])


def _find_last_speech_idx(env: np.ndarray, threshold: float, run_len: int) -> int | None:
    if env.size == 0:
        return None
    mask = env > threshold
    if not np.any(mask):
        return None
    run_len = max(1, run_len)
    streak = np.convolve(mask.astype(np.int32), np.ones(run_len, dtype=np.int32), mode="same")
    idx = np.flatnonzero(streak >= run_len)
    if idx.size == 0:
        idx = np.flatnonzero(mask)
        if idx.size == 0:
            return None
    return int(idx[-1])


def _merge_wav_files_with_pauses(input_paths: list[Path], output_path: Path, pauses_ms: list[int]) -> Path:
    if not input_paths:
        raise ValueError("No input audio files provided for merge.")
    sample_rate = None
    channels = None

    with sf.SoundFile(str(input_paths[0]), mode="r") as first_file:
        sample_rate = int(first_file.samplerate)
        channels = int(first_file.channels)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with sf.SoundFile(str(output_path), mode="w", samplerate=sample_rate, channels=channels) as writer:
        for idx, wav_path in enumerate(input_paths):
            with sf.SoundFile(str(wav_path), mode="r") as reader:
                if int(reader.samplerate) != sample_rate:
                    raise ValueError(f"Sample rate mismatch in {wav_path.name}: {reader.samplerate} != {sample_rate}")
                if int(reader.channels) != channels:
                    raise ValueError(f"Channel mismatch in {wav_path.name}: {reader.channels} != {channels}")
                while True:
                    block = reader.read(frames=131_072, dtype="float32", always_2d=True)
                    if block.size == 0:
                        break
                    writer.write(block)
            if idx < len(input_paths) - 1:
                pause_ms = pauses_ms[idx] if idx < len(pauses_ms) else 220
                pause_samples = int((pause_ms / 1000.0) * sample_rate)
                while pause_samples > 0:
                    block_samples = min(pause_samples, 131_072)
                    writer.write(np.zeros((block_samples, channels), dtype=np.float32))
                    pause_samples -= block_samples
    return output_path


def _smart_trim_edges(
    signal: np.ndarray,
    sr: int,
    enable_head_trim: bool,
    max_head_trim_ms: int,
    head_pre_roll_ms: int,
    tail_keep_ms: int,
) -> tuple[np.ndarray, int]:
    if signal.size == 0:
        return signal, 0
    env = _moving_average_abs(signal, int(sr * 0.01))
    noise_floor = float(np.percentile(env, 25))
    threshold = max(noise_floor * 2.2, 0.0018)
    run_len = int(sr * 0.008)

    start_idx = 0
    if enable_head_trim:
        max_head_trim = int(sr * (max_head_trim_ms / 1000.0))
        max_head_trim = max(0, min(max_head_trim, signal.size // 2))
        probe = env[:max_head_trim] if max_head_trim > 0 else env[:0]
        first_idx = _find_first_speech_idx(probe, threshold, run_len)
        if first_idx is not None:
            pre_roll = int(sr * (head_pre_roll_ms / 1000.0))
            start_idx = max(0, first_idx - pre_roll)

    last_idx = _find_last_speech_idx(env, threshold, run_len)
    if last_idx is None:
        trimmed = signal[start_idx:] if start_idx > 0 else signal
        return trimmed, int((start_idx / sr) * 1000)
    tail_keep = int(sr * (tail_keep_ms / 1000.0))
    end_idx = min(signal.size, last_idx + tail_keep)
    min_len = int(sr * 0.05)
    if end_idx - start_idx < min_len:
        end_idx = min(signal.size, start_idx + min_len)
    trimmed = signal[start_idx:end_idx]
    return trimmed, int((start_idx / sr) * 1000)


def main() -> int:
    runtime = WarmRuntime()
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            cmd = req.get("cmd")
            if cmd == "shutdown":
                _reply({"ok": True, "message": "bye"})
                break
            if cmd == "prewarm":
                if req.get("model_key"):
                    runtime.set_model(str(req["model_key"]))
                runtime.ensure_loaded(req.get("device", "auto"))
                _reply(
                    {
                        "ok": True,
                        "model_key": runtime.model_key,
                        "mode": runtime.mode_used,
                        "device": runtime.runtime_device,
                    }
                )
                continue
            if cmd == "list_models":
                _reply({"ok": True, "models": runtime.list_models(), "selected_model": runtime.model_key})
                continue
            if cmd == "set_model":
                runtime.set_model(str(req["model_key"]))
                runtime.ensure_loaded(req.get("device", "auto"))
                _reply(
                    {
                        "ok": True,
                        "model_key": runtime.model_key,
                        "mode": runtime.mode_used,
                        "device": runtime.runtime_device,
                    }
                )
                continue
            if cmd == "synth":
                if req.get("model_key"):
                    runtime.set_model(str(req["model_key"]))
                result = runtime.synth(req)
                _reply({"ok": True, **result})
                continue
            _reply({"ok": False, "error": f"Unsupported cmd: {cmd}"})
        except Exception as exc:  # pylint: disable=broad-except
            _reply({"ok": False, "error": str(exc)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
