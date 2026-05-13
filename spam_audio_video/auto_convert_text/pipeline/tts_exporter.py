from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable

from auto_convert_text.models.dto import utc_now_iso
from auto_convert_text.storage.project_store import ProjectStore


class TtsExporter:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        self.store = ProjectStore(self.repo_root)
        self.tts_text_dir = self.repo_root / "auto_text_to_voice" / "text"

    def run(
        self,
        project_id: str,
        clear_old: bool = False,
        session_id: str | None = None,
        progress_callback: Callable[[dict], None] | None = None,
    ) -> dict:
        project_dir = self.store.session_dir(project_id, session_id)
        source_dir = project_dir / "chapters_text" / "audio_clean"
        chapters = sorted(source_dir.glob("chapter_*.txt"))
        if not chapters:
            raise FileNotFoundError(f"No audio-clean chapter files found: {source_dir}")

        session_tts_dir = project_dir / "tts_inputs"
        session_tts_dir.mkdir(parents=True, exist_ok=True)

        removed = 0
        if clear_old:
            for path in session_tts_dir.glob("*.txt"):
                path.unlink(missing_ok=True)
                removed += 1

        breath_items = _load_breath_manifest(project_dir)
        total_sentences = len(breath_items)
        if total_sentences == 0:
            for chapter_path in chapters:
                text = chapter_path.read_text(encoding="utf-8", errors="replace").strip()
                if text:
                    total_sentences += len(_split_into_sentences(text))

        items: list[dict] = []
        sentence_index = 0
        if breath_items:
            for breath_item in breath_items:
                sentence_index += 1
                session_target = session_tts_dir / f"text_{sentence_index:04d}.txt"
                sentence = breath_item["text"]
                session_target.write_text(_sanitize_tts_input_text(sentence), encoding="utf-8")
                items.append({
                    "source_path": str(breath_item.get("source_path") or ""),
                    "exported_path": str(session_target.relative_to(self.repo_root)),
                    "session_tts_input_path": str(session_target.relative_to(self.repo_root)),
                    "char_count": len(sentence),
                    "pause_ms": int(breath_item.get("pause_ms", 220)),
                    "status": "success",
                })
                if progress_callback:
                    progress_callback({
                        "stage": "export",
                        "current": sentence_index,
                        "total": max(1, total_sentences),
                        "message": f"Da xuat TTS sentence {sentence_index}/{max(1, total_sentences)}",
                        "files_done": sentence_index,
                        "preview_text": sentence[:220],
                    })
        else:
            for chapter_path in chapters:
                text = chapter_path.read_text(encoding="utf-8", errors="replace").strip()
                if not text:
                    continue
                for sentence in _split_into_sentences(text):
                    sentence_index += 1
                    session_target = session_tts_dir / f"text_{sentence_index:04d}.txt"
                    session_target.write_text(_sanitize_tts_input_text(sentence), encoding="utf-8")
                    items.append({
                        "source_path": str(chapter_path.relative_to(self.repo_root)),
                        "exported_path": str(session_target.relative_to(self.repo_root)),
                        "session_tts_input_path": str(session_target.relative_to(self.repo_root)),
                        "char_count": len(sentence),
                        "pause_ms": _suggest_pause_ms(sentence),
                        "status": "success",
                    })
                    if progress_callback:
                        progress_callback({
                            "stage": "export",
                            "current": sentence_index,
                            "total": max(1, total_sentences),
                            "message": f"Da xuat TTS sentence {sentence_index}/{max(1, total_sentences)}",
                            "files_done": sentence_index,
                            "preview_text": sentence[:220],
                        })

        manifest = {
            "project_id": project_id,
            "session_id": session_id,
            "updated_at": utc_now_iso(),
            "clear_old": clear_old,
            "removed_old_files": removed,
            "summary": {
                "exported": len(items),
                "used_breath_manifest": bool(breath_items),
            },
            "items": items,
        }
        manifest_path = project_dir / "tts_export_manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return manifest


def _split_into_sentences(text: str) -> list[str]:
    compact = " ".join((text or "").split())
    if not compact:
        return []

    parts = re.split(r"(?<=\.)\s+", compact)
    out: list[str] = []
    for part in parts:
        piece = part.strip(" ,")
        if not piece:
            continue
        out.append(piece)
    return out


def _suggest_pause_ms(chunk: str) -> int:
    text = chunk.rstrip()
    if not text:
        return 240
    if text.endswith(","):
        return 140
    if text.endswith("."):
        return 340
    return 220


def _sanitize_tts_input_text(text: str) -> str:
    text = (text or "").replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    out: list[str] = []
    for ch in text:
        if ch in {".", ","} or ch.isspace() or ch.isalnum():
            out.append(ch)
    compact = " ".join("".join(out).split()).strip(" ,.")
    if compact and compact[-1] not in ".,":
        compact += "."
    return compact


def _load_breath_manifest(project_dir: Path) -> list[dict]:
    manifest_path = project_dir / "breath_chunks_manifest.json"
    if not manifest_path.exists():
        return []
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    items = payload.get("items") or []
    clean_items: list[dict] = []
    for item in items:
        text = " ".join(str(item.get("text", "")).split()).strip()
        if not text:
            continue
        clean_items.append({
            "source_path": item.get("source_path"),
            "text": text,
            "pause_ms": int(item.get("pause_ms", 220)),
        })
    return clean_items
