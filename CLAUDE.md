# Product Requirements Document (PRD): Law Consultant Chat Bot

## 1. Giới thiệu (Introduction)
- **Mục tiêu**: Xây dựng một ứng dụng trợ lý ảo tư vấn luật chuyên nghiệp, sử dụng công nghệ RAG (Retrieval-Augmented Generation).
- **Đối tượng sử dụng**: Người dùng cuối cần tra cứu luật pháp Việt Nam.
- **Nguồn dữ liệu**: Các văn bản luật Việt Nam dưới định dạng Markdown (`.md`).

## 2. Các thành phần và Tính năng cốt lõi

### 2.1. Giao diện Người dùng (Chat UI)
- Có Main Header: **"Trợ lý ảo tư vấn luật"**.
- Layout tối giản: Chỉ dùng duy nhất 1 khung chat (chat interface) ở giữa màn hình.
- **Dark Theme (IDE-style)**: Giao diện tối giống theme VS Code — background `#1e1e1e`, header `#252526`, accent blue `#569cd6`.
- **Hiệu ứng Typing**: Bot trả lời với hiệu ứng gõ chữ từng ký tự mượt mà (requestAnimationFrame ~4ms/char) kèm con trỏ `|` nhấp nháy xanh. Message mới slide-up + fade-in.
- **Markdown Rendering**: Bot trả lời dạng Markdown, frontend parse bằng `react-markdown` (in đậm, list, heading...). User message giữ plain text.
- **Trích dẫn pháp lý chuẩn**: Cuối câu trả lời bắt buộc có phần "Căn cứ pháp lý" trích dẫn theo format:
  - Tiêu đề `**Căn cứ pháp lý:**` trên dòng riêng, mỗi nguồn là 1 gạch đầu dòng markdown (`-`) trên dòng riêng.
  - Thứ tự mỗi dòng: Tên văn bản (Số hiệu), Điều [số], Khoản [số], Điểm [chữ].
  - Nhiều Điểm cùng Khoản liệt kê trên 1 dòng: "Luật Giáo dục 2019 (Luật số 43/2019/QH14), Điều 28, Khoản 1, Điểm a, Điểm b, Điểm c."
  - Mỗi Điều khác nhau phải nằm trên 1 gạch đầu dòng riêng.
  - KHÔNG được trích dẫn tên file markdown. Phải ghi tên luật đầy đủ + số hiệu văn bản + Điều/Khoản/Điểm cụ thể.
  - Nếu không xác định được Điều/Khoản, chỉ ghi tên văn bản.
- **Loading Animation**: Khi gửi câu hỏi, hiện ngay icon cán cân (Scale) lắc lư kèm câu trấn an random (8 messages luân phiên). Tắt ngay khi có chữ đầu tiên từ stream (không đợi stream kết thúc). Ẩn bubble assistant rỗng khi chưa có nội dung streaming.
- **Auto Scroll**: Chat tự cuộn xuống đáy khi có tin nhắn mới và liên tục khi typing effect đang chạy (dùng `scrollTop = scrollHeight` trực tiếp, không dùng `scrollIntoView` smooth vì bị lag).

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
- **Query Rewriting**: Trước khi search, dùng LLM chuyển câu hỏi tự nhiên/không dấu thành truy vấn pháp lý tiếng Việt có dấu để vector search chính xác hơn.
- Khi trả lời, hệ thống phải đọc kỹ nội dung chunks để xác định chính xác số Điều, Khoản, Điểm rồi trích dẫn ở cuối câu trả lời theo format chuẩn "Căn cứ pháp lý".
- **Chống bịa đặt (Anti-Hallucination)**:
  - System prompt yêu cầu chỉ trả lời dựa trên dữ liệu được cung cấp, linh hoạt suy luận ý định câu hỏi đời thường.
  - KHÔNG bịa số điều khoản, KHÔNG dùng kiến thức bên ngoài context.

## 3. Kiến trúc Công nghệ (Technology Stack)

### 3.1. Backend (API + RAG Core)
- Python 3.12, FastAPI, LangChain
- LLM: `gemini-2.5-flash` (streaming, temperature=0.0)
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
  - `backend`: FastAPI + RAG (kết nối ChromaDB qua HTTP, mount `md_materials/` read-only)
  - `frontend`: Next.js (port 3000)
- **Git/GitHub**: https://github.com/catboyx99/tuvanluat_chatbot
- **Deploy trên máy mới** (chỉ 3 bước):
  1. `git clone https://github.com/catboyx99/tuvanluat_chatbot.git && cd tuvanluat_chatbot`
  2. Tạo file `.env` ở root chứa `GEMINI_API_KEY=<api-key>`
  3. `docker compose up -d --build` (lần đầu tự ingest ~2-3 phút, các lần sau skip)

## 4. Trạng thái hiện tại — Hoàn thiện
- Frontend + Backend đã hoàn thiện và chạy OK
- 2475 documents pháp luật đã ingest vào ChromaDB
- Dark theme IDE-style, typing effect (~4ms/char), markdown rendering, citation format chuẩn (bullet list)
- Auto scroll theo typing effect (snap instant, không dùng smooth)
- Auto-detect & incremental ingest (1 thư mục md_materials/ duy nhất ở root)
- Query rewriting: câu hỏi tự nhiên/không dấu → truy vấn pháp lý chính xác
- Loading animation (Scale icon lắc lư + random messages, tắt ngay khi stream bắt đầu có text)
- Anti-hallucination (system prompt linh hoạt + không bịa điều khoản)
- Docker 3 services: ChromaDB (container riêng) + Backend + Frontend, data persist qua volume
- ENV: chỉ cần 1 file `.env` ở root (backend đọc qua `load_dotenv()` trỏ về root, Docker inject qua `environment:`)
- Pushed lên GitHub

## 5. Ghi chú kỹ thuật quan trọng
- **Python 3.14** rất mới, có compatibility issues (thiếu `chardet`, Pydantic V1 warning). `--reload` của uvicorn không ổn định trên Windows. Console log phải dùng ASCII (không dùng tiếng Việt trong `print()`) vì Windows cp1252 không encode được Unicode tiếng Việt.
- **Embedding model**: API key chỉ hỗ trợ `gemini-embedding-001`, không có `text-embedding-004`.
- **LLM model**: `gemini-1.5-flash` và `gemini-2.0-flash` đã deprecated. Dùng `gemini-2.5-flash`.
- **AI SDK v6 breaking changes**: `useChat` không còn `input`, `handleInputChange`, `handleSubmit`, `isLoading`. Phải dùng `sendMessage`, `status`, tự quản lý input state. Stream protocol đổi từ `0:"text"\n` sang SSE JSON (`text-start`/`text-delta`/`text-end`).
- **Pydantic**: Model không có `.get()`. Truy cập attribute trực tiếp (`msg.role`, `msg.content`).
