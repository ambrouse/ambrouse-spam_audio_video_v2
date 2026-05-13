from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ChapterRef:
    index: int
    title: str
    url: str


@dataclass
class ChapterContent:
    title: str
    url: str
    text: str


@dataclass
class ChapterRecord:
    chapter_no: int
    title: str
    source_url: str
    status: str
    raw_text_path: str | None = None
    error: str | None = None


@dataclass
class ConvertProject:
    project_id: str
    name: str
    story_url: str
    domain: str
    start_chapter: int
    chapter_count: int
    status: str = "created"
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict:
        return asdict(self)

