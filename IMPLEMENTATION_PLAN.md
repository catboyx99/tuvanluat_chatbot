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
  - Typing effect: `requestAnimationFrame` loop ~12ms/char, blinking cursor `|` khi streaming
  - Message appear animation: slide-up + fade-in (CSS `@keyframes msgAppear`)
  - **Loading Animation**: Hiện ngay khi gửi câu hỏi — icon cán cân (Scale) lắc lư (`@keyframes scaleSwing`) + câu trấn an random (8 messages luân phiên). Ẩn bubble assistant rỗng khi chưa có nội dung streaming.
  - Custom dark scrollbar

### 2.2. RAG Pipeline & Backend Engine (Python FastAPI)
- **Framework**: FastAPI, LangChain, Uvicorn, Pydantic, `langchain-google-genai`, `chromadb` (HTTP client)
- **Models**:
  - LLM: `gemini-2.5-flash` (temperature=0.0, streaming=True)
  - Embedding: `gemini-embedding-001`
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
  1. **Query Rewriting**: Dùng LLM chuyển câu hỏi tự nhiên/không dấu/khẩu ngữ thành truy vấn pháp lý tiếng Việt có dấu (VD: "con bố 20 tuổi nó học trường nào đc?" → "Quyền học tập và trình độ đào tạo cho người 20 tuổi")
  2. Retrieval: Top-5 vector search từ ChromaDB (không dùng threshold — để LLM tự đánh giá relevance)
  3. Context: Build context kèm metadata label `[Nguồn: Luật > Chương > Điều > Khoản]`
  4. System Prompt: Linh hoạt suy luận ý định câu hỏi, trả lời 2 phần:
     - Phần 1: Lời tư vấn dễ hiểu
     - Phần 2: "Căn cứ pháp lý:" theo format: Tên văn bản (Số hiệu), Điều [số], Khoản [số], Điểm [chữ]
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
│   │   ├── rag_engine.py     # ChromaDB HTTP client + Gemini LLM + query rewriting + citation system prompt
│   │   ├── document_loader.py# Hierarchical markdown splitter
│   │   └── schemas.py        # Pydantic: ChatMessage, ChatRequest
│   ├── requirements.txt
│   └── Dockerfile
├── chroma_db/                # ChromaDB service
│   └── Dockerfile            # Dựa trên chromadb/chroma:0.6.3
├── md_materials/             # Duy nhất 1 thư mục — chứa file .md luật, mount read-only vào backend container
├── .env                      # GEMINI_API_KEY cho Docker Compose (không commit, tạo thủ công)
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
- [x] Dọn file test rác, re-ingest ChromaDB sạch (2478 docs)
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
