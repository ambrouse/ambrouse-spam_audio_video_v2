from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf


@dataclass
class PostProcessConfig:
    enable: bool = True
    noise_reduction: float = 0.02
    highpass_hz: float = 70.0
    lowpass_hz: float = 10500.0
    target_peak_db: float = -1.5
    comp_threshold_db: float = -22.0
    comp_ratio: float = 1.4
    make_up_gain_db: float = 0.0
    presence_boost_db: float = 0.0
    de_ess: float = 0.25
    gate_strength: float = 0.20


def _db_to_amp(db: float) -> float:
    return float(10.0 ** (db / 20.0))


def _highpass(signal: np.ndarray, sr: int, cutoff_hz: float) -> np.ndarray:
    if signal.size == 0:
        return signal
    if cutoff_hz <= 0:
        return signal
    rc = 1.0 / (2.0 * np.pi * cutoff_hz)
    dt = 1.0 / float(sr)
    alpha = rc / (rc + dt)
    out = np.zeros_like(signal)
    out[0] = signal[0]
    for i in range(1, signal.shape[0]):
        out[i] = alpha * (out[i - 1] + signal[i] - signal[i - 1])
    return out


def _lowpass(signal: np.ndarray, sr: int, cutoff_hz: float) -> np.ndarray:
    if signal.size == 0:
        return signal
    if cutoff_hz <= 0:
        return signal
    rc = 1.0 / (2.0 * np.pi * cutoff_hz)
    dt = 1.0 / float(sr)
    alpha = dt / (rc + dt)
    out = np.zeros_like(signal)
    out[0] = signal[0]
    for i in range(1, signal.shape[0]):
        out[i] = out[i - 1] + alpha * (signal[i] - out[i - 1])
    return out


def _presence_eq(signal: np.ndarray, sr: int, boost_db: float) -> np.ndarray:
    if abs(boost_db) < 1e-6:
        return signal
    hp = _highpass(signal, sr, 2200.0)
    band = _lowpass(hp, sr, 6500.0)
    g = _db_to_amp(boost_db) - 1.0
    return (signal + (g * band)).astype(np.float32)


def _de_esser(signal: np.ndarray, sr: int, strength: float) -> np.ndarray:
    if strength <= 0:
        return signal
    s_band = _highpass(signal, sr, 5200.0)
    env = np.abs(s_band)
    threshold = np.percentile(env, 82)
    if threshold <= 1e-6:
        return signal
    excess = np.maximum(env - threshold, 0.0) / (threshold + 1e-8)
    gain = 1.0 - np.clip(strength * excess, 0.0, 0.5)
    return (signal * gain).astype(np.float32)


def _noise_gate(signal: np.ndarray, strength: float) -> np.ndarray:
    if strength <= 0:
        return signal
    frame = 512
    hop = 128
    if len(signal) < frame:
        return signal
    env = np.zeros(len(signal), dtype=np.float32)
    for i in range(0, len(signal) - frame, hop):
        rms = np.sqrt(np.mean(signal[i:i + frame] ** 2) + 1e-12)
        env[i:i + hop] = rms
    env[env == 0] = np.max(env) * 1e-3
    floor = np.percentile(env, 20)
    thr = np.percentile(env, 45)
    norm = np.clip((env - floor) / (thr - floor + 1e-8), 0.0, 1.0)
    gain = (1.0 - strength) + (strength * norm)
    return (signal * gain).astype(np.float32)


def _spectral_denoise(signal: np.ndarray, sr: int, reduction: float) -> np.ndarray:
    if signal.size == 0:
        return signal
    if reduction <= 0:
        return signal
    n_fft = 1024
    hop = 256
    if signal.shape[0] < n_fft:
        return signal
    win = np.hanning(n_fft).astype(np.float32)
    pad = n_fft
    x = np.pad(signal, (pad, pad), mode="reflect")
    frames = []
    for i in range(0, x.shape[0] - n_fft + 1, hop):
        frames.append(x[i : i + n_fft] * win)
    stft = np.fft.rfft(np.stack(frames, axis=0), axis=1)
    mag = np.abs(stft)
    phase = np.angle(stft)

    noise_frames = max(1, int(min((0.6 * sr) / hop, mag.shape[0] // 4)))
    noise_profile = np.median(mag[:noise_frames], axis=0)
    cleaned_mag = np.maximum(mag - (reduction * noise_profile[None, :]), 0.0)

    y = np.zeros((stft.shape[0] - 1) * hop + n_fft, dtype=np.float32)
    wsum = np.zeros_like(y)
    for idx in range(stft.shape[0]):
        frame = np.fft.irfft(cleaned_mag[idx] * np.exp(1j * phase[idx]), n_fft).astype(np.float32)
        pos = idx * hop
        y[pos : pos + n_fft] += frame * win
        wsum[pos : pos + n_fft] += win * win
    y = y / np.maximum(wsum, 1e-8)
    y = y[pad : pad + signal.shape[0]]
    return y.astype(np.float32)


def _compress(signal: np.ndarray, threshold_db: float, ratio: float) -> np.ndarray:
    if signal.size == 0:
        return signal
    if ratio <= 1.0:
        return signal
    x = np.clip(signal, -1.0, 1.0)
    amp = np.maximum(np.abs(x), 1e-8)
    db = 20.0 * np.log10(amp)
    over = db > threshold_db
    db_out = db.copy()
    db_out[over] = threshold_db + (db[over] - threshold_db) / ratio
    gain = 10.0 ** ((db_out - db) / 20.0)
    return (x * gain).astype(np.float32)


def _normalize_peak(signal: np.ndarray, target_peak_db: float) -> np.ndarray:
    if signal.size == 0:
        return signal
    peak = float(np.max(np.abs(signal)))
    if peak <= 1e-8:
        return signal
    target = _db_to_amp(target_peak_db)
    return (signal * (target / peak)).astype(np.float32)


def process_audio_array(audio: np.ndarray, sr: int, cfg: PostProcessConfig) -> np.ndarray:
    if audio.size == 0:
        return audio.astype(np.float32)
    x = audio.astype(np.float32)
    x = _highpass(x, sr, cfg.highpass_hz)
    x = _spectral_denoise(x, sr, cfg.noise_reduction)
    x = _presence_eq(x, sr, cfg.presence_boost_db)
    x = _de_esser(x, sr, cfg.de_ess)
    x = _noise_gate(x, cfg.gate_strength)
    x = _lowpass(x, sr, cfg.lowpass_hz)
    x = _compress(x, cfg.comp_threshold_db, cfg.comp_ratio)
    x = x * _db_to_amp(cfg.make_up_gain_db)
    x = _normalize_peak(x, cfg.target_peak_db)
    x = np.tanh(1.1 * x) / np.tanh(1.1)
    return np.clip(x, -1.0, 1.0).astype(np.float32)


def process_wav_file(path: Path, cfg: PostProcessConfig) -> Path:
    audio, sr = sf.read(str(path), dtype="float32", always_2d=True)
    if audio.size == 0:
        return path
    out = np.zeros_like(audio)
    for ch in range(audio.shape[1]):
        out[:, ch] = process_audio_array(audio[:, ch], sr, cfg)
    sf.write(str(path), out, sr)
    return path
