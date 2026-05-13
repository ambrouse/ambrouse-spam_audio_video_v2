# Plan: Refactor spam_audio_video sang bridge toll-brouser-gpt-gemini, GPU-first, chunk audio 16-64 tu

## Cap nhat 2026-05-14

- Huong GPU-first da duoc sieu lai thanh GPU-only cho production audio/video.
- Audio runtime mac dinh CUDA; neu TTS venv dang la CPU-only PyTorch thi job fail ro loi thay vi chay CPU.
- Video render khong fallback `libx264`; `auto` phai chon duoc encoder GPU (`h264_nvenc`, `h264_qsv`, `h264_amf`).
- Clean/chunk/export TTS chi giu dau `.` va `,`; cac dau khac bi xoa, khong replace sang dau nghi.
- Mo port GPT/Gemini chi con nam o tab Bridge; tab GPT/video chi cau hinh ports de dung bridge.
- `.env` la tuy chon. Clone moi van tu nhan GPU neu `nvidia-smi` co san.

## 1. Muc tieu

Sua `spam_audio_video` de pipeline moi chay theo huong:

1. Cao truyen.
2. Goi `toll-brouser-gpt-gemini` de rewrite bang Gemini web bridge.
3. Clean dau cau va chunk audio theo khoang nghi, uu tien 16-64 tu.
4. Tao audio bang GPU neu may co GPU, chi fallback CPU khi khong co GPU.
5. Goi `toll-brouser-gpt-gemini` de viet prompt anh bang Gemini web bridge.
6. Goi `toll-brouser-gpt-gemini` de tao anh bang GPT web bridge.
7. Render/merge video bang encoder GPU neu co, chi fallback CPU khi khong co GPU.
8. Thiet ke lai UI theo cac chuc nang moi, them tab GPU Setting va nut Open Port cho Gemini/GPT.
9. Test bang request that va chay pipeline thuc te, khong chi smoke test.

## 2. Hien trang da doc

### spam_audio_video

- Backend chinh: `spam_audio_video/source_full/backend/server.py`.
- Convert service: `spam_audio_video/source_full/backend/convert_service.py`.
- Audio service: `spam_audio_video/source_full/backend/pipeline_service.py`.
- Video service: `spam_audio_video/source_full/backend/video_service.py`.
- Rewrite hien tai: `spam_audio_video/auto_convert_text/pipeline/gemini_rewriter.py`.
- Adapter LLM cu: `spam_audio_video/auto_convert_text/pipeline/gemini_adapter.py`.
- Clean audio text: `spam_audio_video/auto_convert_text/pipeline/audio_cleaner.py`.
- Chunk TTS: `spam_audio_video/auto_convert_text/pipeline/simple_chunker.py`.
- TTS worker: `spam_audio_video/auto_text_to_voice/vieneu_worker.py`.
- Video pipeline: `spam_audio_video/auto_generate_video/pipeline.py`.
- Frontend: `spam_audio_video/source_full/frontend/index.html`, `app.js`, `styles.css`.

Pipeline cu dang la:

- `Collector` cao chapter vao `chapters_text/raw`.
- `GeminiRewriter` goi `create_gemini_adapter`, hien dang uu tien OpenAI-compatible endpoint `http://localhost:20128/v1`.
- `AudioCleaner` chi giu chu, so, dau cham, dau phay, newline; dang replace `; : ! ?` sang dau cham.
- `SimpleChunker` dang mac dinh 24-96 tu, split theo `. ! ?`, chua toi uu cho 16-64 tu va dau phay/cham phay.
- `AudioPipelineService` goi `vieneu_worker.py`, worker dang `device=auto` va tu chon `cuda` neu `torch.cuda.is_available()`, nhung UI/backend chua co trang thai GPU ro rang.
- `VideoPipeline.generate_prompts` dang goi adapter LLM cu.
- `VideoPipeline.generate_images` con code `gpt_web` tu bam CDP bang Playwright trong source nay.
- `VideoPipeline.render_video` co auto encoder `h264_nvenc`, `h264_qsv`, `h264_amf`, fallback `libx264`, nhung UI chua show GPU/encoder thuc te.
- UI con nhieu phan cu: LLM endpoint `20128`, Gemini chrome pool rieng, GPT port CDP rieng.

### toll-brouser-gpt-gemini

Backend bridge chinh: `toll-brouser-gpt-gemini/examples/apps/gemini-use/server.py`.

Endpoint can dung:

- `POST /v1/web/open`
  - Body: `{ "ports": [9222, 9223], "force_reconnect": false }`
  - Mo/ket noi cac port, register cho ca Gemini va GPT scheduler.
- `GET /v1/ports/ping` hoac `POST /v1/ports/ping`
  - Kiem tra port active, managed_by.
- `POST /v1/chat/gemini`
  - Body: `{ "prompt": ["..."], "mode": "fast", "timeout_s": 600 }`
  - Ho tro batch prompt.
- `POST /v1/chat/gpt`
  - Tuong tu chat neu can.
- `POST /v1/image/gpt`
  - Body: `{ "prompt": ["..."], "timeout_s": 600, "max_images": 1, "response_format": "json" }`
  - Co `download_url`, `local_path`, `content_type`.
- `GET /v1/image/download/{file_name}`
  - Download anh neu image response tra download url.
- `POST /v1/image/clear`
  - Clear anh bridge neu can.

## 3. Skill can dung khi lam

- `backend-skill`: bat buoc cho cac phase sua backend service, adapter bridge, GPU status, API contract.
- `frontend-skill`: bat buoc cho phase sua UI.
- `documentation-skill`: bat buoc sau moi phase de cap nhat docs/task summary.
- `logging-skill`: bat buoc de log qua trinh lam viec theo tung phase.
- `testing-skill`: skill nay chua co trong danh sach hien tai, nen khi implement se thay bang quy trinh test nghiem ngat trong plan nay va cac test repo san co.
- `push-code-skill`: chi dung khi user yeu cau push sau khi da pass test.

## 4. Phase chi tiet

### Phase 0 - Baseline va xac nhan runtime (du kien 45 phut)

Cong viec:

- Doc lai file chinh da liet ke o muc 2 truoc khi edit.
- Ghi lai dependency hien co trong `source_full/requirements.txt` va moi truong `VieNeu-TTS`.
- Chay test/doc hien co neu khong qua nang.
- Xac dinh port bridge mac dinh, de xuat mac dinh `http://127.0.0.1:8008`.
- Xac dinh co nen giu compatibility endpoint cu khong. Huong de xuat: bo UI endpoint cu, backend co shim tam thoi 1 release neu can de tranh vo config cu.

Test phase:

- `python -m compileall spam_audio_video/source_full spam_audio_video/auto_convert_text spam_audio_video/auto_generate_video`
- Goi `/api/health` khi web backend chay.
- Goi `GET http://127.0.0.1:8008/v1/ports/ping` neu user da chay bridge.

### Phase 1 - Tao Browser Bridge client trong spam_audio_video (du kien 90 phut)

Cong viec:

- Tao client rieng, de xuat file:
  - `spam_audio_video/source_full/backend/bridge_client.py` hoac
  - `spam_audio_video/auto_convert_text/pipeline/browser_bridge_client.py` neu can dung chung cho convert/video.
- Config:
  - `bridge_base_url`, default `http://127.0.0.1:8008`.
  - `ports`, `timeout_s`, `mode`, retry, request id.
- Ham can co:
  - `open_ports(ports, force_reconnect=False)`.
  - `ping_ports(ports=None)`.
  - `chat(provider="gemini", prompts=[...], mode="fast")`.
  - `image(provider="gpt", prompts=[...], max_images=1)`.
  - `download_image(download_url, target_path)`.
- Parse response batch:
  - Chap nhan `answer` cho single.
  - Chap nhan `results[]` cho batch.
  - Loi ro rang neu bridge chua chay, port chua active, login/captcha/rate limit.
- Them endpoint backend trong `server.py`:
  - `GET /api/bridge/status`
  - `POST /api/bridge/open`
  - `POST /api/bridge/chat-test`
  - `POST /api/bridge/image-test`

Test phase:

- Unit test client bang monkeypatch/httpx mock.
- Request that khi bridge dang chay:
  - `POST /api/bridge/open` voi ports user mo.
  - `GET /api/bridge/status`.
  - `POST /api/bridge/chat-test` prompt ngan: "Tra loi dung mot tu: OK".
  - `POST /api/bridge/image-test` prompt anh don gian, verify file image duoc luu.

### Phase 2 - Thay rewrite Gemini API cu bang bridge Gemini (du kien 120 phut)

Cong viec:

- Refactor `GeminiRewriter` de khong dung `create_gemini_adapter` cu nua cho production.
- Them provider moi, de xuat `bridge_gemini`.
- Goi `POST /v1/chat/gemini` qua client, gui batch prompts theo `parallel_workers`.
- Giu resume logic va manifest hien co, nhung them:
  - `bridge_base_url`
  - `used_port`
  - `provider="bridge_gemini"`
  - `request_id`
- Sua default rewrite prompt:
  - Gemini rewrite thanh van ban audio.
  - Yeu cau cau ngan, tu nhien.
  - Chi dung dau `.`, `,`, `;` neu can nghi, khong dung markdown.
  - Dau hoi/cham than/ngoac/gach dau dong phai duoc chuyen thanh cau ke chuyen tu nhien.
  - Neu y dai, chen dau phay hoac cham phay de tao nghi.
  - Khong xoa thong tin vi dau cau la, ma chuyen ve dau nghi hop le.
- Sau rewrite van chay sanitize/validate de chan prompt echo, UI text, markdown.
- Clear UI/config cu lien quan OpenAI-compatible endpoint `20128` cho rewrite.

Test phase:

- Unit test `sanitize_rewritten_text`, `validate_rewrite`, parse batch result.
- Integration mock bridge cho 3 chapter, trong do 1 chapter fail/rate-limit de verify manifest failed/partial.
- Request that:
  - Tao project/session test 1-2 chapter.
  - Chay `/api/convert/projects/{project_id}/rewrite`.
  - Mo file `chapters_text/rewritten/chapter_*.txt`, verify khong co markdown, khong co prompt echo, co dau nghi hop ly.

### Phase 3 - Sua clean/chunk audio 16-64 tu, uu tien dau cau (du kien 120 phut)

Cong viec:

- Sua `AudioCleaner.clean_for_audio`:
  - Giu `.`, `,`, `;` nhu dau nghi hop le.
  - Replace `?`, `!`, `:`, dau ba cham, ngoac, gach ngang thanh `.`, `,` hoac khoang trang tuy ngu canh.
  - Khong don gian "xoa" ky tu dac biet neu ky tu do dang tao nghi; phai thay bang dau nghi phu hop.
  - Chuan hoa nhieu dau lien tiep.
- Sua `SimpleChunker` thanh pause-aware:
  - Mac dinh `min_words=16`, `max_words=64`.
  - Split uu tien theo dau `.`, sau do `;`, sau do `,`.
  - Neu clause ngan hon 16 tu thi gom voi clause ke tiep neu khong vuot 64.
  - Neu cau dai hon 64 tu thi cat tai dau phay gan 48-64 tu, neu khong co thi cat theo word boundary.
  - Khong de chunk rong, khong de chunk qua dai tru khi 1 token bat thuong.
  - Ghi `boundary_reason`, `word_count`, `punctuation_end` vao manifest.
- Sua defaults UI va backend:
  - `DEFAULT_TTS_MIN_WORDS=16`
  - `DEFAULT_TTS_MAX_WORDS=64`
  - Preset low la 16-64 va mac dinh selected.
- Can nhac giam `max_chars_tts` UI neu chunk ngan hon, nhung khong bat buoc.

Test phase:

- Unit test voi van ban co `. , ; ? ! : ... - ()`.
- Verify moi chunk trong 16-64 tu voi text binh thuong.
- Verify dau `? !` duoc chuyen thanh `.` de model co nghi.
- Request that:
  - Chay `/api/convert/projects/{project_id}/audio-clean`.
  - Chay `/api/convert/projects/{project_id}/chunk` voi 16-64.
  - Doc `tts_inputs/text_*.txt`, dem tu, kiem tra dau ket cau.

### Phase 4 - Thay tao prompt anh Gemini bang bridge Gemini (du kien 90 phut)

Cong viec:

- Refactor `VideoPipeline.generate_prompts`:
  - Bo phu thuoc `create_gemini_adapter`.
  - Goi `POST /v1/chat/gemini` qua bridge client.
  - Ho tro batch scene prompts theo `prompt_parallel_workers`.
  - Luu `used_port`, `request_id`, `provider="bridge_gemini"`.
- Sanitize prompt anh:
  - Chi 1 dong tieng Anh.
  - Khong markdown/link/data url.
  - Co negative cues.
  - Co 16:9/cinematic/no text/no watermark.
- Neu bridge fail 1 scene thi retry co gioi han, sau do manifest failed ro rang.

Test phase:

- Unit test sanitize prompt.
- Mock bridge batch voi 5 scenes.
- Request that:
  - Chay `/api/pipeline/video/prompts` tren session da co audio/tts_inputs.
  - Verify prompt files sinh ra dung so luong, dung format 1 dong.

### Phase 5 - Thay tao anh GPT port noi bo bang bridge GPT image (du kien 150 phut)

Cong viec:

- Refactor `VideoPipeline.generate_images`:
  - Bo luong `gpt_web` tu connect CDP trong `spam_audio_video`.
  - Provider moi/mac dinh: `bridge_gpt`.
  - Goi `POST /v1/image/gpt` qua bridge client.
  - Uu tien `response_format=json`, lay `download_url` hoac `local_path`, copy/download ve `session/video/images/scene_XXXX.png`.
  - Luu manifest:
    - `engine="bridge_gpt"`
    - `used_port`
    - `bridge_request_id`
    - `source_download_url`
    - `image_path`
- Don sach code thua:
  - Cac ham Playwright GPT trong `auto_generate_video/pipeline.py` neu khong con can.
  - UI `cdp_url/cdp_urls` cho GPT image trong source nay.
  - Text "GPT web Chrome pool" cu doi thanh "GPT bridge".
- Giu `sd_gguf` chi neu user con can fallback local image, neu muc tieu la clear het thi dat sau flag an/advanced hoac remove khoi UI.

Test phase:

- Unit test parse image JSON va download.
- Mock bridge image response JSON co `download_url`, `local_path`.
- Request that:
  - `POST /api/bridge/open` ports.
  - `POST /api/pipeline/video/images`.
  - Verify file anh thuc te ton tai, kich thuoc > 0, PIL mo duoc.
  - Neu GPT limit, verify loi hien ro va khong lam hong manifest.

### Phase 6 - GPU-first cho audio va video, them GPU Setting tab (du kien 150 phut)

Cong viec backend:

- Tao service GPU status, de xuat `source_full/backend/gpu_service.py`.
- Thu thap:
  - OS, Python, torch version.
  - `torch.cuda.is_available()`.
  - CUDA device count, device name, capability, VRAM total/free neu co.
  - `nvidia-smi` neu co: driver, GPU utilization, memory.
  - FFmpeg encoders available: `h264_nvenc`, `h264_qsv`, `h264_amf`, `libx264`.
  - TTS worker actual `runtime_device` tu prewarm/list runtime.
  - Video selected encoder actual tu `_resolve_video_encoder("auto")`.
- Endpoint:
  - `GET /api/gpu/status`
  - `POST /api/gpu/prewarm-audio`
  - `POST /api/gpu/check-video-encoder`
- Audio:
  - Giu `device=auto`, nhung log ro `cuda` hay `cpu`.
  - Neu user chon GPU required va khong co GPU thi bao loi som. Mac dinh van fallback CPU theo yeu cau.
- Video:
  - Mac dinh `video_encoder="auto"` va uu tien `h264_nvenc`, `h264_qsv`, `h264_amf`.
  - Neu GPU encoder co trong ffmpeg nhung render fail, ghi loi va fallback CPU chi khi config cho phep fallback.
  - Manifest phai co `video_encoder`, `gpu_fallback_used`, `fallback_reason`.

Cong viec frontend:

- Them tab `GPU Setting` trong Assets hoac nav rieng.
- Hien:
  - GPU detected yes/no.
  - TTS device actual.
  - Video encoder actual.
  - VRAM, driver, CUDA, torch.
  - Nut refresh, prewarm audio, check ffmpeg encoder.
- Trong progress/run result show "Audio device: cuda/cpu" va "Video encoder: h264_nvenc/libx264".

Test phase:

- Tren laptop khong GPU:
  - `GET /api/gpu/status` phai hien `gpu_available=false`, fallback CPU ro rang.
  - TTS van chay CPU neu dependency cho phep.
  - Video encoder fallback `libx264` neu khong co hardware encoder.
- Test mock GPU:
  - Monkeypatch `torch.cuda.is_available=True` va ffmpeg encoder list co `h264_nvenc`.
  - Verify selected GPU path.
- Tren may co GPU that, can user test sau:
  - `nvidia-smi` thay process Python/ffmpeg khi tao audio/video.
  - Manifest audio `device=cuda`.
  - Manifest video `video_encoder=h264_nvenc` hoac encoder GPU tuong ung.

### Phase 7 - Thiet ke lai UI theo backend moi (du kien 180 phut)

Cong viec:

- Bo/doi ten phan thua:
  - LLM endpoint `20128`, API key/model OpenAI-compatible.
  - Gemini Chrome pool cu cua `spam_audio_video`.
  - GPT CDP pool cu trong `spam_audio_video`.
- Them Bridge tab:
  - Bridge base URL.
  - Ports input dung chung.
  - Nut Open Gemini/GPT ports, thuc te goi `/api/bridge/open`.
  - Nut ping ports.
  - Test Gemini chat.
  - Test GPT image.
- Them GPU Setting tab nhu Phase 6.
- Cap nhat Convert tab:
  - Rewrite provider mac dinh Bridge Gemini.
  - Chunk preset mac dinh 16-64.
  - Run All hien ro cac buoc bridge/GPU.
- Cap nhat Video tab:
  - Prompt bang Gemini bridge.
  - Image bang GPT bridge.
  - Khong bat user nhap CDP URL nua, chi nhap port va bridge URL.
- UI can gon lai:
  - Chuc nang chinh tren man hinh dau: Run All, session, story URL, bridge status, GPU status.
  - Cac action rieng vao advanced/details.

Test phase:

- Test DOM/UI:
  - Khong con control endpoint cu `20128` o UI chinh.
  - Nut Open Port goi dung endpoint backend moi.
  - GPU tab render khong overlap desktop/mobile.
- Test bang browser thuc:
  - Mo backend web.
  - Click Open Ports, Ping, Test Chat, Test Image.
  - Chay Run All 1 chapter.

### Phase 8 - Test end-to-end bang request that va du lieu that (du kien 240 phut)

Dieu kien:

- User chay san `toll-brouser-gpt-gemini` server.
- User mo/login san Gemini va ChatGPT tren cac Chrome profile/ports can dung, hoac cho phep bridge auto open.
- De xuat ports: `9222,9223,9224`.

Test request that toi thieu:

1. Bridge:
   - `POST http://127.0.0.1:8008/v1/web/open`
   - `GET http://127.0.0.1:8008/v1/ports/ping`
   - `POST http://127.0.0.1:8008/v1/chat/gemini`
   - `POST http://127.0.0.1:8008/v1/image/gpt`
2. Backend spam_audio_video:
   - `GET /api/health`
   - `GET /api/gpu/status`
   - `POST /api/bridge/open`
   - `POST /api/bridge/chat-test`
   - `POST /api/bridge/image-test`
3. Convert:
   - Tao project/session.
   - Crawl URL that 1-2 chapter.
   - Rewrite qua Gemini bridge.
   - Audio clean.
   - Chunk 16-64.
4. Audio:
   - Chay TTS tren session.
   - Verify `.wav` ton tai, `combined.wav` ton tai, manifest co `device`.
   - Nghe nhanh file mau de bat loi dau cau/chunk qua dai.
5. Video:
   - Generate prompts qua Gemini bridge.
   - Generate images qua GPT bridge.
   - Render video, merge audio.
   - Verify mp4 mo duoc, co audio track, duration hop ly.
6. Resume/stop:
   - Stop giua pipeline va resume.
   - Verify khong tao duplicate/hong manifest.

Tieu chi pass:

- Khong con path production nao goi Gemini API cu `20128/v1` de rewrite/prompt.
- Khong con path production nao tu connect GPT CDP truc tiep trong `spam_audio_video` de tao anh.
- Tat ca rewrite/prompt/image di qua bridge endpoints cua `toll-brouser-gpt-gemini`.
- Chunk TTS phan lon nam trong 16-64 tu, uu tien nghi theo dau cau.
- Audio/video manifest hien actual device/encoder.
- UI hien trang thai bridge port va GPU ro rang.

### Phase 9 - Documentation, log, cleanup va push neu duoc yeu cau (du kien 90 phut)

Cong viec:

- Cap nhat docs trong `spam_audio_video/docs/`:
  - Architecture bridge moi.
  - GPU setting va fallback.
  - Test report request that.
  - Huong dan chay voi `toll-brouser-gpt-gemini`.
- Ghi log theo `logging-skill`.
- Clean dead code va comment cu.
- Chay lai test tong.
- Neu user yeu cau push thi doc `push-code-skill`, review diff, commit/push theo rule.

## 5. Tai nguyen can thiet

- `toll-brouser-gpt-gemini` server chay tren `http://127.0.0.1:8008`.
- Chrome/Edge ports da login:
  - Gemini/GPT bridge dung chung ports: `9222,9223,9224`.
- Web `spam_audio_video` backend chay local.
- Story URL that de test 1-2 chapter.
- Voice profile hop le trong `auto_text_to_voice/voice`.
- FFmpeg available.
- Neu test GPU that: may co NVIDIA/Intel/AMD GPU va driver ho tro encoder tuong ung.

## 6. Rui ro va cach giam

- Bridge UI web co the bi login/captcha/rate limit:
  - Hien loi ro, co ping/open/test rieng, retry co gioi han.
- Batch rewrite/prompt co the ve thieu item:
  - Map prompt theo index, manifest failed tung item, resume duoc.
- GPT image co the tra JSON nhung file khong tai duoc:
  - Ho tro ca `local_path`, `download_url`, va binary fallback neu can.
- GPU encoder co trong ffmpeg nhung driver fail luc render:
  - Detect truoc, render test ngan, fallback CPU co manifest reason.
- Chunk qua ngan lam giong doc dut:
  - Min 16 tu, gom clause ngan; chi cat duoi 16 khi gap cau don doc lap bat buoc.

## 7. Thu tu thuc hien khi user bao bat dau

1. Doc skill can cho phase hien tai.
2. Lam Phase 0.
3. Lam Phase 1, test phase, log/doc.
4. Lam Phase 2, test phase, log/doc.
5. Lam Phase 3, test phase, log/doc.
6. Lam Phase 4, test phase, log/doc.
7. Lam Phase 5, test phase, log/doc.
8. Lam Phase 6, test phase, log/doc.
9. Lam Phase 7, test UI thuc te, log/doc.
10. Lam Phase 8 end-to-end voi request that.
11. Lam Phase 9 tong ket.

