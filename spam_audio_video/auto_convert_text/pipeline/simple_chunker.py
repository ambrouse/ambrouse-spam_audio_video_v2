from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from auto_convert_text.models.dto import utc_now_iso
from auto_convert_text.storage.project_store import ProjectStore


@dataclass
class TextPiece:
    text: str
    words: int
    boundary: str


def _word_count(text: str) -> int:
    return len(re.findall(r"\S+", text or ""))


def _normalize_piece(text: str) -> str:
    return " ".join((text or "").split()).strip()


def _sanitize_chunk_text(text: str) -> str:
    compact = _normalize_piece((text or "").replace(",", " "))
    compact = re.sub(r"\s+\.", ".", compact)
    compact = re.sub(r"\.+", ".", compact)
    compact = compact.strip(" .")
    return f"{compact}." if compact else ""


def _split_pause_pieces(text: str) -> list[TextPiece]:
    compact = _normalize_piece((text or "").replace(",", " "))
    if not compact:
        return []
    pieces: list[TextPiece] = []
    start = 0
    for match in re.finditer(r"\.", compact):
        end = match.end()
        piece = _sanitize_chunk_text(compact[start:end])
        if piece:
            pieces.append(TextPiece(piece, _word_count(piece), "sentence"))
        start = end
    tail = _sanitize_chunk_text(compact[start:])
    if tail:
        pieces.append(TextPiece(tail, _word_count(tail), "tail"))
    return pieces


def _split_long_piece(piece: TextPiece, max_words: int) -> list[TextPiece]:
    if piece.words <= max_words:
        return [piece]
    words = piece.text.split()
    chunks: list[TextPiece] = []
    start = 0
    while start < len(words):
        end = min(len(words), start + max_words)
        chunk_words = words[start:end]
        text = _sanitize_chunk_text(" ".join(chunk_words))
        chunks.append(TextPiece(text, _word_count(text), "word_limit"))
        start = end
    return chunks


class SimpleChunker:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        self.store = ProjectStore(self.repo_root)

    def run(
        self,
        project_id: str,
        session_id: str | None = None,
        min_words: int = 16,
        max_words: int = 64,
        clear_old: bool = True,
        progress_callback: Callable[[dict], None] | None = None,
    ) -> dict:
        requested_min_words = int(min_words)
        min_words = max(30, requested_min_words)
        max_words = max(min_words, int(max_words))
        session_dir = self.store.session_dir(project_id, session_id)
        source_dir = session_dir / "chapters_text" / "audio_clean"
        chunk_dir = session_dir / "chapters_text" / "chunks"
        tts_dir = session_dir / "tts_inputs"
        chunk_dir.mkdir(parents=True, exist_ok=True)
        tts_dir.mkdir(parents=True, exist_ok=True)

        chapter_files = sorted(source_dir.glob("chapter_*.txt"))
        if not chapter_files:
            raise FileNotFoundError(f"No audio-clean chapter files found: {source_dir}")

        if clear_old:
            for old in chunk_dir.glob("chunk_*.txt"):
                old.unlink(missing_ok=True)
            for old in tts_dir.glob("text_*.txt"):
                old.unlink(missing_ok=True)

        chunks: list[dict] = []
        current_parts: list[TextPiece] = []
        current_words = 0

        def flush_chunk(reason: str) -> None:
            nonlocal current_parts, current_words
            if not current_parts:
                return
            text = _sanitize_chunk_text(" ".join(part.text for part in current_parts))
            if text:
                chunks.append({
                    "text": text,
                    "word_count": _word_count(text),
                    "boundary_reason": reason,
                    "punctuation_end": ".",
                })
            current_parts = []
            current_words = 0

        def add_piece(piece: TextPiece) -> None:
            nonlocal current_parts, current_words
            for part in _split_long_piece(piece, max_words):
                if part.words > max_words:
                    flush_chunk("before_oversize")
                    chunks.append({
                        "text": part.text,
                        "word_count": part.words,
                        "boundary_reason": "oversize",
                        "punctuation_end": ".",
                    })
                    continue
                if not current_parts:
                    current_parts = [part]
                    current_words = part.words
                    if current_words >= max_words:
                        flush_chunk("max_words")
                    continue
                if current_words < min_words or current_words + part.words <= max_words:
                    if current_words + part.words <= max_words:
                        current_parts.append(part)
                        current_words += part.words
                        if current_words >= min_words and part.boundary == "sentence":
                            flush_chunk(part.boundary)
                        continue
                flush_chunk("max_words")
                current_parts = [part]
                current_words = part.words
                if current_words >= min_words and part.boundary == "sentence":
                    flush_chunk(part.boundary)

        for file_idx, chapter_path in enumerate(chapter_files, start=1):
            text = chapter_path.read_text(encoding="utf-8", errors="replace").strip()
            if text:
                for piece in _split_pause_pieces(text):
                    add_piece(piece)
            if progress_callback:
                progress_callback({
                    "stage": "chunk",
                    "current": file_idx,
                    "total": len(chapter_files),
                    "files_done": file_idx,
                    "message": f"Chunked {chapter_path.name}",
                })

        flush_chunk("end")

        items: list[dict] = []
        for idx, chunk in enumerate(chunks, start=1):
            chunk_text = str(chunk["text"]).strip()
            chunk_text = _sanitize_chunk_text(chunk_text)
            chunk_name = f"chunk_{idx:04d}.txt"
            tts_name = f"text_{idx:04d}.txt"
            chunk_path = chunk_dir / chunk_name
            tts_path = tts_dir / tts_name
            chunk_path.write_text(chunk_text + "\n", encoding="utf-8")
            tts_path.write_text(chunk_text + "\n", encoding="utf-8")
            items.append({
                "chunk_index": idx,
                "chunk_path": str(chunk_path.relative_to(self.repo_root)),
                "tts_input_path": str(tts_path.relative_to(self.repo_root)),
                "word_count": _word_count(chunk_text),
                "char_count": len(chunk_text),
                "boundary_reason": chunk.get("boundary_reason") or "",
                "punctuation_end": chunk.get("punctuation_end") or "",
            })

        manifest = {
            "project_id": project_id,
            "session_id": session_id,
            "updated_at": utc_now_iso(),
            "requested_min_words": requested_min_words,
            "min_words": min_words,
            "max_words": max_words,
            "punctuation_policy": "period_only",
            "summary": {
                "chapters": len(chapter_files),
                "chunks": len(items),
                "tts_inputs": len(items),
                "below_min_words": sum(1 for item in items if int(item["word_count"]) < min_words),
                "above_max_words": sum(1 for item in items if int(item["word_count"]) > max_words),
                "non_period_endings": sum(1 for item in items if item.get("punctuation_end") != "."),
                "comma_violations": sum(1 for chunk in chunks if "," in str(chunk.get("text") or "")),
            },
            "items": items,
        }
        manifest_path = session_dir / "chunks_manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return manifest
