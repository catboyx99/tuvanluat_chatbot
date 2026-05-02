---
name: deploy
description: Pull source mới nhất từ GitHub và rebuild Docker stack của chatbot tư vấn luật trên server production. Dùng khi user nói "deploy", "cập nhật server", "pull về server".
---

# DEPLOY — Cập nhật chatbot lên server

Tài liệu dành cho mọi AI agent (Claude, Gemini, GPT, ...). Đọc hết rồi chạy tuần tự.

## Thông tin
- Repo: `https://github.com/catboyx99/tuvanluat_chatbot` — branch `main`
- Thư mục trên server: `~/tuvanluat_chatbot` (Ubuntu, bash)
- Cần có sẵn: `git`, `docker`, `docker compose` v2

## Tiền đề (kiểm tra, KHÔNG tự tạo)
1. `.env` tồn tại ở root repo và chứa `GEMINI_API_KEY=<key>`.
2. Docker daemon đang chạy (`docker info` OK).

Nếu thiếu → DỪNG, báo user.

## Quyết định MODE deploy (BẮT BUỘC đọc trước khi chạy)

So sánh diff giữa commit cũ (`OLD`) và commit mới (`NEW`), chọn 1 trong 2 mode:

### Mode A — Normal (giữ ChromaDB)
**Khi nào dùng**: Thay đổi CHỈ liên quan frontend, prompt LLM, API logic, UI — KHÔNG đụng ingest pipeline hay schema metadata.

Tín hiệu: `git diff OLD NEW --name-only` KHÔNG chứa bất kỳ file nào sau đây:
- `backend/app/document_loader.py` (ingest logic)
- `md_materials/*.md` (nội dung ingest)
- Bất kỳ field metadata mới nào thêm vào chunk

**Lệnh**: `docker compose up -d --build` (không đụng volume, không tốn embedding cost).

### Mode B — Full re-ingest (wipe ChromaDB)
**Khi nào dùng**: Có sửa ingest logic, đổi metadata schema, thêm/xoá/sửa file `md_materials/`, hoặc commit message ghi rõ cần re-ingest.

Tín hiệu:
- `git diff OLD NEW --name-only` có `backend/app/document_loader.py` HOẶC `md_materials/`
- Commit message chứa "re-ingest", "wipe chroma", hoặc "metadata schema"

**LƯU Ý**: Đổi regex extract metadata trong `document_loader.py` (vd `extract_document_metadata`, `extract_so_hieu_*`) BẮT BUỘC Mode B vì metadata được tính tại ingest time và lưu vào ChromaDB. Restart backend KHÔNG re-compute metadata cho chunks đã có.

**Lệnh**: `docker compose down -v && docker compose up -d --build`

**Cảnh báo khi Mode B**:
- Tốn ~$0.25 embedding API (10.3k chunks × Gemini embedding-001)
- Downtime ~5-15 phút chờ auto-ingest (chatbot trả lỗi trong lúc này)
- BÁO USER trước khi chạy Mode B lần đầu nếu không chắc

## Các bước (tuần tự)

```bash
# 1. Vào repo (clone nếu chưa có)
cd ~/tuvanluat_chatbot 2>/dev/null || \
  git clone https://github.com/catboyx99/tuvanluat_chatbot.git ~/tuvanluat_chatbot && \
  cd ~/tuvanluat_chatbot

# 2. Ghi commit cũ
OLD=$(git rev-parse --short HEAD)

# 3. Pull mới, bỏ mọi thay đổi local
git fetch origin && git reset --hard origin/main

# 4. Ghi commit mới
NEW=$(git rev-parse --short HEAD)

# 5. QUYẾT ĐỊNH MODE (xem phần trên)
#    - Mode A: docker compose up -d --build
#    - Mode B: docker compose down -v && docker compose up -d --build

# 6. Kiểm tra containers
docker compose ps

# 7. Smoke test (nếu Mode B, chờ auto-ingest xong trước)
# Mode B: xem log tới khi thấy "Auto-ingest done" hoặc timeout 15p
docker compose logs backend 2>&1 | tail -5
curl -sf http://localhost:8000/health
```

Yêu cầu sau khi xong: 3 service `chroma`, `backend`, `frontend` đều `Up`, health check trả 200, log backend có "Application startup complete" (và "Auto-ingest done" nếu Mode B).

## Báo cáo cho user
```
Deploy xong (Mode A/B).
- Commit: <OLD> → <NEW>
- Mode: A (giữ ChromaDB) / B (re-ingest full)
- Containers: <status>
- Health: OK/FAIL
- Ingest (chỉ Mode B): <N> chunks / <time> seconds
```

## Quy tắc AN TOÀN (nghiêm cấm)
1. **KHÔNG** sửa/xoá `.env`.
2. **KHÔNG** commit/push từ server lên GitHub. Server là consumer một chiều.
3. **KHÔNG** dùng `git clean -fdx`, `--force`, `--no-verify`.
4. Nếu `git reset --hard` phát hiện commit local chưa push → DỪNG, báo user.
5. Lệnh nào exit code ≠ 0 → DỪNG, báo log, KHÔNG retry quá 1 lần.
6. Mode B (wipe volume) chỉ dùng khi THỰC SỰ cần — volume ephemeral nhưng re-ingest tốn tiền/thời gian.

## Xử lý sự cố nhanh
| Triệu chứng | Xử lý |
|---|---|
| `permission denied` docker | Dùng `sudo` (chỉ khi user cho phép) hoặc thêm user vào group `docker` |
| `backend` exit liên tục | `docker compose logs backend` — thường do `GEMINI_API_KEY` sai/hết quota |
| Auto-ingest gặp 429 rate limit | Chờ 60-120s, `docker compose restart backend` để retry |
| Port 3000/8000 bị chiếm | `ss -tlnp \| grep -E ':3000\|:8000'`, báo user trước khi kill |
| Git conflict / unmerged | Báo user, KHÔNG tự resolve |
