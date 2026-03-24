# Implementation Plan: Law Consultant Chat Bot

## 1. Goal Description
Tài liệu này xác định kiến trúc hệ thống và kế hoạch triển khai chi tiết cho ứng dụng Chatbot Luật chuyên nghiệp, đáp ứng yêu cầu chạy thực tế (Production-ready). Hệ thống sử dụng Google Gemini (LLM & Embeddings) kết hợp Next.js (Frontend) và Python FastAPI (Backend).

## 2. System Architecture (Kiến trúc hệ thống)
Hệ thống sẽ được triển khai theo **Phương án B (Next.js Frontend + Python FastAPI Backend)**.
*Lưu ý lập trình*: Xuyên suốt quá trình phát triển, BẮT BUỘC phải viết comment rõ ràng vào từng function và method ở cả Backend và Frontend.

### 2.1. Frontend (User Interface - Next.js)
- **Framework & Libraries**: Next.js 14 (App Router), React, TailwindCSS, `lucide-react` (cho icon).
- **Thư viện AI**: Chuyên dùng `Vercel AI SDK` (`useChat` hook) để quản lý state và text streaming hiển thị gõ chữ tự nhiên.
- **Trải nghiệm UX/UI**:
  - Giao diện 1 khung chat tối giản duy nhất (Main Header: "Trợ lý ảo tư vấn luật").
  - Trả lời bằng plain text. Cho phép hiển thị khối Nguồn Tham khảo pháp luật đính kèm riêng biệt ở đoạn sau cùng của câu trả lời.
  - **Memory & Lịch sử**: Lưu lịch sử chat tạm thời trên **Local Storage** hoặc Session Storage của trình duyệt người dùng để tối ưu băng thông và giảm gánh nặng DB, không bắt user tạo tài khoản đăng nhập.
  - **Xử lý Delay**: Tích hợp một state checker (đếm giây). Nếu thời gian đợi backend phản hồi vượt quá 2s, Frontend chủ động sinh ra dòng chat giả lập giữ chỗ (Ví dụ: "Hệ thống đang rà soát các điều luật liên quan, bạn đợi một lát nhé...").

### 2.2. RAG Pipeline & Backend Engine (Python FastAPI)
- **Framework & Libraries**: FastAPI, LangChain, Uvicorn, Pydantic, ChromaDB, Google GenAI SDK.
- **Mô hình Dữ liệu (API Endpoints)**:
  - `POST /api/chat`: Nhận Input (Query + Mảng Lịch sử hội thoại 5 câu gần nhất) và trả về nội dung theo dạng `StreamingResponse` liên tục từ LLM.
  - `POST /api/ingest`: Trigger để backend quét lại thư mục `md_materials` (Update tài liệu trực tiếp qua endpoint mà không cần khởi động lại Server).
  - `GET /health`: Endpoint Ping kiểm tra kết nối Server & Model.
- **Document Ingestion (Nạp dữ liệu)**: 
  - Đọc thẳng nguồn tài liệu markdown trong `backend/md_materials/`.
  - Thuật toán **Hierarchical Text Splitter**: Phân mảnh phân cấp theo ngữ nghĩa (Luật, Điều, Khoản, Thông tư) đính kèm Metadata rõ ràng để bảo toàn tính pháp lý cho mỗi Node.
- **Embedding & Database**: Sử dụng API `text-embedding-004` -> lưu qua Local Vector Database (ChromaDB).
- **Quy trình Sinh đáp án (Retrieval)**:
  1. *Truy Vấn*: Extract keyword kết hợp Top K Vector Search (Lấy ra 4-5 chunks pháp lý liên quan nhất).
  2. *System Prompting*: Chèn mạnh quy tắc format 2 phần: (1) Lời giải đáp tư vấn, (2) DƯỚI ĐÓ đính kèm câu "Bạn có thể tìm hiểu thêm thông tin tại luật a, khoản b, điều c và các thông tư số xyz..." để minh bạch nguồn. Nếu không thấy tài liệu thì kiên quyết từ chối trả lời (zero-hallucination).
  3. *Call Model*: Gửi context và prompt tới model `gemini-1.5-flash` (cho tốc độ streaming cao nhất).

### 2.3. Cấu trúc Thư mục Hệ thống (Directory Tree)
Để việc lập trình rõ ràng, hệ thống cấp phát chuẩn 2 workspace con:
```text
LawConsultant_ChatBot/
├── frontend/                 # Workspace Frontend (Node.js)
│   ├── src/app/
│   │   ├── api/chat/route.ts # Proxy route: chuyển đổi raw stream → Vercel AI SDK protocol
│   │   ├── page.tsx          # Trọng tâm Khung Chat
│   │   ├── layout.tsx        # SEO metadata, lang="vi"
│   │   └── globals.css       # TailwindCSS base + custom scrollbar
│   ├── package.json
│   ├── tailwind.config.ts
│   └── Dockerfile            # Cấu hình Build Image cho UI
├── backend/                  # Workspace Backend (Python)
│   ├── app/
│   │   ├── __init__.py       # Package init
│   │   ├── main.py           # Init app FastAPI, cấu hình CORS
│   │   ├── rag_engine.py     # Gọi LangChain, quản lý ChromaDB Client, giao tiếp LLM
│   │   ├── document_loader.py# Logic cắt text đa cấp bậc pháp lý
│   │   └── schemas.py        # Pydantic (Định dạng Request Body)
│   ├── md_materials/         # 29 file luật thật (copy từ thư mục gốc)
│   ├── requirements.txt      # Gồm: langchain, langchain-chroma, langchain-community, chromadb...
│   ├── .env                  # Chứa GEMINI_API_KEY
│   └── Dockerfile            # Cấu hình Build Image cho API
├── docker-compose.yml        # Orchestration vận hành 2 hệ thống chung
├── history_log.md            # Log tiến độ dự án & lỗi blocking
└── impl_plan.md              # File kiến trúc này
```

### 2.4. DevOps & Chế độ Triển khai
Để đáp ứng nhu cầu vừa phát triển cục bộ, vừa nhanh chóng gửi link cho Stakeholders dùng thử, hệ thống sẽ định hình 2 quy trình song song:
- **Chế độ Local (Phát triển nội bộ)**: 
  - Build file `docker-compose.yml` quy hoạch 2 Image riêng biệt, kết nối bằng Custom Network nội bộ.
  - Chạy `docker-compose up --build`. Môi trường sẽ tự động dựng Image `node:20` cho Frontend và `python:3.10` cho Backend (Kèm Uvicorn, ChromaDB). Giải quyết dứt điểm rủi ro lỗi version chênh lệch giữa các hệ điều hành cá nhân.
- **Chế độ Share Public (Test cho Stakeholders)**:
  - Khai thác CI/CD của nhánh git để kéo Frontend từ thư mục `frontend/` đưa thẳng lên nền tảng **Vercel** miễn phí, hưởng cơ sở hạ tầng Public cực nhanh.
  - Về Backend: Expose host local qua **Ngrok / Cloudflare Tunnels** và lấy HTTPS trỏ ngược cho Vercel. HOẶC đẩy `docker-compose` backend rớt lên một Cloud VPS cấp thấp (DigitalOcean/Vultr) để chạy 24/7 đón nhận query từ Frontend Vercel gửi về. Không chia sẻ code server cho client.
