from __future__ import annotations

import os
from pathlib import Path

import uvicorn


def load_env_file() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = value.strip().strip('"').strip("'")


if __name__ == "__main__":
    load_env_file()
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("backend.server:app", host="0.0.0.0", port=port, reload=False)
