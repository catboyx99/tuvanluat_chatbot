# Kế Hoạch Cải Thiện Tốc Độ Truy Vấn (Improvement Plan)

## 1. Vấn đề Hiện Tại (Bottlenecks)
Dựa theo phân tích từ mã nguồn (chủ yếu trong `backend/app/rag_engine.py`), hiện tại ứng dụng mất **khoảng 4-8 giây** khởi tạo và xử lý trước khi xuất thông điệp đầu tiên ra giao diện người dùng. Các điểm nghẽn chính bao gồm:

1. **Khởi tạo Model liên tục**: `build_llm()` và `rewrite_query()` tạo phiên bản `ChatGoogleGenerativeAI` mới trên mỗi request, dẫn tới độ trễ kết nối mạng.
2. **Khởi tạo ChromaDB Client liên tục**: `get_vector_store()` gọi khởi tạo `HttpClient` và `GoogleGenerativeAIEmbeddings` mới liên tục.
3. **Model Rewrite quá nặng**: Hàm `rewrite_query` hiện đang dùng `gemini-2.5-flash` - một model suy luận mạnh gây chậm trễ không cần thiết ở bước định hình lại câu hỏi.
4. **Độ dài System Prompt**: Prompt trong `invoke_rag_chain` quá dài và được định dạng lại mới hoàn toàn trên mỗi lượt chat.

## 2. Giải Pháp Cải Thiện Đề Xuất

### Thành phần 1: Triển khai Singleton Pattern (Khởi tạo 1 lần)
**Vị trí**: `backend/app/rag_engine.py`
Thay thế các hàm khởi tạo hiện tại bằng biến global (singleton) để dùng lại instance cho tất cả các truy vấn:
* Tạo instance duy nhất cho `vector_store` (`Chroma` client + Embeddings).
* Tạo instance duy nhất cho `llm_main` (Dùng cho quá trình trả lời chính).
* Tạo instance duy nhất cho `llm_rewrite` (Dùng riêng cho việc rewrite lại câu hỏi).

### Thành phần 2: Tự Động Hóa Chuyển Đổi Model Cho Rewrite
**Vị trí**: `backend/app/rag_engine.py` (Hàm `build_rewrite_llm()`)
* Đổi model tại bước `rewrite_query` từ `gemini-2.5-flash` sang **`gemini-2.0-flash-lite`** hoặc một model tối giản hơn để phản hồi nhanh chóng từ 3-5 lần.
* Đặt `temperature=0.0` để tối ưu thời gian tạo sinh.

### Thành phần 3: Tối ưu Hóa Cấu Trúc System Prompt
**Vị trí**: `backend/app/rag_engine.py`
* Đưa template chính của System Prompt ra làm một biến hằng số (`SYSTEM_PROMPT_TEMPLATE`) bên ngoài vòng lặp.
* Rút gọn bớt giải thích lan man, chỉ giữ lại cấu trúc lệnh cứng.

### Thành phần 4: Bổ Sung Đo Lường Hiệu Suất (Performance Logging)
**Vị trí**: `backend/app/rag_engine.py` (Hàm `invoke_rag_chain()`)
* Thêm các mốc đo thời gian `time.time()` để ghi log ra console thời lượng xử lý của từng công đoạn: `Query rewrite` và `Vector search`.

## 3. Kết Quả Mong Đợi
* Giảm thời gian chờ đợi First-Time-To-Byte (FTTB - chữ cái đầu tiên) trên giao diện.
* Dự kiến rút gọn tổng thời gian xuống còn khoảng **1 - 3 giây** (cải thiện x2 đến x4 lần).
* Giảm hao tải RAM/CPU cho máy chủ do không phải liên tục setup connection.
