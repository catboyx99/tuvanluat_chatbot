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
- **Hiệu ứng Typing**: Bot trả lời với hiệu ứng gõ chữ từng ký tự mượt mà (requestAnimationFrame ~12ms/char) kèm con trỏ `|` nhấp nháy xanh. Message mới slide-up + fade-in.
- **Markdown Rendering**: Bot trả lời dạng Markdown, frontend parse bằng `react-markdown` (in đậm, list, heading...). User message giữ plain text.
- **Trích dẫn pháp lý chuẩn**: Cuối câu trả lời bắt buộc có phần "Căn cứ pháp lý" trích dẫn theo format:
  - Thứ tự: Tên văn bản (Số hiệu), Điều [số], Khoản [số], Điểm [chữ].
  - Nhiều Điểm cùng Khoản liệt kê trên 1 dòng: "Luật Giáo dục 2019 (Luật số 43/2019/QH14), Điều 28, Khoản 1, Điểm a, Điểm b, Điểm c."
  - Nhiều Điều từ cùng văn bản → mỗi Điều trên dòng riêng.
  - KHÔNG được trích dẫn tên file markdown. Phải ghi tên luật đầy đủ + số hiệu văn bản + Điều/Khoản/Điểm cụ thể.
  - Nếu không xác định được Điều/Khoản, chỉ ghi tên văn bản.
- **Loading Animation**: Khi gửi câu hỏi, hiện ngay icon cán cân (Scale) lắc lư kèm câu trấn an random (8 messages luân phiên). Ẩn bubble assistant rỗng khi chưa có nội dung streaming.

### 2.2. Xử lý dữ liệu (Data Pipeline)
- **Nguồn nạp văn bản**: 2 thư mục `md_materials/` — root (nơi user thêm file mới) và `backend/md_materials/` (BE dùng để ingest).
- **Auto-sync & Incremental Ingest**: Khi khởi động backend, tự động so sánh root vs backend, copy file `.md` mới sang backend, rồi chỉ ingest file mới vào ChromaDB (không trùng lặp data cũ).
- **Tính năng Cắt văn bản theo cấu trúc pháp luật**: Áp dụng thuật toán chia nhỏ tài liệu theo cấu trúc:
  1. Luật/Nghị Định (Parent Root — Header #)
  2. Chương/Mục (Header ##)
  3. Điều (Header ###)
  4. Khoản (Header ####)
- **Embedding & Storage**: Dùng `gemini-embedding-001` lưu vào Local Vector DB (ChromaDB).

### 2.3. RAG Engine
- Khi trả lời, hệ thống phải đọc kỹ nội dung chunks để xác định chính xác số Điều, Khoản, Điểm rồi trích dẫn ở cuối câu trả lời theo format chuẩn "Căn cứ pháp lý".
- **Chống bịa đặt (Anti-Hallucination)**:
  - Relevance score threshold (0.35) — lọc bỏ kết quả vector search không liên quan trước khi đưa vào LLM.
  - System prompt nghiêm cấm sử dụng kiến thức bên ngoài, bắt buộc trả lời "không có dữ liệu" nếu context không chứa thông tin.
  - KHÔNG bịa số điều khoản.

## 3. Kiến trúc Công nghệ (Technology Stack)

### 3.1. Backend (API + RAG Core)
- Python 3.14, FastAPI, LangChain, ChromaDB
- LLM: `gemini-2.5-flash` (streaming, temperature=0.0)
- Embedding: `gemini-embedding-001`
- Code luôn được docs/comments rõ ràng

### 3.2. Frontend (UI)
- Next.js 14 (App Router), TailwindCSS, `lucide-react`, `react-markdown`
- **AI SDK**: `@ai-sdk/react` v3 + `ai` v6 (UIMessageStream SSE protocol)
  - Hook: `useChat()` → `sendMessage({ text })`, `status`, `messages`
  - Proxy route chuyển đổi raw text stream từ FastAPI → SSE UIMessageStream format (`text-start`, `text-delta`, `text-end`, `[DONE]`)
  - Message content truy cập qua `m.parts` (không phải `m.content`)

### 3.3. DevOps
- **Docker / Docker-Compose**: 2 services (frontend:3000, backend:8000)
- **Git/GitHub**: Version control
- **Deploy**: Vercel (Frontend) + VPS/Ngrok (Backend)

## 4. Trạng thái hiện tại
- Frontend + Backend đã hoàn thiện và chạy OK
- 2478 documents pháp luật đã ingest vào ChromaDB (sạch, không file test rác)
- Dark theme IDE-style, typing effect, markdown rendering, citation format chuẩn đã triển khai
- Auto-sync & incremental ingest đã triển khai
- Loading animation (Scale icon lắc lư + random messages) đã triển khai
- Cần hoàn thiện: Docker build test, E2E multi-turn test, deploy public demo

## 5. Ghi chú kỹ thuật quan trọng
- **Python 3.14** rất mới, có compatibility issues (thiếu `chardet`, Pydantic V1 warning). `--reload` của uvicorn không ổn định trên Windows. Console log phải dùng ASCII (không dùng tiếng Việt trong `print()`) vì Windows cp1252 không encode được Unicode tiếng Việt.
- **Embedding model**: API key chỉ hỗ trợ `gemini-embedding-001`, không có `text-embedding-004`.
- **LLM model**: `gemini-1.5-flash` và `gemini-2.0-flash` đã deprecated. Dùng `gemini-2.5-flash`.
- **AI SDK v6 breaking changes**: `useChat` không còn `input`, `handleInputChange`, `handleSubmit`, `isLoading`. Phải dùng `sendMessage`, `status`, tự quản lý input state. Stream protocol đổi từ `0:"text"\n` sang SSE JSON (`text-start`/`text-delta`/`text-end`).
- **Pydantic**: Model không có `.get()`. Truy cập attribute trực tiếp (`msg.role`, `msg.content`).
