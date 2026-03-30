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

def rewrite_query(query: str) -> str:
    """Them dau tieng Viet vao cau hoi, giu nguyen y dinh goc de vector search chinh xac hon."""
    llm = build_rewrite_llm()
    result = llm.invoke([
        SystemMessage(content="Them dau tieng Viet vao cau hoi sau, giu nguyen nghia goc. Chi tra ve cau da them dau."),
        HumanMessage(content=query)
    ])
    # Loai bo markdown bold (**) neu co
    return result.content.strip().replace("**", "")


def invoke_rag_chain(query: str, history: list):
    """
    Tìm context liên quan trong DB và stream câu trả lời về HTTP.
    Cấu trúc format chèn chính xác Nguồn tham khảo phía cuối cùng.
    """
    vector_store = get_vector_store()

    # 1. Query rewriting — chuyen cau hoi tu nhien thanh query phap ly
    t0 = time.time()
    search_query = rewrite_query(query)
    t1 = time.time()
    print(f"[Perf] Query rewrite: {t1-t0:.2f}s | '{query}' -> '{search_query}'")

    # 2. Retrieval — lay top-k ket qua
    docs = vector_store.similarity_search(search_query, k=5)
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
    system_prompt = f"""Tro ly tu van luat Viet Nam chinh xac. CHI tra loi dua tren du lieu ben duoi, KHONG bia.
Suy luan y dinh cau hoi doi thuong (VD: "con toi 20 tuoi hoc o dau" = quy dinh do tuoi, quyen hoc tap).
Neu du lieu khong lien quan -> "Xin loi, he thong khong co du lieu phap ly lien quan."

Tra loi 2 phan:
1. Loi tu van de hieu, mach lac.
2. **Can cu phap ly:** cuoi cau tra loi. Moi nguon 1 gach dau dong (-).
   Format: Ten luat day du (So hieu dung dau /), Dieu X, Khoan Y, Diem Z.
   VD: - Luat Giao duc 2019 (Luat so 43/2019/QH14), Dieu 28, Khoan 1, Diem a, Diem b.
   Ten luat lay tu NOI DUNG van ban, KHONG dung ten file. KHONG bia dieu khoan.

Du lieu phap luat:
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

    # 4. Stream output
    llm = build_llm()
    t3 = time.time()
    first_chunk = True
    for chunk in llm.stream(messages):
        if first_chunk:
            print(f"[Perf] LLM first token: {time.time()-t3:.2f}s | Total FTTB: {time.time()-t0:.2f}s")
            first_chunk = False
        yield chunk.content
