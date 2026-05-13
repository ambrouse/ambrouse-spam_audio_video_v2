# Plan Product Rewrite Web (Local-File First, No Database)

Date: 2026-05-01
Owner: Codex + Team
Status: Proposed

## 1) Muc tieu tong

Nang cap web controller thanh he thong quan ly project/session chuan product, tap trung vao:

- Luong vao web giong IDE: vao workspace -> chon/tao project -> vao dashboard project.
- Moi project quan ly day du session va toan bo artifact theo stage.
- CRUD chi tiet theo tung file + CRUD hang loat theo stage.
- Prompt va boi canh truyen theo project, co prompt default cap he thong.
- Du lieu nguon su that la local files, khong dung database.
- Khi mo project: preload toan bo du lieu can thiet (chapter list, prompt, txt, audio, video metadata).
- Co ke hoach clean project an toan: xoa cai khong dung sau khi co audit + backup + verify.

## 2) Hien trang va gap chinh

## 2.1 Hien trang backend/frontend

- Backend FastAPI da co nen tang project/session, convert stage APIs, TTS APIs, progress APIs.
- Frontend hien la SPA 1 file lon (`source_full/frontend/app.js`) va UI gom Projects/Convert/Voice/Assets.
- Registry hien tai: `project_registry/projects.json`.
- Workspace hien tai: `projects_workspace/projects/<project_id>/sessions/<session_id>/...`.

## 2.2 Gap so voi yeu cau moi

- Chua co flow vao app theo kieu IDE (workspace home -> project switcher tao moi -> project space).
- CRUD stage files hien moi manh (chu yeu list/load, clear stage), chua co full CRUD cho tung file tren tat ca stage.
- Chua co CRUD cho audio file le va audio tong theo session (delete/rebuild item-level).
- Chua co CRUD cho chapter list voi de-dup URL chuan hoa va co the crawl bo sung lien tuc.
- Prompt default theo yeu cau chua co (`projects_workspace/prompt_default` dang missing).
- Chua co co che boi canh truyen rieng, ro schema, va preload day du khi mo project.
- Frontend dang roi logic (JS monolith), nav va IA chua chuan product.
- Clean du an chua co quy trinh audit/xoa an toan theo bang phan loai.

## 3) Nguyen tac thiet ke ban moi

- Local-file only: moi trang thai quan trong deu co file contract ro rang.
- Deterministic paths: endpoint khong an side effect ngoai project/session active.
- Incremental rebuild: xoa 1 file -> co the tao lai dung 1 file do (khong buoc rerun full pipeline).
- No-backup policy: khong duy tri co che backup artifacts/logs trong runtime pipeline.
- Strong validation:
  - sanitize filename/path traversal,
  - lock conflict handling,
  - schema check JSON metadata.
- UI first-load: preload bat buoc theo project context, khong doi user bam them de "thay du lieu".
- Anti-unbounded-growth:
  - moi job/queue/log/cache phai co gioi han max-size va TTL ro rang.
  - khong chap nhan bat ky thuat toan tu dong nao co kha nang phinh vo han.

## 4) Muc tieu pham vi chuc nang (Product Scope)

## 4.1 Navigation va IA theo kieu IDE

- Man 1: Workspace Home
  - Danh sach project.
  - Tao project moi.
  - Search/sort/filter.
- Man 2: Project Shell (khi da chon project)
  - Left nav theo module: Overview, Sessions, Chapters, Prompt, Text Stages, Audio, Video (future), Logs.
  - Topbar: project switcher + quick create project + active session picker.

## 4.2 Project model (file-based)

Moi project co:

- `project.json` (metadata tong).
- `story_context.txt` (boi canh truyen).
- `rewrite_prompt.json` (override prompt theo project).
- `chapter_urls/` (list URL + history).
- `sessions/<session_id>/...` (artifact theo phien).

## 4.3 Session artifact model

Moi session quan ly day du:

- `raw`
- `rewritten` (gemini convert)
- `audio_clean`
- `tts_inputs`
- `audio/items/*.wav`
- `audio/combined.wav`
- `video/items/*` (future placeholder)
- `video/combined/*` (future placeholder)

Yeu cau CRUD:

- Per-file: Create, Read, Update, Delete.
- Per-stage bulk: list, clear all, rebuild all.
- Rebuild selective: co API tao lai 1 file huong muc tieu khi file loi.

## 4.4 Chapter list management

- CRUD chapter URLs day du:
  - create/add 1-n URL,
  - read/list/paginate,
  - update URL item,
  - delete 1 item / multi / all.
- Crawl bo sung lien tuc:
  - merge them vao danh sach hien tai,
  - chong trung URL theo normalized key (strip hash, trim slash, lowercase host/path can thiet).
- Luu lich su crawl theo timestamp.

## 4.5 Prompt system

- Prompt default cap he thong:
  - root: `projects_workspace/prompt_default/`
  - CRUD full.
- Prompt theo project:
  - override tu default.
  - CRUD full.
- Story context theo project:
  - file rieng (de xuat: `story_context.txt`).
  - load/persist rieng, truyen vao rewrite payload.

## 4.6 Preload data khi mo project

Khi user open project:

- Bat buoc preload:
  - project metadata,
  - sessions + summary,
  - chapter list,
  - prompt default + prompt project + story context,
  - file indexes cho raw/rewritten/audio_clean/tts_inputs,
  - audio index (items + combined),
  - video index (neu co).
- UI phai hien state complete ngay (hoac skeleton co source ro), khong buoc user bam "load".

## 4.7 Chrome Port Pool cho Gemini song song

- Them khu quan ly Chrome runtime trong UI:
  - danh sach custom ports (vi du: `9222,9223,9224...`)
  - so luong instance can mo (target count)
  - user-data-dir theo tung port
  - trang thai tung instance: `closed`, `opening`, `ready`, `login_required`, `running`, `error`
- Nut `Open Chrome Pool`:
  - bam 1 lan se mo dung 1 lan theo so luong da set.
  - khong mo trung lap instance da `ready`.
  - neu thieu instance so voi target count thi chi mo bo sung phan thieu.
- Login flow:
  - yeu cau login Gemini tren tung Chrome profile trong pool.
  - co checklist xac nhan `logged-in` truoc khi cho phep bat song song.
- Rewrite parallel orchestration:
  - chia chapter queue theo worker/port.
  - moi worker gan cung 1 CDP port co lock rieng.
  - retry theo file loi, khong rerun toan bo batch.
- Muc tieu rollout:
  - phase dau 3-4 ports, on dinh moi nang len 5-10 ports.

## 4.8 Safe Stop / Emergency Stop

- Them co che dung an toan khi dang chay pipeline:
  - `Stop` (graceful): dung tai checkpoint gan nhat, flush state, ghi checkpoint.
  - `Emergency Stop` (immediate): cat queue ngay, danh dau pending tasks la cancelled, yeu cau worker thoat.
- Stop phai ap dung cho:
  - run all flow,
  - tung stage flow,
  - gemini parallel worker pool.
- Dieu kien an toan khi dung:
  - khong de file dang ghi o trang thai mo hoac partial khong danh dau.
  - luu trang thai `stopped/cancelled` ro rang trong job/session metadata.
  - giu nguyen cac artifact da completed truoc khi dung.
- Sau khi stop:
  - cho phep `resume` tu checkpoint gan nhat.
  - hoac `rerun failed/cancelled files only`.

## 4.9 Log Governance va Log Management UI

- Thiet lap kien truc log chuan:
  - tach namespace log: `system`, `backend`, `frontend`, `pipeline`, `worker`, `audit`.
  - dinh dang log thong nhat (jsonl hoac line-structured text co timestamp/level/job_id/project_id/session_id).
- Co giao dien quan ly logs:
  - xem log theo namespace, level, project/session, time range.
  - tim kiem full-text.
  - tai log (co gioi han) va xoa log theo chinh sach.
  - nut `Clean Logs Now` theo tung nhom va toan bo.
- Chinh sach clean log bat buoc:
  - max file size / max so file / max tong dung luong.
  - rotate + prune theo age va dung luong.
  - gioi han so dong preview tra ve frontend.
- Khong backup log runtime.
- `docs/logs.md` la changelog product, khong phai noi luu log runtime vo han.

## 4.10 Cleanup Artifact va Bo Cuc Lai Kien Truc

- Dung va xoa cac backup folder/file dang ton tai (vi du cac muc `.tmp_backup_*`, backup text trung gian khong can thiet).
- Chuan hoa thu muc:
  - runtime source,
  - runtime artifacts co han muc,
  - logs co rotate,
  - docs.
- Cam tao them backup files tu dong trong pipeline.
- Build lai architecture theo quy tac bounded-storage:
  - moi loai artifact deu co retention policy.
  - co command cleanup deterministic, idempotent.

## 4.11 Knowledge Hub tren Frontend (Docs/Plan/Agent/Work Logs)

- Them khu quan ly tri thuc du an tren frontend, uu tien tham my va de dung:
  - docs technical,
  - plan implementation,
  - agent/work logs (bao gom log tuong tac va log runtime lien quan).
- Sap xep theo hoat dong gan nhat (`last_updated desc`) de nhin phat biet ngay viec moi.
- Moi file co metadata JSON de render professional cards:
  - `title`, `type`, `summary`, `diagram`, `owner`, `status`, `updated_at`, `tags`, `related_files`.
- Co tom tat so do ngan gon:
  - pipeline line,
  - module map,
  - phase progress map.
- Co mo ta ro rang cho tung muc:
  - file nay dung de lam gi,
  - tac dong toi flow nao,
  - trang thai hien tai.
- Trinh bay:
  - ngan gon, scan nhanh, de hieu,
  - co minh hoa (icon, mini-diagram, status badge),
  - nhat quan style, whitespace, typography.
- Tinh nang chinh:
  - filter theo `type/status/tag`,
  - tim kiem full-text metadata,
  - sort recent/alpha/priority,
  - quick open file.

## 5) Refactor backend chi tiet

## Phase B0 - Contracts va schema

- Chot JSON schemas:
  - `project.json`, `session.json`, `chapter_urls/index.json`, `prompt_default/*.json`, `rewrite_prompt.json`, `artifact_index.json`.
- Chot error model chung cho API.

Pass criteria:

- Co docs schema + sample payload cho tat ca entities.
- Validate duoc data cu (migrate-safe).

## Phase B1 - API project-first shell

- Them API workspace/project shell:
  - open project context (1 call aggregate preload),
  - create/switch project,
  - create/switch session.
- Giu backward compatibility endpoint cu trong giai doan chuyen doi.

Pass criteria:

- 1 API preload tra du data de render project dashboard.
- Khong can goi them endpoint de thay chapter/prompt/files co san.

## Phase B1.1 - Chrome pool control APIs

- Them API quan ly pool:
  - `POST /api/gemini/chrome-pool/open`
  - `POST /api/gemini/chrome-pool/close`
  - `GET /api/gemini/chrome-pool/status`
  - `POST /api/gemini/chrome-pool/mark-login-ready`
- Contract open pool:
  - nhan danh sach ports/target_count.
  - start cung luc va tra snapshot trang thai tung port.
  - dam bao idempotent: goi lai khong nhan doi so instance dang song.

Pass criteria:

- Bam `Open Chrome Pool` mo dung so instance da set trong 1 lan.
- UI thay duoc trang thai tung port va biet port nao can login.

## Phase B1.2 - Stop control APIs

- Them API dieu khien stop:
  - `POST /api/jobs/{job_id}/stop` (graceful)
  - `POST /api/jobs/{job_id}/emergency-stop` (immediate)
  - `GET /api/jobs/{job_id}/stop-status`
- Contract:
  - request stop co idempotency key.
  - response tra trang thai: `stopping`, `stopped`, `force_stopped`, `stop_failed`.
  - log ly do stop va actor.

Pass criteria:

- Co the dung ngay job dang chay ma khong lam vo contract file.
- Job transition state ro rang va truy vet duoc.

## Phase B1.3 - Log APIs + Retention control

- Them APIs quan ly logs:
  - `GET /api/logs/namespaces`
  - `GET /api/logs/query`
  - `POST /api/logs/clean`
  - `POST /api/logs/retention/apply`
- Them runtime guard:
  - hard-limit payload query.
  - hard-limit so file/doc tra ve.
  - reject query gay tai nang.

Pass criteria:

- Co the xem/loc/xoa logs tren web.
- Log storage khong vuot tran theo chinh sach da set.

## Phase B1.4 - Knowledge Index APIs (JSON-driven)

- Them API index metadata cho Knowledge Hub:
  - `GET /api/knowledge/index`
  - `POST /api/knowledge/reindex`
  - `GET /api/knowledge/file-meta?path=...`
  - `PATCH /api/knowledge/file-meta`
- Co che metadata:
  - moi file docs/plan/agent/log co sidecar `.meta.json` hoac index tap trung.
  - parser auto-doc cho file chua co meta (fallback title/summary tu heading dau).
- Ranking recent:
  - dua theo `git mtime` + `meta.updated_at` + log activity timestamp.
- Guardrails:
  - gioi han max file index va max payload.
  - bo qua binary/large files qua nguong.

Pass criteria:

- Frontend co 1 endpoint lay du catalog docs/plan/agent/log theo recent.
- Meta JSON du de render cards + summary + mini diagram.

## Phase B2 - File CRUD per stage

- Them API CRUD tung file cho stage text:
  - `raw`, `rewritten`, `audio_clean`, `tts_inputs`.
- Them API bulk + selective rebuild hooks.

Pass criteria:

- Xoa/sua/tao lai duoc 1 file o moi stage.
- Bulk clear khong anh huong stage khac.

## Phase B3 - Audio/Video artifact CRUD

- Audio:
  - list, get metadata, delete item wav, delete combined, rebuild combined tu selected items.
- Video (future-ready):
  - tao contract + endpoint placeholder, khong bat buoc generation runtime ngay.

Pass criteria:

- Xoa 1 audio loi va tao lai khong rerun full session.
- Rebuild combined audio deterministic.

## Phase B4 - Chapter URL manager

- CRUD full chapter list item-level.
- Crawl append mode + de-dup normalized URL.
- Co lich su crawl va merge report.

Pass criteria:

- Crawl bo sung 2 lan khong nhan ban URL.
- Delete/update tung URL item hoat dong dung.

## Phase B4.1 - Gemini parallel worker orchestration

- Them rewrite scheduler:
  - input: queue chapter files + chrome pool ready ports.
  - output: rewrite results theo file, progress hop nhat.
- Ho tro:
  - worker timeout,
  - retry backoff,
  - fail-fast threshold neu bi captcha/rate-limit lon.
- Persist checkpoint theo file de resume.
- Worker phai poll stop signal tan suat ngan de dung nhanh khi co su co.

Pass criteria:

- Rewrite parallel qua nhieu port hoat dong on dinh.
- File fail co the rerun rieng, khong can rerun full convert.
- Khi nhan stop, tat ca worker dung trong SLA muc tieu (vi du <= 3s voi emergency stop).

## Phase B5 - Prompt and context manager

- Tao `projects_workspace/prompt_default/` + APIs CRUD.
- Nâng cap prompt project CRUD + story context file rieng.
- Resolve prompt uu tien: project override > default.

Pass criteria:

- Prompt default co the cap nhat runtime.
- Moi project co prompt/context rieng, load dung khi switch project.

## Phase B6 - Cleanup/Deprecation APIs

- Deprecate endpoints cu trung lap/khong con dung.
- Them compatibility layer co canh bao de frontend moi on dinh.
- Bo cac co che backup runtime (neu con) va endpoint lien quan.

Pass criteria:

- API map ro rang old->new.
- Khong pha flow chinh.
- Khong con luong tao backup artifacts tu dong.

## 6) Refactor frontend chi tiet

## Phase F0 - Kien truc frontend

- Tach `app.js` thanh modules:
  - `core/api-client.js`
  - `core/state-store.js`
  - `modules/workspace/*`
  - `modules/project-shell/*`
  - `modules/session/*`
  - `modules/chapter-manager/*`
  - `modules/prompt-manager/*`
  - `modules/artifact-manager/*`
- Unified UI message + error boundary.

Pass criteria:

- Khong con monolith JS 1 file.
- Module ownership ro rang.

## Phase F1 - UX vao app theo IDE

- Workspace landing la man default.
- Chon project -> vao project shell.
- Tao project moi nhanh ngay topbar.

Pass criteria:

- User luon bat dau tu project context.
- Navbar khong con roi giua project va actions.

## Phase F1.1 - Chrome pool panel UX

- Them panel `Gemini Chrome Pool` trong project shell:
  - nhap list ports + target count.
  - nut `Open Chrome Pool` (mo 1 lan theo set).
  - nut `Close Pool`.
  - bang trang thai tung port + nut deep-link mo cua so login neu can.
- Co canh bao ro:
  - chua login du profile thi khong cho chay rewrite song song.

Pass criteria:

- Van hanh pool de dang, trang thai ro rang, khong mo trung lap.

## Phase F1.2 - Logs management page

- Them page `Logs` trong project shell:
  - bo loc namespace/level/job/project/session/time.
  - bang log + stream tail co gioi han.
  - action `Clean Selected Logs`, `Apply Retention Policy`.
- Co canh bao destructive ro rang truoc khi clean.

Pass criteria:

- Quan ly log ngay tren web, khong can vao filesystem thu cong.

## Phase F1.3 - Knowledge Hub UX (Tham my + Tien dung uu tien)

- Them page `Knowledge Hub` trong project shell:
  - section `Docs`, `Plans`, `Agent Notes`, `Work Logs`.
  - timeline `Recent Activity` dung dau trang.
- UI card design:
  - title ngan gon,
  - 2-3 dong summary,
  - mini-diagram/flow chip,
  - status + updated time + owner.
- Co `Project Snapshot` panel:
  - hien tai du an dang lam gi,
  - phase nao dang chay,
  - cac plan/doc lien quan nhat.
- Co style guide cho page nay:
  - visual hierarchy manh,
  - spacing rong,
  - contrast tot,
  - mobile va desktop deu de scan.

Pass criteria:

- Mo frontend la thay ngay buc tranh du an ngan gon, dep va de hieu.
- Tim docs/plan/log nhanh theo recent va filter.

## Phase F2 - Session manager UI

- Session list chuyen nghiep, filter/sort/status badges.
- Open session -> preload artifact tree.
- Actions: create, rename (neu cho phep), delete, duplicate.

Pass criteria:

- Session navigation nhanh, ro state.

## Phase F3 - Artifact CRUD UI

- File explorer cho tung stage + audio/video.
- Per-file actions: open/edit/save/delete/rebuild.
- Bulk actions: clear stage/rebuild stage.

Pass criteria:

- Xu ly 1 file loi khong can rerun toan bo.

## Phase F3.1 - Run All button (end-to-end)

- Them nut `Run All` chay lien tuc:
  - `collect raw -> gemini convert -> clean -> tts input -> tts`
- Co options:
  - `use_parallel_gemini` (on/off),
  - `chrome_pool_profile`,
  - `auto_retry_failed_files`.
- Khi `Run All`, UI lock cac action xung dot va hien pipeline timeline.
- Them nut:
  - `Stop` (an toan),
  - `Emergency Stop` (dung ngay).

Pass criteria:

- 1 nut chay full flow den audio output cho session active.
- Fail o dau co thong bao ro va co kha nang resume.
- Stop duoc tai moi thoi diem va UI cap nhat trang thai ngay lap tuc.

## Phase F4 - Chapter manager UI

- Bang chapter URLs co edit inline, add/remove, import/export text.
- Crawl append + dedupe report hien ngay.

Pass criteria:

- Crawl tiep khi truyen cap nhat va khong trung URL.

## Phase F5 - Prompt & context UI

- Tab Prompt default / Prompt project / Story context.
- CRUD full va compare override.

Pass criteria:

- Switch project -> prompt/context load san ngay.

## Phase F6 - Preload and performance

- On project open: batch preload + cache theo project/session.
- Skeleton loading + stale-while-refresh.

Pass criteria:

- Khong can bam nut "Load" de thay du lieu co san.

## Phase F6.1 - Unified continuous loadscene

- Loadscene phai lien tuc cho ca multi-step run:
  - khong tat giua cac stage.
  - chi tat khi pipeline ket thuc (success/fail/cancel).
- Doi progress contract:
  - backend tra stream/job state hop nhat cho toan flow.
  - frontend dung 1 overlay manager duy nhat, khong mount/unmount theo tung API rieng.
- Hien thi:
  - stage hien tai,
  - tong step da xong/tong step,
  - file done/total,
  - preview noi dung moi nhat.
- Hien thi them:
  - stop state (`stopping`, `stopped`, `force_stopped`),
  - thong bao resume option sau khi dung.

Pass criteria:

- Chay nhieu buoc lien tiep van giu 1 loadscene on dinh, khong nhap nhay/tat ngang.
- Khi stop, loadscene chuyen dung state dung cach va khong treo.

## Phase F6.2 - Knowledge preload va rendering performance

- Khi open project:
  - preload knowledge index metadata (khong preload full content file lon).
  - lazy-load noi dung chi khi user mo chi tiet.
- Co cache metadata theo project de UI mo nhanh.
- Gioi han so card hien thi mac dinh + pagination/virtual list.

Pass criteria:

- Knowledge Hub mo nhanh, khong lag du file docs/log nhieu.
- Van giu duoc thu tu recent chinh xac.

## 7) Ke hoach clean du an (an toan)

Luu y: xoa file/folder chi thuc hien sau audit theo checklist nay.

## Phase C0 - Inventory & classification

- Quet toan repo, phan loai:
  - Runtime source (giu)
  - Generated artifacts (co the clear)
  - Legacy/dead code (candidate remove)
  - Cache/temp (`__pycache__`, old logs)
- Tao file `docs/cleanup_inventory_2026-05-01.md`.
- Danh dau rieng:
  - backup folders/files,
  - logs phat sinh vo han,
  - artifacts khong con duoc tham chieu.

## Phase C1 - Safe removal policy

- Khong backup theo yeu cau du an; dung inventory + dry-run + explicit approve list.
- Xoa theo whitelist duoc approve.
- Moi muc xoa co ly do + tac dong + rollback.

## Phase C2 - Execute cleanup

- Xoa artifacts/rac khong can thiet.
- Xoa code dead sau khi da mapping reference (`rg`).
- Cap nhat `README`, `docs/logs.md`, `setup.sh`, `clear.sh`.
- Xoa backup folders/files va script/hook tao backup neu co.
- Them retention config cho logs va artifacts bounded-growth.

Pass criteria:

- Repo gon, chay duoc 1 lenh setup/run.
- Khong mat du lieu can van hanh.
- Khong con backup artifacts trong architecture moi.
- Khong co luong du lieu nao tang vo han neu khong co user intervention.

## 8) Cau truc thu muc de xuat sau refactor

```text
projects_workspace/
  prompt_default/
    rewrite_prompt.json
    story_context_template.txt
  projects/
    <project_id>/
      project.json
      story_context.txt
      rewrite_prompt.json
      chapter_urls/
        urls_latest.txt
        urls_history/
          urls_YYYYMMDD_HHMMSS.txt
      sessions/
        <session_id>/
          session.json
          chapters_text/
            raw/
            rewritten/
            audio_clean/
          tts_inputs/
          audio/
            items/
            combined.wav
            manifest.json
          video/
            items/
            combined/
          indexes/
            artifact_index.json
```

## 9) API de xuat bo sung (khong DB)

- Workspace/project context:
  - `GET /api/workspace/projects`
  - `POST /api/workspace/projects`
  - `GET /api/workspace/projects/{project_id}/open`
- Session CRUD:
  - `POST /api/projects/{project_id}/sessions`
  - `PATCH /api/projects/{project_id}/sessions/{session_id}`
  - `DELETE /api/projects/{project_id}/sessions/{session_id}`
- Artifact CRUD:
  - `GET /api/projects/{project_id}/sessions/{session_id}/artifacts?stage=...`
  - `POST /api/projects/{project_id}/sessions/{session_id}/artifacts/file`
  - `PATCH /api/projects/{project_id}/sessions/{session_id}/artifacts/file`
  - `DELETE /api/projects/{project_id}/sessions/{session_id}/artifacts/file`
  - `POST /api/projects/{project_id}/sessions/{session_id}/artifacts/rebuild`
- Chapters:
  - `GET/POST/PATCH/DELETE /api/projects/{project_id}/chapters`
  - `POST /api/projects/{project_id}/chapters/crawl-append`
- Prompt:
  - `GET/POST/PATCH/DELETE /api/prompt-default`
  - `GET/POST/PATCH/DELETE /api/projects/{project_id}/prompt`
  - `GET/POST/PATCH/DELETE /api/projects/{project_id}/story-context`
- Knowledge hub:
  - `GET /api/knowledge/index`
  - `POST /api/knowledge/reindex`
  - `GET /api/knowledge/file-meta`
  - `PATCH /api/knowledge/file-meta`
- Gemini chrome pool:
  - `POST /api/gemini/chrome-pool/open`
  - `POST /api/gemini/chrome-pool/close`
  - `GET /api/gemini/chrome-pool/status`
  - `POST /api/gemini/chrome-pool/mark-login-ready`
- End-to-end orchestration:
  - `POST /api/pipeline/run-all`
  - `POST /api/pipeline/run-all/resume`
- Safe stop:
  - `POST /api/jobs/{job_id}/stop`
  - `POST /api/jobs/{job_id}/emergency-stop`
  - `GET /api/jobs/{job_id}/stop-status`

## 10) Test strategy (production-minded)

## 10.1 Backend

- Unit tests cho path safety, dedupe URLs, CRUD stage files.
- Integration tests cho preload project context.
- Regression tests cho convert->tts flow hien tai.

## 10.2 Frontend

- Smoke test routing: workspace -> project shell -> session.
- E2E CRUD test tung stage file + audio item.
- Preload assertions: open project la co data ngay.

## 10.3 Runtime proof

- Kich ban that:
  - Crawl + append chuong moi khong trung.
  - Xoa 1 file rewritten loi -> rewrite lai dung file do.
  - Xoa 1 wav loi -> generate lai item do -> rebuild combined.
  - Mo Chrome pool theo set count, login day du, rewrite song song qua nhieu port.
  - Chay `Run All` tu raw den TTS voi loadscene lien tuc khong tat giua chung.
  - Stop/Emergency Stop trong luc run all, sau do resume thanh cong tu checkpoint.
  - Knowledge Hub hien dung thu tu recent va summary ro rang cho docs/plan/agent/log.

Pass criteria tong:

- Tat ca phase test pass 100% theo checklist.

## 11) Rollout plan

- Milestone 1: Backend contracts + preload API + prompt_default foundation.
- Milestone 2: Frontend IDE shell + preload UX.
- Milestone 3: Full CRUD stage/audio/video placeholder.
- Milestone 4: Logs governance UI + retention engine + bounded-growth guards.
- Milestone 5: Cleanup execution + docs/update scripts + final runtime report.

## 12) Rui ro va giam thieu

- Rui ro vo contract du lieu cu:
  - Giai phap: migration script + compatibility endpoints.
- Rui ro xoa nham khi cleanup:
  - Giai phap: inventory + backup + staged delete.
- Rui ro UI phuc tap lam cham:
  - Giai phap: chia module va rollout theo milestone.
- Rui ro lock file audio tren Windows:
  - Giai phap: retry/remove policy + thong bao lock ro rang.
- Rui ro log phinh nhanh lam day o dia:
  - Giai phap: rotate+prune hard limits + logs UI clean + scheduled retention apply.
- Rui ro backup rac tai xuat:
  - Giai phap: bo toan bo logic backup trong code review gate + CI grep rules.

## 13) Dau ra tai lieu bat buoc sau moi phase

- `docs/logs.md` cap nhat thay doi.
- Test report phase:
  - `docs/test_report_backend_product_refactor.md`
  - `docs/test_report_frontend_product_refactor.md`
- Update `README.md` theo flow moi (project-first IDE UX).

## 14) Quyet dinh quan trong da chot theo yeu cau

- Khong su dung database; chi local file.
- Project-first UX la bat buoc.
- Prompt default phai co CRUD rieng.
- Moi project co prompt rieng + boi canh truyen rieng.
- Session phai quan ly day du artifacts va CRUD tung file.
- Co clean du an toan, co audit truoc khi xoa.
- Khong su dung backup trong runtime architecture.
- Moi automation phai co gioi han, khong duoc phinh vo han.
