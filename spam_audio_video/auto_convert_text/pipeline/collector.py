from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from auto_convert_text.adapters import adapter_for_url
from auto_convert_text.models.dto import ChapterRecord, ChapterRef, ConvertProject
from auto_convert_text.storage.project_store import ProjectStore, slugify


@dataclass
class CollectResult:
    project_id: str
    project_dir: str
    manifest_path: str
    session_id: str | None
    success: int
    failed: int
    chapters: list[ChapterRecord]


class Collector:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        self.store = ProjectStore(self.repo_root)

    @staticmethod
    def _replace_number_in_token(token: str, chapter_no: int) -> str:
        matches = list(re.finditer(r"\d+", token))
        if not matches:
            raise ValueError("Increment segment must contain a number.")
        last = matches[-1]
        return f"{token[:last.start()]}{chapter_no}{token[last.end():]}"

    @classmethod
    def _build_chapter_url(cls, sample_url: str, chapter_no: int, chapter_token: str | None = None) -> str:
        token = (chapter_token or "").strip()
        if token:
            if token not in sample_url:
                raise ValueError("Increment segment was not found in the chapter URL.")
            replacement = cls._replace_number_in_token(token, chapter_no)
            index = sample_url.rfind(token)
            return f"{sample_url[:index]}{replacement}{sample_url[index + len(token):]}"
        if "{chapter}" in sample_url:
            return sample_url.replace("{chapter}", str(chapter_no))
        matches = list(re.finditer(r"\d+", sample_url))
        if not matches:
            raise ValueError("Chapter URL must contain a number or the {chapter} marker.")
        last = matches[-1]
        return f"{sample_url[:last.start()]}{chapter_no}{sample_url[last.end():]}"

    @classmethod
    def _build_chapter_refs(
        cls,
        sample_url: str,
        start_chapter: int,
        chapter_count: int,
        chapter_token: str | None = None,
    ) -> list[ChapterRef]:
        refs: list[ChapterRef] = []
        for chapter_no in range(start_chapter, start_chapter + chapter_count):
            refs.append(
                ChapterRef(
                    index=chapter_no,
                    title=f"Chapter {chapter_no}",
                    url=cls._build_chapter_url(sample_url, chapter_no, chapter_token),
                )
            )
        return refs

    @staticmethod
    def _looks_like_story_page(url: str) -> bool:
        parsed = urlparse(url)
        path = (parsed.path or "").lower()
        return "/truyen/" in path and "/chuong-" not in path

    def _chapter_refs_from_story_page(
        self,
        story_url: str,
        start_chapter: int,
        chapter_count: int,
        chapter_token: str | None,
    ) -> list[ChapterRef]:
        adapter = adapter_for_url(story_url)
        refs = adapter.fetch_chapter_list(story_url)
        if not refs:
            return []

        wanted_start = int(start_chapter)
        wanted_end = wanted_start + int(chapter_count) - 1
        normalized: list[tuple[int, ChapterRef]] = []
        for idx, ref in enumerate(refs, start=1):
            chapter_no = adapter.normalize_chapter_no(ref.title) or adapter.normalize_chapter_no(ref.url) or idx
            normalized.append((int(chapter_no), ref))

        by_chapter_no = {no: ref for no, ref in normalized}
        if all(no in by_chapter_no for no in range(wanted_start, wanted_end + 1)):
            selected: list[ChapterRef] = []
            for chapter_no in range(wanted_start, wanted_end + 1):
                ref = by_chapter_no[chapter_no]
                selected.append(ChapterRef(index=chapter_no, title=ref.title, url=ref.url))
            return selected

        # Fallback for sites with non-contiguous numbers: treat `start_chapter` as list offset.
        offset = max(0, wanted_start - 1)
        window = refs[offset : offset + int(chapter_count)]
        selected = []
        for item_idx, ref in enumerate(window, start=wanted_start):
            selected.append(ChapterRef(index=item_idx, title=ref.title, url=ref.url))
        return selected

    @staticmethod
    def _default_project_name(chapter_url: str) -> str:
        parsed = urlparse(chapter_url)
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        if len(parts) >= 2 and re.search(r"\d+", parts[-1]):
            return parts[-2]
        return parts[-1] if parts else parsed.netloc.lower() or "project"

    def collect(
        self,
        story_url: str,
        start_chapter: int = 1,
        chapter_count: int = 10,
        project_name: str | None = None,
        project_id: str | None = None,
        chapter_token: str | None = None,
        chapter_urls: list[str] | None = None,
        apply_chapter_window: bool = False,
        session_id: str | None = None,
        progress_callback: Callable[[dict], None] | None = None,
    ) -> CollectResult:
        if not story_url.strip():
            raise ValueError("Story URL or chapter sample URL is required.")
        start_chapter = max(1, int(start_chapter))
        chapter_count = max(1, min(1000, int(chapter_count)))

        parsed = urlparse(story_url)
        domain = parsed.netloc.lower() or "generic"
        name = project_name.strip() if project_name else self._default_project_name(story_url)
        resolved_project_id = slugify(project_id or name)
        resolved_session_id = slugify(session_id or self.store.session_id(start_chapter, chapter_count))

        adapter = adapter_for_url(story_url)
        selected_refs: list[ChapterRef] = []
        if chapter_urls:
            cleaned = [item.strip() for item in chapter_urls if isinstance(item, str) and item.strip()]
            window = cleaned
            if apply_chapter_window:
                offset = max(0, start_chapter - 1)
                window = cleaned[offset : offset + chapter_count]
            selected_refs = [
                ChapterRef(index=start_chapter + idx, title=f"Chapter {start_chapter + idx}", url=url)
                for idx, url in enumerate(window)
            ]
        else:
            use_story_list = self._looks_like_story_page(story_url) or not (chapter_token or "").strip()
            if use_story_list:
                try:
                    selected_refs = self._chapter_refs_from_story_page(story_url, start_chapter, chapter_count, chapter_token)
                except Exception:
                    selected_refs = []
            if not selected_refs:
                selected_refs = self._build_chapter_refs(story_url, start_chapter, chapter_count, chapter_token)

        # Do not overwrite project-level chapter URL list during collect.
        # URL master list is managed explicitly from the URLs tab.

        project = ConvertProject(
            project_id=resolved_project_id,
            name=name,
            story_url=story_url,
            domain=domain,
            start_chapter=start_chapter,
            chapter_count=len(selected_refs),
            status="running",
        )
        self.store.write_project(project, resolved_session_id)

        chapters: list[ChapterRecord] = []
        for offset, ref in enumerate(selected_refs, start=start_chapter):
            if progress_callback:
                progress_callback({
                    "stage": "collect",
                    "current": offset - start_chapter,
                    "total": len(selected_refs),
                    "chapter": offset,
                    "message": f"Đang thu thập chapter {offset}",
                    "preview_text": ref.url,
                })
            last_error: Exception | None = None
            preview = ""
            for attempt in range(1, 4):
                try:
                    content = adapter.fetch_chapter(ref.url)
                    text = content.text.strip()
                    if len(text) < 20:
                        raise RuntimeError("Fetched chapter text is too short.")
                    path = self.store.write_chapter_text(resolved_project_id, offset, text, resolved_session_id)
                    chapters.append(
                        ChapterRecord(
                            chapter_no=offset,
                            title=content.title or ref.title,
                            source_url=ref.url,
                            status="success",
                            raw_text_path=str(path.relative_to(self.repo_root)),
                        )
                    )
                    preview = " ".join(text.split())[:220]
                    last_error = None
                    break
                except Exception as exc:  # pylint: disable=broad-except
                    last_error = exc
                    if attempt < 3:
                        time.sleep(0.5 * attempt)
            if last_error is not None:
                chapters.append(
                    ChapterRecord(
                        chapter_no=offset,
                        title=ref.title,
                        source_url=ref.url,
                        status="failed",
                        error=str(last_error),
                    )
                )
            if progress_callback:
                progress_callback({
                    "stage": "collect",
                    "current": offset - start_chapter + 1,
                    "total": len(selected_refs),
                    "chapter": offset,
                    "message": f"Đã thu thập chapter {offset}" if last_error is None else f"Lỗi chapter {offset}",
                    "preview_text": preview if last_error is None else str(last_error),
                })

        project.status = "completed" if all(item.status == "success" for item in chapters) else "partial"
        self.store.write_project(project, resolved_session_id)
        manifest_path = self.store.write_manifest(resolved_project_id, project, chapters, resolved_session_id)
        return CollectResult(
            project_id=resolved_project_id,
            project_dir=str(self.store.session_dir(resolved_project_id, resolved_session_id).relative_to(self.repo_root)),
            manifest_path=str(manifest_path.relative_to(self.repo_root)),
            session_id=resolved_session_id,
            success=sum(1 for item in chapters if item.status == "success"),
            failed=sum(1 for item in chapters if item.status == "failed"),
            chapters=chapters,
        )

    def crawl_chapter_urls(
        self,
        story_url: str,
        start_chapter: int = 1,
        chapter_count: int = 10,
        chapter_token: str | None = None,
    ) -> list[ChapterRef]:
        start_chapter = max(1, int(start_chapter))
        chapter_count = max(1, min(10000, int(chapter_count)))
        refs: list[ChapterRef] = []
        use_story_list = self._looks_like_story_page(story_url) or not (chapter_token or "").strip()
        if use_story_list:
            try:
                refs = self._chapter_refs_from_story_page(story_url, start_chapter, chapter_count, chapter_token)
            except Exception:
                refs = []
        if not refs:
            refs = self._build_chapter_refs(story_url, start_chapter, chapter_count, chapter_token)
        return refs
