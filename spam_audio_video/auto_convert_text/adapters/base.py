from __future__ import annotations

import abc
import html
import json
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx

from auto_convert_text.models.dto import ChapterContent, ChapterRef


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
)


class AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attrs_map = {k.lower(): v for k, v in attrs}
        href = attrs_map.get("href")
        if href:
            self._href = href
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            text = normalize_spaces(" ".join(self._text))
            self.anchors.append((self._href, text))
            self._href = None
            self._text = []


class TextParser(HTMLParser):
    BLOCK_TAGS = {
        "p", "div", "br", "li", "tr", "section", "article", "h1", "h2", "h3",
        "h4", "h5", "blockquote",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        name = tag.lower()
        if name in {"script", "style", "noscript", "svg", "canvas"}:
            self._skip_depth += 1
            return
        if self._skip_depth == 0 and name in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        name = tag.lower()
        if name in {"script", "style", "noscript", "svg", "canvas"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth == 0 and name in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self.parts.append(data)

    def text(self) -> str:
        return normalize_text("\n".join(self.parts))


def normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", repair_mojibake(html.unescape(value or ""))).strip()


def normalize_text(value: str) -> str:
    value = repair_mojibake(html.unescape(value or ""))
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    lines = [normalize_spaces(line) for line in value.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines).strip()


def repair_mojibake(value: str) -> str:
    text = value or ""
    noisy = sum(text.count(ch) for ch in ["Ã", "Â", "Ä", "Å", "Æ", "á»", "â€œ", "â€"])
    if noisy < 3:
        return text
    try:
        repaired = text.encode("latin1", errors="ignore").decode("utf-8", errors="ignore")
    except Exception:
        return text
    repaired_noisy = sum(repaired.count(ch) for ch in ["Ã", "Â", "Ä", "Å", "Æ", "á»", "â€œ", "â€"])
    return repaired if repaired and repaired_noisy < noisy else text


def strip_noise_blocks(raw_html: str) -> str:
    patterns = [
        r"<script\b.*?</script>",
        r"<style\b.*?</style>",
        r"<noscript\b.*?</noscript>",
        r"<header\b.*?</header>",
        r"<footer\b.*?</footer>",
        r"<nav\b.*?</nav>",
        r"<aside\b.*?</aside>",
    ]
    cleaned = raw_html
    for pattern in patterns:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.I | re.S)
    return cleaned


def html_to_text(raw_html: str) -> str:
    parser = TextParser()
    parser.feed(strip_noise_blocks(raw_html))
    return parser.text()


def extract_title(raw_html: str, fallback: str) -> str:
    for pattern in [r"<h1[^>]*>(.*?)</h1>", r"<title[^>]*>(.*?)</title>"]:
        match = re.search(pattern, raw_html, flags=re.I | re.S)
        if match:
            title = html_to_text(match.group(1))
            if title:
                return title[:180]
    return fallback


def extract_next_data_chapters(story_url: str, raw_html: str) -> list[ChapterRef]:
    match = re.search(
        r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
        raw_html,
        flags=re.I | re.S,
    )
    if not match:
        return []
    try:
        payload = json.loads(html.unescape(match.group(1)))
    except json.JSONDecodeError:
        return []

    refs: list[ChapterRef] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            url_value = (
                node.get("url")
                or node.get("href")
                or node.get("slug")
                or node.get("chapterUrl")
                or node.get("path")
            )
            title_value = node.get("title") or node.get("name") or node.get("chapterName")
            if isinstance(url_value, str) and isinstance(title_value, str):
                lower = f"{url_value} {title_value}".lower()
                if any(key in lower for key in ["chuong", "chapter", "chap"]):
                    refs.append(
                        ChapterRef(
                            index=len(refs) + 1,
                            title=normalize_spaces(title_value),
                            url=urljoin(story_url, url_value),
                        )
                    )
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return dedupe_chapters(refs)


def dedupe_chapters(refs: list[ChapterRef]) -> list[ChapterRef]:
    seen: set[str] = set()
    unique: list[ChapterRef] = []
    for ref in refs:
        key = ref.url.split("#", 1)[0].rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        unique.append(ChapterRef(index=len(unique) + 1, title=ref.title, url=ref.url))
    return unique


class BaseAdapter(abc.ABC):
    domain = ""
    chapter_keywords = ("chuong", "chapter", "chap")

    @classmethod
    def detect(cls, url: str) -> bool:
        return cls.domain in urlparse(url).netloc.lower()

    def client(self) -> httpx.Client:
        return httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
            follow_redirects=True,
            timeout=httpx.Timeout(20.0, connect=10.0),
        )

    def fetch_html(self, url: str) -> str:
        with self.client() as client:
            response = client.get(url)
            response.raise_for_status()
            raw = response.content
            # Prefer UTF-8 first because most modern VN novel sites are UTF-8
            # while HTTP headers can be missing or wrong.
            try:
                return raw.decode("utf-8")
            except UnicodeDecodeError:
                pass
            if response.encoding:
                try:
                    return raw.decode(response.encoding, errors="replace")
                except LookupError:
                    pass
            return raw.decode("utf-8", errors="replace")

    def fetch_story_meta(self, story_url: str) -> dict:
        raw_html = self.fetch_html(story_url)
        return {"title": extract_title(raw_html, fallback=story_url), "domain": self.domain}

    def fetch_chapter_list(self, story_url: str) -> list[ChapterRef]:
        raw_html = self.fetch_html(story_url)
        refs = extract_next_data_chapters(story_url, raw_html)
        if refs:
            return refs

        parser = AnchorParser()
        parser.feed(raw_html)
        candidates: list[ChapterRef] = []
        story_host = urlparse(story_url).netloc.lower()
        for href, text in parser.anchors:
            absolute = urljoin(story_url, href)
            parsed = urlparse(absolute)
            if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() != story_host:
                continue
            haystack = f"{href} {text}".lower()
            if not any(keyword in haystack for keyword in self.chapter_keywords):
                continue
            if not text:
                text = f"Chapter {len(candidates) + 1}"
            candidates.append(ChapterRef(index=len(candidates) + 1, title=text[:180], url=absolute))
        return dedupe_chapters(candidates)

    def fetch_chapter(self, chapter_url: str) -> ChapterContent:
        raw_html = self.fetch_html(chapter_url)
        title = extract_title(raw_html, fallback=chapter_url)
        text = html_to_text(raw_html)
        return ChapterContent(title=title, url=chapter_url, text=text)

    def normalize_chapter_no(self, raw: str) -> int | None:
        match = re.search(r"(\d+)", raw or "")
        return int(match.group(1)) if match else None
