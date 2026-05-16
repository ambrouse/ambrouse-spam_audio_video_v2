use std::{
    fs::File,
    io::{BufWriter, Write},
    time::Instant,
};

use anyhow::{anyhow, Context, Result};
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
use serde::Serialize;
use windows::Win32::{
    Foundation::HMODULE,
    Graphics::{
        Direct3D::{D3D_DRIVER_TYPE_UNKNOWN, D3D_FEATURE_LEVEL_11_0},
        Direct3D11::{
            D3D11CreateDevice, ID3D11Device, ID3D11Texture2D, D3D11_BIND_SHADER_RESOURCE,
            D3D11_CREATE_DEVICE_FLAG, D3D11_SDK_VERSION, D3D11_SUBRESOURCE_DATA,
            D3D11_TEXTURE2D_DESC, D3D11_USAGE_DEFAULT,
        },
        Dxgi::Common::{
            DXGI_CPU_ACCESS_NONE, DXGI_FORMAT_NV12, DXGI_FORMAT_R8G8B8A8_UNORM, DXGI_SAMPLE_DESC,
        },
        Dxgi::{CreateDXGIFactory, IDXGIFactory},
    },
};

use crate::cli::EncodeCeilingCommand;

#[derive(Debug, Serialize)]
struct EncodeCeilingReport {
    success: bool,
    backend: String,
    output_path: String,
    elapsed_s: f64,
    duration_s: f64,
    speed_x: f64,
    width: u32,
    height: u32,
    fps: u32,
    frames: u64,
    bitrate: u32,
    buffer_format: String,
    bytes_written: u64,
    notes: Vec<String>,
}

pub fn run_encode_ceiling(command: EncodeCeilingCommand) -> Result<()> {
    let width = command.width.max(16);
    let height = command.height.max(16);
    let fps = command.fps.max(1);
    let seconds = command.seconds.max(0.1);
    let frames = (seconds * f64::from(fps)).ceil() as u64;

    if let Some(parent) = command.output.parent() {
        std::fs::create_dir_all(parent)?;
    }
    if let Some(parent) = command.report.parent() {
        std::fs::create_dir_all(parent)?;
    }

    let device = create_d3d11_device().context("failed to create D3D11 device for NVENC")?;
    let requested_format = command.buffer_format.trim().to_ascii_lowercase();
    let use_nv12 = requested_format != "argb";
    let texture = if use_nv12 {
        create_nv12_test_texture(&device, width, height).context("failed to create NV12 texture")?
    } else {
        create_argb_test_texture(&device, width, height).context("failed to create ARGB texture")?
    };

    let session: Session<nvenc::session::NeedsConfig> = Session::open_dx(&device)
        .map_err(|err| anyhow!("failed to open NVENC D3D11 session: {:?}", err))?;
    anyhow::ensure!(
        session
            .get_encode_codecs()
            .map_err(|err| anyhow!("failed to list NVENC codecs: {:?}", err))?
            .contains(&NV_ENC_CODEC_H264_GUID),
        "NVENC H.264 codec is not available"
    );
    anyhow::ensure!(
        session
            .get_encode_presets(NV_ENC_CODEC_H264_GUID)
            .map_err(|err| anyhow!("failed to list NVENC presets: {:?}", err))?
            .contains(&NV_ENC_PRESET_P3_GUID),
        "NVENC P3 preset is not available"
    );
    let (session, mut config) = session
        .get_encode_preset_config_ex(
            NV_ENC_CODEC_H264_GUID,
            NV_ENC_PRESET_P3_GUID,
            NVencTuningInfo::LowLatency,
        )
        .map_err(|err| anyhow!("failed to get NVENC preset config: {:?}", err))?;

    config.preset_cfg.rc_params.rate_control_mode = NVencParamsRcMode::VBR;
    config.preset_cfg.rc_params.average_bit_rate = command.bitrate;
    config.preset_cfg.gop_len = fps * 2;
    config.preset_cfg.frame_interval_p = 1;

    let init_params = InitParams {
        encode_guid: NV_ENC_CODEC_H264_GUID,
        preset_guid: NV_ENC_PRESET_P3_GUID,
        aspect_ratio: [16, 9],
        encode_config: &mut config.preset_cfg,
        tuning_info: NVencTuningInfo::LowLatency,
        buffer_format: encode_buffer_format(use_nv12),
        frame_rate: [fps, 1],
        resolution: [width, height],
        enable_ptd: true,
        max_encoder_resolution: [width, height],
    };
    let encoder = session
        .init_encoder(init_params)
        .map_err(|err| anyhow!("failed to initialize NVENC encoder: {:?}", err))?;
    let registered = encoder
        .register_resource_dx11(&texture, encode_buffer_format(use_nv12), 0)
        .map_err(|err| anyhow!("failed to register D3D11 texture in NVENC: {:?}", err))?;
    let bitstreams = [
        encoder
            .create_bitstream_buffer()
            .map_err(|err| anyhow!("failed to create NVENC bitstream buffer: {:?}", err))?,
        encoder
            .create_bitstream_buffer()
            .map_err(|err| anyhow!("failed to create NVENC bitstream buffer: {:?}", err))?,
        encoder
            .create_bitstream_buffer()
            .map_err(|err| anyhow!("failed to create NVENC bitstream buffer: {:?}", err))?,
    ];
    let mut writer = BufWriter::new(File::create(&command.output)?);

    let started = Instant::now();
    for frame in 0..frames {
        let bitstream = &bitstreams[(frame as usize) % bitstreams.len()];
        let pic_type = if frame % u64::from(fps * 2) == 0 {
            NVencPicType::IDR
        } else {
            NVencPicType::P
        };
        encoder
            .encode_picture(
                &registered,
                bitstream,
                frame as usize,
                frame,
                encode_buffer_format(use_nv12),
                NVencPicStruct::Frame,
                pic_type,
                None,
            )
            .map_err(|err| anyhow!("NVENC encode_picture failed: {:?}", err))?;
        write_bitstream(bitstream, &mut writer)?;
    }
    encoder
        .end_encode()
        .map_err(|err| anyhow!("NVENC end_encode failed: {:?}", err))?;
    writer.flush()?;
    let elapsed_s = started.elapsed().as_secs_f64();
    let bytes_written = command.output.metadata()?.len();

    let report = EncodeCeilingReport {
        success: true,
        backend: "d3d11_texture_to_nvenc_h264_raw".to_string(),
        output_path: command.output.display().to_string(),
        elapsed_s,
        duration_s: seconds,
        speed_x: seconds / elapsed_s,
        width,
        height,
        fps,
        frames,
        bitrate: command.bitrate,
        buffer_format: if use_nv12 { "nv12" } else { "argb" }.to_string(),
        bytes_written,
        notes: vec![
            "This is a native encoder throughput ceiling probe.".to_string(),
            "It writes raw Annex-B H.264, not the final production MP4.".to_string(),
            "Production parity still requires shader rendering for crop, blur, particles, logo, and audio bars.".to_string(),
        ],
    };
    std::fs::write(&command.report, serde_json::to_vec_pretty(&report)?)?;
    println!("{}", serde_json::to_string_pretty(&report)?);
    Ok(())
}

fn create_d3d11_device() -> Result<ID3D11Device> {
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
    device.context("D3D11CreateDevice returned no device")
}

fn encode_buffer_format(use_nv12: bool) -> NVencBufferFormat {
    if use_nv12 {
        NVencBufferFormat::NV12
    } else {
        NVencBufferFormat::ARGB
    }
}

fn create_argb_test_texture(
    device: &ID3D11Device,
    width: u32,
    height: u32,
) -> Result<ID3D11Texture2D> {
    let row_pitch = width as usize * 4;
    let mut data = vec![0_u8; row_pitch * height as usize];
    for y in 0..height as usize {
        for x in 0..width as usize {
            let offset = y * row_pitch + x * 4;
            data[offset] = ((x * 255) / width as usize) as u8;
            data[offset + 1] = ((y * 255) / height as usize) as u8;
            data[offset + 2] = 32;
            data[offset + 3] = 255;
        }
    }
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
        BindFlags: D3D11_BIND_SHADER_RESOURCE.0 as u32,
        CPUAccessFlags: DXGI_CPU_ACCESS_NONE,
        MiscFlags: 0,
    };
    let initial = D3D11_SUBRESOURCE_DATA {
        pSysMem: data.as_ptr().cast(),
        SysMemPitch: row_pitch as u32,
        SysMemSlicePitch: data.len() as u32,
    };
    let mut texture = None;
    unsafe { device.CreateTexture2D(&desc, Some(&initial), Some(&mut texture)) }?;
    texture.context("CreateTexture2D returned no texture")
}

fn create_nv12_test_texture(
    device: &ID3D11Device,
    width: u32,
    height: u32,
) -> Result<ID3D11Texture2D> {
    let even_width = width + (width % 2);
    let even_height = height + (height % 2);
    let y_size = even_width as usize * even_height as usize;
    let uv_size = y_size / 2;
    let mut data = vec![0_u8; y_size + uv_size];

    for y in 0..even_height as usize {
        for x in 0..even_width as usize {
            data[y * even_width as usize + x] = (16 + ((x * 180) / even_width as usize)) as u8;
        }
    }
    let uv_offset = y_size;
    for y in 0..(even_height as usize / 2) {
        for x in 0..(even_width as usize / 2) {
            let offset = uv_offset + y * even_width as usize + x * 2;
            data[offset] = 128;
            data[offset + 1] = (96 + ((y * 64) / (even_height as usize / 2).max(1))) as u8;
        }
    }

    let desc = D3D11_TEXTURE2D_DESC {
        Width: even_width,
        Height: even_height,
        MipLevels: 1,
        ArraySize: 1,
        Format: DXGI_FORMAT_NV12,
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
        pSysMem: data.as_ptr().cast(),
        SysMemPitch: even_width,
        SysMemSlicePitch: data.len() as u32,
    };
    let mut texture = None;
    unsafe { device.CreateTexture2D(&desc, Some(&initial), Some(&mut texture)) }?;
    texture.context("CreateTexture2D returned no NV12 texture")
}

fn write_bitstream(bitstream: &BitStream, writer: &mut BufWriter<File>) -> Result<()> {
    let lock = bitstream
        .try_lock(true)
        .map_err(|err| anyhow!("failed to lock NVENC bitstream: {:?}", err))?;
    writer.write_all(lock.as_slice())?;
    Ok(())
}
