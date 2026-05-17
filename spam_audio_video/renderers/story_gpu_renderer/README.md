# Story GPU Renderer

Production story renderer for the video pipeline.

Current status:

- Rust/D3D11/NVENC full-timeline renderer.
- Used directly by the main web video pipeline for 16:9 `60fps` `h264_nvenc`
  outputs.
- FFmpeg remains only for MP4 remux and final audio mux.

Run:

```powershell
cargo run --release -- render --config path\to\renderer_input.json --report path\to\renderer_report.json
```
