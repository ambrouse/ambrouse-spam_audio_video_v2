from __future__ import annotations

import concurrent.futures
import hashlib
import json
import math
import os
import random
import re
import shutil
import subprocess
import threading
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from auto_convert_text.pipeline.browser_bridge_client import DEFAULT_BRIDGE_BASE_URL, BrowserBridgeClient
from auto_convert_text.storage.project_store import ProjectStore


DEFAULT_VIDEO_GEMINI_PROMPT_TEMPLATE = (
    'Bạn là prompt engineer chuyên viết prompt ảnh điện ảnh manhua cho mô hình tạo ảnh.\n'
    'Yêu cầu bắt buộc:\n'
    '1. Trả về CHỈ 1 dòng prompt cuối cùng bằng tiếng Anh, không markdown, không giải thích.\n'
    '2. Không trả về ảnh, link, markdown image, data url, html, hoặc file attachment.\n'
    '3. Prompt phải chỉ đạo rõ: landscape 16:9, cinematic wide shot, ưu tiên độ nét cao.\n'
    '4. Nêu rõ nhân vật chính, bố cục tiền-trung-hậu cảnh, ánh sáng, camera angle, mood.\n'
    '4.1. Chỉ mô tả xung đột theo hướng biểu tượng, không mô tả gây sốc hoặc chi tiết thương tổn cơ thể.\n'
    '5. Bổ sung negative cues: no text, no watermark, no logo, blurry, low quality, oversaturated, deformed hands.\n'
    '5.1. Thêm safety cues: PG-13 fantasy tone, symbolic tension, elegant atmosphere, non-graphic storytelling.\n'
    '6. Độ dài 70-140 từ, không lặp lại tình tiết thô, chỉ giữ chi tiết giàu hình ảnh.\n'
    '\n'
    'Bối cảnh truyện: {story_context}\n'
    'Diễn biến cần minh họa:\n'
    '{scene_text}\n'
)

@dataclass
class VideoPipelineConfig:
    scene_duration_seconds: float = 30.0
    width: int = 1280
    height: int = 720
    fps: int = 24
    motion_intensity: float = 0.06
    provider: str = "bridge_gemini"
    image_provider: str = "bridge_gpt"
    cdp_url: str | None = None
    cdp_urls: list[str] | None = None
    gemini_cdp_url: str | None = None
    gemini_cdp_urls: list[str] | None = None
    gpt_cdp_url: str | None = None
    gpt_cdp_urls: list[str] | None = None
    prompt_parallel_workers: int = 1
    prompt_delay_seconds: float = 0.6
    sd_model_path: str | None = None
    sd_executable: str | None = None
    sd_steps: int = 24
    sd_cfg_scale: float = 7.0
    seed: int = 42
    gpt_image_limit: int = 10
    prompt_tts_input_limit: int = 12
    gemini_prompt_strict: bool = False
    llm_base_url: str = ""
    llm_model: str = "gemini/gemini-3-flash-preview"
    llm_api_key: str | None = None
    bridge_base_url: str = DEFAULT_BRIDGE_BASE_URL
    bridge_timeout_s: float = 600.0
    story_context: str = ""
    gemini_prompt_template: str = DEFAULT_VIDEO_GEMINI_PROMPT_TEMPLATE
    video_encoder: str = os.getenv("VIDEO_ENCODER", "auto")
    video_preset: str = os.getenv("VIDEO_PRESET", "quality")
    video_crf: int = 18
    video_cq: int = 18
    render_workers: int = int(os.getenv("VIDEO_RENDER_WORKERS", "6") or 6)


class VideoPipeline:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        self.store = ProjectStore(self.repo_root)
        self.ffmpeg_bin = self._resolve_ffmpeg_bin()
        self._ffmpeg_encoders_cache: set[str] | None = None
        self._ffmpeg_encoder_probe_cache: dict[str, bool] = {}

    def ensure_session_video_dirs(self, project_id: str, session_id: str) -> dict[str, Path]:
        session_dir = self.store.session_dir(project_id, session_id)
        if not session_dir.exists() or not session_dir.is_dir():
            raise FileNotFoundError(f"Session not found: {project_id}/{session_id}")
        video_root = session_dir / "video"
        images_dir = video_root / "images"
        prompts_dir = video_root / "prompts"
        renders_dir = video_root / "renders"
        final_dir = video_root / "final"
        manifests_dir = video_root / "manifests"
        for folder in [video_root, images_dir, prompts_dir, renders_dir, final_dir, manifests_dir]:
            folder.mkdir(parents=True, exist_ok=True)
        return {
            "session_dir": session_dir,
            "video_root": video_root,
            "images_dir": images_dir,
            "prompts_dir": prompts_dir,
            "renders_dir": renders_dir,
            "final_dir": final_dir,
            "manifests_dir": manifests_dir,
        }

    def prewarm(self, sd_executable: str | None = None, sd_model_path: str | None = None) -> dict:
        exe = self._resolve_sd_executable(sd_executable)
        model = self._resolve_sd_model_path(sd_model_path)
        ffmpeg_ok = self._check_ffmpeg()
        return {
            "ok": bool(exe and model and ffmpeg_ok),
            "ffmpeg_ok": ffmpeg_ok,
            "sd_executable": exe,
            "sd_model_path": model,
            "message": "Video runtime ready." if exe and model and ffmpeg_ok else "Video runtime missing executable/model/ffmpeg.",
        }

    def analyze_session(
        self,
        project_id: str,
        session_id: str,
        scene_duration_seconds: float = 30.0,
        image_count_limit: int | None = None,
        prompt_tts_input_limit: int | None = None,
    ) -> dict:
        dirs = self.ensure_session_video_dirs(project_id, session_id)
        audio_path = dirs["session_dir"] / "audio" / "combined.wav"
        tts_root = dirs["session_dir"] / "tts_inputs"
        tts_files = sorted(p for p in tts_root.glob("*.txt") if p.is_file())
        if not tts_files:
            raise FileNotFoundError(f"No tts input files found: {tts_root}")
        total_audio_seconds = self._resolve_session_audio_duration_seconds(dirs["session_dir"])
        max_images = max(1, min(120, int(image_count_limit or 10)))
        scene_count = min(max_images, max(1, len(tts_files)))
        safe_scene_duration = max(5.0, float(scene_duration_seconds or 30.0))
        if total_audio_seconds <= 0:
            total_audio_seconds = scene_count * safe_scene_duration

        groups = self._build_scene_groups(tts_files, scene_count, total_audio_seconds)
        prompt_tts_limit = max(1, min(240, int(prompt_tts_input_limit or 12)))
        selected_tts = self._apply_prompt_tts_sampling(groups, prompt_tts_limit)
        manifest = {
            "project_id": project_id,
            "session_id": session_id,
            "audio_path": self._rel(audio_path),
            "total_audio_seconds": round(total_audio_seconds, 3),
            "scene_duration_seconds": safe_scene_duration,
            "scene_count": scene_count,
            "max_images": max_images,
            "total_tts_inputs": len(tts_files),
            "prompt_tts_input_limit": prompt_tts_limit,
            "prompt_tts_inputs_selected": selected_tts,
            "groups": groups,
        }
        target = dirs["manifests_dir"] / "analysis_manifest.json"
        target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return manifest

    def generate_prompts(
        self,
        project_id: str,
        session_id: str,
        config: VideoPipelineConfig,
        progress_callback: Callable[[dict], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> dict:
        dirs = self.ensure_session_video_dirs(project_id, session_id)
        analysis = self.analyze_session(
            project_id,
            session_id,
            config.scene_duration_seconds,
            image_count_limit=config.gpt_image_limit,
            prompt_tts_input_limit=config.prompt_tts_input_limit,
        )
        story_context = str(config.story_context or "").strip() or self._load_story_context(project_id)
        gemini_prompt_template = str(config.gemini_prompt_template or "").strip() or DEFAULT_VIDEO_GEMINI_PROMPT_TEMPLATE
        total = len(analysis["groups"])
        prompt_items: list[dict] = [None] * total  # type: ignore[list-item]
        completed = 0

        prompt_delay_seconds = max(0.0, float(config.prompt_delay_seconds or 0.0))
        provider_name = str(config.provider or "").strip().lower()
        if provider_name in {"gemini_web", "openai", "openai_compat", ""}:
            provider_name = "bridge_gemini"
        if provider_name not in {"bridge_gemini", "fake"}:
            provider_name = "bridge_gemini"

        strict_env = os.getenv("VIDEO_GEMINI_PROMPT_STRICT", "0").strip().lower() in {"1", "true", "yes", "on"}
        strict_gemini_prompt = bool(config.gemini_prompt_strict) or strict_env

        bridge_client = BrowserBridgeClient(config.bridge_base_url, timeout_s=config.bridge_timeout_s)
        bridge_ports = self._gemini_bridge_ports_from_config(config)
        bridge_warmup = self._warm_bridge_ports(bridge_client, bridge_ports) if provider_name == "bridge_gemini" else {}

        def _process_group(index: int, group: dict) -> dict:
            grouped_text = self._read_group_texts(
                dirs["session_dir"],
                list(group.get("prompt_files") or group.get("files") or []),
            )
            final_prompt = self._sanitize_policy_safe_prompt(self._build_fallback_sd_prompt(story_context, grouped_text))
            prompt_source = "fallback"

            bridge_port = None
            bridge_request_id = ""
            if provider_name == "bridge_gemini":
                gemini_instruction = self._build_gemini_scene_prompt(
                    gemini_prompt_template,
                    story_context,
                    grouped_text,
                )
                for attempt in range(1, 4):
                    try:
                        payload, items = bridge_client.chat(
                            "gemini",
                            [gemini_instruction],
                            mode="fast",
                            timeout_s=config.bridge_timeout_s,
                            ports=bridge_ports,
                        )
                        item = items[0] if items else None
                        if not item or not item.success:
                            raise RuntimeError((item.error_message if item else None) or "Gemini bridge prompt failed.")
                        raw = (item.answer or "").strip()
                        candidate = self._sanitize_policy_safe_prompt(self._sanitize_image_prompt(raw))
                        if self._is_valid_image_prompt(candidate):
                            final_prompt = candidate
                            prompt_source = "bridge_gemini"
                            bridge_port = item.port
                            bridge_request_id = str(payload.get("request_id") or item.request_id or "")
                            break
                    except Exception:
                        if attempt >= 3:
                            break

            if strict_gemini_prompt and prompt_source != "bridge_gemini":
                raise RuntimeError(f"Gemini prompt generation failed for scene {index:04d}.")

            final_prompt = self._sanitize_policy_safe_prompt(final_prompt)

            prompt_path = dirs["prompts_dir"] / f"scene_{index:04d}.prompt.txt"
            prompt_path.write_text(final_prompt, encoding="utf-8")
            return {
                "scene_index": index,
                "prompt_path": self._rel(prompt_path),
                "source": prompt_source,
                "used_port": bridge_port,
                "bridge_request_id": bridge_request_id,
                "group_summary": {
                    "count": group["count"],
                    "duration_seconds": group["duration_seconds"],
                    "first_file": group["first_file"],
                    "last_file": group["last_file"],
                },
                "preview_text": final_prompt[:240],
            }

        max_prompt_workers = max(1, min(24, int(config.prompt_parallel_workers or 1)))
        if max_prompt_workers <= 1 or total <= 1:
            for index, group in enumerate(analysis["groups"], start=1):
                if should_stop and should_stop():
                    raise RuntimeError("STOP_REQUESTED")
                prompt_item = _process_group(index, group)
                prompt_items[index - 1] = prompt_item
                completed += 1
                if progress_callback:
                    progress_callback({
                        "stage": "video_prompts",
                        "current": completed,
                        "total": total,
                        "message": f"Generated prompt {index}/{total} via Gemini bridge",
                        "files_done": completed,
                        "preview_text": prompt_item.get("preview_text") or "",
                    })
                if prompt_delay_seconds > 0:
                    time.sleep(prompt_delay_seconds)
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_prompt_workers) as executor:
                futures = {
                    executor.submit(_process_group, index, group): index
                    for index, group in enumerate(analysis["groups"], start=1)
                }
                for future in concurrent.futures.as_completed(futures):
                    index = futures[future]
                    prompt_item = future.result()
                    prompt_items[index - 1] = prompt_item
                    completed += 1
                    if progress_callback:
                        progress_callback({
                            "stage": "video_prompts",
                            "current": completed,
                            "total": total,
                            "message": f"Generated prompt {index}/{total} via Gemini bridge",
                            "files_done": completed,
                            "preview_text": prompt_item.get("preview_text") or "",
                        })

        prompt_items = [item for item in prompt_items if isinstance(item, dict)]

        prompt_manifest = {
            "project_id": project_id,
            "session_id": session_id,
            "provider": provider_name,
            "bridge_base_url": bridge_client.base_url if provider_name == "bridge_gemini" else "",
            "bridge_ports": bridge_ports,
            "bridge_warmup": bridge_warmup,
            "story_context": story_context,
            "gemini_prompt_template": gemini_prompt_template,
            "scene_count": len(prompt_items),
            "items": prompt_items,
        }
        target = dirs["manifests_dir"] / "prompts_manifest.json"
        target.write_text(json.dumps(prompt_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return prompt_manifest

    def generate_images(
        self,
        project_id: str,
        session_id: str,
        config: VideoPipelineConfig,
        progress_callback: Callable[[dict], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> dict:
        dirs = self.ensure_session_video_dirs(project_id, session_id)
        prompts = sorted(p for p in dirs["prompts_dir"].glob("scene_*.prompt.txt") if p.is_file())
        if not prompts:
            raise FileNotFoundError("No scene prompt files found. Run prompt generation first.")
        image_provider = str(config.image_provider or config.provider or "bridge_gpt").strip().lower()
        max_images = max(1, min(120, int(config.gpt_image_limit or 10)))
        selected_prompts = prompts[:max_images]
        skipped = max(0, len(prompts) - len(selected_prompts))
        if image_provider in {"gpt_web", "gpt", "bridge_gpt"}:
            return self._generate_images_via_bridge_gpt(
                project_id=project_id,
                session_id=session_id,
                config=config,
                dirs=dirs,
                prompts=selected_prompts,
                skipped=skipped,
                progress_callback=progress_callback,
                should_stop=should_stop,
            )

        sd_exe = self._resolve_sd_executable(config.sd_executable)
        sd_model = self._resolve_sd_model_path(config.sd_model_path)
        allow_placeholder = os.getenv("VIDEO_ALLOW_PLACEHOLDER", "0").strip().lower() in {"1", "true", "yes", "on"}
        use_placeholder = False
        if not sd_exe or not sd_model:
            # Placeholder mode is opt-in only, to avoid accidental background-only image outputs.
            use_placeholder = config.provider == "fake" and allow_placeholder
            if not use_placeholder:
                raise FileNotFoundError(
                    "Stable Diffusion runtime is not configured. Set VIDEO_SD_EXECUTABLE and VIDEO_SD_MODEL_PATH "
                    "(or explicitly enable placeholder mode via VIDEO_ALLOW_PLACEHOLDER=1 for fake-provider smoke tests)."
                )

        items: list[dict] = []
        total = len(selected_prompts)
        for index, prompt_path in enumerate(selected_prompts, start=1):
            if should_stop and should_stop():
                raise RuntimeError("STOP_REQUESTED")
            prompt = prompt_path.read_text(encoding="utf-8", errors="replace").strip()
            image_path = dirs["images_dir"] / f"scene_{index:04d}.png"
            if use_placeholder:
                self._render_placeholder_image(
                    output_path=image_path,
                    width=config.width,
                    height=config.height,
                    scene_index=index,
                )
            else:
                self._run_sd_generate(
                    executable=sd_exe,
                    model_path=sd_model,
                    prompt=prompt,
                    output_path=image_path,
                    width=config.width,
                    height=config.height,
                    steps=config.sd_steps,
                    cfg_scale=config.sd_cfg_scale,
                    seed=config.seed + index,
                )
            items.append({
                "scene_index": index,
                "prompt_path": self._rel(prompt_path),
                "image_path": self._rel(image_path),
                "engine": "placeholder" if use_placeholder else "sd_gguf",
            })
            if progress_callback:
                progress_callback({
                    "stage": "video_images",
                    "current": index,
                    "total": total,
                    "message": f"Generated image {index}/{total}",
                    "files_done": index,
                    "preview_text": image_path.name,
                })

        image_manifest = {
            "project_id": project_id,
            "session_id": session_id,
            "model_path": sd_model or "",
            "engine": "placeholder" if use_placeholder else "sd_gguf",
            "scene_count": len(items),
            "max_images": max_images,
            "skipped": skipped,
            "items": items,
        }
        target = dirs["manifests_dir"] / "images_manifest.json"
        target.write_text(json.dumps(image_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return image_manifest

    def _generate_images_via_bridge_gpt(
        self,
        project_id: str,
        session_id: str,
        config: VideoPipelineConfig,
        dirs: dict[str, Path],
        prompts: list[Path],
        skipped: int,
        progress_callback: Callable[[dict], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> dict:
        client = BrowserBridgeClient(config.bridge_base_url, timeout_s=config.bridge_timeout_s)
        items: list[dict] = []
        total = len(prompts)
        prompt_rows: list[tuple[int, Path, str]] = []
        for index, prompt_path in enumerate(prompts, start=1):
            prompt = self._sanitize_policy_safe_prompt(prompt_path.read_text(encoding="utf-8", errors="replace").strip())
            prompt_rows.append((index, prompt_path, prompt))

        if should_stop and should_stop():
            raise RuntimeError("STOP_REQUESTED")
        if progress_callback:
            progress_callback({
                "stage": "video_images",
                "current": 0,
                "total": total,
                "message": f"Submitted {total} GPT image prompts to bridge batch",
                "files_done": 0,
                "preview_text": f"{total} prompts",
            })

        bridge_ports = self._gpt_bridge_ports_from_config(config)
        bridge_warmup = self._warm_bridge_ports(client, bridge_ports)
        batch_size = max(1, min(24, int(os.getenv("VIDEO_BRIDGE_BATCH_SIZE", "24") or 24)))
        for batch_start in range(0, len(prompt_rows), batch_size):
            if should_stop and should_stop():
                raise RuntimeError("STOP_REQUESTED")
            batch_rows = prompt_rows[batch_start : batch_start + batch_size]
            payload, bridge_items = client.image(
                "gpt",
                [prompt for _, _, prompt in batch_rows],
                max_images=1,
                timeout_s=config.bridge_timeout_s,
                ports=bridge_ports,
            )

            for offset, (index, prompt_path, _prompt) in enumerate(batch_rows):
                if should_stop and should_stop():
                    raise RuntimeError("STOP_REQUESTED")
                item = bridge_items[offset] if offset < len(bridge_items) else None
                if not item or not item.success or not item.images:
                    raise RuntimeError((item.error_message if item else None) or f"GPT bridge image failed for scene {index:04d}.")
                image_path = client.save_bridge_image(item.images[0], dirs["images_dir"] / f"scene_{index:04d}.png")
                self._validate_generated_image_file(image_path)
                row = {
                    "scene_index": index,
                    "prompt_path": self._rel(prompt_path),
                    "image_path": self._rel(image_path),
                    "engine": "bridge_gpt",
                    "used_port": item.port,
                    "bridge_request_id": str(payload.get("request_id") or item.request_id or ""),
                    "source_download_url": str((item.images[0] or {}).get("download_url") or ""),
                    "source_local_path": str((item.images[0] or {}).get("local_path") or ""),
                    "elapsed_ms": int(item.elapsed_ms or 0),
                    "byte_size": image_path.stat().st_size,
                }
                items.append(row)
                if progress_callback:
                    progress_callback({
                        "stage": "video_images",
                        "current": len(items),
                        "total": total,
                        "message": f"Generated image {index}/{total} via GPT bridge",
                        "files_done": len(items),
                        "preview_text": image_path.name,
                    })

        image_manifest = {
            "project_id": project_id,
            "session_id": session_id,
            "engine": "bridge_gpt",
            "bridge_base_url": client.base_url,
            "bridge_ports": bridge_ports,
            "bridge_warmup": bridge_warmup,
            "scene_count": len(items),
            "max_images": max(1, min(120, int(config.gpt_image_limit or 10))),
            "batch_size": batch_size,
            "skipped": skipped,
            "items": items,
        }
        target = dirs["manifests_dir"] / "images_manifest.json"
        target.write_text(json.dumps(image_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return image_manifest

    def build_native_renderer_input(
        self,
        project_id: str,
        session_id: str,
        config: VideoPipelineConfig,
        output_path: Path,
    ) -> dict:
        dirs = self.ensure_session_video_dirs(project_id, session_id)
        analysis_path = dirs["manifests_dir"] / "analysis_manifest.json"
        if analysis_path.exists():
            analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
        else:
            analysis = self.analyze_session(project_id, session_id, config.scene_duration_seconds)

        source_image_files = self._collect_scene_images(dirs["images_dir"])
        if not source_image_files:
            raise FileNotFoundError("No scene images found. Run image generation first.")

        raw_scene_duration = float(analysis.get("scene_duration_seconds") or config.scene_duration_seconds or 30.0)
        per_scene_duration = raw_scene_duration if 5.0 <= raw_scene_duration <= 300.0 else 30.0
        audio_seconds = float(analysis.get("total_audio_seconds") or 0.0)
        transition_seconds = min(1.2, max(0.45, per_scene_duration * 0.10))
        image_files = self._build_render_image_sequence(
            source_image_files,
            audio_seconds=audio_seconds,
            per_scene_duration=per_scene_duration,
            transition_seconds=transition_seconds,
            project_id=project_id,
            session_id=session_id,
        )
        width = max(512, int(config.width))
        height = max(512, int(config.height))
        fps = max(1, min(120, int(config.fps or 60)))
        motion = max(0.04, min(0.24, float(config.motion_intensity)))
        side_pad = max(60, int(width * 0.060))
        panel_width = max(320, width - side_pad * 2)
        logo_path = self._resolve_logo_path()
        palette = self._sample_image_palette(image_files[0])
        dust_color, dust_alpha, spark_color = self._choose_vfx_palette(palette)
        particle_seed = int(hashlib.sha256(f"{project_id}|{session_id}|{image_files[0].name}".encode("utf-8")).hexdigest()[:8], 16)

        audio_path = ""
        try:
            audio_candidate = self._resolve_audio_for_merge(dirs)
            audio_path = str(audio_candidate)
        except FileNotFoundError:
            audio_path = ""

        return {
            "schema_version": 1,
            "renderer": "native_gpu",
            "project_id": project_id,
            "session_id": session_id,
            "output_path": str(output_path),
            "session_dir": str(dirs["session_dir"]),
            "audio_path": audio_path,
            "runtime": {
                "ffmpeg_bin": str(self.ffmpeg_bin),
            },
            "video": {
                "width": width,
                "height": height,
                "fps": fps,
                "duration_seconds": round(max(audio_seconds, len(image_files) * per_scene_duration), 3),
                "scene_count": len(image_files),
                "per_scene_duration_seconds": per_scene_duration,
                "transition_seconds": transition_seconds,
                "encoder": str(config.video_encoder or "auto"),
                "preset": str(config.video_preset or "quality"),
                "cq": int(config.video_cq or 18),
                "crf": int(config.video_crf or 18),
            },
            "layout": {
                "side_pad": side_pad,
                "panel_width": panel_width,
                "panel_height": height,
                "motion_intensity": motion,
                "scroll_zoom": min(1.55, 1.34 + motion * 1.60),
                "vertical_travel": min(0.86, (0.18 + motion * 0.62) * 3.48),
            },
            "assets": {
                "images": [str(path) for path in image_files],
                "source_images": [str(path) for path in source_image_files],
                "logo_path": str(logo_path) if logo_path else "",
            },
            "visual_overlay": {
                "enabled": True,
                "particle_seed": particle_seed,
                "dust_color": dust_color,
                "spark_color": spark_color,
                "dust_alpha": round(dust_alpha, 3),
                "sampled_rgb": palette.get("sampled_rgb"),
                "dominant_rgb": palette.get("dominant_rgb"),
                "accent_rgb": palette.get("accent_rgb"),
                "audio_visualizer_enabled": bool(audio_path),
            },
        }

    @staticmethod
    def _sanitize_policy_safe_prompt(prompt: str) -> str:
        text = re.sub(r"\s+", " ", str(prompt or "")).strip()
        if not text:
            return (
                "Manhua cinematic fantasy, landscape 16:9, dramatic lighting, layered foreground-midground-background, "
                "high detail, symbolic tension, PG-13 tone, non-graphic storytelling, no text, no watermark, no logo."
            )

        replacements: list[tuple[str, str]] = [
            (r"\b(?:blood|bloody|gore|gory|slaughter|massacre)\b", "crimson energy"),
            (r"\b(?:kill|killing|killed|murder|murdered|assassin(?:ation)?)\b", "defeat"),
            (r"\b(?:death|dead|die|dying|corpse|severed)\b", "aftermath"),
            (r"\b(?:wound|wounded|injury|injured|torture|agonizing|agony|pain|tearing|ripped|writhing)\b", "hardship"),
            (r"\b(?:violent|violence|brutal|brutality)\b", "intense"),
            ("\\bm\u00e1u me\\b", "n\u0103ng l\u01b0\u1ee3ng \u0111\u1ecf"),
            ("\\bm\u00e1u\\b", "n\u0103ng l\u01b0\u1ee3ng \u0111\u1ecf"),
            ("\\b(?:gi\u1ebft|ch\u00e9m|\u0111\u00e2m|t\u00e0n s\u00e1t|th\u1ea3m s\u00e1t|tra t\u1ea5n)\\b", "\u0111\u1ed1i \u0111\u1ea7u"),
            ("\\b(?:ch\u1ebft|x\u00e1c|t\u1eed thi)\\b", "h\u1ec7 qu\u1ea3"),
            ("\\b(?:\u0111au \u0111\u1edbn|\u0111au nh\u00f3i|qu\u1eb1n qu\u1ea1i|x\u00e9 to\u1ea1c|x\u00e9 r\u00e1ch)\\b", "c\u0103ng th\u1eb3ng"),
        ]
        for pattern, replacement in replacements:
            text = re.sub(pattern, replacement, text, flags=re.I)

        safety_tail = (
            " PG-13 fantasy tone, symbolic conflict only, elegant atmosphere, "
            "non-graphic storytelling, no text, no watermark, no logo."
        )
        lower = text.lower()
        if "pg-13" not in lower:
            text += safety_tail
        return re.sub(r"\s+", " ", text).strip()

    def render_video(
        self,
        project_id: str,
        session_id: str,
        config: VideoPipelineConfig,
        output_name: str = "story_render.mp4",
        render_with_audio: bool = True,
        progress_callback: Callable[[dict], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> dict:
        dirs = self.ensure_session_video_dirs(project_id, session_id)
        analysis_path = dirs["manifests_dir"] / "analysis_manifest.json"
        if not analysis_path.exists():
            analysis = self.analyze_session(project_id, session_id, config.scene_duration_seconds)
        else:
            analysis = json.loads(analysis_path.read_text(encoding="utf-8"))

        source_image_files = self._collect_scene_images(dirs["images_dir"])
        if not source_image_files:
            raise FileNotFoundError("No scene images found. Run image generation first.")
        if not self._check_ffmpeg():
            raise RuntimeError("ffmpeg is required for video render.")

        render_started_at = time.perf_counter()
        render_timings: dict[str, float | list[dict]] = {}
        clips_dir = dirs["renders_dir"] / "clips"
        clips_dir.mkdir(parents=True, exist_ok=True)
        layer_cache_dir = dirs["renders_dir"] / "layer_cache"
        layer_cache_dir.mkdir(parents=True, exist_ok=True)
        raw_scene_duration = float(analysis.get("scene_duration_seconds") or config.scene_duration_seconds or 30.0)
        per_scene_duration = raw_scene_duration if 5.0 <= raw_scene_duration <= 300.0 else 30.0
        audio_seconds = float(analysis.get("total_audio_seconds") or 0.0)
        transition_seconds = min(1.2, max(0.45, per_scene_duration * 0.10))
        image_files = self._build_render_image_sequence(
            source_image_files,
            audio_seconds=audio_seconds,
            per_scene_duration=per_scene_duration,
            transition_seconds=transition_seconds,
            project_id=project_id,
            session_id=session_id,
        )
        total = len(image_files)
        # Honor the requested FPS so web controls and benchmark runs change actual render cost.
        fps = max(1, min(120, int(config.fps or 60)))
        width = max(512, int(config.width))
        height = max(512, int(config.height))
        # Use smooth start->end camera paths (seconds-based) instead of oscillation to avoid shake.
        motion = max(0.04, min(0.24, float(config.motion_intensity)))
        # Avoid over-upscaling pressure at 4K/60 when source images are around ~1K.
        high_res_output = max(width, height) >= 2160
        overscan = min(1.42 if high_res_output else 1.58, 1.20 + motion * 0.46)
        supersample = 1 if high_res_output else 2
        cam_width = width * supersample
        cam_height = height * supersample
        base_zoom_start = 1.03 + motion * 0.08
        speed_factor = 1.74 * 2.0
        fixed_scroll_zoom = min(1.55, 1.34 + motion * 1.60)
        frames = max(1, int(math.ceil(per_scene_duration * fps)))
        gop = max(30, fps * 2)
        clip_timeout = max(360, int(math.ceil(per_scene_duration * 16)))
        full_video_timeout = max(480, int(math.ceil(max(audio_seconds, per_scene_duration * total) * 8)))
        mux_timeout = max(300, int(math.ceil(max(audio_seconds, per_scene_duration * total) * 2)))
        requested_encoder = str(config.video_encoder or "auto").strip().lower() or "auto"
        selected_encoder = self._resolve_video_encoder(config.video_encoder)
        max_workers = max(1, min(8, int(config.render_workers or 6)))
        if selected_encoder != "libx264":
            # Clip renders are independent FFmpeg processes. Keep enough workers to
            # use underloaded NVENC/GPU paths without flooding VRAM on consumer GPUs.
            max_workers = min(max_workers, 6)

        def _clamp(value: float, low: float, high: float) -> float:
            return max(low, min(high, value))

        # Vertical-only scroll is steadier than diagonal crop movement on detailed generated art.
        vertical_travel = min(0.86, (0.18 + motion * 0.62) * speed_factor)
        center_x = 0.50

        fused_visual_overlay: dict | None = None
        fuse_single_scene_overlay = (
            len(image_files) == 1
            and not render_with_audio
            and str(os.getenv("SPAM_VIDEO_FUSE_SINGLE_SCENE_OVERLAY", "0")).strip().lower() in {"1", "true", "yes", "on"}
        )
        native_mode = str(os.getenv("SPAM_VIDEO_NATIVE_GPU_RENDER", "auto")).strip().lower()
        native_forced = native_mode in {"1", "true", "yes", "on", "force"}
        native_disabled = native_mode in {"0", "false", "no", "off", "disabled"}
        native_ratio = (float(width) / float(height)) if height > 0 else 0.0
        native_supported_contract = (
            width >= 512
            and height >= 288
            and 1.70 <= native_ratio <= 1.95
            and fps == 60
            and selected_encoder == "h264_nvenc"
        )
        use_native_gpu_clip = False
        native_renderer_bin: Path | None = None
        native_final_visual = False
        native_visual_overlay: dict | None = None
        native_visual_audio_path: Path | None = None
        native_fallback_reason = ""
        if not native_disabled:
            if not native_supported_contract:
                if native_forced:
                    raise RuntimeError("Native GPU renderer is locked to the production 4K60 h264_nvenc output contract.")
                native_fallback_reason = "native renderer supports only 16:9 60fps h264_nvenc outputs"
            else:
                try:
                    native_renderer_bin = self._resolve_native_story_renderer_bin()
                    use_native_gpu_clip = True
                except FileNotFoundError as exc:
                    if native_forced:
                        raise
                    native_fallback_reason = str(exc)
        if use_native_gpu_clip:
            if not native_supported_contract:
                raise RuntimeError("Native GPU renderer is locked to 16:9 60fps h264_nvenc outputs.")
            native_workers = str(os.getenv("SPAM_VIDEO_NATIVE_RENDER_WORKERS", "1") or "1").strip()
            try:
                native_worker_limit = max(1, min(2, int(native_workers)))
            except ValueError:
                native_worker_limit = 1
            max_workers = min(max_workers, native_worker_limit)
            native_final_visual = True
            native_audio_override = str(os.getenv("SPAM_VIDEO_NATIVE_AUDIO_PATH") or "").strip()
            if native_audio_override:
                candidate_audio = Path(native_audio_override)
                if candidate_audio.exists() and candidate_audio.is_file():
                    native_visual_audio_path = candidate_audio
            elif render_with_audio:
                try:
                    native_visual_audio_path = self._resolve_audio_for_merge(dirs)
                except FileNotFoundError:
                    native_visual_audio_path = None

            logo_path = self._resolve_logo_path()
            palette = self._sample_image_palette(image_files[0])
            dust_color, dust_alpha, spark_color = self._choose_vfx_palette(palette)
            seed_input = f"{project_id}|{session_id}|{image_files[0].name}"
            particle_seed = int(hashlib.sha256(seed_input.encode("utf-8")).hexdigest()[:8], 16)
            native_visual_overlay = {
                "enabled": True,
                "logo_path": logo_path,
                "particle_seed": particle_seed,
                "dust_particle_count": max(48, min(86, int(width / 20))),
                "spark_particle_count": max(14, min(32, int(width / 54))),
                "dust_color": dust_color,
                "spark_color": spark_color,
                "dust_alpha": round(dust_alpha, 3),
                "audio_visualizer_enabled": bool(native_visual_audio_path),
                "audio_visualizer_color": palette.get("accent_hex") or spark_color,
                "sampled_rgb": palette.get("average_rgb", []),
                "dominant_rgb": palette.get("dominant_rgb", []),
                "accent_rgb": palette.get("accent_rgb", []),
            }
            native_clip_dir = f"clips_native_{width}x{height}_{fps}"
            if native_visual_audio_path:
                native_clip_dir += "_av"
            clips_dir = dirs["renders_dir"] / native_clip_dir
            clips_dir.mkdir(parents=True, exist_ok=True)
        if fuse_single_scene_overlay:
            logo_path = self._resolve_logo_path()
            palette = self._sample_image_palette(image_files[0])
            dust_color, dust_alpha, spark_color = self._choose_vfx_palette(palette)
            seed_input = f"{project_id}|{session_id}|{image_files[0].name}"
            particle_seed = int(hashlib.sha256(seed_input.encode("utf-8")).hexdigest()[:8], 16)
            vfx_filter, dust_count, spark_count = self._build_particle_vfx_filter(
                width,
                height,
                particle_seed,
                dust_color,
                dust_alpha,
                spark_color,
            )
            fused_visual_overlay = {
                "enabled": True,
                "logo_path": logo_path,
                "vfx_filter": vfx_filter,
                "dust_particle_count": dust_count,
                "spark_particle_count": spark_count,
                "dust_color": dust_color,
                "spark_color": spark_color,
                "dust_alpha": round(dust_alpha, 3),
                "audio_visualizer_enabled": False,
                "audio_visualizer_color": palette.get("accent_hex") or spark_color,
                "sampled_rgb": palette.get("average_rgb", []),
                "dominant_rgb": palette.get("dominant_rgb", []),
                "accent_rgb": palette.get("accent_rgb", []),
            }

        clip_plan: list[dict] = []
        for index, image_path in enumerate(image_files, start=1):
            if should_stop and should_stop():
                raise RuntimeError("STOP_REQUESTED")
            clip_path = clips_dir / f"clip_{index:04d}.mp4"

            start_x = center_x

            z0 = _clamp(fixed_scroll_zoom, 1.12, 1.30)
            dur = max(1.0, per_scene_duration)
            scroll_period = max(28.8, min(37.2, dur / 0.47))
            scroll_center = 0.50
            scroll_amplitude = min(0.46, max(0.34, vertical_travel * 0.62))
            phase = -math.pi / 2 if index % 2 else math.pi / 2
            scroll_y_expr = (
                f"({scroll_center:.4f}+{scroll_amplitude:.4f}"
                f"*sin(2*PI*t/{scroll_period:.4f}+{phase:.4f}))"
            )
            side_pad = max(60, int(width * 0.060))
            panel_width = max(320, width - side_pad * 2)
            panel_height = height
            panel_cam_width = panel_width * supersample
            panel_cam_height = panel_height * supersample

            fg_static_width = int(panel_cam_width * overscan * z0)
            fg_static_height = int(panel_cam_height * overscan * z0)
            background_filter = (
                f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height},boxblur=lr=18:lp=2:cr=0:cp=0,"
                f"eq=saturation=0.88:brightness=-0.025,format=rgba[bg]"
            )
            foreground_filter = (
                # For small source images, upscale and recover edge contrast before camera moves.
                f"[0:v]scale='if(lt(iw,{int(width * 0.9)}),min(iw*2,{int(width * 1.45)}),iw)':"
                f"'if(lt(ih,{int(height * 0.9)}),min(ih*2,{int(height * 1.45)}),ih)':"
                f"flags=lanczos+accurate_rnd+full_chroma_int,"
                f"hqdn3d=0.9:0.9:4.5:4.5,"
                f"unsharp=5:5:0.38:5:5:0.0,"
                f"scale={fg_static_width}:{fg_static_height}:force_original_aspect_ratio=increase,"
                f"format=rgba[fg_static]"
            )
            filter_complex = (
                f"[1:v]crop={panel_cam_width}:{panel_cam_height}:"
                f"x='(in_w-out_w)*{start_x:.4f}':"
                f"y='(in_h-out_h)*{scroll_y_expr}',"
                f"scale={panel_width}:{panel_height}:flags=lanczos+accurate_rnd+full_chroma_int[fg];"
                f"[0:v][fg]overlay=x={side_pad}:y=0,"
                f"fps={fps},format=yuv420p[vout]"
            )
            legacy_filter_complex = (
                f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height},boxblur=lr=18:lp=2:cr=0:cp=0,"
                f"eq=saturation=0.88:brightness=-0.025[bg];"
                f"[0:v]scale='if(lt(iw,{int(width * 0.9)}),min(iw*2,{int(width * 1.45)}),iw)':"
                f"'if(lt(ih,{int(height * 0.9)}),min(ih*2,{int(height * 1.45)}),ih)':"
                f"flags=lanczos+accurate_rnd+full_chroma_int,"
                f"hqdn3d=0.9:0.9:4.5:4.5,"
                f"unsharp=5:5:0.38:5:5:0.0,"
                f"scale={fg_static_width}:{fg_static_height}:force_original_aspect_ratio=increase,"
                f"crop={panel_cam_width}:{panel_cam_height}:"
                f"x='(in_w-out_w)*{start_x:.4f}':"
                f"y='(in_h-out_h)*{scroll_y_expr}',"
                f"scale={panel_width}:{panel_height}:flags=lanczos+accurate_rnd+full_chroma_int[fg];"
                f"[bg][fg]overlay=x={side_pad}:y=0,"
                f"fps={fps},format=yuv420p[vout]"
            )
            fused_filter_complex = ""
            if fused_visual_overlay:
                logo_path = fused_visual_overlay.get("logo_path")
                logo_input_index = 2 if logo_path else None
                fused_parts = [
                    legacy_filter_complex.rsplit(",format=yuv420p[vout]", 1)[0] + ",format=rgba[base]",
                    f"[1:v]format=rgba,colorchannelmixer=aa=0,{fused_visual_overlay['vfx_filter']}[vfx]",
                    "[base][vfx]overlay=shortest=1:format=auto[vfxed]",
                ]
                current_label = "vfxed"
                if logo_path:
                    logo_width = max(28, min(int(side_pad * 0.68), int(width * 0.034)))
                    bottom_margin = max(8, int(height * 0.014))
                    fused_parts.extend([
                        f"[{logo_input_index}:v]scale=w='if(gt(iw,{logo_width}),{logo_width},iw)':h=-1:flags=lanczos,format=rgba,colorchannelmixer=aa=0.82[logo]",
                        f"[{current_label}][logo]overlay=x=main_w-{side_pad}+({side_pad}-overlay_w)/2:y=main_h-overlay_h-{bottom_margin}:format=auto,format=yuv420p[vout]",
                    ])
                else:
                    fused_parts.append(f"[{current_label}]format=yuv420p[vout]")
                fused_filter_complex = ";".join(fused_parts)
            layer_key = self._build_static_layer_key(
                image_path,
                width,
                height,
                fg_static_width,
                fg_static_height,
                background_filter,
                foreground_filter,
            )
            bg_layer = layer_cache_dir / f"scene_{index:04d}_{layer_key[:16]}_bg.png"
            fg_layer = layer_cache_dir / f"scene_{index:04d}_{layer_key[:16]}_fg.png"

            clip_plan.append({
                "index": index,
                "image_path": image_path,
                "clip_path": clip_path,
                "filter_complex": filter_complex,
                "legacy_filter_complex": legacy_filter_complex,
                "background_filter": background_filter,
                "foreground_filter": foreground_filter,
                "bg_layer": bg_layer,
                "fg_layer": fg_layer,
                "fused_filter_complex": fused_filter_complex,
                "fused_logo_path": fused_visual_overlay.get("logo_path") if fused_visual_overlay else None,
                "native_renderer": use_native_gpu_clip,
                "native_renderer_bin": str(native_renderer_bin) if native_renderer_bin else "",
                "native_scroll_zoom": overscan * z0,
                "native_report_path": str(clips_dir / f"clip_{index:04d}.native_report.json"),
                "native_input_path": str(clips_dir / f"clip_{index:04d}.native_input.json"),
                "native_final_visual": native_final_visual,
                "native_visual_overlay": native_visual_overlay,
                "native_visual_audio_path": str(native_visual_audio_path) if native_visual_audio_path else "",
            })

        clip_paths: list[Path] = []
        done_count = 0
        done_lock = threading.Lock()

        def _render_one_clip(plan: dict) -> tuple[int, Path, str, float]:
            clip_started_at = time.perf_counter()
            if should_stop and should_stop():
                raise RuntimeError("STOP_REQUESTED")
            idx = int(plan["index"])
            src_path = Path(plan["image_path"])
            out_path = Path(plan["clip_path"])
            if self._video_file_matches_render_contract(out_path, width, height, fps, per_scene_duration):
                return idx, out_path, src_path.name, 0.0
            out_path.unlink(missing_ok=True)
            if bool(plan.get("native_renderer")):
                self._render_native_gpu_clip(
                    renderer_bin=Path(str(plan["native_renderer_bin"])),
                    input_path=Path(str(plan["native_input_path"])),
                    report_path=Path(str(plan["native_report_path"])),
                    image_path=src_path,
                    output_path=out_path,
                    project_id=project_id,
                    session_id=session_id,
                    width=width,
                    height=height,
                    fps=fps,
                    duration_seconds=per_scene_duration,
                    audio_start_seconds=max(0.0, (idx - 1) * (per_scene_duration - transition_seconds)),
                    side_pad=side_pad,
                    panel_width=panel_width,
                    panel_height=panel_height,
                    motion_intensity=motion,
                    scroll_zoom=float(plan.get("native_scroll_zoom") or fixed_scroll_zoom),
                    vertical_travel=vertical_travel,
                    logo_path=Path(str(plan["native_visual_overlay"].get("logo_path"))) if plan.get("native_visual_overlay") and plan["native_visual_overlay"].get("logo_path") else None,
                    audio_path=Path(str(plan.get("native_visual_audio_path"))) if plan.get("native_visual_audio_path") else None,
                    visual_overlay=dict(plan.get("native_visual_overlay") or {"enabled": False}),
                    config=config,
                )
                return idx, out_path, src_path.name, round(time.perf_counter() - clip_started_at, 3)
            use_fused_overlay = bool(plan.get("fused_filter_complex"))
            use_static_layers = (
                not use_fused_overlay
                and str(os.getenv("SPAM_VIDEO_STATIC_LAYER_CACHE", "0")).strip().lower() in {"1", "true", "yes", "on"}
            )
            if use_static_layers:
                self._ensure_static_render_layer(src_path, Path(plan["bg_layer"]), str(plan["background_filter"]), "bg")
                self._ensure_static_render_layer(src_path, Path(plan["fg_layer"]), str(plan["foreground_filter"]), "fg_static")
                cmd = [
                    self.ffmpeg_bin,
                    "-y",
                    *self._build_filter_thread_args(),
                    "-loop",
                    "1",
                    "-i",
                    str(plan["bg_layer"]),
                    "-loop",
                    "1",
                    "-i",
                    str(plan["fg_layer"]),
                    "-filter_complex",
                    str(plan["filter_complex"]),
                    "-map",
                    "[vout]",
                    "-t",
                    str(per_scene_duration),
                    "-an",
                    *self._build_video_encode_args(selected_encoder, gop, fps, config),
                    "-movflags",
                    "+faststart",
                    str(out_path),
                ]
            else:
                cmd = [
                    self.ffmpeg_bin,
                    "-y",
                    *self._build_filter_thread_args(),
                    "-loop",
                    "1",
                    "-i",
                    str(src_path),
                ]
                if use_fused_overlay:
                    cmd.extend([
                        "-f",
                        "lavfi",
                        "-i",
                        f"nullsrc=s={width}x{height}:r={fps}",
                    ])
                    fused_logo_path = plan.get("fused_logo_path")
                    if fused_logo_path:
                        cmd.extend(["-i", str(fused_logo_path)])
                    filter_to_use = str(plan["fused_filter_complex"])
                else:
                    filter_to_use = str(plan["legacy_filter_complex"])
                cmd.extend([
                    "-filter_complex",
                    filter_to_use,
                    "-map",
                    "[vout]",
                    "-t",
                    str(per_scene_duration),
                    "-an",
                    *self._build_video_encode_args(selected_encoder, gop, fps, config),
                    "-movflags",
                    "+faststart",
                    str(out_path),
                ])
            self._run_cmd(cmd, timeout=clip_timeout)
            if not self._video_file_matches_render_contract(out_path, width, height, fps, per_scene_duration):
                raise RuntimeError(
                    "Rendered clip does not match the requested render contract "
                    f"({width}x{height}@{fps}, {per_scene_duration:.3f}s): {out_path}"
                )
            return idx, out_path, src_path.name, round(time.perf_counter() - clip_started_at, 3)

        if max_workers <= 1:
            clip_timings: list[dict] = []
            for plan in clip_plan:
                idx, out_path, preview_name, clip_elapsed = _render_one_clip(plan)
                clip_paths.append(out_path)
                clip_timings.append({"index": idx, "elapsed_s": clip_elapsed})
                done_count += 1
                if progress_callback:
                    progress_callback({
                        "stage": "video_render_clips",
                        "current": done_count,
                        "total": total,
                        "message": f"Rendered clip {idx}/{total}",
                        "files_done": done_count,
                        "preview_text": preview_name,
                    })
            render_timings["clips"] = clip_timings
        else:
            rendered: dict[int, Path] = {}
            clip_timings_by_index: dict[int, float] = {}
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(_render_one_clip, plan) for plan in clip_plan]
                for future in concurrent.futures.as_completed(futures):
                    idx, out_path, preview_name, clip_elapsed = future.result()
                    rendered[idx] = out_path
                    clip_timings_by_index[idx] = clip_elapsed
                    with done_lock:
                        done_count += 1
                        current_done = done_count
                    if progress_callback:
                        progress_callback({
                            "stage": "video_render_clips",
                            "current": current_done,
                            "total": total,
                            "message": f"Rendered clip {idx}/{total}",
                            "files_done": current_done,
                            "preview_text": preview_name,
                        })
            clip_paths = [rendered[idx] for idx in sorted(rendered.keys())]
            render_timings["clips"] = [
                {"index": idx, "elapsed_s": clip_timings_by_index[idx]}
                for idx in sorted(clip_timings_by_index.keys())
            ]

        safe_name = (output_name or "story_render.mp4").strip().replace("\\", "/").split("/")[-1]
        if not safe_name.lower().endswith(".mp4"):
            safe_name += ".mp4"
        silent_path = dirs["renders_dir"] / safe_name
        session_video_copy = dirs["video_root"] / safe_name
        combine_started_at = time.perf_counter()
        if len(clip_paths) <= 1:
            shutil.copy2(clip_paths[0], silent_path)
            render_timings["combine_clips_s"] = round(time.perf_counter() - combine_started_at, 3)
        else:
            xfade_cmd = [self.ffmpeg_bin, "-y"]
            xfade_cmd.extend(self._build_filter_thread_args())
            for clip in clip_paths:
                xfade_cmd.extend(["-i", str(clip)])

            filter_parts = []
            for idx in range(len(clip_paths)):
                filter_parts.append(f"[{idx}:v]settb=AVTB,format=yuv420p[v{idx}]")

            prev = "v0"
            for idx in range(1, len(clip_paths)):
                offset = idx * (per_scene_duration - transition_seconds)
                out = f"vx{idx}"
                filter_parts.append(
                    f"[{prev}][v{idx}]xfade=transition=dissolve:duration={transition_seconds:.3f}:offset={offset:.3f}[{out}]"
                )
                prev = out

            xfade_cmd.extend([
                "-filter_complex",
                ";".join(filter_parts),
                "-map",
                f"[{prev}]",
                "-an",
                *self._build_video_encode_args(selected_encoder, gop, fps, config),
                "-movflags",
                "+faststart",
                str(silent_path),
            ])
            self._run_cmd(xfade_cmd, timeout=full_video_timeout)
            render_timings["combine_clips_s"] = round(time.perf_counter() - combine_started_at, 3)

        overlay_audio_path: Path | None = None
        if render_with_audio:
            try:
                overlay_audio_path = self._resolve_audio_for_merge(dirs)
            except FileNotFoundError:
                overlay_audio_path = None

        if native_final_visual and native_visual_overlay:
            visual_overlay = {
                **{key: value for key, value in native_visual_overlay.items() if key != "logo_path"},
                "logo_path": self._safe_rel(native_visual_overlay.get("logo_path")) if native_visual_overlay.get("logo_path") else "",
                "native_shader_overlay": True,
            }
            render_timings["visual_overlay_s"] = 0.0
        elif fused_visual_overlay:
            visual_overlay_public = {key: value for key, value in fused_visual_overlay.items() if key != "vfx_filter"}
            visual_overlay = {
                **visual_overlay_public,
                "logo_path": self._safe_rel(fused_visual_overlay.get("logo_path")) if fused_visual_overlay.get("logo_path") else "",
                "fused_single_scene_overlay": True,
            }
        else:
            visual_overlay_started_at = time.perf_counter()
            visual_overlay = self._apply_visual_overlays(
                input_path=silent_path,
                reference_image=image_files[0],
                audio_path=overlay_audio_path,
                width=width,
                height=height,
                fps=fps,
                gop=gop,
                config=config,
                selected_encoder=selected_encoder,
                project_id=project_id,
                session_id=session_id,
                timeout=full_video_timeout,
                should_stop=should_stop,
            )
            render_timings["visual_overlay_s"] = round(time.perf_counter() - visual_overlay_started_at, 3)
        if progress_callback:
            progress_callback({
                "stage": "video_render_visual_overlays",
                "current": total,
                "total": total,
                "message": "Applied palette VFX, audio visualizer, and logo overlay.",
                "files_done": total,
                "preview_text": Path(visual_overlay.get("logo_path") or "").name or "palette VFX",
            })
        if session_video_copy != silent_path:
            shutil.copy2(silent_path, session_video_copy)

        render_with_audio_path: str = ""
        session_video_audio_path: str = ""
        if render_with_audio:
            if should_stop and should_stop():
                raise RuntimeError("STOP_REQUESTED")
            audio_path = overlay_audio_path or self._resolve_audio_for_merge(dirs)
            audio_name = self._derive_audio_render_name(safe_name)
            rendered_with_audio = dirs["renders_dir"] / audio_name
            session_audio_copy = dirs["video_root"] / audio_name
            audio_duration = self._read_wav_duration_seconds(audio_path)
            audio_duration_args = ["-t", f"{audio_duration:.3f}"] if audio_duration > 0 else []
            audio_cmd = [
                self.ffmpeg_bin,
                "-y",
                "-i",
                str(silent_path),
                "-i",
                str(audio_path),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-af",
                "aresample=async=1:first_pts=0",
                *audio_duration_args,
                "-shortest",
                "-movflags",
                "+faststart",
                str(rendered_with_audio),
            ]
            mux_started_at = time.perf_counter()
            self._run_cmd(audio_cmd, timeout=mux_timeout)
            render_timings["mux_audio_s"] = round(time.perf_counter() - mux_started_at, 3)
            if session_audio_copy != rendered_with_audio:
                shutil.copy2(rendered_with_audio, session_audio_copy)
            render_with_audio_path = self._rel(rendered_with_audio)
            session_video_audio_path = self._rel(session_audio_copy)
            if progress_callback:
                progress_callback({
                    "stage": "video_render_mux_audio",
                    "current": total,
                    "total": total,
                    "message": "Attached audio track to rendered video.",
                    "files_done": total,
                    "preview_text": audio_name,
                })

        manifest = {
            "project_id": project_id,
            "session_id": session_id,
            "render_path": self._rel(silent_path),
            "session_video_path": self._rel(session_video_copy),
            "render_with_audio_path": render_with_audio_path,
            "session_video_audio_path": session_video_audio_path,
            "scene_count": len(image_files),
            "source_scene_count": len(source_image_files),
            "per_image_duration_seconds": per_scene_duration,
            "audio_duration_seconds": round(audio_seconds, 3),
            "fps": fps,
            "width": width,
            "height": height,
            "motion_intensity": motion,
            "transition_seconds": transition_seconds,
            "requested_video_encoder": requested_encoder,
            "video_encoder": selected_encoder,
            "video_preset": str(config.video_preset or "quality"),
            "video_cq": int(config.video_cq or 18),
            "gpu_fallback_used": False,
            "visual_overlay": visual_overlay,
            "fallback_reason": "",
            "render_workers": max_workers,
            "native_gpu_renderer_used": bool(use_native_gpu_clip),
            "native_gpu_renderer_bin": self._safe_rel(native_renderer_bin) if native_renderer_bin else "",
            "native_gpu_renderer_mode": native_mode or "auto",
            "native_gpu_fallback_reason": native_fallback_reason,
            "timings_s": {
                **render_timings,
                "total_render_video_s": round(time.perf_counter() - render_started_at, 3),
            },
        }
        (dirs["manifests_dir"] / "render_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return manifest

    def _build_static_layer_key(
        self,
        image_path: Path,
        width: int,
        height: int,
        fg_static_width: int,
        fg_static_height: int,
        background_filter: str,
        foreground_filter: str,
    ) -> str:
        stat = image_path.stat()
        payload = {
            "version": 1,
            "image": str(image_path.resolve()),
            "mtime_ns": stat.st_mtime_ns,
            "size": stat.st_size,
            "width": width,
            "height": height,
            "fg_static_width": fg_static_width,
            "fg_static_height": fg_static_height,
            "background_filter": background_filter,
            "foreground_filter": foreground_filter,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _ensure_static_render_layer(self, source_image: Path, output_path: Path, filter_complex: str, output_label: str) -> None:
        if output_path.exists() and output_path.stat().st_size > 0:
            return
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = output_path.with_name(f"{output_path.stem}.tmp{output_path.suffix}")
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-i",
            str(source_image),
            "-filter_complex",
            filter_complex,
            "-map",
            f"[{output_label}]",
            "-frames:v",
            "1",
            "-f",
            "image2",
            str(temp_path),
        ]
        self._run_cmd(cmd, timeout=180)
        temp_path.replace(output_path)

    @staticmethod
    def _build_filter_thread_args() -> list[str]:
        raw_value = str(os.getenv("SPAM_FFMPEG_FILTER_THREADS") or "").strip()
        if not raw_value:
            return []
        try:
            thread_count = int(raw_value)
        except ValueError:
            thread_count = 0
        if thread_count <= 1:
            return []
        value = str(thread_count)
        return ["-filter_threads", value, "-filter_complex_threads", value]

    def merge_audio(
        self,
        project_id: str,
        session_id: str,
        silent_video_name: str = "story_render.mp4",
        output_name: str = "final_story.mp4",
    ) -> dict:
        dirs = self.ensure_session_video_dirs(project_id, session_id)
        if not self._check_ffmpeg():
            raise RuntimeError("ffmpeg is required for merge.")
        silent_path = self._resolve_video_for_merge(dirs, silent_video_name)
        audio_path = self._resolve_audio_for_merge(dirs)

        safe_name = (output_name or "final_story.mp4").strip().replace("\\", "/").split("/")[-1]
        if not safe_name.lower().endswith(".mp4"):
            safe_name += ".mp4"
        final_path = dirs["final_dir"] / safe_name
        session_video_copy = dirs["video_root"] / safe_name
        audio_duration = self._read_wav_duration_seconds(audio_path)
        audio_duration_args = ["-t", f"{audio_duration:.3f}"] if audio_duration > 0 else []
        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-i",
            str(silent_path),
            "-i",
            str(audio_path),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-af",
            "aresample=async=1:first_pts=0",
            *audio_duration_args,
            "-shortest",
            "-movflags",
            "+faststart",
            str(final_path),
        ]
        self._run_cmd(cmd, timeout=300)
        if session_video_copy != final_path:
            shutil.copy2(final_path, session_video_copy)
        merge_manifest = {
            "project_id": project_id,
            "session_id": session_id,
            "silent_video_path": self._rel(silent_path),
            "audio_path": self._rel(audio_path),
            "final_video_path": self._rel(final_path),
            "session_video_path": self._rel(session_video_copy),
        }
        (dirs["manifests_dir"] / "merge_manifest.json").write_text(
            json.dumps(merge_manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return merge_manifest

    @staticmethod
    def _build_render_image_sequence(
        source_image_files: list[Path],
        audio_seconds: float,
        per_scene_duration: float,
        transition_seconds: float,
        project_id: str,
        session_id: str,
    ) -> list[Path]:
        if not source_image_files:
            return []
        usable_duration = max(1.0, per_scene_duration - max(0.0, transition_seconds))
        if audio_seconds > 0:
            target_count = max(1, int(math.ceil(max(0.0, audio_seconds - transition_seconds) / usable_duration)))
        else:
            target_count = len(source_image_files)
        target_count = max(1, target_count)
        seed_input = f"{project_id}|{session_id}|render-image-cycle"
        rng = random.Random(int(hashlib.sha256(seed_input.encode("utf-8")).hexdigest()[:8], 16))
        sequence: list[Path] = []
        previous: Path | None = None
        while len(sequence) < target_count:
            batch = list(source_image_files)
            rng.shuffle(batch)
            if previous is not None and len(batch) > 1 and batch[0] == previous:
                batch.append(batch.pop(0))
            for item in batch:
                sequence.append(item)
                previous = item
                if len(sequence) >= target_count:
                    break
        return sequence

    def _apply_visual_overlays(
        self,
        input_path: Path,
        reference_image: Path,
        audio_path: Path | None,
        width: int,
        height: int,
        fps: int,
        gop: int,
        config: VideoPipelineConfig,
        selected_encoder: str,
        project_id: str,
        session_id: str,
        timeout: int = 480,
        should_stop: Callable[[], bool] | None = None,
    ) -> dict:
        if should_stop and should_stop():
            raise RuntimeError("STOP_REQUESTED")
        logo_path = self._resolve_logo_path()
        palette = self._sample_image_palette(reference_image)
        dust_color, dust_alpha, spark_color = self._choose_vfx_palette(palette)
        seed_input = f"{project_id}|{session_id}|{reference_image.name}"
        particle_seed = int(hashlib.sha256(seed_input.encode("utf-8")).hexdigest()[:8], 16)
        vfx_filter, dust_count, spark_count = self._build_particle_vfx_filter(
            width,
            height,
            particle_seed,
            dust_color,
            dust_alpha,
            spark_color,
        )
        audio_visualizer_enabled = bool(audio_path and audio_path.exists() and audio_path.is_file())
        visualizer_color = palette.get("accent_hex") or spark_color

        temp_path = input_path.with_name(f"{input_path.stem}_visual_tmp{input_path.suffix}")
        if temp_path.exists():
            temp_path.unlink()

        cmd = [
            self.ffmpeg_bin,
            "-y",
            *self._build_filter_thread_args(),
            "-i",
            str(input_path),
            "-f",
            "lavfi",
            "-i",
            f"nullsrc=s={width}x{height}:r={fps}",
        ]
        audio_input_index: int | None = None
        if audio_visualizer_enabled and audio_path:
            audio_input_index = 2
            cmd.extend(["-i", str(audio_path)])

        filter_parts = [
            "[0:v]format=rgba[base]",
            f"[1:v]format=rgba,colorchannelmixer=aa=0,{vfx_filter}[vfx]",
            "[base][vfx]overlay=shortest=1:format=auto[vfxed]",
        ]
        current_label = "vfxed"
        if audio_input_index is not None:
            bar_height = max(34, min(86, int(height * 0.075)))
            bar_width = max(320, min(width - max(96, int(width * 0.16)), int(width * 0.78)))
            bottom_gap = max(64, int(height * 0.105))
            bar_y = max(0, height - bar_height - bottom_gap)
            filter_parts.extend([
                (
                    f"[{audio_input_index}:a]aresample=48000,"
                    f"showfreqs=s={bar_width}x{bar_height}:mode=bar:ascale=sqrt:fscale=log:"
                    f"colors={visualizer_color}@0.82,"
                    "format=rgba,colorkey=0x000000:0.08:0.12,"
                    "colorchannelmixer=aa=0.64[audio_viz]"
                ),
                (
                    f"[{current_label}][audio_viz]overlay=x=(main_w-overlay_w)/2:y={bar_y}:"
                    "format=auto:eof_action=pass[visualized]"
                ),
            ])
            current_label = "visualized"
        if logo_path:
            cmd.extend(["-i", str(logo_path)])
            logo_input_index = 3 if audio_input_index is not None else 2
            side_pad = max(60, int(width * 0.060))
            bottom_margin = max(8, int(height * 0.014))
            logo_width = max(28, min(int(side_pad * 0.68), int(width * 0.034)))
            filter_parts.extend([
                f"[{logo_input_index}:v]scale=w='if(gt(iw,{logo_width}),{logo_width},iw)':h=-1:flags=lanczos,format=rgba,colorchannelmixer=aa=0.82[logo]",
                f"[{current_label}][logo]overlay=x=main_w-{side_pad}+({side_pad}-overlay_w)/2:y=main_h-overlay_h-{bottom_margin}:format=auto,format=yuv420p[vout]",
            ])
        else:
            filter_parts.append(f"[{current_label}]format=yuv420p[vout]")

        filter_script = temp_path.with_name(f"{temp_path.stem}_filter.txt")
        filter_script.write_text(";".join(filter_parts), encoding="utf-8")
        cmd.extend([
            "-filter_complex_script",
            str(filter_script),
            "-map",
            "[vout]",
            "-an",
            *self._build_video_encode_args(selected_encoder, gop, fps, config),
            "-movflags",
            "+faststart",
            str(temp_path),
        ])
        try:
            self._run_cmd(cmd, timeout=timeout)
            temp_path.replace(input_path)
        finally:
            try:
                filter_script.unlink()
            except OSError:
                pass
        return {
            "enabled": True,
            "logo_path": self._safe_rel(logo_path) if logo_path else "",
            "dust_particle_count": dust_count,
            "spark_particle_count": spark_count,
            "dust_color": dust_color,
            "spark_color": spark_color,
            "dust_alpha": round(dust_alpha, 3),
            "audio_visualizer_enabled": audio_visualizer_enabled,
            "audio_visualizer_color": visualizer_color,
            "sampled_rgb": palette.get("average_rgb", []),
            "dominant_rgb": palette.get("dominant_rgb", []),
            "accent_rgb": palette.get("accent_rgb", []),
        }

    def _resolve_logo_path(self) -> Path | None:
        logo_roots = [
            self.repo_root / "media-logo" / "logo",
            self.repo_root.parent / "media-logo" / "logo",
        ]
        exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
        for root in logo_roots:
            if not root.exists() or not root.is_dir():
                continue
            files = sorted(
                (p for p in root.iterdir() if p.is_file() and p.suffix.lower() in exts),
                key=lambda p: p.name.lower(),
            )
            if files:
                return files[0]
        return None

    def _choose_vfx_palette(self, palette: dict) -> tuple[str, float, str]:
        average_rgb = tuple(int(v) for v in (palette.get("average_rgb") or [156, 150, 138])[:3])
        dominant_hex = str(palette.get("dominant_hex") or self._rgb_to_ffmpeg_hex(average_rgb))
        accent_hex = str(palette.get("accent_hex") or dominant_hex)
        lum = self._relative_luminance(average_rgb)
        if lum > 205:
            return "0x171513", 0.28, accent_hex
        if lum > 150:
            return "0xF2EEE4", 0.20, accent_hex
        return "0xF7F7EE", 0.34, accent_hex

    def _sample_average_rgb(self, image_path: Path) -> tuple[int, int, int]:
        palette = self._sample_image_palette(image_path)
        rgb = palette.get("average_rgb") or [156, 150, 138]
        return (int(rgb[0]), int(rgb[1]), int(rgb[2]))

    def _sample_image_palette(self, image_path: Path) -> dict:
        try:
            result = subprocess.run(
                [
                    self.ffmpeg_bin,
                    "-v",
                    "error",
                    "-i",
                    str(image_path),
                    "-vf",
                    "scale=16:16:force_original_aspect_ratio=decrease,pad=16:16:(ow-iw)/2:(oh-ih)/2,format=rgb24",
                    "-frames:v",
                    "1",
                    "-f",
                    "rawvideo",
                    "pipe:1",
                ],
                cwd=str(self.repo_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=60,
                check=False,
            )
            if result.returncode == 0 and len(result.stdout) >= 3:
                pixels = [
                    (result.stdout[idx], result.stdout[idx + 1], result.stdout[idx + 2])
                    for idx in range(0, len(result.stdout) - 2, 3)
                ]
                if pixels:
                    return self._build_palette_from_pixels(pixels)
        except Exception:
            pass
        fallback = (156, 150, 138)
        fallback_hex = self._rgb_to_ffmpeg_hex(fallback)
        return {
            "average_rgb": [fallback[0], fallback[1], fallback[2]],
            "dominant_rgb": [fallback[0], fallback[1], fallback[2]],
            "accent_rgb": [fallback[0], fallback[1], fallback[2]],
            "dominant_hex": fallback_hex,
            "accent_hex": fallback_hex,
        }

    @staticmethod
    def _build_palette_from_pixels(pixels: list[tuple[int, int, int]]) -> dict:
        if not pixels:
            fallback = (156, 150, 138)
            fallback_hex = VideoPipeline._rgb_to_ffmpeg_hex(fallback)
            return {
                "average_rgb": [fallback[0], fallback[1], fallback[2]],
                "dominant_rgb": [fallback[0], fallback[1], fallback[2]],
                "accent_rgb": [fallback[0], fallback[1], fallback[2]],
                "dominant_hex": fallback_hex,
                "accent_hex": fallback_hex,
            }

        avg = tuple(int(sum(pixel[channel] for pixel in pixels) / len(pixels)) for channel in range(3))
        buckets: dict[tuple[int, int, int], dict[str, float | int | tuple[int, int, int]]] = {}
        for rgb in pixels:
            if max(rgb) < 10:
                continue
            key = tuple((value // 32) * 32 + 16 for value in rgb)
            bucket = buckets.setdefault(key, {"count": 0, "r": 0, "g": 0, "b": 0, "rgb": key})
            bucket["count"] = int(bucket["count"]) + 1
            bucket["r"] = int(bucket["r"]) + rgb[0]
            bucket["g"] = int(bucket["g"]) + rgb[1]
            bucket["b"] = int(bucket["b"]) + rgb[2]

        if not buckets:
            dominant = avg
            accent = avg
        else:
            ranked = sorted(
                buckets.values(),
                key=lambda item: int(item["count"]),
                reverse=True,
            )
            top = ranked[0]
            dominant = (
                int(int(top["r"]) / int(top["count"])),
                int(int(top["g"]) / int(top["count"])),
                int(int(top["b"]) / int(top["count"])),
            )

            def accent_score(item: dict[str, float | int | tuple[int, int, int]]) -> float:
                count = int(item["count"])
                rgb = (
                    int(int(item["r"]) / count),
                    int(int(item["g"]) / count),
                    int(int(item["b"]) / count),
                )
                lum = VideoPipeline._relative_luminance(rgb)
                saturation = (max(rgb) - min(rgb)) / 255.0
                distance = math.sqrt(sum((rgb[idx] - dominant[idx]) ** 2 for idx in range(3))) / 441.7
                light_bonus = 1.0 - abs(lum - 170.0) / 170.0
                return (saturation * 1.45) + (distance * 0.75) + (light_bonus * 0.35) + min(count, 32) / 160.0

            accent_item = max(ranked[: min(10, len(ranked))], key=accent_score)
            accent_count = int(accent_item["count"])
            accent = (
                int(int(accent_item["r"]) / accent_count),
                int(int(accent_item["g"]) / accent_count),
                int(int(accent_item["b"]) / accent_count),
            )

        accent = VideoPipeline._soften_visualizer_rgb(accent, avg)
        return {
            "average_rgb": [avg[0], avg[1], avg[2]],
            "dominant_rgb": [dominant[0], dominant[1], dominant[2]],
            "accent_rgb": [accent[0], accent[1], accent[2]],
            "dominant_hex": VideoPipeline._rgb_to_ffmpeg_hex(dominant),
            "accent_hex": VideoPipeline._rgb_to_ffmpeg_hex(accent),
        }

    @staticmethod
    def _soften_visualizer_rgb(rgb: tuple[int, int, int], average_rgb: tuple[int, int, int]) -> tuple[int, int, int]:
        lum = VideoPipeline._relative_luminance(rgb)
        mixed = tuple(int(rgb[idx] * 0.72 + average_rgb[idx] * 0.28) for idx in range(3))
        if lum < 95:
            mixed = tuple(min(255, int(value * 1.34 + 26)) for value in mixed)
        elif lum > 218:
            mixed = tuple(max(0, int(value * 0.82)) for value in mixed)
        return mixed

    @staticmethod
    def _relative_luminance(rgb: tuple[int, int, int]) -> float:
        return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]

    @staticmethod
    def _rgb_to_ffmpeg_hex(rgb: tuple[int, int, int]) -> str:
        return f"0x{max(0, min(255, int(rgb[0]))):02X}{max(0, min(255, int(rgb[1]))):02X}{max(0, min(255, int(rgb[2]))):02X}"

    @staticmethod
    def _build_particle_vfx_filter(
        width: int,
        height: int,
        seed: int,
        dust_color: str,
        dust_alpha: float,
        spark_color: str,
    ) -> tuple[str, int, int]:
        rng = random.Random(seed)
        dust_count = max(48, min(86, int(width / 20)))
        spark_count = max(14, min(32, int(width / 54)))
        margin = max(30, int(height * 0.08))
        parts: list[str] = []
        for index in range(dust_count):
            width_px = rng.choice([2, 2, 3, 3, 4])
            height_px = rng.choice([5, 6, 8, 10, 12])
            lane_width = width / dust_count
            x0 = lane_width * (index + 0.5) + rng.uniform(-lane_width * 0.28, lane_width * 0.28)
            y0 = (((index * 0.61803398875) % 1.0) * (height + margin * 2)) + rng.uniform(-margin * 0.28, margin * 0.28)
            speed = rng.uniform(height * 0.012, height * 0.038)
            sway = rng.uniform(width * 0.003, width * 0.014)
            phase = rng.uniform(0.16, 0.42)
            offset = rng.uniform(0.0, math.tau)
            alpha = max(0.12, min(0.46, dust_alpha * rng.uniform(0.70, 1.18)))
            x_expr = f"{x0:.3f}+sin(t*{phase:.4f}+{offset:.4f})*{sway:.3f}"
            y_expr = f"mod({y0:.3f}+t*{speed:.4f}\\,h+{margin * 2})-{margin}"
            parts.append(
                f"drawbox=x='{x_expr}':y='{y_expr}':w={width_px}:h={height_px}:color={dust_color}@{alpha:.3f}:t=fill:replace=1"
            )

        lower_band = height * 0.56
        side_safe = max(42, int(width * 0.045))
        for index in range(spark_count):
            lane = index / max(1, spark_count - 1)
            side_bias = lane if index % 3 else rng.choice([rng.uniform(0.0, 0.18), rng.uniform(0.82, 1.0)])
            x0 = side_safe + side_bias * max(1, width - side_safe * 2) + rng.uniform(-width * 0.018, width * 0.018)
            y0 = lower_band + rng.random() * height * 0.36
            rise = rng.uniform(height * 0.030, height * 0.088)
            sway = rng.uniform(width * 0.002, width * 0.010)
            phase = rng.uniform(0.55, 1.10)
            offset = rng.uniform(0.0, math.tau)
            width_px = rng.choice([2, 2, 3])
            height_px = rng.choice([16, 20, 24, 30])
            alpha = rng.uniform(0.32, 0.62)
            x_expr = f"{x0:.3f}+sin(t*{phase:.4f}+{offset:.4f})*{sway:.3f}"
            y_expr = f"mod({y0:.3f}-t*{rise:.4f}\\,h+{margin * 2})-{margin}"
            parts.append(
                f"drawbox=x='{x_expr}':y='{y_expr}':w={width_px}:h={height_px}:color={spark_color}@{alpha:.3f}:t=fill:replace=1"
            )
        return ",".join(parts), dust_count, spark_count

    def run_full(
        self,
        project_id: str,
        session_id: str,
        config: VideoPipelineConfig,
        merge_audio: bool = True,
        progress_callback: Callable[[dict], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> dict:
        prompts = self.generate_prompts(
            project_id=project_id,
            session_id=session_id,
            config=config,
            progress_callback=progress_callback,
            should_stop=should_stop,
        )
        images = self.generate_images(
            project_id=project_id,
            session_id=session_id,
            config=config,
            progress_callback=progress_callback,
            should_stop=should_stop,
        )
        render = self.render_video(
            project_id=project_id,
            session_id=session_id,
            config=config,
            progress_callback=progress_callback,
            should_stop=should_stop,
        )
        merged = None
        if merge_audio:
            merged = self.merge_audio(project_id, session_id)
        return {
            "success": True,
            "project_id": project_id,
            "session_id": session_id,
            "prompts": prompts,
            "images": images,
            "render": render,
            "merge": merged,
        }

    def _build_scene_groups(self, tts_files: list[Path], scene_count: int, total_audio_seconds: float = 0.0) -> list[dict]:
        total_files = len(tts_files)
        if scene_count <= 0:
            scene_count = 1
        base, extra = divmod(total_files, scene_count)
        groups: list[dict] = []
        cursor = 0
        for idx in range(scene_count):
            take = base + (1 if idx < extra else 0)
            if take <= 0:
                break
            slice_files = tts_files[cursor: cursor + take]
            cursor += take
            names = [p.name for p in slice_files]
            groups.append({
                "scene_index": idx + 1,
                "files": names,
                "count": len(names),
                "first_file": names[0],
                "last_file": names[-1],
                "duration_seconds": round((total_audio_seconds / scene_count) if total_audio_seconds > 0 else 0.0, 3),
            })
        if not groups and tts_files:
            groups = [{
                "scene_index": 1,
                "files": [p.name for p in tts_files],
                "count": len(tts_files),
                "first_file": tts_files[0].name,
                "last_file": tts_files[-1].name,
                "duration_seconds": round(total_audio_seconds, 3) if total_audio_seconds > 0 else 0.0,
            }]
        return groups

    @staticmethod
    def _evenly_spaced_indices(length: int, count: int) -> list[int]:
        if length <= 0 or count <= 0:
            return []
        if count >= length:
            return list(range(length))
        if count == 1:
            return [length // 2]
        return sorted({int(round(i * (length - 1) / (count - 1))) for i in range(count)})

    @classmethod
    def _sample_diverse_clustered(cls, items: list[str], limit: int) -> list[str]:
        total = len(items)
        cap = max(0, int(limit or 0))
        if cap <= 0 or total <= 0:
            return []
        if cap >= total:
            return list(items)

        clusters = min(3, cap)
        base = cap // clusters
        rem = cap % clusters
        anchors = cls._evenly_spaced_indices(total, clusters)

        selected: set[int] = set()
        for idx, anchor in enumerate(anchors):
            take = base + (1 if idx < rem else 0)
            if take <= 0:
                continue
            start = max(0, min(total - take, anchor - (take // 2)))
            for pos in range(start, start + take):
                selected.add(pos)

        if len(selected) < cap:
            for pos in cls._evenly_spaced_indices(total, cap):
                selected.add(pos)
                if len(selected) >= cap:
                    break

        ordered = sorted(selected)[:cap]
        return [items[pos] for pos in ordered]

    @classmethod
    def _apply_prompt_tts_sampling(cls, groups: list[dict], prompt_tts_limit: int) -> int:
        if not groups:
            return 0

        all_files: list[str] = []
        for group in groups:
            all_files.extend(list(group.get("files") or []))

        total_available = len(all_files)
        if total_available <= 0:
            for group in groups:
                group["prompt_files"] = []
                group["prompt_count"] = 0
            return 0

        cap = max(1, min(240, int(prompt_tts_limit or 12)))
        scene_count = len(groups)
        window = min(total_available, cap)

        max_start = max(0, total_available - window)
        if scene_count <= 1:
            starts = [max_start // 2]
        else:
            starts = cls._evenly_spaced_indices(max_start + 1, scene_count)

        if len(starts) < scene_count:
            starts.extend([max_start] * (scene_count - len(starts)))

        selected_total = 0
        for idx, group in enumerate(groups):
            start = min(max_start, max(0, starts[idx]))
            end = min(total_available, start + window)
            picked = all_files[start:end]
            group["prompt_files"] = picked
            group["prompt_count"] = len(picked)
            group["prompt_range"] = {"start": start, "end": max(start, end - 1)}
            selected_total += len(picked)
        return selected_total

    @staticmethod
    def _collect_scene_images(images_dir: Path) -> list[Path]:
        pattern = re.compile(r"^scene_(\d{4})\.(png|jpg|jpeg|webp)$", re.IGNORECASE)
        indexed: dict[int, Path] = {}
        for path in images_dir.glob("scene_*.*"):
            if not path.is_file():
                continue
            match = pattern.match(path.name)
            if not match:
                continue
            scene_index = int(match.group(1))
            indexed[scene_index] = path
        return [indexed[idx] for idx in sorted(indexed.keys())]

    def _read_group_texts(self, session_dir: Path, filenames: list[str]) -> str:
        tts_root = session_dir / "tts_inputs"
        chunks: list[str] = []
        for name in filenames:
            path = (tts_root / name).resolve()
            if path.parent != tts_root.resolve() or not path.exists() or not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace").strip()
            if text:
                chunks.append(text)
        return "\n".join(chunks)

    @staticmethod
    def _build_scene_prompt(story_context: str, grouped_text: str) -> str:
        context = (story_context or "").strip()
        text = (grouped_text or "").strip()
        return (
            "Minh hoa 1 canh truyen tranh manhua, cinematic, chi tiet nhan vat va boi canh, "
            "anh chat luong cao, composition ro rang, anh sach, khong chu, khong watermark.\n"
            f"Boi canh truyen: {context}\n"
            "Dien bien can minh hoa:\n"
            f"{text}"
        ).strip()

    @staticmethod
    def _build_fallback_sd_prompt(story_context: str, grouped_text: str) -> str:
        context = " ".join((story_context or "").split())[:220]
        scene = " ".join((grouped_text or "").split())[:900]
        return (
            "masterpiece, best quality, manhua style, cinematic composition, dramatic lighting, "
            "detailed characters, dynamic pose, high detail environment, no text, no watermark, no logo. "
            f"story context: {context}. "
            f"scene: {scene}"
        ).strip()

    @staticmethod
    def _build_gemini_scene_prompt(prompt_template: str, story_context: str, grouped_text: str) -> str:
        context = (story_context or "").strip()
        scene = (grouped_text or "").strip()
        template = (prompt_template or "").strip() or DEFAULT_VIDEO_GEMINI_PROMPT_TEMPLATE
        try:
            rendered = template.format(story_context=context, scene_text=scene)
        except Exception:
            rendered = DEFAULT_VIDEO_GEMINI_PROMPT_TEMPLATE.format(story_context=context, scene_text=scene)
        return rendered.strip()

    @staticmethod
    def _sanitize_image_prompt(output: str) -> str:
        text = (output or "").replace("\r\n", "\n").strip()
        if not text:
            return ""
        if VideoPipeline._looks_like_image_response(text):
            return ""
        text = re.sub(r"^\s*gemini\s+said[:\s-]*", "", text, flags=re.I)
        text = text.replace("```", "")
        text = re.sub(r"^\s*(?:prompt|final prompt|positive prompt)\s*:\s*", "", text, flags=re.I)
        text = re.sub(r"^\s*(?:here is|sure[, ]+)\s*", "", text, flags=re.I)
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        filtered: list[str] = []
        for line in lines:
            ll = line.lower()
            if ll in {"show thinking", "hide thinking"}:
                continue
            if ll.startswith("ban la ") or ll.startswith("bạn là "):
                continue
            if ll.startswith("yeu cau") or ll.startswith("yêu cầu"):
                continue
            if ll.startswith("dien bien") or ll.startswith("diễn biến"):
                continue
            if ll.startswith("boi canh") or ll.startswith("bối cảnh"):
                continue
            if re.match(r"^\d+[\).]\s+", ll):
                continue
            if ll.startswith("negative prompt:"):
                continue
            if VideoPipeline._looks_like_image_response(line):
                continue
            line = re.sub(r"^\s*(?:prompt|final prompt|positive prompt)\s*:\s*", "", line, flags=re.I)
            filtered.append(line)
        if not filtered:
            return ""
        # Pick the richest candidate instead of always taking the last line.
        candidate = max(filtered, key=lambda item: len(item.strip()))
        candidate = re.sub(r"\s+", " ", candidate).strip(" .")
        return candidate

    @staticmethod
    def _is_valid_image_prompt(prompt: str) -> bool:
        text = (prompt or "").strip()
        if len(text) < 40 or len(text) > 800:
            return False
        if VideoPipeline._looks_like_image_response(text):
            return False
        lower = text.lower()
        blocked = [
            "ban la bien tap",
            "yeu cau",
            "noi dung chapter",
            "toi tiep tuc cau chuyen",
            "show thinking",
            "hide thinking",
            "final prompt:",
            "negative prompt:",
        ]
        if any(token in lower for token in blocked):
            return False
        return True

    @staticmethod
    def _looks_like_image_response(text: str) -> bool:
        raw = (text or "").strip()
        if not raw:
            return False
        lower = raw.lower()
        markers = [
            "![",
            "<img",
            "data:image/",
            "blob:http",
            "blob:",
            "image/png",
            "image/jpeg",
            "image/webp",
            "attachment",
            "sandbox:/mnt/data",
        ]
        if any(token in lower for token in markers):
            return True
        if re.search(r"https?://\S+", raw, flags=re.I):
            image_url = re.search(r"https?://\S+\.(?:png|jpg|jpeg|webp|gif)(?:\?\S*)?", raw, flags=re.I)
            if image_url:
                return True
            # Treat bare single-link responses as invalid prompt payloads.
            if len(raw) <= 260 and re.fullmatch(r"https?://\S+", raw, flags=re.I):
                return True
        return False

    @staticmethod
    def _validate_generated_image_file(path: Path) -> None:
        if not path.exists() or not path.is_file() or path.stat().st_size <= 0:
            raise RuntimeError(f"Generated image is missing or empty: {path}")
        header = path.read_bytes()[:16]
        valid = (
            header.startswith(b"\x89PNG\r\n\x1a\n")
            or header.startswith(b"\xff\xd8\xff")
            or header.startswith(b"RIFF") and b"WEBP" in header
        )
        if not valid:
            raise RuntimeError(f"Generated image is not a PNG/JPEG/WEBP file: {path}")

    @staticmethod
    def _derive_audio_render_name(silent_name: str) -> str:
        base = (silent_name or "story_render.mp4").strip()
        if not base.lower().endswith(".mp4"):
            base += ".mp4"
        stem = Path(base).stem
        if "silent" in stem.lower():
            stem = re.sub(r"silent", "with_audio", stem, flags=re.I)
        else:
            stem = f"{stem}_with_audio"
        return f"{stem}.mp4"

    def _load_story_context(self, project_id: str) -> str:
        path = self.store.project_dir(project_id) / "rewrite_prompt.json"
        if not path.exists() or not path.is_file():
            return ""
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return ""
        return str(payload.get("story_context") or "").strip()

    @staticmethod
    def _read_wav_duration_seconds(path: Path) -> float:
        if not path.exists() or not path.is_file():
            return 0.0
        try:
            with wave.open(str(path), "rb") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                if rate <= 0:
                    return 0.0
                return float(frames) / float(rate)
        except Exception:
            return 0.0

    def _resolve_session_audio_duration_seconds(self, session_dir: Path) -> float:
        combined = session_dir / "audio" / "combined.wav"
        total = self._read_wav_duration_seconds(combined)
        if total > 0:
            return total
        legacy_combined = self.repo_root / "source_full" / "audio" / "combined.wav"
        total = self._read_wav_duration_seconds(legacy_combined)
        if total > 0:
            return total
        audio_dir = session_dir / "audio"
        if not audio_dir.exists() or not audio_dir.is_dir():
            legacy_audio_dir = self.repo_root / "source_full" / "audio"
            if not legacy_audio_dir.exists() or not legacy_audio_dir.is_dir():
                return 0.0
            wav_files = sorted(p for p in legacy_audio_dir.glob("*.wav") if p.is_file())
            total = 0.0
            for wav in wav_files:
                total += self._read_wav_duration_seconds(wav)
            return float(total)
        wav_files = sorted(p for p in audio_dir.glob("text_*.wav") if p.is_file())
        if not wav_files:
            wav_files = sorted(p for p in audio_dir.glob("*.wav") if p.is_file())
        total = 0.0
        for wav in wav_files:
            total += self._read_wav_duration_seconds(wav)
        return float(total)

    def _resolve_audio_for_merge(self, dirs: dict[str, Path]) -> Path:
        session_dir = dirs["session_dir"]
        combined = session_dir / "audio" / "combined.wav"
        if combined.exists() and combined.is_file():
            return combined
        legacy_combined = self.repo_root / "source_full" / "audio" / "combined.wav"
        if legacy_combined.exists() and legacy_combined.is_file():
            return legacy_combined
        audio_dir = session_dir / "audio"
        if not audio_dir.exists() or not audio_dir.is_dir():
            legacy_audio_dir = self.repo_root / "source_full" / "audio"
            if legacy_audio_dir.exists() and legacy_audio_dir.is_dir():
                audio_dir = legacy_audio_dir
            else:
                raise FileNotFoundError(f"Session audio folder not found: {audio_dir}")
        wav_files = sorted(p for p in audio_dir.glob("text_*.wav") if p.is_file())
        if not wav_files:
            wav_files = sorted(p for p in audio_dir.glob("*.wav") if p.is_file())
        if not wav_files:
            raise FileNotFoundError(
                f"No wav files found to merge audio. Checked: {session_dir / 'audio'} and {self.repo_root / 'source_full' / 'audio'}"
            )

        concat_list = dirs["renders_dir"] / "audio_concat.txt"
        lines = []
        for wav in wav_files:
            escaped = wav.as_posix().replace("'", "'\\''")
            lines.append(f"file '{escaped}'")
        concat_list.write_text("\n".join(lines) + "\n", encoding="utf-8")

        out_audio = dirs["renders_dir"] / "auto_combined.wav"
        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list),
            "-c:a",
            "pcm_s16le",
            str(out_audio),
        ]
        self._run_cmd(cmd, timeout=300)
        return out_audio

    def _resolve_video_for_merge(self, dirs: dict[str, Path], requested_name: str) -> Path:
        candidates: list[Path] = []
        name = (requested_name or "story_render.mp4").strip().replace("\\", "/").split("/")[-1]
        if name:
            candidates.append(dirs["renders_dir"] / name)
            candidates.append(dirs["video_root"] / name)

        render_manifest_path = dirs["manifests_dir"] / "render_manifest.json"
        if render_manifest_path.exists() and render_manifest_path.is_file():
            try:
                data = json.loads(render_manifest_path.read_text(encoding="utf-8"))
                rel_keys = ["render_path", "session_video_path"]
                for key in rel_keys:
                    rel = str(data.get(key) or "").strip()
                    if rel:
                        candidates.append(self.repo_root / rel)
            except Exception:
                pass

        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return candidate

        # Fallback to newest render mp4 if named target cannot be found.
        render_mp4 = sorted(
            (p for p in dirs["renders_dir"].glob("*.mp4") if p.is_file()),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if render_mp4:
            return render_mp4[0]

        raise FileNotFoundError(f"Video for merge not found. Requested: {requested_name}")

    def _render_placeholder_image(self, output_path: Path, width: int, height: int, scene_index: int) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        palette = ["#0f172a", "#1f2937", "#0b3d2e", "#3f1d2e", "#1e3a8a", "#3d2f12"]
        color = palette[(scene_index - 1) % len(palette)]
        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s={max(256, int(width))}x{max(256, int(height))}:d=1",
            "-vf",
            "drawgrid=w=80:h=80:t=2:c=white@0.20,drawbox=x=0:y=0:w=iw:h=ih:t=8:color=white@0.28",
            "-frames:v",
            "1",
            str(output_path),
        ]
        self._run_cmd(cmd, timeout=120)

    def _resolve_sd_executable(self, explicit: str | None = None) -> str | None:
        raw = (explicit or "").strip() or os.getenv("VIDEO_SD_EXECUTABLE", "").strip()
        if not raw:
            return None
        path = Path(raw)
        if path.exists() and path.is_file():
            return str(path)
        which_hit = shutil.which(raw)
        return which_hit if which_hit else None

    def _resolve_sd_model_path(self, explicit: str | None = None) -> str | None:
        raw = (explicit or "").strip() or os.getenv("VIDEO_SD_MODEL_PATH", "").strip()
        if not raw:
            return None
        path = Path(raw)
        if not path.exists() or not path.is_file():
            return None
        return str(path)

    def _run_sd_generate(
        self,
        executable: str,
        model_path: str,
        prompt: str,
        output_path: Path,
        width: int,
        height: int,
        steps: int,
        cfg_scale: float,
        seed: int,
    ) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            executable,
            "-m",
            model_path,
            "-p",
            prompt,
            "-o",
            str(output_path),
            "--width",
            str(max(256, int(width))),
            "--height",
            str(max(256, int(height))),
            "--steps",
            str(max(1, int(steps))),
            "--cfg-scale",
            str(max(1.0, float(cfg_scale))),
            "--seed",
            str(int(seed)),
        ]
        self._run_cmd(cmd, timeout=600)

    def _check_ffmpeg(self) -> bool:
        try:
            result = subprocess.run(
                [self.ffmpeg_bin, "-version"],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=12,
                check=False,
            )
        except Exception:
            return False
        return result.returncode == 0

    def _resolve_ffmpeg_bin(self) -> str:
        hit = shutil.which("ffmpeg")
        if hit:
            return hit
        for candidate in (
            self.repo_root / ".venv" / "Lib" / "site-packages" / "imageio_ffmpeg" / "binaries",
            self.repo_root.parent / "spam_audio_video" / ".venv" / "Lib" / "site-packages" / "imageio_ffmpeg" / "binaries",
        ):
            if candidate.exists():
                matches = sorted(candidate.glob("ffmpeg*.exe"))
                if matches:
                    return str(matches[0])
        try:
            import imageio_ffmpeg  # type: ignore

            bundled = imageio_ffmpeg.get_ffmpeg_exe()
            if bundled and Path(bundled).exists():
                return bundled
        except Exception:
            pass
        return "ffmpeg"

    def _list_ffmpeg_encoders(self) -> set[str]:
        if self._ffmpeg_encoders_cache is not None:
            return self._ffmpeg_encoders_cache
        encoders: set[str] = set()
        try:
            result = subprocess.run(
                [self.ffmpeg_bin, "-hide_banner", "-encoders"],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
                check=False,
            )
            text = f"{result.stdout or ''}\n{result.stderr or ''}"
            for line in text.splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("-") or stripped.startswith("Encoders"):
                    continue
                parts = stripped.split()
                if len(parts) >= 2 and len(parts[0]) >= 6:
                    name = parts[1].strip()
                    if name:
                        encoders.add(name)
        except Exception:
            encoders = set()
        self._ffmpeg_encoders_cache = encoders
        return encoders

    def _resolve_video_encoder(self, requested: str | None = None) -> str:
        raw = str(requested or "auto").strip().lower()
        aliases = {
            "cpu": "libx264",
            "x264": "libx264",
            "gpu": "auto",
            "nvenc": "h264_nvenc",
            "qsv": "h264_qsv",
            "amf": "h264_amf",
        }
        normalized = aliases.get(raw, raw)
        available = self._list_ffmpeg_encoders()
        if normalized in {"libx264", "h264_nvenc", "h264_qsv", "h264_amf"}:
            if normalized == "libx264":
                raise RuntimeError("CPU video encoder is disabled. Use a GPU H.264 encoder such as h264_nvenc.")
            if normalized in available and self._probe_video_encoder(normalized):
                return normalized
            raise RuntimeError(f"Requested GPU video encoder is not usable: {normalized}")
        if normalized in {"", "auto"}:
            for candidate in ("h264_nvenc", "h264_qsv", "h264_amf"):
                if candidate in available and self._probe_video_encoder(candidate):
                    return candidate
        raise RuntimeError(
            "GPU video encoder is required, but no supported FFmpeg hardware H.264 encoder is usable. "
            "Install/update NVIDIA driver/FFmpeg NVENC support or choose a working hardware encoder."
        )

    def _resolve_native_story_renderer_bin(self) -> Path:
        exe_name = "story_gpu_renderer.exe" if os.name == "nt" else "story_gpu_renderer"
        candidates: list[Path] = []
        env_path = str(os.getenv("SPAM_VIDEO_NATIVE_RENDERER_BIN") or "").strip()
        if env_path:
            candidates.append(Path(env_path))
        cargo_target_dir = str(os.getenv("CARGO_TARGET_DIR") or "").strip()
        if cargo_target_dir:
            candidates.append(Path(cargo_target_dir) / "release" / exe_name)
        candidates.extend([
            self.repo_root / "native_renderers" / "story_gpu_renderer" / "target" / "release" / exe_name,
            Path("D:/cargo-target/story_gpu_renderer/release") / exe_name,
            Path.home() / ".cargo" / "target" / "release" / exe_name,
        ])
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return candidate.resolve()
        checked = ", ".join(str(path) for path in candidates)
        raise FileNotFoundError(f"Native GPU renderer binary not found. Checked: {checked}")

    def _render_native_gpu_clip(
        self,
        *,
        renderer_bin: Path,
        input_path: Path,
        report_path: Path,
        image_path: Path,
        output_path: Path,
        project_id: str,
        session_id: str,
        width: int,
        height: int,
        fps: int,
        duration_seconds: float,
        audio_start_seconds: float,
        side_pad: int,
        panel_width: int,
        panel_height: int,
        motion_intensity: float,
        scroll_zoom: float,
        vertical_travel: float,
        logo_path: Path | None,
        audio_path: Path | None,
        visual_overlay: dict,
        config: VideoPipelineConfig,
    ) -> None:
        input_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": 1,
            "renderer": "native_gpu",
            "project_id": project_id,
            "session_id": session_id,
            "output_path": str(output_path),
            "audio_path": str(audio_path) if audio_path else "",
            "runtime": {
                "ffmpeg_bin": str(self.ffmpeg_bin),
            },
            "video": {
                "width": int(width),
                "height": int(height),
                "fps": int(fps),
                "duration_seconds": round(float(duration_seconds), 3),
                "audio_start_seconds": round(max(0.0, float(audio_start_seconds)), 3),
                "per_scene_duration_seconds": round(float(duration_seconds), 3),
                "encoder": str(config.video_encoder or "auto"),
                "preset": str(config.video_preset or "quality"),
                "cq": int(config.video_cq or 18),
            },
            "layout": {
                "side_pad": int(side_pad),
                "panel_width": int(panel_width),
                "panel_height": int(panel_height),
                "motion_intensity": float(motion_intensity),
                "scroll_zoom": float(scroll_zoom),
                "vertical_travel": float(vertical_travel),
            },
            "assets": {
                "images": [str(image_path)],
                "logo_path": str(logo_path) if logo_path else "",
            },
            "visual_overlay": {
                "enabled": bool(visual_overlay.get("enabled")),
                "particle_seed": int(visual_overlay.get("particle_seed") or 0),
                "dust_color": str(visual_overlay.get("dust_color") or "0xF7F7EE"),
                "spark_color": str(visual_overlay.get("spark_color") or "0xD8D0C0"),
                "dust_alpha": float(visual_overlay.get("dust_alpha") or 0.30),
                "audio_visualizer_enabled": bool(visual_overlay.get("audio_visualizer_enabled") and audio_path),
                "audio_visualizer_color": str(visual_overlay.get("audio_visualizer_color") or visual_overlay.get("spark_color") or "0xD8D0C0"),
            },
        }
        input_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        cmd = [
            str(renderer_bin),
            "render",
            "--config",
            str(input_path),
            "--report",
            str(report_path),
            "--output",
            str(output_path),
        ]
        self._run_cmd(cmd, timeout=max(240, int(duration_seconds * 12)))

    @staticmethod
    def _bridge_ports_from_values(cdp_url: str | None, cdp_urls: list[str] | None) -> list[int]:
        values: set[int] = set()
        urls: list[str] = []
        if cdp_url:
            urls.append(str(cdp_url))
        urls.extend(str(item) for item in (cdp_urls or []) if str(item or "").strip())
        for raw in urls:
            try:
                parsed = urlparse(raw if "://" in raw else f"http://127.0.0.1:{raw}")
                candidate = int(parsed.port or 0)
            except Exception:
                candidate = 0
            if 1 <= candidate <= 65535:
                values.add(candidate)
        return sorted(values)

    @classmethod
    def _bridge_ports_from_config(cls, config: VideoPipelineConfig) -> list[int]:
        return cls._bridge_ports_from_values(config.cdp_url, config.cdp_urls)

    @classmethod
    def _gemini_bridge_ports_from_config(cls, config: VideoPipelineConfig) -> list[int]:
        ports = cls._bridge_ports_from_values(config.gemini_cdp_url, config.gemini_cdp_urls)
        return ports or cls._bridge_ports_from_config(config)

    @classmethod
    def _gpt_bridge_ports_from_config(cls, config: VideoPipelineConfig) -> list[int]:
        ports = cls._bridge_ports_from_values(config.gpt_cdp_url, config.gpt_cdp_urls)
        return ports or cls._bridge_ports_from_config(config)

    @staticmethod
    def _warm_bridge_ports(client: BrowserBridgeClient, ports: list[int]) -> dict:
        if not ports:
            return {"ports": [], "skipped": True}
        data = client.ping_ports(ports)
        if data.get("success") is False:
            raise RuntimeError(f"Browser bridge port warmup failed for ports {ports}: {data}")
        return data

    def _probe_video_encoder(self, encoder: str) -> bool:
        if encoder == "libx264":
            return True
        if encoder in self._ffmpeg_encoder_probe_cache:
            return self._ffmpeg_encoder_probe_cache[encoder]
        probe_path = self.repo_root / "projects_workspace" / "runtime" / "video" / f"encoder_probe_{encoder}.mp4"
        probe_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=256x256:r=10",
            "-t",
            "0.2",
            "-an",
            "-c:v",
            encoder,
            "-pix_fmt",
            "yuv420p",
            str(probe_path),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            ok = result.returncode == 0 and probe_path.exists() and probe_path.stat().st_size > 0
        except Exception:
            ok = False
        finally:
            probe_path.unlink(missing_ok=True)
        self._ffmpeg_encoder_probe_cache[encoder] = ok
        return ok

    def _build_video_encode_args(
        self,
        encoder: str,
        gop: int,
        fps: int,
        config: VideoPipelineConfig,
    ) -> list[str]:
        preset_raw = str(config.video_preset or "quality").strip().lower()
        crf = max(0, min(51, int(config.video_crf or 18)))
        cq = max(0, min(51, int(config.video_cq or 18)))

        if encoder == "h264_nvenc":
            preset_map = {
                "throughput": "p1",
                "quality": "p6",
                "balanced": "p5",
                "fast": "p3",
            }
            preset = preset_map.get(preset_raw, preset_raw if preset_raw in {"p1", "p2", "p3", "p4", "p5", "p6", "p7"} else "p6")
            if preset_raw in {"throughput", "p1"}:
                return [
                    "-c:v",
                    "h264_nvenc",
                    "-preset",
                    "p1",
                    "-rc:v",
                    "constqp",
                    "-qp",
                    str(cq),
                    "-g",
                    str(gop),
                    "-pix_fmt",
                    "yuv420p",
                ]
            return [
                "-c:v",
                "h264_nvenc",
                "-preset",
                preset,
                "-rc:v",
                "vbr_hq",
                "-cq:v",
                str(cq),
                "-b:v",
                "0",
                "-g",
                str(gop),
                "-pix_fmt",
                "yuv420p",
            ]

        if encoder == "h264_qsv":
            preset_map = {"quality": "slow", "balanced": "medium", "fast": "fast"}
            preset = preset_map.get(preset_raw, "slow")
            return [
                "-c:v",
                "h264_qsv",
                "-preset",
                preset,
                "-global_quality",
                str(cq),
                "-g",
                str(gop),
                "-pix_fmt",
                "yuv420p",
            ]

        if encoder == "h264_amf":
            quality_map = {"quality": "quality", "balanced": "balanced", "fast": "speed"}
            quality = quality_map.get(preset_raw, "quality")
            return [
                "-c:v",
                "h264_amf",
                "-quality",
                quality,
                "-rc",
                "cqp",
                "-qp_i",
                str(cq),
                "-qp_p",
                str(cq),
                "-g",
                str(gop),
                "-pix_fmt",
                "yuv420p",
            ]

        # CPU reference path, quality baseline compatible with existing renders.
        preset_map = {
            "quality": "slow",
            "balanced": "medium",
            "fast": "faster",
        }
        preset = preset_map.get(
            preset_raw,
            preset_raw
            if preset_raw in {"ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"}
            else "slow",
        )
        return [
            "-c:v",
            "libx264",
            "-preset",
            preset,
            "-crf",
            str(crf),
            "-g",
            str(gop),
            "-keyint_min",
            str(fps),
            "-sc_threshold",
            "0",
            "-pix_fmt",
            "yuv420p",
        ]

    def _run_cmd(self, cmd: list[str], timeout: int = 120) -> None:
        result = subprocess.run(
            cmd,
            cwd=str(self.repo_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            stdout = (result.stdout or "").strip()
            raise RuntimeError(
                "Command failed with exit code "
                f"{result.returncode}: {' '.join(cmd)}\n"
                f"stdout: {stdout[:1200]}\n"
                f"stderr: {stderr[:1200]}"
            )

    def _is_readable_video_file(self, path: Path) -> bool:
        if not path.exists() or not path.is_file() or path.stat().st_size <= 0:
            return False
        cmd = [
            self.ffmpeg_bin,
            "-hide_banner",
            "-v",
            "error",
            "-i",
            str(path),
            "-map",
            "0:v:0",
            "-c",
            "copy",
            "-f",
            "null",
            os.devnull,
        ]
        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=45,
                check=False,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _video_file_matches_render_contract(
        self,
        path: Path,
        width: int,
        height: int,
        fps: int,
        duration_seconds: float,
    ) -> bool:
        if not self._is_readable_video_file(path):
            return False
        try:
            result = subprocess.run(
                [self.ffmpeg_bin, "-hide_banner", "-i", str(path)],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
                check=False,
            )
        except Exception:
            return False
        text = f"{result.stderr or ''}\n{result.stdout or ''}"
        if not text.strip():
            return False
        video_match = re.search(
            r"Video:\s*[^,\n]+.*?(\d{3,5})x(\d{3,5}).*?(\d+(?:\.\d+)?)\s*fps",
            text,
            flags=re.I | re.S,
        )
        if not video_match:
            return False
        found_width, found_height, found_fps = video_match.groups()
        if int(found_width) != int(width) or int(found_height) != int(height):
            return False
        if abs(float(found_fps) - float(fps)) > 0.5:
            return False
        duration_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
        if duration_match:
            hours, minutes, seconds = duration_match.groups()
            duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
            if abs(duration - float(duration_seconds)) > 0.25:
                return False
        return True

    def _rel(self, path: Path) -> str:
        return str(path.resolve().relative_to(self.repo_root)).replace("\\", "/")

    def _safe_rel(self, path: Path) -> str:
        resolved = path.resolve()
        try:
            return str(resolved.relative_to(self.repo_root)).replace("\\", "/")
        except ValueError:
            return str(resolved)
