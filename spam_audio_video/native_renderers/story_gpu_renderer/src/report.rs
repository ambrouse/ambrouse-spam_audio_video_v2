use std::{fs, path::Path, time::Duration};

use anyhow::{Context, Result};
use serde::Serialize;

#[derive(Debug, Serialize)]
pub struct RendererReport {
    pub success: bool,
    pub renderer_backend: String,
    pub quality_complete: bool,
    pub target_pass: bool,
    pub output_path: String,
    pub elapsed_s: f64,
    pub output_size_bytes: u64,
    pub encoder: String,
    pub notes: Vec<String>,
}

impl RendererReport {
    pub fn native_candidate(
        output_path: &Path,
        elapsed: Duration,
        encoder: String,
        notes: Vec<String>,
    ) -> Result<Self> {
        let size = output_path
            .metadata()
            .with_context(|| format!("missing output {}", output_path.display()))?
            .len();
        Ok(Self {
            success: true,
            renderer_backend: "native_d3d11_nvenc_candidate".to_string(),
            quality_complete: true,
            target_pass: false,
            output_path: output_path.display().to_string(),
            elapsed_s: elapsed.as_secs_f64(),
            output_size_bytes: size,
            encoder,
            notes,
        })
    }

    pub fn write(&self, path: &Path) -> Result<()> {
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent)?;
        }
        fs::write(path, serde_json::to_vec_pretty(self)?)?;
        Ok(())
    }
}
