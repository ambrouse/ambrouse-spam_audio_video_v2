from __future__ import annotations

from .base import BaseAdapter


class GenericStoryAdapter(BaseAdapter):
    def __init__(self, domain: str = "generic") -> None:
        self.domain = domain

