# VieNeu-TTS Pipeline Guide

Tài liệu này giúp bạn đọc một lần là nắm được toàn bộ luồng chạy của dự án `VieNeu-TTS`, cách setup và cách chạy nhanh trên máy local.

## 1. Mục tiêu dự án

`VieNeu-TTS` là hệ Text-to-Speech tiếng Việt (kèm bilingual Anh-Việt ở Turbo v2), hỗ trợ:

1. Synthesize bằng giọng preset.
2. Voice cloning từ audio tham chiếu.
3. Chạy local (nhẹ, nhanh) hoặc remote server (chất lượng cao, production).

## 2. Cấu trúc source quan trọng

1. `src/vieneu/`
- `factory.py`: class `Vieneu` chọn engine theo mode.
- `turbo.py`: engine Turbo v2 (ưu tiên tốc độ, local CPU/GPU nhẹ).
- `standard.py`: engine chuẩn local.
- `fast.py`: fast path/optimized backend.
- `remote.py`: client mode gọi server TTS từ xa.
- `serve.py`: logic phục vụ model backend.
- `base.py`, `utils.py`: hàm nền tảng.

2. `src/vieneu_utils/`
- `phonemize_text.py`: chuẩn hóa + phonemize text.
- `core_utils.py`: split/join chunk audio, utility runtime.
- `url_extract.py`: tách URL/phần đặc biệt trong text.

3. `apps/`
- `gradio_main.py`: Web UI chính (`vieneu-web`).
- `web_stream.py`: Web UI stream (`vieneu-stream`).
- `gradio_xpu.py`: UI cho hướng chạy XPU.

4. `config.yaml`
- Cấu hình backbone, codec, text chunking, behavior của web app.

5. `examples/`
- Ví dụ dùng SDK local/remote.

6. `finetune/`
- Script/data pipeline cho fine-tune + merge LoRA.

## 3. Pipeline suy luận end-to-end

## 3.1 Local Turbo (mặc định, nhanh nhất)

1. Input text (+ optional voice preset hoặc ref audio).
2. Normalize và phonemize text qua `sea-g2p` + `vieneu_utils`.
3. Chia câu/chunk nếu dài (`split_text_into_chunks`, `split_into_chunks_v2`).
4. Engine Turbo (`src/vieneu/turbo.py`) sinh token/codec representation.
5. Decode thành waveform 24kHz bằng codec tương ứng.
6. Join chunk audio + thêm silence hợp lý.
7. Xuất `numpy audio` rồi save `.wav` bằng `soundfile`.

## 3.2 Local Standard / Fast

1. Tải backbone chuẩn (nặng hơn).
2. Thực thi inference với voice conditioning.
3. Decode audio tương tự.
4. Cho chất lượng tốt hơn Turbo trong nhiều ngữ cảnh nhưng tốn tài nguyên hơn.

## 3.3 Remote mode

1. SDK local chỉ encode input/ref voice nhẹ.
2. Gửi request tới server (`/v1`) đã host model lớn.
3. Nhận audio output về local để save/phát.

Phù hợp khi app client không có GPU hoặc muốn scale production.

## 4. Các mode chạy chính

1. `vieneu-web`:
- Chạy Gradio UI tiêu chuẩn.
- Mặc định ưu tiên Turbo v2 để vào nhanh.

2. `vieneu-stream`:
- UI/flow cho streaming synthesis.

3. SDK Python:
- `from vieneu import Vieneu`
- `tts = Vieneu(...)` rồi `tts.infer(...)`.

## 5. Setup môi trường khuyến nghị

Repo khuyến nghị `uv`:

```bash
uv sync
```

Nếu cần GPU group:

```bash
uv sync --group gpu
```

Fallback thuần `venv + pip`:

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Linux/macOS:
# source .venv/bin/activate
pip install -U pip setuptools wheel
pip install -e .
```

## 6. Cách chạy nhanh

1. Chạy Web UI:

```bash
uv run vieneu-web
```

2. Chạy stream UI:

```bash
uv run vieneu-stream
```

3. Chạy ví dụ SDK:

```bash
python examples/main.py
```

## 7. Dữ liệu model và tải model

Model không nằm toàn bộ trong repo; engine sẽ tải từ Hugging Face theo backbone bạn chọn trong app/config.

Các model tiêu biểu:

1. `pnnbao-ump/VieNeu-TTS-v2-Turbo-GGUF` (Turbo CPU)
2. `pnnbao-ump/VieNeu-TTS-v2-Turbo` (Turbo GPU)
3. `pnnbao-ump/VieNeu-TTS` (Standard chất lượng cao)
4. `pnnbao-ump/VieNeu-TTS-0.3B`

## 8. Chạy production (remote server)

Docker image server:

```bash
docker run --gpus all -p 23333:23333 pnnbao/vieneu-tts:serve --tunnel
```

Sau đó SDK local dùng `mode='remote'` để gọi API.

## 9. Nút thắt thường gặp

1. Cài `llama-cpp-python` lâu hoặc lỗi build:
- Dùng `uv` theo lock file để giảm xung đột.

2. Không có GPU:
- Dùng Turbo CPU (`v2-Turbo-GGUF`).

3. Chạy web báo thiếu package:
- Chạy lại `uv sync` hoặc `pip install -e .`.

4. Model tải lần đầu chậm:
- Bình thường, do download weights từ Hugging Face.

