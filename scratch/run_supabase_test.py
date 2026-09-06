import os
import sys

def parse_env_file(filepath):
    env_vars = {}
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip()
    return env_vars

def test_supabase_pg():
    print("=== 1. SUPABASE POSTGRESQL PREFLIGHT TEST ===")
    
    env_path = r"E:\n8n\flight-agent-hackathon\.env"
    env_vars = parse_env_file(env_path)
    
    supabase_url = env_vars.get("SUPABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not supabase_url:
        print("[FAIL] SUPABASE_URL not found in .env or environment.")
        return False
        
    print("Found SUPABASE_URL in configuration. Connecting to Supabase Cloud PostgreSQL...")
    
    # Extract params safely to handle special chars in password
    # e.g. postgresql://postgres:w+jH*8AT?VjUP@?@db.ewqzxwurcmdgnvoczeyz.supabase.co:5432/postgres
    import psycopg2
    try:
        # Try raw DSN first
        try:
            conn = psycopg2.connect(dsn=supabase_url, connect_timeout=10)
        except Exception:
            # Fallback manual extraction
            host = "db.ewqzxwurcmdgnvoczeyz.supabase.co"
            port = 5432
            user = "postgres"
            dbname = "postgres"
            # Password extracted between postgres: and @db.
            prefix = "postgresql://postgres:"
            suffix = "@db.ewqzxwurcmdgnvoczeyz.supabase.co"
            if supabase_url.startswith(prefix) and suffix in supabase_url:
                password = supabase_url[len(prefix):supabase_url.rfind(suffix)]
            else:
                password = ""
            conn = psycopg2.connect(host=host, port=port, user=user, password=password, dbname=dbname, connect_timeout=10)
            
        cur = conn.cursor()
        
        # 1. SELECT 1
        cur.execute("SELECT 1;")
        res1 = cur.fetchone()[0]
        assert res1 == 1
        print("  [✓] SELECT 1: SUCCESS")
        
        # 2. PostgreSQL Version
        cur.execute("SELECT version();")
        ver = cur.fetchone()[0]
        print(f"  [✓] PostgreSQL Version: {ver[:65]}...")
        assert "PostgreSQL" in ver or "Supabase" in ver
        
        # 3. Temp Table CRUD
        cur.execute("CREATE TEMP TABLE supabase_p0_test (id serial primary key, val int check (val >= 0));")
        cur.execute("INSERT INTO supabase_p0_test (val) VALUES (100);")
        cur.execute("SELECT val FROM supabase_p0_test WHERE val = 100;")
        assert cur.fetchone()[0] == 100
        cur.execute("DROP TABLE supabase_p0_test;")
        print("  [✓] Temporary Table CRUD: SUCCESS")
        
        # 4. Transaction & ROLLBACK
        cur.execute("CREATE TEMP TABLE supabase_tx_test (id int);")
        cur.execute("INSERT INTO supabase_tx_test VALUES (777);")
        conn.rollback()
        
        # Verify rollback
        try:
            cur.execute("SELECT * FROM supabase_tx_test;")
            print("  [X] ROLLBACK Test: FAILED (table persisted after rollback)")
            return False
        except Exception:
            conn.rollback()
            print("  [✓] Transaction & ROLLBACK: SUCCESS")
            
        # 5. CHECK Constraint Rejection (Seats >= 0) -> Error 23514
        cur.execute("CREATE TEMP TABLE supabase_seats_check (seats int check (seats >= 0));")
        err_code = None
        try:
            cur.execute("INSERT INTO supabase_seats_check (seats) VALUES (-5);")
            print("  [X] CHECK Constraint: FAILED (did not raise exception)")
            return False
        except psycopg2.Error as ex:
            err_code = ex.pgcode
            conn.rollback()
            if err_code == "23514":
                print("  [✓] CHECK Constraint Rejection: SUCCESS (PostgreSQL Error 23514 check_violation verified)")
            else:
                print(f"  [X] CHECK Constraint Error Code: Received {err_code}, expected 23514")
                return False
                
        conn.close()
        print("\n--> SUPABASE POSTGRESQL PREFLIGHT: ALL TESTS PASSED! <--")
        return True
    except Exception as e:
        print(f"  [X] Supabase PostgreSQL Connection/Test FAILED: {type(e).__name__} - {e}")
        return False

if __name__ == "__main__":
    test_supabase_pg()
