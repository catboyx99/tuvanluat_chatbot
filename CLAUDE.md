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
  - Tên luật phải lấy từ NỘI DUNG văn bản trong dữ liệu, KHÔNG dùng tên file hoặc mã metadata (ví dụ: `"Luật-15-2017-QH14"` là SAI, phải ghi `"Luật Quản lý, sử dụng tài sản công"`).
  - Số hiệu văn bản dùng dấu gạch chéo `/` (ví dụ: `"Luật số 43/2019/QH14"`), KHÔNG dùng dấu gạch ngang `-`.
  - Nếu không xác định được Điều/Khoản, chỉ ghi tên văn bản.
- **Loading Animation**: Khi gửi câu hỏi, hiện ngay icon cán cân (Scale) lắc lư kèm câu trấn an random (8 messages luân phiên). Tắt ngay khi có chữ đầu tiên từ stream (không đợi stream kết thúc). Ẩn bubble assistant rỗng khi chưa có nội dung streaming.
- **Auto Scroll**: Chat tự cuộn xuống đáy khi có tin nhắn mới và liên tục khi typing effect đang chạy (dùng `scrollTop = scrollHeight` trực tiếp, không dùng `scrollIntoView` smooth vì bị lag).
- **Bộ đếm thời gian chờ (Response Timer)**: Khi gửi câu hỏi, phía dưới loading bubble hiển thị dòng "Đang phân tích câu hỏi của bạn..." với thinking dots animation (3 chấm nhấp nháy lần lượt) kèm bộ đếm thời gian. Dòng này biến mất khi có chữ đầu tiên từ stream. Thời gian cuối cùng hiển thị nhỏ phía dưới khung chat câu trả lời. Format: `120ms` → `1.2s` → `1m:05s`.

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

### 2.4. Authentication Gate (SSO từ website external)
- **Mục tiêu**: Chatbot CHỈ truy cập được sau khi user đã đăng nhập từ 1 website external (tự xây). Người dùng vào chatbot trực tiếp (không qua website kia) → bị chặn, redirect về trang login.
- **Kiến trúc**: **Nginx reverse proxy (OpenResty) + JWT HS256 shared secret** đứng trước Frontend/Backend. Chỉ Nginx expose port ra ngoài; Frontend + Backend chỉ lắng nghe trong Docker network.
- **Flow**:
  1. User login thành công trên **External Login Website** → website sinh JWT ký HS256 bằng `JWT_SECRET` (shared giữa 2 bên).
  2. Website kia redirect user: `https://<chatbot-domain>/?auth=<JWT>`.
  3. Nginx gateway verify JWT (chữ ký + `exp`) → set cookie `chatbot_session` (HttpOnly, Secure, SameSite=Lax, Max-Age=1d) → 302 redirect URL sạch.
  4. Mọi request tiếp theo: Nginx đọc cookie → verify JWT → forward vào frontend/backend nếu hợp lệ, 302 redirect về `LOGIN_URL` nếu không.
- **JWT Payload**: `{ iat: <timestamp>, exp: <timestamp>, iss: "<login-site-identifier>" }`. KHÔNG chứa user info (chatbot không quan tâm user là ai — chỉ cần token hợp lệ).
- **Session**: 1 ngày (configurable qua `SESSION_MAX_AGE` env, default 86400s).
- **Env vars mới**: `JWT_SECRET` (random 32+ chars), `LOGIN_URL` (URL redirect khi unauthorized), `SESSION_MAX_AGE` (seconds, default 86400 = 1 ngày).
- **Bypass endpoints**: `/health` (backend) giữ public để monitoring. Tất cả endpoints khác (`/`, `/api/chat`, static assets) đều phải qua auth.

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
- **Docker / Docker-Compose**: 4 services:
  - `nginx`: OpenResty (nginx + Lua) — reverse proxy + JWT auth gate, expose port 3000 ra ngoài
  - `chroma`: ChromaDB server (container riêng, data persist qua `chroma_data` volume)
  - `backend`: FastAPI + RAG — KHÔNG expose port (chỉ internal network)
  - `frontend`: Next.js — KHÔNG expose port (chỉ internal network)
- **Git/GitHub**: https://github.com/catboyx99/tuvanluat_chatbot
- **Deploy trên máy mới** (chỉ 3 bước):
  1. `git clone https://github.com/catboyx99/tuvanluat_chatbot.git && cd tuvanluat_chatbot`
  2. Tạo file `.env` ở root chứa: `GEMINI_API_KEY=<key>`, `JWT_SECRET=<random-32+chars>`, `LOGIN_URL=<url-redirect-khi-unauth>`
  3. `docker compose up -d --build` (lần đầu tự ingest ~2-3 phút, các lần sau skip)

## 4. Trạng thái hiện tại — Hoàn thiện
- Frontend + Backend đã hoàn thiện và chạy OK
- 11326 documents pháp luật đã ingest vào ChromaDB
- Dark theme IDE-style, typing effect (~4ms/char), markdown rendering, citation format chuẩn (bullet list)
- Auto scroll theo typing effect (snap instant, không dùng smooth)
- Auto-detect & incremental ingest (1 thư mục md_materials/ duy nhất ở root)
- Query rewriting: thêm dấu tiếng Việt vào câu hỏi, giữ nguyên nghĩa gốc (dùng `gemini-2.5-flash-lite`)
- Singleton pattern: LLM, ChromaDB, embedding khởi tạo 1 lần, dùng lại cho mọi request
- Performance logging: đo thời gian rewrite, vector search, LLM first token
- Loading animation (Scale icon lắc lư + random messages, tắt ngay khi stream bắt đầu có text)
- Anti-hallucination (system prompt linh hoạt + không bịa điều khoản)
- Docker 3 services: ChromaDB (container riêng) + Backend + Frontend, data persist qua volume
- ENV: chỉ cần 1 file `.env` ở root (backend đọc qua `load_dotenv()` trỏ về root, Docker inject qua `environment:`)
- Pushed lên GitHub

## 5. Quy trình phát triển
- **Khi dev tính năng mới**: PHẢI thực hiện đầy đủ đến khi chạy được bằng Docker (`docker compose up -d --build`). Không dừng ở code local — phải đảm bảo build Docker thành công và tính năng hoạt động trong môi trường container.
- **Cập nhật IMPLEMENTATION_PLAN.md**: Khi implement tính năng, phải cập nhật tiến độ trong IMPLEMENTATION_PLAN.md (đánh dấu `[x]` cho task hoàn thành, thêm ghi chú nếu cần).

## 6. Ghi chú kỹ thuật quan trọng
- **Python 3.14** rất mới, có compatibility issues (thiếu `chardet`, Pydantic V1 warning). `--reload` của uvicorn không ổn định trên Windows. Console log phải dùng ASCII (không dùng tiếng Việt trong `print()`) vì Windows cp1252 không encode được Unicode tiếng Việt.
- **Embedding model**: API key chỉ hỗ trợ `gemini-embedding-001`, không có `text-embedding-004`.
- **LLM model**: `gemini-1.5-flash` và `gemini-2.0-flash` đã deprecated. Dùng `gemini-2.5-flash`.
- **AI SDK v6 breaking changes**: `useChat` không còn `input`, `handleInputChange`, `handleSubmit`, `isLoading`. Phải dùng `sendMessage`, `status`, tự quản lý input state. Stream protocol đổi từ `0:"text"\n` sang SSE JSON (`text-start`/`text-delta`/`text-end`).
- **Pydantic**: Model không có `.get()`. Truy cập attribute trực tiếp (`msg.role`, `msg.content`).
