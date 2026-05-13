from __future__ import annotations

import hashlib
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from auto_convert_text.models.dto import utc_now_iso
from auto_convert_text.pipeline.browser_bridge_client import DEFAULT_BRIDGE_BASE_URL, BrowserBridgeClient
from auto_convert_text.storage.project_store import ProjectStore


DEFAULT_REWRITE_PROMPT = """Bạn là biên tập truyện audio tiếng Việt.
Bối cảnh truyện: {story_context}
Yêu cầu:
1. Viết lại dưới góc nhìn nhân vật chính.
2. Giữ ý chính và mạch truyện.
3. Lược bỏ cảnh không quan trọng, lặp lại, quảng cáo, menu web.
4. BẮT BUỘC dùng tiếng Việt có dấu đầy đủ. Nếu input bị lỗi mã hóa, thiếu dấu, hoặc có ký tự lạ, hãy khôi phục thành tiếng Việt có dấu tự nhiên.
5. Câu văn phải tự nhiên theo cách người Việt nói và viết; ưu tiên từ ngữ phổ thông, hạn chế Hán Việt khó hiểu.
6. Đặt nhịp câu tự nhiên cho giọng đọc audio: ưu tiên câu ngắn và vừa, tránh câu quá dài.
7. Chỉ dùng dấu chấm, dấu phẩy, dấu chấm phẩy để tạo khoảng nghỉ. Nếu gặp dấu hỏi, dấu than, dấu hai chấm, ngoặc, gạch ngang, hãy chuyển thành dấu nghỉ phù hợp thay vì xóa ý.
8. Mỗi đoạn nên có các khoảng nghỉ rõ ràng, giúp model TTS đọc ổn định. Không dùng markdown, không đánh số mục, không giải thích.
Nội dung chapter:
{chapter_text}
"""


@dataclass
class RewriteConfig:
    provider: str = "bridge_gemini"
    model_preference: str = "fast"
    story_context: str = ""
    rewrite_prompt: str = DEFAULT_REWRITE_PROMPT
    llm_base_url: str = ""
    llm_model: str = "gemini/gemini-3-flash-preview"
    llm_api_key: str | None = None
    bridge_base_url: str = DEFAULT_BRIDGE_BASE_URL
    bridge_timeout_s: float = 600.0
    cdp_url: str | None = None
    cdp_urls: list[str] | None = None
    parallel_workers: int = 1
    request_delay_seconds: float = 0.6
    min_output_chars_ratio: float = 0.08
    max_output_chars_ratio: float = 2.5


def build_prompt(template: str, story_context: str, chapter_text: str) -> str:
    return template.format(story_context=story_context.strip(), chapter_text=chapter_text.strip())


def sanitize_rewritten_text(output: str) -> str:
    text = (output or "").replace("\r\n", "\n").strip()
    if not text:
        return text
    # Heuristic fallback: drop short instruction block at the beginning before first blank line.
    raw_lines = text.split("\n")
    if len(raw_lines) >= 4:
        first_blank = None
        for i, line in enumerate(raw_lines[:20]):
            if not line.strip():
                first_blank = i
                break
        if first_blank is not None and first_blank >= 2:
            head = [ln.strip() for ln in raw_lines[:first_blank] if ln.strip()]
            tail = "\n".join(raw_lines[first_blank + 1:]).strip()
            head_instruction_like = sum(1 for ln in head if len(ln) <= 120 and (ln.endswith(":") or "..." in ln or re.match(r"^\d+[\).]\s+", ln) is not None))
            if tail and len(tail) >= 120 and head_instruction_like >= max(2, len(head) // 2):
                text = tail
    # Strip common prompt-echo block that Gemini may return before actual rewritten content.
    lower_src = text.lower()
    if ("bạn là biên tập" in lower_src or "ban la bien tap" in lower_src) and ("yêu cầu" in lower_src or "yeu cau" in lower_src):
        lines = text.split("\n")
        kept: list[str] = []
        skipping = True
        for line in lines:
            ll = line.strip().lower()
            is_prompt_line = (
                ll.startswith("bạn là biên tập")
                or ll.startswith("ban la bien tap")
                or ll.startswith("bối cảnh")
                or ll.startswith("boi canh")
                or ll.startswith("yêu cầu")
                or ll.startswith("yeu cau")
                or re.match(r"^\d+[\).]\s+", ll) is not None
            )
            if skipping and (is_prompt_line or not ll):
                continue
            skipping = False
            kept.append(line)
        if kept:
            text = "\n".join(kept).strip()
    text = re.sub(r"^\s*gemini\s+said[:\s-]*", "", text, flags=re.I)
    scaffold_patterns = [
        r"^\s*bạn là biên tập.*$",
        r"^\s*ban la bien tap.*$",
        r"^\s*bối cảnh.*$",
        r"^\s*boi canh.*$",
        r"^\s*yêu cầu:.*$",
        r"^\s*báº¡n lÃ \b.*$",
        r"^\s*bá»‘i cáº£nh truyá»‡n:.*$",
        r"^\s*boi canh truyen:.*$",
        r"^\s*yÃªu cáº§u:.*$",
        r"^\s*yeu cau:.*$",
        r"^\s*ná»™i dung chapter:.*$",
        r"^\s*noi dung chapter:.*$",
    ]
    compact: list[str] = []
    for line in text.split("\n"):
        lowered_line = line.strip().lower()
        if lowered_line in {"show thinking", "hide thinking", "gemini said"}:
            continue
        if lowered_line.startswith("show thinking"):
            continue
        if any(re.search(pat, line, flags=re.I) for pat in scaffold_patterns):
            continue
        compact.append(line)
    text = "\n".join(compact).strip()
    chapter_markers = list(re.finditer(r"chapter\s*:", text, flags=re.I))
    if chapter_markers:
        text = text[chapter_markers[-1].end() :].strip()
    text = re.sub(r"^\s*(\d+[\).]|[-*])\s+", "", text, flags=re.M)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def validate_rewrite(raw_text: str, rewritten: str, config: RewriteConfig) -> str | None:
    output = rewritten.strip()
    if not output:
        return "Gemini output is empty."
    blocked_ui_tokens = [
        "Gemini PRO",
        "New chat",
        "My stuff",
        "Notebooks",
        "Gems",
        "Google apps",
        "Gemini can make mistakes",
        "Show thinking",
        "Hide thinking",
    ]
    lowered = output.lower()
    if any(token.lower() in lowered for token in blocked_ui_tokens):
        return "Gemini output contains UI chrome text, not model answer."
    if "```" in output:
        return "Gemini output contains code fence."
    if re.search(r"^\s*[-*#]{1,3}\s+", output, flags=re.M):
        return "Gemini output appears to contain markdown."
    if len(output) >= 120 and not re.search(r"[ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]", output, flags=re.I):
        return "Output appears to be Vietnamese without diacritics."
    raw_len = max(1, len(raw_text.strip()))
    ratio = len(output) / raw_len
    if ratio < config.min_output_chars_ratio:
        return f"Output too short: ratio={ratio:.2f}"
    if ratio > config.max_output_chars_ratio:
        return f"Output too long: ratio={ratio:.2f}"
    return None


class GeminiRewriter:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        self.store = ProjectStore(self.repo_root)

    def _resolve_cdp_urls(self, config: RewriteConfig) -> list[str | None]:
        urls = [u.strip() for u in (config.cdp_urls or []) if isinstance(u, str) and u.strip()]
        if config.cdp_url and config.cdp_url not in urls:
            urls.insert(0, config.cdp_url)
        if urls:
            return urls
        return [None]

    def _rewrite_one(self, index: int, raw_path: Path, config: RewriteConfig, cdp_url: str | None, output_dir: Path) -> dict:
        chapter_no_match = re.search(r"(\d+)", raw_path.stem)
        chapter_no = int(chapter_no_match.group(1)) if chapter_no_match else index
        raw_text = raw_path.read_text(encoding="utf-8", errors="replace").strip()
        out_path = output_dir / raw_path.name
        err = None
        status = "failed"
        preview_text = ""
        rewritten_rel = None
        try:
            prompt = build_prompt(config.rewrite_prompt, config.story_context, raw_text)
            provider = str(config.provider or "bridge_gemini").strip().lower()
            if provider not in {"bridge_gemini", "fake"}:
                provider = "bridge_gemini"
            bridge_client = None if provider == "fake" else BrowserBridgeClient(config.bridge_base_url, timeout_s=config.bridge_timeout_s)
            for attempt in range(1, 4):
                try:
                    if bridge_client is None:
                        rewritten = sanitize_rewritten_text(raw_text)
                        cdp_url = "fake"
                    else:
                        _payload, bridge_items = bridge_client.chat(
                            "gemini",
                            [prompt],
                            mode=config.model_preference or "fast",
                            timeout_s=config.bridge_timeout_s,
                        )
                        if not bridge_items or not bridge_items[0].success:
                            item = bridge_items[0] if bridge_items else None
                            raise RuntimeError(
                                (item.error_message if item else None)
                                or (item.error_code if item else None)
                                or "Gemini bridge returned no successful answer."
                            )
                        rewritten = sanitize_rewritten_text(bridge_items[0].answer)
                        cdp_url = f"bridge-port:{bridge_items[0].port}" if bridge_items[0].port else "bridge"
                    error = validate_rewrite(raw_text, rewritten, config)
                    if error:
                        raise RuntimeError(error)
                    out_path.write_text(rewritten + "\n", encoding="utf-8")
                    status = "success"
                    preview_text = " ".join(rewritten.split())[:220]
                    err = None
                    rewritten_rel = str(out_path.relative_to(self.repo_root))
                    break
                except Exception as exc:  # pylint: disable=broad-except
                    err = f"attempt {attempt}: {exc}"
                    if attempt >= 3:
                        raise RuntimeError(err) from exc
        except Exception as exc:  # pylint: disable=broad-except
            status = "failed"
            err = str(exc)
            preview_text = err
        finally:
            pass
        if config.request_delay_seconds > 0:
            time.sleep(config.request_delay_seconds)
        return {
            "index": index,
            "chapter_no": chapter_no,
            "cdp_url": cdp_url,
            "target": cdp_url or config.bridge_base_url or "bridge",
            "chapter_file": raw_path.name,
            "raw_path": str(raw_path.relative_to(self.repo_root)),
            "rewritten_path": rewritten_rel,
            "status": status,
            "error": err,
            "preview_text": preview_text,
        }

    def run(
        self,
        project_id: str,
        config: RewriteConfig,
        session_id: str | None = None,
        progress_callback: Callable[[dict], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
        resume_only: bool = False,
    ) -> dict:
        project_dir = self.store.session_dir(project_id, session_id)
        source_dir = project_dir / "chapters_text" / "raw"
        output_dir = project_dir / "chapters_text" / "rewritten"
        output_dir.mkdir(parents=True, exist_ok=True)
        raw_files = sorted(source_dir.glob("chapter_*.txt"))
        if not raw_files:
            raise FileNotFoundError(f"No raw chapter files found: {source_dir}")
        if resume_only:
            pending: list[Path] = []
            for raw in raw_files:
                target = output_dir / raw.name
                if not target.exists() or not target.is_file():
                    pending.append(raw)
                    continue
                try:
                    if not target.read_text(encoding="utf-8", errors="replace").strip():
                        pending.append(raw)
                except Exception:
                    pending.append(raw)
            raw_files = pending
            if not raw_files:
                manifest = {
                    "project_id": project_id,
                    "session_id": session_id,
                    "updated_at": utc_now_iso(),
                    "provider": config.provider,
                    "parallel_workers": 0,
                    "cdp_urls": [],
                    "prompt_hash": hashlib.sha256(config.rewrite_prompt.encode("utf-8")).hexdigest()[:16],
                    "summary": {"total": 0, "success": 0, "failed": 0},
                    "items": [],
                    "resume_only": True,
                    "stopped": False,
                }
                manifest_path = project_dir / "rewrite_manifest.json"
                manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
                return manifest

        provider = str(config.provider or "bridge_gemini").strip().lower()
        if provider not in {"bridge_gemini", "fake"}:
            provider = "bridge_gemini"
            config.provider = provider
        cdp_urls = [None]
        requested_workers = max(1, int(config.parallel_workers or 1))
        # Rewrite flow always runs through the browser bridge in production.
        workers = max(1, min(len(raw_files), requested_workers))
        items: list[dict] = []
        prompt_hash = hashlib.sha256(config.rewrite_prompt.encode("utf-8")).hexdigest()[:16]
        completed = 0
        stopped = False

        if workers <= 1:
            for idx, raw_path in enumerate(raw_files, start=1):
                if should_stop and should_stop():
                    stopped = True
                    break
                if progress_callback:
                    progress_callback({
                        "stage": "rewrite",
                        "current": completed,
                        "total": len(raw_files),
                        "chapter": idx,
                        "message": f"Dang gui chapter {idx} toi Gemini",
                    })
                result = self._rewrite_one(idx, raw_path, config, cdp_urls[0], output_dir)
                completed += 1
                if progress_callback:
                    endpoint = result.get("target") or "default"
                    progress_callback({
                        "stage": "rewrite",
                        "current": completed,
                        "total": len(raw_files),
                        "chapter": result["chapter_no"],
                        "message": (
                            f"Da rewrite chapter {result['chapter_no']} qua {endpoint}"
                            if result["status"] == "success"
                            else f"Loi rewrite chapter {result['chapter_no']} qua {endpoint}: {result['error']}"
                        ),
                        "item_status": result["status"],
                        "files_done": completed,
                        "preview_text": result["preview_text"],
                    })
                items.append({
                    "chapter_file": result["chapter_file"],
                    "raw_path": result["raw_path"],
                    "rewritten_path": result["rewritten_path"],
                    "status": result["status"],
                    "error": result["error"],
                })
                if should_stop and should_stop():
                    stopped = True
                    break
        else:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                in_flight: dict = {}
                next_idx = 1
                while next_idx <= len(raw_files) and len(in_flight) < workers:
                    cdp_url = cdp_urls[(next_idx - 1) % len(cdp_urls)]
                    fut = executor.submit(self._rewrite_one, next_idx, raw_files[next_idx - 1], config, cdp_url, output_dir)
                    in_flight[fut] = next_idx
                    next_idx += 1
                while in_flight:
                    fut = next(as_completed(list(in_flight.keys())))
                    in_flight.pop(fut, None)
                    result = fut.result()
                    completed += 1
                    if progress_callback:
                        endpoint = result.get("target") or "default"
                        progress_callback({
                            "stage": "rewrite",
                            "current": completed,
                            "total": len(raw_files),
                            "chapter": result["chapter_no"],
                            "message": (
                                f"Da rewrite chapter {result['chapter_no']} qua {endpoint}"
                                if result["status"] == "success"
                                else f"Loi rewrite chapter {result['chapter_no']} qua {endpoint}: {result['error']}"
                            ),
                            "item_status": result["status"],
                            "files_done": completed,
                            "preview_text": result["preview_text"],
                        })
                    items.append({
                        "chapter_file": result["chapter_file"],
                        "raw_path": result["raw_path"],
                        "rewritten_path": result["rewritten_path"],
                        "status": result["status"],
                        "error": result["error"],
                    })
                    if should_stop and should_stop():
                        stopped = True
                    if not stopped and next_idx <= len(raw_files):
                        cdp_url = cdp_urls[(next_idx - 1) % len(cdp_urls)]
                        nfut = executor.submit(self._rewrite_one, next_idx, raw_files[next_idx - 1], config, cdp_url, output_dir)
                        in_flight[nfut] = next_idx
                        next_idx += 1
            items.sort(key=lambda x: x["chapter_file"])

        manifest = {
            "project_id": project_id,
            "session_id": session_id,
            "updated_at": utc_now_iso(),
            "provider": config.provider,
            "parallel_workers": workers,
            "bridge_base_url": config.bridge_base_url if config.provider == "bridge_gemini" else "",
            "prompt_hash": prompt_hash,
            "summary": {
                "total": len(items),
                "success": sum(1 for item in items if item["status"] == "success"),
                "failed": sum(1 for item in items if item["status"] == "failed"),
            },
            "items": items,
            "resume_only": bool(resume_only),
            "stopped": bool(stopped),
        }
        manifest_path = project_dir / "rewrite_manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return manifest
