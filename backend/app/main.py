import os
import time

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from contextlib import asynccontextmanager

from .schemas import ChatRequest
from .rag_engine import invoke_rag_chain, ingest_docs_to_vector_store, get_vector_store
from .document_loader import load_and_split_markdown_documents

# Thu muc chua file .md (Docker mount hoac local dev)
MD_DIR = os.environ.get("MD_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "md_materials")))


def wait_for_chroma(max_retries=30, delay=2):
    """Doi ChromaDB server san sang truoc khi tiep tuc."""
    for i in range(max_retries):
        try:
            vs = get_vector_store()
            vs._collection.count()
            print(f"[Startup] ChromaDB connected.")
            return vs
        except Exception:
            print(f"[Startup] Waiting for ChromaDB... ({i + 1}/{max_retries})")
            time.sleep(delay)
    raise RuntimeError("ChromaDB not available")


def get_ingested_sources(vs):
    """Lay danh sach ten file .md da duoc ingest trong ChromaDB."""
    result = vs._collection.get(include=["metadatas"])
    sources = set()
    for meta in result["metadatas"]:
        src = meta.get("source", "")
        sources.add(os.path.basename(src))
    return sources


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup logic:
    1. Neu ChromaDB rong -> ingest toan bo md_materials/
    2. Neu co file .md moi (chua co trong DB) -> incremental ingest
    3. Neu khong co gi moi -> skip
    """
    try:
        vs = wait_for_chroma()
        count = vs._collection.count()

        if count == 0:
            print(f"[Startup] ChromaDB empty -- auto-ingesting all from {MD_DIR}...")
            docs = load_and_split_markdown_documents(MD_DIR)
            if docs:
                ingest_docs_to_vector_store(docs)
                print(f"[Startup] Auto-ingest done: {len(docs)} documents.")
            else:
                print(f"[Startup] No .md files found in {MD_DIR}.")
        else:
            # So sanh file trong folder vs file da ingest trong ChromaDB
            if os.path.exists(MD_DIR):
                folder_files = {f for f in os.listdir(MD_DIR) if f.endswith(".md")}
            else:
                folder_files = set()
            ingested_files = get_ingested_sources(vs)
            new_files = folder_files - ingested_files

            if new_files:
                print(f"[Startup] ChromaDB has {count} docs -- incremental ingest {len(new_files)} new file(s): {list(new_files)}")
                docs = load_and_split_markdown_documents(MD_DIR, only_files=list(new_files))
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
    docs = load_and_split_markdown_documents(MD_DIR)
    if not docs:
        return {"status": "no_docs_found"}
    
    success = ingest_docs_to_vector_store(docs)
    if success:
        return {"status": "ingested", "documents_processed": len(docs)}
    return {"status": "error"}
