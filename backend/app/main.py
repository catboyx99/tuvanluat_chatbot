import os
import shutil

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from contextlib import asynccontextmanager

from .schemas import ChatRequest
from .rag_engine import invoke_rag_chain, ingest_docs_to_vector_store, get_vector_store
from .document_loader import load_and_split_markdown_documents

# Thư mục root chứa file .md nguồn (nơi user thêm file mới)
ROOT_MD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "md_materials"))
# Thư mục backend dùng để ingest vào ChromaDB
BACKEND_MD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "md_materials"))


def sync_new_md_files():
    """
    So sánh root md_materials/ với backend/md_materials/.
    Copy các file .md mới (chưa có trong backend) từ root sang backend.
    Trả về danh sách tên file mới đã copy.
    """
    if not os.path.exists(ROOT_MD_DIR):
        print(f"[Sync] Root md_materials not found: {ROOT_MD_DIR}")
        return []

    os.makedirs(BACKEND_MD_DIR, exist_ok=True)

    root_files = {f for f in os.listdir(ROOT_MD_DIR) if f.endswith(".md")}
    backend_files = {f for f in os.listdir(BACKEND_MD_DIR) if f.endswith(".md")}

    new_files = root_files - backend_files
    for f in new_files:
        src = os.path.join(ROOT_MD_DIR, f)
        dst = os.path.join(BACKEND_MD_DIR, f)
        shutil.copy2(src, dst)
        print(f"[Sync] Copied new file: {f}")

    return list(new_files)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup logic:
    1. Sync file .md mới từ root md_materials/ → backend/md_materials/
    2. Nếu ChromaDB trống → ingest toàn bộ
    3. Nếu có file mới → chỉ ingest file mới (incremental)
    """
    try:
        # Step 1: Sync new files from root -> backend
        new_files = sync_new_md_files()
        if new_files:
            print(f"[Startup] Found {len(new_files)} new file(s): {new_files}")
        else:
            print("[Startup] No new .md files from root md_materials/.")

        # Step 2: Check ChromaDB
        vs = get_vector_store()
        count = vs._collection.count()

        if count == 0:
            # DB empty -> ingest all
            print("[Startup] ChromaDB empty -- auto-ingesting all md_materials/...")
            docs = load_and_split_markdown_documents("md_materials")
            if docs:
                ingest_docs_to_vector_store(docs)
                print(f"[Startup] Auto-ingest done: {len(docs)} documents.")
            else:
                print("[Startup] No .md files found in md_materials/.")
        elif new_files:
            # DB has data + new files -> incremental ingest
            print(f"[Startup] ChromaDB has {count} docs -- incremental ingest {len(new_files)} new file(s)...")
            docs = load_and_split_markdown_documents("md_materials", only_files=new_files)
            if docs:
                ingest_docs_to_vector_store(docs)
                print(f"[Startup] Incremental ingest done: {len(docs)} docs from {len(new_files)} new file(s).")
        else:
            print(f"[Startup] ChromaDB has {count} docs, no new files -- skip ingest.")
    except Exception as e:
        print(f"[Startup] Auto-ingest error: {e}")
    yield


app = FastAPI(title="Law Consultant API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    """Kiểm tra đường truyền tới LLM và DB."""
    return {"status": "ok"}

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    """
    RAG Streaming endpoint.
    Trả về dữ liệu dạng chunk string để Vercel AI SDK Frontend vẽ lên UI thời gian thực.
    """
    if not req.query:
        raise HTTPException(status_code=400, detail="Query is empty")
    
    return StreamingResponse(
        invoke_rag_chain(req.query, req.history), 
        media_type="text/plain"
    )

@app.post("/api/ingest")
def ingest_documents():
    """
    Kích hoạt nạp lại markdown files vào ChromaDB mà không cần tắt Server.
    """
    # Đường dẫn relative được ánh xạ từ Docker volumes hoặc local mount
    docs = load_and_split_markdown_documents("md_materials")
    if not docs:
        return {"status": "no_docs_found"}
    
    success = ingest_docs_to_vector_store(docs)
    if success:
        return {"status": "ingested", "documents_processed": len(docs)}
    return {"status": "error"}
