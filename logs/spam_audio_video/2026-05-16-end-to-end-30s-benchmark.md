# 2026-05-16 End-to-End 30s Benchmark

## Request
- Run one real near-30s sample with both audio and video, collect everything into one folder, and write a detailed report for output review.

## Artifact
- Folder: `spam_audio_video/benchmarks/end_to_end_30s/20260516_234237_real_first_run_audio_plus_real_4k60`
- Main report: `reports/benchmark.json`
- Human summary: `reports/summary.md`
- Main review file: `final/final_eval_lossless_audio.mkv`
- MP4 preview: `final/final_preview_mp4_aac.mp4`
- Raw TTS WAV: `final/combined.wav`
- Screenshots: `screenshots/frame_05s.jpg`, `screenshots/frame_20s.jpg`

## Results
- Audio was generated from 4 real TTS chunks with cache disabled: 0 cache hits, 4 misses.
- Audio duration: 34.299s.
- Audio runtime: 31.491s in the TTS benchmark report, 31.684s by wrapper command wall clock.
- Video rendered through the real current FFmpeg/NVENC 4K60 path.
- Video duration: 34.300s.
- Video runtime: 116.999s in the render benchmark report, 117.635s by wrapper command wall clock.
- Total wrapper wall time from child command logs: 152.427s.
- Final lossless review mux uses H.264 video copy plus PCM s16le audio in MKV.

## Quality Checks
- Final video probe: 3840x2160, 60/1 fps.
- Final lossless review audio probe: pcm_s16le, 44100 Hz, mono.
- Audio scan: mean volume -18.6 dB, max volume -3.8 dB, no >=0.5s silence detected at -35 dB threshold.
- Visual frame checks at 5s and 20s show the expected rendered scene, logo, motion crop, and overlay effects.

## Notes
- This was a real first-run TTS sample for the selected text chunks, not a cache-hit sample.
- The run is suitable for manual quality review, but it does not meet the earlier performance targets: audio is about 1.09x realtime and video about 0.29x realtime on this current pipeline.
