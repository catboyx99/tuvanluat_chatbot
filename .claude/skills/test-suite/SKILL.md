---
name: test-suite
description: Chạy test suite 100 câu hỏi pháp luật trên server production để đo citation rate + answered rate + FTTB. Dùng khi user nói "chạy test", "test suite", "đo lại test", "benchmark chatbot".
---

# TEST SUITE — Chạy 100 câu hỏi benchmark

Tài liệu dành cho mọi AI agent (Claude, Gemini, GPT, ...). Đọc hết rồi chạy tuần tự.

## Mục đích
Đo chất lượng chatbot theo 3 chỉ số chính:
- **Answered rate**: % câu có trả lời thực chất (không phải "không có dữ liệu")
- **Citation rate**: % câu có phần "Căn cứ pháp lý" cuối trả lời
- **Avg response time**: thời gian trả lời trung bình (seconds, full response)
- **FTTB** (First-Time-To-Byte): thời gian nhận byte đầu tiên

Baseline hiện tại (trước Giai đoạn 7-8, xem `IMPLEMENTATION_PLAN.md`): 100% answered / 98% citation / avg ~14.35s.

## Thông tin

| Mục | Giá trị |
|---|---|
| Script | `backend/tests/test_100_questions.py` trên host. Script KHÔNG có trong Docker image — phải `docker compose cp` vào container khi chạy. |
| Số câu hỏi | 100 (phân theo group: Giáo dục, Quốc tịch, Lao động, Tài chính, Khiếu nại, Khác) |
| API endpoint | `http://localhost:8000/api/chat` (từ trong container backend) |
| Output file | `backend/tests/test_suite_YYYYMMDD_HHMMSS.json` (bên trong container) |
| Thời gian chạy | ~25-40 phút (100 câu × 15-25s/câu, tuỳ Gemini latency) |

## Tiền đề
1. Stack Docker đang chạy: `docker compose ps` → `chroma`, `backend`, `frontend` đều `Up`.
2. Backend đã ingest xong (log `Auto-ingest done` hoặc `no new files — skip`).
3. Smoke test passed: `curl -sf http://localhost:8000/health` trả 200.

Nếu thiếu → DỪNG, báo user chạy `/deploy` trước.

## Các bước (tuần tự)

```bash
# 1. Vào repo
cd ~/tuvanluat_chatbot

# 2. Kiểm tra stack
docker compose ps
curl -sf http://localhost:8000/health || (echo "Backend not healthy"; exit 1)

# 3. Copy script + tạo thư mục output trong container
docker compose exec -T backend mkdir -p /tmp/tests
docker compose cp backend/tests/test_100_questions.py backend:/tmp/tests/test_100_questions.py

# 4. Chạy test suite bên trong container backend
#    - Override TEST_API_URL để gọi localhost:8000 (default trong script là :8088)
#    - Pipe output ra file log trên host để theo dõi
TS=$(date +%Y%m%d_%H%M%S)
docker compose exec -T -e TEST_API_URL=http://localhost:8000/api/chat backend \
  python /tmp/tests/test_100_questions.py 2>&1 | tee "auto_test_serverside/test_run_${TS}.log"

# 5. Copy file JSON kết quả từ container ra host
#    Script tự lưu JSON cùng thư mục với script (/tmp/tests/test_suite_*.json)
LATEST=$(docker compose exec -T backend sh -c "ls -t /tmp/tests/test_suite_*.json 2>/dev/null | head -1" | tr -d '\r\n')
if [ -n "$LATEST" ]; then
  FNAME=$(basename "$LATEST")
  docker compose cp "backend:${LATEST}" "./auto_test_serverside/${FNAME}"
  echo "Result file: ./auto_test_serverside/${FNAME}"
else
  echo "[WARN] No result JSON found in container"
fi

# 6. Dọn script tạm trong container (optional)
docker compose exec -T backend rm -rf /tmp/tests
```

## Báo cáo cho user

Sau khi chạy xong, tổng hợp từ output cuối của script:

```
Test suite xong.
- Total: 100 câu
- Answered: <X>/<valid> (<pct>%)
- Has citation: <X>/<valid> (<pct>%)
- Errors: <N>
- Avg time: <X.XX>s
- Result file: auto_test_serverside/test_suite_YYYYMMDD_HHMMSS.json
```

Nếu có regression so với baseline:
- Answered < 95% → nêu 5 câu fail đầu tiên
- Citation < 90% → nêu 5 câu thiếu citation đầu tiên
- Avg time tăng > 30% → nêu nghi ngờ (Gemini rate limit? prompt dài?)

## Đọc kết quả JSON

Cấu trúc file `test_suite_*.json`:
```json
{
  "run_at": "2026-04-23T...",
  "api_url": "http://localhost:8000/api/chat",
  "total_questions": 100,
  "answered": 100,
  "no_data": 0,
  "has_citation": 99,
  "errors": 0,
  "avg_response_time_s": 14.45,
  "results": [
    {
      "id": 1,
      "question": "...",
      "group": "Giao duc",
      "target_docs": ["..."],
      "answered": true,
      "has_citation": true,
      "fttb_s": 3.2,
      "total_time_s": 12.8,
      "response_preview": "..."  // 500 ký tự đầu
    },
    // ...
  ]
}
```

Query nhanh:
```bash
# Đếm câu không có citation
jq '[.results[] | select(.has_citation == false)] | length' <file>

# Top 5 câu chậm nhất
jq '[.results[]] | sort_by(-.total_time_s) | .[0:5] | .[] | {id, question, total_time_s}' <file>

# Câu lỗi
jq '.results[] | select(.error != null) | {id, question, error}' <file>
```

## Quy tắc AN TOÀN
1. **KHÔNG** chạy test suite song song với traffic user thật (ảnh hưởng trải nghiệm + đốt quota Gemini).
2. **KHÔNG** chạy quá 2 lần trong 1 giờ (rate limit Gemini embedding-001 dev quota ~15 RPM; test suite call 100 LLM streams + 100 embeddings).
3. Nếu gặp lỗi 429 RESOURCE_EXHAUSTED giữa chừng → DỪNG, báo user, chờ ≥10 phút trước khi chạy lại. KHÔNG auto-retry.
4. File JSON output KHÔNG commit lên git (đã trong `.gitignore` qua memory `feedback_server_files.md`).

## Xử lý sự cố

| Triệu chứng | Xử lý |
|---|---|
| `Backend API not reachable` | `docker compose ps` kiểm tra backend Up, `docker compose logs backend` |
| Nhiều câu `ERROR: timeout` | Gemini chậm, tăng timeout trong script (hiện 120s) hoặc chờ Gemini ổn định |
| Citation rate giảm mạnh | Kiểm tra prompt `rag_engine.py` có regression, đối chiếu commit gần nhất |
| Answered rate giảm | Có thể retrieval hỏng — kiểm tra ChromaDB có đủ chunks (`docker compose exec backend python -c "from app.vector_store import get_vector_store; print(get_vector_store()._collection.count())"`) |
| Script báo `ModuleNotFoundError: requests` | Backend container thiếu lib — kiểm tra `backend/requirements.txt` có `requests`, nếu thiếu thì thêm + rebuild |
| `docker compose cp` lỗi `not found` | File `backend/tests/test_100_questions.py` chưa có trên server — pull lại code: `git pull origin main` |
