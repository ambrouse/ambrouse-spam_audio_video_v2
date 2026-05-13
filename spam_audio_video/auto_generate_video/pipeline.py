from __future__ import annotations

import concurrent.futures
import json
import math
import os
import re
import shutil
import subprocess
import threading
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from auto_convert_text.pipeline.browser_bridge_client import DEFAULT_BRIDGE_BASE_URL, BrowserBridgeClient
from auto_convert_text.storage.project_store import ProjectStore


DEFAULT_VIDEO_GEMINI_PROMPT_TEMPLATE = (
    "B?n l? prompt engineer chuy?n vi?t prompt ?nh ?i?n ?nh manhua cho m? h?nh t?o ?nh.\n"
    "Y?u c?u b?t bu?c:\n"
    "1. Tr? v? CH? 1 d?ng prompt cu?i c?ng b?ng ti?ng Anh, kh?ng markdown, kh?ng gi?i th?ch.\n"
    "2. Kh?ng tr? v? ?nh, link, markdown image, data url, html, ho?c file attachment.\n"
    "3. Prompt ph?i ch? ??o r?: landscape 16:9, cinematic wide shot, ?u ti?n ?? n?t cao.\n"
    "4. N?u r? nh?n v?t ch?nh, b? c?c ti?n-trung-h?u c?nh, ?nh s?ng, camera angle, mood.\n"
    "4.1. Ch? m? t? xung ??t theo h??ng bi?u t??ng, kh?ng m? t? g?y s?c ho?c chi ti?t th??ng t?n c? th?.\n"
    "5. B? sung negative cues: no text, no watermark, no logo, blurry, low quality, oversaturated, deformed hands.\n"
    "5.1. Th?m safety cues: PG-13 fantasy tone, symbolic tension, elegant atmosphere, non-graphic storytelling.\n"
    "6. ?? d?i 70-140 t?, kh?ng l?p l?i t?nh ti?t th?, ch? gi? chi ti?t gi?u h?nh ?nh.\n\n"
    "B?i c?nh truy?n: {story_context}\n"
    "Di?n bi?n c?n minh h?a:\n"
    "{scene_text}\n"
)

@dataclass
class VideoPipelineConfig:
    scene_duration_seconds: float = 60.0
    width: int = 1280
    height: int = 720
    fps: int = 24
    motion_intensity: float = 0.06
    provider: str = "bridge_gemini"
    image_provider: str = "bridge_gpt"
    cdp_url: str | None = None
    cdp_urls: list[str] | None = None
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
    video_encoder: str = "auto"
    video_preset: str = "quality"
    video_crf: int = 18
    video_cq: int = 18
    render_workers: int = 1


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
        scene_duration_seconds: float = 60.0,
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
        safe_scene_duration = max(5.0, float(scene_duration_seconds or 60.0))
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

        prompt_items = [item for item in prompt_items if isinstance(item, dict)]

        prompt_manifest = {
            "project_id": project_id,
            "session_id": session_id,
            "provider": provider_name,
            "bridge_base_url": bridge_client.base_url if provider_name == "bridge_gemini" else "",
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
        for index, prompt_path in enumerate(prompts, start=1):
            if should_stop and should_stop():
                raise RuntimeError("STOP_REQUESTED")
            prompt = self._sanitize_policy_safe_prompt(prompt_path.read_text(encoding="utf-8", errors="replace").strip())
            payload, bridge_items = client.image("gpt", [prompt], max_images=1, timeout_s=config.bridge_timeout_s)
            item = bridge_items[0] if bridge_items else None
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
                "byte_size": image_path.stat().st_size,
            }
            items.append(row)
            if progress_callback:
                progress_callback({
                    "stage": "video_images",
                    "current": index,
                    "total": total,
                    "message": f"Generated image {index}/{total} via GPT bridge",
                    "files_done": index,
                    "preview_text": image_path.name,
                })

        image_manifest = {
            "project_id": project_id,
            "session_id": session_id,
            "engine": "bridge_gpt",
            "bridge_base_url": client.base_url,
            "scene_count": len(items),
            "max_images": max(1, min(120, int(config.gpt_image_limit or 10))),
            "skipped": skipped,
            "items": items,
        }
        target = dirs["manifests_dir"] / "images_manifest.json"
        target.write_text(json.dumps(image_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return image_manifest

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
            (r"\bm?u me\b", "n?ng l??ng ??"),
            (r"\bm?u\b", "n?ng l??ng ??"),
            (r"\b(?:gi?t|ch?m|??m|t?n s?t|th?m s?t|tra t?n)\b", "??i ??u"),
            (r"\b(?:ch?t|x?c|t? thi)\b", "h? qu?"),
            (r"\b(?:?au ??n|?au nh?i|qu?n qu?i|x? to?c|x? r?ch)\b", "c?ng th?ng"),
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
        output_name: str = "story_silent.mp4",
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

        image_files = self._collect_scene_images(dirs["images_dir"])
        if not image_files:
            raise FileNotFoundError("No scene images found. Run image generation first.")
        if not self._check_ffmpeg():
            raise RuntimeError("ffmpeg is required for video render.")

        clips_dir = dirs["renders_dir"] / "clips"
        clips_dir.mkdir(parents=True, exist_ok=True)
        total = len(image_files)
        per_scene_duration = max(3.0, float(analysis.get("scene_duration_seconds") or config.scene_duration_seconds or 60.0))
        # Keep a higher floor for better visual smoothness when users watch at 2x speed.
        fps = max(30, min(60, int(config.fps)))
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
        speed_factor = 1.74
        base_zoom_delta = (0.028 + motion * 0.07) * speed_factor
        transition_seconds = min(1.2, max(0.45, per_scene_duration * 0.10))
        frames = max(1, int(math.ceil(per_scene_duration * fps)))
        gop = max(30, fps * 2)
        requested_encoder = str(config.video_encoder or "auto").strip().lower() or "auto"
        selected_encoder = self._resolve_video_encoder(config.video_encoder)
        max_workers = max(1, min(8, int(config.render_workers or 1)))
        if selected_encoder != "libx264":
            # Most consumer GPUs throttle concurrent encode sessions.
            max_workers = min(max_workers, 3)

        def _clamp(value: float, low: float, high: float) -> float:
            return max(low, min(high, value))

        # Keep the camera path continuous across scene cuts to avoid "reset" feeling.
        travel = min(0.34, (0.07 + motion * 0.52) * speed_factor)
        lane_vectors: list[tuple[float, float]] = [
            (0.85, -0.12),
            (-0.78, 0.14),
            (0.64, -0.54),
            (-0.56, 0.48),
        ]
        prev_end_x = 0.44
        prev_end_y = 0.52
        prev_end_z = min(1.24, max(1.04, base_zoom_start + 0.02))

        clip_plan: list[dict] = []
        for index, image_path in enumerate(image_files, start=1):
            if should_stop and should_stop():
                raise RuntimeError("STOP_REQUESTED")
            clip_path = clips_dir / f"clip_{index:04d}.mp4"

            # Scene i starts where scene i-1 ended, then keeps moving along the next lane vector.
            lane = (index - 1) % len(lane_vectors)
            vx, vy = lane_vectors[lane]
            start_x = prev_end_x
            start_y = prev_end_y
            end_x = _clamp(start_x + vx * travel, 0.08, 0.86)
            end_y = _clamp(start_y + vy * travel, 0.10, 0.82)

            z0 = _clamp(prev_end_z, 1.03, 1.28)
            z_step = base_zoom_delta * (0.92 if lane in {0, 2} else 0.58)
            z1 = _clamp(z0 + z_step, 1.06, 1.32)
            dur = max(1.0, per_scene_duration)
            u_expr = f"clip(t/{dur:.4f},0,1)"
            # Quintic smoothstep: smoother velocity/acceleration than cubic.
            ease_expr = f"(({u_expr})*({u_expr})*({u_expr})*(({u_expr})*(({u_expr})*6-15)+10))"

            vf = (
                # 1) For small source images, upscale and recover edge contrast before camera moves.
                f"scale='if(lt(iw,{int(width * 0.9)}),min(iw*2,{int(width * 1.45)}),iw)':"
                f"'if(lt(ih,{int(height * 0.9)}),min(ih*2,{int(height * 1.45)}),ih)':"
                f"flags=lanczos+accurate_rnd+full_chroma_int,"
                f"hqdn3d=0.9:0.9:4.5:4.5,"
                f"unsharp=5:5:0.38:5:5:0.0,"
                f"scale={int(cam_width * overscan)}:{int(cam_height * overscan)}:force_original_aspect_ratio=increase,"
                f"crop={cam_width}:{cam_height},"
                f"scale=w='iw*({z0:.5f}+({z1:.5f}-{z0:.5f})*{ease_expr})':"
                f"h='ih*({z0:.5f}+({z1:.5f}-{z0:.5f})*{ease_expr})':"
                f"eval=frame,"
                f"crop={cam_width}:{cam_height}:"
                f"x='(in_w-out_w)*({start_x:.4f}+({end_x - start_x:.4f})*{ease_expr})':"
                f"y='(in_h-out_h)*({start_y:.4f}+({end_y - start_y:.4f})*{ease_expr})',"
                f"scale={width}:{height}:flags=lanczos+accurate_rnd+full_chroma_int,"
                f"fps={fps},format=yuv420p"
            )

            prev_end_x = end_x
            prev_end_y = end_y
            prev_end_z = z1
            clip_plan.append({
                "index": index,
                "image_path": image_path,
                "clip_path": clip_path,
                "vf": vf,
            })

        clip_paths: list[Path] = []
        done_count = 0
        done_lock = threading.Lock()

        def _render_one_clip(plan: dict) -> tuple[int, Path, str]:
            if should_stop and should_stop():
                raise RuntimeError("STOP_REQUESTED")
            idx = int(plan["index"])
            src_path = Path(plan["image_path"])
            out_path = Path(plan["clip_path"])
            cmd = [
                self.ffmpeg_bin,
                "-y",
                "-loop",
                "1",
                "-i",
                str(src_path),
                "-vf",
                str(plan["vf"]),
                "-t",
                str(per_scene_duration),
                "-an",
                *self._build_video_encode_args(selected_encoder, gop, fps, config),
                "-movflags",
                "+faststart",
                str(out_path),
            ]
            self._run_cmd(cmd, timeout=360)
            return idx, out_path, src_path.name

        if max_workers <= 1:
            for plan in clip_plan:
                idx, out_path, preview_name = _render_one_clip(plan)
                clip_paths.append(out_path)
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
        else:
            rendered: dict[int, Path] = {}
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(_render_one_clip, plan) for plan in clip_plan]
                for future in concurrent.futures.as_completed(futures):
                    idx, out_path, preview_name = future.result()
                    rendered[idx] = out_path
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

        safe_name = (output_name or "story_silent.mp4").strip().replace("\\", "/").split("/")[-1]
        if not safe_name.lower().endswith(".mp4"):
            safe_name += ".mp4"
        silent_path = dirs["renders_dir"] / safe_name
        session_video_copy = dirs["video_root"] / safe_name
        if len(clip_paths) <= 1:
            single_cmd = [
                self.ffmpeg_bin,
                "-y",
                "-i",
                str(clip_paths[0]),
                *self._build_video_encode_args(selected_encoder, gop, fps, config),
                "-movflags",
                "+faststart",
                str(silent_path),
            ]
            self._run_cmd(single_cmd, timeout=480)
        else:
            xfade_cmd = [self.ffmpeg_bin, "-y"]
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
            self._run_cmd(xfade_cmd, timeout=480)
        if session_video_copy != silent_path:
            shutil.copy2(silent_path, session_video_copy)

        render_with_audio_path: str = ""
        session_video_audio_path: str = ""
        if render_with_audio:
            if should_stop and should_stop():
                raise RuntimeError("STOP_REQUESTED")
            audio_path = self._resolve_audio_for_merge(dirs)
            audio_name = self._derive_audio_render_name(safe_name)
            rendered_with_audio = dirs["renders_dir"] / audio_name
            session_audio_copy = dirs["video_root"] / audio_name
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
                "-shortest",
                "-movflags",
                "+faststart",
                str(rendered_with_audio),
            ]
            self._run_cmd(audio_cmd, timeout=300)
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
            "fps": fps,
            "width": width,
            "height": height,
            "motion_intensity": motion,
            "transition_seconds": transition_seconds,
            "requested_video_encoder": requested_encoder,
            "video_encoder": selected_encoder,
            "gpu_fallback_used": selected_encoder == "libx264",
            "fallback_reason": (
                "No supported FFmpeg GPU H.264 encoder was available."
                if selected_encoder == "libx264" and requested_encoder in {"auto", "gpu", "nvenc", "qsv", "amf", "h264_nvenc", "h264_qsv", "h264_amf"}
                else ""
            ),
            "render_workers": max_workers,
        }
        (dirs["manifests_dir"] / "render_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return manifest

    def merge_audio(
        self,
        project_id: str,
        session_id: str,
        silent_video_name: str = "story_silent.mp4",
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
        base = (silent_name or "story_silent.mp4").strip()
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
        name = (requested_name or "story_silent.mp4").strip().replace("\\", "/").split("/")[-1]
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

    @staticmethod
    def _resolve_ffmpeg_bin() -> str:
        hit = shutil.which("ffmpeg")
        if hit:
            return hit
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
                return normalized
            return normalized if normalized in available and self._probe_video_encoder(normalized) else "libx264"
        if normalized in {"", "auto"}:
            for candidate in ("h264_nvenc", "h264_qsv", "h264_amf"):
                if candidate in available and self._probe_video_encoder(candidate):
                    return candidate
        return "libx264"

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
            "color=c=black:s=64x64:r=10",
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
                "quality": "p6",
                "balanced": "p5",
                "fast": "p3",
            }
            preset = preset_map.get(preset_raw, preset_raw if preset_raw in {"p1", "p2", "p3", "p4", "p5", "p6", "p7"} else "p6")
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

    def _rel(self, path: Path) -> str:
        return str(path.resolve().relative_to(self.repo_root)).replace("\\", "/")
