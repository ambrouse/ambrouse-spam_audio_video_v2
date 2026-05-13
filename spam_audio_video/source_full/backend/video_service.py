from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Callable

from auto_convert_text.storage.project_store import slugify
from auto_convert_text.pipeline.browser_bridge_client import DEFAULT_BRIDGE_BASE_URL
from auto_convert_text.storage.shared_project_registry import SharedProjectRegistry
from auto_generate_video import DEFAULT_VIDEO_GEMINI_PROMPT_TEMPLATE, VideoPipeline, VideoPipelineConfig


DEFAULT_VIDEO_STORY_CONTEXT = (
    "Manhua cinematic, khung hình ngang 16:9, không chữ trên hình, nhân vật nhất quán, bố cục rõ ràng, "
    "ưu tiên ảnh sắc nét, ánh sáng điện ảnh và không watermark."
)


class VideoPipelineService:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        self.pipeline = VideoPipeline(self.repo_root)
        self.registry = SharedProjectRegistry(self.repo_root)
        self.video_prompt_default_dir = self.repo_root / "projects_workspace" / "prompt_default"
        self.video_prompt_default_path = self.video_prompt_default_dir / "video_prompt.json"

    @staticmethod
    def _build_config(payload: dict) -> VideoPipelineConfig:
        provider = str(payload.get("provider") or "bridge_gemini").strip().lower()
        if provider in {"", "gemini_web", "openai", "openai_compat"}:
            provider = "bridge_gemini"
        image_provider = str(payload.get("image_provider") or payload.get("provider") or "bridge_gpt").strip().lower()
        if image_provider in {"gpt_web", "gpt"}:
            image_provider = "bridge_gpt"
        cfg = VideoPipelineConfig(
            scene_duration_seconds=float(payload.get("scene_duration_seconds") or 60.0),
            width=int(payload.get("width") or 1280),
            height=int(payload.get("height") or 720),
            fps=int(payload.get("fps") or 24),
            motion_intensity=float(payload.get("motion_intensity") or 0.06),
            provider=provider,
            image_provider=image_provider,
            cdp_url=payload.get("cdp_url"),
            cdp_urls=payload.get("cdp_urls"),
            prompt_parallel_workers=int(payload.get("prompt_parallel_workers") or 1),
            prompt_delay_seconds=float(payload.get("prompt_delay_seconds") or 0.6),
            sd_model_path=payload.get("sd_model_path"),
            sd_executable=payload.get("sd_executable"),
            sd_steps=int(payload.get("sd_steps") or 24),
            sd_cfg_scale=float(payload.get("sd_cfg_scale") or 7.0),
            seed=int(payload.get("seed") or 42),
            gpt_image_limit=int(payload.get("gpt_image_limit") or 10),
            prompt_tts_input_limit=int(payload.get("prompt_tts_input_limit") or 40),
            gemini_prompt_strict=bool(payload.get("gemini_prompt_strict", False)),
            llm_base_url=str(payload.get("llm_base_url") or ""),
            llm_model=str(payload.get("llm_model") or "gemini/gemini-3-flash-preview"),
            llm_api_key=payload.get("llm_api_key"),
            bridge_base_url=str(payload.get("bridge_base_url") or DEFAULT_BRIDGE_BASE_URL),
            bridge_timeout_s=float(payload.get("bridge_timeout_s") or 600.0),
            story_context=str(payload.get("story_context") or ""),
            gemini_prompt_template=str(payload.get("gemini_prompt_template") or DEFAULT_VIDEO_GEMINI_PROMPT_TEMPLATE),
            video_encoder=str(payload.get("video_encoder") or "auto"),
            video_preset=str(payload.get("video_preset") or "quality"),
            video_crf=int(payload.get("video_crf") or 18),
            video_cq=int(payload.get("video_cq") or 18),
            render_workers=int(payload.get("render_workers") or 1),
        )
        image_provider = str(cfg.image_provider or "").strip().lower()
        if image_provider in {"gpt_web", "gpt"}:
            # Keep GPT image workflow in cinematic landscape output.
            ratio = (float(cfg.width) / float(cfg.height)) if int(cfg.height or 0) > 0 else 0.0
            if cfg.width < cfg.height or ratio < 1.70 or ratio > 1.95:
                cfg.width = 3840
                cfg.height = 2160
        return cfg

    def _ensure_video_prompt_default_seed(self) -> None:
        self.video_prompt_default_dir.mkdir(parents=True, exist_ok=True)
        if not self.video_prompt_default_path.exists():
            self.video_prompt_default_path.write_text(
                json.dumps(
                    {
                        "story_context": DEFAULT_VIDEO_STORY_CONTEXT,
                        "gemini_prompt_template": DEFAULT_VIDEO_GEMINI_PROMPT_TEMPLATE,
                        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

    def get_video_prompt_default(self) -> dict:
        self._ensure_video_prompt_default_seed()
        try:
            payload = json.loads(self.video_prompt_default_path.read_text(encoding="utf-8"))
        except Exception:
            payload = {"story_context": DEFAULT_VIDEO_STORY_CONTEXT, "gemini_prompt_template": DEFAULT_VIDEO_GEMINI_PROMPT_TEMPLATE}
        return {
            "success": True,
            "story_context": str(payload.get("story_context") or DEFAULT_VIDEO_STORY_CONTEXT),
            "gemini_prompt_template": str(payload.get("gemini_prompt_template") or DEFAULT_VIDEO_GEMINI_PROMPT_TEMPLATE),
        }

    def save_video_prompt_default(self, story_context: str, gemini_prompt_template: str) -> dict:
        self._ensure_video_prompt_default_seed()
        payload = {
            "story_context": (story_context or "").strip() or DEFAULT_VIDEO_STORY_CONTEXT,
            "gemini_prompt_template": (gemini_prompt_template or "").strip() or DEFAULT_VIDEO_GEMINI_PROMPT_TEMPLATE,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        self.video_prompt_default_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"success": True, **payload}

    def clear_video_prompt_default(self) -> dict:
        removed = 0
        if self.video_prompt_default_path.exists() and self.video_prompt_default_path.is_file():
            self.video_prompt_default_path.unlink(missing_ok=True)
            removed += 1
        self._ensure_video_prompt_default_seed()
        return {"success": True, "removed": removed}

    def get_session_video_prompt(self, project_id: str, session_id: str | None = None) -> dict:
        clean_project_id = slugify(project_id)
        clean_session_id = slugify(session_id) if session_id else None
        data = self.pipeline.store.read_video_prompt_config(clean_project_id, session_id=clean_session_id)
        return {
            "success": True,
            "project_id": clean_project_id,
            "session_id": clean_session_id,
            "story_context": data.get("story_context", ""),
            "gemini_prompt_template": data.get("gemini_prompt_template", ""),
            "source": data.get("source", "none"),
        }

    def save_session_video_prompt(
        self,
        project_id: str,
        session_id: str,
        story_context: str,
        gemini_prompt_template: str,
    ) -> dict:
        clean_project_id = slugify(project_id)
        clean_session_id = slugify(session_id)
        data = self.pipeline.store.write_video_prompt_config(
            clean_project_id,
            clean_session_id,
            story_context=story_context,
            gemini_prompt_template=gemini_prompt_template,
        )
        return {
            "success": True,
            "project_id": clean_project_id,
            "session_id": clean_session_id,
            "story_context": data.get("story_context", ""),
            "gemini_prompt_template": data.get("gemini_prompt_template", ""),
        }

    def clear_session_video_prompt(self, project_id: str, session_id: str | None = None) -> dict:
        clean_project_id = slugify(project_id)
        clean_session_id = slugify(session_id) if session_id else None
        removed = self.pipeline.store.clear_video_prompt_config(clean_project_id, session_id=clean_session_id)
        return {
            "success": True,
            "project_id": clean_project_id,
            "session_id": clean_session_id,
            "removed": int(removed.get("removed", 0)),
        }

    def _resolve_video_prompt_inputs(self, project_id: str, session_id: str, payload: dict | None = None) -> tuple[str, str, str]:
        payload_data = payload or {}
        payload_context = str(payload_data.get("story_context") or "").strip()
        payload_template = str(payload_data.get("gemini_prompt_template") or "").strip()
        clean_project_id = slugify(project_id)
        clean_session_id = slugify(session_id)
        persisted = self.pipeline.store.read_video_prompt_config(clean_project_id, session_id=clean_session_id)
        persisted_template = str(persisted.get("gemini_prompt_template") or "").strip()
        persisted_context = str(persisted.get("story_context") or "").strip()
        defaults = self.get_video_prompt_default()
        default_context = str(defaults.get("story_context") or "").strip()
        default_template = str(defaults.get("gemini_prompt_template") or DEFAULT_VIDEO_GEMINI_PROMPT_TEMPLATE).strip()

        resolved_template = payload_template or persisted_template or default_template
        resolved_context = payload_context or persisted_context or default_context

        if payload_context or payload_template:
            source = "payload"
        elif persisted_context or persisted_template:
            source = "session"
        else:
            source = "default"
        return resolved_context, resolved_template, source

    def prewarm(self, sd_executable: str | None = None, sd_model_path: str | None = None) -> dict:
        return self.pipeline.prewarm(sd_executable=sd_executable, sd_model_path=sd_model_path)

    def analyze(self, project_id: str, session_id: str, scene_duration_seconds: float = 60.0) -> dict:
        return self.pipeline.analyze_session(project_id, session_id, scene_duration_seconds)

    def run_prompts(
        self,
        project_id: str,
        session_id: str,
        payload: dict,
        progress_callback: Callable[[dict], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> dict:
        cfg = self._build_config(payload)
        resolved_context, resolved_template, prompt_source = self._resolve_video_prompt_inputs(project_id, session_id, payload=payload)
        cfg.story_context = resolved_context
        cfg.gemini_prompt_template = resolved_template
        result = self.pipeline.generate_prompts(
            project_id=project_id,
            session_id=session_id,
            config=cfg,
            progress_callback=progress_callback,
            should_stop=should_stop,
        )
        result["prompt_source"] = prompt_source
        self.registry.upsert_session(
            project_id,
            session_id,
            {
                "status": "video_prompts_ready",
                "video": {
                    "config": asdict(cfg),
                    "prompt_scene_count": int(result.get("scene_count") or 0),
                },
            },
        )
        return result

    def run_images(
        self,
        project_id: str,
        session_id: str,
        payload: dict,
        progress_callback: Callable[[dict], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> dict:
        cfg = self._build_config(payload)
        result = self.pipeline.generate_images(
            project_id=project_id,
            session_id=session_id,
            config=cfg,
            progress_callback=progress_callback,
            should_stop=should_stop,
        )
        self.registry.upsert_session(
            project_id,
            session_id,
            {
                "status": "video_images_ready",
                "video": {
                    "config": asdict(cfg),
                    "image_scene_count": int(result.get("scene_count") or 0),
                },
            },
        )
        return result

    def render(
        self,
        project_id: str,
        session_id: str,
        payload: dict,
        progress_callback: Callable[[dict], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> dict:
        cfg = self._build_config(payload)
        output_name = str(payload.get("output_name") or "story_silent.mp4")
        result = self.pipeline.render_video(
            project_id=project_id,
            session_id=session_id,
            config=cfg,
            output_name=output_name,
            render_with_audio=bool(payload.get("render_with_audio", True)),
            progress_callback=progress_callback,
            should_stop=should_stop,
        )
        self.registry.upsert_session(
            project_id,
            session_id,
            {
                "status": "video_render_ready",
                "video": {
                    "config": asdict(cfg),
                    "render_path": result.get("render_path"),
                },
            },
        )
        return result

    def merge(self, project_id: str, session_id: str, silent_video_name: str = "story_silent.mp4", output_name: str = "final_story.mp4") -> dict:
        result = self.pipeline.merge_audio(
            project_id=project_id,
            session_id=session_id,
            silent_video_name=silent_video_name,
            output_name=output_name,
        )
        self.registry.upsert_session(
            project_id,
            session_id,
            {
                "status": "video_ready",
                "video": {
                    "final_video_path": result.get("final_video_path"),
                    "silent_video_path": result.get("silent_video_path"),
                },
            },
        )
        return result

    def run_full(
        self,
        project_id: str,
        session_id: str,
        payload: dict,
        progress_callback: Callable[[dict], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> dict:
        cfg = self._build_config(payload)
        result = self.pipeline.run_full(
            project_id=project_id,
            session_id=session_id,
            config=cfg,
            merge_audio=bool(payload.get("merge_audio", True)),
            progress_callback=progress_callback,
            should_stop=should_stop,
        )
        self.registry.upsert_session(
            project_id,
            session_id,
            {
                "status": "video_ready",
                "video": {
                    "config": asdict(cfg),
                    "render_path": (result.get("render") or {}).get("render_path"),
                    "final_video_path": ((result.get("merge") or {}).get("final_video_path") if result.get("merge") else ""),
                },
            },
        )
        return result
