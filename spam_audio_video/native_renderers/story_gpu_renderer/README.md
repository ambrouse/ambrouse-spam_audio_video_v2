# Story GPU Renderer

Experimental native renderer for the 4K60 pipeline.

Current status:

- Phase: MVP scaffold and speed-ceiling probe.
- This crate is not production-ready.
- It must not be used as a passing renderer until both benchmark and quality gates pass.

Target:

- 30s 4K60 one-scene output in `<= 12.84s` for the 8x target.
- Strong target is `<= 8.56s` for 12x.

Run:

```powershell
cargo run --release -- render --config path\to\renderer_input.json --report path\to\renderer_report.json
```

The first MVP intentionally writes a report that marks `quality_complete=false`; it is a speed probe, not a final renderer.
