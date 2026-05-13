from __future__ import annotations

import json
import re
from pathlib import Path

from auto_convert_text.models.dto import ChapterRecord, ConvertProject, utc_now_iso


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip().lower()).strip("-")
    return slug or "project"


class ProjectStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.projects_root = self.root / "projects_workspace" / "projects"
        self.legacy_projects_root = self.root / "auto_convert_text" / "data" / "projects"

    def project_dir(self, project_id: str) -> Path:
        return (self.projects_root / slugify(project_id)).resolve()

    def session_id(self, start_chapter: int, chapter_count: int) -> str:
        start = max(1, int(start_chapter))
        end = start + max(1, int(chapter_count)) - 1
        return f"session_ch{start:04d}_to_ch{end:04d}"

    def session_dir(self, project_id: str, session_id: str | None = None) -> Path:
        if not session_id:
            return self.project_dir(project_id)
        return self.project_dir(project_id) / "sessions" / slugify(session_id)

    def raw_dir(self, project_id: str, session_id: str | None = None) -> Path:
        return self.session_dir(project_id, session_id) / "chapters_text" / "raw"

    def logs_dir(self, project_id: str, session_id: str | None = None) -> Path:
        return self.session_dir(project_id, session_id) / "logs"

    def ensure_project_dirs(self, project_id: str, session_id: str | None = None) -> Path:
        project_dir = self.project_dir(project_id)
        session_dir = self.session_dir(project_id, session_id)
        for folder in [
            project_dir,
            project_dir / "chapter_urls",
            project_dir / "sessions",
            session_dir,
            self.raw_dir(project_id, session_id),
            session_dir / "chapters_text" / "rewritten",
            session_dir / "chapters_text" / "audio_clean",
            session_dir / "tts_inputs",
            session_dir / "video",
            session_dir / "video" / "images",
            session_dir / "video" / "prompts",
            session_dir / "video" / "renders",
            session_dir / "video" / "final",
            session_dir / "video" / "manifests",
            self.logs_dir(project_id, session_id),
        ]:
            folder.mkdir(parents=True, exist_ok=True)
        return session_dir

    def write_chapter_urls(
        self,
        project_id: str,
        session_id: str | None,
        urls: list[str],
    ) -> dict:
        self.ensure_project_dirs(project_id, session_id)
        cleaned = [u.strip() for u in urls if isinstance(u, str) and u.strip()]
        project_urls_dir = self.project_dir(project_id) / "chapter_urls"
        latest_path = project_urls_dir / "urls_latest.txt"
        latest_path.write_text("\n".join(cleaned).strip() + ("\n" if cleaned else ""), encoding="utf-8")
        session_path = None
        if session_id:
            session_slug = slugify(session_id)
            session_path = project_urls_dir / f"urls_{session_slug}.txt"
            session_path.write_text("\n".join(cleaned).strip() + ("\n" if cleaned else ""), encoding="utf-8")
        return {
            "count": len(cleaned),
            "latest_path": latest_path,
            "session_path": session_path,
        }

    def read_chapter_urls(self, project_id: str) -> list[str]:
        target = self.project_dir(project_id) / "chapter_urls" / "urls_latest.txt"
        if not target.exists() or not target.is_file():
            return []
        return [
            line.strip()
            for line in target.read_text(encoding="utf-8", errors="replace").splitlines()
            if line.strip()
        ]

    def clear_chapter_urls(self, project_id: str) -> dict:
        project_urls_dir = self.project_dir(project_id) / "chapter_urls"
        if not project_urls_dir.exists():
            return {"removed": 0}
        removed = 0
        for path in project_urls_dir.glob("*.txt"):
            if path.is_file():
                path.unlink(missing_ok=True)
                removed += 1
        return {"removed": removed}

    def rewrite_prompt_path(self, project_id: str, session_id: str | None = None) -> Path:
        if session_id:
            return self.session_dir(project_id, session_id) / "rewrite_prompt.json"
        return self.project_dir(project_id) / "rewrite_prompt.json"

    def session_rewrite_prompt_path(self, project_id: str, session_id: str | None) -> Path | None:
        if not session_id:
            return None
        return self.rewrite_prompt_path(project_id, session_id=session_id)

    def read_rewrite_prompt_config(self, project_id: str, session_id: str | None = None) -> dict:
        # Runtime priority: session-level prompt first, then project-level prompt.
        candidates: list[Path] = []
        session_path = self.session_rewrite_prompt_path(project_id, session_id)
        if session_path is not None:
            candidates.append(session_path)
        candidates.append(self.rewrite_prompt_path(project_id))
        path = None
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                path = candidate
                break
        if path is None:
            return {"story_context": "", "rewrite_prompt": "", "source": "none"}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"story_context": "", "rewrite_prompt": "", "source": "invalid"}
        source = "session" if session_path is not None and path == session_path else "project"
        return {
            "story_context": str(payload.get("story_context") or ""),
            "rewrite_prompt": str(payload.get("rewrite_prompt") or ""),
            "source": source,
        }

    def write_rewrite_prompt_config(
        self,
        project_id: str,
        story_context: str,
        rewrite_prompt: str,
        session_id: str | None = None,
    ) -> dict:
        self.ensure_project_dirs(project_id, session_id)
        path = self.rewrite_prompt_path(project_id, session_id=session_id)
        payload = {
            "project_id": slugify(project_id),
            "session_id": slugify(session_id) if session_id else None,
            "story_context": (story_context or "").strip(),
            "rewrite_prompt": (rewrite_prompt or "").strip(),
            "updated_at": utc_now_iso(),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    def clear_rewrite_prompt_config(self, project_id: str, session_id: str | None = None) -> dict:
        path = self.rewrite_prompt_path(project_id, session_id=session_id)
        if path.exists() and path.is_file():
            path.unlink(missing_ok=True)
            return {"removed": 1}
        return {"removed": 0}

    def session_video_prompt_path(self, project_id: str, session_id: str | None) -> Path | None:
        if not session_id:
            return None
        return self.session_dir(project_id, session_id) / "video_prompt.json"

    def read_video_prompt_config(self, project_id: str, session_id: str | None = None) -> dict:
        path = self.session_video_prompt_path(project_id, session_id)
        if path is None or not path.exists() or not path.is_file():
            return {"story_context": "", "gemini_prompt_template": "", "source": "none"}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"story_context": "", "gemini_prompt_template": "", "source": "invalid"}
        return {
            "story_context": str(payload.get("story_context") or ""),
            "gemini_prompt_template": str(payload.get("gemini_prompt_template") or ""),
            "source": "session",
        }

    def write_video_prompt_config(
        self,
        project_id: str,
        session_id: str,
        story_context: str,
        gemini_prompt_template: str,
    ) -> dict:
        clean_session_id = slugify(session_id)
        self.ensure_project_dirs(project_id, clean_session_id)
        path = self.session_video_prompt_path(project_id, clean_session_id)
        payload = {
            "project_id": slugify(project_id),
            "session_id": clean_session_id,
            "story_context": (story_context or "").strip(),
            "gemini_prompt_template": (gemini_prompt_template or "").strip(),
            "updated_at": utc_now_iso(),
        }
        if path is None:
            return payload
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    def clear_video_prompt_config(self, project_id: str, session_id: str | None = None) -> dict:
        path = self.session_video_prompt_path(project_id, session_id)
        if path is not None and path.exists() and path.is_file():
            path.unlink(missing_ok=True)
            return {"removed": 1}
        return {"removed": 0}

    def migrate_legacy_projects(self) -> dict:
        import shutil

        moved = 0
        removed_empty_legacy = False
        if not self.legacy_projects_root.exists():
            return {"moved": moved, "removed_empty_legacy": removed_empty_legacy}
        self.projects_root.mkdir(parents=True, exist_ok=True)
        for legacy_dir in sorted(self.legacy_projects_root.glob("*")):
            if not legacy_dir.is_dir():
                continue
            target_dir = self.projects_root / legacy_dir.name
            if target_dir.exists():
                continue
            shutil.move(str(legacy_dir), str(target_dir))
            moved += 1
        if not any(self.legacy_projects_root.iterdir()):
            self.legacy_projects_root.rmdir()
            removed_empty_legacy = True
        return {"moved": moved, "removed_empty_legacy": removed_empty_legacy}

    def write_project(self, project: ConvertProject, session_id: str | None = None) -> Path:
        self.ensure_project_dirs(project.project_id, session_id)
        project.updated_at = utc_now_iso()
        path = self.project_dir(project.project_id) / "project.json"
        path.write_text(json.dumps(project.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        if session_id:
            session_path = self.session_dir(project.project_id, session_id) / "session.json"
            session_payload = project.to_dict()
            session_payload["session_id"] = slugify(session_id)
            session_payload["chapter_start"] = project.start_chapter
            session_payload["chapter_end"] = project.start_chapter + project.chapter_count - 1
            session_path.write_text(json.dumps(session_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def write_chapter_text(self, project_id: str, chapter_no: int, text: str, session_id: str | None = None) -> Path:
        self.ensure_project_dirs(project_id, session_id)
        path = self.raw_dir(project_id, session_id) / f"chapter_{chapter_no:04d}.txt"
        path.write_text(text.strip() + "\n", encoding="utf-8")
        return path

    def write_manifest(
        self,
        project_id: str,
        project: ConvertProject,
        chapters: list[ChapterRecord],
        session_id: str | None = None,
    ) -> Path:
        self.ensure_project_dirs(project_id, session_id)
        payload = {
            "project": project.to_dict(),
            "session_id": slugify(session_id) if session_id else None,
            "chapter_start": project.start_chapter,
            "chapter_end": project.start_chapter + project.chapter_count - 1,
            "summary": {
                "requested": project.chapter_count,
                "success": sum(1 for item in chapters if item.status == "success"),
                "failed": sum(1 for item in chapters if item.status == "failed"),
                "updated_at": utc_now_iso(),
            },
            "chapters": [item.__dict__ for item in chapters],
        }
        path = self.session_dir(project_id, session_id) / "chapters_manifest.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def list_projects(self) -> list[dict]:
        roots = [self.projects_root]
        if self.legacy_projects_root.exists():
            roots.append(self.legacy_projects_root)
        projects: list[dict] = []
        seen: set[str] = set()
        for root in roots:
            if not root.exists():
                continue
            for path in sorted(root.glob("*/project.json")):
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    continue
                project_id = str(payload.get("project_id") or "")
                if project_id and project_id in seen:
                    continue
                if project_id:
                    seen.add(project_id)
                projects.append(payload)
        return projects

    def read_manifest(self, project_id: str) -> dict:
        path = self.project_dir(project_id) / "chapters_manifest.json"
        if not path.exists():
            legacy = self.legacy_projects_root / slugify(project_id) / "chapters_manifest.json"
            if legacy.exists():
                return json.loads(legacy.read_text(encoding="utf-8"))
            raise FileNotFoundError(f"Manifest not found for project: {project_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def read_session_manifest(self, project_id: str, session_id: str) -> dict:
        path = self.session_dir(project_id, session_id) / "chapters_manifest.json"
        if not path.exists():
            legacy = self.legacy_projects_root / slugify(project_id) / "sessions" / slugify(session_id) / "chapters_manifest.json"
            if legacy.exists():
                return json.loads(legacy.read_text(encoding="utf-8"))
            raise FileNotFoundError(f"Manifest not found for project/session: {project_id}/{session_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def delete_session(self, project_id: str, session_id: str) -> bool:
        import shutil

        sessions_root = (self.project_dir(project_id) / "sessions").resolve()
        target = (sessions_root / slugify(session_id)).resolve()
        if target.exists() and target.is_dir() and target.parent == sessions_root:
            shutil.rmtree(target)
            return True
        return False
