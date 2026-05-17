use std::path::PathBuf;

use clap::{Parser, Subcommand};

#[derive(Debug, Parser)]
#[command(author, version, about = "Production Rust/D3D11/NVENC story renderer")]
pub struct Args {
    #[command(subcommand)]
    pub command: Command,
}

#[derive(Debug, Subcommand)]
pub enum Command {
    Render(RenderCommand),
}

#[derive(Debug, Parser)]
pub struct RenderCommand {
    #[arg(long)]
    pub config: PathBuf,

    #[arg(long)]
    pub report: PathBuf,

    #[arg(long)]
    pub output: Option<PathBuf>,
}
