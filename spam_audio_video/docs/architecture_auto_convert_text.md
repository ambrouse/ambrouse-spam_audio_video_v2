# Auto Convert Text Architecture

## Current Scope

Stage hien tai cua `auto_convert_text` chi lam:

```text
Chapter Sample URL -> Generate Chapter URLs -> Chapter HTML -> Raw TXT files -> Manifest
```

Chua day file sang `auto_text_to_voice/text/`. Rewrite, normalize, split/pack va TTS bridge la phase sau.

## Artifact Contract

Moi project convert luu trong:

```text
projects_workspace/projects/<project_id>/
  project.json
  sessions/<session_id>/
    session.json
    chapters_manifest.json
    chapters_text/
      raw/chapter_XXXX.txt
      normalized/
      rewritten/
      split/
    tts_inputs/
    logs/
```

Raw chapter text bat buoc nam trong:

```text
projects_workspace/projects/<project_id>/sessions/<session_id>/chapters_text/raw/
```

## Components

- `auto_convert_text/adapters/*`
  - Fetch chapter HTML va chuyen ve text bang parser generic.
- `auto_convert_text/pipeline/collector.py`
  - Nhan URL chapter mau, `start_chapter`, `chapter_count`.
  - Sinh URL chapter bang cach thay "doan tang theo chap" user set, cum so cuoi trong URL, hoac marker `{chapter}`.
  - Retry tung chapter.
  - Ghi `.txt` va `chapters_manifest.json`.
- `auto_convert_text/storage/project_store.py`
  - Quan ly folder project.
  - Ghi `project.json`, raw text, manifest.
- `source_full/backend/convert_service.py`
  - Bridge backend FastAPI sang collector.
- `source_full/frontend/*`
  - Panel Auto Convert Text tren controller hien tai.

## API

- `POST /api/convert/collect`
- `GET /api/convert/projects`
- `GET /api/convert/projects/{project_id}`

## TTS Defaults

Trang TTS hien tai mac dinh:

```text
temperature: 0.80
top_k: 80
max_chars: 420
ref_clean: false
```

Buoc lam sach audio mau truoc khi clone da duoc bo khoi frontend va backend mac dinh luon gui `preprocess_reference=false`.

## TTS Input Chunking (Current)

- Stage tao `tts_inputs` cat theo cau (`. ! ?`) va dong goi toi da trong nguong so tu.
- Default hien tai:
  - `min_words=24`
  - `max_words=96`
- Chien luoc dong goi:
  - khong flush som ngay khi vua dat `min_words`,
  - tiep tuc gom cau cho toi khi sap vuot `max_words`,
  - giup giam so file synth va giam overhead runtime.
