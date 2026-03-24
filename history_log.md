# History Log - Law Consultant Chat Bot
> Cập nhật lần cuối: 2026-03-23 23:10

---

## ✅ ĐÃ HOÀN THÀNH

### 1. Tài liệu thiết kế
- [x] `prd.md` — Product Requirements Document (đã chốt).
- [x] `impl_plan.md` — Kiến trúc hệ thống, directory tree, DevOps Docker (đã chốt).

### 2. Frontend (Next.js 14) — `frontend/`
| File | Trạng thái | Mô tả |
|---|---|---|
| `package.json` | ✅ Done | Đã cài `ai`, `@ai-sdk/react`, `lucide-react`, Next 14, TailwindCSS |
| `src/app/page.tsx` | ✅ Done | Giao diện chat 1 khung, Header "Trợ lý ảo tư vấn luật", fallback UX >2s delay, streaming text |
| `src/app/layout.tsx` | ✅ Done | SEO metadata tiếng Việt, lang="vi" |
| `src/app/globals.css` | ✅ Done | TailwindCSS base + custom scrollbar |
| `src/app/api/chat/route.ts` | ✅ Done | Proxy route chuyển đổi raw text stream từ FastAPI sang Vercel AI SDK data stream protocol |
| `tailwind.config.ts` | ✅ Done | Content paths đã cấu hình |
| `next.config.mjs` | ✅ Done | Bỏ qua TS/ESLint errors khi build |
| `Dockerfile` | ✅ Done | node:20-alpine, build + start |
| `node_modules/` | ✅ Done | Đã `npm install` thành công |

### 3. Backend (Python FastAPI) — `backend/`
| File | Trạng thái | Mô tả |
|---|---|---|
| `app/__init__.py` | ✅ Done | Package init |
| `app/main.py` | ✅ Done | FastAPI app, CORS, 3 endpoints: `/health`, `/api/chat`, `/api/ingest` |
| `app/rag_engine.py` | ✅ Done | ChromaDB vector store, Gemini LLM streaming, system prompt anti-hallucination |
| `app/document_loader.py` | ✅ Done | Hierarchical Markdown splitter (Luật→Chương→Điều→Khoản) + RecursiveCharacterTextSplitter |
| `app/schemas.py` | ✅ Done | Pydantic models: ChatMessage, ChatRequest |
| `requirements.txt` | ✅ Done | fastapi, uvicorn, langchain, langchain-google-genai, chromadb, pydantic, python-dotenv |
| `.env` | ✅ Done | GEMINI_API_KEY đã có |
| `Dockerfile` | ✅ Done | python:3.10-slim, pip install, uvicorn |
| `md_materials/` | ✅ Done | 29 file luật thật đã copy từ thư mục gốc (Luật, Nghị định, Thông tư, Quyết định) |

### 4. DevOps
| File | Trạng thái | Mô tả |
|---|---|---|
| `docker-compose.yml` | ✅ Done | Orchestration 2 services (frontend:3000, backend:8000), volume mount md_materials |

### 5. Python Environment & Backend Runtime
| Bước | Trạng thái | Chi tiết |
|---|---|---|
| Cài Python 3.14.3 | ✅ Done | Đã cài thành công trên máy Windows |
| Tạo venv | ✅ Done | `python -m venv venv` trong `backend/` |
| Cài dependencies | ✅ Done | `pip install -r requirements.txt` + bổ sung `chardet` (thiếu module) |
| Fix Embedding Model | ✅ Done | Đổi `text-embedding-004` → `gemini-embedding-001` (model cũ không khả dụng trên API key) |
| Fix LLM Model | ✅ Done | Đổi `gemini-1.5-flash` → `gemini-2.0-flash` → `gemini-2.5-flash` (các phiên bản cũ không còn khả dụng) |
| Chạy Backend | ✅ Done | `uvicorn app.main:app --reload --port 8000` đang chạy OK |
| Ingest dữ liệu luật | ✅ Done | `POST /api/ingest` thành công: **2692 documents** đã nạp vào ChromaDB |
| Chạy Frontend | ✅ Done | `npm run dev` tại `http://localhost:3000` đang chạy OK |

### 6. E2E Testing & Bug Fixes *(MỚI)*
| Bước | Trạng thái | Chi tiết |
|---|---|---|
| Backend `/health` | ✅ Done | Trả về `{"status":"ok"}` |
| Backend single-query stream | ✅ Done | Stream hoạt động đúng, câu trả lời có nguồn trích dẫn |
| Fix model deprecated | ✅ Done | `gemini-2.0-flash` bị khai tử với user mới → đổi sang `gemini-2.5-flash` trong `rag_engine.py` |
| Fix multi-turn bug | ✅ Done | `msg.get("role")` gọi trên Pydantic model gây AttributeError → sửa thành `msg.role` / `msg.content` trực tiếp |
| Next.js proxy single-query | ✅ Done | Trả về đúng chuẩn `0:"..."` Vercel AI SDK, header `X-Vercel-AI-Data-Stream: v1` |
| Next.js proxy multi-turn | ⚠️ Pending | Server Next.js bị crash khi test, cần restart lại và retest |

---

## 🔜 CÁC BƯỚC TIẾP THEO

### 7. Hoàn thiện E2E Test (ưu tiên cao)
- [ ] Restart `npm run dev` tại `frontend/`
- [ ] Test multi-turn conversation qua Next.js proxy (câu 1 → câu 2 liên tiếp)
- [ ] Mở trình duyệt `http://localhost:3000` và test thủ công trên UI
- [ ] Kiểm tra UX: fallback loading >2s, scroll behavior, error handling

### 8. Dọn dẹp ChromaDB (ưu tiên trung bình)
- [ ] Xoá các file test bị lẫn vào `md_materials/` (`auto_realtime_test_*.md`, `auto_livecheck_*.md`)
- [ ] Re-ingest lại `POST /api/ingest` để loại bỏ nguồn trích dẫn rác

### 9. Polish & Deploy
- [ ] Test Docker build (`docker-compose up --build`)
- [ ] Tối ưu UI/UX nếu cần
- [ ] Triển khai public demo (nếu cần)

---

## 📝 GHI CHÚ KỸ THUẬT

- **Python 3.14.3** rất mới, có thể gặp compatibility issues với một số packages (đã gặp lỗi thiếu `chardet`, Pydantic V1 warning).
- **Embedding model**: API key hiện tại chỉ hỗ trợ `gemini-embedding-001`, không có `text-embedding-004`.
- **LLM model**: `gemini-2.0-flash` không còn khả dụng cho user mới. Dùng `gemini-2.5-flash`.
- **Multi-turn bug**: Pydantic model không có method `.get()`. Luôn truy cập trực tiếp qua `msg.role`, `msg.content`.
- **Browser test limitation**: Playwright không gõ được tiếng Việt có dấu trực tiếp (lỗi `Unknown key: "ô"`), cần dùng clipboard paste hoặc test thủ công.
- **ChromaDB pollution**: Một số file test (`.md`) bị lẫn vào `md_materials/` và đã được ingest, gây xuất hiện trong nguồn trích dẫn. Cần dọn trước khi demo.
