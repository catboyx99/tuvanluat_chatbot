# PRD: Law Consultant Chat Bot

## 1. Giới thiệu
Trợ lý ảo tư vấn luật Việt Nam dùng RAG. Nguồn dữ liệu: văn bản luật Markdown trong `md_materials/`.

## 2. Tính năng cốt lõi

### 2.1. Chat UI
- Header **"AI tư vấn pháp luật"**, layout 1 khung chat giữa màn hình.
- **Light theme navy**: bg `#f0f4fb`, header navy `#0d1b6e` + chữ trắng, user bubble navy, bot bubble trắng border `#dde3f0`, scrollbar `#c5cfe8`, markdown heading/strong/code navy.
- **Typing effect**: `requestAnimationFrame` ~4ms/char, cursor `|` nhấp nháy navy, message mới slide-up + fade-in.
- **Markdown rendering** (`react-markdown`): bot message parse bold/list/heading; user giữ plain text.
- **Loading animation**: Scale icon lắc lư + 1 trong 8 câu trấn an random, hiện ngay, tắt khi stream có text đầu tiên. Ẩn bubble assistant rỗng.
- **Auto scroll**: `scrollTop = scrollHeight` trực tiếp (KHÔNG `scrollIntoView smooth` — lag).
- **Response Timer**: Dưới loading bubble hiện "Đang phân tích câu hỏi của bạn..." + thinking dots + counter. Biến mất khi có text đầu tiên, lưu final time hiển thị nhỏ dưới bubble. Format `120ms` → `1.2s` → `1m:05s`.
- **Timestamp cuối bubble**: Tiếng Việt đầy đủ (`Thứ Hai, ngày 21 tháng 4 năm 2026, 14:35:22`), `font-medium`, màu thừa hưởng, ẩn khi còn stream.
- **Export PDF**: Link "📄 Tải lời tư vấn" góc phải dưới mỗi bubble → `html2pdf.js` client-side, template A4 (header + body clone + footer disclaimer), tên file `tu-van-luat_YYYY-MM-DD_HH-mm.pdf`. Bullet dùng `::before` pseudo-elements (html2canvas không render `::marker` ổn định).
- **Gemini quá tải**: Backend stream yield sentinel `__GEMINI_OVERLOAD__` khi 503 → frontend hiện thông báo đỏ "Model Gemini hiện đang quá tải vui lòng bấm nút retry để load câu trả lời" + nút **Retry** (resend câu hỏi cuối).

### 2.2. Trích dẫn pháp lý (BẮT BUỘC cuối mỗi câu trả lời)
- Tiêu đề `**Căn cứ pháp lý:**` trên dòng riêng, mỗi nguồn 1 gạch đầu dòng markdown (`-`).
- Format: `Tên văn bản đầy đủ (Số hiệu), Điều [số], Khoản [số], Điểm [chữ]`. Số hiệu dùng dấu `/` (VD `Luật số 43/2019/QH14`), KHÔNG dùng `-`.
- Nhiều Điểm cùng Khoản gộp 1 dòng (`..., Điểm a, Điểm b, Điểm c.`); Điều khác nhau phải tách dòng.
- Tên luật LẤY TỪ NỘI DUNG văn bản, KHÔNG từ tên file/metadata (`Luật-15-2017-QH14` ❌ → `Luật Quản lý, sử dụng tài sản công` ✅).
- Nếu không xác định được Điều/Khoản → chỉ ghi tên văn bản. KHÔNG bịa, KHÔNG placeholder `[...]`, KHÔNG copy nhãn nội bộ `[Nguồn: ...]`.

### 2.3. Data Pipeline
- **Nguồn**: 1 thư mục `md_materials/` ở root, Docker volume mount read-only vào backend.
- **Auto-detect & Incremental Ingest**: Boot backend → DB rỗng thì ingest toàn bộ; DB có data thì so sánh file vs source đã ingest, chỉ ingest file mới; không mới → skip.
- **Split theo cấu trúc pháp luật**: `#` Luật/Nghị Định → `##` Chương/Mục → `###` Điều → `####` Khoản. Preprocessing: strip code blocks, inject markdown headers từ "Điều X."/"Chương X", filter chunks <15 chars.
- **Embedding**: `gemini-embedding-001` → ChromaDB.

### 2.4. RAG Engine
- **Query Rewriting** (`gemini-2.5-flash-lite`): thêm dấu tiếng Việt, chuẩn hoá intent (loại bỏ "quy định"/"là gì"/"cho tôi biết"), BẮT BUỘC giữ số liệu (tuổi, lớp, thời gian), đối tượng pháp lý (trẻ em, học sinh...), động từ pháp lý.
- **Retrieval**: top-10 vector search, không threshold (LLM tự đánh giá).
- **Answer**: LLM đọc chunks → 2 phần (lời tư vấn + Căn cứ pháp lý). Chỉ dùng context, KHÔNG bịa/KHÔNG dùng kiến thức ngoài. Data không liên quan → "Xin lỗi, hệ thống không có dữ liệu pháp lý liên quan."

## 3. Technology Stack
- **Backend**: Python 3.12, FastAPI, LangChain. LLM chính `gemini-2.5-flash` (streaming, temp=0), rewrite `gemini-2.5-flash-lite`, embedding `gemini-embedding-001`. ChromaDB HTTP client. Singleton pattern cho LLM/vector store.
- **Frontend**: Next.js 14 App Router, TailwindCSS, `lucide-react`, `react-markdown`, `html2pdf.js`. AI SDK v6: `useChat()` → `sendMessage({text})`, `status`, `messages`. Proxy route `/api/chat` raw stream → SSE UIMessageStream (`text-start`/`text-delta`/`text-end`/`[DONE]`). Message content qua `m.parts` (không phải `m.content`).
- **Docker Compose 3 services**: `chroma` (persist qua `chroma_data` volume), `backend` (internal network), `frontend` (expose 3000). ENV: 1 file `.env` ở root chỉ chứa `GEMINI_API_KEY`. GitHub: https://github.com/catboyx99/tuvanluat_chatbot.

## 4. Trạng thái & tiến độ
Tiến độ chi tiết + tóm tắt trạng thái hoàn thiện: xem `IMPLEMENTATION_PLAN.md`. **Trước khi bắt đầu task mới, đọc file này để biết tính năng đã có chưa, tránh làm trùng.**

## 5. Quy trình phát triển
- **Cập nhật `IMPLEMENTATION_PLAN.md`** khi implement xong — PHẢI update cả 2 chỗ: (1) Section 3 đánh `[x]` task chi tiết; (2) Section 2.5 "Tóm tắt trạng thái hoàn thiện" sửa/thêm bullet tương ứng + cập nhật "Số liệu hiện tại" nếu thay đổi. Quên Section 2.5 → AI phiên sau đọc trạng thái sai.
- **Deploy**: KHÔNG tự deploy server sau khi commit. User tự deploy. Lưu ý khi deploy → `.claude/skills/deploy/SKILL.md`.

## 6. Ghi chú kỹ thuật
- **Python 3.14** có compatibility issues (thiếu `chardet`, Pydantic V1 warning); uvicorn `--reload` không ổn định Windows. `print()` dùng ASCII, KHÔNG tiếng Việt có dấu (Windows cp1252 crash). String literals tiếng Việt trong code OK.
- **Models**: API key chỉ hỗ trợ `gemini-embedding-001` (không `text-embedding-004`). `gemini-1.5-flash` và `gemini-2.0-flash` đã deprecated, dùng `gemini-2.5-flash`.
- **AI SDK v6**: `useChat` KHÔNG còn `input`/`handleInputChange`/`handleSubmit`/`isLoading`. Dùng `sendMessage`, `status`, tự quản lý input state. Stream protocol SSE JSON thay vì `0:"text"\n`.
- **Pydantic model**: KHÔNG có `.get()`, truy cập attribute trực tiếp (`msg.role`, `msg.content`).
