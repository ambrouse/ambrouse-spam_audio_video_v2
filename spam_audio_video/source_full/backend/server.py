from __future__ import annotations

import json
import os
import sys
import threading
import uuid
from pathlib import Path
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Query
from fastapi import Request
from fastapi import Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = BASE_DIR / "frontend"
REPO_ROOT = BASE_DIR.parents[0]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from auto_convert_text.pipeline.browser_bridge_client import DEFAULT_BRIDGE_BASE_URL, BrowserBridgeClient
    from .convert_service import ConvertPipelineService
    from .gpu_service import GpuStatusService
    from .pipeline_service import AudioPipelineService
    from .progress_store import ProgressStore
    from .video_service import VideoPipelineService
except ImportError:
    from auto_convert_text.pipeline.browser_bridge_client import DEFAULT_BRIDGE_BASE_URL, BrowserBridgeClient
    from convert_service import ConvertPipelineService
    from gpu_service import GpuStatusService
    from pipeline_service import AudioPipelineService
    from progress_store import ProgressStore
    from video_service import VideoPipelineService


app = FastAPI(title="Pipeline Controller", version="1.1.0")
service = AudioPipelineService(REPO_ROOT)
video_service = VideoPipelineService(REPO_ROOT)
convert_service = ConvertPipelineService(REPO_ROOT)
gpu_service = GpuStatusService(REPO_ROOT, service, video_service)
progress_store = ProgressStore()
pipeline_lock = threading.Lock()
convert_lock = threading.Lock()


@app.middleware("http")
async def disable_api_cache(request: Request, call_next):
    response: Response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/api/") or request.url.path.startswith("/assets/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


class PipelineRunResponse(BaseModel):
    success: bool
    message: str
    manifest: dict | None = None
    stdout: str = ""
    stderr: str = ""


class PipelineRunRequest(BaseModel):
    job_id: str | None = None
    project_id: str | None = None
    session_id: str | None = None
    voice_profile: str | None = None
    model_key: str | None = None
    temperature: float = 0.05
    top_k: int = 80
    max_chars: int = 420
    tts_io_workers: int = 2
    inference_timesteps: int = 8
    postprocess: bool = False
    noise_reduction: float = 0.12
    highpass_hz: float = 70.0
    lowpass_hz: float = 10500.0
    target_peak_db: float = -1.5
    comp_threshold_db: float = -22.0
    comp_ratio: float = 1.4
    make_up_gain_db: float = 0.0
    presence_boost_db: float = 0.4
    de_ess: float = 0.30
    gate_strength: float = 0.20
    anti_leak_trim: bool = True
    anti_leak_max_ms: int = 900


class ConvertCollectRequest(BaseModel):
    job_id: str | None = None
    story_url: str
    start_chapter: int = 1
    chapter_count: int = 10
    project_name: str | None = None
    project_id: str | None = None
    chapter_token: str | None = None
    chapter_urls: list[str] | None = None
    apply_chapter_window: bool = False
    session_id: str | None = None


class ConvertCrawlRequest(BaseModel):
    story_url: str
    start_chapter: int = 1
    chapter_count: int = 10
    chapter_token: str | None = None


class ConvertCrawlBrowserRequest(BaseModel):
    job_id: str | None = None
    story_url: str
    cdp_url: str = "http://127.0.0.1:9222"
    max_scroll_rounds: int = 120


class ProjectChapterUrlsRequest(BaseModel):
    project_id: str
    urls: list[str] | None = None
    session_id: str | None = None


class ProjectChapterItemRequest(BaseModel):
    project_id: str
    index: int
    url: str | None = None
    session_id: str | None = None


class ProjectRewritePromptRequest(BaseModel):
    project_id: str
    session_id: str | None = None
    story_context: str = ""
    rewrite_prompt: str = ""


class VideoPromptConfigRequest(BaseModel):
    project_id: str
    session_id: str | None = None
    story_context: str = ""
    gemini_prompt_template: str = ""


class VideoPromptDefaultRequest(BaseModel):
    story_context: str = ""
    gemini_prompt_template: str = ""


class PromptDefaultRequest(BaseModel):
    story_context: str = ""
    rewrite_prompt: str = ""
    story_context_template: str | None = None


class LlmDefaultRequest(BaseModel):
    llm_base_url: str = ""
    llm_model: str = "gemini/gemini-3-flash-preview"
    llm_api_key: str | None = None


class LlmChatTestRequest(BaseModel):
    message: str
    llm_base_url: str = ""
    llm_model: str = "gemini/gemini-3-flash-preview"
    llm_api_key: str | None = None
    max_tokens: int = 128
    temperature: float = 0.2


class ConvertRewriteRequest(BaseModel):
    job_id: str | None = None
    provider: str = "bridge_gemini"
    rewrite_model: str = "fast"
    story_context: str = ""
    rewrite_prompt: str | None = None
    llm_base_url: str = ""
    llm_model: str = "gemini/gemini-3-flash-preview"
    llm_api_key: str | None = None
    cdp_url: str | None = None
    cdp_urls: list[str] | None = None
    bridge_base_url: str = DEFAULT_BRIDGE_BASE_URL
    bridge_timeout_s: float = 600.0
    parallel_workers: int = 2
    resume_only: bool = False
    session_id: str | None = None


class ConvertChunkRequest(BaseModel):
    job_id: str | None = None
    min_words: int = 16
    max_words: int = 64
    session_id: str | None = None


class ConvertExportRequest(BaseModel):
    clear_old: bool = False
    session_id: str | None = None


class ConvertFullRunRequest(ConvertCollectRequest):
    provider: str = "bridge_gemini"
    rewrite_model: str = "fast"
    story_context: str = ""
    rewrite_prompt: str | None = None
    llm_base_url: str = ""
    llm_model: str = "gemini/gemini-3-flash-preview"
    llm_api_key: str | None = None
    cdp_url: str | None = None
    cdp_urls: list[str] | None = None
    bridge_base_url: str = DEFAULT_BRIDGE_BASE_URL
    bridge_timeout_s: float = 600.0
    parallel_workers: int = 2
    clear_old_tts_text: bool = True
    target_chars: int = 600
    max_chars: int = 1100
    min_chars: int = 200
    auto_open_gemini_browser: bool = False
    job_id: str | None = None


class GeminiChromeRequest(BaseModel):
    port: int = 9222
    user_data_dir: str = r"D:\chrome-gemini-profile"
    url: str = "https://gemini.google.com"


class GeminiChromePoolRequest(BaseModel):
    ports: list[int]
    user_data_root: str = r"D:\chrome-gemini-profile-pool"
    url: str = "https://gemini.google.com"


class GeminiChromePoolLoginRequest(BaseModel):
    ports: list[int]
    login_ready: bool = True


class JobStopRequest(BaseModel):
    reason: str = "Stopped by user."


class RunAllRequest(ConvertFullRunRequest):
    voice_profile: str | None = None
    model_key: str | None = None
    temperature: float = 0.05
    top_k: int = 80
    max_chars_tts: int = 420
    tts_io_workers: int = 2
    inference_timesteps: int = 8
    resume_from_checkpoint: bool = False
    video_enabled: bool = True
    video_scene_duration_seconds: float = 60.0
    video_provider: str = "bridge_gemini"
    video_image_provider: str = "bridge_gpt"
    video_gpt_cdp_url: str | None = None
    video_gpt_cdp_urls: list[str] | None = None
    video_prompt_workers: int = 9
    video_prompt_delay_seconds: float = 0.6
    video_width: int = 3840
    video_height: int = 2160
    video_fps: int = 60
    video_motion_intensity: float = 0.012
    video_gpt_image_limit: int = 10
    video_prompt_tts_input_limit: int = 40
    video_story_context: str = ""
    video_gemini_prompt_template: str = ""
    video_render_with_audio: bool = True
    video_merge_audio: bool = True
    video_output_name: str = "story_render.mp4"
    video_encoder: str = "auto"
    video_preset: str = "quality"
    video_crf: int = 18
    video_cq: int = 18
    video_render_workers: int = 4


class VideoPipelineRequest(BaseModel):
    job_id: str | None = None
    project_id: str
    session_id: str
    scene_duration_seconds: float = 60.0
    provider: str = "bridge_gemini"
    image_provider: str = "bridge_gpt"
    cdp_url: str | None = None
    cdp_urls: list[str] | None = None
    prompt_parallel_workers: int = 1
    prompt_delay_seconds: float = 0.6
    width: int = 1280
    height: int = 720
    fps: int = 24
    motion_intensity: float = 0.06
    sd_executable: str | None = None
    sd_model_path: str | None = None
    sd_steps: int = 24
    sd_cfg_scale: float = 7.0
    seed: int = 42
    gpt_image_limit: int = 10
    prompt_tts_input_limit: int = 40
    llm_base_url: str = ""
    llm_model: str = "gemini/gemini-3-flash-preview"
    llm_api_key: str | None = None
    bridge_base_url: str = DEFAULT_BRIDGE_BASE_URL
    bridge_timeout_s: float = 600.0
    story_context: str = ""
    gemini_prompt_template: str = ""
    video_encoder: str = "auto"
    video_preset: str = "quality"
    video_crf: int = 18
    video_cq: int = 18
    render_workers: int = 4
    render_with_audio: bool = True
    merge_audio: bool = True
    output_name: str = "story_render.mp4"


class BridgeOpenRequest(BaseModel):
    bridge_base_url: str = DEFAULT_BRIDGE_BASE_URL
    ports: list[int]
    force_reconnect: bool = False


class BridgeStatusRequest(BaseModel):
    bridge_base_url: str = DEFAULT_BRIDGE_BASE_URL
    ports: list[int] | None = None


class BridgeChatTestRequest(BaseModel):
    bridge_base_url: str = DEFAULT_BRIDGE_BASE_URL
    provider: str = "gemini"
    message: str
    mode: str = "fast"
    timeout_s: float = 600.0


class BridgeImageTestRequest(BaseModel):
    bridge_base_url: str = DEFAULT_BRIDGE_BASE_URL
    provider: str = "gpt"
    prompt: str
    timeout_s: float = 600.0


class VideoMergeRequest(BaseModel):
    job_id: str | None = None
    project_id: str
    session_id: str
    silent_video_name: str = "story_render.mp4"
    output_name: str = "final_story.mp4"


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/bridge/status")
def bridge_status_get(bridge_base_url: str = Query(default=DEFAULT_BRIDGE_BASE_URL)) -> dict:
    try:
        client = BrowserBridgeClient(bridge_base_url)
        data = client.ping_ports()
        return {"success": True, "bridge_base_url": client.base_url, "bridge": data}
    except Exception as exc:  # pylint: disable=broad-except
        return {"success": False, "bridge_base_url": bridge_base_url, "error": str(exc)}


@app.post("/api/bridge/status")
def bridge_status_post(payload: BridgeStatusRequest) -> dict:
    try:
        client = BrowserBridgeClient(payload.bridge_base_url)
        data = client.ping_ports(payload.ports)
        return {"success": True, "bridge_base_url": client.base_url, "bridge": data}
    except Exception as exc:  # pylint: disable=broad-except
        return {"success": False, "bridge_base_url": payload.bridge_base_url, "error": str(exc)}


@app.post("/api/bridge/open")
def bridge_open(payload: BridgeOpenRequest) -> dict:
    try:
        client = BrowserBridgeClient(payload.bridge_base_url)
        data = client.open_ports(payload.ports, force_reconnect=payload.force_reconnect)
        return {"success": bool(data.get("success")), "bridge_base_url": client.base_url, "bridge": data}
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/bridge/chat-test")
def bridge_chat_test(payload: BridgeChatTestRequest) -> dict:
    try:
        client = BrowserBridgeClient(payload.bridge_base_url, timeout_s=payload.timeout_s)
        data, items = client.chat(payload.provider, [payload.message], mode=payload.mode, timeout_s=payload.timeout_s)
        first = items[0] if items else None
        return {
            "success": bool(first and first.success and first.answer.strip()),
            "bridge_base_url": client.base_url,
            "provider": payload.provider,
            "used_port": first.port if first else None,
            "answer": first.answer if first else "",
            "raw": data,
        }
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/bridge/image-test")
def bridge_image_test(payload: BridgeImageTestRequest) -> dict:
    try:
        client = BrowserBridgeClient(payload.bridge_base_url, timeout_s=payload.timeout_s)
        data, items = client.image(payload.provider, [payload.prompt], max_images=1, timeout_s=payload.timeout_s)
        first = items[0] if items else None
        if not first or not first.success or not first.images:
            raise RuntimeError((first.error_message if first else None) or "Bridge image test did not return an image.")
        target_root = REPO_ROOT / "projects_workspace" / "runtime" / "bridge_tests"
        target = target_root / f"{payload.provider}_image_test.png"
        saved_path = client.save_bridge_image(first.images[0], target)
        return {
            "success": saved_path.exists() and saved_path.stat().st_size > 0,
            "bridge_base_url": client.base_url,
            "provider": payload.provider,
            "used_port": first.port,
            "image_path": str(saved_path.relative_to(REPO_ROOT)),
            "byte_size": saved_path.stat().st_size,
            "raw": data,
        }
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/gpu/status")
def gpu_status() -> dict:
    try:
        return gpu_service.status()
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/gpu/prewarm-audio")
def gpu_prewarm_audio() -> dict:
    try:
        return gpu_service.prewarm_audio()
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/gpu/check-video-encoder")
def gpu_check_video_encoder() -> dict:
    try:
        return gpu_service.check_video_encoder()
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.on_event("startup")
def startup_prewarm() -> None:
    def warmup() -> None:
        try:
            service.prewarm()
        except Exception:
            # Keep web server up even if warmup fails; runtime run() will return concrete error.
            pass

    threading.Thread(target=warmup, daemon=True).start()


@app.get("/api/pipeline/audio/voices")
def list_audio_voices() -> dict:
    return {"voices": service.list_voice_profiles()}


@app.get("/api/pipeline/audio/models")
def list_audio_models() -> dict:
    return service.list_models()


class SetModelRequest(BaseModel):
    model_key: str


@app.post("/api/pipeline/audio/model")
def set_audio_model(payload: SetModelRequest) -> dict:
    return service.set_model(payload.model_key)


@app.post("/api/pipeline/audio/reset-runtime")
def reset_audio_runtime() -> dict:
    return service.reset_runtime()


@app.get("/api/text/files")
def list_text_files(project_id: str | None = Query(default=None), session_id: str | None = Query(default=None)) -> dict:
    try:
        return service.list_text_files(project_id=project_id, session_id=session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


class TextFileRequest(BaseModel):
    filename: str
    project_id: str | None = None
    session_id: str | None = None


class TextFileSaveRequest(BaseModel):
    filename: str
    content: str
    project_id: str | None = None
    session_id: str | None = None


class ProjectUpdateRequest(BaseModel):
    name: str
    notes: str = ""


class WorkspaceProjectCreateRequest(BaseModel):
    name: str
    project_id: str | None = None


class ProjectDeleteRequest(BaseModel):
    delete_artifacts: bool = False


class SessionDeleteRequest(BaseModel):
    delete_artifacts: bool = True


class SessionCreateRequest(BaseModel):
    session_id: str
    start_chapter: int = 1
    chapter_count: int = 1


class SessionFileRequest(BaseModel):
    stage: str
    filename: str
    content: str | None = None


class SessionAudioClearRequest(BaseModel):
    project_id: str
    session_id: str


class SessionStageClearRequest(BaseModel):
    project_id: str
    session_id: str
    stage: str


class LogsQueryRequest(BaseModel):
    namespaces: list[str] | None = None
    keyword: str = ""
    limit: int = 200


class LogsCleanRequest(BaseModel):
    namespaces: list[str] | None = None


class LogsRetentionRequest(BaseModel):
    namespaces: list[str] | None = None
    max_files_per_namespace: int = 20
    max_total_mb_per_namespace: int = 100


class KnowledgeMetaPatchRequest(BaseModel):
    path: str
    title: str | None = None
    summary: str | None = None
    type: str | None = None
    status: str | None = None
    diagram: str | None = None
    owner: str | None = None
    tags: list[str] | None = None


@app.post("/api/text/file")
def get_text_file(payload: TextFileRequest) -> dict:
    try:
        return service.get_text_file_content(payload.filename, project_id=payload.project_id, session_id=payload.session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/text/file/save")
def save_text_file(payload: TextFileSaveRequest) -> dict:
    try:
        return service.save_text_file_content(
            payload.filename,
            payload.content,
            project_id=payload.project_id,
            session_id=payload.session_id,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/text/file/delete")
def delete_text_file(payload: TextFileRequest) -> dict:
    try:
        return service.delete_text_file(payload.filename, project_id=payload.project_id, session_id=payload.session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/pipeline/audio/run", response_model=PipelineRunResponse)
def run_audio_pipeline(payload: PipelineRunRequest) -> PipelineRunResponse:
    if not pipeline_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Audio pipeline is already running.")

    try:
        job_id = payload.job_id or uuid.uuid4().hex
        progress_store.start(job_id, "Run Audio Pipeline", 3)

        def update_progress(event: dict) -> None:
            progress_store.update(job_id, event)

        result = service.run(
            progress_callback=update_progress,
            project_id=payload.project_id,
            session_id=payload.session_id,
            voice_profile=payload.voice_profile,
            model_key=payload.model_key,
            temperature=payload.temperature,
            top_k=payload.top_k,
            max_chars=payload.max_chars,
            tts_io_workers=payload.tts_io_workers,
            inference_timesteps=payload.inference_timesteps,
            postprocess=payload.postprocess,
            noise_reduction=payload.noise_reduction,
            highpass_hz=payload.highpass_hz,
            lowpass_hz=payload.lowpass_hz,
            target_peak_db=payload.target_peak_db,
            comp_threshold_db=payload.comp_threshold_db,
            comp_ratio=payload.comp_ratio,
            make_up_gain_db=payload.make_up_gain_db,
            presence_boost_db=payload.presence_boost_db,
            de_ess=payload.de_ess,
            gate_strength=payload.gate_strength,
            anti_leak_trim=payload.anti_leak_trim,
            anti_leak_max_ms=payload.anti_leak_max_ms,
        )
        progress_store.finish(job_id, result.success, result.message, result.manifest or {})
    except Exception as exc:  # pylint: disable=broad-except
        if "job_id" in locals():
            progress_store.finish(job_id, False, str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        pipeline_lock.release()

    return PipelineRunResponse(
        success=result.success,
        message=result.message,
        manifest=result.manifest,
        stdout=result.stdout,
        stderr=result.stderr,
    )


@app.get("/api/convert/projects")
def list_convert_projects() -> dict:
    return convert_service.list_projects()


@app.get("/api/projects")
def list_shared_projects() -> dict:
    return convert_service.list_projects()


@app.get("/api/workspace/projects")
def list_workspace_projects() -> dict:
    return convert_service.list_projects()


@app.post("/api/workspace/projects")
def create_workspace_project(payload: WorkspaceProjectCreateRequest) -> dict:
    try:
        return convert_service.create_workspace_project(name=payload.name, project_id=payload.project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/projects/{project_id}")
def get_shared_project(project_id: str) -> dict:
    try:
        return convert_service.get_project(project_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/workspace/projects/{project_id}/open")
def open_workspace_project(project_id: str, session_id: str | None = Query(default=None)) -> dict:
    try:
        projects_payload = convert_service.list_projects()
        projects = projects_payload.get("projects", [])
        selected_project = None
        for item in projects:
            if str(item.get("project_id", "")) == str(project_id):
                selected_project = item
                break
        if not selected_project:
            raise FileNotFoundError(f"Project not found: {project_id}")

        sessions = selected_project.get("sessions", []) or []
        selected_session_id = session_id
        if not selected_session_id and sessions:
            selected_session_id = str((sessions[0] or {}).get("session_id", "")).strip() or None

        chapter_urls = convert_service.get_project_chapter_urls(project_id)
        rewrite_prompt = convert_service.get_session_rewrite_prompt(project_id, session_id=selected_session_id)
        stage_indexes = {}
        for stage in ("raw", "rewritten", "audio_clean", "tts_inputs", "chapter_urls"):
            if not selected_session_id:
                stage_indexes[stage] = {"stage": stage, "files": []}
                continue
            try:
                stage_indexes[stage] = convert_service.list_session_files(project_id, selected_session_id, stage)
            except Exception:
                stage_indexes[stage] = {"stage": stage, "files": []}

        try:
            text_files = service.list_text_files(project_id=project_id, session_id=selected_session_id)
        except Exception:
            text_files = {"files": []}
        try:
            media_files = service.list_source_media_files(project_id=project_id, session_id=selected_session_id)
        except Exception:
            media_files = {"audio_files": [], "video_files": []}
        try:
            project_manifest = (
                convert_service.get_manifest(project_id, session_id=selected_session_id)
                if selected_session_id else
                convert_service.get_manifest(project_id)
            )
        except Exception:
            project_manifest = None

        return {
            "ok": True,
            "project_id": project_id,
            "session_id": selected_session_id,
            "workspace": {
                "projects": projects,
                "selected_project": selected_project,
                "selected_session_id": selected_session_id,
            },
            "preload": {
                "chapter_urls": chapter_urls,
                "rewrite_prompt": rewrite_prompt,
                "stage_indexes": stage_indexes,
                "text_files": text_files,
                "media_files": media_files,
                "manifest": project_manifest,
            },
        }
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.put("/api/projects/{project_id}")
def update_shared_project(project_id: str, payload: ProjectUpdateRequest) -> dict:
    try:
        return convert_service.rename_project(project_id, payload.name, payload.notes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/projects/{project_id}/delete")
def delete_shared_project(project_id: str, payload: ProjectDeleteRequest) -> dict:
    return convert_service.delete_project(project_id, delete_artifacts=payload.delete_artifacts)


@app.post("/api/projects/{project_id}/sessions/{session_id}/delete")
def delete_project_session(project_id: str, session_id: str, payload: SessionDeleteRequest) -> dict:
    return convert_service.delete_session(project_id, session_id, delete_artifacts=payload.delete_artifacts)


@app.post("/api/projects/{project_id}/sessions")
def create_project_session(project_id: str, payload: SessionCreateRequest) -> dict:
    try:
        return convert_service.create_session(
            project_id=project_id,
            session_id=payload.session_id,
            start_chapter=payload.start_chapter,
            chapter_count=payload.chapter_count,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/projects/{project_id}/sessions/{session_id}/files")
def list_project_session_files(project_id: str, session_id: str, stage: str = Query(...)) -> dict:
    try:
        return convert_service.list_session_files(project_id, session_id, stage)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/projects/{project_id}/sessions/{session_id}/file")
def get_project_session_file(project_id: str, session_id: str, payload: SessionFileRequest) -> dict:
    try:
        return convert_service.get_session_file_content(project_id, session_id, payload.stage, payload.filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.patch("/api/projects/{project_id}/sessions/{session_id}/file")
def save_project_session_file(project_id: str, session_id: str, payload: SessionFileRequest) -> dict:
    try:
        return convert_service.save_session_file_content(
            project_id,
            session_id,
            payload.stage,
            payload.filename,
            payload.content or "",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.delete("/api/projects/{project_id}/sessions/{session_id}/file")
def delete_project_session_file(project_id: str, session_id: str, stage: str = Query(...), filename: str = Query(...)) -> dict:
    try:
        return convert_service.delete_session_file(project_id, session_id, stage, filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/jobs/{job_id}")
def get_job_progress(job_id: str) -> dict:
    job = progress_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


@app.post("/api/jobs/{job_id}/stop")
def request_job_stop(job_id: str, payload: JobStopRequest) -> dict:
    try:
        progress_store.request_stop(job_id, emergency=False)
        return {"ok": True, "job_id": job_id, "stop_state": "stopping", "message": payload.reason}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found.") from exc


@app.post("/api/jobs/{job_id}/emergency-stop")
def request_job_emergency_stop(job_id: str, payload: JobStopRequest) -> dict:
    try:
        progress_store.request_stop(job_id, emergency=True)
        return {"ok": True, "job_id": job_id, "stop_state": "force_stopping", "message": payload.reason}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found.") from exc


@app.get("/api/jobs/{job_id}/stop-status")
def get_job_stop_status(job_id: str) -> dict:
    try:
        return progress_store.stop_status(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found.") from exc


@app.get("/api/convert/projects/{project_id}")
def get_convert_project(project_id: str, session_id: str | None = Query(default=None)) -> dict:
    try:
        return convert_service.get_manifest(project_id, session_id=session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/convert/collect")
def collect_story_text(payload: ConvertCollectRequest) -> dict:
    if not convert_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Convert pipeline is already running.")
    try:
        job_id = payload.job_id or uuid.uuid4().hex
        progress_store.start(job_id, "Collect Chapters", max(1, payload.chapter_count))

        def update_progress(event: dict) -> None:
            total = max(1, int(event.get("total") or payload.chapter_count or 1))
            current = max(0, min(total, int(event.get("current") or 0)))
            progress_store.update(job_id, {
                "stage": event.get("stage") or "collect",
                "message": event.get("message") or "",
                "preview_text": event.get("preview_text") or "",
                "current_units": current,
                "total_units": total,
                "files_done": int(event.get("files_done") or current),
            })

        return convert_service.collect(
            story_url=payload.story_url,
            start_chapter=payload.start_chapter,
            chapter_count=payload.chapter_count,
            project_name=payload.project_name,
            project_id=payload.project_id,
            chapter_token=payload.chapter_token,
            chapter_urls=payload.chapter_urls,
            apply_chapter_window=payload.apply_chapter_window,
            session_id=payload.session_id,
            progress_callback=update_progress,
        )
    except ValueError as exc:
        if "job_id" in locals():
            progress_store.finish(job_id, False, str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pylint: disable=broad-except
        if "job_id" in locals():
            progress_store.finish(job_id, False, str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        if "job_id" in locals():
            job = progress_store.get(job_id)
            if job and job.get("status") == "running":
                progress_store.finish(job_id, True, "Collect completed.")
        convert_lock.release()


@app.post("/api/convert/run-full")
def run_full_convert_to_tts_text(payload: ConvertFullRunRequest) -> dict:
    if not convert_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Convert pipeline is already running.")
    try:
        job_id = payload.job_id or uuid.uuid4().hex
        progress_store.start(job_id, "Convert To TTS TXT", max(1, payload.chapter_count * 3 + 2))

        def update_progress(event: dict) -> None:
            if progress_store.should_stop(job_id):
                raise RuntimeError("STOP_REQUESTED")
            progress_store.update(job_id, event)

        result = convert_service.run_full_to_tts_text(
            story_url=payload.story_url,
            start_chapter=payload.start_chapter,
            chapter_count=payload.chapter_count,
            project_name=payload.project_name,
            project_id=payload.project_id,
            chapter_token=payload.chapter_token,
            chapter_urls=payload.chapter_urls,
            apply_chapter_window=payload.apply_chapter_window,
            session_id=payload.session_id,
            provider=payload.provider,
            rewrite_model=payload.rewrite_model,
            story_context=payload.story_context,
            rewrite_prompt=payload.rewrite_prompt,
            llm_base_url=payload.llm_base_url,
            llm_model=payload.llm_model,
            llm_api_key=payload.llm_api_key,
            cdp_url=payload.cdp_url,
            cdp_urls=payload.cdp_urls,
            bridge_base_url=payload.bridge_base_url,
            bridge_timeout_s=payload.bridge_timeout_s,
            parallel_workers=payload.parallel_workers,
            clear_old_tts_text=payload.clear_old_tts_text,
            target_chars=payload.target_chars,
            max_chars=payload.max_chars,
            min_chars=payload.min_chars,
            auto_open_gemini_browser=payload.auto_open_gemini_browser,
            progress_callback=update_progress,
        )
        result["job_id"] = job_id
        progress_store.finish(job_id, bool(result.get("success")), result.get("message", "Convert pipeline completed."), result)
        return result
    except ValueError as exc:
        if "job_id" in locals():
            progress_store.finish(job_id, False, str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        if "job_id" in locals() and str(exc) == "STOP_REQUESTED":
            emergency = bool((progress_store.get(job_id) or {}).get("emergency_stop_requested"))
            progress_store.mark_stopped(job_id, emergency=emergency, message="Convert pipeline stopped by user.")
            return {"success": False, "stopped": True, "job_id": job_id, "message": "Stopped by user."}
        if "job_id" in locals():
            progress_store.finish(job_id, False, str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # pylint: disable=broad-except
        if "job_id" in locals():
            progress_store.finish(job_id, False, str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        convert_lock.release()


@app.post("/api/convert/crawl-chapters")
def crawl_story_chapters(payload: ConvertCrawlRequest) -> dict:
    if not convert_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Convert pipeline is already running.")
    try:
        return convert_service.crawl_chapters(
            story_url=payload.story_url,
            start_chapter=payload.start_chapter,
            chapter_count=payload.chapter_count,
            chapter_token=payload.chapter_token,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        convert_lock.release()


@app.post("/api/pipeline/run-all")
def run_all_pipeline(payload: RunAllRequest) -> dict:
    if not convert_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Convert pipeline is already running.")
    if not pipeline_lock.acquire(blocking=False):
        convert_lock.release()
        raise HTTPException(status_code=409, detail="Audio pipeline is already running.")
    try:
        job_id = payload.job_id or uuid.uuid4().hex
        progress_store.start(job_id, "Run All Pipeline", max(1, payload.chapter_count * 3 + 6))

        def update_progress(event: dict) -> None:
            if progress_store.should_stop(job_id):
                raise RuntimeError("STOP_REQUESTED")
            progress_store.update(job_id, event)

        if payload.resume_from_checkpoint and payload.project_id and payload.session_id:
            progress_store.update(job_id, {"stage": "resume", "message": "Resume from checkpoint."})
            rewrite_result = convert_service.rewrite(
                project_id=payload.project_id,
                provider=payload.provider,
                rewrite_model=payload.rewrite_model,
                story_context=payload.story_context,
                rewrite_prompt=payload.rewrite_prompt,
                llm_base_url=payload.llm_base_url,
                llm_model=payload.llm_model,
                llm_api_key=payload.llm_api_key,
                cdp_url=payload.cdp_url,
                cdp_urls=payload.cdp_urls,
                bridge_base_url=payload.bridge_base_url,
                bridge_timeout_s=payload.bridge_timeout_s,
                parallel_workers=payload.parallel_workers,
                session_id=payload.session_id,
                progress_callback=update_progress,
                should_stop=lambda: progress_store.should_stop(job_id),
                resume_only=True,
            )
            rewrite_summary = rewrite_result.get("summary", {})
            rewrite_failed = int(rewrite_summary.get("failed", 0) or 0)
            rewrite_success = int(rewrite_summary.get("success", 0) or 0)
            if rewrite_failed > 0 and rewrite_success <= 0:
                progress_store.finish(job_id, False, "Resume rewrite failed for all pending chapters.", rewrite_result)
                return {"success": False, "job_id": job_id, "rewrite": rewrite_result}
            clean_result = convert_service.audio_clean(payload.project_id, session_id=payload.session_id, progress_callback=update_progress)
            chunk_result = convert_service.chunk(payload.project_id, session_id=payload.session_id, progress_callback=update_progress)
            convert_result = {
                "success": True,
                "message": "Resume convert path completed.",
                "project_id": payload.project_id,
                "session_id": payload.session_id,
                "rewrite": rewrite_result,
                "audio_clean": clean_result,
                "chunk": chunk_result,
                "warning": (
                    f"Resume rewrite has partial failures: {rewrite_failed} chapter(s) failed. "
                    "Pipeline continued with available chapters."
                    if rewrite_failed > 0
                    else None
                ),
            }
        else:
            convert_result = convert_service.run_full_to_tts_text(
                story_url=payload.story_url,
                start_chapter=payload.start_chapter,
                chapter_count=payload.chapter_count,
                project_name=payload.project_name,
                project_id=payload.project_id,
                chapter_token=payload.chapter_token,
                chapter_urls=payload.chapter_urls,
                apply_chapter_window=payload.apply_chapter_window,
                session_id=payload.session_id,
                provider=payload.provider,
                rewrite_model=payload.rewrite_model,
                story_context=payload.story_context,
                rewrite_prompt=payload.rewrite_prompt,
                llm_base_url=payload.llm_base_url,
                llm_model=payload.llm_model,
                llm_api_key=payload.llm_api_key,
                cdp_url=payload.cdp_url,
                cdp_urls=payload.cdp_urls,
                bridge_base_url=payload.bridge_base_url,
                bridge_timeout_s=payload.bridge_timeout_s,
                parallel_workers=payload.parallel_workers,
                clear_old_tts_text=payload.clear_old_tts_text,
                target_chars=payload.target_chars,
                max_chars=payload.max_chars,
                min_chars=payload.min_chars,
                auto_open_gemini_browser=payload.auto_open_gemini_browser,
                progress_callback=update_progress,
            )
        if not convert_result.get("success"):
            progress_store.finish(job_id, False, convert_result.get("message", "Convert failed"), convert_result)
            return {"success": False, "job_id": job_id, "convert": convert_result}

        if progress_store.should_stop(job_id):
            emergency = bool((progress_store.get(job_id) or {}).get("emergency_stop_requested"))
            progress_store.mark_stopped(job_id, emergency=emergency, message="Run-all stopped before TTS.")
            return {"success": False, "stopped": True, "job_id": job_id, "convert": convert_result}

        progress_store.update(job_id, {"stage": "tts_prepare", "message": "Starting audio pipeline."})
        tts_result = service.run(
            progress_callback=update_progress,
            project_id=convert_result.get("project_id"),
            session_id=convert_result.get("session_id"),
            voice_profile=payload.voice_profile,
            model_key=payload.model_key,
            temperature=payload.temperature,
            top_k=payload.top_k,
            max_chars=payload.max_chars_tts,
            tts_io_workers=payload.tts_io_workers,
            inference_timesteps=payload.inference_timesteps,
        )
        result = {
            "success": bool(tts_result.success),
            "job_id": job_id,
            "convert": convert_result,
            "tts": {
                "success": tts_result.success,
                "message": tts_result.message,
                "manifest": tts_result.manifest,
            },
        }
        if not tts_result.success:
            progress_store.finish(job_id, False, tts_result.message or "TTS failed.", result)
            return result

        if progress_store.should_stop(job_id):
            emergency = bool((progress_store.get(job_id) or {}).get("emergency_stop_requested"))
            progress_store.mark_stopped(job_id, emergency=emergency, message="Run-all stopped before video.")
            return {"success": False, "stopped": True, "job_id": job_id, **result}

        if payload.video_enabled:
            progress_store.update(job_id, {"stage": "video_pipeline", "message": "Starting video pipeline."})
            video_payload = {
                "scene_duration_seconds": payload.video_scene_duration_seconds,
                "provider": payload.video_provider,
                "image_provider": payload.video_image_provider,
                "cdp_url": payload.video_gpt_cdp_url,
                "cdp_urls": payload.video_gpt_cdp_urls,
                "prompt_parallel_workers": payload.video_prompt_workers,
                "prompt_delay_seconds": payload.video_prompt_delay_seconds,
                "width": payload.video_width,
                "height": payload.video_height,
                "fps": payload.video_fps,
                "motion_intensity": payload.video_motion_intensity,
                "gpt_image_limit": payload.video_gpt_image_limit,
                "prompt_tts_input_limit": payload.video_prompt_tts_input_limit,
                "llm_base_url": payload.llm_base_url,
                "llm_model": payload.llm_model,
                "llm_api_key": payload.llm_api_key,
                "bridge_base_url": payload.bridge_base_url,
                "bridge_timeout_s": payload.bridge_timeout_s,
                "story_context": payload.video_story_context or payload.story_context,
                "gemini_prompt_template": payload.video_gemini_prompt_template,
                "render_with_audio": payload.video_render_with_audio,
                "merge_audio": payload.video_merge_audio,
                "output_name": payload.video_output_name,
                "video_encoder": payload.video_encoder,
                "video_preset": payload.video_preset,
                "video_crf": payload.video_crf,
                "video_cq": payload.video_cq,
                "render_workers": payload.video_render_workers,
            }
            video_result = video_service.run_full(
                project_id=convert_result.get("project_id"),
                session_id=convert_result.get("session_id"),
                payload=video_payload,
                progress_callback=update_progress,
                should_stop=lambda: progress_store.should_stop(job_id),
            )
            result["video"] = video_result

        progress_store.finish(job_id, True, "Run-all completed successfully.", result)
        return result
    except RuntimeError as exc:
        if str(exc) == "STOP_REQUESTED":
            emergency = bool((progress_store.get(job_id) or {}).get("emergency_stop_requested"))
            progress_store.mark_stopped(job_id, emergency=emergency, message="Run-all stopped by user.")
            return {"success": False, "stopped": True, "job_id": job_id, "message": "Stopped by user."}
        progress_store.finish(job_id, False, str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # pylint: disable=broad-except
        if "job_id" in locals():
            progress_store.finish(job_id, False, str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        pipeline_lock.release()
        convert_lock.release()


@app.post("/api/pipeline/run-all/resume")
def run_all_pipeline_resume(payload: RunAllRequest) -> dict:
    payload.resume_from_checkpoint = True
    return run_all_pipeline(payload)


@app.post("/api/pipeline/video/prewarm")
def prewarm_video_runtime(payload: VideoPipelineRequest) -> dict:
    job_id = payload.job_id or uuid.uuid4().hex
    progress_store.start(job_id, "Prewarm Video Runtime", 2)
    try:
        progress_store.update(job_id, {"stage": "video_prewarm", "current": 1, "total": 2, "message": "Checking video runtime..."})
        result = video_service.prewarm(
            sd_executable=payload.sd_executable,
            sd_model_path=payload.sd_model_path,
        )
        progress_store.finish(job_id, bool(result.get("ok")), result.get("message") or "Video prewarm finished.", result)
        return {"success": bool(result.get("ok")), "job_id": job_id, "result": result}
    except Exception as exc:  # pylint: disable=broad-except
        progress_store.finish(job_id, False, str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/pipeline/video/analyze")
def analyze_video_pipeline(payload: VideoPipelineRequest) -> dict:
    job_id = payload.job_id or uuid.uuid4().hex
    progress_store.start(job_id, "Analyze Video Session", 2)
    try:
        progress_store.update(job_id, {"stage": "video_analyze", "current": 1, "total": 2, "message": "Analyzing audio and tts inputs..."})
        result = video_service.analyze(
            project_id=payload.project_id,
            session_id=payload.session_id,
            scene_duration_seconds=payload.scene_duration_seconds,
        )
        progress_store.finish(job_id, True, "Video analyze completed.", result)
        return {"success": True, "job_id": job_id, "result": result}
    except Exception as exc:  # pylint: disable=broad-except
        progress_store.finish(job_id, False, str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/pipeline/video/prompts")
def run_video_prompts(payload: VideoPipelineRequest) -> dict:
    if not pipeline_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Pipeline is already running.")
    try:
        job_id = payload.job_id or uuid.uuid4().hex
        progress_store.start(job_id, "Run Video Prompts", 100)

        def update_progress(event: dict) -> None:
            if progress_store.should_stop(job_id):
                raise RuntimeError("STOP_REQUESTED")
            progress_store.update(job_id, event)

        result = video_service.run_prompts(
            project_id=payload.project_id,
            session_id=payload.session_id,
            payload=payload.model_dump(),
            progress_callback=update_progress,
            should_stop=lambda: progress_store.should_stop(job_id),
        )
        progress_store.finish(job_id, True, "Video prompts completed.", result)
        return {"success": True, "job_id": job_id, "result": result}
    except RuntimeError as exc:
        if str(exc) == "STOP_REQUESTED":
            emergency = bool((progress_store.get(job_id) or {}).get("emergency_stop_requested"))
            progress_store.mark_stopped(job_id, emergency=emergency, message="Video prompts stopped by user.")
            return {"success": False, "stopped": True, "job_id": job_id}
        progress_store.finish(job_id, False, str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # pylint: disable=broad-except
        if "job_id" in locals():
            progress_store.finish(job_id, False, str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        pipeline_lock.release()


@app.post("/api/pipeline/video/images")
def run_video_images(payload: VideoPipelineRequest) -> dict:
    if not pipeline_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Pipeline is already running.")
    try:
        job_id = payload.job_id or uuid.uuid4().hex
        progress_store.start(job_id, "Run Video Images", 100)

        def update_progress(event: dict) -> None:
            if progress_store.should_stop(job_id):
                raise RuntimeError("STOP_REQUESTED")
            progress_store.update(job_id, event)

        result = video_service.run_images(
            project_id=payload.project_id,
            session_id=payload.session_id,
            payload=payload.model_dump(),
            progress_callback=update_progress,
            should_stop=lambda: progress_store.should_stop(job_id),
        )
        progress_store.finish(job_id, True, "Video images completed.", result)
        return {"success": True, "job_id": job_id, "result": result}
    except RuntimeError as exc:
        if str(exc) == "STOP_REQUESTED":
            emergency = bool((progress_store.get(job_id) or {}).get("emergency_stop_requested"))
            progress_store.mark_stopped(job_id, emergency=emergency, message="Video image generation stopped by user.")
            return {"success": False, "stopped": True, "job_id": job_id}
        progress_store.finish(job_id, False, str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # pylint: disable=broad-except
        if "job_id" in locals():
            progress_store.finish(job_id, False, str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        pipeline_lock.release()


@app.post("/api/pipeline/video/render")
def run_video_render(payload: VideoPipelineRequest) -> dict:
    if not pipeline_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Pipeline is already running.")
    try:
        job_id = payload.job_id or uuid.uuid4().hex
        progress_store.start(job_id, "Run Video Render", 100)

        def update_progress(event: dict) -> None:
            if progress_store.should_stop(job_id):
                raise RuntimeError("STOP_REQUESTED")
            progress_store.update(job_id, event)

        result = video_service.render(
            project_id=payload.project_id,
            session_id=payload.session_id,
            payload=payload.model_dump(),
            progress_callback=update_progress,
            should_stop=lambda: progress_store.should_stop(job_id),
        )
        progress_store.finish(job_id, True, "Video render completed.", result)
        return {"success": True, "job_id": job_id, "result": result}
    except RuntimeError as exc:
        if str(exc) == "STOP_REQUESTED":
            emergency = bool((progress_store.get(job_id) or {}).get("emergency_stop_requested"))
            progress_store.mark_stopped(job_id, emergency=emergency, message="Video render stopped by user.")
            return {"success": False, "stopped": True, "job_id": job_id}
        progress_store.finish(job_id, False, str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # pylint: disable=broad-except
        if "job_id" in locals():
            progress_store.finish(job_id, False, str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        pipeline_lock.release()


@app.post("/api/pipeline/video/merge")
def merge_video_audio(payload: VideoMergeRequest) -> dict:
    if not pipeline_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Pipeline is already running.")
    try:
        job_id = payload.job_id or uuid.uuid4().hex
        progress_store.start(job_id, "Merge Video And Audio", 3)
        progress_store.update(job_id, {"stage": "video_merge", "current": 1, "total": 3, "message": "Merging final video..."})
        result = video_service.merge(
            project_id=payload.project_id,
            session_id=payload.session_id,
            silent_video_name=payload.silent_video_name,
            output_name=payload.output_name,
        )
        progress_store.finish(job_id, True, "Video merge completed.", result)
        return {"success": True, "job_id": job_id, "result": result}
    except Exception as exc:  # pylint: disable=broad-except
        if "job_id" in locals():
            progress_store.finish(job_id, False, str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        pipeline_lock.release()


@app.post("/api/pipeline/video/run")
def run_video_pipeline(payload: VideoPipelineRequest) -> dict:
    if not pipeline_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Pipeline is already running.")
    try:
        job_id = payload.job_id or uuid.uuid4().hex
        progress_store.start(job_id, "Run Video Pipeline", 300)

        def update_progress(event: dict) -> None:
            if progress_store.should_stop(job_id):
                raise RuntimeError("STOP_REQUESTED")
            progress_store.update(job_id, event)

        result = video_service.run_full(
            project_id=payload.project_id,
            session_id=payload.session_id,
            payload=payload.model_dump(),
            progress_callback=update_progress,
            should_stop=lambda: progress_store.should_stop(job_id),
        )
        progress_store.finish(job_id, True, "Video pipeline completed.", result)
        return {"success": True, "job_id": job_id, "result": result}
    except RuntimeError as exc:
        if str(exc) == "STOP_REQUESTED":
            emergency = bool((progress_store.get(job_id) or {}).get("emergency_stop_requested"))
            progress_store.mark_stopped(job_id, emergency=emergency, message="Video pipeline stopped by user.")
            return {"success": False, "stopped": True, "job_id": job_id}
        progress_store.finish(job_id, False, str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # pylint: disable=broad-except
        if "job_id" in locals():
            progress_store.finish(job_id, False, str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        pipeline_lock.release()


@app.post("/api/convert/crawl-chapters-from-browser")
def crawl_story_chapters_from_browser(payload: ConvertCrawlBrowserRequest) -> dict:
    if not convert_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Convert pipeline is already running.")
    try:
        return convert_service.crawl_chapters_from_browser(
            story_url=payload.story_url,
            cdp_url=payload.cdp_url,
            max_scroll_rounds=payload.max_scroll_rounds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        convert_lock.release()


@app.get("/api/projects/{project_id}/chapter-urls")
def get_project_chapter_urls(project_id: str) -> dict:
    try:
        return convert_service.get_project_chapter_urls(project_id)
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/projects/chapter-urls/save")
def save_project_chapter_urls(payload: ProjectChapterUrlsRequest) -> dict:
    try:
        return convert_service.save_project_chapter_urls(
            project_id=payload.project_id,
            urls=payload.urls or [],
            session_id=payload.session_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/projects/chapter-urls/clear")
def clear_project_chapter_urls(payload: ProjectChapterUrlsRequest) -> dict:
    try:
        return convert_service.clear_project_chapter_urls(project_id=payload.project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/projects/{project_id}/chapters")
def list_project_chapters(project_id: str) -> dict:
    try:
        return convert_service.list_project_chapter_items(project_id)
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/projects/chapters/add")
def add_project_chapters(payload: ProjectChapterUrlsRequest) -> dict:
    try:
        return convert_service.add_project_chapter_urls(payload.project_id, payload.urls or [], session_id=payload.session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.patch("/api/projects/chapters/item")
def patch_project_chapter_item(payload: ProjectChapterItemRequest) -> dict:
    try:
        return convert_service.update_project_chapter_item(
            project_id=payload.project_id,
            index=int(payload.index),
            url=str(payload.url or ""),
            session_id=payload.session_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.delete("/api/projects/chapters/item")
def delete_project_chapter_item(
    project_id: str = Query(...),
    index: int = Query(...),
    session_id: str | None = Query(default=None),
) -> dict:
    try:
        return convert_service.delete_project_chapter_item(project_id=project_id, index=index, session_id=session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/projects/{project_id}/rewrite-prompt")
def get_project_rewrite_prompt(project_id: str, session_id: str | None = Query(default=None)) -> dict:
    try:
        return convert_service.get_session_rewrite_prompt(project_id, session_id=session_id)
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/projects/rewrite-prompt/save")
def save_project_rewrite_prompt(payload: ProjectRewritePromptRequest) -> dict:
    try:
        return convert_service.save_project_rewrite_prompt(
            project_id=payload.project_id,
            session_id=payload.session_id,
            story_context=payload.story_context,
            rewrite_prompt=payload.rewrite_prompt,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/projects/rewrite-prompt/clear")
def clear_project_rewrite_prompt(payload: ProjectRewritePromptRequest) -> dict:
    try:
        return convert_service.clear_project_rewrite_prompt(project_id=payload.project_id, session_id=payload.session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/projects/{project_id}/video-prompt")
def get_project_video_prompt(project_id: str, session_id: str | None = Query(default=None)) -> dict:
    try:
        return video_service.get_session_video_prompt(project_id, session_id=session_id)
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/projects/video-prompt/save")
def save_project_video_prompt(payload: VideoPromptConfigRequest) -> dict:
    try:
        if not payload.session_id:
            raise ValueError("session_id is required for video prompt config")
        return video_service.save_session_video_prompt(
            project_id=payload.project_id,
            session_id=payload.session_id,
            story_context=payload.story_context,
            gemini_prompt_template=payload.gemini_prompt_template,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/projects/video-prompt/clear")
def clear_project_video_prompt(payload: VideoPromptConfigRequest) -> dict:
    try:
        return video_service.clear_session_video_prompt(project_id=payload.project_id, session_id=payload.session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/video-prompt-default")
def get_video_prompt_default() -> dict:
    try:
        return video_service.get_video_prompt_default()
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/video-prompt-default/save")
def save_video_prompt_default(payload: VideoPromptDefaultRequest) -> dict:
    try:
        return video_service.save_video_prompt_default(
            story_context=payload.story_context,
            gemini_prompt_template=payload.gemini_prompt_template,
        )
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/video-prompt-default/clear")
def clear_video_prompt_default() -> dict:
    try:
        return video_service.clear_video_prompt_default()
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/prompt-default")
def get_prompt_default() -> dict:
    try:
        return convert_service.get_prompt_default()
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/prompt-default/save")
def save_prompt_default(payload: PromptDefaultRequest) -> dict:
    try:
        return convert_service.save_prompt_default(
            story_context=payload.story_context,
            rewrite_prompt=payload.rewrite_prompt,
            story_context_template=payload.story_context_template,
        )
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/prompt-default/clear")
def clear_prompt_default() -> dict:
    try:
        return convert_service.clear_prompt_default()
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/llm-default")
def get_llm_default() -> dict:
    try:
        return convert_service.get_llm_default()
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/llm-default/save")
def save_llm_default(payload: LlmDefaultRequest) -> dict:
    try:
        return convert_service.save_llm_default(
            llm_base_url=payload.llm_base_url,
            llm_model=payload.llm_model,
            llm_api_key=payload.llm_api_key,
        )
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/llm-default/clear")
def clear_llm_default() -> dict:
    try:
        return convert_service.clear_llm_default()
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/llm/chat-test")
def llm_chat_test(payload: LlmChatTestRequest) -> dict:
    try:
        return convert_service.test_llm_chat(
            message=payload.message,
            llm_base_url=payload.llm_base_url,
            llm_model=payload.llm_model,
            llm_api_key=payload.llm_api_key,
            max_tokens=payload.max_tokens,
            temperature=payload.temperature,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/convert/projects/{project_id}/rewrite")
def rewrite_convert_project(project_id: str, payload: ConvertRewriteRequest) -> dict:
    if not convert_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Convert pipeline is already running.")
    try:
        job_id = payload.job_id or uuid.uuid4().hex
        progress_store.start(job_id, "Rewrite", 1)

        def update_progress(event: dict) -> None:
            total = max(1, int(event.get("total") or 1))
            current = max(0, min(total, int(event.get("current") or 0)))
            progress_store.update(job_id, {
                "stage": event.get("stage") or "rewrite",
                "message": event.get("message") or "",
                "preview_text": event.get("preview_text") or "",
                "current_units": current,
                "total_units": total,
                "files_done": int(event.get("files_done") or current),
            })

        return convert_service.rewrite(
            project_id=project_id,
            provider=payload.provider,
            rewrite_model=payload.rewrite_model,
            story_context=payload.story_context,
            rewrite_prompt=payload.rewrite_prompt,
            llm_base_url=payload.llm_base_url,
            llm_model=payload.llm_model,
            llm_api_key=payload.llm_api_key,
            cdp_url=payload.cdp_url,
            cdp_urls=payload.cdp_urls,
            bridge_base_url=payload.bridge_base_url,
            bridge_timeout_s=payload.bridge_timeout_s,
            parallel_workers=payload.parallel_workers,
            resume_only=payload.resume_only,
            session_id=payload.session_id,
            progress_callback=update_progress,
            should_stop=lambda: progress_store.should_stop(job_id),
        )
    except Exception as exc:  # pylint: disable=broad-except
        if "job_id" in locals():
            progress_store.finish(job_id, False, str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        if "job_id" in locals():
            job = progress_store.get(job_id)
            if job and job.get("status") == "running":
                progress_store.finish(job_id, True, "Rewrite completed.")
        convert_lock.release()


@app.post("/api/convert/projects/{project_id}/audio-clean")
def audio_clean_convert_project(
    project_id: str,
    session_id: str | None = Query(default=None),
    job_id: str | None = Query(default=None),
) -> dict:
    if not convert_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Convert pipeline is already running.")
    try:
        resolved_job_id = job_id or uuid.uuid4().hex
        progress_store.start(resolved_job_id, "Audio Clean", 1)

        def update_progress(event: dict) -> None:
            total = max(1, int(event.get("total") or 1))
            current = max(0, min(total, int(event.get("current") or 0)))
            progress_store.update(resolved_job_id, {
                "stage": event.get("stage") or "audio_clean",
                "message": event.get("message") or "",
                "preview_text": event.get("preview_text") or "",
                "current_units": current,
                "total_units": total,
                "files_done": int(event.get("files_done") or current),
            })

        return convert_service.audio_clean(project_id, session_id=session_id, progress_callback=update_progress)
    except Exception as exc:  # pylint: disable=broad-except
        if "resolved_job_id" in locals():
            progress_store.finish(resolved_job_id, False, str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        if "resolved_job_id" in locals():
            job = progress_store.get(resolved_job_id)
            if job and job.get("status") == "running":
                progress_store.finish(resolved_job_id, True, "Audio clean completed.")
        convert_lock.release()


@app.post("/api/convert/projects/{project_id}/chunk")
def chunk_convert_project(project_id: str, payload: ConvertChunkRequest) -> dict:
    if not convert_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Convert pipeline is already running.")
    try:
        job_id = payload.job_id or uuid.uuid4().hex
        progress_store.start(job_id, "Create TTS Inputs", 1)

        def update_progress(event: dict) -> None:
            total = max(1, int(event.get("total") or 1))
            current = max(0, min(total, int(event.get("current") or 0)))
            progress_store.update(job_id, {
                "stage": event.get("stage") or "tts_inputs",
                "message": event.get("message") or "",
                "preview_text": event.get("preview_text") or "",
                "current_units": current,
                "total_units": total,
                "files_done": int(event.get("files_done") or current),
            })

        return convert_service.chunk(
            project_id,
            min_words=payload.min_words,
            max_words=payload.max_words,
            session_id=payload.session_id,
            progress_callback=update_progress,
        )
    except Exception as exc:  # pylint: disable=broad-except
        if "job_id" in locals():
            progress_store.finish(job_id, False, str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        if "job_id" in locals():
            job = progress_store.get(job_id)
            if job and job.get("status") == "running":
                progress_store.finish(job_id, True, "TTS inputs completed.")
        convert_lock.release()


@app.post("/api/convert/projects/{project_id}/export-tts-text")
def export_tts_text_convert_project(project_id: str, payload: ConvertExportRequest) -> dict:
    if not convert_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Convert pipeline is already running.")
    try:
        return convert_service.export_tts_text(project_id, clear_old=payload.clear_old, session_id=payload.session_id)
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        convert_lock.release()


@app.post("/api/convert/gemini-browser/start")
def start_gemini_browser(payload: GeminiChromeRequest) -> dict:
    try:
        return convert_service.open_gemini_chrome(
            port=payload.port,
            user_data_dir=payload.user_data_dir,
            url=payload.url,
        )
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/files/clear/text")
def clear_text_files() -> dict:
    return service.clear_text_files()


@app.post("/api/files/clear/auto-output-audio")
def clear_auto_output_audio() -> dict:
    return service.clear_auto_output_audio()


@app.post("/api/files/clear/source-media")
def clear_source_media() -> dict:
    return service.clear_source_full_audio_video()


@app.post("/api/files/clear/session-audio")
def clear_session_audio(payload: SessionAudioClearRequest) -> dict:
    try:
        return service.clear_session_audio_files(payload.project_id, payload.session_id)
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/files/clear/session-video")
def clear_session_video(payload: SessionAudioClearRequest) -> dict:
    try:
        return service.clear_session_video_files(payload.project_id, payload.session_id)
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/files/clear/session-video-images")
def clear_session_video_images(payload: SessionAudioClearRequest) -> dict:
    try:
        return service.clear_session_video_images_files(payload.project_id, payload.session_id)
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/browser/chrome-pool/open")
def open_browser_chrome_pool(payload: GeminiChromePoolRequest) -> dict:
    try:
        return convert_service.open_gemini_chrome_pool(
            ports=payload.ports,
            user_data_root=payload.user_data_root,
            url=payload.url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/browser/chrome-pool/close")
def close_browser_chrome_pool(payload: GeminiChromePoolRequest) -> dict:
    try:
        return convert_service.close_gemini_chrome_pool(payload.ports)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/browser/chrome-pool/status")
def status_browser_chrome_pool() -> dict:
    try:
        return convert_service.get_gemini_chrome_pool_status()
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/browser/chrome-pool/mark-login-ready")
def mark_login_ready_browser_chrome_pool(payload: GeminiChromePoolLoginRequest) -> dict:
    try:
        return convert_service.mark_gemini_chrome_pool_login_ready(
            ports=payload.ports,
            login_ready=payload.login_ready,
        )
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/files/clear/session-stage")
def clear_session_stage(payload: SessionStageClearRequest) -> dict:
    try:
        return service.clear_session_stage_files(payload.project_id, payload.session_id, payload.stage)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _log_namespace_roots() -> dict[str, Path]:
    return {
        "backend": BASE_DIR / "web_stdout.log",
        "backend_err": BASE_DIR / "web_stderr.log",
        "setup": REPO_ROOT / ".logs",
        "runtime": REPO_ROOT / "auto_text_to_voice" / "output" / "last_run.log",
        "docs": REPO_ROOT / "docs",
    }


def _knowledge_catalog_path() -> Path:
    return REPO_ROOT / "docs" / "knowledge_catalog.json"


def _load_knowledge_catalog() -> dict:
    path = _knowledge_catalog_path()
    if not path.exists():
        return {"version": 1, "updated_at": "", "items": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "updated_at": "", "items": []}
    if not isinstance(payload.get("items"), list):
        payload["items"] = []
    return payload


def _save_knowledge_catalog(payload: dict) -> None:
    path = _knowledge_catalog_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    payload.setdefault("version", 1)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


@app.get("/api/logs/namespaces")
def list_log_namespaces() -> dict:
    roots = _log_namespace_roots()
    result = []
    for name, root in roots.items():
        if root.is_dir():
            count = len(list(root.glob("*")))
            result.append({"name": name, "type": "dir", "path": str(root), "count": count})
        else:
            result.append({"name": name, "type": "file", "path": str(root), "exists": root.exists()})
    return {"namespaces": result}


@app.post("/api/logs/query")
def query_logs(payload: LogsQueryRequest) -> dict:
    roots = _log_namespace_roots()
    namespaces = payload.namespaces or list(roots.keys())
    keyword = (payload.keyword or "").strip().lower()
    limit = max(1, min(500, int(payload.limit or 200)))
    rows: list[dict] = []
    for ns in namespaces:
        root = roots.get(ns)
        if not root:
            continue
        files: list[Path]
        if root.is_dir():
            files = sorted([p for p in root.glob("*.log") if p.is_file()], key=lambda p: p.stat().st_mtime, reverse=True)
        else:
            files = [root] if root.exists() and root.is_file() else []
        for file_path in files[:20]:
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                continue
            for line in reversed(content[-600:]):
                if keyword and keyword not in line.lower():
                    continue
                rows.append({"namespace": ns, "file": file_path.name, "line": line})
                if len(rows) >= limit:
                    return {"rows": rows, "count": len(rows)}
    return {"rows": rows, "count": len(rows)}


@app.post("/api/logs/clean")
def clean_logs(payload: LogsCleanRequest) -> dict:
    roots = _log_namespace_roots()
    namespaces = payload.namespaces or list(roots.keys())
    removed = 0
    for ns in namespaces:
        root = roots.get(ns)
        if not root:
            continue
        if root.is_dir():
            for p in root.glob("*.log"):
                if p.is_file():
                    p.unlink(missing_ok=True)
                    removed += 1
        else:
            if root.exists() and root.is_file():
                root.unlink(missing_ok=True)
                removed += 1
    return {"ok": True, "removed": removed}


@app.post("/api/logs/retention/apply")
def apply_logs_retention(payload: LogsRetentionRequest) -> dict:
    roots = _log_namespace_roots()
    namespaces = payload.namespaces or list(roots.keys())
    max_files = max(1, min(200, int(payload.max_files_per_namespace or 20)))
    max_total_bytes = max(5, min(2048, int(payload.max_total_mb_per_namespace or 100))) * 1024 * 1024
    removed_files = 0
    removed_bytes = 0
    details: list[dict] = []
    for ns in namespaces:
        root = roots.get(ns)
        if not root:
            continue
        if root.is_file():
            files = [root] if root.exists() and root.is_file() else []
        else:
            files = sorted(
                [p for p in root.glob("*.log") if p.is_file()],
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        keep = files[:max_files]
        delete = files[max_files:]
        total = sum(p.stat().st_size for p in keep if p.exists())
        for p in list(reversed(keep)):
            if total <= max_total_bytes:
                break
            sz = p.stat().st_size if p.exists() else 0
            p.unlink(missing_ok=True)
            removed_files += 1
            removed_bytes += sz
            total -= sz
        for p in delete:
            sz = p.stat().st_size if p.exists() else 0
            p.unlink(missing_ok=True)
            removed_files += 1
            removed_bytes += sz
        details.append({
            "namespace": ns,
            "kept": min(len(files), max_files),
            "deleted": max(0, len(files) - max_files),
        })
    return {
        "ok": True,
        "removed_files": removed_files,
        "removed_bytes": removed_bytes,
        "max_files_per_namespace": max_files,
        "max_total_mb_per_namespace": int(max_total_bytes / (1024 * 1024)),
        "details": details,
    }


@app.get("/api/knowledge/index")
def knowledge_index() -> dict:
    groups = {
        "docs": list((REPO_ROOT / "docs").glob("*.md")),
        "plans": [p for p in (REPO_ROOT / "docs").glob("plan*.md")],
        "agent": [REPO_ROOT / "agens" / "flow_code_skill.md"],
        "logs": list((REPO_ROOT / ".logs").glob("*.log")),
    }
    items = []
    for group, paths in groups.items():
        for p in paths:
            if not p.exists() or not p.is_file():
                continue
            rel = str(p.relative_to(REPO_ROOT)).replace("\\", "/")
            try:
                head = p.read_text(encoding="utf-8", errors="replace").splitlines()[:20]
            except Exception:
                head = []
            title = next((line.strip("# ").strip() for line in head if line.strip().startswith("#")), p.stem)
            summary = ""
            for line in head:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                summary = line[:180]
                break
            items.append({
                "path": rel,
                "type": group,
                "title": title or p.name,
                "summary": summary or "No summary.",
                "updated_at": p.stat().st_mtime,
            })
    catalog = _load_knowledge_catalog()
    by_path = {str(item.get("path") or ""): item for item in catalog.get("items", []) if isinstance(item, dict)}
    merged = []
    for item in items:
        meta = by_path.get(item["path"])
        if meta:
            for key in ("title", "summary", "type", "status", "diagram", "owner", "tags"):
                if key in meta and meta.get(key) not in (None, ""):
                    item[key] = meta.get(key)
        merged.append(item)
    merged.sort(key=lambda x: x["updated_at"], reverse=True)
    return {"items": merged[:500], "count": len(merged)}


@app.post("/api/knowledge/reindex")
def knowledge_reindex() -> dict:
    data = knowledge_index()
    catalog = _load_knowledge_catalog()
    existing = {str(i.get("path") or ""): i for i in catalog.get("items", []) if isinstance(i, dict)}
    next_items = []
    for item in data.get("items", []):
        path = str(item.get("path") or "")
        base = existing.get(path, {})
        merged = dict(base)
        for key in ("path", "type", "title", "summary", "diagram", "status", "owner", "tags"):
            if key in item:
                merged[key] = item[key]
        next_items.append(merged)
    catalog["items"] = next_items[:1000]
    _save_knowledge_catalog(catalog)
    return {"ok": True, "count": len(catalog["items"])}


@app.get("/api/knowledge/file-meta")
def knowledge_file_meta(path: str = Query(..., min_length=1)) -> dict:
    clean = path.replace("\\", "/").strip().lstrip("/")
    target = (REPO_ROOT / clean).resolve()
    if not str(target).startswith(str(REPO_ROOT.resolve())):
        raise HTTPException(status_code=400, detail="Invalid path.")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found.")
    catalog = _load_knowledge_catalog()
    item = next((x for x in catalog.get("items", []) if str(x.get("path") or "") == clean), None)
    if not item:
        item = {"path": clean}
    item["size_bytes"] = target.stat().st_size
    item["updated_at_fs"] = target.stat().st_mtime
    if target.suffix.lower() in {".md", ".txt", ".log", ".json"} and target.stat().st_size <= 512 * 1024:
        head = target.read_text(encoding="utf-8", errors="replace").splitlines()[:30]
        item["preview_head"] = "\n".join(head)
    else:
        item["preview_head"] = "(preview skipped: binary or too large)"
    return {"item": item}


@app.patch("/api/knowledge/file-meta")
def patch_knowledge_file_meta(payload: KnowledgeMetaPatchRequest) -> dict:
    clean = payload.path.replace("\\", "/").strip().lstrip("/")
    target = (REPO_ROOT / clean).resolve()
    if not str(target).startswith(str(REPO_ROOT.resolve())):
        raise HTTPException(status_code=400, detail="Invalid path.")
    catalog = _load_knowledge_catalog()
    items = catalog.get("items", [])
    found = None
    for item in items:
        if str(item.get("path") or "") == clean:
            found = item
            break
    if found is None:
        found = {"path": clean}
        items.append(found)
    for key in ("title", "summary", "type", "status", "diagram", "owner"):
        value = getattr(payload, key)
        if value is not None:
            found[key] = value
    if payload.tags is not None:
        found["tags"] = [str(x).strip() for x in payload.tags if str(x).strip()][:20]
    catalog["items"] = items[:1000]
    _save_knowledge_catalog(catalog)
    return {"ok": True, "item": found}


@app.get("/api/files/source-media")
def list_source_media(
    project_id: str | None = Query(default=None),
    session_id: str | None = Query(default=None),
) -> dict:
    data = service.list_source_media_files(project_id=project_id, session_id=session_id)
    audio_exts = {".wav", ".mp3", ".flac", ".m4a", ".ogg"}
    audio_files = [
        name for name in (data.get("audio_files") or [])
        if Path(name).suffix.lower() in audio_exts
    ]
    return {
        "audio_files": audio_files,
        "video_files": data.get("video_files") or [],
    }


@app.get("/api/files/download/audio")
def download_audio_file(
    filename: str = Query(..., min_length=1),
    project_id: str | None = Query(default=None),
    session_id: str | None = Query(default=None),
) -> FileResponse:
    root = service.resolve_audio_root(project_id=project_id, session_id=session_id)
    target = (root / filename).resolve()
    if target.parent != root.resolve() or not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Audio file not found.")
    return FileResponse(
        path=target,
        filename=target.name,
        media_type="application/octet-stream",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/api/files/download/video")
def download_video_file(
    filename: str = Query(..., min_length=1),
    project_id: str | None = Query(default=None),
    session_id: str | None = Query(default=None),
) -> FileResponse:
    root = service.resolve_video_root(project_id=project_id, session_id=session_id)
    target = (root / filename).resolve()
    if target.parent != root.resolve() or not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Video file not found.")
    return FileResponse(
        path=target,
        filename=target.name,
        media_type="application/octet-stream",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR)), name="assets")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")
