import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

try:
    load_dotenv()
except:
    pass

CHROMA_PATH = "./chroma_db"

def get_vector_store():
    # Sử dụng Embedding model của Gemini
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
    vector_store = Chroma(
        collection_name="law_database",
        embedding_function=embeddings,
        persist_directory=CHROMA_PATH
    )
    return vector_store

def ingest_docs_to_vector_store(documents):
    if not documents:
        return False
    vector_store = get_vector_store()
    vector_store.add_documents(documents)
    return True

def build_llm():
    # Gọi model Gemini 2.5 Flash tối ưu hóa tốc độ độ trễ <2s
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.0,
        streaming=True
    )

def invoke_rag_chain(query: str, history: list):
    """
    Tìm context liên quan trong DB và stream câu trả lời về HTTP.
    Cấu trúc format chèn chính xác Nguồn tham khảo phía cuối cùng.
    """
    vector_store = get_vector_store()

    # 1. Retrieval with relevance score filtering
    RELEVANCE_THRESHOLD = 0.35
    results_with_scores = vector_store.similarity_search_with_relevance_scores(query, k=5)

    # Filter out low-relevance results
    docs = [doc for doc, score in results_with_scores if score >= RELEVANCE_THRESHOLD]

    if not docs:
        yield "Xin l\u1ed7i, h\u1ec7 th\u1ed1ng kh\u00f4ng t\u00ecm th\u1ea5y d\u1eef li\u1ec7u ph\u00e1p l\u00fd li\u00ean quan \u0111\u1ebfn c\u00e2u h\u1ecfi c\u1ee7a b\u1ea1n trong c\u01a1 s\u1edf d\u1eef li\u1ec7u hi\u1ec7n c\u00f3. Vui l\u00f2ng h\u1ecfi v\u1ec1 c\u00e1c v\u0103n b\u1ea3n lu\u1eadt \u0111\u00e3 \u0111\u01b0\u1ee3c n\u1ea1p v\u00e0o h\u1ec7 th\u1ed1ng."
        return

    # 2. Compose Knowledge Context — kèm metadata rõ ràng để LLM trích dẫn chính xác
    context_parts = []
    for d in docs:
        law_name = d.metadata.get("Luật/Nghị Định", "")
        chapter = d.metadata.get("Chương/Mục", "")
        article = d.metadata.get("Điều", "")
        clause = d.metadata.get("Khoản", "")
        label_parts = [p for p in [law_name, chapter, article, clause] if p]
        label = " > ".join(label_parts) if label_parts else "Không rõ nguồn"
        context_parts.append(f"[Nguồn: {label}]\n{d.page_content}")
    context_str = "\n\n---\n\n".join(context_parts)

    # System Prompt yêu cầu trích dẫn theo đúng Điều/Khoản
    system_prompt = f"""Bạn là một Trợ lý Ảo Tư Vấn Luật Pháp Việt Nam vô cùng chính xác.
Nhiệm vụ của bạn là giải đáp câu hỏi của người dùng CHỈ DỰA TRÊN phần "Dữ liệu pháp luật" được cung cấp bên dưới.
TUYỆT ĐỐI KHÔNG sử dụng kiến thức bên ngoài. CHỈ trả lời dựa trên dữ liệu pháp luật bên dưới.
Hãy cố gắng tìm thông tin liên quan nhất trong dữ liệu để trả lời câu hỏi của người dùng.
KHÔNG ĐƯỢC bịa ra bất kỳ điều luật, khoản, hay nội dung nào không có trong dữ liệu bên dưới.
Chỉ khi dữ liệu HOÀN TOÀN không liên quan đến câu hỏi, hãy trả lời: "Xin lỗi, hệ thống hiện tại không có dữ liệu pháp lý liên quan đến câu hỏi này."

YÊU CẦU ĐỊNH DẠNG câu trả lời gồm 2 phần:

Phần 1 — Lời tư vấn: Giải thích dễ hiểu, mạch lạc cho người dùng.

Phần 2 — Căn cứ pháp lý: Nằm ở cuối câu trả lời, liệt kê CHÍNH XÁC các điều khoản đã sử dụng.
Format bắt buộc theo thứ tự: Tên văn bản (Số hiệu), Điều [số], Khoản [số], Điểm [chữ].
Nếu có nhiều Điểm trong cùng một Khoản thì liệt kê tất cả trên cùng một dòng.
Mỗi văn bản pháp luật khác nhau trích trên một dòng riêng.

Ví dụ:
- "Căn cứ pháp lý: Luật Giáo dục 2019 (Luật số 43/2019/QH14), Điều 28, Khoản 1, Điểm a, Điểm b, Điểm c."
- "Căn cứ pháp lý: Thông tư số 03/2022/TT-BGDĐT, Điều 5, Khoản 2."
- "Căn cứ pháp lý: Nghị định số 115/2020/NĐ-CP, Điều 10, Khoản 2, Điểm a."
- Nếu trích nhiều Điều từ cùng một văn bản, liệt kê từng Điều trên dòng riêng:
  "Căn cứ pháp lý:
  Luật Giáo dục 2019 (Luật số 43/2019/QH14), Điều 28, Khoản 1, Điểm a, Điểm b.
  Luật Giáo dục 2019 (Luật số 43/2019/QH14), Điều 29, Khoản 3."

QUY TẮC trích dẫn:
- Đọc kỹ nội dung dữ liệu để xác định chính xác số Điều, Khoản, Điểm được nhắc đến.
- Tên luật phải viết đầy đủ dạng đọc được (ví dụ: "Luật Giáo dục 2019" thay vì "Luật-43-2019-QH14").
- Kèm số hiệu văn bản trong ngoặc đơn (ví dụ: "(Luật số 43/2019/QH14)").
- Luôn trích dẫn đầy đủ đến cấp chi tiết nhất có trong dữ liệu: Điều → Khoản → Điểm.
- KHÔNG trích dẫn tên file markdown. KHÔNG bịa số điều khoản không có trong dữ liệu.
- Nếu dữ liệu không đủ để xác định Điều/Khoản cụ thể, chỉ ghi tên văn bản.

Dữ liệu pháp luật:
======================
{context_str}
======================
"""

    messages = [SystemMessage(content=system_prompt)]

    # 3. Quản lý Memory - Push Sliding Window
    # Frontend gửi 5 messages gần nhất để tạo luồng multi-turn
    for msg in history:
        # msg là Pydantic ChatMessage object, truy cập trực tiếp qua attribute
        if msg.role == "user":
            messages.append(HumanMessage(content=msg.content))
        else:
            messages.append(AIMessage(content=msg.content))

    # Thêm câu hỏi cuối
    messages.append(HumanMessage(content=query))

    # 4. Stream output
    llm = build_llm()
    for chunk in llm.stream(messages):
        yield chunk.content
