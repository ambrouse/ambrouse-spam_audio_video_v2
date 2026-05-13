from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any


class ProgressStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def start(self, job_id: str, label: str, total_units: int) -> dict[str, Any]:
        payload = {
            "job_id": job_id,
            "label": label,
            "status": "running",
            "stage": "queued",
            "message": "Queued",
            "current_units": 0,
            "total_units": max(1, total_units),
            "percent": 0,
            "files_done": 0,
            "preview_text": "",
            "preview_feed": [],
            "stop_requested": False,
            "emergency_stop_requested": False,
            "stop_state": "none",
            "updated_at": self._now(),
        }
        with self._lock:
            self._jobs[job_id] = payload
        return payload

    def update(self, job_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                job = {
                    "job_id": job_id,
                    "label": "Pipeline",
                    "status": "running",
                    "stage": "queued",
                    "message": "Queued",
                    "current_units": 0,
                    "total_units": 1,
                    "percent": 0,
                    "files_done": 0,
                    "preview_text": "",
                    "preview_feed": [],
                    "stop_requested": False,
                    "emergency_stop_requested": False,
                    "stop_state": "none",
                    "updated_at": self._now(),
                }
                self._jobs[job_id] = job
            safe_patch = dict(patch or {})
            incoming_status = str(safe_patch.get("status") or "").strip().lower()
            # Terminal job status must be set only by finish()/mark_stopped().
            if incoming_status and incoming_status != "running":
                safe_patch.pop("status", None)
            stage = str(safe_patch.get("stage") or job.get("stage") or "running")
            feed = list(job.get("preview_feed") or [])

            incoming_message = str(safe_patch.get("message") or "").strip()
            if incoming_message:
                msg_entry = f"[{stage}] {incoming_message}"
                if not feed or feed[-1] != msg_entry:
                    feed.append(msg_entry)

            incoming_preview = str(safe_patch.get("preview_text") or "").strip()
            if incoming_preview:
                preview_entry = f"[{stage}] {incoming_preview}"
                if not feed or feed[-1] != preview_entry:
                    feed.append(preview_entry)
                safe_patch = {**safe_patch, "preview_text": incoming_preview}

            job["preview_feed"] = feed[-30:]
            job.update(safe_patch)
            total = max(1, int(job.get("total_units") or 1))
            current = max(0, min(total, int(job.get("current_units") or 0)))
            job["percent"] = round((current / total) * 100, 1)
            job["updated_at"] = self._now()
            return dict(job)

    def finish(self, job_id: str, success: bool, message: str, result: dict | None = None) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                job = {
                    "job_id": job_id,
                    "label": "Pipeline",
                    "status": "running",
                    "stage": "queued",
                    "message": "Queued",
                    "current_units": 0,
                    "total_units": 1,
                    "percent": 0,
                    "files_done": 0,
                    "preview_text": "",
                    "preview_feed": [],
                    "stop_requested": False,
                    "emergency_stop_requested": False,
                    "stop_state": "none",
                    "updated_at": self._now(),
                }
                self._jobs[job_id] = job
            job.update({
                "status": "success" if success else "failed",
                "message": message,
                "result": result,
                "current_units": job.get("total_units", 1) if success else job.get("current_units", 0),
                "updated_at": self._now(),
            })
            total = max(1, int(job.get("total_units") or 1))
            current = max(0, min(total, int(job.get("current_units") or 0)))
            job["percent"] = round((current / total) * 100, 1)
            return dict(job)

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None

    def request_stop(self, job_id: str, emergency: bool = False) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError(job_id)
            if emergency:
                job["emergency_stop_requested"] = True
                job["stop_requested"] = True
                job["stop_state"] = "force_stopping"
                job["message"] = "Emergency stop requested."
            else:
                job["stop_requested"] = True
                if not job.get("emergency_stop_requested"):
                    job["stop_state"] = "stopping"
                job["message"] = "Stop requested."
            job["updated_at"] = self._now()
            return dict(job)

    def stop_status(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError(job_id)
            return {
                "job_id": job_id,
                "status": job.get("status"),
                "stop_requested": bool(job.get("stop_requested")),
                "emergency_stop_requested": bool(job.get("emergency_stop_requested")),
                "stop_state": job.get("stop_state") or "none",
                "updated_at": job.get("updated_at"),
            }

    def should_stop(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return False
            return bool(job.get("stop_requested") or job.get("emergency_stop_requested"))

    def mark_stopped(self, job_id: str, emergency: bool = False, message: str = "Stopped by user.") -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError(job_id)
            job["status"] = "stopped"
            job["message"] = message
            job["stop_state"] = "force_stopped" if emergency else "stopped"
            job["updated_at"] = self._now()
            return dict(job)
