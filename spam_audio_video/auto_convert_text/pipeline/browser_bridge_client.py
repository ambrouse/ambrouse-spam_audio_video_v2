from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx


DEFAULT_BRIDGE_BASE_URL = "http://127.0.0.1:8008"


class BrowserBridgeError(RuntimeError):
    def __init__(self, message: str, *, payload: dict | None = None) -> None:
        super().__init__(message)
        self.payload = payload or {}


@dataclass
class BridgeChatItem:
    prompt: str
    success: bool
    answer: str
    port: int | None = None
    request_id: str = ""
    error_code: str | None = None
    error_message: str | None = None
    elapsed_ms: int = 0


@dataclass
class BridgeImageItem:
    prompt: str
    success: bool
    images: list[dict]
    port: int | None = None
    request_id: str = ""
    error_code: str | None = None
    error_message: str | None = None
    elapsed_ms: int = 0


class BrowserBridgeClient:
    def __init__(self, base_url: str | None = None, timeout_s: float = 600.0) -> None:
        self.base_url = (base_url or DEFAULT_BRIDGE_BASE_URL).strip().rstrip("/")
        self.timeout_s = max(10.0, float(timeout_s or 600.0))

    def open_ports(self, ports: list[int], force_reconnect: bool = False) -> dict:
        payload = {
            "ports": self._sanitize_ports(ports),
            "force_reconnect": bool(force_reconnect),
        }
        return self._post_json("/v1/web/open", payload, timeout_s=max(30.0, self.timeout_s))

    def ping_ports(self, ports: list[int] | None = None) -> dict:
        clean_ports = self._sanitize_ports(ports or [])
        if clean_ports:
            return self._post_json("/v1/ports/ping", {"ports": clean_ports}, timeout_s=20.0)
        return self._get_json("/v1/ports/ping", timeout_s=20.0)

    def chat(
        self,
        provider: str,
        prompts: list[str],
        mode: str | None = "fast",
        timeout_s: float | None = None,
    ) -> tuple[dict, list[BridgeChatItem]]:
        clean_provider = self._provider(provider)
        clean_prompts = self._clean_prompts(prompts)
        payload: dict = {
            "prompt": clean_prompts,
            "timeout_s": max(10.0, float(timeout_s or self.timeout_s)),
        }
        if clean_provider == "gemini" and mode:
            payload["mode"] = mode
        data = self._post_json(f"/v1/chat/{clean_provider}", payload, timeout_s=payload["timeout_s"] + 30.0)
        request_id = str(data.get("request_id") or "")
        results = data.get("results")
        items: list[BridgeChatItem] = []
        if isinstance(results, list) and results:
            for index, row in enumerate(results):
                if not isinstance(row, dict):
                    continue
                items.append(
                    BridgeChatItem(
                        prompt=str(row.get("prompt") or clean_prompts[min(index, len(clean_prompts) - 1)]),
                        success=bool(row.get("success")),
                        answer=str(row.get("answer") or ""),
                        port=self._optional_int(row.get("port")),
                        request_id=request_id,
                        error_code=row.get("error_code"),
                        error_message=row.get("error_message"),
                        elapsed_ms=int(row.get("elapsed_ms") or 0),
                    )
                )
        else:
            items.append(
                BridgeChatItem(
                    prompt=clean_prompts[0],
                    success=bool(data.get("success")),
                    answer=str(data.get("answer") or ""),
                    port=self._optional_int(data.get("used_port")),
                    request_id=request_id,
                    error_code=data.get("error_code"),
                    error_message=data.get("error_message"),
                    elapsed_ms=int(data.get("elapsed_ms") or 0),
                )
            )
        return data, items

    def image(
        self,
        provider: str,
        prompts: list[str],
        max_images: int = 1,
        timeout_s: float | None = None,
    ) -> tuple[dict, list[BridgeImageItem]]:
        clean_provider = self._provider(provider)
        clean_prompts = self._clean_prompts(prompts)
        payload = {
            "prompt": clean_prompts,
            "timeout_s": max(20.0, float(timeout_s or self.timeout_s)),
            "max_images": max(1, min(4, int(max_images or 1))),
            "response_format": "json",
        }
        data = self._post_json(f"/v1/image/{clean_provider}", payload, timeout_s=payload["timeout_s"] + 30.0)
        request_id = str(data.get("request_id") or "")
        results = data.get("results")
        items: list[BridgeImageItem] = []
        if isinstance(results, list) and results:
            for index, row in enumerate(results):
                if not isinstance(row, dict):
                    continue
                images = row.get("images") if isinstance(row.get("images"), list) else []
                items.append(
                    BridgeImageItem(
                        prompt=str(row.get("prompt") or clean_prompts[min(index, len(clean_prompts) - 1)]),
                        success=bool(row.get("success")),
                        images=[dict(item) for item in images if isinstance(item, dict)],
                        port=self._optional_int(row.get("port")),
                        request_id=request_id,
                        error_code=row.get("error_code"),
                        error_message=row.get("error_message"),
                        elapsed_ms=int(row.get("elapsed_ms") or 0),
                    )
                )
        else:
            images = data.get("images") if isinstance(data.get("images"), list) else []
            items.append(
                BridgeImageItem(
                    prompt=clean_prompts[0],
                    success=bool(data.get("success")),
                    images=[dict(item) for item in images if isinstance(item, dict)],
                    port=self._optional_int(data.get("used_port")),
                    request_id=request_id,
                    error_code=data.get("error_code"),
                    error_message=data.get("error_message"),
                    elapsed_ms=int(data.get("elapsed_ms") or 0),
                )
            )
        return data, items

    def save_bridge_image(self, image: dict, target_path: Path) -> Path:
        local_path = str(image.get("local_path") or "").strip()
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if local_path:
            source = Path(local_path)
            if source.exists() and source.is_file():
                final = target_path.with_suffix(source.suffix or target_path.suffix)
                shutil.copy2(source, final)
                return final
        download_url = str(image.get("download_url") or "").strip()
        if not download_url:
            raise BrowserBridgeError("Bridge image response did not include local_path or download_url.", payload=image)
        if download_url.startswith("http://") or download_url.startswith("https://"):
            url = download_url
        else:
            url = urljoin(f"{self.base_url}/", download_url.lstrip("/"))
        suffix = self._suffix_from_image(image, url, target_path.suffix or ".png")
        final = target_path.with_suffix(suffix)
        with httpx.Client(timeout=max(30.0, self.timeout_s)) as client:
            response = client.get(url)
            response.raise_for_status()
            final.write_bytes(response.content)
        if final.stat().st_size <= 0:
            raise BrowserBridgeError("Downloaded bridge image is empty.", payload=image)
        return final

    def _get_json(self, path: str, timeout_s: float) -> dict:
        url = f"{self.base_url}{path}"
        try:
            with httpx.Client(timeout=timeout_s) as client:
                response = client.get(url, headers={"Accept": "application/json"})
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            raise BrowserBridgeError(f"Bridge request failed: GET {url}: {exc}") from exc
        if not isinstance(data, dict):
            raise BrowserBridgeError(f"Bridge returned non-object JSON for GET {url}.")
        return data

    def _post_json(self, path: str, payload: dict, timeout_s: float) -> dict:
        url = f"{self.base_url}{path}"
        try:
            with httpx.Client(timeout=timeout_s) as client:
                response = client.post(url, json=payload, headers={"Accept": "application/json"})
                data = self._response_json(response)
                if response.status_code >= 400:
                    message = str(data.get("error_message") or data.get("detail") or response.text[:240])
                    raise BrowserBridgeError(f"Bridge returned HTTP {response.status_code}: {message}", payload=data)
        except BrowserBridgeError:
            raise
        except Exception as exc:
            raise BrowserBridgeError(f"Bridge request failed: POST {url}: {exc}") from exc
        if not isinstance(data, dict):
            raise BrowserBridgeError(f"Bridge returned non-object JSON for POST {url}.")
        return data

    @staticmethod
    def _response_json(response: httpx.Response) -> dict:
        try:
            data = response.json()
        except Exception as exc:
            raise BrowserBridgeError(f"Bridge did not return JSON. Body preview: {response.text[:240]}") from exc
        if not isinstance(data, dict):
            raise BrowserBridgeError("Bridge JSON response must be an object.")
        return data

    @staticmethod
    def _sanitize_ports(ports: list[int]) -> list[int]:
        clean = []
        for value in ports or []:
            try:
                port = int(value)
            except Exception:
                continue
            if 1 <= port <= 65535:
                clean.append(port)
        return sorted(set(clean))

    @staticmethod
    def _clean_prompts(prompts: list[str]) -> list[str]:
        clean = [str(item or "").strip() for item in prompts if str(item or "").strip()]
        if not clean:
            raise BrowserBridgeError("At least one prompt is required.")
        return clean

    @staticmethod
    def _provider(provider: str) -> str:
        clean = str(provider or "").strip().lower()
        if clean not in {"gemini", "gpt"}:
            raise BrowserBridgeError(f"Unsupported bridge provider: {provider}")
        return clean

    @staticmethod
    def _optional_int(value: object) -> int | None:
        try:
            if value is None or value == "":
                return None
            return int(value)
        except Exception:
            return None

    @staticmethod
    def _suffix_from_image(image: dict, url: str, default: str) -> str:
        content_type = str(image.get("content_type") or "").lower()
        if "jpeg" in content_type or "jpg" in content_type:
            return ".jpg"
        if "webp" in content_type:
            return ".webp"
        if "png" in content_type:
            return ".png"
        parsed = urlparse(url)
        suffix = Path(parsed.path).suffix.lower()
        return suffix if suffix in {".png", ".jpg", ".jpeg", ".webp"} else default
