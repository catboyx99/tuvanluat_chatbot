import os
import re
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter


def _normalize_type(t: str) -> str:
    """Chuan hoa TYPE: cac dau cach/underscore -> '-', merge dau '-' lien tiep, ND -> NĐ, QD -> QĐ."""
    t = re.sub(r"[\s_]+", "-", t.strip())
    t = re.sub(r"-+", "-", t)
    # Chuan hoa ASCII -> Unicode (file ascii dat ten "ND-CP" thay vi "NĐ-CP")
    t = t.replace("ND-CP", "NĐ-CP").replace("Nd-CP", "NĐ-CP")
    t = re.sub(r"^QD-", "QĐ-", t)
    t = re.sub(r"\bBGDDT\b", "BGDĐT", t)
    t = re.sub(r"\bBLDTBXH\b", "BLĐTBXH", t)
    return t


def _extract_so_hieu_from_filename(source_path: str) -> str:
    """Parse so hieu tu filename. Reliable hon text vi OCR thuong hong dong tieu de.
    Tra ve so hieu chuan format NN/YYYY/TYPE hoac NN/TYPE (QD khong co nam) hoac '' neu khong match.
    Vd:
      - 'Luật-43-2019-QH14.md' -> '43/2019/QH14'
      - 'Thông tư số 25-2021-TT-BGDĐT .md' -> '25/2021/TT-BGDĐT'
      - 'Quyết-định-2383-QĐ-BGDĐT.md' -> '2383/QĐ-BGDĐT'
      - '212_2025_ND-CP_666742.md' -> '212/2025/NĐ-CP'
      - '1134_QD-BGDDT_512062.md' -> '1134/QĐ-BGDĐT'
    """
    fname = os.path.basename(source_path).replace(".md", "").strip()

    # Pattern A: Luat/Nghi dinh/Thong tu/Nghi quyet co nam
    pat_a = re.compile(
        r"(?:Luật|Nghị[-\s]?định|Thông[-\s]?tư|Nghị[-\s]?quyết)"
        r"(?:\s+số)?[-\s_]+(\d{1,4})[-\s_]+(\d{4})[-\s_]+"
        r"(QH\d+|N[ĐD][-\s_]?CP|TT[-\s_][\w\-ĐD]+|NQ[-\s_][\w\-ĐD]+)",
        re.IGNORECASE,
    )
    m = pat_a.search(fname)
    if m:
        return f"{m.group(1)}/{m.group(2)}/{_normalize_type(m.group(3))}"

    # Pattern B: bat dau bang so - format <NN>_<YYYY>_<TYPE>... vd "21_2020_TT_BGDDT", "212_2025_ND-CP_666742"
    pat_b = re.compile(
        r"^(\d{1,4})[_-](\d{4})[_-]"
        r"(QH\d+|N[ĐD][-_]?CP|TT[_-][\w\-ĐD]+|NQ[_-][\w\-ĐD]+)",
        re.IGNORECASE,
    )
    m = pat_b.match(fname)
    if m:
        return f"{m.group(1)}/{m.group(2)}/{_normalize_type(m.group(3))}"

    # Pattern C: Quyet dinh khong co nam - "Quyết-định-2383-QĐ-BGDĐT" / "Quyết định 1596-QĐ-BGDĐT "
    pat_c = re.compile(
        r"(?:Quyết[-\s]?định)[-\s_]+(\d{1,5})[-\s_]+(Q[ĐD][-\s_][\w\-ĐD]+)",
        re.IGNORECASE,
    )
    m = pat_c.search(fname)
    if m:
        return f"{m.group(1)}/{_normalize_type(m.group(2))}"

    # Pattern D: file ascii bat dau bang so + QD - vd "1134_QD-BGDDT_512062", "4022_QD-BGDDT_637691"
    pat_d = re.compile(
        r"^(\d{1,5})[_-](Q[ĐD][_-][\w\-ĐD]+)",
        re.IGNORECASE,
    )
    m = pat_d.match(fname)
    if m:
        return f"{m.group(1)}/{_normalize_type(m.group(2))}"

    return ""


def _extract_so_hieu_from_text(head: str) -> str:
    """Fallback khi filename khong match pattern. Bo qua match nam sau 'Can cu' (vd 'Can cu Nghi dinh so 99/2019/ND-CP')."""
    type_alt = r"(?:QH\d+|N[ĐD][-\s]?CP|TT[-\s][\w\-ĐD]+|Q[ĐD][-\s][\w\-ĐD]+|NQ[-\s][\w\-ĐD]+|CT[-\s][\w\-ĐD]+)"
    so_hieu_pat = rf"[Ss]ố\s*:?\s*(\d+)\s*/\s*(\d{{4}})\s*/?\s*({type_alt})"
    for m in re.finditer(so_hieu_pat, head):
        start = max(0, m.start() - 80)
        prefix = head[start:m.start()].lower()
        # Bo qua neu trong 80 chars truoc co "can cu" (kem dau hoac khong)
        if "căn cứ" in prefix or "căn cú" in prefix or "can cu" in prefix:
            continue
        return f"{m.group(1)}/{m.group(2)}/{_normalize_type(m.group(3))}"
    return ""


def extract_document_metadata(raw_text: str, source_path: str = "") -> dict:
    """
    Trich so hieu + ngay ban hanh tu header van ban.
    - so_hieu: NN/YYYY/TYPE (VD "43/2019/QH14", "125/2024/NĐ-CP", "08/2021/TT-BGDĐT")
    - ngay_ban_hanh: dd/mm/yyyy (lay tu dong dia danh "Ha Noi, ngay..." o dau hoac cuoi van ban)

    Strategy so_hieu: filename TRUOC (reliable, OCR khong dung den), text fallback voi loai tru "Can cu".
    """
    meta = {}
    head = raw_text[:5000]
    tail = raw_text[-3000:]

    # --- So hieu: filename first, text fallback ---
    so_hieu = _extract_so_hieu_from_filename(source_path)
    if not so_hieu:
        so_hieu = _extract_so_hieu_from_text(head)
    if so_hieu:
        meta["so_hieu"] = so_hieu

    # --- Ngay ban hanh (priority order) ---
    # Uu tien 1: pattern dia danh "Ha Noi[,] ngay DD thang MM nam YYYY" (day la ngay ky ban hanh)
    # Uu tien 2: last match "ngay DD thang MM nam YYYY" trong 1500 ky tu cuoi (signature block)
    # Uu tien 3: "co hieu luc tu ngay..." (chi dung khi khong tim duoc ngay ban hanh)
    # Dau phay optional vi PDF OCR hay nuot.
    def _parse_date(match):
        try:
            dd, mm, yy = int(match.group(1)), int(match.group(2)), int(match.group(3))
            if 1 <= dd <= 31 and 1 <= mm <= 12 and 1900 <= yy <= 2100:
                return f"{dd:02d}/{mm:02d}/{yy}"
        except (ValueError, IndexError):
            pass
        return None

    date_pat_primary = (
        r"(?:Hà\s*Nội|Hà-Nội|TP\.?\s*Hồ\s*Chí\s*Minh|Hà\s*Nọi)"
        r"[\s,]*ng[àa]y\s*(\d{1,2})\s*th[áa]ng\s*(\d{1,2})\s*n[ăa]m\s*(\d{4})"
    )
    m = re.search(date_pat_primary, head + "\n" + tail)
    if m:
        d = _parse_date(m)
        if d:
            meta["ngay_ban_hanh"] = d

    if "ngay_ban_hanh" not in meta:
        # Last occurrence in tail — usually signature date
        matches = list(re.finditer(
            r"ng[àa]y\s*(\d{1,2})\s*th[áa]ng\s*(\d{1,2})\s*n[ăa]m\s*(\d{4})",
            raw_text[-1500:]
        ))
        if matches:
            d = _parse_date(matches[-1])
            if d:
                meta["ngay_ban_hanh"] = d

    if "ngay_ban_hanh" not in meta:
        # Fallback cuoi: "co hieu luc thi hanh tu ngay..."
        m = re.search(
            r"c[óo]\s+hi[ệe]u\s+l[ựu]c.{0,30}?ng[àa]y\s*(\d{1,2})\s*th[áa]ng\s*(\d{1,2})\s*n[ăa]m\s*(\d{4})",
            raw_text, re.IGNORECASE
        )
        if m:
            d = _parse_date(m)
            if d:
                meta["ngay_ban_hanh"] = d

    return meta


def strip_code_blocks(text):
    """
    Xoa code block markers (```text ... ```) va metadata thua tu file .md convert tu PDF.
    77/90 file .md co noi dung nam trong code block, khien MarkdownHeaderTextSplitter
    khong parse duoc header -> chunks thieu metadata -> vector search kem chinh xac.
    """
    # Xoa dong "Converted from PDF with per-page boundaries."
    text = re.sub(r"Converted from PDF with per-page boundaries\.?\n?", "", text)
    # Xoa header "## Page X" (metadata PDF, khong phai cau truc phap luat)
    text = re.sub(r"^##\s*Page\s+\d+\s*$", "", text, flags=re.MULTILINE)
    # Xoa code block markers: ```text va ``` (giu nguyen noi dung ben trong)
    text = re.sub(r"^```\w*\s*$", "", text, flags=re.MULTILINE)
    # Xoa dong tieu de trung voi ten file (VD: "# Luat-43-2019-QH14")
    # Chi xoa dong # dau tien neu noi dung giong ten file (khong chua noi dung luat)
    text = re.sub(r"^#\s+[\w\-\.]+\s*$", "", text, flags=re.MULTILINE)
    # Xoa so trang don le tu PDF (dong chi co 1-3 chu so, la page number)
    text = re.sub(r"^\d{1,3}\s*$", "", text, flags=re.MULTILINE)
    # Xoa watermark/footer thua tu PDF (VD: "Luallielnam Tien ich van ban |ual")
    text = re.sub(r"^Luallielnam.*$", "", text, flags=re.MULTILINE)
    # Xoa cac dong trong thua (nhieu dong trong lien tiep -> 1 dong trong)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def inject_markdown_headers(text):
    """
    Convert cau truc phap luat trong plain text thanh markdown headers.
    PDF convert ra text khong co headers -> MarkdownHeaderTextSplitter khong parse duoc.
    QUAN TRONG: Header chi chua ten ngan (VD: "Dieu 28"), noi dung xuong dong rieng.
    Neu de ca dong dai lam header, MarkdownHeaderTextSplitter nuot content vao metadata.
    """
    # Chen newline truoc "Điều X." de tach khoi dong truoc (PDF concat tat ca tren 1 dong)
    text = re.sub(
        r"(?<!\n)(?=(?:Điều|Đíều|Diều|Điêu)\s+\d+[\.\s])",
        "\n",
        text
    )
    # Chen newline truoc "Chương"
    text = re.sub(
        r"(?<!\n)(?=Chương\s+[IVXLCDM\d]+)",
        "\n",
        text
    )

    lines = text.split("\n")
    result = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            result.append("")
            continue

        # Pattern: LUẬT ... hoac NGHỊ ĐỊNH ... (tieu de van ban) -> # header
        if re.match(r"^(LUẬT|NGHỊ\s*ĐỊNH|THÔNG\s*TƯ|QUYẾT\s*ĐỊNH)\s+", stripped, re.IGNORECASE):
            if len(stripped) < 200:
                result.append("# " + stripped)
                continue

        # Pattern: Chương [so/roman] [tieu de] -> ## header ngan + content xuong dong
        m = re.match(r"^(Chương\s+[IVXLCDM\d]+)\s*(.*)", stripped)
        if m:
            header_part = m.group(1).strip()
            rest = m.group(2).strip()
            result.append("## " + header_part)
            if rest:
                result.append(rest)
            continue

        # Pattern: Mục [so]. [tieu de] -> ## header
        # Yeu cau dau cham sau so de tranh match nham OCR artifacts (VD: "Muc 7 tieu" = "Muc tieu")
        m = re.match(r"^(Mục\s+\d{1,2})\.\s*(.*)", stripped)
        if m and len(stripped) < 200:
            header_part = m.group(1).strip()
            rest = m.group(2).strip()
            result.append("## " + header_part)
            if rest:
                result.append(rest)
            continue

        # Pattern: Điều [so]. [noi dung] -> ### header ngan + content xuong dong
        m = re.match(r"^((?:Điều|Đíều|Diều|Điêu)\s+\d+)[\.\s]\s*(.*)", stripped)
        if m:
            header_part = m.group(1).strip()
            rest = m.group(2).strip()
            result.append("### " + header_part)
            if rest:
                result.append(rest)
            continue

        result.append(line)

    return "\n".join(result)


def load_and_split_markdown_documents(directory: str = "md_materials", only_files: list = None):
    """
    Quet file .md trong thu muc duoc chi dinh.
    Neu only_files duoc truyen vao, chi load cac file co ten trong danh sach do (dung cho incremental ingest).
    Strip code block markers truoc khi split.
    Cat noi dung dua theo cau truc Markdown Header (dai dien cho Luat -> Chuong -> Dieu -> Khoan).
    """
    full_dir = os.path.abspath(directory)
    if not os.path.exists(full_dir):
        print("[Loader] Directory %s not found. Creating empty dir." % full_dir)
        os.makedirs(full_dir, exist_ok=True)
        return []

    # Load raw markdown files
    if only_files:
        raw_documents = []
        for fname in only_files:
            fpath = os.path.join(full_dir, fname)
            if os.path.exists(fpath):
                loader = TextLoader(fpath, autodetect_encoding=True)
                raw_documents.extend(loader.load())
    else:
        loader = DirectoryLoader(full_dir, glob="**/*.md", loader_cls=TextLoader, loader_kwargs={'autodetect_encoding': True})
        raw_documents = loader.load()

    if not raw_documents:
        return []

    # Trich so hieu + ngay ban hanh TRUOC khi strip (vi strip co the xoa header PDF)
    for doc in raw_documents:
        src = doc.metadata.get("source", "")
        extracted = extract_document_metadata(doc.page_content, src)
        doc.metadata["so_hieu"] = extracted.get("so_hieu", "")
        doc.metadata["ngay_ban_hanh"] = extracted.get("ngay_ban_hanh", "")
        if not extracted.get("so_hieu"):
            print("[Loader] WARN: khong trich duoc so_hieu tu %s" % os.path.basename(src))
        if not extracted.get("ngay_ban_hanh"):
            print("[Loader] WARN: khong trich duoc ngay_ban_hanh tu %s" % os.path.basename(src))

    # Strip code block markers, metadata thua, roi inject markdown headers
    for doc in raw_documents:
        doc.page_content = strip_code_blocks(doc.page_content)
        doc.page_content = inject_markdown_headers(doc.page_content)

    # Text splitter cau hinh theo cap bac phap luat thong qua header Markdown
    headers_to_split_on = [
        ("#", "Luật/Nghị Định"),
        ("##", "Chương/Mục"),
        ("###", "Điều"),
        ("####", "Khoản")
    ]
    markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)

    md_header_splits = []
    for doc in raw_documents:
        splits = markdown_splitter.split_text(doc.page_content)
        for s in splits:
            if 'source' not in s.metadata:
                s.metadata['source'] = doc.metadata.get('source', 'Unknown file')
            # Propagate metadata so_hieu + ngay_ban_hanh (MarkdownHeaderTextSplitter khong tu copy)
            s.metadata['so_hieu'] = doc.metadata.get('so_hieu', '')
            s.metadata['ngay_ban_hanh'] = doc.metadata.get('ngay_ban_hanh', '')
        md_header_splits.extend(splits)

    # Cat bang Character Limit de han che token LLM
    char_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    final_splits = char_splitter.split_documents(md_header_splits)

    # Loc bo chunks qua ngan (< 15 ky tu) — thuong la so trang, ky tu rac tu PDF
    final_splits = [s for s in final_splits if len(s.page_content.strip()) >= 15]

    print("[Loader] Processed %d files -> %d chunks" % (len(raw_documents), len(final_splits)))
    return final_splits
