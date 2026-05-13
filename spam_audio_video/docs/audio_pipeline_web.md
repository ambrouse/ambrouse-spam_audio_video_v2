# Audio Pipeline Web Controller

## Run with one command
```bash
bash setup.sh
```

## Manual run
```bash
cd source_full
python -m pip install -r requirements.txt
python run_web.py
```

Open: `http://localhost:8080`

## Current pipeline behavior
- Trigger by button: `POST /api/pipeline/audio/run`
- Convert all `auto_text_to_voice/text/*.txt` to `auto_text_to_voice/output/*.wav`
- Merge generated wav files to `source_full/audio/combined.wav`
- Persist metadata to `auto_text_to_voice/output/manifest.json`


## Voice profile rules
- System scan folder uto_text_to_voice/voice/ theo các thư mục con.
- Mỗi profile bắt buộc có: 1 file audio mẫu (.wav/.mp3/.flac/.m4a/.ogg) và 1 file text (oice.txt hoặc .txt không rỗng).
- Chọn profile trên UI trước khi bấm Run.



## New UI features
- Full-screen loadscene khi mở trang.
- Full-screen run overlay khi chạy pipeline (không còn thanh load trên cùng).
- Hiển thị logo từ repo ảnh theo rule.
- Nút xóa nhanh:
  - Clear All TXT
  - Clear Auto Output Audio
  - Clear Source Audio/Video



## Download feature
- Download Center hiển thị file audio/video trong source_full/audio và source_full/video.
- Chọn file và bấm Download để tải trực tiếp từ backend.

