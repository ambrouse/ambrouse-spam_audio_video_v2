from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from auto_convert_text.models.dto import ChapterContent, ChapterRef

from .base import (
    AnchorParser,
    BaseAdapter,
    dedupe_chapters,
    extract_next_data_chapters,
    extract_title,
    html_to_text,
    normalize_spaces,
)


class ApptruyenchuProAdapter(BaseAdapter):
    domain = "apptruyenchu.pro"
    chapter_keywords = ("chuong", "chapter", "chap")

    def fetch_chapter_list(self, story_url: str) -> list[ChapterRef]:
        raw_html = self.fetch_html(story_url)
        from_next_data = extract_next_data_chapters(story_url, raw_html)
        if from_next_data:
            filtered = [ref for ref in from_next_data if "/chuong-" in ref.url.lower()]
            if filtered:
                return dedupe_chapters(filtered)

        parser = AnchorParser()
        parser.feed(raw_html)
        parsed_story = urlparse(story_url)
        host = parsed_story.netloc.lower()
        base_story = story_url.rstrip("/")
        refs: list[ChapterRef] = []

        for href, text in parser.anchors:
            absolute = urljoin(story_url, href)
            parsed = urlparse(absolute)
            if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() != host:
                continue
            absolute_norm = absolute.split("#", 1)[0].rstrip("/")
            if "/chuong-" not in absolute_norm.lower():
                continue
            if not absolute_norm.startswith(base_story):
                continue
            title = normalize_spaces(text) or absolute_norm.rsplit("/", 1)[-1].replace("-", " ")
            refs.append(ChapterRef(index=len(refs) + 1, title=title[:180], url=absolute_norm))

        deduped = dedupe_chapters(refs)
        if len(deduped) >= 5:
            return deduped

        dynamic_refs = self._fetch_chapter_list_playwright(story_url)
        if dynamic_refs:
            deduped_dynamic = dedupe_chapters(dynamic_refs)
            if len(deduped_dynamic) >= 5:
                return deduped_dynamic

        # Fallback for this site: walk chapter-by-chapter from first chapter link.
        chapter_count_hint = self._extract_chapter_count_hint(raw_html)
        walked = self._walk_chapters_from_first(story_url, deduped, chapter_count_hint)
        if walked:
            return walked
        return deduped

    @staticmethod
    def _extract_chapter_count_hint(raw_html: str) -> int | None:
        # Example block contains: "808" + "Chương"
        match = re.search(r'(\d{1,6})\s*</[^>]*>\s*<[^>]*>\s*Chương', raw_html, flags=re.I)
        if match:
            try:
                return int(match.group(1))
            except Exception:
                return None
        # Loose text fallback
        match2 = re.search(r'(\d{1,6})\s+Chương', raw_html, flags=re.I)
        if match2:
            try:
                return int(match2.group(1))
            except Exception:
                return None
        return None

    def _walk_chapters_from_first(
        self,
        story_url: str,
        seed_refs: list[ChapterRef],
        chapter_count_hint: int | None,
    ) -> list[ChapterRef]:
        if not seed_refs:
            return []
        first = None
        for ref in seed_refs:
            if re.search(r"/chuong-1([-/]|$)", ref.url.lower()):
                first = ref.url
                break
        if not first:
            first = seed_refs[0].url

        max_steps = chapter_count_hint if chapter_count_hint and chapter_count_hint > 0 else 5000
        max_steps = min(max_steps, 15000)
        seen: set[str] = set()
        refs: list[ChapterRef] = []
        current = first
        story_prefix = story_url.rstrip("/")

        for idx in range(1, max_steps + 1):
            normalized = current.split("#", 1)[0].rstrip("/")
            if normalized in seen:
                break
            seen.add(normalized)
            refs.append(ChapterRef(index=idx, title=f"Chapter {idx}", url=normalized))

            try:
                html = self.fetch_html(normalized)
            except Exception:
                break

            parser = AnchorParser()
            parser.feed(html)
            next_url = ""
            for href, text in parser.anchors:
                absolute = urljoin(normalized, href).split("#", 1)[0].rstrip("/")
                if not absolute.startswith(story_prefix):
                    continue
                if "/chuong-" not in absolute.lower():
                    continue
                label = (text or "").lower()
                if "sau" in label or "next" in label:
                    next_url = absolute
                    break
            if not next_url:
                # Fallback: choose the first same-story chapter URL that is not current.
                for href, _text in parser.anchors:
                    absolute = urljoin(normalized, href).split("#", 1)[0].rstrip("/")
                    if absolute != normalized and absolute.startswith(story_prefix) and "/chuong-" in absolute.lower():
                        next_url = absolute
                        break
            if not next_url:
                break
            current = next_url

        return dedupe_chapters(refs)

    def _fetch_chapter_list_playwright(self, story_url: str) -> list[ChapterRef]:
        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            return []

        refs: list[ChapterRef] = []
        parsed_story = urlparse(story_url)
        host = parsed_story.netloc.lower()
        base_story = story_url.rstrip("/")
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(story_url, wait_until="networkidle", timeout=45000)
                # Ensure chapter section is in viewport and give the app time to hydrate chapter list.
                page.mouse.wheel(0, 2400)
                page.wait_for_timeout(2200)
                links = page.eval_on_selector_all(
                    "a[href*='/chuong-']",
                    "els => els.map(el => ({href: el.getAttribute('href') || '', text: (el.textContent || '').trim()}))",
                )
                browser.close()
        except Exception:
            return []

        for item in links or []:
            href = item.get("href") or ""
            text = item.get("text") or ""
            absolute = urljoin(story_url, href)
            parsed = urlparse(absolute)
            if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() != host:
                continue
            absolute_norm = absolute.split("#", 1)[0].rstrip("/")
            if "/chuong-" not in absolute_norm.lower():
                continue
            if not absolute_norm.startswith(base_story):
                continue
            title = normalize_spaces(text) or absolute_norm.rsplit("/", 1)[-1].replace("-", " ")
            refs.append(ChapterRef(index=len(refs) + 1, title=title[:180], url=absolute_norm))
        return refs

    def fetch_chapter(self, chapter_url: str) -> ChapterContent:
        raw_html = self.fetch_html(chapter_url)
        title = extract_title(raw_html, fallback=chapter_url)

        # Prefer dedicated chapter content blocks to avoid navbar/comments noise.
        content_patterns = [
            r'<div[^>]+class="[^"]*chapter-content[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]+id="[^"]*chapter-content[^"]*"[^>]*>(.*?)</div>',
            r'<article[^>]*>(.*?)</article>',
        ]
        text = ""
        for pattern in content_patterns:
            match = re.search(pattern, raw_html, flags=re.I | re.S)
            if not match:
                continue
            candidate = html_to_text(match.group(1))
            if len(candidate) > 80:
                text = candidate
                break
        if not text:
            text = html_to_text(raw_html)
        return ChapterContent(title=title, url=chapter_url, text=text)
