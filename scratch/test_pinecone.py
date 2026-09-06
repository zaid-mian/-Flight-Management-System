import os
import sys
import json
import urllib.request
import urllib.error

def test_pinecone():
    print("=== PINECONE PREFLIGHT VERIFICATION ===")
    api_key = os.environ.get("PINECONE_API_KEY")
    index_host = os.environ.get("PINECONE_HOST") or os.environ.get("PINECONE_INDEX_HOST")
    
    print(f"PINECONE_API_KEY in env: {'FOUND' if api_key else 'NOT IN ENV'}")
    print(f"PINECONE_HOST in env: {'FOUND' if index_host else 'NOT IN ENV'}")
    
    try:
        from pinecone import Pinecone
        print("pinecone-client Python library: INSTALLED")
        if api_key:
            pc = Pinecone(api_key=api_key)
            indexes = pc.list_indexes()
            print(f"Pinecone Indexes: {[i.name for i in indexes]}")
            return True
        else:
            print("[BLOCKED] PINECONE_API_KEY environment variable is missing.")
            return False
    except ImportError:
        print("pinecone-client Python library: NOT INSTALLED")
        if not api_key:
            print("[BLOCKED] PINECONE_API_KEY is missing and pinecone-client is not installed.")
            return False
        return False
    except Exception as e:
        print(f"[FAIL] Pinecone check error: {type(e).__name__} - {e}")
        return False

if __name__ == "__main__":
    test_pinecone()
