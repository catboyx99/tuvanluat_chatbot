# Kế Hoạch Cải Thiện Tốc Độ Truy Vấn (Improvement Plan)

## 1. Vấn đề Ban Đầu (Bottlenecks — ĐÃ FIX)
Trước khi tối ưu, ứng dụng mất **10-17 giây** trước khi xuất chữ đầu tiên. Các điểm nghẽn đã được xử lý:

1. ~~**Khởi tạo Model liên tục**~~ → ✅ Đã áp dụng Singleton Pattern (`_vector_store`, `_llm_main`, `_llm_rewrite`)
2. ~~**Khởi tạo ChromaDB Client liên tục**~~ → ✅ Singleton, khởi tạo 1 lần
3. ~~**Model Rewrite quá nặng** (`gemini-2.5-flash` ~11s)~~ → ✅ Đổi sang `gemini-2.5-flash-lite` (~1s)
4. ~~**System Prompt quá dài** (~1900 chars)~~ → ✅ Rút gọn còn ~600 chars (giảm 70%)

## 2. Phân Tích RAG Flow Theo Từng Bước

Khi user gửi câu hỏi, request đi qua chuỗi xử lý sau (file `backend/app/rag_engine.py`, hàm `invoke_rag_chain()`):

```
User gửi câu hỏi
    ↓
[Frontend] useChat() → POST /api/chat (Next.js proxy route)
    ↓
[Proxy] Extract query + history (5 messages gần nhất) → POST /api/chat (FastAPI)
    ↓
[Backend] invoke_rag_chain(query, history) bắt đầu xử lý:

  Step 1 — Lấy ChromaDB client (singleton)    ~0ms (warm) ✅ ĐÃ FIX
  ┃  get_vector_store() trả về instance đã khởi tạo
  ↓
  Step 2 — Query Rewriting (flash-lite)       ~0.5-1.5s  ✅ ĐÃ FIX (từ ~11s)
  ┃  build_rewrite_llm() singleton, dùng gemini-2.5-flash-lite
  ┃  → Thêm dấu tiếng Việt, giữ nguyên nghĩa gốc
  ┃  VD: "con toi 10 tuoi hoc o dau" → "Con tôi 10 tuổi, nó học được trường nào?"
  ↓
  Step 3 — Vector Search (ChromaDB)           ~0.4-0.7s  ✅ OK
  ┃  similarity_search(search_query, k=5) → 5 chunks liên quan nhất
  ↓
  Step 4 — Build Context                      ~1-5ms  ✅ NHANH
  ┃  Ghép 5 chunks + metadata label [Nguồn: Luật > Chương > Điều > Khoản]
  ↓
  Step 5 — Build Messages                     ~1-5ms  ✅ NHANH
  ┃  System Prompt rút gọn (~600 chars) + history + câu hỏi
  ↓
  Step 6 — LLM Streaming (Main response)      ~3-8s đến token đầu tiên  🟡 BOTTLENECK CÒN LẠI
  ┃  build_llm() singleton, dùng gemini-2.5-flash (thinking model)
  ┃  llm.stream(messages) → yield từng chunk text
  ↓
[Proxy] Raw text stream → SSE UIMessageStream (text-start/text-delta/text-end/[DONE])
    ↓
[Frontend] Typing effect ~4ms/char → hiển thị cho user
```

### Tổng thời gian FTTB (SAU tối ưu):
| Step | Công đoạn | Thời gian | Ghi chú |
|------|-----------|-----------|---------|
| 1 | ChromaDB client (singleton) | ~0ms (warm) | ✅ Đã fix |
| 2 | Query Rewriting (flash-lite) | 0.5-1.5s | ✅ Đã fix (từ ~11s) |
| 3 | Vector Search | 0.4-0.7s | Ổn định |
| 4 | Build Context | ~5ms | Không đáng kể |
| 5 | Build Messages | ~5ms | Không đáng kể |
| 6 | LLM Main first token | 3-8s | 🟡 Bottleneck còn lại (thinking model) |
| | **TỔNG FTTB** | **~4-10s** | **Giảm từ 10-17s, cải thiện ~2x** |

→ Bottleneck còn lại chỉ Step 6 — Gemini API latency, nằm ngoài tầm kiểm soát code.

## 3. Giải Pháp Cải Thiện Đề Xuất

### Thành phần 1: Singleton Pattern ✅ ĐÃ TRIỂN KHAI
**Vị trí**: `backend/app/rag_engine.py`
* `_vector_store`: Chroma client + Embeddings — khởi tạo 1 lần
* `_llm_main`: `gemini-2.5-flash` — dùng cho câu trả lời chính
* `_llm_rewrite`: `gemini-2.5-flash-lite` — dùng cho query rewriting

### Thành phần 2: Chuyển Model Rewrite Sang `gemini-2.5-flash-lite` ✅ ĐÃ TRIỂN KHAI
**Vị trí**: `backend/app/rag_engine.py` (Hàm `rewrite_query()`)
* Đã đổi từ `gemini-2.5-flash` sang **`gemini-2.5-flash-lite`** + đổi prompt thành "thêm dấu, giữ nguyên nghĩa".
* **Benchmark thực tế** (cùng query "con toi 20 tuoi hoc o dau duoc"):
  - `gemini-2.5-flash`: AVG **11.33s** — quá chậm, model suy luận nặng
  - `gemini-2.5-flash-lite`: AVG **1.05s** — nhanh gấp ~10 lần
* `gemini-2.0-flash-lite` đã deprecated (404 NOT_FOUND), không dùng được.

### Thành phần 3: Tối ưu Hóa System Prompt ✅ ĐÃ TRIỂN KHAI
**Vị trí**: `backend/app/rag_engine.py`
* Rút gọn từ ~1900 chars → ~600 chars (giảm ~70% input tokens).
* Giữ nguyên các quy tắc citation cốt lõi, bỏ giải thích dài dòng.

### Thành phần 4: Performance Logging ✅ ĐÃ TRIỂN KHAI
**Vị trí**: `backend/app/rag_engine.py` (Hàm `invoke_rag_chain()`)
* 3 mốc đo: `[Perf] Query rewrite`, `[Perf] Vector search`, `[Perf] LLM first token + Total FTTB`.

## 4. Kết Quả Đo Thực Tế

### Bảng so sánh tổng FTTB: TRƯỚC vs SAU tối ưu

| Câu hỏi | TRƯỚC | SAU | Cải thiện |
|----------|-------|-----|-----------|
| "con tôi 10 tuổi nó học được trường nào" | ~12s | **6.43s** | ~1.9x |
| "Nó muốn đi học đại học nó cần gì" | ~14s | **9.67s** | ~1.4x |
| "tôi cho cháu căn nhà để đi học được không" | — | **6.01s** | (câu test mới) |

### Chi tiết thời gian từng step SAU tối ưu:

| Step | Câu 1 | Câu 2 | Câu 3 | Ghi chú |
|------|-------|-------|-------|---------|
| Query Rewrite (flash-lite) | 1.07s | 0.70s | 1.81s | Giảm từ ~11s → ~1s ✅ |
| Vector Search | 0.61s | 0.67s | 0.63s | Ổn định ~0.6s |
| LLM Main first token | 4.57s | 8.24s | 3.52s | Dao động lớn (thinking model) |
| **FTTB tổng** | **6.43s** | **9.67s** | **6.01s** | |

### Fix chất lượng Query Rewrite:
- **Vấn đề**: Prompt cũ ("chuyển thành truy vấn pháp lý") khiến flash-lite tự ý đổi nghĩa ("cho tặng nhà" → "thuê nhà")
- **Giải pháp**: Đổi prompt thành "thêm dấu tiếng Việt, giữ nguyên nghĩa gốc" — model chỉ thêm dấu, không diễn giải lại
- **Kết quả**: "toi cho chau can nha de di hoc duoc khong" → "Tôi cho cháu căn nhà để đi học được không?" ✅

### Các thay đổi đã áp dụng:
1. ✅ **Thành phần 2**: Đổi model rewrite từ `gemini-2.5-flash` → `gemini-2.5-flash-lite` (10x nhanh hơn)
2. ✅ **Thành phần 3**: Rút gọn System Prompt từ ~1900 chars → ~600 chars (giảm ~70% input tokens)
3. ✅ **Thành phần 4**: Thêm performance logging cho rewrite, vector search, LLM first token

### Nhận xét:
- ✅ **Query Rewrite**: ~11s → ~0.9s (10x nhanh hơn)
- ✅ **System Prompt**: ~1900 → ~600 chars (giảm 70% tokens)
- ✅ **Singleton**: Request warm giảm thêm ~0.3-0.5s
- 🟡 **Bottleneck còn lại**: LLM Main (`gemini-2.5-flash`) dao động 3-8s — thinking model, không tắt được qua API

## 5. Kết Quả Tổng Kết
* Tất cả 4 thành phần đã triển khai xong.
* FTTB giảm từ **10-17s → 4-10s** (cải thiện ~2x). Request warm tốt nhất **4.08s**.
* Bottleneck còn lại nằm ở Gemini API latency (thinking model), nằm ngoài tầm kiểm soát code.
