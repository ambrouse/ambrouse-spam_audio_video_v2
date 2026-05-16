use std::{fs, path::PathBuf};

use anyhow::{Context, Result};
use serde::Deserialize;

#[derive(Debug, Deserialize)]
pub struct RendererInput {
    pub schema_version: u32,
    pub renderer: String,
    pub output_path: PathBuf,
    #[serde(default)]
    pub audio_path: Option<PathBuf>,
    pub runtime: RuntimeConfig,
    pub video: VideoConfig,
    #[serde(default)]
    pub layout: LayoutConfig,
    pub assets: AssetConfig,
    #[serde(default)]
    pub visual_overlay: VisualOverlayConfig,
}

#[derive(Debug, Deserialize)]
pub struct RuntimeConfig {
    pub ffmpeg_bin: PathBuf,
}

#[derive(Debug, Deserialize)]
pub struct VideoConfig {
    pub width: u32,
    pub height: u32,
    pub fps: u32,
    pub duration_seconds: f64,
    #[serde(default)]
    pub per_scene_duration_seconds: f64,
    pub encoder: String,
    pub preset: String,
    pub cq: u8,
}

#[derive(Debug, Deserialize)]
#[serde(default)]
pub struct LayoutConfig {
    pub side_pad: u32,
    pub panel_width: u32,
    pub panel_height: u32,
    pub motion_intensity: f64,
    pub scroll_zoom: f64,
    pub vertical_travel: f64,
}

impl Default for LayoutConfig {
    fn default() -> Self {
        Self {
            side_pad: 230,
            panel_width: 3380,
            panel_height: 2160,
            motion_intensity: 0.06,
            scroll_zoom: 1.43,
            vertical_travel: 0.75,
        }
    }
}

#[derive(Debug, Deserialize)]
pub struct AssetConfig {
    pub images: Vec<PathBuf>,
    pub logo_path: Option<PathBuf>,
}

#[derive(Debug, Deserialize)]
#[serde(default)]
pub struct VisualOverlayConfig {
    pub enabled: bool,
    pub particle_seed: u32,
    pub dust_color: String,
    pub spark_color: String,
    pub dust_alpha: f32,
    pub audio_visualizer_enabled: bool,
    pub audio_visualizer_color: String,
}

impl Default for VisualOverlayConfig {
    fn default() -> Self {
        Self {
            enabled: false,
            particle_seed: 0,
            dust_color: "0xF7F7EE".to_string(),
            spark_color: "0xD8D0C0".to_string(),
            dust_alpha: 0.30,
            audio_visualizer_enabled: false,
            audio_visualizer_color: "0xD8D0C0".to_string(),
        }
    }
}

impl RendererInput {
    pub fn read(path: &PathBuf) -> Result<Self> {
        let raw = fs::read_to_string(path)
            .with_context(|| format!("failed to read config {}", path.display()))?;
        let payload: Self = serde_json::from_str(&raw)
            .with_context(|| format!("invalid renderer config {}", path.display()))?;
        payload.validate()?;
        Ok(payload)
    }

    fn validate(&self) -> Result<()> {
        anyhow::ensure!(
            self.schema_version == 1,
            "unsupported schema_version {}",
            self.schema_version
        );
        anyhow::ensure!(self.renderer == "native_gpu", "renderer must be native_gpu");
        anyhow::ensure!(self.video.width == 3840, "width must stay 3840");
        anyhow::ensure!(self.video.height == 2160, "height must stay 2160");
        anyhow::ensure!(self.video.fps == 60, "fps must stay 60");
        anyhow::ensure!(
            self.video.duration_seconds > 0.0,
            "duration_seconds must be positive"
        );
        anyhow::ensure!(
            !self.assets.images.is_empty(),
            "at least one image is required"
        );
        if let Some(logo_path) = &self.assets.logo_path {
            if !logo_path.as_os_str().is_empty() {
                anyhow::ensure!(
                    logo_path.exists(),
                    "logo_path does not exist: {}",
                    logo_path.display()
                );
            }
        }
        if let Some(audio_path) = &self.audio_path {
            if !audio_path.as_os_str().is_empty() {
                anyhow::ensure!(
                    audio_path.exists(),
                    "audio_path does not exist: {}",
                    audio_path.display()
                );
            }
        }
        anyhow::ensure!(
            self.runtime.ffmpeg_bin.exists(),
            "ffmpeg_bin does not exist: {}",
            self.runtime.ffmpeg_bin.display()
        );
        let encoder = self.video.encoder.to_ascii_lowercase();
        anyhow::ensure!(
            encoder == "auto" || encoder == "h264_nvenc",
            "CPU or unsupported encoder is not allowed: {}",
            self.video.encoder
        );
        Ok(())
    }
}
