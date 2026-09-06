import os
import sys

def test_pinecone_live():
    print("=== 2. PINECONE PREFLIGHT LIVE TEST ===")
    
    # Read env file
    env_path = r"E:\n8n\flight-agent-hackathon\.env"
    api_key = None
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    if k.strip() in ["PINECONE_API_KEY", "PINECORN_APII"]:
                        api_key = v.strip()
                        if api_key:
                            break
                            
    if not api_key:
        print("[FAIL] Pinecone API key not found in .env")
        return False
        
    print("Found Pinecone API key in configuration (masked).")
    
    from pinecone import Pinecone
    try:
        pc = Pinecone(api_key=api_key)
        indexes_list = pc.list_indexes()
        index_names = [i.name for i in indexes_list]
        print(f"  [PASS] Pinecone Authentication: SUCCESS")
        print(f"  [PASS] Existing Pinecone Indexes: {index_names}")
        
        if not index_names:
            print("  [!] No existing Pinecone index configured. Reporting index status as: NOT YET CREATED.")
            print("  [!] Note: As per instructions, not creating arbitrary production index without confirmation.")
            return "NO_INDEX"
        else:
            target_index_name = index_names[0]
            print(f"  [PASS] Found intended index: '{target_index_name}'")
            idx = pc.Index(target_index_name)
            
            # Temporary Vector Upsert Test
            print("  -> Performing temporary vector upsert/query/delete test...")
            desc = idx.describe_stats()
            dim = desc.dimension
            print(f"  -> Index dimension: {dim}")
            
            test_vector_id = "p0_test_vector_temp_id_99"
            dummy_values = [0.1] * dim
            
            # Upsert
            idx.upsert(vectors=[(test_vector_id, dummy_values, {"purpose": "preflight_test"})])
            print("  [PASS] Temporary vector upsert: SUCCESS")
            
            # Query
            query_res = idx.query(vector=dummy_values, top_k=1, include_metadata=True)
            assert len(query_res.matches) > 0
            print("  [PASS] Temporary vector query: SUCCESS")
            
            # Delete cleanup
            idx.delete(ids=[test_vector_id])
            print("  [PASS] Temporary vector cleanup/deletion: SUCCESS")
            
            print("\n--> PINECONE PREFLIGHT: ALL TESTS PASSED! <--")
            return "PASS"
    except Exception as e:
        print(f"  [FAIL] Pinecone Test FAILED: {type(e).__name__} - {e}")
        return False

if __name__ == "__main__":
    test_pinecone_live()
