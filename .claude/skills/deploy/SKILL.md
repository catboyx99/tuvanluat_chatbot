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

# 5. Rebuild & restart stack
docker compose up -d --build

# 6. Kiểm tra containers
docker compose ps

# 7. Smoke test
curl -sf http://localhost:8000/health
```

Yêu cầu sau khi xong: 3 service `chroma`, `backend`, `frontend` đều `Up`, health check trả 200.

## Báo cáo cho user
```
Deploy xong.
- Commit: <OLD> → <NEW>
- Containers: <status>
- Health: OK/FAIL
```

## Quy tắc AN TOÀN (nghiêm cấm)
1. **KHÔNG** sửa/xoá `.env`.
2. **KHÔNG** chạy `docker compose down -v` hay xoá volume `chroma_data` — sẽ mất ~11k embeddings.
3. **KHÔNG** commit/push từ server lên GitHub. Server là consumer một chiều.
4. **KHÔNG** dùng `git clean -fdx`, `--force`, `--no-verify`.
5. Nếu `git reset --hard` phát hiện commit local chưa push → DỪNG, báo user.
6. Lệnh nào exit code ≠ 0 → DỪNG, báo log, KHÔNG retry quá 1 lần.

## Xử lý sự cố nhanh
| Triệu chứng | Xử lý |
|---|---|
| `permission denied` docker | Dùng `sudo` (chỉ khi user cho phép) hoặc thêm user vào group `docker` |
| `backend` exit liên tục | `docker compose logs backend` — thường do `GEMINI_API_KEY` sai/hết quota |
| Port 3000/8000 bị chiếm | `ss -tlnp \| grep -E ':3000\|:8000'`, báo user trước khi kill |
| Git conflict / unmerged | Báo user, KHÔNG tự resolve |
