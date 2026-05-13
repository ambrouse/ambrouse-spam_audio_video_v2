# Plan Chi Tiet: Auto Convert Text Pipeline

## 1) Muc tieu

Xay dung pipeline `auto_convert_text` doc lap. Muc tieu dot hien tai chi can:

1. Nguoi dung paste 1 URL chapter mau, vi du:
   - `https://metruyenchu.co/truyen/vu-su-lang-hoc-phai-thu-ma-thu-ky/chuong-1`
2. Pipeline tu doi so chapter trong URL de sinh hang loat chapter theo range.
3. Sau khi load duoc chapter ve, luu moi chapter thanh file `.txt` rieng trong folder con cua project.
4. Toan bo code, metadata, log va file text cua pipeline convert nam trong `auto_convert_text/`.

Pipeline dot hien tai:

```text
Chapter Sample URL -> Generate Chapter URLs -> Fetch Chapter HTML -> Save TXT -> Manifest
```

Pipeline mo rong da noi vao web hien tai:

```text
Collect Raw TXT -> Gemini Rewrite Per Chapter -> Audio Text Clean -> Chunk -> Export TTS TXT -> TTS Bridge -> Video Bridge
```

Frontend hien tai van hanh bang 2 nut chinh:

```text
Convert Text page: Run Convert To TTS TXT
TTS Studio page: Run Audio Pipeline
```

---

## 2) Pham vi va nguyen tac

### 2.1 Pham vi code

- Toan bo logic pipeline convert nam trong: `auto_convert_text/`.
- Toan bo artifact cua convert pipeline nam trong: `auto_convert_text/data/`.
- Frontend/backend trong `source_full/` chi dieu phoi lenh chay, khong luu artifact convert ra ngoai `auto_convert_text/`.

### 2.2 Input muc tieu dot nay

- Khong can ho tro nhieu domain bang adapter rieng trong dot nay.
- Input chinh la 1 URL chapter mau co so chapter trong URL.
- Neu URL co nhieu so, user co the set "doan tang theo chap" tren frontend, vi du `chuong-1`.
- Neu khong set doan tang, mac dinh thay cum so cuoi cung.
- Neu can chi dinh ro vi tri doi so trong URL, van cho phep dung marker `{chapter}`.

Vi du:

```text
URL mau: https://metruyenchu.co/truyen/vu-su-lang-hoc-phai-thu-ma-thu-ky/chuong-1
Start: 1
Count: 3

Sinh ra:
https://metruyenchu.co/truyen/vu-su-lang-hoc-phai-thu-ma-thu-ky/chuong-1
https://metruyenchu.co/truyen/vu-su-lang-hoc-phai-thu-ma-thu-ky/chuong-2
https://metruyenchu.co/truyen/vu-su-lang-hoc-phai-thu-ma-thu-ky/chuong-3
```

### 2.3 Nguyen tac crawl

- Khong can lay TOC/JSON trong dot nay.
- Chi sinh URL chapter bang cach thay so chapter trong URL mau.
- Co retry + backoff + log loi theo tung chapter.
- Loi chapter khong duoc lam sap toan bo run.

### 2.4 Tieu chuan production

- Moi run co `project.json` va `chapters_manifest.json`.
- Co co che resume sau nay dua tren project artifact.
- Moi chapter success phai co file `.txt` khong rong.

---

## 3) Kien truc de xuat

### 3.1 Cau truc thu muc

```text
auto_convert_text/
  adapters/
    base.py
    generic.py
  pipeline/
    collector.py
    gemini_rewriter.py  # phase tiep theo
    audio_cleaner.py    # phase tiep theo
    chunker.py          # phase tiep theo
    tts_exporter.py     # phase tiep theo
    tts_bridge.py       # phase sau
  storage/
    project_store.py
  models/
    dto.py
  cli/
    run_convert.py
  data/
    projects/<project_id>/
      project.json
      chapters_manifest.json
      chapters_text/
        raw/
        rewritten/       # Gemini rewrite output
        audio_clean/     # text da sach cho audio
        chunks/          # chunk trung gian
      tts_inputs/        # ban copy/manifest truoc khi day sang auto_text_to_voice/text
      logs/
```

### 3.2 Quy uoc luu chapter dot hien tai

- Sau khi collector fetch thanh cong chapter, bat buoc ghi file vao:
  - `auto_convert_text/data/projects/<project_id>/chapters_text/raw/chapter_XXXX.txt`
- Moi file `.txt` chi chua text cua mot chapter.
- Ten file dung zero-padding theo so chapter:
  - `chapter_0001.txt`
  - `chapter_0002.txt`
  - `chapter_0100.txt`
- Metadata cua chapter duoc ghi vao:
  - `auto_convert_text/data/projects/<project_id>/chapters_manifest.json`
- Khong ghi file chapter vao `auto_text_to_voice/text/` trong phase nay.

### 3.3 Data model toi thieu

- `Project`
  - `project_id`, `name`, `story_url`, `domain`, `status`
  - `start_chapter`, `chapter_count`
- `Chapter`
  - `chapter_no`, `title`, `source_url`, `status`
  - `raw_text_path`, `rewritten_path`, `audio_clean_path`, `chunk_paths`, `tts_export_paths`, `error`
- `RewriteConfig`
  - `provider`, `model`, `prompt_template`, `story_context`, `pov`, `remove_unimportant_scenes`
  - `allowed_punctuation`, `max_retry`, `manual_review_required`
- `TextChunk`
  - `chunk_index`, `from_chapter`, `to_chapter`, `char_count`, `text_path`, `status`

---

## 4) Phase trien khai chi tiet

## Phase 0 - Discovery + Contract

### Muc tieu

- Chot contract input/output cho pipeline convert.
- Chot quy uoc URL chapter mau va duong dan artifact.

### Cong viec

1. Dinh nghia DTO + schema.
2. Dinh nghia file manifest.
3. Chot quy uoc thay so chapter trong URL.

### Test & pass

- Validate schema bang unit test/parser test.
- Tao duoc project skeleton tren disk.

---

## Phase 1 - Collector Theo URL Chapter Mau

### Muc tieu

- Tu 1 URL chapter mau, sinh URL theo range chapter.
- Fetch content tung chapter.
- Luu moi chapter thanh file `.txt` rieng trong `auto_convert_text/data/projects/<project_id>/chapters_text/raw/`.

### Cong viec

1. Viet logic detect vi tri so chapter trong URL mau.
2. Ho tro 3 cach sinh URL:
   - user set doan tang theo chap, vi du `chuong-1`.
   - thay cum so cuoi cung trong URL.
   - thay marker `{chapter}` neu user muon chi dinh vi tri.
3. Viet `collector.py`:
   - nhan `chapter_sample_url + start + count`
   - sinh URL chapter theo thu tu
   - fetch chapter theo thu tu
   - tao folder project trong `auto_convert_text/data/projects/<project_id>/`
   - tao folder con `chapters_text/raw/`
   - luu `chapters_text/raw/chapter_XXXX.txt`
   - cap nhat `chapters_manifest.json`
4. Retry/backoff + timeout + user-agent.

### Test & pass

- Runtime test:
  - URL mau + doan tang `chuong-1`, `count=2`: pass 100% voi server local.
  - URL mau `/chuong-1`, `count=2`: pass 100% voi server local.
  - URL mau `/chuong-{chapter}`, `count=2`: pass 100% voi server local.
- Kiem tra chapter file luu dung ten va dung thu tu.
- Kiem tra khong co artifact convert nao bi ghi ra ngoai `auto_convert_text/`.
- Kiem tra moi chapter success co file `.txt` khong rong trong `chapters_text/raw/`.

---

## Phase 2 - Gemini Rewrite Qua Phien Google/Gemini Co San

### Muc tieu

- Lay raw chapter `.txt` trong `chapters_text/raw/`.
- Gui tung chapter hoac tung nhom chapter sang Gemini thong qua phien Google/Gemini ma user da mo san.
- Rewrite lai theo prompt cua project:
  - boi canh truyen.
  - viet lai duoi goc nhin nhan vat chinh.
  - luoc bo canh khong quan trong.
  - giu mach truyen de nghe audio lien mach.
  - bo ky tu dac biet, chi giu chu, so, khoang trang, dau cham va dau phay.
- Luu output vao `chapters_text/rewritten/chapter_XXXX.txt`.

### Nguyen tac automation Gemini

- Dot dau tien uu tien browser automation voi phien dang nhap san cua user, khong yeu cau API key.
- Khong luu cookie/token Google vao repo.
- Neu can automation on dinh, chay Chrome/Edge bang remote debugging hoac persistent profile rieng, roi Playwright attach vao phien do.
- Moi request Gemini phai co timeout, retry, va co co che manual-resume neu Gemini bi captcha, popup, rate limit, hoac UI thay doi.
- Khong gui qua nhieu chapter mot luc neu de gay mat context/qua token.

### Prompt contract

Prompt can gom:

```text
Ban la bien tap truyen audio tieng Viet.
Boi canh truyen: {story_context}
Yeu cau:
1. Viet lai duoi goc nhin nhan vat chinh.
2. Giu y chinh va mach truyen.
3. Luoc bo canh khong quan trong, lap lai, quang cao, menu web.
4. Van phong de doc thanh audio, cau ngan vua phai, nghe tu nhien.
5. Chi duoc dung dau cham va dau phay, khong dung ky tu dac biet khac.
6. Khong them markdown, khong danh so muc, khong giai thich.
Noi dung chapter:
{chapter_text}
```

### Cong viec

1. Them config rewrite trong project:
   - `story_context`
   - `main_character_pov`
   - `rewrite_prompt`
   - `chapters_per_gemini_request`
   - `min_output_chars_ratio`
   - `max_output_chars_ratio`
2. Viet `gemini_rewriter.py`:
   - doc `chapters_manifest.json`.
   - lay raw chapter theo thu tu.
   - gui moi chapter sang Gemini dung 1 lan, khong gop nhieu chapter vao cung mot prompt.
   - tao prompt.
   - gui sang Gemini web session.
   - lay response.
   - validate response.
   - luu `chapters_text/rewritten/chapter_XXXX.txt`.
3. Ghi rewrite manifest:
   - `rewrite_manifest.json`
   - status tung chapter.
   - prompt hash.
   - input/output path.
   - retry count.
4. UI page Convert Text gom rewrite vao nut full pipeline:
   - nhap boi canh truyen.
   - nhap prompt rieng.
   - chon provider Gemini web hoac fake adapter.
   - nut `Run Convert To TTS TXT`.
   - progress tong cho full pipeline.

### Test & pass

- Unit test prompt builder.
- Runtime test voi fake Gemini adapter:
  - 3 chapter input.
  - 3 rewritten output.
  - manifest dung thu tu.
- Runtime test voi Gemini web session that:
  - 1 chapter ngan.
  - response lay duoc va luu file.
- Pass 100% khi:
  - chapter fail khong lam sap toan bo run.
  - chapter success co file rewritten khong rong.
  - output khong chua markdown/code fence.
  - manifest ghi day du loi neu fail.

---

## Phase 3 - Audio Text Clean

- Chuan hoa text than thien TTS.
- Bo ky tu dac biet sau rewrite.
- Chi giu lai:
  - chu cai tieng Viet.
  - so.
  - khoang trang.
  - dau cham `.`
  - dau phay `,`
- Luu `chapters_text/audio_clean/chapter_XXXX.txt`.

### Cong viec

1. Viet `audio_cleaner.py`.
2. Chuan hoa unicode/encoding.
3. Thay cac dau cau khac bang dau phay hoac dau cham tuy ngu canh.
4. Xoa markdown, emoji, ngoac dac biet, dau gach dau dong, quote marker.
5. Chuan hoa khoang trang va do dai dong.
6. Dam bao khong xoa mat chu tieng Viet.

### Test & pass

- Unit test bo ky tu dac biet.
- Runtime test 10 rewritten chapters.
- Pass 100% khi:
  - output chi con allowed charset.
  - khong rong file.
  - do dai output nam trong nguong hop ly so voi rewritten input.

---

## Phase 4 - Chunk Text Cho Audio

### Muc tieu

- Chia text audio-clean thanh chunk phu hop TTS.
- Moi chunk duoc doc tu nhien, khong cat giua cau neu co the.
- Luu chunk trung gian vao `chapters_text/chunks/`.

### Quy uoc chunk

- Chunk theo gioi han ky tu cau hinh, vi du:
  - `target_chars = 2500`
  - `max_chars = 4200`
  - `min_chars = 600`
- Uu tien cat tai dau cham.
- Neu khong co dau cham phu hop thi cat tai dau phay.
- Neu van qua dai thi cat tai khoang trang gan nhat.
- Ten file:
  - `chunk_0001.txt`
  - `chunk_0002.txt`
  - `chunk_0003.txt`

### Cong viec

1. Viet `chunker.py`.
2. Doc `audio_clean` theo thu tu chapter.
3. Co tuy chon:
   - 1 chunk co the gom nhieu chapter ngan.
   - chapter dai co the tach thanh nhieu chunk.
4. Ghi `chunks_manifest.json`:
   - chunk index.
   - source chapters.
   - char count.
   - output path.

### Test & pass

- Unit test cat theo dau cham/phay/khoang trang.
- Runtime test 10 chapter.
- Pass 100% khi:
  - khong mat text.
  - tong text chunks sau khi noi lai tuong duong input audio-clean.
  - moi chunk <= `max_chars`.
  - khong co chunk rong.

---

## Phase 5 - Export Sang `auto_text_to_voice/text`

### Muc tieu

- Copy chunk da tao thanh tung file `.txt` trong `auto_text_to_voice/text/`.
- Day la output san sang cho TTS pipeline hien tai.

### Quy uoc export

- Truoc khi export co tuy chon clear folder dich:
  - mac dinh khong clear neu user chua xac nhan.
  - UI co checkbox `Clear old TTS txt before export`.
- File dich:
  - `auto_text_to_voice/text/text_0001.txt`
  - `auto_text_to_voice/text/text_0002.txt`
  - `auto_text_to_voice/text/text_0003.txt`
- Manifest:
  - `auto_convert_text/data/projects/<project_id>/tts_export_manifest.json`

### Cong viec

1. Viet `tts_exporter.py`.
2. Validate chunk path nam trong project.
3. Copy chunks sang `auto_text_to_voice/text/`.
4. Ghi manifest map:
   - chunk path.
   - exported txt path.
   - char count.
5. UI export duoc noi vao nut `Run Convert To TTS TXT`.

### Test & pass

- Runtime test export 3 chunks.
- Pass 100% khi:
  - `auto_text_to_voice/text/` co dung so file.
  - noi dung file dich trung voi chunk source.
  - manifest map chinh xac.
  - khong xoa file cu neu user khong bat clear.

---

## Phase 6 - TTS Bridge

Phase sau.

### Muc tieu

- Tu dong day chunk TXT sang `auto_text_to_voice/text`.
- Audio generation van duoc kick bang nut rieng tren trang TTS Studio.

---

## Phase 7 - UI Project Manager

Da co page Convert Text trong frontend hien tai.

### Chuc nang hien tai cho phase rewrite/chunk/export

1. Nhap URL chapter mau va doan tang theo chap.
2. Nhap boi canh truyen va prompt rewrite.
3. Chon provider Gemini web session hoac fake adapter.
4. Cau hinh target/max chunk chars.
5. Chay mot nut `Run Convert To TTS TXT` de crawl, rewrite, clean, chunk va export.
6. Xem status/manifest tong trong status output.

### API

- `POST /api/convert/collect`
- `GET /api/convert/projects`
- `GET /api/convert/projects/{id}`
- `POST /api/convert/projects/{id}/rewrite`
- `POST /api/convert/projects/{id}/audio-clean`
- `POST /api/convert/projects/{id}/chunk`
- `POST /api/convert/projects/{id}/export-tts-text`

---

## 5) Ke hoach test runtime

### 5.1 Test matrix URL mau

- URL co so cuoi: `/chuong-1`
- URL co doan tang user set: `chuong-1`
- URL co marker: `/chuong-{chapter}`
- Moi mode test:
  - `count=2`
  - `start=bat ky + count=2`

### 5.2 Tieu chi pass tong

1. Crawl pass 100% trong runtime test local.
2. Manifest day du va dung thu tu chapter.
3. Tat ca chapter success co file `.txt` khong rong trong `auto_convert_text/data/projects/<project_id>/chapters_text/raw/`.
4. Khong co artifact convert nao bi ghi ra ngoai `auto_convert_text/`.
5. Frontend page Convert Text goi duoc API collect.
6. Rewrite Gemini co fake adapter pass 100% va real Gemini smoke test pass voi 1 chapter.
7. Audio clean chi con dau cham va dau phay trong nhom dau cau.
8. Chunk khong mat text va khong vuot `max_chars`.
9. Export tao dung file trong `auto_text_to_voice/text/`.

---

## 6) Rui ro va giai phap

1. URL khong co so chapter:
   - Giai phap: bao loi ro rang, yeu cau them `{chapter}`.
2. Website doi HTML:
   - Giai phap: HTML-to-text generic + log fail tung chapter.
3. Domain co anti-bot:
   - Giai phap: retry/backoff/user-agent/session pooling.
4. Chapter bi thieu:
   - Giai phap: chapter fail ghi vao manifest, pipeline tiep tuc.
5. Gemini web UI thay doi hoac bi captcha:
   - Giai phap: tach Gemini adapter, co fake adapter de test, co manual-resume va log loi ro.
6. Gemini tra ve markdown hoac ky tu dac biet:
   - Giai phap: validation + audio_clean stage bat buoc.
7. Rewrite lam sai y truyen:
   - Giai phap: prompt co story context, ty le output min/max, va sample review truoc khi chay hang loat.
8. Export ghi de file TTS cu:
   - Giai phap: checkbox clear explicit + backup/manifest truoc khi ghi.

---

## 7) Deliverables

### Deliverables dot hien tai

1. Code collector pipeline trong `auto_convert_text/`.
2. Project store trong `auto_convert_text/data/projects/<project_id>/`.
3. File chapter `.txt` trong `auto_convert_text/data/projects/<project_id>/chapters_text/raw/`.
4. Manifest `auto_convert_text/data/projects/<project_id>/chapters_manifest.json`.
5. Frontend page Convert Text trong `source_full/`.
6. Docs:
   - `docs/plan_auto_convert_text_pipeline.md` (file nay)
   - `docs/architecture_auto_convert_text.md`
   - `docs/test_report_auto_convert_text.md`
   - `docs/logs.md`

### Deliverables phase sau

1. Gemini rewriter.
2. Audio cleaner.
3. Chunker.
4. TTS text exporter.
5. UI controls cho rewrite/clean/chunk/export.
6. Test report runtime cho tung stage.
7. `setup.sh` cap nhat neu them dependency moi.

---

## 8) Thu tu thuc thi de nghi

1. Phase 0 -> 1: URL chapter mau -> raw `.txt` trong `auto_convert_text`.
2. Dung tai milestone nay de test runtime that ky: URL -> chapter files -> manifest.
3. Phase 2: Gemini rewrite bang fake adapter truoc, sau do smoke test Gemini web session that.
4. Phase 3: audio clean.
5. Phase 4: chunk.
6. Phase 5: export sang `auto_text_to_voice/text`.
7. Phase 6: bridge TTS.
