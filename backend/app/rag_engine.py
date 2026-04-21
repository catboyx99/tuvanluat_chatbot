import os
import time
import chromadb
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

try:
    # Tim file .env o root project (2 cap tren file nay)
    _root_env = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
    load_dotenv(_root_env)
except:
    pass

CHROMA_HOST = os.environ.get("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.environ.get("CHROMA_PORT", "8000"))

# === Singleton instances — khoi tao 1 lan, dung lai cho moi request ===
_vector_store = None
_llm_main = None
_llm_rewrite = None

def get_vector_store():
    global _vector_store
    if _vector_store is None:
        embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
        client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
        _vector_store = Chroma(
            client=client,
            collection_name="law_database",
            embedding_function=embeddings,
        )
    return _vector_store

def ingest_docs_to_vector_store(documents):
    if not documents:
        return False
    vector_store = get_vector_store()
    vector_store.add_documents(documents)
    return True

def build_llm():
    # Model chinh: Gemini 2.5 Flash cho cau tra loi (streaming)
    global _llm_main
    if _llm_main is None:
        _llm_main = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.0,
            streaming=True
        )
    return _llm_main

def build_rewrite_llm():
    # Model nhe cho query rewriting: gemini-2.5-flash-lite (nhanh gap ~10x so voi 2.5-flash)
    global _llm_rewrite
    if _llm_rewrite is None:
        _llm_rewrite = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash-lite",
            temperature=0.0,
            streaming=False
        )
    return _llm_rewrite

# Sentinel token frontend dung de nhan biet loi qua tai
GEMINI_OVERLOAD_SENTINEL = "__GEMINI_OVERLOAD__"


def rewrite_query(query: str) -> str:
    """Chuan hoa cau hoi thanh cum tu tim kiem phap ly:
    - Them dau tieng Viet.
    - Loai bo tu dem/tu yeu cau (quy dinh, cho toi biet, hay, la gi, the nao, ...).
    - Giu nguyen chu de goc + thuat ngu phap ly chinh.
    Muc tieu: cau hoi cung chu de nhung khac cach dien dat se chuan hoa ve cung mot query.
    """
    llm = build_rewrite_llm()
    try:
        result = llm.invoke([
            SystemMessage(content=(
            "Chuẩn hoá câu hỏi thành cụm từ khoá tìm kiếm pháp lý bằng tiếng Việt CÓ DẤU ĐẦY ĐỦ. "
            "BẮT BUỘC output luôn có dấu tiếng Việt đầy đủ, kể cả khi input không có dấu — ví dụ 'thanh lap dai hoc' phải thành 'thành lập đại học'.\n\n"
            "BẮT BUỘC GIỮ LẠI (không được xoá dù input có dài):\n"
            "- Số liệu cụ thể: tuổi ('5 tuổi', '18 tuổi'), lớp ('lớp 1', 'lớp 6'), thời gian ('3 tháng', '6 năm'), số tiền.\n"
            "- Đối tượng pháp lý: trẻ em, con, cháu, học sinh, sinh viên, người lao động, công dân, vợ chồng, giáo viên, công chức, ...\n"
            "- Danh từ chủ đề + động từ pháp lý: học, kết hôn, ly hôn, thành lập, giải thể, bổ nhiệm, thừa kế, nhận con nuôi, ...\n\n"
            "CHỈ LOẠI BỎ từ đệm/yêu cầu KHÔNG mang nội dung: 'cho tôi biết', 'tôi muốn biết', 'hãy nói', 'là gì', 'như thế nào', 'ra sao', 'được không', 'dc', 'quy định về' (khi đứng đầu), dấu '?'.\n\n"
            "Ví dụ:\n"
            "- 'con tôi 5 tuổi cháu học ở đâu' → 'trẻ 5 tuổi học ở đâu' (GIỮ '5 tuổi').\n"
            "- 'con toi 5 tuoi chau hoc truong nao dc' → 'trẻ 5 tuổi học trường nào'.\n"
            "- 'quy định thành lập đại học' → 'thành lập đại học'.\n"
            "- 'cho tôi biết độ tuổi vào lớp 1 là gì' → 'độ tuổi vào lớp 1'.\n"
            "- 'hãy nói về điều kiện kết hôn' → 'điều kiện kết hôn'.\n"
            "- 'vợ chồng ly hôn chia tài sản như thế nào' → 'vợ chồng ly hôn chia tài sản'.\n\n"
            "CHỈ trả về cụm từ đã chuẩn hoá, tiếng Việt có dấu, KHÔNG giải thích, KHÔNG thêm dấu câu."
            )),
            HumanMessage(content=query)
        ])
        # Loai bo markdown bold (**) va whitespace du thua
        return result.content.strip().replace("**", "")
    except Exception as e:
        # Neu rewrite fail (503, network, ...) -> fallback dung query goc, khong chan luong
        print(f"[Warn] Rewrite failed, fallback to raw query: {e}")
        return query


def invoke_rag_chain(query: str, history: list):
    """
    Tìm context liên quan trong DB và stream câu trả lời về HTTP.
    Cấu trúc format chèn chính xác Nguồn tham khảo phía cuối cùng.
    """
    # DEBUG: go "/test-overload" tu chat de trigger UI retry test
    if query.strip() == "/test-overload":
        print("[Debug] Forcing Gemini overload sentinel for UI test")
        yield GEMINI_OVERLOAD_SENTINEL
        return

    vector_store = get_vector_store()

    # 1. Query rewriting — chuyen cau hoi tu nhien thanh query phap ly
    t0 = time.time()
    search_query = rewrite_query(query)
    t1 = time.time()
    print(f"[Perf] Query rewrite: {t1-t0:.2f}s | '{query}' -> '{search_query}'")

    # 2. Retrieval — lay top-k ket qua
    docs = vector_store.similarity_search(search_query, k=10)
    t2 = time.time()
    print(f"[Perf] Vector search: {t2-t1:.2f}s | {len(docs)} docs found")

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

    # System Prompt — rut gon de giam input tokens, tang toc LLM first token
    # LUU Y: prompt phai viet tieng Viet CO DAU day du, neu khong LLM se copy lai khong dau vao output
    system_prompt = f"""Trợ lý tư vấn luật Việt Nam chính xác. CHỈ trả lời dựa trên dữ liệu bên dưới, KHÔNG bịa.
Suy luận ý định câu hỏi đời thường (VD: "con tôi 20 tuổi học ở đâu" = quy định độ tuổi, quyền học tập).
Nếu dữ liệu không liên quan → "Xin lỗi, hệ thống không có dữ liệu pháp lý liên quan."

Trả lời bằng tiếng Việt có dấu đầy đủ, chia 2 phần:
1. Lời tư vấn dễ hiểu, mạch lạc.
2. **Căn cứ pháp lý:** cuối câu trả lời. Mỗi nguồn 1 gạch đầu dòng (-).

QUY TẮC TRÍCH DẪN (BẮT BUỘC — đọc kỹ):
- Mỗi dòng trích dẫn PHẢI bắt đầu bằng tên luật/nghị định/thông tư đầy đủ kèm số hiệu (dấu /), rồi mới đến Chương, Điều, Khoản, Điểm.
- VD đúng: `- Luật Giáo dục 2019 (Luật số 43/2019/QH14), Điều 28, Khoản 1, Điểm a, Điểm b.`
- VD đúng (Thông tư): `- Thông tư 08/2021/TT-BGDĐT, Điều 5, Khoản 2.`
- VD đúng (cả Luật + Thông tư hướng dẫn) — mỗi văn bản 1 dòng:
  `- Luật Giáo dục 2019 (Luật số 43/2019/QH14), Điều 28.`
  `- Thông tư 08/2021/TT-BGDĐT, Điều 5, Khoản 2.`

CẤM TUYỆT ĐỐI:
- KHÔNG viết `Chương II, Điều 3, Khoản 3.` (thiếu tên văn bản) — VI PHẠM.
- KHÔNG copy nguyên văn `[Nguồn: ...]` — đó là nhãn nội bộ.
- KHÔNG viết placeholder trong dấu ngoặc vuông như `[Tên văn bản không xác định]`, `[Tên luật]`, `[...]` — DẤU NGOẶC VUÔNG KHÔNG ĐƯỢC XUẤT HIỆN trong phần Căn cứ pháp lý.
- KHÔNG ghi chú giải thích như "(không rõ nguồn)", "(chưa xác định)".
- KHÔNG bịa tên luật, số hiệu, điều khoản.

XỬ LÝ CHUNK THIẾU METADATA:
- Đọc NỘI DUNG chunk (thường đầu văn bản có tên luật) để tự trích xuất tên + số hiệu.
- Nếu vẫn KHÔNG xác định được tên văn bản → BỎ HẲN dòng đó, KHÔNG trích dẫn nửa vời, KHÔNG viết placeholder.
- Nếu TẤT CẢ chunk đều thiếu tên văn bản → bỏ luôn phần "Căn cứ pháp lý" thay vì viết nửa vời.

Dữ liệu pháp luật:
{context_str}"""

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

    # 4. Stream output — bat loi 503/qua tai -> yield sentinel cho frontend hien retry
    llm = build_llm()
    t3 = time.time()
    first_chunk = True
    try:
        for chunk in llm.stream(messages):
            if first_chunk:
                print(f"[Perf] LLM first token: {time.time()-t3:.2f}s | Total FTTB: {time.time()-t0:.2f}s")
                first_chunk = False
            yield chunk.content
    except Exception as e:
        print(f"[Error] LLM stream failed: {type(e).__name__}: {e}")
        # Neu chua co chu nao stream ra -> yield sentinel de frontend nhan biet va hien nut retry
        # Neu da stream 1 phan -> yield sentinel o cuoi, frontend van co the retry
        yield GEMINI_OVERLOAD_SENTINEL
