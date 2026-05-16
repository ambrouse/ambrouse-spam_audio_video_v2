from __future__ import annotations

import os
import re
import subprocess
import sys
import time
import urllib.request
import urllib.error
import json
from pathlib import Path
from typing import Callable
from urllib.parse import unquote, urljoin, urlparse

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from auto_convert_text.pipeline.collector import Collector
from auto_convert_text.pipeline.audio_cleaner import AudioCleaner
from auto_convert_text.pipeline.browser_bridge_client import DEFAULT_BRIDGE_BASE_URL, BrowserBridgeClient
from auto_convert_text.pipeline.gemini_rewriter import DEFAULT_REWRITE_PROMPT, GeminiRewriter, RewriteConfig
from auto_convert_text.pipeline.simple_chunker import SimpleChunker
from auto_convert_text.models.dto import ConvertProject
from auto_convert_text.storage.shared_project_registry import SharedProjectRegistry
from auto_convert_text.storage.project_store import ProjectStore
from auto_convert_text.storage.project_store import slugify

DEFAULT_TTS_MIN_WORDS = 30
DEFAULT_TTS_MAX_WORDS = 64
DEFAULT_LLM_BASE_URL = ""
DEFAULT_LLM_MODEL = "gemini/gemini-3-flash-preview"
DEFAULT_STORY_CONTEXT = (
    "Truyen audio tieng Viet, phong cach ke chuyen gan gui, ro boi canh, ro nhan vat, "
    "giu mach cam xuc xuyen suot tung chuong."
)


class ConvertPipelineService:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        self.collector = Collector(self.repo_root)
        self.rewriter = GeminiRewriter(self.repo_root)
        self.audio_cleaner = AudioCleaner(self.repo_root)
        self.simple_chunker = SimpleChunker(self.repo_root)
        self.store = ProjectStore(self.repo_root)
        self.store.migrate_legacy_projects()
        self.registry = SharedProjectRegistry(self.repo_root)
        self.chrome_pool_state_path = self.repo_root / "project_registry" / "chrome_pool_state.json"
        self.prompt_default_dir = self.repo_root / "projects_workspace" / "prompt_default"
        self.prompt_default_path = self.prompt_default_dir / "rewrite_prompt.json"
        self.story_context_template_path = self.prompt_default_dir / "story_context_template.txt"
        self.llm_default_path = self.prompt_default_dir / "llm_default.json"

    def collect(
        self,
        story_url: str,
        start_chapter: int,
        chapter_count: int,
        project_name: str | None = None,
        project_id: str | None = None,
        chapter_token: str | None = None,
        chapter_urls: list[str] | None = None,
        apply_chapter_window: bool = False,
        session_id: str | None = None,
        progress_callback: Callable[[dict], None] | None = None,
    ) -> dict:
        if (not chapter_urls) and project_id:
            chapter_urls = self.store.read_chapter_urls(project_id)
        result = self.collector.collect(
            story_url=story_url,
            start_chapter=start_chapter,
            chapter_count=chapter_count,
            project_name=project_name,
            project_id=project_id,
            chapter_token=chapter_token,
            chapter_urls=chapter_urls,
            apply_chapter_window=apply_chapter_window,
            session_id=session_id,
            progress_callback=progress_callback,
        )
        session_patch = {
            "name": project_name or result.project_id,
            "status": "convert_collected" if result.failed == 0 else "convert_partial",
            "chapter_start": start_chapter,
            "chapter_end": start_chapter + chapter_count - 1,
            "source_url": story_url,
            "chapter_token": chapter_token or "",
            "convert": {
                "project_dir": result.project_dir,
                "manifest_path": result.manifest_path,
                "raw_success": result.success,
                "raw_failed": result.failed,
                "start_chapter": start_chapter,
                "chapter_count": chapter_count,
            },
        }
        self.registry.upsert_project(
            result.project_id,
            {
                "name": project_name or result.project_id,
                "status": "convert_collected" if result.failed == 0 else "convert_partial",
                "source_url": story_url,
                "chapter_token": chapter_token or "",
                "convert": {
                    "project_dir": result.project_dir,
                    "manifest_path": result.manifest_path,
                    "raw_success": result.success,
                    "raw_failed": result.failed,
                    "start_chapter": start_chapter,
                    "chapter_count": chapter_count,
                },
            },
        )
        if result.session_id:
            self.registry.upsert_session(result.project_id, result.session_id, session_patch)
        return {
            "success": result.failed == 0,
            "message": "Collected chapter text files." if result.failed == 0 else "Collected with failed chapters.",
            "project_id": result.project_id,
            "session_id": result.session_id,
            "project_dir": result.project_dir,
            "manifest_path": result.manifest_path,
            "success_count": result.success,
            "failed_count": result.failed,
            "chapters": [chapter.__dict__ for chapter in result.chapters],
        }

    def get_project_chapter_urls(self, project_id: str) -> dict:
        clean_project_id = slugify(project_id)
        urls = self._sort_chapter_url_strings(self._dedupe_urls(self.store.read_chapter_urls(clean_project_id)))
        return {
            "project_id": clean_project_id,
            "count": len(urls),
            "urls": urls,
        }

    def save_project_chapter_urls(self, project_id: str, urls: list[str], session_id: str | None = None) -> dict:
        clean_project_id = slugify(project_id)
        deduped = self._sort_chapter_url_strings(self._dedupe_urls(urls))
        _ = session_id
        saved = self.store.write_chapter_urls(clean_project_id, session_id=None, urls=deduped)
        return {
            "success": True,
            "project_id": clean_project_id,
            "count": int(saved.get("count", 0)),
        }

    @staticmethod
    def _normalize_url(url: str) -> str:
        text = str(url or "").strip()
        if not text:
            return ""
        parsed = urlparse(text)
        if not parsed.scheme or not parsed.netloc:
            return text.rstrip("/")
        netloc = parsed.netloc.lower()
        path = parsed.path.rstrip("/") or "/"
        normalized = f"{parsed.scheme.lower()}://{netloc}{path}"
        if parsed.query:
            normalized = f"{normalized}?{parsed.query}"
        return normalized

    def _dedupe_urls(self, urls: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for item in urls or []:
            normalized = self._normalize_url(item)
            key = normalized.split("#", 1)[0]
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(normalized)
        return result

    @classmethod
    def _sort_chapter_url_strings(cls, urls: list[str]) -> list[str]:
        return [item["url"] for item in cls._sort_chapter_urls(urls)]

    def list_project_chapter_items(self, project_id: str) -> dict:
        payload = self.get_project_chapter_urls(project_id)
        rows = []
        for idx, url in enumerate(payload.get("urls", [])):
            rows.append({"index": idx, "url": url, "normalized": self._normalize_url(url)})
        return {"project_id": payload["project_id"], "count": len(rows), "items": rows}

    def add_project_chapter_urls(self, project_id: str, urls: list[str], session_id: str | None = None) -> dict:
        clean_project_id = slugify(project_id)
        existing = self.store.read_chapter_urls(clean_project_id)
        merged = self._sort_chapter_url_strings(self._dedupe_urls([*existing, *(urls or [])]))
        _ = session_id
        saved = self.store.write_chapter_urls(clean_project_id, session_id=None, urls=merged)
        return {"success": True, "project_id": clean_project_id, "count": int(saved.get("count", 0))}

    def update_project_chapter_item(self, project_id: str, index: int, url: str, session_id: str | None = None) -> dict:
        clean_project_id = slugify(project_id)
        urls = self.store.read_chapter_urls(clean_project_id)
        if index < 0 or index >= len(urls):
            raise ValueError("chapter index out of range")
        urls[index] = url
        deduped = self._sort_chapter_url_strings(self._dedupe_urls(urls))
        _ = session_id
        saved = self.store.write_chapter_urls(clean_project_id, session_id=None, urls=deduped)
        return {"success": True, "project_id": clean_project_id, "count": int(saved.get("count", 0))}

    def delete_project_chapter_item(self, project_id: str, index: int, session_id: str | None = None) -> dict:
        clean_project_id = slugify(project_id)
        urls = self.store.read_chapter_urls(clean_project_id)
        if index < 0 or index >= len(urls):
            raise ValueError("chapter index out of range")
        del urls[index]
        deduped = self._sort_chapter_url_strings(self._dedupe_urls(urls))
        _ = session_id
        saved = self.store.write_chapter_urls(clean_project_id, session_id=None, urls=deduped)
        return {"success": True, "project_id": clean_project_id, "count": int(saved.get("count", 0))}

    def clear_project_chapter_urls(self, project_id: str) -> dict:
        clean_project_id = slugify(project_id)
        removed = self.store.clear_chapter_urls(clean_project_id)
        return {
            "success": True,
            "project_id": clean_project_id,
            "removed": int(removed.get("removed", 0)),
        }

    def get_project_rewrite_prompt(self, project_id: str) -> dict:
        clean_project_id = slugify(project_id)
        data = self.store.read_rewrite_prompt_config(clean_project_id)
        return {
            "success": True,
            "project_id": clean_project_id,
            "story_context": data.get("story_context", ""),
            "rewrite_prompt": data.get("rewrite_prompt", ""),
            "source": data.get("source", "none"),
        }

    def get_session_rewrite_prompt(self, project_id: str, session_id: str | None = None) -> dict:
        clean_project_id = slugify(project_id)
        clean_session_id = slugify(session_id) if session_id else None
        data = self.store.read_rewrite_prompt_config(clean_project_id, session_id=clean_session_id)
        return {
            "success": True,
            "project_id": clean_project_id,
            "session_id": clean_session_id,
            "story_context": data.get("story_context", ""),
            "rewrite_prompt": data.get("rewrite_prompt", ""),
            "source": data.get("source", "none"),
        }

    def save_project_rewrite_prompt(
        self,
        project_id: str,
        story_context: str,
        rewrite_prompt: str,
        session_id: str | None = None,
    ) -> dict:
        clean_project_id = slugify(project_id)
        clean_session_id = slugify(session_id) if session_id else None
        data = self.store.write_rewrite_prompt_config(
            clean_project_id,
            story_context=story_context,
            rewrite_prompt=rewrite_prompt,
            session_id=clean_session_id,
        )
        return {
            "success": True,
            "project_id": clean_project_id,
            "session_id": clean_session_id,
            "story_context": data.get("story_context", ""),
            "rewrite_prompt": data.get("rewrite_prompt", ""),
        }

    def clear_project_rewrite_prompt(self, project_id: str, session_id: str | None = None) -> dict:
        clean_project_id = slugify(project_id)
        clean_session_id = slugify(session_id) if session_id else None
        removed = self.store.clear_rewrite_prompt_config(clean_project_id, session_id=clean_session_id)
        return {
            "success": True,
            "project_id": clean_project_id,
            "session_id": clean_session_id,
            "removed": int(removed.get("removed", 0)),
        }

    def _resolve_rewrite_prompt_inputs(
        self,
        project_id: str,
        session_id: str | None,
        story_context: str,
        rewrite_prompt: str | None,
    ) -> tuple[str, str, str]:
        clean_project_id = slugify(project_id)
        clean_session_id = slugify(session_id) if session_id else None
        persisted = self.store.read_rewrite_prompt_config(clean_project_id, session_id=clean_session_id)
        persisted_prompt = str(persisted.get("rewrite_prompt") or "").strip()
        persisted_context = str(persisted.get("story_context") or "").strip()
        persisted_source = str(persisted.get("source") or "")
        if persisted_prompt and persisted_source == "session":
            return persisted_context, persisted_prompt, str(persisted.get("source") or "session")
        prompt_default = self.get_prompt_default()
        default_prompt = str(prompt_default.get("rewrite_prompt") or "").strip() or DEFAULT_REWRITE_PROMPT
        default_context = str(prompt_default.get("story_context") or "").strip()
        # If default config is absent/empty, keep request values as final fallback.
        final_prompt = default_prompt or str(rewrite_prompt or "").strip() or DEFAULT_REWRITE_PROMPT
        final_context = default_context or str(story_context or "").strip()
        return final_context, final_prompt, "prompt_default"

    def _ensure_prompt_default_seed(self) -> None:
        self.prompt_default_dir.mkdir(parents=True, exist_ok=True)
        if not self.prompt_default_path.exists():
            self.prompt_default_path.write_text(
                json.dumps(
                    {
                        "story_context": DEFAULT_STORY_CONTEXT,
                        "rewrite_prompt": DEFAULT_REWRITE_PROMPT,
                        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        if not self.story_context_template_path.exists():
            self.story_context_template_path.write_text("", encoding="utf-8")

    def get_prompt_default(self) -> dict:
        self._ensure_prompt_default_seed()
        try:
            payload = json.loads(self.prompt_default_path.read_text(encoding="utf-8"))
        except Exception:
            payload = {"story_context": DEFAULT_STORY_CONTEXT, "rewrite_prompt": DEFAULT_REWRITE_PROMPT}
        story_context_template = self.story_context_template_path.read_text(encoding="utf-8", errors="replace")
        return {
            "success": True,
            "story_context": str(payload.get("story_context") or DEFAULT_STORY_CONTEXT),
            "rewrite_prompt": str(payload.get("rewrite_prompt") or DEFAULT_REWRITE_PROMPT),
            "story_context_template": story_context_template,
        }

    def save_prompt_default(self, story_context: str, rewrite_prompt: str, story_context_template: str | None = None) -> dict:
        self._ensure_prompt_default_seed()
        payload = {
            "story_context": (story_context or "").strip() or DEFAULT_STORY_CONTEXT,
            "rewrite_prompt": (rewrite_prompt or "").strip() or DEFAULT_REWRITE_PROMPT,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        self.prompt_default_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        if story_context_template is not None:
            self.story_context_template_path.write_text(story_context_template, encoding="utf-8")
        return {"success": True, **payload}

    def clear_prompt_default(self) -> dict:
        removed = 0
        for path in (self.prompt_default_path, self.story_context_template_path):
            if path.exists() and path.is_file():
                path.unlink(missing_ok=True)
                removed += 1
        self._ensure_prompt_default_seed()
        return {"success": True, "removed": removed}

    def _ensure_llm_default_seed(self) -> None:
        self.prompt_default_dir.mkdir(parents=True, exist_ok=True)
        if not self.llm_default_path.exists():
            payload = {
                "llm_base_url": DEFAULT_LLM_BASE_URL,
                "llm_model": DEFAULT_LLM_MODEL,
                "llm_api_key": "",
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            self.llm_default_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_llm_default(self) -> dict:
        self._ensure_llm_default_seed()
        try:
            payload = json.loads(self.llm_default_path.read_text(encoding="utf-8"))
        except Exception:
            payload = {
                "llm_base_url": DEFAULT_LLM_BASE_URL,
                "llm_model": DEFAULT_LLM_MODEL,
                "llm_api_key": "",
            }
        return {
            "success": True,
            "llm_base_url": DEFAULT_LLM_BASE_URL,
            "llm_model": str(payload.get("llm_model") or DEFAULT_LLM_MODEL),
            "llm_api_key": str(payload.get("llm_api_key") or ""),
        }

    def save_llm_default(self, llm_base_url: str | None, llm_model: str, llm_api_key: str | None = None) -> dict:
        self._ensure_llm_default_seed()
        payload = {
            "llm_base_url": DEFAULT_LLM_BASE_URL,
            "llm_model": str(llm_model or "").strip() or DEFAULT_LLM_MODEL,
            "llm_api_key": str(llm_api_key or "").strip(),
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        self.llm_default_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"success": True, **payload}

    def clear_llm_default(self) -> dict:
        removed = 0
        if self.llm_default_path.exists() and self.llm_default_path.is_file():
            self.llm_default_path.unlink(missing_ok=True)
            removed = 1
        self._ensure_llm_default_seed()
        return {"success": True, "removed": removed}

    def test_llm_chat(
        self,
        message: str,
        llm_base_url: str | None = None,
        llm_model: str | None = None,
        llm_api_key: str | None = None,
        max_tokens: int = 128,
        temperature: float = 0.2,
    ) -> dict:
        base_url = DEFAULT_LLM_BASE_URL
        model = str(llm_model or "").strip() or DEFAULT_LLM_MODEL
        prompt = str(message or "").strip()
        if not prompt:
            raise ValueError("message is required")
        endpoint = f"{base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": max(0.0, float(temperature or 0.0)),
            "max_tokens": max(16, int(max_tokens or 128)),
        }
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        key = str(llm_api_key or "").strip()
        if key:
            headers["Authorization"] = f"Bearer {key}"
        req = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                text = response.read().decode("utf-8", errors="replace")
                status_code = int(response.status)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else str(exc)
            return {
                "success": False,
                "status_code": int(getattr(exc, "code", 500) or 500),
                "message": f"HTTP error from LLM endpoint: {exc}",
                "error": detail,
                "llm_base_url": base_url,
                "llm_model": model,
            }
        except Exception as exc:
            return {
                "success": False,
                "status_code": 500,
                "message": f"Cannot connect to LLM endpoint: {exc}",
                "llm_base_url": base_url,
                "llm_model": model,
            }
        try:
            data = json.loads(text)
        except Exception:
            data = {"raw": text}
        choices = data.get("choices") if isinstance(data, dict) else None
        answer = ""
        if isinstance(choices, list) and choices:
            first = choices[0] if isinstance(choices[0], dict) else {}
            message_block = first.get("message") if isinstance(first, dict) else {}
            if isinstance(message_block, dict):
                answer = str(message_block.get("content") or "")
        return {
            "success": 200 <= status_code < 300,
            "status_code": status_code,
            "message": "LLM chat test ok." if 200 <= status_code < 300 else "LLM chat test failed.",
            "reply": answer,
            "llm_base_url": base_url,
            "llm_model": model,
            "raw": data,
        }

    def crawl_chapters(
        self,
        story_url: str,
        start_chapter: int,
        chapter_count: int,
        chapter_token: str | None = None,
    ) -> dict:
        refs = self.collector.crawl_chapter_urls(
            story_url=story_url,
            start_chapter=start_chapter,
            chapter_count=chapter_count,
            chapter_token=chapter_token,
        )
        return {
            "success": True,
            "message": f"Crawled {len(refs)} chapter URLs.",
            "count": len(refs),
            "chapters": [item.__dict__ for item in refs],
        }

    def crawl_chapters_from_browser(
        self,
        story_url: str,
        cdp_url: str = "http://127.0.0.1:9222",
        max_scroll_rounds: int = 120,
    ) -> dict:
        max_scroll_rounds = max(10, min(1000, int(max_scroll_rounds)))
        links = self._crawl_chapter_urls_via_cdp(story_url=story_url, cdp_url=cdp_url, max_scroll_rounds=max_scroll_rounds)
        sorted_links = self._sort_chapter_urls(links)
        refs = []
        for idx, item in enumerate(sorted_links, start=1):
            refs.append({
                "index": idx,
                "title": f"Chapter {idx}",
                "url": item["url"],
                "chapter_no": item["chapter_no"],
            })
        return {
            "success": True,
            "message": f"Crawled full chapter list from Chrome tab: {len(refs)} URLs.",
            "count": len(refs),
            "total_found": len(refs),
            "used_fallback": False,
            "chapters": refs,
        }

    @staticmethod
    def _extract_chapter_no(url: str) -> float | None:
        parsed = urlparse(url)
        path = unquote(parsed.path or "").lower()
        query = unquote(parsed.query or "").lower()
        haystack = f"{path}?{query}" if query else path
        patterns = [
            r"(?:^|[/?#&._-])(?:chuong|chapter|chap|ch)[._/-]*(\d+(?:\.\d+)?)",
            r"(?:chuong|chapter|chap|ch)[^\d]{0,12}(\d+(?:\.\d+)?)",
            r"(?:^|[/?#&._-])c(\d+(?:\.\d+)?)(?:$|[/?#&._-])",
        ]
        for pattern in patterns:
            match = re.search(pattern, haystack, flags=re.I)
            if match:
                return float(match.group(1))

        # Fallback for sites that use only a numeric slug at the end of the chapter path.
        for segment in reversed([part for part in path.split("/") if part]):
            numbers = re.findall(r"\d+(?:\.\d+)?", segment)
            if numbers:
                return float(numbers[-1])
        return None

    @classmethod
    def _sort_chapter_urls(cls, urls: list[str]) -> list[dict]:
        uniq: list[str] = []
        seen: set[str] = set()
        for url in urls:
            key = (url or "").split("#", 1)[0].rstrip("/")
            if not key or key in seen:
                continue
            seen.add(key)
            uniq.append(key)
        items = []
        for idx, url in enumerate(uniq, start=1):
            extracted = cls._extract_chapter_no(url)
            chapter_no = extracted if extracted is not None else 10_000_000 + idx
            items.append({"url": url, "chapter_no": chapter_no})
        items.sort(key=lambda item: (item["chapter_no"], item["url"]))
        return items

    @staticmethod
    def _crawl_chapter_urls_via_cdp(story_url: str, cdp_url: str, max_scroll_rounds: int) -> list[str]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError("Playwright is required for browser-based chapter crawl.") from exc

        parsed_story = urlparse(story_url)
        story_host = parsed_story.netloc.lower()
        story_prefix = story_url.rstrip("/")
        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp(cdp_url)
            page = None
            for context in browser.contexts:
                for candidate in context.pages:
                    url = (candidate.url or "").split("#", 1)[0].rstrip("/")
                    if url.startswith(story_prefix):
                        page = candidate
                        break
                if page is not None:
                    break
            if page is None:
                raise RuntimeError(
                    "No matching story tab found in debug Chrome. Open the exact story tab first, then retry."
                )
            page.bring_to_front()
            page.wait_for_load_state("domcontentloaded", timeout=0)

            tab_selectors = [
                "button:has-text('D.s chương')",
                "button:has-text('Danh sách chương')",
                "a:has-text('D.s chương')",
                "a:has-text('Danh sách chương')",
                "[role='tab']:has-text('D.s chương')",
                "[role='tab']:has-text('Danh sách chương')",
            ]
            for selector in tab_selectors:
                try:
                    loc = page.locator(selector)
                    if loc.count() > 0 and loc.first.is_visible():
                        loc.first.click(timeout=5000)
                        page.wait_for_timeout(900)
                        break
                except Exception:
                    continue

            collected: set[str] = set()
            stable_rounds = 0
            for _ in range(max_scroll_rounds):
                hrefs = page.eval_on_selector_all(
                    "a[href*='/chuong-']",
                    "els => els.map(el => el.getAttribute('href') || '')",
                )
                before = len(collected)
                for href in hrefs:
                    absolute = urljoin(story_url, href).split("#", 1)[0].rstrip("/")
                    parsed = urlparse(absolute)
                    if parsed.scheme not in {"http", "https"}:
                        continue
                    if parsed.netloc.lower() != story_host:
                        continue
                    if not absolute.startswith(story_prefix):
                        continue
                    if "/chuong-" not in absolute.lower():
                        continue
                    collected.add(absolute)
                if len(collected) == before:
                    stable_rounds += 1
                else:
                    stable_rounds = 0
                if stable_rounds >= 8:
                    break
                # Scroll viewport + any scrollable containers to force lazy-loaded chapter list.
                page.mouse.wheel(0, 2600)
                page.keyboard.press("End")
                page.eval_on_selector_all(
                    "*",
                    """els => {
                      for (const el of els) {
                        const style = window.getComputedStyle(el);
                        const overflowY = style.overflowY || '';
                        const canScroll = (overflowY.includes('auto') || overflowY.includes('scroll')) && el.scrollHeight > el.clientHeight;
                        if (canScroll) {
                          el.scrollTop = el.scrollHeight;
                        }
                      }
                    }""",
                )
                # Best-effort click for load-more style controls.
                for selector in [
                    "button:has-text('Xem thêm')",
                    "button:has-text('Xem tiep')",
                    "button:has-text('Load more')",
                    "a:has-text('Xem thêm')",
                ]:
                    try:
                        loc = page.locator(selector)
                        if loc.count() > 0 and loc.first.is_visible():
                            loc.first.click(timeout=1200)
                    except Exception:
                        pass
                page.wait_for_timeout(900)
            if not collected:
                html = page.content()
                for match in re.findall(r'href=["\']([^"\']*?/chuong-[^"\']+)["\']', html, flags=re.I):
                    absolute = urljoin(story_url, match).split("#", 1)[0].rstrip("/")
                    parsed = urlparse(absolute)
                    if parsed.netloc.lower() == story_host and absolute.startswith(story_prefix):
                        collected.add(absolute)
            browser.close()
        if not collected:
            raise RuntimeError("No chapter URLs found from browser tab. Open story page and chapter list tab first.")
        return list(collected)

    def list_projects(self) -> dict:
        projects_by_id = {item.get("project_id"): item for item in self.registry.list_projects()}
        for project in self.store.list_projects():
            project_id = project.get("project_id")
            if project_id and project_id not in projects_by_id:
                projects_by_id[project_id] = project
        return {"projects": list(projects_by_id.values())}

    def create_workspace_project(self, name: str, project_id: str | None = None) -> dict:
        clean_name = (name or "").strip()
        if not clean_name:
            raise ValueError("Project name is required.")
        wanted_id = slugify(project_id or clean_name)
        if any(str(item.get("project_id") or "") == wanted_id for item in self.registry.list_projects()):
            raise ValueError(f"Project already exists: {wanted_id}")

        project = ConvertProject(
            project_id=wanted_id,
            name=clean_name,
            story_url="",
            domain="",
            start_chapter=1,
            chapter_count=1,
            status="created",
        )
        self.store.write_project(project)
        shared = self.registry.upsert_project(
            wanted_id,
            {
                "name": clean_name,
                "status": "created",
                "source_url": "",
                "chapter_token": "",
            },
        )
        return {
            "ok": True,
            "project": shared,
        }

    def get_project(self, project_id: str) -> dict:
        shared = self.registry.get_project(project_id)
        manifest = None
        try:
            manifest = self.store.read_manifest(project_id)
        except FileNotFoundError:
            manifest = None
        return {"project": shared, "manifest": manifest}

    def rename_project(self, project_id: str, name: str, notes: str = "") -> dict:
        return self.registry.rename_project(project_id, name, notes)

    def delete_project(self, project_id: str, delete_artifacts: bool = False) -> dict:
        return self.registry.delete_project(project_id, delete_artifacts=delete_artifacts)

    def delete_session(self, project_id: str, session_id: str, delete_artifacts: bool = True) -> dict:
        from auto_convert_text.storage.project_store import slugify

        clean_project = slugify(project_id)
        clean_session = slugify(session_id)
        removed_artifacts = self.store.delete_session(clean_project, clean_session) if delete_artifacts else False
        registry = self.registry.delete_session(clean_project, clean_session)
        return {
            **registry,
            "removed_artifacts": removed_artifacts,
            "removed_tts_text": 0,
        }

    def create_session(
        self,
        project_id: str,
        session_id: str,
        start_chapter: int = 1,
        chapter_count: int = 1,
    ) -> dict:
        clean_project = slugify(project_id)
        clean_session = slugify(session_id)
        if not clean_project:
            raise ValueError("project_id is required")
        if not clean_session:
            raise ValueError("session_id is required")
        start = max(1, int(start_chapter))
        count = max(1, int(chapter_count))
        end = start + count - 1
        self.store.ensure_project_dirs(clean_project, clean_session)
        session = self.registry.upsert_session(
            clean_project,
            clean_session,
            {
                "status": "created",
                "chapter_start": start,
                "chapter_end": end,
                "convert": {
                    "start_chapter": start,
                    "chapter_count": count,
                },
            },
        )
        return {
            "success": True,
            "project_id": clean_project,
            "session_id": clean_session,
            "session": session,
        }

    def get_manifest(self, project_id: str, session_id: str | None = None) -> dict:
        if session_id:
            return self.store.read_session_manifest(project_id, session_id)
        return self.store.read_manifest(project_id)

    def list_session_files(self, project_id: str, session_id: str, stage: str) -> dict:
        session_dir = self.store.session_dir(project_id, session_id)
        stage_map = {
            "chapter_urls": self.store.project_dir(project_id) / "chapter_urls",
            "raw": session_dir / "chapters_text" / "raw",
            "rewritten": session_dir / "chapters_text" / "rewritten",
            "audio_clean": session_dir / "chapters_text" / "audio_clean",
            "chunks": session_dir / "chapters_text" / "chunks",
            "tts_inputs": session_dir / "tts_inputs",
        }
        target = stage_map.get(stage)
        if target is None:
            raise ValueError(f"Unsupported stage: {stage}")
        if not target.exists():
            return {"stage": stage, "files": []}
        files = [
            {"name": p.name, "size": p.stat().st_size}
            for p in sorted(target.glob("*.txt"))
            if p.is_file()
        ]
        return {"stage": stage, "files": files}

    def get_session_file_content(self, project_id: str, session_id: str, stage: str, filename: str) -> dict:
        session_dir = self.store.session_dir(project_id, session_id)
        stage_map = {
            "chapter_urls": self.store.project_dir(project_id) / "chapter_urls",
            "raw": session_dir / "chapters_text" / "raw",
            "rewritten": session_dir / "chapters_text" / "rewritten",
            "audio_clean": session_dir / "chapters_text" / "audio_clean",
            "chunks": session_dir / "chapters_text" / "chunks",
            "tts_inputs": session_dir / "tts_inputs",
        }
        target_root = stage_map.get(stage)
        if target_root is None:
            raise ValueError(f"Unsupported stage: {stage}")
        safe_name = filename.strip().replace("\\", "/").split("/")[-1]
        if not safe_name.endswith(".txt"):
            raise ValueError("Filename must be .txt")
        target = (target_root / safe_name).resolve()
        if target.parent != target_root.resolve() or not target.exists() or not target.is_file():
            raise FileNotFoundError(f"File not found: {safe_name}")
        return {
            "stage": stage,
            "name": safe_name,
            "content": target.read_text(encoding="utf-8", errors="replace"),
        }

    def save_session_file_content(self, project_id: str, session_id: str, stage: str, filename: str, content: str) -> dict:
        session_dir = self.store.session_dir(project_id, session_id)
        stage_map = {
            "raw": session_dir / "chapters_text" / "raw",
            "rewritten": session_dir / "chapters_text" / "rewritten",
            "audio_clean": session_dir / "chapters_text" / "audio_clean",
            "chunks": session_dir / "chapters_text" / "chunks",
            "tts_inputs": session_dir / "tts_inputs",
        }
        target_root = stage_map.get(stage)
        if target_root is None:
            raise ValueError(f"Unsupported stage for save: {stage}")
        target_root.mkdir(parents=True, exist_ok=True)
        safe_name = filename.strip().replace("\\", "/").split("/")[-1]
        if not safe_name.endswith(".txt"):
            raise ValueError("Filename must be .txt")
        target = (target_root / safe_name).resolve()
        if target.parent != target_root.resolve():
            raise ValueError("Invalid filename.")
        target.write_text((content or ""), encoding="utf-8")
        return {"stage": stage, "name": safe_name, "size": target.stat().st_size}

    def delete_session_file(self, project_id: str, session_id: str, stage: str, filename: str) -> dict:
        session_dir = self.store.session_dir(project_id, session_id)
        stage_map = {
            "raw": session_dir / "chapters_text" / "raw",
            "rewritten": session_dir / "chapters_text" / "rewritten",
            "audio_clean": session_dir / "chapters_text" / "audio_clean",
            "chunks": session_dir / "chapters_text" / "chunks",
            "tts_inputs": session_dir / "tts_inputs",
        }
        target_root = stage_map.get(stage)
        if target_root is None:
            raise ValueError(f"Unsupported stage for delete: {stage}")
        safe_name = filename.strip().replace("\\", "/").split("/")[-1]
        if not safe_name.endswith(".txt"):
            raise ValueError("Filename must be .txt")
        target = (target_root / safe_name).resolve()
        if target.parent != target_root.resolve() or not target.exists() or not target.is_file():
            raise FileNotFoundError(f"File not found: {safe_name}")
        target.unlink(missing_ok=True)
        return {"stage": stage, "name": safe_name, "deleted": True}

    def rewrite(
        self,
        project_id: str,
        provider: str = "bridge_gemini",
        rewrite_model: str = "fast",
        story_context: str = "",
        rewrite_prompt: str | None = None,
        llm_base_url: str = "",
        llm_model: str = "gemini/gemini-3-flash-preview",
        llm_api_key: str | None = None,
        cdp_url: str | None = None,
        cdp_urls: list[str] | None = None,
        bridge_base_url: str = DEFAULT_BRIDGE_BASE_URL,
        bridge_timeout_s: float = 600.0,
        parallel_workers: int = 2,
        session_id: str | None = None,
        progress_callback: Callable[[dict], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
        resume_only: bool = False,
    ) -> dict:
        resolved_story_context, resolved_rewrite_prompt, prompt_source = self._resolve_rewrite_prompt_inputs(
            project_id=project_id,
            session_id=session_id,
            story_context=story_context,
            rewrite_prompt=rewrite_prompt,
        )
        config = RewriteConfig(
            provider=provider,
            model_preference=(rewrite_model or "fast"),
            story_context=resolved_story_context,
            rewrite_prompt=resolved_rewrite_prompt,
            llm_base_url=llm_base_url,
            llm_model=llm_model,
            llm_api_key=llm_api_key,
            cdp_url=cdp_url,
            cdp_urls=cdp_urls or [],
            bridge_base_url=bridge_base_url,
            bridge_timeout_s=bridge_timeout_s,
            parallel_workers=max(1, int(parallel_workers or 2)),
            request_delay_seconds=0.6,
        )
        rewrite_warmup = {}
        if str(provider or "").strip().lower() in {"", "bridge_gemini", "gemini_web"}:
            rewrite_ports = self._ports_from_cdp_values(cdp_url, cdp_urls or [])
            if rewrite_ports:
                rewrite_warmup = BrowserBridgeClient(bridge_base_url, timeout_s=bridge_timeout_s).ping_ports(rewrite_ports)
        result = self.rewriter.run(
            project_id,
            config,
            session_id=session_id,
            progress_callback=progress_callback,
            should_stop=should_stop,
            resume_only=resume_only,
        )
        result["prompt_source"] = prompt_source
        if rewrite_warmup:
            result["bridge_warmup"] = rewrite_warmup
        session_dir = self.store.session_dir(project_id, session_id)
        self.registry.update_convert(
            project_id,
            {
                "rewrite_provider": provider,
                "rewritten_success": result["summary"]["success"],
                "rewritten_failed": result["summary"]["failed"],
                "rewrite_manifest_path": str((session_dir / "rewrite_manifest.json").relative_to(self.repo_root)),
            },
        )
        if session_id:
            self.registry.upsert_session(project_id, session_id, {
                "status": "rewritten" if result["summary"]["failed"] == 0 else "rewrite_failed",
                "convert": {
                    "rewrite_provider": provider,
                    "rewritten_success": result["summary"]["success"],
                    "rewritten_failed": result["summary"]["failed"],
                    "rewrite_manifest_path": str((session_dir / "rewrite_manifest.json").relative_to(self.repo_root)),
                },
            })
        return result

    @staticmethod
    def _cdp_alive(cdp_url: str) -> bool:
        try:
            with urllib.request.urlopen(f"{cdp_url}/json/version", timeout=1.5) as response:
                return response.status == 200
        except Exception:
            return False

    @staticmethod
    def _ports_from_cdp_values(cdp_url: str | None, cdp_urls: list[str] | None) -> list[int]:
        values: set[int] = set()
        urls: list[str] = []
        if cdp_url:
            urls.append(str(cdp_url))
        urls.extend(str(item) for item in (cdp_urls or []) if str(item or "").strip())
        for raw in urls:
            try:
                parsed = urlparse(raw if "://" in raw else f"http://127.0.0.1:{raw}")
                port = int(parsed.port or 0)
            except Exception:
                port = 0
            if 1 <= port <= 65535:
                values.add(port)
        return sorted(values)

    def open_gemini_chrome_pool(
        self,
        ports: list[int],
        user_data_root: str = r"D:\chrome-gemini-profile-pool",
        url: str = "https://gemini.google.com",
    ) -> dict:
        clean_ports = sorted({max(1, min(65535, int(p))) for p in ports})
        if not clean_ports:
            raise ValueError("ports is required.")
        rows = []
        for port in clean_ports:
            profile_dir = str((Path(user_data_root) / f"port_{port}").resolve())
            state = self.open_gemini_chrome(port=port, user_data_dir=profile_dir, url=url)
            state["ready"] = self._cdp_alive(state["cdp_url"])
            state["login_ready"] = False
            rows.append(state)
        self._save_chrome_pool_state(rows)
        return {"ok": True, "count": len(rows), "instances": rows}

    def close_gemini_chrome_pool(self, ports: list[int]) -> dict:
        clean_ports = sorted({max(1, min(65535, int(p))) for p in ports})
        closed = 0
        for port in clean_ports:
            # Best effort via netstat/taskkill on Windows.
            if os.name == "nt":
                cmd = f'for /f "tokens=5" %a in (\'netstat -ano ^| findstr :{port} ^| findstr LISTENING\') do taskkill /PID %a /F'
                subprocess.call(cmd, shell=True)
                closed += 1
        current = self.get_gemini_chrome_pool_status().get("instances", [])
        keep = [item for item in current if int(item.get("port") or 0) not in set(clean_ports)]
        self._save_chrome_pool_state(keep)
        return {"ok": True, "requested": len(clean_ports), "closed": closed}

    def get_gemini_chrome_pool_status(self) -> dict:
        instances = self._load_chrome_pool_state()
        for item in instances:
            cdp_url = str(item.get("cdp_url") or "")
            item["ready"] = self._cdp_alive(cdp_url) if cdp_url else False
        self._save_chrome_pool_state(instances)
        return {"ok": True, "count": len(instances), "instances": instances}

    def mark_gemini_chrome_pool_login_ready(self, ports: list[int], login_ready: bool = True) -> dict:
        wanted = {max(1, min(65535, int(p))) for p in ports}
        instances = self._load_chrome_pool_state()
        updated = 0
        for item in instances:
            port = int(item.get("port") or 0)
            if port in wanted:
                item["login_ready"] = bool(login_ready)
                updated += 1
        self._save_chrome_pool_state(instances)
        return {"ok": True, "updated": updated, "count": len(instances), "instances": instances}

    def _load_chrome_pool_state(self) -> list[dict]:
        if not self.chrome_pool_state_path.exists():
            return []
        try:
            import json
            payload = json.loads(self.chrome_pool_state_path.read_text(encoding="utf-8"))
            rows = payload.get("instances")
            if isinstance(rows, list):
                return [dict(item) for item in rows if isinstance(item, dict)]
        except Exception:
            return []
        return []

    def _save_chrome_pool_state(self, instances: list[dict]) -> None:
        import json
        self.chrome_pool_state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "instances": instances,
        }
        self.chrome_pool_state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def audio_clean(
        self,
        project_id: str,
        session_id: str | None = None,
        progress_callback: Callable[[dict], None] | None = None,
    ) -> dict:
        result = self.audio_cleaner.run(project_id, session_id=session_id, progress_callback=progress_callback)
        self.registry.update_convert(
            project_id,
            {
                "audio_clean_success": result["summary"]["success"],
                "audio_clean_failed": result["summary"]["failed"],
            },
        )
        if session_id:
            self.registry.upsert_session(project_id, session_id, {
                "status": "audio_cleaned" if result["summary"]["failed"] == 0 else "audio_clean_failed",
                "convert": {
                    "audio_clean_success": result["summary"]["success"],
                    "audio_clean_failed": result["summary"]["failed"],
                },
            })
        return result

    def chunk(
        self,
        project_id: str,
        min_words: int = DEFAULT_TTS_MIN_WORDS,
        max_words: int = DEFAULT_TTS_MAX_WORDS,
        session_id: str | None = None,
        progress_callback: Callable[[dict], None] | None = None,
    ) -> dict:
        result = self.simple_chunker.run(
            project_id=project_id,
            session_id=session_id,
            min_words=min_words,
            max_words=max_words,
            clear_old=True,
            progress_callback=progress_callback,
        )
        exported = int(result.get("summary", {}).get("tts_inputs", 0))
        self.registry.update_convert(
            project_id,
            {
                "chunk_min_words": int(min_words),
                "chunk_max_words": int(max_words),
                "chunk_count": int(result.get("summary", {}).get("chunks", 0)),
                "exported_tts_text": exported,
            },
        )
        if session_id:
            self.registry.upsert_session(project_id, session_id, {
                "status": "tts_text_ready",
                "convert": {
                    "chunk_min_words": int(min_words),
                    "chunk_max_words": int(max_words),
                    "chunk_count": int(result.get("summary", {}).get("chunks", 0)),
                    "exported_tts_text": exported,
                },
            })
        return result

    def export_tts_text(
        self,
        project_id: str,
        clear_old: bool = False,
        session_id: str | None = None,
        progress_callback: Callable[[dict], None] | None = None,
    ) -> dict:
        _ = clear_old
        return self.chunk(
            project_id=project_id,
            min_words=DEFAULT_TTS_MIN_WORDS,
            max_words=DEFAULT_TTS_MAX_WORDS,
            session_id=session_id,
            progress_callback=progress_callback,
        )

    def run_full_to_tts_text(
        self,
        story_url: str,
        start_chapter: int,
        chapter_count: int,
        project_name: str | None = None,
        project_id: str | None = None,
        chapter_token: str | None = None,
        chapter_urls: list[str] | None = None,
        apply_chapter_window: bool = False,
        provider: str = "bridge_gemini",
        rewrite_model: str = "fast",
        story_context: str = "",
        rewrite_prompt: str | None = None,
        breath_chunk_prompt: str | None = None,
        llm_base_url: str = "",
        llm_model: str = "gemini/gemini-3-flash-preview",
        llm_api_key: str | None = None,
        cdp_url: str | None = None,
        cdp_urls: list[str] | None = None,
        bridge_base_url: str = DEFAULT_BRIDGE_BASE_URL,
        bridge_timeout_s: float = 600.0,
        parallel_workers: int = 2,
        clear_old_tts_text: bool = True,
        target_chars: int = 600,
        max_chars: int = 1100,
        min_chars: int = 200,
        auto_open_gemini_browser: bool = False,
        session_id: str | None = None,
        progress_callback: Callable[[dict], None] | None = None,
    ) -> dict:
        resolved_session_id = self.store.session_id(start_chapter, chapter_count) if not session_id else session_id
        max_seen_units = 0

        def emit_progress(event: dict) -> None:
            if not progress_callback:
                return
            stage = event.get("stage", "")
            total = max(1, int(event.get("total") or 1))
            current = max(0, int(event.get("current") or 0))
            nonlocal max_seen_units
            total_units = chapter_count * 3 + max(chapter_count, total)
            stage_base = {
                "collect": 0,
                "rewrite": chapter_count,
                "audio_clean": chapter_count * 2,
                "chunk": chapter_count * 3,
            }
            base = stage_base.get(stage, max_seen_units)
            current_units = min(total_units, base + current)
            max_seen_units = max(max_seen_units, current_units)
            progress_callback({
                **event,
                "session_id": resolved_session_id,
                "current_units": max_seen_units,
                "total_units": total_units,
                "files_done": int(event.get("files_done", current)),
            })

        collect_result = self.collect(
            story_url=story_url,
            start_chapter=start_chapter,
            chapter_count=chapter_count,
            project_name=project_name,
            project_id=project_id,
            chapter_token=chapter_token,
            chapter_urls=chapter_urls,
            apply_chapter_window=apply_chapter_window,
            session_id=resolved_session_id,
            progress_callback=emit_progress,
        )
        resolved_project_id = collect_result["project_id"]
        resolved_session_id = collect_result.get("session_id") or resolved_session_id
        if collect_result["failed_count"]:
            return {
                "success": False,
                "message": "Full convert stopped because one or more chapters failed during crawl.",
                "project_id": resolved_project_id,
                "session_id": resolved_session_id,
                "collect": collect_result,
            }
        gemini_browser = None
        if provider not in {"bridge_gemini", "fake"}:
            provider = "bridge_gemini"
        rewrite_result = self.rewrite(
            project_id=resolved_project_id,
            provider=provider,
            rewrite_model=rewrite_model,
            story_context=story_context,
            rewrite_prompt=rewrite_prompt,
            llm_base_url=llm_base_url,
            llm_model=llm_model,
            llm_api_key=llm_api_key,
                cdp_url=cdp_url,
                cdp_urls=cdp_urls,
                bridge_base_url=bridge_base_url,
                bridge_timeout_s=bridge_timeout_s,
                parallel_workers=parallel_workers,
            session_id=resolved_session_id,
            progress_callback=emit_progress,
        )
        rewrite_summary = rewrite_result.get("summary", {})
        rewrite_failed = int(rewrite_summary.get("failed", 0) or 0)
        rewrite_success = int(rewrite_summary.get("success", 0) or 0)
        if rewrite_failed and rewrite_success <= 0:
            return {
                "success": False,
                "message": "Full convert stopped because Gemini rewrite failed for all chapters.",
                "project_id": resolved_project_id,
                "session_id": resolved_session_id,
                "gemini_browser": gemini_browser,
                "collect": collect_result,
                "rewrite": rewrite_result,
            }
        clean_result = self.audio_clean(resolved_project_id, session_id=resolved_session_id, progress_callback=emit_progress)
        if clean_result["summary"]["failed"]:
            return {
                "success": False,
                "message": "Full convert stopped because audio clean failed.",
                "project_id": resolved_project_id,
                "session_id": resolved_session_id,
                "gemini_browser": gemini_browser,
                "collect": collect_result,
                "rewrite": rewrite_result,
                "audio_clean": clean_result,
            }
        chunk_result = self.chunk(
            project_id=resolved_project_id,
            min_words=DEFAULT_TTS_MIN_WORDS,
            max_words=DEFAULT_TTS_MAX_WORDS,
            session_id=resolved_session_id,
            progress_callback=emit_progress,
        )
        self.registry.upsert_project(
            resolved_project_id,
            {
                "status": "tts_text_ready",
                "convert": {
                    "full_pipeline_completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "exported_tts_text": chunk_result["summary"]["tts_inputs"],
                    "active_session_id": resolved_session_id,
                },
            },
        )
        self.registry.upsert_session(resolved_project_id, resolved_session_id, {
            "status": "tts_text_ready",
            "chapter_start": start_chapter,
            "chapter_end": start_chapter + chapter_count - 1,
            "convert": {
                "full_pipeline_completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "exported_tts_text": chunk_result["summary"]["tts_inputs"],
            },
        })
        return {
            "success": True,
            "message": "Collected, rewritten, cleaned, chunked and created TTS text files.",
            "project_id": resolved_project_id,
            "session_id": resolved_session_id,
            "gemini_browser": gemini_browser,
            "collect": collect_result,
            "rewrite": rewrite_result,
            "audio_clean": clean_result,
            "chunk": chunk_result,
            "warning": (
                f"Rewrite completed with partial failures: {rewrite_failed} chapter(s) failed. "
                "Pipeline continued with available chapters."
                if rewrite_failed > 0
                else None
            ),
        }

    @staticmethod
    def _find_chrome_executable() -> Path:
        candidates = [
            Path(os.environ.get("CHROME_PATH", "")),
            Path(os.environ.get("PROGRAMFILES", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
        ]
        for candidate in candidates:
            if candidate and candidate.exists() and candidate.is_file():
                return candidate
        raise FileNotFoundError(
            "chrome.exe not found. Set CHROME_PATH or install Google Chrome."
        )

    def open_gemini_chrome(
        self,
        port: int = 9222,
        user_data_dir: str = r"D:\chrome-gemini-profile",
        url: str = "https://gemini.google.com",
    ) -> dict:
        cdp_url = f"http://127.0.0.1:{int(port)}"
        try:
            with urllib.request.urlopen(f"{cdp_url}/json/version", timeout=1.5) as response:
                if response.status == 200:
                    return {
                        "ok": True,
                        "message": "Chrome remote debugging is already available.",
                        "pid": None,
                        "chrome": "already-running",
                        "port": int(port),
                        "user_data_dir": user_data_dir,
                        "url": url,
                        "cdp_url": cdp_url,
                    }
        except Exception:
            pass
        chrome = self._find_chrome_executable()
        profile_dir = Path(user_data_dir)
        profile_dir.mkdir(parents=True, exist_ok=True)
        args = [
            str(chrome),
            f"--remote-debugging-port={int(port)}",
            f"--user-data-dir={str(profile_dir)}",
            url,
        ]
        proc = subprocess.Popen(  # noqa: S603 - user-triggered local browser launch
            args,
            cwd=str(self.repo_root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        )
        return {
            "ok": True,
            "message": "Chrome started for Gemini remote debugging.",
            "pid": proc.pid,
            "chrome": str(chrome),
            "port": int(port),
            "user_data_dir": str(profile_dir),
            "url": url,
            "cdp_url": cdp_url,
        }
