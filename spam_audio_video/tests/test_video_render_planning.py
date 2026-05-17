from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from auto_generate_video.pipeline import VideoPipeline


class VideoRenderPlanningTest(unittest.TestCase):
    def test_current_audio_duration_avoids_extra_tail_clip(self) -> None:
        images = [Path(f"scene_{idx:04d}.png") for idx in range(1, 6)]

        current_sequence = VideoPipeline._build_render_image_sequence(
            images,
            audio_seconds=1858.183,
            per_scene_duration=60.0,
            transition_seconds=1.2,
            project_id="test-1",
            session_id="session_ch0001_to_ch0010",
        )
        stale_sequence = VideoPipeline._build_render_image_sequence(
            images,
            audio_seconds=1936.191,
            per_scene_duration=60.0,
            transition_seconds=1.2,
            project_id="test-1",
            session_id="session_ch0001_to_ch0010",
        )

        self.assertEqual(len(current_sequence), 32)
        self.assertEqual(len(stale_sequence), 33)


if __name__ == "__main__":
    unittest.main()
