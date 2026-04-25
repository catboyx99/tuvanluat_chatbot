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
- **Format citation**: ✅/❌ — kiểm tra hành vi post-process Giai đoạn 13 (mỗi câu trả lời 1 cột)

Baseline hiện tại (trước Giai đoạn 7-8, xem `IMPLEMENTATION_PLAN.md`): 100% answered / 98% citation / avg ~14.35s.

## Tiêu chí "Format citation" ✅/❌

Sau Giai đoạn 13, mỗi câu trả lời PHẢI thoả 4 tiêu chí dưới (post-process đã đảm bảo deterministic). Đánh dấu ✅ nếu đủ cả 4, ❌ nếu thiếu bất kỳ tiêu chí nào:

1. **Đúng format mỗi dòng**: `- <Tên văn bản đầy đủ> (<Luật số X | Số X>), ban hành ngày <DD/MM/YYYY>, Điều ..., Khoản ..., Điểm ....` (chấm cuối câu, paren chứa số hiệu, ngày bắt buộc nếu chunk có).
2. **Không lặp văn bản**: cùng 1 số hiệu chỉ xuất hiện trên 1 dòng (Điều/Khoản/Điểm gộp thành 1 dòng).
3. **Đúng thứ tự hiệu lực**: Luật → Luật sửa đổi → Nghị quyết → Nghị định → Quyết định → Thông tư → khác. Trong cùng cấp sắp theo năm giảm dần.
4. **Không có dòng dị dạng**: không có placeholder `[...]`, không có nhãn `[Nguồn: ...]` / `[Meta: ...]` rò rỉ ra output, không có dòng thiếu tên ("Luật số X/Y/Z, ..." mà không có tên đứng trước paren).

## Chọn test suite (BẮT BUỘC hỏi user trước khi chạy)

Hiện có 2 test suite. Khi user gọi skill mà KHÔNG chỉ rõ suite nào → BẮT BUỘC hỏi user chọn 1 trong 2 trước khi chạy. Nếu user đã nói rõ ("chạy baseline", "chạy lite", "suite 1", "4lite", ...) thì dùng luôn, không hỏi lại.

| # | Script | Tiêu chí | Dùng khi |
|---|---|---|---|
| **1** | `backend/tests/test_100_questions.py` | `answered` + `has_citation` | Baseline gốc — so sánh với kết quả production 2026-04-01 (100% answered, 99% citation, avg 14.45s) |
| **2** | `backend/tests/test_100_questions_4lite.py` | `answered` + `has_citation` + **`target_hit`** (có `target_id` cho 93/100 câu) | Đánh giá model mới (VD `gemini-2.5-flash-lite`) — thêm chỉ số target-hit để đo độ chính xác retrieval |

Câu hỏi cho user (khi cần hỏi):
> Chọn test suite:
> 1. **Baseline** (`test_100_questions.py`) — answered + citation
> 2. **4Lite** (`test_100_questions_4lite.py`) — thêm chỉ số target_hit
> Bạn chọn số mấy?

## Thông tin chung

| Mục | Giá trị |
|---|---|
| Script | `backend/tests/<script_chọn>.py` trên host. Script KHÔNG có trong Docker image — phải `docker compose cp` vào container khi chạy. |
| Số câu hỏi | 100 (phân theo group: Giáo dục, BHXH, BHYT, Việc làm, Tài chính, Khiếu nại, Khác) |
| API endpoint | `http://localhost:8000/api/chat` (từ trong container backend) |
| Output file | Trong container `/tmp/tests/test_suite_*.json` (suite 1) hoặc `test_suit_*.json` (suite 2) |
| Thời gian chạy | ~25-40 phút (100 câu × 15-25s/câu, tuỳ Gemini latency) |

## Tiền đề
1. Stack Docker đang chạy: `docker compose ps` → `chroma`, `backend`, `frontend` đều `Up`.
2. Backend đã ingest xong (log `Auto-ingest done` hoặc `no new files — skip`).
3. Smoke test passed: `curl -sf http://localhost:8000/health` trả 200.

Nếu thiếu → DỪNG, báo user chạy `/deploy` trước.

## Các bước (tuần tự)

Sau khi có lựa chọn, set biến `SCRIPT` theo bảng trên rồi chạy khối dưới. Ví dụ:
- Suite 1: `SCRIPT=test_100_questions.py`, `PATTERN=test_suite_*.json`
- Suite 2: `SCRIPT=test_100_questions_4lite.py`, `PATTERN=test_suit_*.json`

```bash
# 0. Set bien theo lua chon
SCRIPT=test_100_questions.py              # hoac test_100_questions_4lite.py
PATTERN="test_suite_*.json"               # hoac "test_suit_*.json"

# 1. Vao repo
cd ~/tuvanluat_chatbot

# 2. Kiem tra stack
docker compose ps
curl -sf http://localhost:8000/health || (echo "Backend not healthy"; exit 1)

# 3. Copy script + tao thu muc output trong container
docker compose exec -T backend mkdir -p /tmp/tests
docker compose cp "backend/tests/${SCRIPT}" "backend:/tmp/tests/${SCRIPT}"

# 4. Chay test suite ben trong container backend
#    - Override TEST_API_URL de goi localhost:8000 (default trong script la :8088)
#    - Pipe output ra file log tren host de theo doi
TS=$(date +%Y%m%d_%H%M%S)
docker compose exec -T -e TEST_API_URL=http://localhost:8000/api/chat backend \
  python "/tmp/tests/${SCRIPT}" 2>&1 | tee "auto_test_serverside/test_run_${TS}.log"

# 5. Copy file JSON ket qua tu container ra host
LATEST=$(docker compose exec -T backend sh -c "ls -t /tmp/tests/${PATTERN} 2>/dev/null | head -1" | tr -d '\r\n')
if [ -n "$LATEST" ]; then
  FNAME=$(basename "$LATEST")
  docker compose cp "backend:${LATEST}" "./auto_test_serverside/${FNAME}"
  echo "Result file: ./auto_test_serverside/${FNAME}"
else
  echo "[WARN] No result JSON found in container"
fi

# 6. Don script tam trong container (optional)
docker compose exec -T backend rm -rf /tmp/tests
```

## Hướng dẫn xem tiến độ (BẮT BUỘC cung cấp cho user khi bắt đầu)

Ngay sau khi lệnh chạy test ở bước 4 được khởi chạy (thường sẽ được chạy ngầm do mất 30-40 phút), bạn **PHẢI** tự động cung cấp cho user câu lệnh PowerShell (nếu dùng Windows) hoặc Bash (nếu Linux) để họ có thể tự mở terminal và theo dõi tiến độ log trực tiếp. 

Mẫu trả lời cho user:
> Test suite đang chạy ngầm, dự kiến mất 30-40 phút. Bạn có thể mở một tab Terminal mới và dán lệnh sau để xem tiến độ cập nhật real-time:
> ```powershell
> Get-Content -Path "<đường_dẫn_tuyệt_đối>\auto_test_serverside\<tên_file_log.log>" -Wait -Tail 15
> ```
*(thay đường dẫn tuyệt đối cho chính xác với log file vừa sinh ra).*

## Báo cáo cho user

Sau khi chạy xong, tổng hợp từ output cuối của script:

```
Test suite xong.
- Total: 100 câu
- Answered: <X>/<valid> (<pct>%)
- Has citation: <X>/<valid> (<pct>%)
- Format citation OK: <X>/<valid> (<pct>%)
- Errors: <N>
- Avg time: <X.XX>s
- Result file: auto_test_serverside/test_suite_YYYYMMDD_HHMMSS.json
```

Kèm bảng chi tiết per-câu (Answered + Citation + **Format citation** ✅/❌):

| ID | Câu hỏi (cắt 60 chars) | Answered | Citation | Format citation |
|---|---|---|---|---|
| 1 | ... | ✅ | ✅ | ✅ |
| 2 | ... | ✅ | ✅ | ❌ |

Cột "Format citation" đánh giá theo 4 tiêu chí ở section "Tiêu chí Format citation" phía trên — tự parse phần citation block của mỗi response, KHÔNG mô tả lỗi cụ thể (chỉ ✅ hoặc ❌).

Nếu có regression so với baseline:
- Answered < 95% → nêu 5 câu fail đầu tiên
- Citation < 90% → nêu 5 câu thiếu citation đầu tiên
- Format citation < 95% → nêu 5 câu ❌ đầu tiên (chỉ liệt kê ID + câu hỏi, KHÔNG phân tích nguyên nhân)
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
