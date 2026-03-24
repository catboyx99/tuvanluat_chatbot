import os
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

def load_and_split_markdown_documents(directory: str = "md_materials", only_files: list = None):
    """
    Quét file .md trong thư mục được chỉ định.
    Nếu only_files được truyền vào, chỉ load các file có tên trong danh sách đó (dùng cho incremental ingest).
    Cắt nội dung dựa theo cấu trúc Markdown Header (đại diện cho Luật -> Chương -> Điều -> Khoản).
    """
    full_dir = os.path.abspath(directory)
    if not os.path.exists(full_dir):
        print(f"Thư mục {full_dir} không tồn tại. Tự động tạo thư mục rỗng.")
        os.makedirs(full_dir, exist_ok=True)
        return []

    # Load raw markdown files — nếu có only_files thì chỉ load các file chỉ định
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
    
    # Text splitter cấu hình theo cấp bậc pháp luật thông qua header HTML
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
                # Đưa cả đường dẫn file gốc vào metadata làm nguồn trích dẫn
                s.metadata['source'] = doc.metadata.get('source', 'Unknown file')
        md_header_splits.extend(splits)
        
    # Tiếp tục cắt bằng Character Limit để hạn chế token LLM
    char_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    final_splits = char_splitter.split_documents(md_header_splits)
    
    return final_splits
