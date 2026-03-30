"""
Test Retrieval Coverage for ChromaDB
=====================================
Chay trong Docker: docker compose exec backend python /app/tests/test_retrieval_coverage.py
Hoac local (ChromaDB o localhost:8000): python tests/test_retrieval_coverage.py --local
"""

import os
import sys
import json
import time
from collections import Counter

# === CONFIG ===
CHROMA_HOST = os.environ.get("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.environ.get("CHROMA_PORT", "8000"))
COLLECTION_NAME = "law_database"
MD_DIR = os.environ.get("MD_DIR", "md_materials")

# Search quality test queries: (query, list of substrings expected in source or content)
SEARCH_QUERIES = [
    ("Quyen va nghia vu cua nguoi hoc theo Luat Giao duc", ["giao duc", "Giao duc", "giáo dục", "Giáo dục"]),
    ("Dieu kien thanh lap truong dai hoc", ["dai hoc", "đại học", "Dai hoc", "Đại học"]),
    ("Che do bao hiem xa hoi cho nguoi lao dong", ["bao hiem", "bảo hiểm", "lao dong", "lao động"]),
    ("Quy dinh ve quan ly su dung tai san cong", ["tai san", "tài sản", "công"]),
    ("Tuyen dung vien chuc nganh giao duc", ["vien chuc", "viên chức", "tuyen dung", "tuyển dụng"]),
    ("Xu phat vi pham hanh chinh trong linh vuc giao duc", ["xu phat", "xử phạt", "vi pham", "vi phạm"]),
    ("Chuong trinh giao duc mam non", ["mam non", "mầm non"]),
    ("Dao tao tien si quy che tuyen sinh", ["tien si", "tiến sĩ", "tuyen sinh", "tuyển sinh"]),
    ("Quy dinh ve khieu nai trong giao duc", ["khieu nai", "khiếu nại"]),
    ("Che do lam viec cua giang vien dai hoc", ["giang vien", "giảng viên", "lam viec", "làm việc"]),
]


def get_chroma_client():
    import chromadb
    client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
    return client


def test_source_coverage(collection, md_dir):
    """Test 1: Kiem tra moi file .md co it nhat 1 chunk trong ChromaDB."""
    print("\n" + "=" * 60)
    print("TEST 1: SOURCE COVERAGE")
    print("=" * 60)

    # Get all metadatas from ChromaDB
    result = collection.get(include=["metadatas"])
    metadatas = result["metadatas"]
    total_chunks = len(metadatas)
    print(f"Total chunks in ChromaDB: {total_chunks}")

    # Extract source basenames
    source_counter = Counter()
    empty_sources = 0
    unknown_sources = 0

    for meta in metadatas:
        src = meta.get("source", "")
        if not src:
            empty_sources += 1
            continue
        if src == "Unknown file":
            unknown_sources += 1
            continue
        basename = os.path.basename(src)
        source_counter[basename] += 1

    ingested_files = set(source_counter.keys())

    # Get files in md_materials folder
    if os.path.exists(md_dir):
        folder_files = {f for f in os.listdir(md_dir) if f.endswith(".md")}
    else:
        print(f"  WARNING: {md_dir} not found, skipping folder comparison")
        folder_files = set()

    # Compare
    missing_files = folder_files - ingested_files
    extra_files = ingested_files - folder_files  # in DB but not in folder (deleted?)

    print(f"\nFiles in folder: {len(folder_files)}")
    print(f"Files in ChromaDB: {len(ingested_files)}")
    print(f"Empty source metadata: {empty_sources}")
    print(f"Unknown file source: {unknown_sources}")

    if missing_files:
        print(f"\n  FAIL: {len(missing_files)} file(s) NOT found in ChromaDB:")
        for f in sorted(missing_files):
            print(f"    - {f}")
    else:
        print(f"\n  PASS: All {len(folder_files)} files have chunks in ChromaDB")

    if extra_files:
        print(f"\n  INFO: {len(extra_files)} file(s) in DB but not in folder:")
        for f in sorted(extra_files):
            print(f"    - {f} ({source_counter[f]} chunks)")

    # Show chunk distribution (top 10 largest, top 10 smallest)
    sorted_sources = sorted(source_counter.items(), key=lambda x: x[1], reverse=True)
    print(f"\nTop 10 files by chunk count:")
    for name, count in sorted_sources[:10]:
        print(f"  {count:>5} chunks | {name}")

    print(f"\nBottom 10 files by chunk count:")
    for name, count in sorted_sources[-10:]:
        print(f"  {count:>5} chunks | {name}")

    passed = len(missing_files) == 0 and empty_sources == 0 and unknown_sources == 0
    return passed, total_chunks, source_counter


def test_metadata_integrity(collection, metadatas=None):
    """Test 2: Kiem tra metadata keys duoc populate dung."""
    print("\n" + "=" * 60)
    print("TEST 2: METADATA INTEGRITY")
    print("=" * 60)

    if metadatas is None:
        result = collection.get(include=["metadatas"])
        metadatas = result["metadatas"]

    total = len(metadatas)
    keys_to_check = ["source", "Luật/Nghị Định", "Chương/Mục", "Điều", "Khoản"]
    key_counts = {k: 0 for k in keys_to_check}
    key_empty = {k: 0 for k in keys_to_check}

    law_names = Counter()

    for meta in metadatas:
        for k in keys_to_check:
            val = meta.get(k, "")
            if val:
                key_counts[k] += 1
                if k == "Luật/Nghị Định":
                    law_names[val] += 1
            else:
                if k in meta:
                    key_empty[k] += 1

    print(f"\nMetadata key population ({total} chunks):")
    print(f"  {'Key':<20} {'Present':>8} {'%':>7} {'Empty val':>10}")
    print(f"  {'-'*20} {'-'*8} {'-'*7} {'-'*10}")

    all_pass = True
    for k in keys_to_check:
        pct = key_counts[k] / total * 100 if total > 0 else 0
        status = "OK" if (k == "source" and pct == 100) or (k != "source") else "FAIL"
        if k == "source" and pct < 100:
            all_pass = False
        print(f"  {k:<20} {key_counts[k]:>8} {pct:>6.1f}% {key_empty[k]:>10}  {status}")

    # Show top law names for sanity check
    print(f"\nTop 15 'Luat/Nghi Dinh' values:")
    for name, count in law_names.most_common(15):
        # Truncate long names
        display = name[:70] + "..." if len(name) > 70 else name
        print(f"  {count:>5} chunks | {display}")

    luat_pct = key_counts["Luật/Nghị Định"] / total * 100 if total > 0 else 0
    if luat_pct < 80:
        print(f"\n  WARNING: Only {luat_pct:.1f}% chunks have 'Luat/Nghi Dinh' (expected >= 80%)")
    else:
        print(f"\n  PASS: {luat_pct:.1f}% chunks have 'Luat/Nghi Dinh'")

    return all_pass


def test_search_quality(collection):
    """Test 3: Kiem tra similarity_search tra ket qua dung nguon."""
    print("\n" + "=" * 60)
    print("TEST 3: SEARCH QUALITY (requires GEMINI_API_KEY)")
    print("=" * 60)

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("  SKIP: No GEMINI_API_KEY found. Set env var to run this test.")
        return None

    try:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        from langchain_chroma import Chroma
        import chromadb
    except ImportError as e:
        print(f"  SKIP: Missing dependency: {e}")
        return None

    # Build vector store with embedding
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
    client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
    vs = Chroma(client=client, collection_name=COLLECTION_NAME, embedding_function=embeddings)

    passed = 0
    failed = 0

    for i, (query, expected_keywords) in enumerate(SEARCH_QUERIES, 1):
        try:
            t0 = time.perf_counter()
            docs = vs.similarity_search(query, k=5)
            elapsed_ms = (time.perf_counter() - t0) * 1000
        except Exception as e:
            print(f"  Query {i}: ERROR - {e}")
            failed += 1
            continue

        if not docs:
            print(f"  Query {i}: FAIL - 0 results | {elapsed_ms:.0f}ms")
            failed += 1
            continue

        # Check if any doc content or metadata contains expected keywords
        found = False
        for d in docs:
            text = (d.page_content + " " + json.dumps(d.metadata, ensure_ascii=False)).lower()
            for kw in expected_keywords:
                if kw.lower() in text:
                    found = True
                    break
            if found:
                break

        status = "PASS" if found else "FAIL"
        if found:
            passed += 1
        else:
            failed += 1

        # Show first result source for debugging
        first_source = os.path.basename(docs[0].metadata.get("source", "?"))
        first_law = docs[0].metadata.get("Luật/Nghị Định", "?")
        print(f"  Query {i}: {status} | {elapsed_ms:.0f}ms | top-1 source: {first_source}")
        print(f"           query: {query[:50]}...")
        if not found:
            print(f"           expected keywords: {expected_keywords}")
            print(f"           top-1 law: {first_law}")

    total = passed + failed
    print(f"\nSearch quality: {passed}/{total} queries passed")
    return passed >= 10  # Threshold: 10/10 (all queries must pass)


def main():
    print("=" * 60)
    print("RETRIEVAL COVERAGE TEST SUITE")
    print(f"ChromaDB: {CHROMA_HOST}:{CHROMA_PORT}")
    print(f"Collection: {COLLECTION_NAME}")
    print(f"MD dir: {MD_DIR}")
    print("=" * 60)

    # Connect to ChromaDB
    try:
        client = get_chroma_client()
        collection = client.get_collection(COLLECTION_NAME)
        print(f"Connected. Collection '{COLLECTION_NAME}' has {collection.count()} chunks.")
    except Exception as e:
        print(f"FATAL: Cannot connect to ChromaDB at {CHROMA_HOST}:{CHROMA_PORT}")
        print(f"  Error: {e}")
        print(f"  Make sure 'docker compose up -d' is running.")
        sys.exit(1)

    # Run tests
    t1_pass, total_chunks, source_counter = test_source_coverage(collection, MD_DIR)
    t2_pass = test_metadata_integrity(collection)
    t3_pass = test_search_quality(collection)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Test 1 (Source Coverage):     {'PASS' if t1_pass else 'FAIL'}")
    print(f"  Test 2 (Metadata Integrity):  {'PASS' if t2_pass else 'FAIL'}")
    print(f"  Test 3 (Search Quality):      {'PASS' if t3_pass else 'SKIP' if t3_pass is None else 'FAIL'}")

    if t1_pass and t2_pass and (t3_pass is None or t3_pass):
        print("\n  Overall: ALL TESTS PASSED")
        sys.exit(0)
    else:
        print("\n  Overall: SOME TESTS FAILED")
        sys.exit(1)


if __name__ == "__main__":
    # Handle --local flag (default: use env vars)
    if "--local" in sys.argv:
        CHROMA_HOST = "localhost"
        # Try loading .env from project root
        try:
            from dotenv import load_dotenv
            root_env = os.path.join(os.path.dirname(__file__), "..", ".env")
            load_dotenv(root_env)
        except ImportError:
            pass

    main()
