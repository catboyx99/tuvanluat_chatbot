# Product Requirements Document (PRD): Law Consultant Chat Bot

## 1. Giới thiệu (Introduction)
- **Mục tiêu**: Xây dựng một ứng dụng trợ lý ảo tư vấn luật chuyên nghiệp, sử dụng công nghệ RAG (Retrieval-Augmented Generation).
- **Đối tượng sử dụng**: Người dùng cuối cần tra cứu luật pháp Việt Nam.
- **Nguồn dữ liệu**: Các văn bản luật Việt Nam dưới định dạng Markdown (`.md`).

## 2. Các thành phần và Tính năng cốt lõi

### 2.1. Giao diện Người dùng (Chat UI)
- Có Main Header: **"AI tư vấn pháp luật"**.
- Layout tối giản: Chỉ dùng duy nhất 1 khung chat (chat interface) ở giữa màn hình.
- **Light Theme (navy accent)**: Background `#f0f4fb` (xanh nhạt), header navy `#0d1b6e` + chữ trắng, user bubble navy + chữ trắng, bot bubble trắng + border `#dde3f0`, scrollbar `#c5cfe8`, markdown heading/strong/code dùng navy.
- **Hiệu ứng Typing**: Bot trả lời với hiệu ứng gõ chữ từng ký tự mượt mà (requestAnimationFrame ~4ms/char) kèm con trỏ `|` nhấp nháy navy. Message mới slide-up + fade-in.
- **Markdown Rendering**: Bot trả lời dạng Markdown, frontend parse bằng `react-markdown` (in đậm, list, heading...). User message giữ plain text.
- **Trích dẫn pháp lý chuẩn**: Cuối câu trả lời bắt buộc có phần "Căn cứ pháp lý" trích dẫn theo format:
  - Tiêu đề `**Căn cứ pháp lý:**` trên dòng riêng, mỗi nguồn là 1 gạch đầu dòng markdown (`-`) trên dòng riêng.
  - Thứ tự mỗi dòng: Tên văn bản (Số hiệu), Điều [số], Khoản [số], Điểm [chữ].
  - Nhiều Điểm cùng Khoản liệt kê trên 1 dòng: "Luật Giáo dục 2019 (Luật số 43/2019/QH14), Điều 28, Khoản 1, Điểm a, Điểm b, Điểm c."
  - Mỗi Điều khác nhau phải nằm trên 1 gạch đầu dòng riêng.
  - KHÔNG được trích dẫn tên file markdown. Phải ghi tên luật đầy đủ + số hiệu văn bản + Điều/Khoản/Điểm cụ thể.
  - Tên luật phải lấy từ NỘI DUNG văn bản trong dữ liệu, KHÔNG dùng tên file hoặc mã metadata (ví dụ: `"Luật-15-2017-QH14"` là SAI, phải ghi `"Luật Quản lý, sử dụng tài sản công"`).
  - Số hiệu văn bản dùng dấu gạch chéo `/` (ví dụ: `"Luật số 43/2019/QH14"`), KHÔNG dùng dấu gạch ngang `-`.
  - Nếu không xác định được Điều/Khoản, chỉ ghi tên văn bản.
- **Loading Animation**: Khi gửi câu hỏi, hiện ngay icon cán cân (Scale) lắc lư kèm câu trấn an random (8 messages luân phiên). Tắt ngay khi có chữ đầu tiên từ stream (không đợi stream kết thúc). Ẩn bubble assistant rỗng khi chưa có nội dung streaming.
- **Auto Scroll**: Chat tự cuộn xuống đáy khi có tin nhắn mới và liên tục khi typing effect đang chạy (dùng `scrollTop = scrollHeight` trực tiếp, không dùng `scrollIntoView` smooth vì bị lag).
- **Bộ đếm thời gian chờ (Response Timer)**: Khi gửi câu hỏi, phía dưới loading bubble hiển thị dòng "Đang phân tích câu hỏi của bạn..." với thinking dots animation (3 chấm nhấp nháy lần lượt) kèm bộ đếm thời gian. Dòng này biến mất khi có chữ đầu tiên từ stream. Thời gian cuối cùng hiển thị nhỏ phía dưới khung chat câu trả lời. Format: `120ms` → `1.2s` → `1m:05s`.
- **Timestamp cuối bubble**: Mỗi bubble assistant có timestamp tiếng Việt đầy đủ ở cuối (`Thứ Hai, ngày 21 tháng 4 năm 2026, 14:35:22`), `font-medium`, màu thừa hưởng content, ẩn khi còn đang stream.
- **Export PDF từng câu trả lời**: Mỗi bubble assistant có link "📄 Tải lời tư vấn" ở góc phải dưới. Click → xuất PDF (template A4: header tên app + timestamp, body clone node bubble, footer disclaimer) qua `html2pdf.js` client-side. Tên file `tu-van-luat_YYYY-MM-DD_HH-mm.pdf`. Bullet list dùng `::before` pseudo-elements để tương thích html2canvas.
- **Xử lý Gemini quá tải**: Khi backend gặp 503/overload, stream yield sentinel `__GEMINI_OVERLOAD__` → frontend hiện thông báo đỏ "Model Gemini hiện đang quá tải vui lòng bấm nút retry để load câu trả lời" + nút **Retry** (resend câu hỏi cuối).

### 2.2. Xử lý dữ liệu (Data Pipeline)
- **Nguồn nạp văn bản**: Duy nhất 1 thư mục `md_materials/` ở root project. Backend đọc trực tiếp qua Docker volume mount.
- **Auto-detect & Incremental Ingest**: Khi khởi động backend, tự kiểm tra ChromaDB:
  - DB rỗng → ingest toàn bộ file `.md` trong `md_materials/`
  - DB có data → so sánh file trong folder vs source đã ingest trong ChromaDB, chỉ ingest file mới (incremental)
  - Không có gì mới → skip, khởi động nhanh
- **Tính năng Cắt văn bản theo cấu trúc pháp luật**: Áp dụng thuật toán chia nhỏ tài liệu theo cấu trúc:
  1. Luật/Nghị Định (Parent Root — Header #)
  2. Chương/Mục (Header ##)
  3. Điều (Header ###)
  4. Khoản (Header ####)
- **Embedding & Storage**: Dùng `gemini-embedding-001` lưu vào Local Vector DB (ChromaDB).

### 2.3. RAG Engine
- **Query Rewriting**: Trước khi search, dùng LLM (`gemini-2.5-flash-lite`) thêm dấu tiếng Việt vào câu hỏi, giữ nguyên nghĩa gốc để vector search chính xác hơn.
- Khi trả lời, hệ thống phải đọc kỹ nội dung chunks để xác định chính xác số Điều, Khoản, Điểm rồi trích dẫn ở cuối câu trả lời theo format chuẩn "Căn cứ pháp lý".
- **Chống bịa đặt (Anti-Hallucination)**:
  - System prompt yêu cầu chỉ trả lời dựa trên dữ liệu được cung cấp, linh hoạt suy luận ý định câu hỏi đời thường.
  - KHÔNG bịa số điều khoản, KHÔNG dùng kiến thức bên ngoài context.

## 3. Kiến trúc Công nghệ (Technology Stack)

### 3.1. Backend (API + RAG Core)
- Python 3.12, FastAPI, LangChain
- LLM chính: `gemini-2.5-flash` (streaming, temperature=0.0)
- LLM rewrite: `gemini-2.5-flash-lite` (temperature=0.0) — chỉ thêm dấu tiếng Việt vào câu hỏi
- Embedding: `gemini-embedding-001`
- ChromaDB: container riêng (server mode), backend kết nối qua HTTP client
- Code luôn được docs/comments rõ ràng

### 3.2. Frontend (UI)
- Next.js 14 (App Router), TailwindCSS, `lucide-react`, `react-markdown`
- **AI SDK**: `@ai-sdk/react` v3 + `ai` v6 (UIMessageStream SSE protocol)
  - Hook: `useChat()` → `sendMessage({ text })`, `status`, `messages`
  - Proxy route chuyển đổi raw text stream từ FastAPI → SSE UIMessageStream format (`text-start`, `text-delta`, `text-end`, `[DONE]`)
  - Message content truy cập qua `m.parts` (không phải `m.content`)

### 3.3. DevOps
- **Docker / Docker-Compose**: 3 services:
  - `chroma`: ChromaDB server (container riêng, data persist qua `chroma_data` volume)
  - `backend`: FastAPI + RAG (internal network)
  - `frontend`: Next.js — expose port 3000 ra ngoài
- **Git/GitHub**: https://github.com/catboyx99/tuvanluat_chatbot
- **Deploy trên máy mới** (chỉ 3 bước):
  1. `git clone https://github.com/catboyx99/tuvanluat_chatbot.git && cd tuvanluat_chatbot`
  2. Tạo file `.env` ở root chứa: `GEMINI_API_KEY=<key>`
  3. `docker compose up -d --build` (lần đầu tự ingest ~2-3 phút, các lần sau skip)

## 4. Trạng thái hiện tại — Hoàn thiện
Tổng quan 6 giai đoạn (xem chi tiết trong `IMPLEMENTATION_PLAN.md`):

- **Giai đoạn 1 — Dựng nền tảng RAG end-to-end ✅**: Frontend Next.js 14 + Backend FastAPI + ChromaDB, streaming qua AI SDK v6 (SSE UIMessageStream), citation chuẩn pháp lý (Điều/Khoản/Điểm), auto-detect & incremental ingest từ `md_materials/`, Docker 3 services, pushed GitHub.
- **Giai đoạn 2 — Polish UX & tối ưu hiệu năng ✅**: Typing effect 4ms/char, auto-scroll instant, loading animation (Scale icon + thinking dots), Response Timer (`120ms` → `1.2s` → `1m:05s`), Singleton LLM/vector store, FTTB 12-14s → ~4-6s (rewrite đổi sang `gemini-2.5-flash-lite`, system prompt rút gọn 70%).
- **Giai đoạn 3 — Cải thiện Retrieval Quality ✅**: Preprocessing markdown (strip code blocks, inject headers), filter junk chunks, tăng k=10. Test suite 100 câu: 100% answered, 98% citation, avg 14.35s. Re-ingest 90 files → 10300 chunks.
- **Giai đoạn 4 — UI Light Mode & Đổi tên ✅**: Chuyển dark → light theme (background `#f0f4fb`, navy `#0d1b6e`), đổi tên header "AI tư vấn pháp chế".
- **Giai đoạn 5 — Fix citation & rewrite & timestamp ✅**: Đổi tên "AI tư vấn pháp luật", fix diacritics trong system prompt, siết quy tắc trích dẫn (cấm placeholder `[...]`, cấm copy `[Nguồn: ...]`), fix loading bubble lần submit 2+, timestamp tiếng Việt cuối bubble, rewrite chuẩn hoá intent + ép output có dấu đầy đủ, thêm deploy skill ở `.claude/skills/deploy/SKILL.md`.
- **Giai đoạn 6 — Export PDF từng câu trả lời ✅**: Link "📄 Tải lời tư vấn" mỗi bubble assistant, html2pdf.js client-side, template A4 với header/body/footer, bullet dùng `::before` pseudo-elements cho html2canvas compatibility, handle Gemini 503 overload sentinel + Retry button.

**Số liệu hiện tại**:
- ~10300 chunks pháp luật (90 files .md) trong ChromaDB
- FTTB ~4-6s (warm request), test suite 100% answered / 98% citation
- ENV: 1 file `.env` ở root (`GEMINI_API_KEY`)

## 5. Quy trình phát triển
- **Cập nhật IMPLEMENTATION_PLAN.md**: Khi implement tính năng, phải cập nhật tiến độ trong IMPLEMENTATION_PLAN.md (đánh dấu `[x]` cho task hoàn thành, thêm ghi chú nếu cần).
- **Deploy**: Không tự deploy lên server sau khi code/commit. User sẽ tự deploy. Nếu có lưu ý kỹ thuật cần nhớ khi deploy, cập nhật vào `.claude/skills/deploy/SKILL.md`.

## 6. Ghi chú kỹ thuật quan trọng
- **Python 3.14** rất mới, có compatibility issues (thiếu `chardet`, Pydantic V1 warning). `--reload` của uvicorn không ổn định trên Windows. Console log phải dùng ASCII (không dùng tiếng Việt trong `print()`) vì Windows cp1252 không encode được Unicode tiếng Việt.
- **Embedding model**: API key chỉ hỗ trợ `gemini-embedding-001`, không có `text-embedding-004`.
- **LLM model**: `gemini-1.5-flash` và `gemini-2.0-flash` đã deprecated. Dùng `gemini-2.5-flash`.
- **AI SDK v6 breaking changes**: `useChat` không còn `input`, `handleInputChange`, `handleSubmit`, `isLoading`. Phải dùng `sendMessage`, `status`, tự quản lý input state. Stream protocol đổi từ `0:"text"\n` sang SSE JSON (`text-start`/`text-delta`/`text-end`).
- **Pydantic**: Model không có `.get()`. Truy cập attribute trực tiếp (`msg.role`, `msg.content`).
