mod cli;
mod config;
mod native_encode;
mod native_probe;
mod native_story;
mod renderer;
mod report;

use anyhow::Result;
use clap::Parser;

fn main() -> Result<()> {
    let args = cli::Args::parse();
    match args.command {
        cli::Command::Render(command) => renderer::run_render(command),
        cli::Command::ProbeNative(command) => native_probe::run_probe(command),
        cli::Command::EncodeCeiling(command) => native_encode::run_encode_ceiling(command),
    }
}
