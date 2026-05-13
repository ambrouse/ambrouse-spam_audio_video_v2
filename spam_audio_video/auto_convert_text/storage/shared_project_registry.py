from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from auto_convert_text.models.dto import utc_now_iso
from auto_convert_text.storage.project_store import slugify


class SharedProjectRegistry:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        self.registry_dir = self.repo_root / "project_registry"
        self.registry_path = self.registry_dir / "projects.json"

    def _read(self) -> dict[str, Any]:
        if not self.registry_path.exists():
            return {"version": 1, "updated_at": utc_now_iso(), "projects": []}
        try:
            data = json.loads(self.registry_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"version": 1, "updated_at": utc_now_iso(), "projects": []}
        if not isinstance(data.get("projects"), list):
            data["projects"] = []
        return data

    def _write(self, data: dict[str, Any]) -> None:
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        data["updated_at"] = utc_now_iso()
        self.registry_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def list_projects(self) -> list[dict[str, Any]]:
        data = self._read()
        projects = data.get("projects", [])
        return sorted(projects, key=lambda item: item.get("updated_at", ""), reverse=True)

    def get_project(self, project_id: str) -> dict[str, Any]:
        wanted = slugify(project_id)
        for project in self.list_projects():
            if project.get("project_id") == wanted:
                return project
        raise FileNotFoundError(f"Shared project not found: {wanted}")

    def upsert_project(self, project_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        wanted = slugify(project_id)
        data = self._read()
        projects = data.get("projects", [])
        now = utc_now_iso()
        existing = None
        for project in projects:
            if project.get("project_id") == wanted:
                existing = project
                break
        if existing is None:
            existing = {
                "project_id": wanted,
                "name": patch.get("name") or wanted,
                "status": "created",
                "created_at": now,
                "updated_at": now,
                "convert": {},
                "tts": {},
                "sessions": [],
            }
            projects.append(existing)

        for key, value in patch.items():
            if key in {"convert", "tts"}:
                existing.setdefault(key, {})
                existing[key].update(value or {})
            else:
                existing[key] = value
        existing["project_id"] = wanted
        existing["updated_at"] = now
        data["projects"] = projects
        self._write(data)
        return existing

    def upsert_session(self, project_id: str, session_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        wanted = slugify(project_id)
        clean_session = slugify(session_id)
        project = self.upsert_project(wanted, {})
        sessions = project.setdefault("sessions", [])
        existing = None
        for session in sessions:
            if session.get("session_id") == clean_session:
                existing = session
                break
        if existing is None:
            existing = {
                "session_id": clean_session,
                "status": "created",
                "created_at": utc_now_iso(),
                "updated_at": utc_now_iso(),
                "convert": {},
                "tts": {},
            }
            sessions.append(existing)
        for key, value in patch.items():
            if key in {"convert", "tts"}:
                existing.setdefault(key, {})
                existing[key].update(value or {})
            else:
                existing[key] = value
        existing["updated_at"] = utc_now_iso()
        project["sessions"] = sorted(sessions, key=lambda item: item.get("created_at", ""), reverse=True)
        return self.upsert_project(wanted, {"sessions": project["sessions"]})

    def delete_session(self, project_id: str, session_id: str) -> dict[str, Any]:
        wanted = slugify(project_id)
        clean_session = slugify(session_id)
        data = self._read()
        removed = 0
        for project in data.get("projects", []):
            if project.get("project_id") != wanted:
                continue
            before = len(project.get("sessions", []))
            project["sessions"] = [s for s in project.get("sessions", []) if s.get("session_id") != clean_session]
            removed = before - len(project["sessions"])
            project["updated_at"] = utc_now_iso()
            break
        self._write(data)
        return {"project_id": wanted, "session_id": clean_session, "removed_registry": removed}

    def update_convert(self, project_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        return self.upsert_project(project_id, {"convert": patch})

    def update_tts(self, project_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        return self.upsert_project(project_id, {"tts": patch})

    def rename_project(self, project_id: str, name: str, notes: str = "") -> dict[str, Any]:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Project name is required.")
        return self.upsert_project(project_id, {"name": clean_name, "notes": notes.strip()})

    def delete_project(self, project_id: str, delete_artifacts: bool = False) -> dict[str, Any]:
        wanted = slugify(project_id)
        data = self._read()
        before = len(data.get("projects", []))
        data["projects"] = [p for p in data.get("projects", []) if p.get("project_id") != wanted]
        removed_registry = before - len(data["projects"])
        removed_artifacts = False
        if delete_artifacts:
            roots = [
                (self.repo_root / "projects_workspace" / "projects").resolve(),
                (self.repo_root / "auto_convert_text" / "data" / "projects").resolve(),
            ]
            for root in roots:
                target = (root / wanted).resolve()
                if target.exists() and target.is_dir() and target.parent == root:
                    shutil.rmtree(target)
                    removed_artifacts = True
        self._write(data)
        return {
            "project_id": wanted,
            "removed_registry": removed_registry,
            "removed_artifacts": removed_artifacts,
        }
