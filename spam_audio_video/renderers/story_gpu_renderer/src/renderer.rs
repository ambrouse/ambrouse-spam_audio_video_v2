use std::time::Instant;

use anyhow::Result;

use crate::{cli::RenderCommand, config::RendererInput, report::RendererReport, story};

pub fn run_render(command: RenderCommand) -> Result<()> {
    let input = RendererInput::read(&command.config)?;
    let output_path = command.output.unwrap_or_else(|| input.output_path.clone());
    if let Some(parent) = output_path.parent() {
        std::fs::create_dir_all(parent)?;
    }

    let started = Instant::now();
    let encode = story::run_story_render(&input, &output_path)?;
    let elapsed = started.elapsed();
    let report =
        RendererReport::production_timeline(&output_path, elapsed, encode.encoder, encode.notes)?;
    report.write(&command.report)?;

    // Keep full FFmpeg logs next to the requested report for benchmark evidence.
    if let Some(parent) = command.report.parent() {
        std::fs::write(parent.join("stdout.log"), encode.stdout)?;
        std::fs::write(parent.join("stderr.log"), encode.stderr)?;
    }
    Ok(())
}
