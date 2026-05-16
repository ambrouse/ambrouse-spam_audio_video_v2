from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from auto_convert_text.pipeline.audio_cleaner import clean_for_audio
from auto_convert_text.pipeline.simple_chunker import SimpleChunker


class TtsChunkPolicyTest(unittest.TestCase):
    def test_audio_clean_removes_commas_and_keeps_periods(self) -> None:
        text = "Thien Dau de quoc, Thanh Hon thon. Ngay hom nay, la le thuc tinh vo hon."
        cleaned = clean_for_audio(text)
        self.assertNotIn(",", cleaned)
        self.assertTrue(cleaned.endswith("."))
        self.assertIn("Thanh Hon thon.", cleaned)

    def test_chunker_clamps_min_words_and_outputs_period_only_chunks(self) -> None:
        sentence_one = " ".join(f"mot{i}" for i in range(18)) + "."
        sentence_two = " ".join(f"hai{i}" for i in range(18)) + "."
        sentence_three = " ".join(f"ba{i}" for i in range(35)) + "."

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session_dir = root / "projects_workspace" / "projects" / "proj" / "sessions" / "sess"
            source_dir = session_dir / "chapters_text" / "audio_clean"
            source_dir.mkdir(parents=True)
            (source_dir / "chapter_0001.txt").write_text(
                f"{sentence_one} Doan co dau phay, van khong duoc cat o dau phay. {sentence_two} {sentence_three}",
                encoding="utf-8",
            )

            manifest = SimpleChunker(root).run("proj", session_id="sess", min_words=10, max_words=64)
            self.assertEqual(manifest["min_words"], 30)
            self.assertEqual(manifest["punctuation_policy"], "period_only")

            tts_files = sorted((session_dir / "tts_inputs").glob("text_*.txt"))
            self.assertTrue(tts_files)
            for path in tts_files:
                content = path.read_text(encoding="utf-8").strip()
                self.assertNotIn(",", content)
                self.assertTrue(content.endswith("."))

            manifest_path = session_dir / "chunks_manifest.json"
            saved_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(saved_manifest["summary"]["comma_violations"], 0)
            self.assertEqual(saved_manifest["summary"]["non_period_endings"], 0)


if __name__ == "__main__":
    unittest.main()
