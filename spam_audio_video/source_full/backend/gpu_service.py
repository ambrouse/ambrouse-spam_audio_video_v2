from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path


class GpuStatusService:
    def __init__(self, repo_root: Path, audio_service, video_service) -> None:
        self.repo_root = repo_root.resolve()
        self.audio_service = audio_service
        self.video_service = video_service

    def status(self) -> dict:
        torch_info = self._torch_info()
        ffmpeg_info = self._ffmpeg_info()
        nvidia_info = self._nvidia_smi_info()
        audio_runtime = self._audio_runtime_info()
        selected_encoder = ""
        try:
            selected_encoder = self.video_service.pipeline._resolve_video_encoder("auto")  # pylint: disable=protected-access
        except Exception as exc:
            selected_encoder = f"unknown: {exc}"
        return {
            "success": True,
            "system": {
                "platform": platform.platform(),
                "python": sys.version.split()[0],
            },
            "torch": torch_info,
            "gpu_available": bool(torch_info.get("cuda_available")),
            "nvidia_smi": nvidia_info,
            "ffmpeg": ffmpeg_info,
            "audio_runtime": audio_runtime,
            "video": {
                "selected_encoder_auto": selected_encoder,
                "gpu_encoder_available": selected_encoder in {"h264_nvenc", "h264_qsv", "h264_amf"},
            },
        }

    def prewarm_audio(self) -> dict:
        result = self.audio_service.prewarm()
        return {"success": bool(result.get("ok")), "result": result, "gpu_status": self.status()}

    def check_video_encoder(self) -> dict:
        try:
            selected = self.video_service.pipeline._resolve_video_encoder("auto")  # pylint: disable=protected-access
        except Exception as exc:
            selected = f"unavailable: {exc}"
        return {
            "success": not str(selected).startswith("unavailable:"),
            "ffmpeg": self._ffmpeg_info(),
            "selected_encoder_auto": selected,
        }

    @staticmethod
    def _torch_info() -> dict:
        try:
            import torch  # type: ignore
        except Exception as exc:
            return {"installed": False, "error": str(exc), "cuda_available": False}
        info = {
            "installed": True,
            "version": getattr(torch, "__version__", ""),
            "cuda_available": bool(torch.cuda.is_available()),
            "cuda_version": getattr(torch.version, "cuda", None),
            "device_count": 0,
            "devices": [],
        }
        try:
            count = int(torch.cuda.device_count()) if torch.cuda.is_available() else 0
            info["device_count"] = count
            devices = []
            for idx in range(count):
                props = torch.cuda.get_device_properties(idx)
                free_bytes = None
                total_bytes = int(getattr(props, "total_memory", 0) or 0)
                try:
                    free_bytes, total_bytes = torch.cuda.mem_get_info(idx)
                except Exception:
                    pass
                devices.append({
                    "index": idx,
                    "name": torch.cuda.get_device_name(idx),
                    "capability": ".".join(str(x) for x in torch.cuda.get_device_capability(idx)),
                    "total_vram_mb": int(total_bytes / (1024 * 1024)) if total_bytes else 0,
                    "free_vram_mb": int(free_bytes / (1024 * 1024)) if free_bytes is not None else None,
                })
            info["devices"] = devices
        except Exception as exc:
            info["device_error"] = str(exc)
        return info

    def _ffmpeg_info(self) -> dict:
        ffmpeg_bin = getattr(self.video_service.pipeline, "ffmpeg_bin", "ffmpeg")
        encoders = []
        try:
            encoders = sorted(self.video_service.pipeline._list_ffmpeg_encoders())  # pylint: disable=protected-access
        except Exception:
            encoders = []
        hardware = [name for name in ["h264_nvenc", "h264_qsv", "h264_amf"] if name in encoders]
        try:
            selected_auto = self.video_service.pipeline._resolve_video_encoder("auto")  # pylint: disable=protected-access
        except Exception as exc:
            selected_auto = f"unavailable: {exc}"
        return {
            "ffmpeg_bin": ffmpeg_bin,
            "exists": bool(shutil.which(ffmpeg_bin) or Path(ffmpeg_bin).exists()),
            "hardware_h264_encoders": hardware,
            "has_libx264": "libx264" in encoders,
            "selected_auto": selected_auto,
        }

    @staticmethod
    def _nvidia_smi_info() -> dict:
        binary = shutil.which("nvidia-smi")
        if not binary:
            return {"available": False}
        try:
            result = subprocess.run(
                [
                    binary,
                    "--query-gpu=name,driver_version,memory.total,memory.free,utilization.gpu",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except Exception as exc:
            return {"available": True, "error": str(exc)}
        rows = []
        for line in (result.stdout or "").splitlines():
            parts = [part.strip() for part in line.split(",")]
            if len(parts) >= 5:
                rows.append({
                    "name": parts[0],
                    "driver_version": parts[1],
                    "memory_total_mb": parts[2],
                    "memory_free_mb": parts[3],
                    "utilization_gpu_percent": parts[4],
                })
        return {
            "available": result.returncode == 0,
            "returncode": result.returncode,
            "gpus": rows,
            "stderr": (result.stderr or "").strip(),
        }

    def _audio_runtime_info(self) -> dict:
        proc = getattr(self.audio_service, "_worker_proc", None)
        info = {
            "worker_running": bool(proc is not None and proc.poll() is None),
            "selected_model": getattr(self.audio_service, "model_key", ""),
        }
        try:
            python_exec = str(self.audio_service._pick_python())  # pylint: disable=protected-access
            info["python"] = python_exec
            result = subprocess.run(
                [
                    python_exec,
                    "-c",
                    (
                        "import json, sys\n"
                        "payload={'python_version': sys.version.split()[0], 'executable': sys.executable}\n"
                        "try:\n"
                        " import torch\n"
                        " payload['torch']={'installed': True, 'version': getattr(torch, '__version__', ''), "
                        "'cuda_available': bool(torch.cuda.is_available()), "
                        "'cuda_version': getattr(torch.version, 'cuda', None), "
                        "'device_count': int(torch.cuda.device_count()) if torch.cuda.is_available() else 0}\n"
                        "except Exception as exc:\n"
                        " payload['torch']={'installed': False, 'error': str(exc), 'cuda_available': False}\n"
                        "print(json.dumps(payload, ensure_ascii=False))\n"
                    ),
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode == 0 and result.stdout.strip():
                info.update(json.loads(result.stdout.strip()))
            elif result.stderr.strip():
                info["runtime_probe_error"] = result.stderr.strip()[-1200:]
        except Exception as exc:
            info["runtime_probe_error"] = str(exc)
        return info
