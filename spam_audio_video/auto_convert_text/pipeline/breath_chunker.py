from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from auto_convert_text.models.dto import utc_now_iso
from auto_convert_text.pipeline.browser_bridge_client import DEFAULT_BRIDGE_BASE_URL, BrowserBridgeClient
from auto_convert_text.storage.project_store import ProjectStore


DEFAULT_BREATH_CHUNK_PROMPT = """Ban la bien tap vien voice-over tieng Viet.
Hay chia doan van duoi day thanh cac nhom lay hoi tu nhien de doc truyen.
Quy tac:
1. Giu nguyen noi dung, khong them bot chu.
2. Moi dong la mot nhom lay hoi de TTS doc.
3. Uu tien ngat o dau cham, cham phay, hai cham, phay.
4. Khong cat giua ten rieng, so + don vi, cum chu co nghia.
5. Moi dong thuong dai 12-28 tu, khong qua 220 ky tu.
6. Tra ve duy nhat danh sach dong text, khong markdown, khong danh so.
Noi dung:
{text}
"""


@dataclass
class BreathChunkConfig:
    provider: str = "bridge_gemini"
    model_preference: str = "fast"
    prompt: str = DEFAULT_BREATH_CHUNK_PROMPT
    cdp_url: str | None = None
    bridge_base_url: str = DEFAULT_BRIDGE_BASE_URL
    bridge_timeout_s: float = 600.0
    min_chars: int = 40
    max_chars: int = 220


def _split_sentences_fallback(text: str) -> list[str]:
    compact = " ".join((text or "").split())
    if not compact:
        return []
    return [p.strip(" ,") for p in re.split(r"(?<=[.!?])\s+", compact) if p.strip(" ,")]


def _merge_short_chunks(chunks: list[str], min_chars: int, max_chars: int) -> list[str]:
    merged: list[str] = []
    for chunk in chunks:
        item = " ".join(chunk.split()).strip()
        if not item:
            continue
        if merged and len(item) < min_chars and len(merged[-1]) + 1 + len(item) <= max_chars:
            merged[-1] = f"{merged[-1]} {item}".strip()
        else:
            merged.append(item)
    return merged


def _normalize_gemini_chunk_lines(output: str) -> list[str]:
    lines = []
    for raw in (output or "").splitlines():
        line = raw.strip()
        line = re.sub(r"^\d+[\).:\-]\s*", "", line)
        line = re.sub(r"^[-*]\s*", "", line)
        line = " ".join(line.split())
        if not line:
            continue
        if line.lower() in {"show thinking", "hide thinking"}:
            continue
        lines.append(line)
    return lines


class BreathChunker:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        self.store = ProjectStore(self.repo_root)

    def run(
        self,
        project_id: str,
        config: BreathChunkConfig,
        session_id: str | None = None,
        progress_callback: Callable[[dict], None] | None = None,
    ) -> dict:
        session_dir = self.store.session_dir(project_id, session_id)
        source_dir = session_dir / "chapters_text" / "audio_clean"
        files = sorted(source_dir.glob("chapter_*.txt"))
        if not files:
            raise FileNotFoundError(f"No audio-clean chapter files found: {source_dir}")

        provider = str(config.provider or "bridge_gemini").strip().lower()
        if provider not in {"bridge_gemini", "fake"}:
            provider = "bridge_gemini"
        bridge_client = None if provider == "fake" else BrowserBridgeClient(config.bridge_base_url, timeout_s=config.bridge_timeout_s)
        items: list[dict] = []
        global_index = 0
        failed = 0
        for file_idx, chapter_path in enumerate(files, start=1):
            text = chapter_path.read_text(encoding="utf-8", errors="replace").strip()
            if not text:
                continue
            if progress_callback:
                progress_callback({
                    "stage": "breath_chunk",
                    "current": file_idx - 1,
                    "total": len(files),
                    "message": f"Dang chia nhom lay hoi chapter {chapter_path.name}",
                })

            prompt = config.prompt.format(text=text)
            chunks: list[str] = []
            error: str | None = None
            try:
                if bridge_client is None:
                    chunks = _split_sentences_fallback(text)
                else:
                    _payload, bridge_items = bridge_client.chat(
                        "gemini",
                        [prompt],
                        mode=config.model_preference or "fast",
                        timeout_s=config.bridge_timeout_s,
                    )
                    if not bridge_items or not bridge_items[0].success:
                        item = bridge_items[0] if bridge_items else None
                        raise RuntimeError((item.error_message if item else None) or "Gemini bridge returned empty breath chunks.")
                    chunks = _normalize_gemini_chunk_lines(bridge_items[0].answer)
                if not chunks:
                    raise RuntimeError("Gemini bridge returned empty breath chunks.")
            except Exception as exc:  # pylint: disable=broad-except
                error = str(exc)
                failed += 1
                chunks = _split_sentences_fallback(text)

            chunks = _merge_short_chunks(chunks, min_chars=max(20, config.min_chars), max_chars=max(80, config.max_chars))
            if not chunks:
                chunks = _split_sentences_fallback(text)

            for chunk in chunks:
                global_index += 1
                items.append({
                    "chunk_index": global_index,
                    "source_path": str(chapter_path.relative_to(self.repo_root)),
                    "text": chunk,
                    "char_count": len(chunk),
                    "pause_ms": _suggest_pause_ms(chunk),
                    "status": "fallback" if error else "success",
                })

            if progress_callback:
                progress_callback({
                    "stage": "breath_chunk",
                    "current": file_idx,
                    "total": len(files),
                    "message": f"Da chia chapter {chapter_path.name} thanh {len(chunks)} nhom",
                    "files_done": file_idx,
                    "preview_text": chunks[0][:220] if chunks else "",
                })

        manifest = {
            "project_id": project_id,
            "session_id": session_id,
            "updated_at": utc_now_iso(),
            "provider": config.provider,
            "summary": {
                "chapters": len(files),
                "chunks": len(items),
                "failed_chapters": failed,
            },
            "items": items,
        }
        manifest_path = session_dir / "breath_chunks_manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return manifest


def _suggest_pause_ms(chunk: str) -> int:
    text = chunk.rstrip()
    if not text:
        return 240
    if text.endswith(","):
        return 140
    if text.endswith(";") or text.endswith(":"):
        return 260
    if text.endswith(".") or text.endswith("!") or text.endswith("?"):
        return 340
    return 220

