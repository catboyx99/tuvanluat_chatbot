import os
import re
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter


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
        md_header_splits.extend(splits)

    # Cat bang Character Limit de han che token LLM
    char_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    final_splits = char_splitter.split_documents(md_header_splits)

    # Loc bo chunks qua ngan (< 15 ky tu) — thuong la so trang, ky tu rac tu PDF
    final_splits = [s for s in final_splits if len(s.page_content.strip()) >= 15]

    print("[Loader] Processed %d files -> %d chunks" % (len(raw_documents), len(final_splits)))
    return final_splits
