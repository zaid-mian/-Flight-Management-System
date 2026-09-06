import os
import sys
import glob
import time
from dotenv import dotenv_values
from pinecone import Pinecone, ServerlessSpec
from sentence_transformers import SentenceTransformer

# Project root setup
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")
POLICIES_DIR = os.path.join(PROJECT_ROOT, "data", "policies")

INDEX_NAME = "flight-policies"
MODEL_NAME = "all-MiniLM-L6-v2"
DIMENSION = 384

def get_pinecone_client():
    env = dotenv_values(ENV_PATH)
    api_key = env.get("PINECONE_API_KEY") or env.get("PINECORN_APII")
    if not api_key:
        raise ValueError("PINECONE_API_KEY missing from .env")
    return Pinecone(api_key=api_key)

def ensure_index_exists(pc: Pinecone):
    indexes = [i.name for i in pc.list_indexes()]
    if INDEX_NAME not in indexes:
        print(f"Creating Pinecone serverless index '{INDEX_NAME}' (dim={DIMENSION})...")
        pc.create_index(
            name=INDEX_NAME,
            dimension=DIMENSION,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1")
        )
        while INDEX_NAME not in [i.name for i in pc.list_indexes()]:
            time.sleep(1)
        print(f"Index '{INDEX_NAME}' created successfully.")

def chunk_markdown_file(file_path: str):
    basename = os.path.basename(file_path)
    category = basename.replace("_policy.md", "").replace(".md", "")
    
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    sections = content.split("\n## ")
    doc_title = sections[0].strip() if len(sections) > 0 else basename
    
    chunks = []
    chunk_index = 0
    
    for i, sec in enumerate(sections):
        sec_text = sec.strip()
        if not sec_text:
            continue
        if i > 0:
            sec_text = "## " + sec_text
            
        full_text = f"Document: {doc_title}\nCategory: {category}\n\n{sec_text}"
        chunk_id = f"{category}_chunk_{chunk_index}"
        
        chunks.append({
            "id": chunk_id,
            "text": full_text,
            "metadata": {
                "source": basename,
                "category": category,
                "chunk_id": chunk_id,
                "text": full_text,
                "version": "2026.1"
            }
        })
        chunk_index += 1
        
    return chunks

def ingest_policies():
    print("=== Task 4.1: Pinecone Policy Document Ingestion ===")
    pc = get_pinecone_client()
    ensure_index_exists(pc)
    
    index = pc.Index(INDEX_NAME)
    
    print(f"Loading embedding model '{MODEL_NAME}'...")
    embedder = SentenceTransformer(MODEL_NAME)
    
    policy_files = glob.glob(os.path.join(POLICIES_DIR, "*.md"))
    print(f"Found {len(policy_files)} policy files in {POLICIES_DIR}")
    
    all_chunks = []
    for pf in policy_files:
        chunks = chunk_markdown_file(pf)
        all_chunks.extend(chunks)
        print(f"  - {os.path.basename(pf)}: {len(chunks)} chunks")
        
    print(f"Total chunks created: {len(all_chunks)}")
    
    vectors_to_upsert = []
    for chunk in all_chunks:
        vector = embedder.encode(chunk["text"]).tolist()
        vectors_to_upsert.append((chunk["id"], vector, chunk["metadata"]))
        
    print(f"Upserting {len(vectors_to_upsert)} vectors into Pinecone index '{INDEX_NAME}'...")
    index.upsert(vectors=vectors_to_upsert)
    
    time.sleep(2)
    stats = index.describe_index_stats()
    print(f"[PASS] Vector Ingestion Complete!")
    print(f"  - Total vector count: {stats.total_vector_count}")
    
    # Verification query
    test_query = "What is the refund eligibility if I cancel 30 hours before departure?"
    print(f"\n--- Running Verification Retrieval Query ---")
    print(f"Query: '{test_query}'")
    query_vector = embedder.encode(test_query).tolist()
    results = index.query(vector=query_vector, top_k=2, include_metadata=True)
    
    print(f"Top Matched Policy Chunks ({len(results.matches)}):")
    for match in results.matches:
        print(f"  - [Score: {match.score:.4f}] ID: {match.id} | Source: {match.metadata['source']}")
        print(f"    Snippet: {match.metadata['text'][:150]}...\n")
        
    return True

if __name__ == "__main__":
    ingest_policies()
