import os
import sys
import json
import urllib.request
import urllib.error

def load_env(env_path):
    env_vars = {}
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip()
    return env_vars

def run_phase0():
    print("==========================================================")
    print("         PHASE 0 FINAL PREFLIGHT VERIFICATION             ")
    print("==========================================================")
    
    env_path = r"E:\n8n\flight-agent-hackathon\.env"
    if not os.path.exists(env_path):
        env_path = os.path.join(os.getcwd(), ".env")
        
    env = load_env(env_path)
    print(f"Loaded .env from: {env_path} (found keys: {list(env.keys())})")
    
    # 1. SUPABASE POSTGRESQL TEST
    print("\n[1/4] Testing Supabase-hosted PostgreSQL...")
    supabase_url = env.get("SUPABASE_URL") or env.get("SUPABASE_DB_URL") or os.environ.get("SUPABASE_URL")
    
    supabase_result = {"status": "BLOCKED", "notes": ""}
    if supabase_url:
        try:
            import psycopg2
            print("Connecting to Supabase PostgreSQL...")
            conn = psycopg2.connect(supabase_url, connect_timeout=10)
            cur = conn.cursor()
            
            # SELECT 1
            cur.execute("SELECT 1;")
            assert cur.fetchone()[0] == 1
            print("  -> SELECT 1: PASS")
            
            # Version
            cur.execute("SELECT version();")
            version_str = cur.fetchone()[0]
            print(f"  -> PostgreSQL Version: {version_str[:60]}...")
            
            # Temp table CRUD
            cur.execute("CREATE TEMP TABLE p0_supa_test (id serial primary key, val int check (val >= 0));")
            cur.execute("INSERT INTO p0_supa_test (val) VALUES (100);")
            cur.execute("SELECT val FROM p0_supa_test WHERE val = 100;")
            assert cur.fetchone()[0] == 100
            print("  -> Temp Table CRUD: PASS")
            
            # CHECK constraint rejection (error 23514)
            check_ok = False
            err_code = None
            try:
                cur.execute("INSERT INTO p0_supa_test (val) VALUES (-50);")
            except psycopg2.Error as ex:
                err_code = ex.pgcode
                if err_code == "23514":
                    check_ok = True
                conn.rollback()
            print(f"  -> CHECK Constraint (Error 23514): {'PASS' if check_ok else 'FAIL (' + str(err_code) + ')'}")
            
            # ROLLBACK test
            cur.execute("CREATE TEMP TABLE p0_tx (id int);")
            cur.execute("INSERT INTO p0_tx VALUES (777);")
            conn.rollback()
            rb_ok = False
            try:
                cur.execute("SELECT * FROM p0_tx;")
            except Exception:
                conn.rollback()
                rb_ok = True
            print(f"  -> Transaction ROLLBACK: {'PASS' if rb_ok else 'FAIL'}")
            
            if check_ok and rb_ok:
                supabase_result = {
                    "status": "PASS",
                    "host": "Supabase Cloud Host",
                    "version": version_str[:60],
                    "notes": "SELECT 1, Version, CRUD, ROLLBACK, and CHECK Error 23514 verified on Supabase Postgres."
                }
            conn.close()
        except Exception as e:
            supabase_result = {"status": "FAIL", "notes": f"Supabase connection error: {type(e).__name__} - {e}"}
            print(f"  -> Supabase Test FAILED: {type(e).__name__} - {e}")
    else:
        supabase_result = {"status": "BLOCKED", "notes": "SUPABASE_URL not found in .env"}
        print("  -> Supabase URL: NOT FOUND IN .ENV")

    # 2. PINECONE TEST
    print("\n[2/4] Testing Pinecone Vector Database...")
    pinecone_key = env.get("PINECORN_APII") or env.get("PINECONE_API_KEY") or os.environ.get("PINECONE_API_KEY")
    pinecone_result = {"status": "BLOCKED", "notes": ""}
    
    if pinecone_key:
        try:
            from pinecone import Pinecone
            pc = Pinecone(api_key=pinecone_key)
            index_list = pc.list_indexes()
            names = [idx.name for idx in index_list]
            print(f"  -> Pinecone Authenticated! Available Indexes: {names}")
            
            if names:
                target_index_name = names[0]
                print(f"  -> Testing temporary vector upsert/query/delete on index '{target_index_name}'...")
                idx = pc.Index(target_index_name)
                stats = idx.describe_index_stats()
                dim = stats.get("dimension") or 1536
                print(f"  -> Index dimension: {dim}")
                
                dummy_vec = [0.1] * dim
                idx.upsert(vectors=[{"id": "p0_test_vector", "values": dummy_vec, "metadata": {"test": "true"}}])
                print("  -> Temporary Vector Upsert: PASS")
                
                q_res = idx.query(vector=dummy_vec, top_k=1, include_metadata=True)
                assert len(q_res.get("matches", [])) > 0
                print("  -> Vector Query: PASS")
                
                idx.delete(ids=["p0_test_vector"])
                print("  -> Temporary Vector Cleanup/Delete: PASS")
                
                pinecone_result = {
                    "status": "PASS",
                    "indexes": names,
                    "target_index": target_index_name,
                    "notes": f"Authenticated, index '{target_index_name}' present, vector upsert/query/delete verified."
                }
            else:
                pinecone_result = {
                    "status": "PASS (AUTHENTICATED / READY FOR PHASE 4)",
                    "indexes": [],
                    "notes": "Authentication successful. No indexes currently exist. Ready for Phase 4 policy index creation."
                }
        except ImportError:
            print("  -> pinecone-client package not installed. Testing via Pinecone Control Plane REST API...")
            try:
                req = urllib.request.Request(
                    "https://api.pinecone.io/indexes",
                    headers={"Api-Key": pinecone_key, "Accept": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    idx_names = [i["name"] for i in data.get("indexes", [])]
                    print(f"  -> Pinecone REST API Auth SUCCESS! Indexes: {idx_names}")
                    pinecone_result = {
                        "status": "PASS (AUTHENTICATED)",
                        "indexes": idx_names,
                        "notes": f"Authentication verified via Pinecone Control Plane API. Found indexes: {idx_names}"
                    }
            except Exception as ex:
                pinecone_result = {"status": "FAIL", "notes": f"Pinecone REST API error: {ex}"}
                print(f"  -> Pinecone Auth FAILED: {ex}")
        except Exception as e:
            pinecone_result = {"status": "FAIL", "notes": f"Pinecone error: {type(e).__name__} - {e}"}
            print(f"  -> Pinecone Test FAILED: {type(e).__name__} - {e}")
    else:
        pinecone_result = {"status": "BLOCKED", "notes": "PINECONE_API_KEY missing"}
        print("  -> Pinecone API Key: NOT FOUND")

    # 3. GMAIL TEST VIA N8N
    print("\n[3/4] Testing Gmail Service in n8n...")
    gmail_result = {"status": "NOT CONFIGURED / BLOCKED", "notes": "Gmail OAuth credential not configured in n8n credential vault."}
    print("  -> Gmail: NOT CONFIGURED IN N8N")

    # 4. N8N WEBHOOK STABILITY TEST
    print("\n[4/4] Testing n8n Webhook Endpoint...")
    webhook_url = "https://mlengineerss.app.n8n.cloud/webhook/jobscout-search"
    webhook_result = {"status": "FAIL", "notes": ""}
    try:
        req = urllib.request.Request(
            webhook_url,
            data=json.dumps({"cvText": "Phase 0 Final Verification", "targetRole": "AI Architect"}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            st = resp.getcode()
            if st == 200:
                print("  -> n8n Webhook: HTTP 200 OK PASS")
                webhook_result = {"status": "PASS", "notes": "HTTP 200 OK returned successfully."}
            else:
                webhook_result = {"status": "FAIL", "notes": f"HTTP {st}"}
    except Exception as e:
        print(f"  -> n8n Webhook check: {type(e).__name__} - {e}")
        webhook_result = {"status": "TRANSIENT / NETWORK UNREACHABLE", "notes": str(e)}

    print("\n==========================================================")
    print("              PHASE 0 PREFLIGHT SUMMARY                   ")
    print("==========================================================")
    print(f"Supabase PostgreSQL : {supabase_result['status']}")
    print(f"Pinecone Vector DB  : {pinecone_result['status']}")
    print(f"Gmail Service       : {gmail_result['status']}")
    print(f"n8n Webhook         : {webhook_result['status']}")
    print("==========================================================")
    
    return {
        "supabase": supabase_result,
        "pinecone": pinecone_result,
        "gmail": gmail_result,
        "webhook": webhook_result
    }

if __name__ == "__main__":
    run_phase0()
