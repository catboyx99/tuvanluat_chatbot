---
name: deploy
description: Pull source mới nhất từ GitHub về server rồi rebuild & restart Docker stack của chatbot. Dùng khi user nói "deploy", "cập nhật server", "pull về server", hoặc bất kỳ yêu cầu cập nhật source lên production nào.
---

# Deploy chatbot lên server

Skill này chạy TRÊN server production (113.161.95.116, Ubuntu). Mục đích: đồng bộ source mới nhất từ GitHub và rebuild Docker stack theo đúng 3 bước deploy trong `IMPLEMENTATION_PLAN.md`.

## Repo
- GitHub: https://github.com/catboyx99/tuvanluat_chatbot
- Branch deploy: `main`

## Tiền đề
- Đã clone repo về server tại một thư mục (thường là `~/tuvanluat_chatbot`).
- Nếu chưa clone: `git clone https://github.com/catboyx99/tuvanluat_chatbot.git ~/tuvanluat_chatbot`
- File `.env` ở root repo đã tồn tại và chứa `GEMINI_API_KEY=...`. KHÔNG tạo lại, KHÔNG overwrite.
- Docker + docker compose đã cài sẵn.

## Các bước thực hiện (chạy tuần tự)

1. **Vào thư mục repo**: `cd ~/tuvanluat_chatbot` (hoặc đường dẫn user đã clone).

2. **Pull source mới nhất, bỏ local changes nếu có**:
   ```bash
   git fetch origin && git reset --hard origin/main
   ```
   Lý do dùng `reset --hard`: server không nên có commit/edit local — mọi thay đổi phải đi qua GitHub.

3. **Rebuild & restart toàn bộ stack**:
   ```bash
   docker compose up -d --build
   ```
   Lần đầu ingest ~2-3 phút, các lần sau skip (incremental ingest auto-detect).

4. **Kiểm tra containers đã up**:
   ```bash
   docker compose ps
   ```
   Cả 3 service `chroma`, `backend`, `frontend` phải ở trạng thái `Up`.

5. **Smoke test backend**:
   ```bash
   curl -sf http://localhost:8000/health
   ```

## Quy tắc quan trọng
- KHÔNG sửa `.env`, KHÔNG commit gì lên git từ server (server chỉ consume, không produce).
- KHÔNG xoá volume `chroma_data` — sẽ mất toàn bộ embeddings đã ingest (~11k docs).
- Nếu `git reset --hard` phát hiện file untracked quan trọng (ví dụ log, backup), dừng lại và báo user trước khi xoá.
- Báo user commit hash trước/sau pull và status containers sau khi xong.
