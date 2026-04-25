import os
import re
import time
import chromadb
from collections import OrderedDict
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
    # Model chinh: gemini-2.5-flash-lite. Profile 24/04: flash co 503 va first-token 40s
    # trong khi lite khong 503, avg first-token tuong duong. Giu lite de on dinh.
    global _llm_main
    if _llm_main is None:
        _llm_main = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash-lite",
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

# === Post-process citation block: dedupe theo so hieu, sap thu tu hieu luc, gop Dieu/Khoan/Diem ===
CITATION_MARKER = "**Căn cứ pháp lý"
CITE_LINE_RE = re.compile(
    r"^\s*[-*]\s*`?\s*(?P<name>.+?)\s*`?\s*\(\s*(?P<num>[^)]+?)\s*\)\s*,\s*"
    r"(?:ban\s+hành\s+ngày\s*(?P<date>\d{1,2}/\d{1,2}/\d{4})\s*,\s*)?"
    r"(?P<refs>.+?)\s*\.?\s*$"
)
# Fallback: dong "BUG 2" - thieu ten van ban, chi co "Luật số X/Y/Z, ban hành..., Điều..."
CITE_LINE_NONAME_RE = re.compile(
    r"^\s*[-*]\s*(?P<num>(?:luật\s*số|số\s*hiệu|số)\s+\S+?)\s*,\s*"
    r"(?:ban\s+hành\s+ngày\s*(?P<date>\d{1,2}/\d{1,2}/\d{4})\s*,\s*)?"
    r"(?P<refs>.+?)\s*\.?\s*$",
    re.IGNORECASE,
)
REF_TOKEN_RE = re.compile(r"(Điều|Khoản|Điểm|Chương|Mục)\s+([^\s,;]+)", re.IGNORECASE)


def _doc_level(name: str, num: str) -> int:
    n = name.lower()
    u = num.lower()
    if "luật sửa đổi" in n or "sửa đổi, bổ sung" in n:
        return 2
    if n.startswith("luật") or "/qh" in u:
        # /qh trong so hieu luat (vd 08/2012/QH13)
        return 2 if "sửa đổi" in n else 1
    if "nghị quyết" in n or "/nq-" in u:
        return 3
    if "nghị định" in n or "nđ-cp" in u or "/nd-" in u:
        return 4
    if "quyết định" in n or "/qđ-" in u or "/qd-" in u:
        return 5
    if "thông tư" in n or "/tt-" in u:
        return 6
    return 7


def _extract_year(num: str) -> int:
    # Vd "08/2012/QH13" -> 2012, "125/2024/NĐ-CP" -> 2024
    m = re.search(r"/(\d{4})/", num) or re.search(r"(\d{4})", num)
    return int(m.group(1)) if m else 0


def _parse_refs(s: str):
    return [(kind.capitalize(), val.rstrip(".,;)")) for kind, val in REF_TOKEN_RE.findall(s)]


def _merge_refs(struct: "OrderedDict", tokens):
    """struct: OrderedDict[Điều -> OrderedDict[Khoản -> list[Điểm]]]. Khoản="" khi khong co."""
    cur_dieu = None
    cur_khoan = None
    for kind, val in tokens:
        k = kind.lower()
        if k == "điều":
            cur_dieu = val
            struct.setdefault(cur_dieu, OrderedDict())
            cur_khoan = None
        elif k == "khoản":
            if cur_dieu is None:
                continue
            cur_khoan = val
            struct[cur_dieu].setdefault(cur_khoan, [])
        elif k == "điểm":
            if cur_dieu is None:
                continue
            if cur_khoan is None:
                cur_khoan = ""
                struct[cur_dieu].setdefault("", [])
            if val not in struct[cur_dieu][cur_khoan]:
                struct[cur_dieu][cur_khoan].append(val)
        # bo qua Chuong/Muc — khong dua vao trich dan cuoi


def _format_refs(struct: "OrderedDict") -> str:
    parts = []
    for dieu, khoan_map in struct.items():
        parts.append(f"Điều {dieu}")
        for khoan, diems in khoan_map.items():
            if khoan:
                parts.append(f"Khoản {khoan}")
            for diem in diems:
                parts.append(f"Điểm {diem}")
    return ", ".join(parts)


def fix_citation_block(text: str) -> str:
    """Parse citation block sau '**Căn cứ pháp lý:**' va viet lai chuan:
    - Dedupe theo so hieu (gop nhieu dong cua cung 1 van ban thanh 1 dong).
    - Sap theo thu bac hieu luc (Luat -> Luat sua doi -> NQ -> ND -> QD -> TT -> khac).
    - Trong cung 1 cap, sap theo nam giam dan.
    - Format paren: 'Luật số X' neu ten bat dau 'Luật', con lai 'Số X'.
    """
    lines = text.splitlines()
    head_idx = None
    for i, ln in enumerate(lines):
        if "Căn cứ pháp lý" in ln:
            head_idx = i
            break
    if head_idx is None:
        return text

    prefix = "\n".join(lines[:head_idx])
    head = lines[head_idx]
    body = lines[head_idx + 1:]

    docs = OrderedDict()  # key (so hieu chuan hoa) -> {name, num_core, date, struct}
    leftover_pre = []
    leftover_post = []
    seen_any = False
    for ln in body:
        if not ln.strip():
            if seen_any:
                continue
            else:
                leftover_pre.append(ln)
                continue
        m = CITE_LINE_RE.match(ln)
        m2 = None if m else CITE_LINE_NONAME_RE.match(ln)
        if not m and not m2:
            (leftover_post if seen_any else leftover_pre).append(ln)
            continue
        seen_any = True
        if m:
            name = m.group("name").strip().strip("`*").strip()
            num_raw = m.group("num").strip()
            date = (m.group("date") or "").strip()
            refs_str = m.group("refs").strip()
        else:
            # Khong co ten -> tam gan name=""; neu sau merge khong co dong nao bo sung ten thi BO
            name = ""
            num_raw = m2.group("num").strip()
            date = (m2.group("date") or "").strip()
            refs_str = m2.group("refs").strip()
        # Strip "Luật số" / "Số hiệu" / "Số" prefix de lay key chuan
        core = re.sub(r"^(?:luật\s*số|số\s*hiệu|số)\s*[:\s]*", "", num_raw, flags=re.I).strip()
        key = core.lower()
        if key not in docs:
            docs[key] = {"name": name, "core": core, "date": date, "struct": OrderedDict()}
        else:
            if not docs[key]["date"] and date:
                docs[key]["date"] = date
            # Giu ten dai hon (it co kha nang day du hon)
            if len(name) > len(docs[key]["name"]):
                docs[key]["name"] = name
        _merge_refs(docs[key]["struct"], _parse_refs(refs_str))

    # Bo cac doc thieu ten (BUG 2 khong duoc dong khac bo sung) — theo CLAUDE.md
    docs = OrderedDict((k, v) for k, v in docs.items() if v["name"])

    items = list(docs.items())
    items.sort(key=lambda kv: (_doc_level(kv[1]["name"], kv[1]["core"]), -_extract_year(kv[1]["core"])))

    out_lines = []
    if prefix:
        out_lines.append(prefix)
    out_lines.append(head)
    out_lines.extend(leftover_pre)
    for _, v in items:
        if v["name"].lower().startswith("luật"):
            paren = f"Luật số {v['core']}"
        else:
            paren = f"Số {v['core']}"
        line = f"- {v['name']} ({paren})"
        if v["date"]:
            line += f", ban hành ngày {v['date']}"
        refs_out = _format_refs(v["struct"])
        if refs_out:
            line += f", {refs_out}"
        line += "."
        out_lines.append(line)
    out_lines.extend(leftover_post)
    return "\n".join(out_lines)


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
        so_hieu = d.metadata.get("so_hieu", "")
        ngay_bh = d.metadata.get("ngay_ban_hanh", "")
        label_parts = [p for p in [law_name, chapter, article, clause] if p]
        label = " > ".join(label_parts) if label_parts else "Không rõ nguồn"
        # Dong meta chuan: so hieu + ngay ban hanh (lay tu regex extract luc ingest, CHINH XAC)
        meta_line = ""
        if so_hieu or ngay_bh:
            bits = []
            if so_hieu:
                bits.append(f"Số hiệu: {so_hieu}")
            if ngay_bh:
                bits.append(f"Ban hành: {ngay_bh}")
            meta_line = " | ".join(bits)
        header_line = f"[Nguồn: {label}]"
        if meta_line:
            header_line += f"\n[Meta: {meta_line}]"
        context_parts.append(f"{header_line}\n{d.page_content}")
    context_str = "\n\n---\n\n".join(context_parts)

    # System Prompt — rut gon de giam input tokens, tang toc LLM first token
    # LUU Y: prompt phai viet tieng Viet CO DAU day du, neu khong LLM se copy lai khong dau vao output
    system_prompt = f"""Trợ lý tư vấn luật Việt Nam chính xác.

CHỐNG BỊA (BẮT BUỘC — ƯU TIÊN CAO NHẤT):
- CHỈ trả lời dựa trên phần "Dữ liệu pháp luật" bên dưới. TUYỆT ĐỐI KHÔNG dùng kiến thức ngoài, KHÔNG dựa vào trí nhớ về luật Việt Nam.
- KHÔNG bịa tên văn bản, số hiệu, ngày ban hành, số Điều, số Khoản, số Điểm hoặc nội dung quy định không có trong dữ liệu.
- KHÔNG suy luận quy định từ "thông thường" hay "tương tự" nếu dữ liệu không nói rõ.
- Nếu dữ liệu HOÀN TOÀN không liên quan đến câu hỏi → trả lời đúng một câu: "Xin lỗi, hệ thống không có dữ liệu pháp lý liên quan." (không trích dẫn, không phần Căn cứ pháp lý).
- Nếu dữ liệu chỉ liên quan MỘT PHẦN → trả lời phần có dữ liệu, phần còn lại nói rõ "dữ liệu hiện có chưa đề cập", KHÔNG tự điền.

Suy luận ý định câu hỏi đời thường được phép (VD: "con tôi 20 tuổi học ở đâu" = quy định độ tuổi, quyền học tập) — nhưng câu trả lời vẫn PHẢI bám vào dữ liệu bên dưới.

Trả lời bằng tiếng Việt có dấu đầy đủ, chia 2 phần:
1. **Lời tư vấn ĐẦY ĐỦ và mạch lạc** — KHÔNG được rút gọn xuống còn 1-2 câu. Phải bao gồm: (a) trả lời trực tiếp câu hỏi, (b) liệt kê toàn bộ điều kiện/thẩm quyền/quy trình/đối tượng có trong dữ liệu, (c) chia mục rõ ràng nếu có nhiều nội dung (dùng heading **bold** hoặc bullet). Mục tiêu: người đọc nắm trọn bộ quy định mà không cần đọc Căn cứ pháp lý.
2. **Căn cứ pháp lý:** cuối câu trả lời. Mỗi nguồn 1 gạch đầu dòng (-).

QUY TẮC TRÍCH DẪN (BẮT BUỘC — đọc kỹ):
- Mỗi dòng trích dẫn PHẢI có ĐẦY ĐỦ 3 phần theo thứ tự: (1) tên văn bản đầy đủ lấy từ NỘI DUNG CÙNG CHUNK, (2) số hiệu trong `( )` lấy từ dòng `[Meta: ...]` CỦA CHÍNH CHUNK ĐÓ, (3) ngày ban hành lấy từ dòng `[Meta: ...]` CỦA CHÍNH CHUNK ĐÓ. Sau đó mới đến Chương, Điều, Khoản, Điểm.
- **QUY TẮC TRÓI BUỘC CHUNK**: Tên + số hiệu + ngày + Điều/Khoản PHẢI cùng đến từ MỘT chunk duy nhất. TUYỆT ĐỐI KHÔNG ghép tên từ chunk A với số hiệu/ngày từ chunk B. VD SAI: lấy "Luật sửa đổi, bổ sung..." từ chunk có số `34/2018/QH14`, rồi ghi số hiệu `08/2012/QH13` lấy từ chunk khác — 2 số hiệu khác nhau = 2 văn bản khác nhau, không được trộn.
- Số hiệu và ngày đã được trích sẵn ở dòng `[Meta: Số hiệu: N/Y/TYPE | Ban hành: dd/mm/yyyy]` — DÙNG NGUYÊN VĂN, KHÔNG suy luận, KHÔNG chuyển format.
- Tên văn bản (VD "Luật Giáo dục 2019", "Luật sửa đổi, bổ sung một số điều của Luật Giáo dục đại học") lấy từ nội dung chunk (tiêu đề LUẬT / NGHỊ ĐỊNH / THÔNG TƯ), KHÔNG từ nhãn `[Nguồn: ...]`.

**THỨ TỰ TRÌNH BÀY BẮT BUỘC** (sắp xếp từ cao xuống thấp theo hiệu lực pháp lý):
1. Luật (gốc) — xuất hiện ĐẦU TIÊN
2. Luật sửa đổi, bổ sung
3. Nghị quyết của Quốc hội / Ủy ban thường vụ
4. Nghị định (của Chính phủ)
5. Quyết định (của Thủ tướng / Bộ trưởng)
6. Thông tư (của Bộ / Liên Bộ)
7. Các văn bản khác (Công văn, Kế hoạch...)

Trong cùng 1 cấp, sắp theo năm ban hành mới → cũ. Nếu câu hỏi trực tiếp liên quan Luật Giáo dục / Luật Giáo dục đại học → dòng Luật đó PHẢI ở vị trí đầu tiên.

**FORMAT BẮT BUỘC cho MỖI dòng** (copy-paste chính xác cấu trúc này, KHÔNG được đảo thứ tự các thành phần):
`<TÊN VĂN BẢN ĐẦY ĐỦ> (<SỐ HIỆU>), ban hành ngày <DD/MM/YYYY>, Điều <số>, Khoản <số>, Điểm <chữ>.`

Dòng Căn cứ pháp lý CHỈ chứa thông tin định vị nguồn (tên + số hiệu + ngày + Điều/Khoản/Điểm). TUYỆT ĐỐI KHÔNG nhét nội dung quy định/trích nguyên văn vào dòng trích dẫn — nội dung quy định đã nói ở phần 1 (lời tư vấn) phía trên.

VD format hợp lệ (chỉ minh hoạ cấu trúc — KHÔNG phải nội dung mẫu để copy):
- `<TÊN LUẬT GỐC> (Luật số <NN/YYYY/QHxx>), ban hành ngày <DD/MM/YYYY>, Điều X, Khoản Y.`
- `<TÊN LUẬT SỬA ĐỔI> (Luật số <NN/YYYY/QHxx>), ban hành ngày <DD/MM/YYYY>, Điều X, Khoản Y.`
- `<TÊN NGHỊ ĐỊNH> (Số <NN/YYYY/NĐ-CP>), ban hành ngày <DD/MM/YYYY>, Điều X.`
- `<TÊN THÔNG TƯ> (Số <NN/YYYY/TT-CƠQUAN>), ban hành ngày <DD/MM/YYYY>, Điều X, Điểm a.`

VD SAI — BUG 1 (format đảo, nội dung quy định nhét vào trích dẫn):
`- <CÂU NỘI DUNG QUY ĐỊNH BỊ ĐẶT TRONG DÒNG TRÍCH DẪN>. (<số hiệu>, <ngày>, Điều X, Khoản Y)`
→ CẤM. Nội dung quy định phải nằm ở phần 1 (lời tư vấn). Dòng trích dẫn chỉ chứa định danh nguồn theo FORMAT BẮT BUỘC ở trên.

VD SAI — BUG 2 (thiếu tên văn bản, chỉ có "Luật số ..."):
`- <Loại> số <NN/YYYY/TYPE>, ban hành ngày <ngày>, Điều X, Khoản Y.`
→ CẤM. Bắt buộc có tên TRƯỚC paren: `- <TÊN VĂN BẢN ĐẦY ĐỦ> (<Loại> số <NN/YYYY/TYPE>), ban hành ngày <ngày>, Điều X, Khoản Y.`

VD SAI — BUG 3 (thứ tự đảo: văn bản cấp thấp đứng trước văn bản cấp cao):
```
- <Thông tư> ..., Điều X.
- <Nghị định> ..., Điều Y.
- <Luật> ..., Điều Z.
```
→ CẤM. Luật BẮT BUỘC đứng trên Nghị định, Nghị định BẮT BUỘC đứng trên Thông tư. Sửa lại theo thứ tự Luật → NĐ → TT.

VD SAI — BUG 4 (lặp cùng 1 văn bản ở 2 dòng khác nhau):
```
- <Văn bản A> (<Số hiệu A>) ..., Điều 1.
- <Văn bản A> (<Số hiệu A>) ..., Điều 3, Khoản 2.
```
→ CẤM lặp. Gộp 1 dòng duy nhất: `- <Văn bản A> (<Số hiệu A>), ban hành ngày ..., Điều 1, Điều 3, Khoản 2.`

CẤM TUYỆT ĐỐI (tổng hợp):
- KHÔNG ghép tên từ chunk này với số hiệu/ngày từ chunk khác (VD: tên "Luật sửa đổi" + số hiệu `08/2012/QH13` = SAI, vì `08/2012/QH13` là Luật gốc, không phải sửa đổi).
- KHÔNG viết trích dẫn thiếu tên văn bản hoặc thiếu số hiệu trong `( )` — VI PHẠM (xem BUG 2).
- KHÔNG đảo format: nội dung quy định ở ngoài, `(số hiệu, ngày, Điều)` trong ngoặc → CẤM (xem BUG 1). Luôn theo format `TÊN (SỐ HIỆU), ban hành ngày ..., Điều ...`.
- KHÔNG copy nguyên văn `[Nguồn: ...]` hay `[Meta: ...]` — đó là nhãn nội bộ.
- KHÔNG dùng placeholder `[...]`, KHÔNG ghi `(không rõ nguồn)`, `(chưa xác định)`.
- KHÔNG bịa số hiệu hoặc ngày tháng. Nếu dòng `[Meta: ...]` không có `Số hiệu` hoặc `Ban hành` → BỎ HẲN dòng đó.
- KHÔNG lặp cùng 1 văn bản ở 2 dòng khác nhau — gộp 1 dòng duy nhất (xem BUG 4).
- KHÔNG đảo thứ tự hiệu lực: Luật phải đứng TRƯỚC Nghị định/Thông tư trong mọi trường hợp (xem BUG 3).

XỬ LÝ CHUNK THIẾU METADATA:
- Nếu chunk KHÔNG có dòng `[Meta: ...]` (số hiệu/ngày không trích được khi ingest) → BỎ dòng trích dẫn đó, dùng chunk khác có `[Meta: ...]` đầy đủ.
- Nếu TẤT CẢ chunk đều thiếu `[Meta: ...]` → bỏ luôn phần "Căn cứ pháp lý".

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

    # 4. Stream output — auto retry 1 lan neu 503/UNAVAILABLE & chua stream byte nao.
    #    Sau 2 lan fail -> yield sentinel cho frontend hien nut retry thu cong.
    #    Phan loi tu van: stream bth (chi giu HOLD ky tu cuoi de phat hien marker bi cat).
    #    Phan Can cu phap ly: buffer toan bo, post-process bang fix_citation_block roi yield.
    llm = build_llm()
    max_attempts = 2
    HOLD = 80  # giu duoi pending de bat marker bi cat ngang giua cac chunk
    for attempt in range(max_attempts):
        t3 = time.time()
        first_chunk = True
        streamed_any = False
        pending = ""
        citation_buf = ""
        in_citation = False
        try:
            for chunk in llm.stream(messages):
                if first_chunk:
                    print(f"[Perf] LLM first token: {time.time()-t3:.2f}s | Total FTTB: {time.time()-t0:.2f}s (attempt {attempt+1})")
                    first_chunk = False
                text = chunk.content or ""
                if not text:
                    continue
                if in_citation:
                    citation_buf += text
                    streamed_any = True
                    continue
                pending += text
                idx = pending.find(CITATION_MARKER)
                if idx >= 0:
                    if idx > 0:
                        yield pending[:idx]
                        streamed_any = True
                    citation_buf = pending[idx:]
                    pending = ""
                    in_citation = True
                else:
                    if len(pending) > HOLD:
                        out = pending[:-HOLD]
                        pending = pending[-HOLD:]
                        yield out
                        streamed_any = True
            # Stream xong binh thuong: flush
            if in_citation:
                yield fix_citation_block(citation_buf)
            elif pending:
                yield pending
            return
        except Exception as e:
            err = str(e)
            is_503 = "503" in err or "UNAVAILABLE" in err
            if is_503 and not streamed_any and attempt < max_attempts - 1:
                print(f"[Retry] 503 on attempt {attempt+1}, backing off 2s")
                time.sleep(2)
                continue
            print(f"[Error] LLM stream failed: {type(e).__name__}: {e}")
            # Flush phan da co (neu co) truoc khi yield sentinel
            if in_citation and citation_buf:
                try:
                    yield fix_citation_block(citation_buf)
                except Exception:
                    yield citation_buf
            elif pending:
                yield pending
            yield GEMINI_OVERLOAD_SENTINEL
            return
