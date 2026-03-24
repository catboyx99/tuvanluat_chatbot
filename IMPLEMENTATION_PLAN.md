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
- **Framework**: FastAPI, LangChain, Uvicorn, Pydantic, ChromaDB, `langchain-google-genai`
- **Models**:
  - LLM: `gemini-2.5-flash` (temperature=0.0, streaming=True)
  - Embedding: `gemini-embedding-001`
- **API Endpoints**:
  - `POST /api/chat`: Nhận `{ query: string, history: ChatMessage[] }`, trả `StreamingResponse` (text/plain)
  - `POST /api/ingest`: Quét `md_materials/`, split + embed + lưu ChromaDB
  - `GET /health`: Health check
- **Document Ingestion**:
  - 2 thư mục `md_materials/`: root (nơi user thêm file mới) và `backend/md_materials/` (BE dùng để ingest)
  - **Auto-sync & Incremental Ingest**: Khi khởi động backend, tự so sánh root vs backend, copy file `.md` mới sang backend, chỉ ingest file mới vào ChromaDB (không trùng lặp). Hỗ trợ param `only_files` trong `load_and_split_markdown_documents()`.
  - `MarkdownHeaderTextSplitter`: Split theo header hierarchy (#→Luật, ##→Chương, ###→Điều, ####→Khoản)
  - `RecursiveCharacterTextSplitter`: chunk_size=1000, overlap=150
  - Metadata: `source`, `Luật/Nghị Định`, `Chương/Mục`, `Điều`, `Khoản`
- **RAG Flow**:
  1. Retrieval: Top-5 vector search từ ChromaDB, lọc qua relevance score threshold (0.35) — loại bỏ kết quả không liên quan
  2. Context: Build context kèm metadata label `[Nguồn: Luật > Chương > Điều > Khoản]`
  3. System Prompt: Yêu cầu trả lời 2 phần:
     - Phần 1: Lời tư vấn dễ hiểu
     - Phần 2: "Căn cứ pháp lý:" theo format: Tên văn bản (Số hiệu), Điều [số], Khoản [số], Điểm [chữ]. Nhiều Điểm cùng Khoản liệt kê trên 1 dòng (VD: "Điểm a, Điểm b, Điểm c"). Nhiều Điều từ cùng văn bản → mỗi Điều trên dòng riêng.
  4. KHÔNG trích dẫn tên file markdown, KHÔNG bịa điều khoản, KHÔNG dùng kiến thức bên ngoài context
  5. Nếu không có dữ liệu liên quan → trả lời "Xin lỗi, hệ thống không tìm thấy dữ liệu..."
  5. Stream output qua `llm.stream(messages)`

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
│   │   ├── main.py           # FastAPI app, CORS, 3 endpoints
│   │   ├── rag_engine.py     # ChromaDB + Gemini LLM + citation system prompt
│   │   ├── document_loader.py# Hierarchical markdown splitter
│   │   └── schemas.py        # Pydantic: ChatMessage, ChatRequest
│   ├── md_materials/         # 27 file luật (Luật, Nghị định, Thông tư, Quyết định)
│   ├── chroma_db/            # ChromaDB persistent storage (2478 documents)
│   ├── requirements.txt
│   ├── .env                  # GEMINI_API_KEY
│   └── Dockerfile
├── md_materials/             # Thư mục root — nơi user thêm file .md mới (auto-sync sang backend)
├── docker-compose.yml        # 2 services (frontend:3000, backend:8000)
├── CLAUDE.md                 # PRD (file này dùng làm context cho Claude Code)
├── IMPLEMENTATION_PLAN.md    # File kiến trúc này
└── history_log.md            # Log tiến độ & lỗi blocking
```

### 2.4. DevOps & Triển khai
- **Local**: `docker-compose up -d` — 2 images (node:20-alpine standalone + python:3.12-slim)
- **Docker images**: backend 271MB, frontend 53MB. Self-contained (chứa sẵn chroma_db + md_materials)
- **Chuyển máy khác**: `docker save` → copy `.tar` + `docker-compose.yml` + `.env` → `docker load` → `docker-compose up -d`
- **GitHub**: https://github.com/catboyx99/tuvanluat_chatbot
- **Root `.env`**: Chứa `GEMINI_API_KEY`, docker-compose tự đọc — không cần truyền thủ công
- **Lưu ý Windows**: Uvicorn `--reload` không ổn định với Python 3.14 trên Windows, chạy không có `--reload`. Console log phải dùng ASCII (không tiếng Việt trong `print()`) vì Windows cp1252 không encode được Unicode tiếng Việt.

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
- [x] Auto-sync file .md mới từ root → backend + incremental ingest
- [x] Dọn file test rác (luat_doanh_nghiep_mau.md, run_law_chatbot.cmd)
- [x] Anti-hallucination: relevance score threshold (0.35) + system prompt cấm kiến thức ngoài
- [x] Docker build OK — 2 images: backend (271MB, Python 3.12) + frontend (53MB, Node 20 standalone)
- [x] Docker Compose chạy OK — root `.env` chứa GEMINI_API_KEY, không cần truyền thủ công
- [x] Push project lên GitHub (https://github.com/catboyx99/tuvanluat_chatbot)
