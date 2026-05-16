use std::{ffi::c_void, path::PathBuf, ptr, time::Instant};

use anyhow::{Context, Result};
use libloading::Library;
use serde::Serialize;
use windows::core::Interface;
use windows::Win32::Foundation::HMODULE;
use windows::Win32::Graphics::Direct3D::{
    D3D_DRIVER_TYPE_HARDWARE, D3D_FEATURE_LEVEL, D3D_FEATURE_LEVEL_11_0,
};
use windows::Win32::Graphics::Direct3D11::{
    D3D11CreateDevice, ID3D11Device, ID3D11DeviceContext, D3D11_CREATE_DEVICE_BGRA_SUPPORT,
    D3D11_SDK_VERSION,
};

use crate::cli::ProbeNativeCommand;

type NvEncodeApiGetMaxSupportedVersion = unsafe extern "system" fn(*mut u32) -> i32;
type NvEncodeApiCreateInstance = unsafe extern "system" fn(*mut NvEncodeApiFunctionList) -> i32;
type NvEncOpenEncodeSessionEx =
    unsafe extern "system" fn(*mut NvEncOpenEncodeSessionExParams, *mut *mut c_void) -> i32;
type NvEncDestroyEncoder = unsafe extern "system" fn(*mut c_void) -> i32;

const NV_ENC_SUCCESS: i32 = 0;
const NV_ENC_DEVICE_TYPE_DIRECTX: u32 = 0;
const NVENCAPI_VERSION: u32 = 12 | (1 << 24);
const NV_ENCODE_API_FUNCTION_LIST_VER: u32 = NVENCAPI_VERSION | (2 << 16) | (0x7 << 28);
const NV_ENC_OPEN_ENCODE_SESSION_EX_PARAMS_VER: u32 = NVENCAPI_VERSION | (1 << 16) | (0x7 << 28);

#[repr(C)]
#[derive(Clone, Copy)]
struct NvEncodeApiFunctionList {
    version: u32,
    reserved: u32,
    nv_enc_open_encode_session: *mut c_void,
    nv_enc_get_encode_guid_count: *mut c_void,
    nv_enc_get_encode_profile_guid_count: *mut c_void,
    nv_enc_get_encode_profile_guids: *mut c_void,
    nv_enc_get_encode_guids: *mut c_void,
    nv_enc_get_input_format_count: *mut c_void,
    nv_enc_get_input_formats: *mut c_void,
    nv_enc_get_encode_caps: *mut c_void,
    nv_enc_get_encode_preset_count: *mut c_void,
    nv_enc_get_encode_preset_guids: *mut c_void,
    nv_enc_get_encode_preset_config: *mut c_void,
    nv_enc_initialize_encoder: *mut c_void,
    nv_enc_create_input_buffer: *mut c_void,
    nv_enc_destroy_input_buffer: *mut c_void,
    nv_enc_create_bitstream_buffer: *mut c_void,
    nv_enc_destroy_bitstream_buffer: *mut c_void,
    nv_enc_encode_picture: *mut c_void,
    nv_enc_lock_bitstream: *mut c_void,
    nv_enc_unlock_bitstream: *mut c_void,
    nv_enc_lock_input_buffer: *mut c_void,
    nv_enc_unlock_input_buffer: *mut c_void,
    nv_enc_get_encode_stats: *mut c_void,
    nv_enc_get_sequence_params: *mut c_void,
    nv_enc_register_async_event: *mut c_void,
    nv_enc_unregister_async_event: *mut c_void,
    nv_enc_map_input_resource: *mut c_void,
    nv_enc_unmap_input_resource: *mut c_void,
    nv_enc_destroy_encoder: *mut c_void,
    nv_enc_invalidate_ref_frames: *mut c_void,
    nv_enc_open_encode_session_ex: *mut c_void,
    nv_enc_register_resource: *mut c_void,
    nv_enc_unregister_resource: *mut c_void,
    nv_enc_reconfigure_encoder: *mut c_void,
    reserved1: *mut c_void,
    nv_enc_create_mv_buffer: *mut c_void,
    nv_enc_destroy_mv_buffer: *mut c_void,
    nv_enc_run_motion_estimation_only: *mut c_void,
    nv_enc_get_last_error_string: *mut c_void,
    nv_enc_set_io_cuda_streams: *mut c_void,
    nv_enc_get_encode_preset_config_ex: *mut c_void,
    nv_enc_get_sequence_param_ex: *mut c_void,
    nv_enc_restore_encoder_state: *mut c_void,
    nv_enc_lookahead_picture: *mut c_void,
    reserved2: [*mut c_void; 275],
}

impl Default for NvEncodeApiFunctionList {
    fn default() -> Self {
        Self {
            version: NV_ENCODE_API_FUNCTION_LIST_VER,
            reserved: 0,
            nv_enc_open_encode_session: ptr::null_mut(),
            nv_enc_get_encode_guid_count: ptr::null_mut(),
            nv_enc_get_encode_profile_guid_count: ptr::null_mut(),
            nv_enc_get_encode_profile_guids: ptr::null_mut(),
            nv_enc_get_encode_guids: ptr::null_mut(),
            nv_enc_get_input_format_count: ptr::null_mut(),
            nv_enc_get_input_formats: ptr::null_mut(),
            nv_enc_get_encode_caps: ptr::null_mut(),
            nv_enc_get_encode_preset_count: ptr::null_mut(),
            nv_enc_get_encode_preset_guids: ptr::null_mut(),
            nv_enc_get_encode_preset_config: ptr::null_mut(),
            nv_enc_initialize_encoder: ptr::null_mut(),
            nv_enc_create_input_buffer: ptr::null_mut(),
            nv_enc_destroy_input_buffer: ptr::null_mut(),
            nv_enc_create_bitstream_buffer: ptr::null_mut(),
            nv_enc_destroy_bitstream_buffer: ptr::null_mut(),
            nv_enc_encode_picture: ptr::null_mut(),
            nv_enc_lock_bitstream: ptr::null_mut(),
            nv_enc_unlock_bitstream: ptr::null_mut(),
            nv_enc_lock_input_buffer: ptr::null_mut(),
            nv_enc_unlock_input_buffer: ptr::null_mut(),
            nv_enc_get_encode_stats: ptr::null_mut(),
            nv_enc_get_sequence_params: ptr::null_mut(),
            nv_enc_register_async_event: ptr::null_mut(),
            nv_enc_unregister_async_event: ptr::null_mut(),
            nv_enc_map_input_resource: ptr::null_mut(),
            nv_enc_unmap_input_resource: ptr::null_mut(),
            nv_enc_destroy_encoder: ptr::null_mut(),
            nv_enc_invalidate_ref_frames: ptr::null_mut(),
            nv_enc_open_encode_session_ex: ptr::null_mut(),
            nv_enc_register_resource: ptr::null_mut(),
            nv_enc_unregister_resource: ptr::null_mut(),
            nv_enc_reconfigure_encoder: ptr::null_mut(),
            reserved1: ptr::null_mut(),
            nv_enc_create_mv_buffer: ptr::null_mut(),
            nv_enc_destroy_mv_buffer: ptr::null_mut(),
            nv_enc_run_motion_estimation_only: ptr::null_mut(),
            nv_enc_get_last_error_string: ptr::null_mut(),
            nv_enc_set_io_cuda_streams: ptr::null_mut(),
            nv_enc_get_encode_preset_config_ex: ptr::null_mut(),
            nv_enc_get_sequence_param_ex: ptr::null_mut(),
            nv_enc_restore_encoder_state: ptr::null_mut(),
            nv_enc_lookahead_picture: ptr::null_mut(),
            reserved2: [ptr::null_mut(); 275],
        }
    }
}

#[repr(C)]
struct NvEncOpenEncodeSessionExParams {
    version: u32,
    device_type: u32,
    device: *mut c_void,
    reserved: *mut c_void,
    api_version: u32,
    reserved1: [u32; 253],
    reserved2: [*mut c_void; 64],
}

impl NvEncOpenEncodeSessionExParams {
    fn new_d3d11(device: *mut c_void) -> Self {
        Self {
            version: NV_ENC_OPEN_ENCODE_SESSION_EX_PARAMS_VER,
            device_type: NV_ENC_DEVICE_TYPE_DIRECTX,
            device,
            reserved: ptr::null_mut(),
            api_version: NVENCAPI_VERSION,
            reserved1: [0; 253],
            reserved2: [ptr::null_mut(); 64],
        }
    }
}

#[derive(Debug, Serialize)]
struct NativeProbeReport {
    success: bool,
    elapsed_ms: u128,
    nvenc_dll: String,
    nvenc_get_max_supported_version: bool,
    nvenc_max_supported_version_raw: u32,
    nvenc_max_supported_version_major: u32,
    nvenc_max_supported_version_minor: u32,
    d3d11_device_created: bool,
    d3d11_feature_level: String,
    nvenc_function_list_created: bool,
    nvenc_d3d11_session_opened: bool,
    notes: Vec<String>,
}

pub fn run_probe(command: ProbeNativeCommand) -> Result<()> {
    let started = Instant::now();
    let dll_path = PathBuf::from(r"C:\Windows\System32\nvEncodeAPI64.dll");
    let mut max_supported_version: u32 = 0;
    let mut notes = Vec::new();

    let library = unsafe { Library::new(&dll_path) }
        .with_context(|| format!("failed to load {}", dll_path.display()))?;
    let get_max_supported_version = unsafe {
        library
            .get::<NvEncodeApiGetMaxSupportedVersion>(b"NvEncodeAPIGetMaxSupportedVersion\0")
            .context("NvEncodeAPIGetMaxSupportedVersion symbol was not found")?
    };
    let status = unsafe { get_max_supported_version(&mut max_supported_version as *mut u32) };
    anyhow::ensure!(
        status == 0,
        "NvEncodeAPIGetMaxSupportedVersion failed with status {}",
        status
    );
    let feature_levels = [D3D_FEATURE_LEVEL_11_0];
    let mut device: Option<ID3D11Device> = None;
    let mut context: Option<ID3D11DeviceContext> = None;
    let mut selected_feature_level = D3D_FEATURE_LEVEL(0);
    unsafe {
        D3D11CreateDevice(
            None,
            D3D_DRIVER_TYPE_HARDWARE,
            HMODULE::default(),
            D3D11_CREATE_DEVICE_BGRA_SUPPORT,
            Some(&feature_levels),
            D3D11_SDK_VERSION,
            Some(&mut device),
            Some(&mut selected_feature_level),
            Some(&mut context),
        )
    }
    .context("failed to create D3D11 hardware device")?;
    anyhow::ensure!(device.is_some(), "D3D11CreateDevice returned no device");
    anyhow::ensure!(context.is_some(), "D3D11CreateDevice returned no context");
    let create_instance = unsafe {
        library
            .get::<NvEncodeApiCreateInstance>(b"NvEncodeAPICreateInstance\0")
            .context("NvEncodeAPICreateInstance symbol was not found")?
    };
    let mut function_list = NvEncodeApiFunctionList::default();
    let create_status =
        unsafe { create_instance(&mut function_list as *mut NvEncodeApiFunctionList) };
    anyhow::ensure!(
        create_status == NV_ENC_SUCCESS,
        "NvEncodeAPICreateInstance failed with status {}",
        create_status
    );
    anyhow::ensure!(
        !function_list.nv_enc_open_encode_session_ex.is_null(),
        "nvEncOpenEncodeSessionEx was not populated"
    );
    let open_session_ex: NvEncOpenEncodeSessionEx =
        unsafe { std::mem::transmute(function_list.nv_enc_open_encode_session_ex) };
    let destroy_encoder: Option<NvEncDestroyEncoder> =
        if function_list.nv_enc_destroy_encoder.is_null() {
            None
        } else {
            Some(unsafe { std::mem::transmute(function_list.nv_enc_destroy_encoder) })
        };
    let raw_device = device.as_ref().expect("D3D11 device exists").as_raw() as *mut c_void;
    let mut open_params = NvEncOpenEncodeSessionExParams::new_d3d11(raw_device);
    let mut encoder: *mut c_void = ptr::null_mut();
    let open_status =
        unsafe { open_session_ex(&mut open_params, &mut encoder as *mut *mut c_void) };
    anyhow::ensure!(
        open_status == NV_ENC_SUCCESS,
        "nvEncOpenEncodeSessionEx failed with status {}",
        open_status
    );
    anyhow::ensure!(
        !encoder.is_null(),
        "nvEncOpenEncodeSessionEx returned null encoder"
    );
    if let Some(destroy) = destroy_encoder {
        let _ = unsafe { destroy(encoder) };
    }
    notes.push("Loaded NVIDIA NVENC API DLL directly.".to_string());
    notes.push("Created a D3D11 hardware device.".to_string());
    notes.push("Opened and closed an NVENC D3D11 encode session; next phase can initialize H.264 config and submit GPU textures.".to_string());

    let report = NativeProbeReport {
        success: true,
        elapsed_ms: started.elapsed().as_millis(),
        nvenc_dll: dll_path.display().to_string(),
        nvenc_get_max_supported_version: true,
        nvenc_max_supported_version_raw: max_supported_version,
        nvenc_max_supported_version_major: max_supported_version >> 4,
        nvenc_max_supported_version_minor: max_supported_version & 0xF,
        d3d11_device_created: true,
        d3d11_feature_level: format!("{:?}", selected_feature_level),
        nvenc_function_list_created: true,
        nvenc_d3d11_session_opened: true,
        notes,
    };
    if let Some(parent) = command.report.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(
        &command.report,
        serde_json::to_string_pretty(&report).context("failed to encode native probe report")?,
    )
    .with_context(|| format!("failed to write {}", command.report.display()))?;
    println!("{}", serde_json::to_string_pretty(&report)?);
    Ok(())
}
