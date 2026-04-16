# Implementation Plan: Law Consultant Chat Bot

## 1. Goal Description
Tài liệu này xác định kiến trúc hệ thống và kế hoạch triển khai chi tiết cho ứng dụng Chatbot Luật chuyên nghiệp. Hệ thống sử dụng Google Gemini (LLM & Embeddings) kết hợp Next.js (Frontend) và Python FastAPI (Backend).

## 2. System Architecture (Kiến trúc hệ thống)
Hệ thống triển khai theo **Next.js Frontend + Python FastAPI Backend**, giao tiếp qua proxy route.
*Lưu ý*: BẮT BUỘC viết comment rõ ràng vào từng function và method ở cả Backend và Frontend.

### 2.1. Frontend (User Interface - Next.js)
- **Framework**: Next.js 14 (App Router), React 18, TailwindCSS, `lucide-react`, `react-markdown`
- **AI SDK**: `@ai-sdk/react` v3.0.136 + `ai` v6.0.134
  - Hook `useChat()` trả về: `messages`, `sendMessage`, `status`, `error`
  - `status`: `'ready'` | `'submitted'` | `'streaming'`
  - Gửi message: `sendMessage({ text: string })`
  - Đọc nội dung: `m.parts?.filter(p => p.type === 'text').map(p => p.text).join('')`
  - KHÔNG còn: `input`, `handleInputChange`, `handleSubmit`, `isLoading`, `m.content`
- **Proxy Route** (`src/app/api/chat/route.ts`):
  - Nhận request từ AI SDK (format: `{ id, messages }` với messages chứa `parts`)
  - Extract `query` + `history` gửi sang FastAPI backend
  - Chuyển đổi raw text stream → **SSE UIMessageStream** format:
    ```
    data: {"type":"text-start","id":"uuid"}
    data: {"type":"text-delta","id":"uuid","delta":"text chunk"}
    data: {"type":"text-end","id":"uuid"}
    data: [DONE]
    ```
  - Response headers: `Content-Type: text/event-stream`
- **UI/UX**:
  - Dark theme IDE-style (VS Code colors: `#1e1e1e`, `#252526`, `#2d2d2d`, `#3c3c3c`, `#569cd6`)
  - **Markdown Rendering**: Bot response parse bằng `react-markdown` (bold, list, heading...). User message giữ plain text.
  - Typing effect: `requestAnimationFrame` loop ~4ms/char, blinking cursor `|` khi streaming
  - Message appear animation: slide-up + fade-in (CSS `@keyframes msgAppear`)
  - **Loading Animation**: Hiện ngay khi gửi câu hỏi — icon cán cân (Scale) lắc lư (`@keyframes scaleSwing`) + câu trấn an random (8 messages luân phiên). Tắt ngay khi assistant có text đầu tiên (không đợi stream kết thúc). Ẩn bubble assistant rỗng khi chưa có nội dung streaming.
  - **Auto Scroll**: Dùng `scrollTop = scrollHeight` trên `<main>` ref, gọi liên tục qua `onUpdate` callback từ TypingText component (không dùng `scrollIntoView smooth` vì bị queue lag)
  - **Response Timer**: Bộ đếm thời gian chờ hiển thị trong loading bubble (cạnh icon Scale + câu trấn an). Bắt đầu đếm khi gửi câu hỏi, dừng khi stream có text đầu tiên. Thời gian cuối cùng hiển thị nhỏ dưới khung chat câu trả lời. Format: `120ms` → `1.2s` → `1m:05s`.
  - Custom dark scrollbar
  - **Markdown list style**: CSS bổ sung `list-style-type: disc/decimal` cho `ul/ol` (Tailwind reset mặc định xóa list style)

### 2.2. RAG Pipeline & Backend Engine (Python FastAPI)
- **Framework**: FastAPI, LangChain, Uvicorn, Pydantic, `langchain-google-genai`, `chromadb` (HTTP client)
- **Models**:
  - LLM chính: `gemini-2.5-flash` (temperature=0.0, streaming=True)
  - LLM rewrite: `gemini-2.5-flash-lite` (temperature=0.0) — thêm dấu tiếng Việt vào câu hỏi
  - Embedding: `gemini-embedding-001`
- **Singleton Pattern**: `_vector_store`, `_llm_main`, `_llm_rewrite` khởi tạo 1 lần, dùng lại cho mọi request
- **Performance Logging**: `time.time()` đo rewrite, vector search, LLM first token — log ra console
- **API Endpoints**:
  - `POST /api/chat`: Nhận `{ query: string, history: ChatMessage[] }`, trả `StreamingResponse` (text/plain)
  - `POST /api/ingest`: Quét `md_materials/`, split + embed + lưu ChromaDB
  - `GET /health`: Health check
- **Document Ingestion**:
  - Duy nhất 1 thư mục `md_materials/` ở root project. Backend đọc trực tiếp qua Docker volume mount (`MD_DIR` env var).
  - **Auto-detect & Incremental Ingest**: Khi khởi động backend, kiểm tra ChromaDB:
    - DB rỗng → ingest toàn bộ file `.md`
    - DB có data → so sánh file trong folder vs source metadata trong ChromaDB (`get_ingested_sources()`), chỉ ingest file mới
    - Không có gì mới → skip
  - Hỗ trợ param `only_files` trong `load_and_split_markdown_documents()` cho incremental ingest.
  - `MarkdownHeaderTextSplitter`: Split theo header hierarchy (#→Luật, ##→Chương, ###→Điều, ####→Khoản)
  - `RecursiveCharacterTextSplitter`: chunk_size=1000, overlap=150
  - Metadata: `source`, `Luật/Nghị Định`, `Chương/Mục`, `Điều`, `Khoản`
- **RAG Flow**:
  1. **Query Rewriting**: Dùng `gemini-2.5-flash-lite` thêm dấu tiếng Việt vào câu hỏi, giữ nguyên nghĩa gốc (VD: "con toi 10 tuoi no hoc duoc truong nao" → "Con tôi 10 tuổi, nó học được trường nào?")
  2. Retrieval: Top-10 vector search từ ChromaDB (không dùng threshold — để LLM tự đánh giá relevance)
  3. Context: Build context kèm metadata label `[Nguồn: Luật > Chương > Điều > Khoản]`
  4. System Prompt: Linh hoạt suy luận ý định câu hỏi, trả lời 2 phần:
     - Phần 1: Lời tư vấn dễ hiểu
     - Phần 2: "**Căn cứ pháp lý:**" trên dòng riêng, mỗi nguồn là gạch đầu dòng markdown (`-`). Format: Tên văn bản (Số hiệu), Điều [số], Khoản [số], Điểm [chữ]
  5. KHÔNG trích dẫn tên file markdown, KHÔNG bịa điều khoản, KHÔNG dùng kiến thức bên ngoài context
  6. Nếu không có dữ liệu liên quan → trả lời "Xin lỗi, hệ thống không tìm thấy dữ liệu..."
  7. Stream output qua `llm.stream(messages)`

### 2.3. Cấu trúc Thư mục
```text
LawConsultant_ChatBot/
├── frontend/                 # Workspace Frontend (Node.js)
│   ├── src/app/
│   │   ├── api/chat/route.ts # Proxy: raw stream → SSE UIMessageStream
│   │   ├── page.tsx          # Chat UI + TypingText component + dark theme
│   │   ├── layout.tsx        # SEO metadata, lang="vi"
│   │   └── globals.css       # TailwindCSS + dark scrollbar + typing cursor + msg animation
│   ├── package.json          # @ai-sdk/react v3, ai v6, next 14
│   ├── tailwind.config.ts
│   └── Dockerfile
├── backend/                  # Workspace Backend (Python)
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py           # FastAPI app, CORS, 3 endpoints, auto-detect & incremental ingest, wait_for_chroma
│   │   ├── rag_engine.py     # ChromaDB HTTP client + Gemini LLM (singleton) + query rewriting (flash-lite) + perf logging
│   │   ├── document_loader.py# Hierarchical markdown splitter
│   │   └── schemas.py        # Pydantic: ChatMessage, ChatRequest
│   ├── requirements.txt
│   └── Dockerfile
├── chroma_db/                # ChromaDB service
│   └── Dockerfile            # Dựa trên chromadb/chroma:0.6.3
├── md_materials/             # Duy nhất 1 thư mục — chứa file .md luật, mount read-only vào backend container
├── .env                      # GEMINI_API_KEY — duy nhất 1 file ở root (Docker inject + backend load_dotenv đều đọc file này)
├── docker-compose.yml        # 3 services (chroma, backend, frontend) + chroma_data volume
├── CLAUDE.md                 # PRD (file này dùng làm context cho Claude Code)
├── IMPLEMENTATION_PLAN.md    # File kiến trúc này
└── history_log.md            # Log tiến độ & lỗi blocking
```

### 2.4. DevOps & Triển khai
- **Docker Compose**: 3 services
  - `chroma`: ChromaDB server (image chromadb/chroma:0.6.3), data persist qua `chroma_data` volume
  - `backend`: Python 3.12 FastAPI, kết nối ChromaDB qua HTTP client
  - `frontend`: Node 20 Alpine standalone
- **Docker volumes**:
  - `chroma_data`: persist ChromaDB data giữa các lần run (không cần re-ingest)
  - `./md_materials` mount read-only vào `/app/md_materials` trong backend container
- **Deploy trên máy mới** (chỉ 3 bước):
  1. `git clone https://github.com/catboyx99/tuvanluat_chatbot.git && cd tuvanluat_chatbot`
  2. Tạo file `.env` ở root chứa `GEMINI_API_KEY=<api-key>` (lấy tại https://aistudio.google.com/apikey)
  3. `docker compose up -d --build` (lần đầu tự ingest ~2-3 phút, các lần sau skip)
- **Thêm file luật mới**: Copy file `.md` vào `md_materials/` → `docker compose restart backend`
- **GitHub**: https://github.com/catboyx99/tuvanluat_chatbot

## 3. Các bước triển khai

### Giai đoạn 1 — Khởi tạo Project ✅
Setup `frontend` Next.js và `backend` FastAPI trong root workspace.

### Giai đoạn 2 — RAG Core (Backend) ✅
Hoàn thiện: đọc Markdown đa cấp, lưu ChromaDB, API query logic với Gemini 2.5 Flash.

### Giai đoạn 3 — Giao diện & Tích hợp (Frontend) ✅
- UI dark theme IDE-style, typing effect, streaming
- Proxy route SSE UIMessageStream (tương thích AI SDK v6)
- Fallback UX >2s, citation format chuẩn

### Giai đoạn 4 — Kiểm thử & Triển khai ✅
- [x] Backend health check, single-query stream
- [x] Dọn file test rác, re-ingest ChromaDB sạch (11326 docs)
- [x] Fix AI SDK v6 breaking changes (useChat API + SSE protocol)
- [x] Dark theme + typing effect
- [x] Citation format chuẩn pháp lý (Điều/Khoản/Điểm a, Điểm b, Điểm c)
- [x] Markdown rendering (react-markdown) cho bot response
- [x] Loading animation: Scale icon lắc lư + random messages (hiện ngay, không đợi 2s)
- [x] Ẩn bubble assistant rỗng khi chưa có streaming content
- [x] Auto-detect file .md mới + incremental ingest (1 thư mục md_materials/ duy nhất ở root)
- [x] Dọn file test rác (luat_doanh_nghiep_mau.md, run_law_chatbot.cmd)
- [x] Query rewriting: câu hỏi tự nhiên/không dấu → truy vấn pháp lý chính xác
- [x] Anti-hallucination: system prompt linh hoạt suy luận ý định + không bịa điều khoản
- [x] ChromaDB tách container riêng (server mode, HTTP client)
- [x] Docker 3 services (chroma + backend + frontend), volume persist, chỉ cần `.env` + `docker compose up`
- [x] Push project lên GitHub (https://github.com/catboyx99/tuvanluat_chatbot)

### Giai đoạn 5 — Cải thiện UX ✅
- [x] Tăng tốc typing effect: 12ms/char → 4ms/char (nhanh gấp 3)
- [x] Auto scroll theo typing: dùng `scrollTop` instant thay vì `scrollIntoView smooth` (hết lag)
- [x] Loading animation tắt ngay khi stream có text đầu tiên (không đợi kết thúc)
- [x] Căn cứ pháp lý hiển thị bullet list (mỗi nguồn 1 gạch đầu dòng)
- [x] Fix Tailwind reset xóa list-style: thêm `list-style-type: disc/decimal` trong CSS
- [x] Xóa `backend/.env` thừa, backend `load_dotenv()` trỏ về root `.env`

### Giai đoạn 6 — Response Timer ✅
- [x] Thêm bộ đếm thời gian chờ (Response Timer) trong loading bubble
  - [x] Bắt đầu đếm khi user gửi câu hỏi (status chuyển sang `submitted`)
  - [x] Hiển thị label nhỏ phía dưới loading bubble (text `#6a6a6a`, font 11px)
  - [x] Dừng đếm khi assistant có text đầu tiên (stream bắt đầu)
  - [x] Lưu thời gian cuối cùng vào `finalTimes` map, hiển thị nhỏ phía dưới khung chat câu trả lời
  - [x] Format hiển thị: `120ms` → `1.2s` → `1m:05s`
  - [x] Docker build & deploy thành công

### Giai đoạn 7 — Cải thiện Loading UX ✅
- [x] Đổi dòng timer loading bubble: "Câu trả lời sẽ có trong..." → "Đang phân tích câu hỏi của bạn..."
- [x] Thêm thinking dots animation (3 chấm nhấp nháy lần lượt) vào CSS
- [x] Docker build & deploy thành công

### Giai đoạn 8 — Tối ưu tốc độ FTTB ✅
**Vấn đề**: FTTB 12-14s. Bottleneck: query rewrite (gemini-2.5-flash ~11s) + system prompt quá dài (~1900 chars).
**Giải pháp**: Đổi model rewrite + rút gọn system prompt.

- [x] Tạo hàm `build_rewrite_llm()` riêng dùng `gemini-2.5-flash-lite`, `temperature=0.0`, `streaming=False`
- [x] Cập nhật `rewrite_query()` gọi `build_rewrite_llm()` thay vì `build_llm()`
- [x] Rút gọn System Prompt từ ~1900 chars → ~600 chars (giảm ~70% input tokens)
- [x] Thêm performance logging (`time.time()`) đo rewrite, vector search, LLM first token
- [x] Docker build & deploy thành công
- [x] Benchmark FTTB (3 câu test):
  - "con tôi 10 tuổi nó học được trường nào": 12s → **6.43s** (~1.9x)
  - "Nó muốn đi học đại học nó cần gì": 14s → **9.67s** (~1.4x)
  - "tôi cho cháu căn nhà để đi học được không": **6.01s** (câu test mới)
- [x] Chi tiết cải thiện từng step:
  - Query rewrite: ~11s → ~1s (đổi sang `gemini-2.5-flash-lite`, 10x nhanh hơn)
  - System prompt: ~1900 chars → ~600 chars (giảm 70% input tokens → LLM xử lý nhanh hơn)
  - LLM main: vẫn dao động 3-8s (thinking model, không tắt được qua API)
  - Singleton: request warm giảm thêm ~0.3-0.5s (rewrite 0.48s, search 0.45s)
- [x] **Fix rewrite sai ý định**: Đổi prompt rewrite từ "chuyển thành truy vấn pháp lý" → "thêm dấu tiếng Việt, giữ nguyên nghĩa gốc" — câu 3 rewrite đúng "cho cháu căn nhà" thay vì "thuê nhà"
- [x] **Singleton Pattern**: `get_vector_store()`, `build_llm()`, `build_rewrite_llm()` dùng global singleton — tạo 1 lần, dùng lại cho mọi request
- [x] Docker build & deploy thành công
- [x] Benchmark sau singleton: FTTB request warm tốt nhất **4.08s** (câu 1 lặp lại)

### Giai đoạn 9 — Cải thiện Retrieval Quality ✅
**Vấn đề**: Deploy tại `http://113.161.95.116:3000/`. Khi hỏi "con tôi 5 tuổi cháu học tại đâu được", LLM trả lời "không có dữ liệu pháp lý liên quan" — dù Luật Giáo dục 2019 CÓ chứa nội dung về mầm non, tiểu học.
**Nguyên nhân**: 77/90 file .md có nội dung trong code block → MarkdownHeaderTextSplitter không parse header → chunks thiếu metadata → vector search kém.
**Giải pháp**: Sửa `document_loader.py` — thêm 2 hàm preprocessing + filter junk chunks:
- `strip_code_blocks()`: xóa code block markers, `## Page X`, page numbers, watermarks
- `inject_markdown_headers()`: convert "Điều X.", "Chương X", "LUẬT..." → markdown headers. Header ngắn gọn (chỉ "Điều X"), nội dung xuống dòng riêng (tránh bị nuốt vào metadata).
- Filter chunks < 15 ký tự (junk từ PDF)
- Tăng k=5 → k=10 trong `rag_engine.py`

**Bước 1 — Fix trên local** ✅
- [x] Kiểm tra format: 77/90 file nội dung trong code block
- [x] Thêm `strip_code_blocks()`: xóa code block markers, page numbers, watermarks
- [x] Thêm `inject_markdown_headers()`: convert cấu trúc pháp luật → markdown headers (header ngắn + content tách dòng)
- [x] Filter chunks < 15 chars (junk page numbers)
- [x] Tăng k=5 → k=10

**Bước 2 — Test thành công trên local** ✅
- [x] Re-ingest: 90 files → 10300 chunks (clean, không junk)
- [x] Test "con toi 5 tuoi": trả về đúng Luật GD Điều 28, Điều 99, Điều 26 + NĐ 125 (mầm non)
- [x] Metadata đầy đủ: Luật/Nghị Định, Chương/Mục, Điều (không còn "Không rõ nguồn")
- [x] Test suite 100 câu: **100% answered, 98% citation, 0% no_data, avg 14.35s**
  - Kết quả: `backend/tests/test_suite_20260401_092001.json`
  - Per group: GD 45/45, BHXH 15/15, BHYT 12/12, VL 9/10, TC 10/10, KN 4/5, Khác 3/3

**Bước 3 — Push code lên Git** ✅
- [x] `git commit` (a3dd2fa) + `git push origin main`

**Bước 4 — Pull source về server** ✅
- [x] SSH vào server `113.161.95.116` (user: ubuntu, via plink)
- [x] `cd tuvanluat_chatbot && git pull origin main` — fast-forward OK

**Bước 5 — Re-ingest trên server** ✅
- [x] `docker compose down -v && docker compose up -d --build`
- [x] Auto-ingest: 90 files → 10300 chunks (lần 1 lỗi Gemini 503, lần 2 OK)

**Bước 6 — Verify trên server** ✅
- [x] Test "con toi 5 tuoi chau hoc duoc truong nao" → trả lời đúng mầm non + citation Luật GD Điều 23, 26, 28, 80
- [x] http://113.161.95.116:3000/ hoạt động OK

### Giai đoạn 10 — Authentication Gate (JWT SSO qua Reverse Proxy) 🚧
**Mục tiêu**: Chatbot chỉ truy cập được sau khi user đã login từ 1 website external (tự xây). Dùng **OpenResty (nginx + Lua) reverse proxy** verify JWT HS256 với shared secret.

**Kiến trúc**:
```
External Login Website → generate JWT (HS256, JWT_SECRET) → redirect /?auth=<JWT>
        ↓
Nginx Gateway (OpenResty, port 3000, expose ra ngoài)
        ↓ verify JWT signature + exp
        ├─ Valid  → set cookie chatbot_session (HttpOnly, Max-Age=1d) → forward internal
        └─ Invalid → 302 redirect LOGIN_URL
        ↓
Frontend (Next.js, internal only) + Backend (FastAPI, internal only)
```

**JWT Payload** (minimal, không chứa user info):
```json
{ "iat": 1712345678, "exp": 1712950478, "iss": "login-site-name" }
```

**Env vars mới** (thêm vào `.env` root):
- `JWT_SECRET`: random 32+ chars (generate: `openssl rand -hex 32`)
- `LOGIN_URL`: URL redirect khi unauthorized (VD: `https://login.example.com`)
- `SESSION_MAX_AGE`: default 86400 (1 ngày, seconds) — JWT `exp` + cookie Max-Age cùng giá trị này

**Bước 1 — Thiết kế & chọn tech stack**
- [ ] Xác nhận JWT HS256 + OpenResty `lua-resty-jwt`
- [ ] Tạo file `nginx/` folder: `Dockerfile`, `nginx.conf`, `auth.lua`

**Bước 2 — Implement Nginx gateway**
- [ ] Dockerfile: base `openresty/openresty:alpine` + `opm install SkyLothar/lua-resty-jwt`
- [ ] `nginx.conf`: 
  - `server` block lắng nghe port 3000
  - Location `/` → access_by_lua_file auth.lua → proxy_pass http://frontend:3000
  - Location `/api/chat` → auth check → proxy_pass http://backend:8000 (stream-friendly: `proxy_buffering off`)
  - Location `/health` → public, proxy trực tiếp backend (monitoring)
- [ ] `auth.lua`:
  - Extract `?auth=<JWT>` query param → verify → set cookie + 302 redirect clean URL
  - Hoặc đọc cookie `chatbot_session` → verify JWT → allow/deny
  - Invalid/missing → 302 redirect `LOGIN_URL` (backend env)

**Bước 3 — Cập nhật docker-compose**
- [ ] Thêm service `nginx` với build context `./nginx`
- [ ] Expose chỉ `nginx:3000 → 3000`
- [ ] Remove `ports:` khỏi `frontend` và `backend` (chỉ internal network)
- [ ] Inject env vars: `JWT_SECRET`, `LOGIN_URL`, `SESSION_MAX_AGE` vào nginx
- [ ] Depends_on: `nginx` → `frontend`, `backend`

**Bước 4 — Spec JWT + mock login để test**
- [ ] Tạo file `docs/JWT_SPEC.md`: spec payload format + algo HS256 + pattern redirect `?auth=<JWT>`
- [ ] Tạo `test/mock_login.html` — trang HTML sinh JWT HS256 (dùng JS library) để test end-to-end local, không phụ thuộc website nguồn

**Bước 5 — Test scenarios**
- [ ] Test 1: Truy cập `http://localhost:3000/` không có cookie → 302 redirect `LOGIN_URL` ✓
- [ ] Test 2: Truy cập `http://localhost:3000/?auth=<valid-JWT>` → set cookie + load chatbot UI ✓
- [ ] Test 3: Truy cập `http://localhost:3000/?auth=<expired-JWT>` → 302 redirect ✓
- [ ] Test 4: Truy cập với cookie JWT bị tamper → 302 redirect ✓
- [ ] Test 5: Truy cập `/health` không cần auth → 200 OK ✓
- [ ] Test 6: Gửi chat `/api/chat` có cookie hợp lệ → stream OK ✓

**Bước 6 — Deploy & verify trên server**
- [ ] `git commit` + `git push origin main`
- [ ] SSH server `113.161.95.116`, `git pull`, `docker compose up -d --build`
- [ ] Test trên production với mock_login page
- [ ] Verify port 8000 (backend) + 3000 (frontend) KHÔNG còn expose trực tiếp
- [ ] Cập nhật `.env` server với `JWT_SECRET` + `LOGIN_URL` production

**Bước 7 — Cập nhật docs**
- [ ] Cập nhật CLAUDE.md mục 2.4 Authentication Gate ✅ (đã cập nhật)
- [ ] Cập nhật IMPLEMENTATION_PLAN.md Phase 10 ✅ (đã cập nhật)
- [ ] Cập nhật README deploy steps với `.env` vars mới
