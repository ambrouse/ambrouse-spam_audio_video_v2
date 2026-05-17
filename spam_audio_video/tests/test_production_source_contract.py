from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = REPO_ROOT.parent


class ProductionSourceContractTest(unittest.TestCase):
    def test_video_source_has_no_segmented_renderer_contract(self) -> None:
        scan_paths = [
            REPO_ROOT / "auto_generate_video" / "pipeline.py",
            REPO_ROOT / "source_full" / "backend" / "video_service.py",
            REPO_ROOT / ".env.example",
            PROJECT_ROOT / "scripts" / "portable" / "build_portable_release.ps1",
        ]
        banned_tokens = [
            "clips_native",
            "native_timeline",
            "native_gpu_renderer",
            "SPAM_VIDEO_NATIVE",
            "native_renderers",
        ]
        for path in scan_paths:
            content = path.read_text(encoding="utf-8")
            for token in banned_tokens:
                self.assertNotIn(token, content, f"{token} still present in {path}")

    def test_run_full_remains_instance_method(self) -> None:
        source_path = REPO_ROOT / "auto_generate_video" / "pipeline.py"
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        video_pipeline = next(
            node for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "VideoPipeline"
        )
        run_full = next(
            node for node in video_pipeline.body
            if isinstance(node, ast.FunctionDef) and node.name == "run_full"
        )
        decorator_names = {
            dec.id for dec in run_full.decorator_list if isinstance(dec, ast.Name)
        }
        self.assertNotIn("staticmethod", decorator_names)
        self.assertEqual(run_full.args.args[0].arg, "self")

    def test_audio_merge_is_streaming_not_full_concatenate(self) -> None:
        worker_path = REPO_ROOT / "auto_text_to_voice" / "vieneu_worker.py"
        source = worker_path.read_text(encoding="utf-8")
        start = source.index("def _merge_wav_files_with_pauses")
        end = source.index("\ndef _smart_trim_edges", start)
        merge_source = source[start:end]
        self.assertIn("sf.SoundFile", merge_source)
        self.assertIn("writer.write", merge_source)
        self.assertNotIn("np.concatenate", merge_source)

    def test_tts_worker_prefers_short_runtime_python(self) -> None:
        service_source = (REPO_ROOT / "source_full" / "backend" / "pipeline_service.py").read_text(encoding="utf-8")
        setup_source = (REPO_ROOT / "setup.sh").read_text(encoding="utf-8")
        self.assertIn("SPAM_TTS_PYTHON", service_source)
        self.assertIn(".vieneu-", service_source)
        self.assertIn("export SPAM_TTS_PYTHON", setup_source)

    def test_story_renderer_source_is_the_only_renderer_tree(self) -> None:
        self.assertTrue((REPO_ROOT / "renderers" / "story_gpu_renderer" / "Cargo.toml").exists())
        self.assertFalse((REPO_ROOT / "native_renderers").exists())


if __name__ == "__main__":
    unittest.main()
