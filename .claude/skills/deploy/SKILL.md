---
name: deploy
description: Cập nhật source mới nhất từ GitHub về server production và rebuild Docker stack của chatbot tư vấn luật. Dùng khi người dùng nói "deploy", "cập nhật server", "pull về server", "update production".
---

# DEPLOY — Cập nhật chatbot lên server production

> Tài liệu này dành cho BẤT KỲ AI agent nào (Claude, Gemini, GPT, v.v.) được triển khai trên server để chạy quy trình deploy. Đọc toàn bộ trước khi thực thi. Mỗi bước là bắt buộc và phải chạy tuần tự.

## 1. Thông tin cố định

- **Repo GitHub**: `https://github.com/catboyx99/tuvanluat_chatbot`
- **Branch production**: `main`
- **Thư mục repo trên server (mặc định)**: `~/tuvanluat_chatbot`
- **Hệ điều hành server**: Ubuntu Linux
- **Shell**: bash
- **Yêu cầu cài sẵn**: `git`, `docker`, `docker compose` (plugin v2, KHÔNG phải `docker-compose` cũ)

## 2. Điều kiện tiên quyết (KIỂM TRA, KHÔNG tự tạo)

Trước khi deploy, xác nhận các điều kiện sau. Nếu thiếu, DỪNG và báo user — KHÔNG tự ý tạo.

1. File `.env` ở root repo đã tồn tại và chứa `GEMINI_API_KEY=<key>`.
   - Kiểm tra: `test -f ~/tuvanluat_chatbot/.env && echo OK || echo MISSING`
2. Docker daemon đang chạy.
   - Kiểm tra: `docker info > /dev/null 2>&1 && echo OK || echo DOCKER_DOWN`
3. Volume `chroma_data` đã tồn tại (giữ embeddings). Nếu chưa có, lần deploy đầu sẽ tự tạo.

## 3. Các bước deploy (chạy TUẦN TỰ, không song song)

### Bước 1 — Vào thư mục repo
```bash
cd ~/tuvanluat_chatbot
```
Nếu thư mục không tồn tại → đây là server mới, clone trước:
```bash
git clone https://github.com/catboyx99/tuvanluat_chatbot.git ~/tuvanluat_chatbot
cd ~/tuvanluat_chatbot
```

### Bước 2 — Ghi nhận commit hiện tại (để log/rollback)
```bash
git rev-parse --short HEAD
```
Ghi lại giá trị này (ví dụ: `e6ebbfe`) để báo cáo sau.

### Bước 3 — Pull source mới nhất, BỎ mọi thay đổi local
```bash
git fetch origin
git reset --hard origin/main
```
Giải thích:
- `fetch` tải commit mới từ GitHub.
- `reset --hard origin/main` ép branch local trùng khớp 100% với remote, XOÁ mọi sửa đổi local chưa commit.
- Lý do: server KHÔNG sửa code — chỉ consume. Mọi thay đổi phải đi qua GitHub.

### Bước 4 — Ghi nhận commit mới
```bash
git rev-parse --short HEAD
```
Nếu giá trị Bước 4 bằng Bước 2 → KHÔNG có code mới, có thể bỏ qua Bước 5 (nhưng vẫn nên chạy để đảm bảo container chạy bản mới nhất nếu đã sửa Dockerfile).

### Bước 5 — Rebuild & restart toàn bộ Docker stack
```bash
docker compose up -d --build
```
- `-d`: chạy background.
- `--build`: rebuild image từ source mới.
- Lần đầu ingest dữ liệu có thể mất 2-3 phút. Các lần sau auto-skip (incremental ingest).
- Lệnh này có thể in nhiều log. Chờ đến khi lệnh kết thúc (exit code 0).

### Bước 6 — Kiểm tra container đã UP
```bash
docker compose ps
```
Yêu cầu: cả 3 service sau đều ở trạng thái `Up` (hoặc `running`):
- `chroma` (ChromaDB)
- `backend` (FastAPI)
- `frontend` (Next.js)

Nếu có service nào `Exit` hoặc `Restarting` → xem log ngay:
```bash
docker compose logs --tail=50 <service-name>
```

### Bước 7 — Smoke test backend
```bash
curl -sf http://localhost:8000/health
```
Phải trả về 200 OK (hoặc JSON `{"status":"ok"}`). Nếu fail → backend chưa sẵn sàng, chờ 10-20 giây rồi thử lại; nếu vẫn fail → xem log `docker compose logs backend`.

### Bước 8 — Báo cáo kết quả cho user
Template báo cáo:
```
Deploy xong.
- Commit cũ: <hash-bước-2>
- Commit mới: <hash-bước-4>
- Containers: <danh sách service Up>
- Health check: OK / FAIL
```

## 4. Quy tắc AN TOÀN (nghiêm cấm vi phạm)

1. **KHÔNG** chỉnh sửa file `.env`. KHÔNG tạo mới đè lên. Nếu user yêu cầu đổi key, yêu cầu họ xác nhận rõ ràng trước khi ghi.
2. **KHÔNG** chạy `docker compose down -v` hoặc `docker volume rm chroma_data` — sẽ mất toàn bộ ~11,000 embeddings đã ingest, phải re-ingest lại 10-15 phút.
3. **KHÔNG** commit hay push từ server lên GitHub. Server là consumer một chiều.
4. **KHÔNG** chạy `git clean -fdx` hoặc xoá file untracked mà chưa xem user có artefact (log, backup) quan trọng.
5. **KHÔNG** dùng `--no-verify`, `--force` với git push, hoặc bất kỳ flag nào bỏ qua safety check.
6. Nếu Bước 3 `git reset --hard` phát hiện có commit local chưa push (hiếm) — DỪNG và báo user trước khi xoá.
7. Nếu bất kỳ lệnh nào trả về exit code khác 0 → DỪNG, báo user kèm output lỗi, KHÔNG tự động retry quá 1 lần.

## 5. Xử lý sự cố thường gặp

| Triệu chứng | Kiểm tra | Cách xử lý |
|---|---|---|
| `docker: command not found` | `which docker` | Docker chưa cài → báo user cài |
| `permission denied` khi chạy docker | `groups $USER` xem có `docker` không | Thêm user vào group hoặc dùng `sudo` (chỉ nếu user cho phép) |
| `git reset` lỗi "unmerged paths" | `git status` | Có conflict local → báo user, KHÔNG tự resolve |
| Container `backend` bị `Exit 1` liên tục | `docker compose logs backend` | Thường do `GEMINI_API_KEY` sai/hết quota — báo user |
| Port 3000/8000 đã bị dùng | `ss -tlnp \| grep -E ':3000\|:8000'` | Tìm process đang chiếm, báo user trước khi kill |

## 6. Danh sách lệnh tối giản (copy-paste nhanh)

```bash
cd ~/tuvanluat_chatbot && \
git fetch origin && \
git reset --hard origin/main && \
docker compose up -d --build && \
docker compose ps && \
curl -sf http://localhost:8000/health
```
Dùng chuỗi này khi user yêu cầu deploy nhanh và đã xác nhận các điều kiện tiên quyết ở Mục 2.
