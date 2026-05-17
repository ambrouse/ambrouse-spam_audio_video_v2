use std::{
    ffi::CString,
    fs::File,
    io::{BufWriter, Read, Seek, SeekFrom, Write},
    mem::size_of,
    path::{Path, PathBuf},
    process::Command,
    time::Instant,
};

use anyhow::{anyhow, Context, Result};
use image::{imageops, Rgba, RgbaImage};
use nvenc::{
    bitstream::BitStream,
    session::{InitParams, Session},
    sys::{
        enums::{
            NVencBufferFormat, NVencParamsRcMode, NVencPicStruct, NVencPicType, NVencTuningInfo,
        },
        guids::{NV_ENC_CODEC_H264_GUID, NV_ENC_PRESET_P3_GUID},
    },
};
use windows::core::PCSTR;
use windows::Win32::{
    Foundation::{FALSE, HMODULE, TRUE},
    Graphics::{
        Direct3D::{
            Fxc::D3DCompile, ID3DBlob, D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST,
            D3D_DRIVER_TYPE_UNKNOWN, D3D_FEATURE_LEVEL_11_0,
        },
        Direct3D11::{
            D3D11CreateDevice, ID3D11BlendState, ID3D11Buffer, ID3D11Device, ID3D11DeviceContext,
            ID3D11InputLayout, ID3D11PixelShader, ID3D11RenderTargetView, ID3D11SamplerState,
            ID3D11ShaderResourceView, ID3D11Texture2D, ID3D11VertexShader,
            D3D11_BIND_RENDER_TARGET, D3D11_BIND_SHADER_RESOURCE, D3D11_BIND_VERTEX_BUFFER,
            D3D11_BLEND_DESC, D3D11_BLEND_INV_SRC_ALPHA, D3D11_BLEND_ONE, D3D11_BLEND_OP_ADD,
            D3D11_BLEND_SRC_ALPHA, D3D11_BOX, D3D11_BUFFER_DESC, D3D11_COLOR_WRITE_ENABLE_ALL,
            D3D11_COMPARISON_NEVER, D3D11_CREATE_DEVICE_FLAG, D3D11_FILTER_MIN_MAG_MIP_LINEAR,
            D3D11_INPUT_ELEMENT_DESC, D3D11_INPUT_PER_VERTEX_DATA, D3D11_RENDER_TARGET_BLEND_DESC,
            D3D11_SAMPLER_DESC, D3D11_SDK_VERSION, D3D11_SUBRESOURCE_DATA, D3D11_TEXTURE2D_DESC,
            D3D11_TEXTURE_ADDRESS_CLAMP, D3D11_USAGE_DEFAULT, D3D11_VIEWPORT,
        },
        Dxgi::Common::{
            DXGI_CPU_ACCESS_NONE, DXGI_FORMAT_R32G32B32A32_FLOAT, DXGI_FORMAT_R32G32B32_FLOAT,
            DXGI_FORMAT_R32G32_FLOAT, DXGI_FORMAT_R8G8B8A8_UNORM, DXGI_SAMPLE_DESC,
        },
        Dxgi::{CreateDXGIFactory, IDXGIFactory},
    },
};

use crate::config::RendererInput;

pub struct NativeStoryResult {
    pub encoder: String,
    pub stdout: String,
    pub stderr: String,
    pub notes: Vec<String>,
}

struct D3DContext {
    device: ID3D11Device,
    context: ID3D11DeviceContext,
}

#[repr(C)]
#[derive(Clone, Copy, Default)]
struct QuadVertex {
    position: [f32; 3],
    uv: [f32; 2],
    color: [f32; 4],
}

struct TextureLayer {
    width: u32,
    height: u32,
    srv: ID3D11ShaderResourceView,
}

struct ShaderRenderer {
    vertex_shader: ID3D11VertexShader,
    pixel_shader: ID3D11PixelShader,
    input_layout: ID3D11InputLayout,
    vertex_buffer: ID3D11Buffer,
    sampler: ID3D11SamplerState,
    blend_state: ID3D11BlendState,
    max_quads: usize,
}

struct OutputTarget {
    texture: ID3D11Texture2D,
    rtv: ID3D11RenderTargetView,
}

#[derive(Clone)]
struct OverlayParticle {
    x0: f32,
    y0: f32,
    width: f32,
    height: f32,
    speed: f32,
    rise: bool,
    sway: f32,
    phase: f32,
    offset: f32,
    color: [f32; 4],
}

struct VisualPlan {
    particles: Vec<OverlayParticle>,
    logo_enabled: bool,
    audio_bars: Option<AudioBars>,
}

struct AudioBars {
    frames: Vec<Vec<f32>>,
    color: [f32; 4],
}

pub fn run_native_story_render(input: &RendererInput, output: &Path) -> Result<NativeStoryResult> {
    let width = input.video.width.max(16);
    let height = input.video.height.max(16);
    let fps = input.video.fps.max(1);
    let duration_s = input.video.duration_seconds.max(0.1);
    let frames = (duration_s * f64::from(fps)).ceil() as u64;
    let image_path = input
        .assets
        .images
        .first()
        .context("native renderer requires at least one image")?;

    let prepare_started = Instant::now();
    let source = load_rgba(image_path)?;
    let background = build_background(&source, width, height);
    let logo = match &input.assets.logo_path {
        Some(path) if !path.as_os_str().is_empty() && path.exists() => Some(load_rgba(path)?),
        _ => None,
    };
    let notes = vec![
        "Native renderer draws scene imagery, particles, logo, audio visualizer bars, and encodes through D3D11/NVENC.".to_string(),
        "Final visual overlay is shader-native for the single-scene 4K60 production path.".to_string(),
    ];

    if let Some(parent) = output.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let raw_h264 = output.with_extension("native_candidate.h264");
    let d3d = create_d3d11_context()?;
    let renderer = ShaderRenderer::new(&d3d.device, width, height)
        .context("failed to initialize D3D11 shader renderer")?;

    let session: Session<nvenc::session::NeedsConfig> = Session::open_dx(&d3d.device)
        .map_err(|err| anyhow!("failed to open NVENC D3D11 session: {:?}", err))?;
    anyhow::ensure!(
        session
            .get_encode_codecs()
            .map_err(|err| anyhow!("failed to list NVENC codecs: {:?}", err))?
            .contains(&NV_ENC_CODEC_H264_GUID),
        "NVENC H.264 codec is not available"
    );
    let (session, mut config) = session
        .get_encode_preset_config_ex(
            NV_ENC_CODEC_H264_GUID,
            NV_ENC_PRESET_P3_GUID,
            NVencTuningInfo::LowLatency,
        )
        .map_err(|err| anyhow!("failed to get NVENC preset config: {:?}", err))?;
    config.preset_cfg.rc_params.rate_control_mode = NVencParamsRcMode::VBR;
    let requested_cq = input.video.cq.clamp(12, 30);
    let average_bit_rate = 18_000_000 + u32::from(18_u8.saturating_sub(requested_cq)) * 1_000_000;
    config.preset_cfg.rc_params.average_bit_rate = average_bit_rate;
    config.preset_cfg.gop_len = fps * 2;
    config.preset_cfg.frame_interval_p = 1;
    let init_params = InitParams {
        encode_guid: NV_ENC_CODEC_H264_GUID,
        preset_guid: NV_ENC_PRESET_P3_GUID,
        aspect_ratio: [16, 9],
        encode_config: &mut config.preset_cfg,
        tuning_info: NVencTuningInfo::LowLatency,
        buffer_format: NVencBufferFormat::ARGB,
        frame_rate: [fps, 1],
        resolution: [width, height],
        enable_ptd: true,
        max_encoder_resolution: [width, height],
    };
    let encoder = session
        .init_encoder(init_params)
        .map_err(|err| anyhow!("failed to initialize NVENC encoder: {:?}", err))?;
    let encode_depth = std::env::var("SPAM_NATIVE_NVENC_PIPELINE_DEPTH")
        .ok()
        .and_then(|value| value.parse::<usize>().ok())
        .unwrap_or(3)
        .clamp(2, 8);
    let mut output_targets = Vec::with_capacity(encode_depth);
    let mut registered = Vec::with_capacity(encode_depth);
    let mut bitstreams = Vec::with_capacity(encode_depth);
    for _ in 0..encode_depth {
        let target = create_output_target(&d3d.device, width, height)?;
        registered.push(
            encoder
                .register_resource_dx11(&target.texture, NVencBufferFormat::ARGB, 0)
                .map_err(|err| anyhow!("failed to register render texture in NVENC: {:?}", err))?,
        );
        bitstreams.push(
            encoder
                .create_bitstream_buffer()
                .map_err(|err| anyhow!("failed to create bitstream buffer: {:?}", err))?,
        );
        output_targets.push(target);
    }

    let mut raw_writer = BufWriter::new(File::create(&raw_h264)?);
    let side_pad = input.layout.side_pad.max(60).min(width / 3);
    let panel_width = input
        .layout
        .panel_width
        .max(320)
        .min(width.saturating_sub(side_pad * 2).max(320));
    let panel_height = input.layout.panel_height.max(320).min(height);
    let scroll_zoom = input.layout.scroll_zoom.max(1.0).min(1.8);
    let foreground_scaled =
        build_foreground_scaled(&source, panel_width, panel_height, scroll_zoom);
    let bg_layer = create_texture_layer(&d3d.device, &background)?;
    let fg_layer = create_texture_layer(&d3d.device, &foreground_scaled)?;
    let white_layer = create_solid_texture_layer(&d3d.device, [255, 255, 255, 255])?;
    let logo_layer = match &logo {
        Some(logo_image) => Some(create_texture_layer(
            &d3d.device,
            &resize_logo_for_layout(logo_image, width, side_pad),
        )?),
        None => None,
    };
    let visual_plan = build_visual_plan(input, width, height, fps, frames)?;
    let prepare_elapsed_s = prepare_started.elapsed().as_secs_f64();
    let render_started = Instant::now();
    for frame_idx in 0..frames {
        let slot = (frame_idx as usize) % encode_depth;
        if frame_idx >= encode_depth as u64 {
            write_bitstream(&bitstreams[slot], &mut raw_writer)?;
        }
        let frame_time = frame_idx as f64 / f64::from(fps);
        let progress = production_scroll_y(input, frame_time);
        renderer.draw_story_frame(
            &d3d.context,
            &output_targets[slot].rtv,
            width,
            height,
            side_pad,
            panel_width,
            panel_height,
            progress,
            &bg_layer,
            &fg_layer,
            if visual_plan.logo_enabled {
                logo_layer.as_ref()
            } else {
                None
            },
            &white_layer,
            &visual_plan,
            frame_idx as usize,
            frame_time as f32,
        );
        maybe_flush_context(&d3d.context);
        let pic_type = if frame_idx % u64::from(fps * 2) == 0 {
            NVencPicType::IDR
        } else {
            NVencPicType::P
        };
        encoder
            .encode_picture(
                &registered[slot],
                &bitstreams[slot],
                frame_idx as usize,
                frame_idx,
                NVencBufferFormat::ARGB,
                NVencPicStruct::Frame,
                pic_type,
                None,
            )
            .map_err(|err| anyhow!("NVENC encode_picture failed: {:?}", err))?;
    }
    let pending_start = frames.saturating_sub(encode_depth as u64);
    for frame_idx in pending_start..frames {
        let slot = (frame_idx as usize) % encode_depth;
        write_bitstream(&bitstreams[slot], &mut raw_writer)?;
    }
    let render_encode_elapsed_s = render_started.elapsed().as_secs_f64();
    encoder
        .end_encode()
        .map_err(|err| anyhow!("NVENC end_encode failed: {:?}", err))?;
    raw_writer.flush()?;
    let remux_started = Instant::now();
    remux_h264_to_mp4(&input.runtime.ffmpeg_bin, &raw_h264, output, fps)?;
    let remux_elapsed_s = remux_started.elapsed().as_secs_f64();
    let _ = std::fs::remove_file(&raw_h264);

    let mut final_notes = notes;
    final_notes.push(format!(
        "Prepared source layers in {:.3}s.",
        prepare_elapsed_s
    ));
    final_notes.push(format!(
        "Rendered and encoded {} frames in {:.3}s.",
        frames, render_encode_elapsed_s
    ));
    final_notes.push(format!(
        "Remuxed native H.264 to MP4 in {:.3}s.",
        remux_elapsed_s
    ));
    final_notes.push(format!(
        "NVENC pipeline depth: {} render targets/bitstreams.",
        encode_depth
    ));
    final_notes.push(format!(
        "Requested preset={} cq={} mapped to native average_bit_rate={}.",
        input.video.preset, input.video.cq, average_bit_rate
    ));
    final_notes.push(
        "Per-frame image composition, particles, logo, and audio visualizer are drawn with D3D11 shader quads."
            .to_string(),
    );
    final_notes.push(format!(
        "Native visual overlay: particles={}, logo={}, audio_visualizer={}.",
        visual_plan.particles.len(),
        visual_plan.logo_enabled && logo_layer.is_some(),
        visual_plan.audio_bars.is_some()
    ));
    Ok(NativeStoryResult {
        encoder: "h264_nvenc_native_d3d11".to_string(),
        stdout: String::new(),
        stderr: String::new(),
        notes: final_notes,
    })
}

fn production_scroll_y(input: &RendererInput, frame_time: f64) -> f64 {
    let duration = input.video.per_scene_duration_seconds.max(1.0);
    let scroll_period = duration.mul_add(1.0 / 0.47, 0.0).clamp(28.8, 37.2);
    let scroll_amplitude = (input.layout.vertical_travel * 0.62).clamp(0.34, 0.46);
    let phase = -std::f64::consts::FRAC_PI_2;
    (0.50 + scroll_amplitude * ((std::f64::consts::TAU * frame_time / scroll_period) + phase).sin())
        .clamp(0.0, 1.0)
}

fn load_rgba(path: &Path) -> Result<RgbaImage> {
    let image = image::open(path)
        .with_context(|| format!("failed to decode image {}", path.display()))?
        .to_rgba8();
    Ok(image)
}

fn build_background(source: &RgbaImage, width: u32, height: u32) -> RgbaImage {
    let cover = resize_cover(source, width, height);
    let blurred = imageops::blur(&cover, 18.0);
    let mut output = RgbaImage::new(width, height);
    for (x, y, pixel) in output.enumerate_pixels_mut() {
        let p = blurred.get_pixel(x, y);
        let r = ((f32::from(p[0]) * 0.88) - 6.0).clamp(0.0, 255.0) as u8;
        let g = ((f32::from(p[1]) * 0.88) - 6.0).clamp(0.0, 255.0) as u8;
        let b = ((f32::from(p[2]) * 0.88) - 6.0).clamp(0.0, 255.0) as u8;
        *pixel = Rgba([r, g, b, 255]);
    }
    output
}

fn build_foreground_scaled(
    source: &RgbaImage,
    panel_width: u32,
    panel_height: u32,
    zoom: f64,
) -> RgbaImage {
    let target_w = ((panel_width as f64 * zoom).round() as u32).max(panel_width);
    let target_h = ((panel_height as f64 * zoom).round() as u32).max(panel_height);
    resize_cover(source, target_w, target_h)
}

fn resize_logo_for_layout(logo: &RgbaImage, video_width: u32, side_pad: u32) -> RgbaImage {
    let logo_width = (side_pad.saturating_mul(68) / 100).clamp(28, video_width / 20);
    let ratio = logo_width as f32 / logo.width().max(1) as f32;
    let logo_height = (logo.height() as f32 * ratio).round().max(1.0) as u32;
    imageops::resize(
        logo,
        logo_width,
        logo_height,
        imageops::FilterType::Lanczos3,
    )
}

fn resize_cover(source: &RgbaImage, width: u32, height: u32) -> RgbaImage {
    let scale = (width as f64 / source.width().max(1) as f64)
        .max(height as f64 / source.height().max(1) as f64);
    let scaled_w = ((source.width() as f64 * scale).ceil() as u32).max(width);
    let scaled_h = ((source.height() as f64 * scale).ceil() as u32).max(height);
    let resized = imageops::resize(source, scaled_w, scaled_h, imageops::FilterType::Lanczos3);
    let x = scaled_w.saturating_sub(width) / 2;
    let y = scaled_h.saturating_sub(height) / 2;
    imageops::crop_imm(&resized, x, y, width, height).to_image()
}

fn create_d3d11_context() -> Result<D3DContext> {
    let factory: IDXGIFactory = unsafe { CreateDXGIFactory() }?;
    let adapter = unsafe { factory.EnumAdapters(0) }?;
    let mut device = None;
    let mut context = None;
    unsafe {
        D3D11CreateDevice(
            &adapter,
            D3D_DRIVER_TYPE_UNKNOWN,
            HMODULE::default(),
            D3D11_CREATE_DEVICE_FLAG(0),
            Some(&[D3D_FEATURE_LEVEL_11_0]),
            D3D11_SDK_VERSION,
            Some(&mut device),
            None,
            Some(&mut context),
        )
    }?;
    Ok(D3DContext {
        device: device.context("D3D11CreateDevice returned no device")?,
        context: context.context("D3D11CreateDevice returned no context")?,
    })
}

fn create_output_target(device: &ID3D11Device, width: u32, height: u32) -> Result<OutputTarget> {
    let desc = D3D11_TEXTURE2D_DESC {
        Width: width,
        Height: height,
        MipLevels: 1,
        ArraySize: 1,
        Format: DXGI_FORMAT_R8G8B8A8_UNORM,
        SampleDesc: DXGI_SAMPLE_DESC {
            Count: 1,
            Quality: 0,
        },
        Usage: D3D11_USAGE_DEFAULT,
        BindFlags: (D3D11_BIND_RENDER_TARGET | D3D11_BIND_SHADER_RESOURCE).0 as u32,
        CPUAccessFlags: DXGI_CPU_ACCESS_NONE,
        MiscFlags: 0,
    };
    let mut texture = None;
    unsafe { device.CreateTexture2D(&desc, None, Some(&mut texture)) }?;
    let texture = texture.context("CreateTexture2D returned no render target texture")?;
    let mut rtv = None;
    unsafe { device.CreateRenderTargetView(&texture, None, Some(&mut rtv)) }?;
    Ok(OutputTarget {
        texture,
        rtv: rtv.context("CreateRenderTargetView returned no RTV")?,
    })
}

fn create_texture_layer(device: &ID3D11Device, image: &RgbaImage) -> Result<TextureLayer> {
    let row_pitch = image.width() * 4;
    let desc = D3D11_TEXTURE2D_DESC {
        Width: image.width(),
        Height: image.height(),
        MipLevels: 1,
        ArraySize: 1,
        Format: DXGI_FORMAT_R8G8B8A8_UNORM,
        SampleDesc: DXGI_SAMPLE_DESC {
            Count: 1,
            Quality: 0,
        },
        Usage: D3D11_USAGE_DEFAULT,
        BindFlags: D3D11_BIND_SHADER_RESOURCE.0 as u32,
        CPUAccessFlags: DXGI_CPU_ACCESS_NONE,
        MiscFlags: 0,
    };
    let initial = D3D11_SUBRESOURCE_DATA {
        pSysMem: image.as_raw().as_ptr().cast(),
        SysMemPitch: row_pitch,
        SysMemSlicePitch: row_pitch * image.height(),
    };
    let mut texture = None;
    unsafe { device.CreateTexture2D(&desc, Some(&initial), Some(&mut texture)) }?;
    let texture = texture.context("CreateTexture2D returned no texture layer")?;
    let mut srv = None;
    unsafe { device.CreateShaderResourceView(&texture, None, Some(&mut srv)) }?;
    Ok(TextureLayer {
        width: image.width(),
        height: image.height(),
        srv: srv.context("CreateShaderResourceView returned no SRV")?,
    })
}

fn create_solid_texture_layer(device: &ID3D11Device, rgba: [u8; 4]) -> Result<TextureLayer> {
    let image = RgbaImage::from_pixel(1, 1, Rgba(rgba));
    create_texture_layer(device, &image)
}

fn build_visual_plan(
    input: &RendererInput,
    width: u32,
    height: u32,
    fps: u32,
    frames: u64,
) -> Result<VisualPlan> {
    if !input.visual_overlay.enabled {
        return Ok(VisualPlan {
            particles: Vec::new(),
            logo_enabled: false,
            audio_bars: None,
        });
    }
    let dust_color = parse_overlay_color(
        &input.visual_overlay.dust_color,
        input.visual_overlay.dust_alpha,
    );
    let spark_color = parse_overlay_color(&input.visual_overlay.spark_color, 0.52);
    let visualizer_color = parse_overlay_color(&input.visual_overlay.audio_visualizer_color, 0.64);
    let particles = build_particles(
        width,
        height,
        input.visual_overlay.particle_seed,
        dust_color,
        spark_color,
    );
    let audio_bars = if input.visual_overlay.audio_visualizer_enabled {
        match &input.audio_path {
            Some(path) if path.exists() => Some(AudioBars {
                frames: build_audio_bar_frames(
                    path,
                    fps,
                    frames as usize,
                    input.video.audio_start_seconds,
                )?,
                color: visualizer_color,
            }),
            _ => None,
        }
    } else {
        None
    };
    Ok(VisualPlan {
        particles,
        logo_enabled: true,
        audio_bars,
    })
}

fn parse_overlay_color(raw: &str, alpha: f32) -> [f32; 4] {
    let cleaned = raw.trim().trim_start_matches("0x").trim_start_matches('#');
    let value = u32::from_str_radix(cleaned, 16).unwrap_or(0xF7F7EE);
    [
        ((value >> 16) & 0xff) as f32 / 255.0,
        ((value >> 8) & 0xff) as f32 / 255.0,
        (value & 0xff) as f32 / 255.0,
        alpha.clamp(0.0, 1.0),
    ]
}

fn build_particles(
    width: u32,
    height: u32,
    seed: u32,
    dust_color: [f32; 4],
    spark_color: [f32; 4],
) -> Vec<OverlayParticle> {
    let mut rng = LcgRng::new(seed.max(1));
    let width_f = width as f32;
    let height_f = height as f32;
    let dust_count = (width / 20).clamp(48, 86);
    let spark_count = (width / 54).clamp(14, 32);
    let margin = (height_f * 0.08).max(30.0);
    let mut particles = Vec::with_capacity((dust_count + spark_count) as usize);

    for index in 0..dust_count {
        let widths = [2.0, 2.0, 3.0, 3.0, 4.0];
        let heights = [5.0, 6.0, 8.0, 10.0, 12.0];
        let lane_width = width_f / dust_count as f32;
        let x0 =
            lane_width * (index as f32 + 0.5) + rng.range(-lane_width * 0.28, lane_width * 0.28);
        let y0 = (((index as f32 * 0.61803398875) % 1.0) * (height_f + margin * 2.0))
            + rng.range(-margin * 0.28, margin * 0.28);
        let mut color = dust_color;
        color[3] = (dust_color[3] * rng.range(0.70, 1.18)).clamp(0.12, 0.46);
        particles.push(OverlayParticle {
            x0,
            y0,
            width: widths[rng.index(widths.len())],
            height: heights[rng.index(heights.len())],
            speed: rng.range(height_f * 0.012, height_f * 0.038),
            rise: false,
            sway: rng.range(width_f * 0.003, width_f * 0.014),
            phase: rng.range(0.16, 0.42),
            offset: rng.range(0.0, std::f32::consts::TAU),
            color,
        });
    }

    let lower_band = height_f * 0.56;
    let side_safe = (width_f * 0.045).max(42.0);
    for index in 0..spark_count {
        let lane = index as f32 / (spark_count - 1).max(1) as f32;
        let side_bias = if index % 3 == 0 {
            if rng.next_f32() < 0.5 {
                rng.range(0.0, 0.18)
            } else {
                rng.range(0.82, 1.0)
            }
        } else {
            lane
        };
        let mut color = spark_color;
        color[3] = rng.range(0.32, 0.62);
        particles.push(OverlayParticle {
            x0: side_safe
                + side_bias * (width_f - side_safe * 2.0).max(1.0)
                + rng.range(-width_f * 0.018, width_f * 0.018),
            y0: lower_band + rng.next_f32() * height_f * 0.36,
            width: [2.0, 2.0, 3.0][rng.index(3)],
            height: [16.0, 20.0, 24.0, 30.0][rng.index(4)],
            speed: rng.range(height_f * 0.030, height_f * 0.088),
            rise: true,
            sway: rng.range(width_f * 0.002, width_f * 0.010),
            phase: rng.range(0.55, 1.10),
            offset: rng.range(0.0, std::f32::consts::TAU),
            color,
        });
    }
    particles
}

struct LcgRng {
    state: u64,
}

impl LcgRng {
    fn new(seed: u32) -> Self {
        Self { state: seed as u64 }
    }

    fn next_f32(&mut self) -> f32 {
        self.state = self.state.wrapping_mul(6364136223846793005).wrapping_add(1);
        ((self.state >> 40) as u32) as f32 / 16_777_215.0
    }

    fn range(&mut self, low: f32, high: f32) -> f32 {
        low + (high - low) * self.next_f32()
    }

    fn index(&mut self, len: usize) -> usize {
        ((self.next_f32() * len as f32) as usize).min(len.saturating_sub(1))
    }
}

fn build_audio_bar_frames(
    path: &Path,
    fps: u32,
    frame_count: usize,
    start_seconds: f64,
) -> Result<Vec<Vec<f32>>> {
    let audio = read_pcm16_wav(path)?;
    if audio.samples.is_empty() || audio.sample_rate == 0 {
        return Ok(vec![vec![0.0; AUDIO_BAR_COUNT]; frame_count]);
    }
    let mut frames = Vec::with_capacity(frame_count);
    let channels = audio.channels.max(1) as usize;
    let samples_per_frame = audio.sample_rate as f32 / fps.max(1) as f32;
    let start_sample = (start_seconds.max(0.0) * audio.sample_rate as f64) as usize * channels;
    let total_samples = audio.samples.len();
    for frame_idx in 0..frame_count {
        let center_sample =
            start_sample + (frame_idx as f32 * samples_per_frame) as usize * channels;
        let window = (audio.sample_rate as usize / 30).max(512) * channels;
        let start = center_sample.saturating_sub(window / 2);
        let end = (center_sample + window / 2).min(total_samples);
        if start >= total_samples || start >= end {
            frames.push(vec![0.0; AUDIO_BAR_COUNT]);
        } else {
            frames.push(compute_audio_bars(&audio.samples[start..end], channels));
        }
    }
    Ok(frames)
}

fn compute_audio_bars(samples: &[f32], channels: usize) -> Vec<f32> {
    let mono_len = samples.len() / channels.max(1);
    if mono_len == 0 {
        return vec![0.0; AUDIO_BAR_COUNT];
    }
    let mut bars = vec![0.0_f32; AUDIO_BAR_COUNT];
    for (bar, value) in bars.iter_mut().enumerate() {
        let stride = 1 + bar * 3;
        let offset = (bar * 17) % channels.max(1);
        let mut acc = 0.0;
        let mut count = 0_u32;
        let mut index = offset;
        while index < samples.len() && count < 96 {
            let sample = samples[index].abs();
            acc += sample * sample;
            index += stride * channels.max(1);
            count += 1;
        }
        let rms = if count > 0 {
            (acc / count as f32).sqrt()
        } else {
            0.0
        };
        let shaped = (rms * (2.8 + bar as f32 * 0.018)).sqrt();
        *value = shaped.clamp(0.02, 1.0);
    }
    smooth_bars(&mut bars);
    bars
}

fn smooth_bars(bars: &mut [f32]) {
    if bars.len() < 3 {
        return;
    }
    let copy = bars.to_vec();
    for idx in 1..bars.len() - 1 {
        bars[idx] = copy[idx - 1] * 0.22 + copy[idx] * 0.56 + copy[idx + 1] * 0.22;
    }
}

struct PcmAudio {
    sample_rate: u32,
    channels: u16,
    samples: Vec<f32>,
}

fn read_pcm16_wav(path: &Path) -> Result<PcmAudio> {
    let mut file =
        File::open(path).with_context(|| format!("failed to open wav {}", path.display()))?;
    let mut riff = [0_u8; 12];
    file.read_exact(&mut riff)?;
    anyhow::ensure!(
        &riff[0..4] == b"RIFF" && &riff[8..12] == b"WAVE",
        "unsupported wav header"
    );
    let mut channels = 0_u16;
    let mut sample_rate = 0_u32;
    let mut bits_per_sample = 0_u16;
    let mut audio_format = 0_u16;
    let mut data = Vec::new();
    loop {
        let mut header = [0_u8; 8];
        match file.read_exact(&mut header) {
            Ok(()) => {}
            Err(_) => break,
        }
        let chunk_id = &header[0..4];
        let chunk_size = u32::from_le_bytes(header[4..8].try_into().unwrap()) as usize;
        if chunk_id == b"fmt " {
            let mut fmt = vec![0_u8; chunk_size];
            file.read_exact(&mut fmt)?;
            anyhow::ensure!(fmt.len() >= 16, "invalid wav fmt chunk");
            audio_format = u16::from_le_bytes(fmt[0..2].try_into().unwrap());
            channels = u16::from_le_bytes(fmt[2..4].try_into().unwrap());
            sample_rate = u32::from_le_bytes(fmt[4..8].try_into().unwrap());
            bits_per_sample = u16::from_le_bytes(fmt[14..16].try_into().unwrap());
        } else if chunk_id == b"data" {
            data.resize(chunk_size, 0);
            file.read_exact(&mut data)?;
        } else {
            file.seek(SeekFrom::Current(chunk_size as i64))?;
        }
        if chunk_size % 2 == 1 {
            file.seek(SeekFrom::Current(1))?;
        }
    }
    anyhow::ensure!(
        audio_format == 1,
        "only PCM wav is supported for native visualizer"
    );
    anyhow::ensure!(
        bits_per_sample == 16,
        "only 16-bit wav is supported for native visualizer"
    );
    anyhow::ensure!(
        channels > 0 && sample_rate > 0,
        "wav fmt chunk missing channel/rate"
    );
    let samples = data
        .chunks_exact(2)
        .map(|bytes| i16::from_le_bytes([bytes[0], bytes[1]]) as f32 / 32768.0)
        .collect();
    Ok(PcmAudio {
        sample_rate,
        channels,
        samples,
    })
}

impl ShaderRenderer {
    fn new(device: &ID3D11Device, width: u32, height: u32) -> Result<Self> {
        let vertex_blob = compile_shader(SHADER_SOURCE, "vs_main", "vs_5_0")?;
        let pixel_blob = compile_shader(SHADER_SOURCE, "ps_main", "ps_5_0")?;
        let mut vertex_shader = None;
        let mut pixel_shader = None;
        unsafe {
            device.CreateVertexShader(&vertex_blob, None, Some(&mut vertex_shader))?;
            device.CreatePixelShader(&pixel_blob, None, Some(&mut pixel_shader))?;
        }

        let input_elements = [
            D3D11_INPUT_ELEMENT_DESC {
                SemanticName: PCSTR(b"POSITION\0".as_ptr()),
                SemanticIndex: 0,
                Format: DXGI_FORMAT_R32G32B32_FLOAT,
                InputSlot: 0,
                AlignedByteOffset: 0,
                InputSlotClass: D3D11_INPUT_PER_VERTEX_DATA,
                InstanceDataStepRate: 0,
            },
            D3D11_INPUT_ELEMENT_DESC {
                SemanticName: PCSTR(b"TEXCOORD\0".as_ptr()),
                SemanticIndex: 0,
                Format: DXGI_FORMAT_R32G32_FLOAT,
                InputSlot: 0,
                AlignedByteOffset: 12,
                InputSlotClass: D3D11_INPUT_PER_VERTEX_DATA,
                InstanceDataStepRate: 0,
            },
            D3D11_INPUT_ELEMENT_DESC {
                SemanticName: PCSTR(b"COLOR\0".as_ptr()),
                SemanticIndex: 0,
                Format: DXGI_FORMAT_R32G32B32A32_FLOAT,
                InputSlot: 0,
                AlignedByteOffset: 20,
                InputSlotClass: D3D11_INPUT_PER_VERTEX_DATA,
                InstanceDataStepRate: 0,
            },
        ];
        let mut input_layout = None;
        unsafe {
            device.CreateInputLayout(&input_elements, &vertex_blob, Some(&mut input_layout))?;
        }

        let max_quads = 384;
        let vertex_buffer = create_vertex_buffer(device, max_quads)?;
        let sampler = create_sampler(device)?;
        let blend_state = create_alpha_blend_state(device)?;
        let renderer = Self {
            vertex_shader: vertex_shader.context("CreateVertexShader returned no shader")?,
            pixel_shader: pixel_shader.context("CreatePixelShader returned no shader")?,
            input_layout: input_layout.context("CreateInputLayout returned no layout")?,
            vertex_buffer,
            sampler,
            blend_state,
            max_quads,
        };
        renderer.bind_static_pipeline(device, width, height);
        Ok(renderer)
    }

    fn bind_static_pipeline(&self, _device: &ID3D11Device, _width: u32, _height: u32) {}

    #[allow(clippy::too_many_arguments)]
    fn draw_story_frame(
        &self,
        context: &ID3D11DeviceContext,
        render_target: &ID3D11RenderTargetView,
        width: u32,
        height: u32,
        side_pad: u32,
        panel_width: u32,
        panel_height: u32,
        progress: f64,
        background: &TextureLayer,
        foreground: &TextureLayer,
        logo: Option<&TextureLayer>,
        white: &TextureLayer,
        visual_plan: &VisualPlan,
        frame_idx: usize,
        frame_time: f32,
    ) {
        let viewport = D3D11_VIEWPORT {
            TopLeftX: 0.0,
            TopLeftY: 0.0,
            Width: width as f32,
            Height: height as f32,
            MinDepth: 0.0,
            MaxDepth: 1.0,
        };
        let stride = size_of::<QuadVertex>() as u32;
        let offset = 0_u32;
        let vertex_buffers = [Some(self.vertex_buffer.clone())];
        let srvs = [Some(background.srv.clone())];
        let samplers = [Some(self.sampler.clone())];
        let rtvs = [Some(render_target.clone())];

        unsafe {
            context.OMSetRenderTargets(Some(&rtvs), None);
            context.OMSetBlendState(
                Some(&self.blend_state),
                Some(&[0.0, 0.0, 0.0, 0.0]),
                u32::MAX,
            );
            context.ClearRenderTargetView(render_target, &[0.0, 0.0, 0.0, 1.0]);
            context.RSSetViewports(Some(&[viewport]));
            context.IASetInputLayout(Some(&self.input_layout));
            context.IASetPrimitiveTopology(D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
            context.IASetVertexBuffers(
                0,
                1,
                Some(vertex_buffers.as_ptr()),
                Some(&stride),
                Some(&offset),
            );
            context.VSSetShader(Some(&self.vertex_shader), None);
            context.PSSetShader(Some(&self.pixel_shader), None);
            context.PSSetSamplers(0, Some(&samplers));
            context.PSSetShaderResources(0, Some(&srvs));
        }

        self.draw_quad(
            context,
            width,
            height,
            RectPixels::new(0.0, 0.0, width as f32, height as f32),
            UvRect::full(),
            background,
            [1.0, 1.0, 1.0, 1.0],
        );

        let max_y = foreground.height.saturating_sub(panel_height);
        let src_y = (max_y as f32 * progress.clamp(0.0, 1.0) as f32) / foreground.height as f32;
        let src_x =
            foreground.width.saturating_sub(panel_width) as f32 * 0.5 / foreground.width as f32;
        let fg_uv = UvRect {
            left: src_x,
            top: src_y,
            right: src_x + panel_width as f32 / foreground.width as f32,
            bottom: src_y + panel_height as f32 / foreground.height as f32,
        };
        self.draw_quad(
            context,
            width,
            height,
            RectPixels::new(
                side_pad as f32,
                0.0,
                panel_width as f32,
                panel_height as f32,
            ),
            fg_uv,
            foreground,
            [1.0, 1.0, 1.0, 1.0],
        );

        self.draw_white_overlays(
            context,
            width,
            height,
            white,
            visual_plan,
            frame_idx,
            frame_time,
        );

        if let Some(logo_layer) = logo {
            let x = width
                .saturating_sub(side_pad)
                .saturating_add(side_pad.saturating_sub(logo_layer.width) / 2);
            let y = height
                .saturating_sub(logo_layer.height)
                .saturating_sub(height / 72);
            self.draw_quad(
                context,
                width,
                height,
                RectPixels::new(
                    x as f32,
                    y as f32,
                    logo_layer.width as f32,
                    logo_layer.height as f32,
                ),
                UvRect::full(),
                logo_layer,
                [1.0, 1.0, 1.0, 0.82],
            );
        }
    }

    fn draw_white_overlays(
        &self,
        context: &ID3D11DeviceContext,
        width: u32,
        height: u32,
        white: &TextureLayer,
        visual_plan: &VisualPlan,
        frame_idx: usize,
        frame_time: f32,
    ) {
        let margin = (height as f32 * 0.08).max(30.0);
        let mut vertices = Vec::with_capacity(
            self.max_quads
                .min(visual_plan.particles.len() + AUDIO_BAR_COUNT)
                * 6,
        );
        for particle in &visual_plan.particles {
            let x =
                particle.x0 + (frame_time * particle.phase + particle.offset).sin() * particle.sway;
            let travel = if particle.rise {
                particle.y0 - frame_time * particle.speed
            } else {
                particle.y0 + frame_time * particle.speed
            };
            let y = positive_mod(travel, height as f32 + margin * 2.0) - margin;
            append_quad_vertices(
                &mut vertices,
                width as f32,
                height as f32,
                RectPixels::new(x, y, particle.width, particle.height),
                UvRect::full(),
                particle.color,
            );
        }

        if let Some(audio_bars) = &visual_plan.audio_bars {
            if let Some(bars) = audio_bars.frames.get(frame_idx) {
                append_audio_visualizer_clusters(
                    &mut vertices,
                    width as f32,
                    height as f32,
                    bars,
                    audio_bars.color,
                );
            }
        }

        if !vertices.is_empty() {
            self.draw_vertices(context, white, &vertices);
        }
    }

    fn draw_quad(
        &self,
        context: &ID3D11DeviceContext,
        width: u32,
        height: u32,
        dest: RectPixels,
        uv: UvRect,
        texture: &TextureLayer,
        color: [f32; 4],
    ) {
        let vertices = quad_vertices(width as f32, height as f32, dest, uv, color);
        self.draw_vertices(context, texture, &vertices);
    }

    fn draw_vertices(
        &self,
        context: &ID3D11DeviceContext,
        texture: &TextureLayer,
        vertices: &[QuadVertex],
    ) {
        debug_assert!(vertices.len() <= self.max_quads * 6);
        if vertices.is_empty() {
            return;
        }
        let bytes_to_upload = (vertices.len() * size_of::<QuadVertex>()) as u32;
        let update_box = D3D11_BOX {
            left: 0,
            top: 0,
            front: 0,
            right: bytes_to_upload,
            bottom: 1,
            back: 1,
        };
        let srvs = [Some(texture.srv.clone())];
        unsafe {
            context.UpdateSubresource(
                &self.vertex_buffer,
                0,
                Some(&update_box),
                vertices.as_ptr().cast(),
                0,
                0,
            );
            context.PSSetShaderResources(0, Some(&srvs));
            context.Draw(vertices.len() as u32, 0);
        }
    }
}

#[derive(Clone, Copy)]
struct RectPixels {
    x: f32,
    y: f32,
    width: f32,
    height: f32,
}

impl RectPixels {
    fn new(x: f32, y: f32, width: f32, height: f32) -> Self {
        Self {
            x,
            y,
            width,
            height,
        }
    }
}

#[derive(Clone, Copy)]
struct UvRect {
    left: f32,
    top: f32,
    right: f32,
    bottom: f32,
}

impl UvRect {
    fn full() -> Self {
        Self {
            left: 0.0,
            top: 0.0,
            right: 1.0,
            bottom: 1.0,
        }
    }
}

fn quad_vertices(
    video_width: f32,
    video_height: f32,
    dest: RectPixels,
    uv: UvRect,
    color: [f32; 4],
) -> [QuadVertex; 6] {
    let left = (dest.x / video_width) * 2.0 - 1.0;
    let right = ((dest.x + dest.width) / video_width) * 2.0 - 1.0;
    let top = 1.0 - (dest.y / video_height) * 2.0;
    let bottom = 1.0 - ((dest.y + dest.height) / video_height) * 2.0;
    [
        QuadVertex {
            position: [left, top, 0.0],
            uv: [uv.left, uv.top],
            color,
        },
        QuadVertex {
            position: [right, top, 0.0],
            uv: [uv.right, uv.top],
            color,
        },
        QuadVertex {
            position: [left, bottom, 0.0],
            uv: [uv.left, uv.bottom],
            color,
        },
        QuadVertex {
            position: [left, bottom, 0.0],
            uv: [uv.left, uv.bottom],
            color,
        },
        QuadVertex {
            position: [right, top, 0.0],
            uv: [uv.right, uv.top],
            color,
        },
        QuadVertex {
            position: [right, bottom, 0.0],
            uv: [uv.right, uv.bottom],
            color,
        },
    ]
}

fn append_quad_vertices(
    target: &mut Vec<QuadVertex>,
    video_width: f32,
    video_height: f32,
    dest: RectPixels,
    uv: UvRect,
    color: [f32; 4],
) {
    target.extend_from_slice(&quad_vertices(video_width, video_height, dest, uv, color));
}

fn append_audio_visualizer_clusters(
    target: &mut Vec<QuadVertex>,
    video_width: f32,
    video_height: f32,
    bars: &[f32],
    color: [f32; 4],
) {
    if bars.is_empty() {
        return;
    }
    let bars_per_side = AUDIO_BARS_PER_SIDE.min(bars.len() / 2).max(6);
    let cluster_width = (video_width * 0.14).clamp(320.0, 560.0);
    let side_gap = (video_width * 0.19).clamp(260.0, 760.0);
    let bottom_gap = (video_height * 0.105).clamp(72.0, 132.0);
    let base_y = (video_height - bottom_gap).max(0.0);
    let max_bar_height = (video_height * 0.056).clamp(30.0, 72.0);
    let slot = cluster_width / bars_per_side as f32;
    let draw_width = (slot * 0.58).clamp(5.0, 18.0);
    let left_start = side_gap;
    let right_start = (video_width - side_gap - cluster_width).max(left_start + cluster_width);
    let left_source = &bars[..bars_per_side];
    let right_source_start = bars.len().saturating_sub(bars_per_side);
    let right_source = &bars[right_source_start..];

    append_audio_bar_cluster(
        target,
        video_width,
        video_height,
        left_start,
        base_y,
        slot,
        draw_width,
        max_bar_height,
        left_source,
        color,
        false,
    );
    append_audio_bar_cluster(
        target,
        video_width,
        video_height,
        right_start,
        base_y,
        slot,
        draw_width,
        max_bar_height,
        right_source,
        color,
        true,
    );
}

#[allow(clippy::too_many_arguments)]
fn append_audio_bar_cluster(
    target: &mut Vec<QuadVertex>,
    video_width: f32,
    video_height: f32,
    start_x: f32,
    base_y: f32,
    slot: f32,
    draw_width: f32,
    max_bar_height: f32,
    bars: &[f32],
    color: [f32; 4],
    reverse: bool,
) {
    let center = (bars.len().saturating_sub(1)) as f32 * 0.5;
    for idx in 0..bars.len() {
        let source_idx = if reverse { bars.len() - 1 - idx } else { idx };
        let value = bars[source_idx].clamp(0.0, 1.0);
        let distance = if center > 0.0 {
            ((idx as f32 - center).abs() / center).clamp(0.0, 1.0)
        } else {
            0.0
        };
        let envelope = 0.72 + (1.0 - distance) * 0.34;
        let h = (max_bar_height * value.sqrt() * envelope).clamp(3.0, max_bar_height);
        let x = start_x + idx as f32 * slot + (slot - draw_width) * 0.5;
        let y = base_y - h;
        let mut bar_color = color;
        bar_color[3] = (color[3] * (0.44 + value * 0.32)).clamp(0.18, 0.66);
        append_quad_vertices(
            target,
            video_width,
            video_height,
            RectPixels::new(x, y, draw_width, h),
            UvRect::full(),
            bar_color,
        );
    }
}

fn positive_mod(value: f32, modulus: f32) -> f32 {
    ((value % modulus) + modulus) % modulus
}

fn create_vertex_buffer(device: &ID3D11Device, max_quads: usize) -> Result<ID3D11Buffer> {
    let vertices = vec![QuadVertex::default(); max_quads.max(1) * 6];
    let desc = D3D11_BUFFER_DESC {
        ByteWidth: (vertices.len() * size_of::<QuadVertex>()) as u32,
        Usage: D3D11_USAGE_DEFAULT,
        BindFlags: D3D11_BIND_VERTEX_BUFFER.0 as u32,
        CPUAccessFlags: 0,
        MiscFlags: 0,
        StructureByteStride: 0,
    };
    let initial = D3D11_SUBRESOURCE_DATA {
        pSysMem: vertices.as_ptr().cast(),
        SysMemPitch: 0,
        SysMemSlicePitch: 0,
    };
    let mut buffer = None;
    unsafe { device.CreateBuffer(&desc, Some(&initial), Some(&mut buffer)) }?;
    buffer.context("CreateBuffer returned no vertex buffer")
}

fn create_sampler(device: &ID3D11Device) -> Result<ID3D11SamplerState> {
    let desc = D3D11_SAMPLER_DESC {
        Filter: D3D11_FILTER_MIN_MAG_MIP_LINEAR,
        AddressU: D3D11_TEXTURE_ADDRESS_CLAMP,
        AddressV: D3D11_TEXTURE_ADDRESS_CLAMP,
        AddressW: D3D11_TEXTURE_ADDRESS_CLAMP,
        MipLODBias: 0.0,
        MaxAnisotropy: 1,
        ComparisonFunc: D3D11_COMPARISON_NEVER,
        BorderColor: [0.0, 0.0, 0.0, 0.0],
        MinLOD: 0.0,
        MaxLOD: f32::MAX,
    };
    let mut sampler = None;
    unsafe { device.CreateSamplerState(&desc, Some(&mut sampler)) }?;
    sampler.context("CreateSamplerState returned no sampler")
}

fn create_alpha_blend_state(device: &ID3D11Device) -> Result<ID3D11BlendState> {
    let mut desc = D3D11_BLEND_DESC::default();
    desc.AlphaToCoverageEnable = FALSE;
    desc.IndependentBlendEnable = FALSE;
    desc.RenderTarget[0] = D3D11_RENDER_TARGET_BLEND_DESC {
        BlendEnable: TRUE,
        SrcBlend: D3D11_BLEND_SRC_ALPHA,
        DestBlend: D3D11_BLEND_INV_SRC_ALPHA,
        BlendOp: D3D11_BLEND_OP_ADD,
        SrcBlendAlpha: D3D11_BLEND_ONE,
        DestBlendAlpha: D3D11_BLEND_INV_SRC_ALPHA,
        BlendOpAlpha: D3D11_BLEND_OP_ADD,
        RenderTargetWriteMask: D3D11_COLOR_WRITE_ENABLE_ALL.0 as u8,
    };
    let mut blend = None;
    unsafe { device.CreateBlendState(&desc, Some(&mut blend)) }?;
    blend.context("CreateBlendState returned no blend state")
}

fn compile_shader(source: &str, entry: &str, target: &str) -> Result<Vec<u8>> {
    let entry = CString::new(entry)?;
    let target = CString::new(target)?;
    let mut code: Option<ID3DBlob> = None;
    let mut errors: Option<ID3DBlob> = None;
    let result = unsafe {
        D3DCompile(
            source.as_ptr().cast(),
            source.len(),
            PCSTR::null(),
            None,
            None,
            PCSTR(entry.as_ptr().cast()),
            PCSTR(target.as_ptr().cast()),
            0,
            0,
            &mut code,
            Some(&mut errors),
        )
    };
    if let Err(err) = result {
        let message = errors
            .map(|blob| unsafe {
                let bytes = std::slice::from_raw_parts(
                    blob.GetBufferPointer().cast::<u8>(),
                    blob.GetBufferSize(),
                );
                String::from_utf8_lossy(bytes).into_owned()
            })
            .unwrap_or_else(|| "D3DCompile returned no error blob".to_string());
        return Err(anyhow!(
            "failed to compile shader entry {} target {}: {:?}\n{}",
            entry.to_string_lossy(),
            target.to_string_lossy(),
            err,
            message
        ));
    }
    let blob = code.context("D3DCompile returned no shader bytecode")?;
    let bytes = unsafe {
        std::slice::from_raw_parts(blob.GetBufferPointer().cast::<u8>(), blob.GetBufferSize())
            .to_vec()
    };
    Ok(bytes)
}

const SHADER_SOURCE: &str = r#"
struct VsIn {
    float3 pos : POSITION;
    float2 uv : TEXCOORD0;
    float4 color : COLOR0;
};

struct VsOut {
    float4 pos : SV_POSITION;
    float2 uv : TEXCOORD0;
    float4 color : COLOR0;
};

Texture2D tex0 : register(t0);
SamplerState linear_sampler : register(s0);

VsOut vs_main(VsIn input) {
    VsOut output;
    output.pos = float4(input.pos, 1.0);
    output.uv = input.uv;
    output.color = input.color;
    return output;
}

float4 ps_main(VsOut input) : SV_Target {
    return tex0.Sample(linear_sampler, input.uv) * input.color;
}
"#;

const AUDIO_BAR_COUNT: usize = 48;
const AUDIO_BARS_PER_SIDE: usize = 18;

fn maybe_flush_context(context: &ID3D11DeviceContext) {
    if std::env::var("SPAM_NATIVE_D3D11_FLUSH_EACH_FRAME")
        .map(|value| {
            matches!(
                value.trim().to_ascii_lowercase().as_str(),
                "1" | "true" | "yes" | "on"
            )
        })
        .unwrap_or(false)
    {
        unsafe {
            context.Flush();
        }
    }
}

fn write_bitstream(bitstream: &BitStream, writer: &mut BufWriter<File>) -> Result<()> {
    let lock = bitstream
        .try_lock(true)
        .map_err(|err| anyhow!("failed to lock NVENC bitstream: {:?}", err))?;
    writer.write_all(lock.as_slice())?;
    Ok(())
}

fn remux_h264_to_mp4(ffmpeg_bin: &PathBuf, input: &Path, output: &Path, fps: u32) -> Result<()> {
    let result = Command::new(ffmpeg_bin)
        .arg("-y")
        .arg("-r")
        .arg(fps.to_string())
        .arg("-i")
        .arg(input)
        .arg("-c:v")
        .arg("copy")
        .arg("-movflags")
        .arg("+faststart")
        .arg(output)
        .output()
        .with_context(|| format!("failed to start ffmpeg {}", ffmpeg_bin.display()))?;
    anyhow::ensure!(
        result.status.success(),
        "failed to remux native h264 to mp4: {}",
        String::from_utf8_lossy(&result.stderr)
    );
    Ok(())
}
