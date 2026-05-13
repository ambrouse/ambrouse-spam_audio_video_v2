from __future__ import annotations

import argparse
import json
from pathlib import Path

from auto_convert_text.pipeline.collector import Collector


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect story chapters into raw txt files.")
    parser.add_argument("--story-url", required=True)
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--project-name", default="")
    parser.add_argument("--project-id", default="")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()

    result = Collector(args.repo_root).collect(
        story_url=args.story_url,
        start_chapter=args.start,
        chapter_count=args.count,
        project_name=args.project_name or None,
        project_id=args.project_id or None,
    )
    print(json.dumps(result.__dict__ | {"chapters": [c.__dict__ for c in result.chapters]}, ensure_ascii=False, indent=2))
    return 0 if result.failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
