# Architecture: Gemini Rewrite, Audio Clean, Chunk, TTS Export

## Goal

Phase nay noi tiep sau collector:

```text
chapter sample URL -> raw chapter txt -> Gemini rewrite per chapter -> audio-clean text -> chunks -> auto_text_to_voice/text/*.txt
```

Muc tieu la bien chapter truyen da crawl thanh text san sang doc audio:

- co boi canh truyen.
- viet lai theo goc nhin nhan vat chinh.
- luoc bo canh khong quan trong.
- cau van de nghe bang TTS.
- chi giu dau cham va dau phay trong nhom dau cau.

## Folders

```text
auto_convert_text/data/projects/<project_id>/
  sessions/<session_id>/
    chapters_text/
      raw/chapter_XXXX.txt
      rewritten/chapter_XXXX.txt
      audio_clean/chapter_XXXX.txt
      chunks/chunk_XXXX.txt
    tts_inputs/<project_id>_<session_id>_text_XXXX.txt

Legacy non-session projects may still contain:

```text
auto_convert_text/data/projects/<project_id>/
  chapters_text/
    raw/chapter_XXXX.txt
    rewritten/chapter_XXXX.txt
    audio_clean/chapter_XXXX.txt
    chunks/chunk_XXXX.txt
  rewrite_manifest.json
  audio_clean_manifest.json
  chunks_manifest.json
  tts_export_manifest.json

auto_text_to_voice/text/
  text_0001.txt
  text_0002.txt

project_registry/projects.json
  shared project records used by convert and TTS stages
```

Each new convert run creates or reuses a session id:

```text
session_ch0001_to_ch0010
```

The session stores the exact chapter range so the same range can be converted again or sent back through TTS.

## Components

- `gemini_rewriter.py`
  - Builds prompts from raw chapter text and project rewrite config.
  - Sends exactly one prompt per raw chapter through a Gemini adapter.
  - Saves rewritten chapter text.
  - Writes `rewrite_manifest.json`.

- `gemini_adapter.py`
  - Interface:
    - `send_prompt(prompt) -> str`
  - Implementations:
    - `FakeGeminiAdapter` for deterministic tests.
    - `GeminiWebAdapter` for browser session opened by the user.

- `audio_cleaner.py`
  - Removes markdown and special symbols.
  - Allows Vietnamese letters, numbers, spaces, dot, comma.
  - Saves cleaned text for TTS.

- `chunker.py`
  - Splits text by dot first, comma second, whitespace fallback.
  - Preserves chapter order.
  - Writes `chunks_manifest.json`.

- `tts_exporter.py`
  - Copies chunks into `auto_text_to_voice/text/`.
  - Optional clear target folder only when explicitly enabled.
  - Writes `tts_export_manifest.json`.

- `shared_project_registry.py`
  - Stores project-level status outside `auto_convert_text` and `auto_text_to_voice`.
  - Lets the web UI select one active project and keep convert/TTS metadata together.

## Gemini Web Session Strategy

Dot dau tien khong yeu cau API key. He thong se dung phien Google/Gemini ma user da mo san.

Production-safe rule:

- Khong luu Google cookie/token vao repo.
- Khong hardcode account.
- Neu dung Playwright, uu tien attach vao Chrome/Edge remote debugging hoac persistent profile rieng.
- Khi chon provider `Gemini web session`, full pipeline tu mo Chrome bang:
  - `--remote-debugging-port=9222`
  - `--user-data-dir=D:\chrome-gemini-profile`
  - `https://gemini.google.com`
- Co fake adapter de test 100% logic pipeline ma khong phu thuoc Gemini UI.
- Real Gemini test chi la smoke test 1 chapter de chung minh integration.
- Real Gemini automation now filters visible prompt editors, avoids hidden Quill clipboard nodes, and extracts only the latest Gemini answer after the matching prompt.

## Validation

Moi stage phai co validation rieng:

- Rewrite:
  - output khong rong.
  - khong co markdown/code fence.
  - output length nam trong nguong cau hinh.
- Audio clean:
  - khong con ky tu dac biet ngoai dau cham va dau phay.
  - khong mat chu tieng Viet.
- Chunk:
  - moi chunk <= `max_chars`.
  - khong co chunk rong.
  - noi chunks lai khong mat text.
- Export:
  - file dich nam dung `auto_text_to_voice/text/`.
  - manifest map chunk -> exported file chinh xac.

## Unified Web Flow

Frontend hien tai giu flow van hanh thanh 2 nut chinh:

```text
Convert Text page: Run Convert To TTS TXT
TTS Studio page: Run Audio Pipeline
```

Nut Convert Text goi `POST /api/convert/run-full` va chay tu dau den cuoi:

```text
crawl chapter range -> save raw files -> Gemini rewrite each chapter once -> audio clean -> chunk -> export TTS TXT
```

Sau khi thanh cong, file cuoi nam trong `auto_text_to_voice/text/text_XXXX.txt` va co the dung ngay nut TTS Studio de tao audio.
