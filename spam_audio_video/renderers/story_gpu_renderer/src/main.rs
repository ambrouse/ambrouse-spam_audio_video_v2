mod cli;
mod config;
mod renderer;
mod report;
mod story;

use anyhow::Result;
use clap::Parser;

fn main() -> Result<()> {
    let args = cli::Args::parse();
    match args.command {
        cli::Command::Render(command) => renderer::run_render(command),
    }
}
