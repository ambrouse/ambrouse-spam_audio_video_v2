# Plan: Breath Chunk + Anti-Leak + Prosody Quality Upgrade

## Muc tieu
- Cai thien ro ret chat luong audio dau ra (giong goc, trong, sach).
- Cai thien ngu dieu khi doc truyen dai.
- Giam hien tuong leak 0.5-1s o dau cau.

## Pham vi thuc hien
1. Gemini Breath Chunker
- Sau audio_clean, dung Gemini de chia nhom lay hoi (khong chia co hoc theo ky tu).
- Luu ket qua vao `breath_chunks_manifest.json` trong session.
- Neu Gemini fail thi fallback chia cau an toan.

2. Export sang tts_inputs theo breath chunk
- `tts_exporter` uu tien dung breath manifest.
- Moi chunk xuat thanh `tts_inputs/text_XXXX.txt`.
- Manifest export co `pause_ms` de dung cho merge audio tu nhien.

3. TTS runtime optimization
- `max_len` dong theo do dai text chunk.
- Cho phep dieu chinh `inference_timesteps` qua API.
- Them log infer_ms tung file de benchmark.

4. Anti-leak dau cau
- Them trim thong minh vung dau (80-400ms, mac dinh 220ms) de giam prompt leak.
- Them thong ke `anti_leak_trim_applied_files` vao manifest audio.

5. Prosody merge
- Khi merge wav, chen pause map theo dau cau:
  - `,` ~140ms
  - `; :` ~260ms
  - `. ! ?` ~340ms

## Kien truc moi cua full convert
`collect -> rewrite -> audio_clean -> breath_chunk (Gemini) -> export tts_inputs -> tts`

## API lien quan
- Moi endpoint: `POST /api/convert/projects/{project_id}/breath-chunk`
- `/api/convert/run-full` da duoc noi breath chunk vao flow.
- `/api/pipeline/audio/run` bo sung:
  - `inference_timesteps`
  - `anti_leak_trim`
  - `anti_leak_max_ms`

## Tieu chi danh gia cai thien
- Dau cau giam leak nghe thay ro.
- Ngu dieu lien mach hon khi nghe lien tuc.
- TTS speed tot hon voi chunk ngan-vua nho max_len dong.
- Khong mat noi dung khi convert/export.

## Ghi chu production
- Uu tien 1 server + 1 worker GPU de tranh an VRAM chong cheo.
- Voice sample 8-15s, sach, it hoi-tho/noise de giam leak.
