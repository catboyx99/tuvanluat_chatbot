# Product Requirements Document (PRD): Law Consultant Chat Bot

## 1. Giới thiệu (Introduction)
- **Mục tiêu**: Xây dựng một ứng dụng trợ lý ảo báo tư vấn luật chuyên nghiệp, sử dụng công nghệ RAG.
- **Đối tượng sử dụng**: Người dùng cuối cần tra cứu luật pháp Việt Nam.
- **Nguồn dữ liệu**: Các văn bản luật Việt Nam dưới định dạng Markdown (`.md`).

## 2. Các thành phần và Tính năng cốt lõi

### 2.1. Giao diện Người dùng (Chat UI)
- Có Main Header: **"Trợ lý ảo tư vấn luật"**.
- Layout tối giản: Chỉ dùng duy nhất 1 khung chat (chat interface) ở giữa màn hình.
- Trả lời bằng văn bản thuần túy (plain text). Theo sau nội dung tư vấn, bắt buộc phải liệt kê chi tiết nguồn trích dẫn pháp luật (Ví dụ: Bạn có thể tìm hiểu thêm thông tin tại Luật A, Khoản B, Điều C...).
- **Fallback UX (>2s Delay)**: Nếu request lên model tốn quá 2 giây, bot sẽ tự động hiện thông báo trấn an người dùng (hội thoại giả lập ngắn) trước khi có phản hồi thật từ RAG.

### 2.2. Xử lý dữ liệu (Data Pipeline)
- **Nguồn nạp văn bản**: Toàn bộ dữ liệu được hệ thống tự động quét từ thư mục `md_materials`.
- **Tính năng Cắt văn bản Hệ thống Hành chính**: Áp dụng thuật toán chia nhỏ tài liệu theo cấu trúc pháp luật:
  1. Luật (Parent Root)
  2. Điều (1st Child)
  3. Khoản (2nd Child)
  4. Thông tư (Related References)
- **Embedding & Storage**: Dùng Gemini Embedding 2 lưu vào trực tiếp Local Vector DB (ChromaDB).

### 2.3. RAG Engine
- Khi thiết lập LLM, hệ thống phải tuân thủ việc nối kèm đoạn thông tin nguồn vào phía đuôi câu trả lời (Ví dụ: "...lời tư vấn... Bạn có thể tìm thêm thông tin tại Luật a, Khoản b, Điều c và các thông tư số xyz liên quan.")
- **Chống bịa đặt (Anti-Hallucination)**: Tuyệt đối chính xác. Nếu không có thông tin thuộc database pháp luật đã cung cấp thì báo không có dữ liệu.

## 3. Kiến trúc Công nghệ (Technology Stack)
Dự án áp dụng chia tách tách bạch 2 hệ thống Frontend và Backend:
- **Backend (API + RAG Core)**: Python, FastAPI, LangChain, ChromaDB. Yêu cầu thêm: Code luôn được docs/comments method, function rõ ràng.
- **Frontend (UI)**: Next.js 14, TailwindCSS, Vercel AI SDK.
- **Quản lý Mã nguồn (VCS)**: Trọng tâm dùng **Git** và lưu toàn bộ nhánh code, lịch sử file lên hệ sinh thái **GitHub**.
- **Môi trường Demo & Triển khai Linh hoạt**:
  - **Chạy Local**: Mọi service được đóng gói qua **Docker / Docker-Compose** để 1-click chạy đồng nhất trên mọi máy (Developer mode).
  - **Share Public (Stakeholders test)**: Cung cấp quy trình Deploy thông minh lấy Frontend đưa lên Vercel tốc độ cao, và Expose/Deploy ngắn hạn Backend API qua VPS hoặc Ngrok, tiện việc gửi link nghiệm thu sản phẩm.

## 4. Các bước triển khai (Implementation Plan)
1. **Giai đoạn 1 - Khởi tạo Project**: Setup `frontend` Next.js và `backend` FastAPI trong root workspace.
2. **Giai đoạn 2 - Xây dựng RAG Core (Backend)**: Hoàn thiện luồng đọc Markdown đa cấp bậc, lưu ChromaDB, và API query logic với Google Gemini LLM.
3. **Giai đoạn 3 - Giao diện & Tích hợp (Frontend)**: Xây dựng UI 1 khung chat, hiệu ứng streaming, cơ chế "fallback trấn an >2s delay". Kết nối frontend chat với Backend.
4. **Giai đoạn 4 - Kiểm thử & Triển khai**: Thực nghiệm với dữ liệu luật thực tế, đánh giá UX và độ chính xác của văn phong pháp lý.
