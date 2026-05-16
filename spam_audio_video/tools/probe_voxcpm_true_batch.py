from __future__ import annotations

import argparse
import json
import re
import sys
import time
import wave
from pathlib import Path

import numpy as np
import soundfile as sf
import torch


REPO_ROOT = Path(__file__).resolve().parents[1]
TTS_ROOT = REPO_ROOT / "auto_text_to_voice"
VIE_ROOT = TTS_ROOT / "VieNeu-TTS"
for candidate in (VIE_ROOT / "src", VIE_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))
if str(TTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TTS_ROOT))

from run_vieneu_batch_clone import discover_voice_profiles


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _wav_metadata(path: Path) -> dict:
    with wave.open(str(path), "rb") as handle:
        frames = handle.getnframes()
        rate = handle.getframerate()
        return {
            "path": str(path),
            "sample_rate": rate,
            "channels": handle.getnchannels(),
            "frames": frames,
            "duration_s": round(frames / rate, 3) if rate else 0,
            "size": path.stat().st_size,
        }


def _read_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _safe_torchaudio_load(path: str):
    audio, sr = sf.read(path, dtype="float32", always_2d=True)
    return torch.from_numpy(audio.T), sr


def _pad_1d(tensors: list[torch.Tensor], pad_value: int = 0) -> torch.Tensor:
    max_len = max(int(t.shape[0]) for t in tensors)
    out = []
    for tensor in tensors:
        if tensor.shape[0] < max_len:
            pad = torch.full((max_len - tensor.shape[0],), pad_value, dtype=tensor.dtype)
            tensor = torch.cat([tensor, pad], dim=0)
        out.append(tensor)
    return torch.stack(out, dim=0)


def _pad_3d(tensors: list[torch.Tensor]) -> torch.Tensor:
    max_len = max(int(t.shape[0]) for t in tensors)
    out = []
    for tensor in tensors:
        if tensor.shape[0] < max_len:
            pad = torch.zeros((max_len - tensor.shape[0], tensor.shape[1], tensor.shape[2]), dtype=tensor.dtype)
            tensor = torch.cat([tensor, pad], dim=0)
        out.append(tensor)
    return torch.stack(out, dim=0)


def _build_batch_inputs(model, prompt_cache: dict, texts: list[str]) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    prompt_audio_feat = prompt_cache["audio_feat"]
    prompt_text = prompt_cache["prompt_text"]
    text_tokens: list[torch.Tensor] = []
    text_masks: list[torch.Tensor] = []
    audio_feats: list[torch.Tensor] = []
    audio_masks: list[torch.Tensor] = []
    for target_text in texts:
        full_text = prompt_text + target_text
        text_token = torch.LongTensor(model.text_tokenizer(full_text))
        text_token = torch.cat(
            [
                text_token,
                torch.tensor([model.audio_start_token], dtype=torch.int32, device=text_token.device),
            ],
            dim=-1,
        )
        audio_length = prompt_audio_feat.size(0)
        text_length = text_token.shape[0]
        text_pad_token = torch.zeros(audio_length, dtype=torch.int32, device=text_token.device)
        audio_pad_feat = torch.zeros(
            (text_length, model.patch_size, model.audio_vae.latent_dim),
            dtype=torch.float32,
            device=text_token.device,
        )
        text_tokens.append(torch.cat([text_token, text_pad_token]).to(torch.long))
        audio_feats.append(torch.cat([audio_pad_feat, prompt_audio_feat], dim=0))
        text_masks.append(torch.cat([torch.ones(text_length), torch.zeros(audio_length)]).type(torch.int32))
        audio_masks.append(torch.cat([torch.zeros(text_length), torch.ones(audio_length)]).type(torch.int32))
    return (
        _pad_1d(text_tokens, 0).to(model.device),
        _pad_1d(text_masks, 0).to(model.device),
        _pad_3d(audio_feats).to(model.device).to(next(model.parameters()).dtype),
        _pad_1d(audio_masks, 0).to(model.device),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe private true-batch VoxCPM inference.")
    parser.add_argument("--project-id", default="test-1")
    parser.add_argument("--session-id", default="session_ch0001_to_ch0010")
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--inference-timesteps", type=int, default=8)
    parser.add_argument("--output-dir", default=str(REPO_ROOT / "benchmarks" / "audio_8x4x" / "voxcpm_true_batch_probe"))
    args = parser.parse_args()

    import torchaudio
    from voxcpm import VoxCPM

    torchaudio.load = _safe_torchaudio_load  # type: ignore[assignment]
    torch.set_float32_matmul_precision("high")

    session_dir = REPO_ROOT / "projects_workspace" / "projects" / args.project_id / "sessions" / args.session_id
    text_files = sorted((session_dir / "tts_inputs").glob("*.txt"))[: max(1, int(args.batch_size))]
    texts = [_read_text(path) for path in text_files]
    # Keep the longest target first because the stock internal stop check only
    # observes sample 0. This probe is not production-safe until stop handling is fixed.
    ordered = sorted(zip(text_files, texts), key=lambda item: len(item[1]), reverse=True)
    text_files = [item[0] for item in ordered]
    texts = [item[1] for item in ordered]

    profiles = discover_voice_profiles(TTS_ROOT / "voice")
    selected = next((p for p in profiles if p.name == "su-review"), profiles[0])
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    tts = VoxCPM.from_pretrained(
        hf_model_id="JayLL13/VoxCPM-1.5-VN",
        load_denoiser=False,
        optimize=True,
    )
    load_s = time.perf_counter() - t0

    model = tts.tts_model
    prompt_cache = model.build_prompt_cache(prompt_text=selected.ref_text, prompt_wav_path=str(selected.ref_audio))
    text_token, text_mask, audio_feat, audio_mask = _build_batch_inputs(model, prompt_cache, texts)
    target_text_lengths = [len(model.text_tokenizer(text)) for text in texts]
    max_len = min(max(int(length * 6.0 + 10) for length in target_text_lengths), 2200)
    batch_size = len(texts)
    cache_dtype = next(model.parameters()).dtype
    model.base_lm.setup_cache(batch_size, model.config.max_length, model.device, cache_dtype)
    model.residual_lm.setup_cache(batch_size, model.config.max_length, model.device, cache_dtype)

    infer_t0 = time.perf_counter()
    result = model._inference(
        text_token,
        text_mask,
        audio_feat,
        audio_mask,
        min_len=2,
        max_len=max_len,
        inference_timesteps=args.inference_timesteps,
        cfg_value=2.0,
        streaming=False,
    )
    feat_pred, pred_audio_feat = next(result)
    decode_audio = []
    for sample_idx in range(feat_pred.shape[0]):
        sample_audio = (
            model.audio_vae.decode(feat_pred[sample_idx : sample_idx + 1].to(torch.float32))
            .squeeze(1)
            .detach()
            .cpu()
            .numpy()[0]
        )
        decode_audio.append(sample_audio)
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    infer_s = time.perf_counter() - infer_t0

    outputs = []
    for idx, wav in enumerate(decode_audio):
        out_path = out_dir / f"{text_files[idx].stem}.wav"
        sf.write(str(out_path), np.asarray(wav, dtype=np.float32), int(model.sample_rate))
        outputs.append(_wav_metadata(out_path))

    report = {
        "success": True,
        "warning": "Experimental probe only. Stock stop handling observes sample 0, so quality parity is not proven.",
        "load_s": round(load_s, 3),
        "infer_decode_s": round(infer_s, 3),
        "batch_size": len(texts),
        "max_len": max_len,
        "text_files": [path.name for path in text_files],
        "outputs": outputs,
    }
    _write_json(out_dir / "report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
