use std::path::PathBuf;

use clap::{Parser, Subcommand};

#[derive(Debug, Parser)]
#[command(author, version, about = "Experimental native 4K60 story renderer")]
pub struct Args {
    #[command(subcommand)]
    pub command: Command,
}

#[derive(Debug, Subcommand)]
pub enum Command {
    Render(RenderCommand),
    ProbeNative(ProbeNativeCommand),
    EncodeCeiling(EncodeCeilingCommand),
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

#[derive(Debug, Parser)]
pub struct ProbeNativeCommand {
    #[arg(long)]
    pub report: PathBuf,
}

#[derive(Debug, Parser)]
pub struct EncodeCeilingCommand {
    #[arg(long)]
    pub output: PathBuf,

    #[arg(long)]
    pub report: PathBuf,

    #[arg(long, default_value_t = 3840)]
    pub width: u32,

    #[arg(long, default_value_t = 2160)]
    pub height: u32,

    #[arg(long, default_value_t = 60)]
    pub fps: u32,

    #[arg(long, default_value_t = 30.0)]
    pub seconds: f64,

    #[arg(long, default_value_t = 18_000_000)]
    pub bitrate: u32,

    #[arg(long, default_value = "nv12")]
    pub buffer_format: String,
}
