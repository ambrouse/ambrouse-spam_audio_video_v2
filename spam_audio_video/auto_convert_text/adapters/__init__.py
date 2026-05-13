from __future__ import annotations

from urllib.parse import urlparse

from .base import BaseAdapter
from .apptruyenchu_pro import ApptruyenchuProAdapter
from .generic import GenericStoryAdapter
from .metruyenchu_co import MetruyenchuCoAdapter
from .metruyenchu_com_vn import MetruyenchuComVnAdapter
from .metruyenchu_org import MetruyenchuOrgAdapter
from .truyenchucv_org import TruyenchucvOrgAdapter


ADAPTERS: list[type[BaseAdapter]] = [
    ApptruyenchuProAdapter,
    MetruyenchuComVnAdapter,
    MetruyenchuOrgAdapter,
    MetruyenchuCoAdapter,
    TruyenchucvOrgAdapter,
]


def adapter_for_url(url: str) -> BaseAdapter:
    host = urlparse(url).netloc.lower()
    for adapter_cls in ADAPTERS:
        if adapter_cls.detect(url):
            return adapter_cls()
    return GenericStoryAdapter(domain=host or "generic")
