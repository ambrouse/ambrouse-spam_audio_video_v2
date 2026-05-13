# Chapter URL List Flow (Per Project)

## Muc tieu
- Moi project co 1 danh sach URL chuong chinh de tai su dung.
- Convert se uu tien doc danh sach URL da luu theo project.
- Frontend cho phep load, sua, save, clear ngay tren man hinh Convert.

## Luu tru
- Thu muc: `projects_workspace/projects/<project_id>/chapter_urls/`
- File chinh:
  - `urls_latest.txt` (danh sach URL chuan cua project)
  - `urls_<session_id>.txt` (ban sao theo session, neu co)

## Hanh vi runtime
1. Bam `Cao URL tu Chrome`:
- Crawl full URL list tu tab Chrome (CDP).
- Do vao textarea.
- Tu dong save vao `urls_latest.txt`.

2. Bam `Run Raw + Clean` hoac `Collect only`:
- Neu textarea co noi dung: dung noi dung do.
- Neu textarea rong va co `project_id`: backend auto doc `urls_latest.txt`.
- Mac dinh se chay theo toan bo URL list da co (khong tu cat lai).
- Neu can cat cua so theo `start_chapter` + `chapter_count` thi gui them `apply_chapter_window=true`.

## Frontend actions
- `Load URL List`: nap `urls_latest.txt` cua project vao textarea.
- `Save URL List`: luu noi dung textarea vao file URL list cua project.
- `Clear URL List`: xoa toan bo file `.txt` trong `chapter_urls/` cua project.

## API lien quan
- `GET /api/projects/{project_id}/chapter-urls`
- `POST /api/projects/chapter-urls/save`
- `POST /api/projects/chapter-urls/clear`
- `POST /api/convert/crawl-chapters-from-browser`
- `POST /api/convert/collect`
