from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Callable

from auto_convert_text.models.dto import utc_now_iso
from auto_convert_text.storage.project_store import ProjectStore


def strip_prompt_scaffold(text: str) -> str:
    raw = (text or "").replace("\r\n", "\n")
    lines = raw.split("\n")
    marker_patterns = [
        re.compile(r"^\s*b[aạ]n l[aà]\b", re.I),
        re.compile(r"^\s*y[eê]u c[aầ]u\b", re.I),
        re.compile(r"^\s*n[oộ]i dung chapter\b", re.I),
        re.compile(r"^\s*noi dung chapter\b", re.I),
    ]
    for idx, line in enumerate(lines):
        if any(pattern.search(line) for pattern in marker_patterns):
            return "\n".join(lines[idx + 1 :]).strip()
    return raw.strip()


def clean_for_audio(text: str) -> str:
    text = strip_prompt_scaffold(text)
    text = unicodedata.normalize("NFC", text or "")
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    replacements = {
        "?": ".",
        "!": ".",
        ":": ".",
        "...": ".",
        "…": ".",
        "â€¦": ".",
        "-": ",",
        "–": ",",
        "—": ",",
        "â€“": ",",
        "â€”": ",",
        "(": ",",
        ")": ",",
        "[": ",",
        "]": ",",
        "{": ",",
        "}": ",",
        '"': " ",
        "'": " ",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)

    out: list[str] = []
    for ch in text:
        if ch in {".", ",", ";", "\n"}:
            out.append(ch)
            continue
        if ch.isspace():
            out.append(" ")
            continue
        if unicodedata.category(ch)[0] in {"L", "N"}:
            out.append(ch)

    cleaned = "".join(out)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r" *\n+ *", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"\s+([.,;])", r"\1", cleaned)
    cleaned = re.sub(r"([.,;])\s*([.,;])+", r"\2", cleaned)
    cleaned = re.sub(r",\s*\.", ".", cleaned)
    cleaned = re.sub(r";\s*\.", ".", cleaned)
    cleaned = re.sub(r"\.\s*,", ".", cleaned)
    cleaned = cleaned.strip(" ,.;\n")
    if cleaned and cleaned[-1] not in ".,;":
        cleaned += "."
    return cleaned


class AudioCleaner:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        self.store = ProjectStore(self.repo_root)

    def run(
        self,
        project_id: str,
        session_id: str | None = None,
        progress_callback: Callable[[dict], None] | None = None,
    ) -> dict:
        project_dir = self.store.session_dir(project_id, session_id)
        rewritten_dir = project_dir / "chapters_text" / "rewritten"
        raw_dir = project_dir / "chapters_text" / "raw"
        source_dir = rewritten_dir if any(rewritten_dir.glob("chapter_*.txt")) else raw_dir
        output_dir = project_dir / "chapters_text" / "audio_clean"
        output_dir.mkdir(parents=True, exist_ok=True)
        files = sorted(source_dir.glob("chapter_*.txt"))
        if not files:
            raise FileNotFoundError(f"No source chapter files found for audio clean: {source_dir}")

        items: list[dict] = []
        for index, path in enumerate(files, start=1):
            original = path.read_text(encoding="utf-8", errors="replace")
            cleaned = clean_for_audio(original)
            out_path = output_dir / path.name
            status = "success" if cleaned else "failed"
            error = None if cleaned else "Cleaned text is empty."
            if cleaned:
                out_path.write_text(cleaned + "\n", encoding="utf-8")
            items.append({
                "source_path": str(path.relative_to(self.repo_root)),
                "audio_clean_path": str(out_path.relative_to(self.repo_root)) if cleaned else None,
                "status": status,
                "error": error,
                "char_count": len(cleaned),
            })
            if progress_callback:
                progress_callback({
                    "stage": "audio_clean",
                    "current": index,
                    "total": len(files),
                    "message": f"Cleaned {path.name}" if cleaned else f"Clean failed {path.name}",
                    "status": status,
                    "files_done": index,
                })

        manifest = {
            "project_id": project_id,
            "session_id": session_id,
            "updated_at": utc_now_iso(),
            "summary": {
                "total": len(items),
                "success": sum(1 for item in items if item["status"] == "success"),
                "failed": sum(1 for item in items if item["status"] == "failed"),
            },
            "items": items,
        }
        manifest_path = project_dir / "audio_clean_manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return manifest
