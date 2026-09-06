import psycopg2
import sys

def run_supabase_preflight():
    print("=== 1. AUTHORITATIVE SUPABASE POSTGRESQL PREFLIGHT SUITE ===")
    
    from dotenv import dotenv_values
    import os
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = dotenv_values(os.path.join(project_root, ".env"))
    
    host = env.get("POSTGRES_HOST") or "aws-0-ap-southeast-1.pooler.supabase.com"
    port = int(env.get("POSTGRES_PORT") or 5432)
    user = env.get("POSTGRES_USER") or "postgres.ewqzxwurcmdgnvoczeyz"
    dbname = env.get("POSTGRES_DB") or "postgres"
    password = env.get("POSTGRES_PASSWORD", "")
    
    try:
        # Connection 1 (FastAPI simulation)
        conn1 = psycopg2.connect(host=host, port=port, user=user, password=password, dbname=dbname, connect_timeout=10)
        cur1 = conn1.cursor()
        
        # Connection 2 (n8n simulation)
        conn2 = psycopg2.connect(host=host, port=port, user=user, password=password, dbname=dbname, connect_timeout=10)
        cur2 = conn2.cursor()
        
        print("  [PASS] FastAPI & n8n Dual Connection to Supabase: SUCCESS")
        
        # 1. SELECT 1
        cur1.execute("SELECT 1;")
        res1 = cur1.fetchone()[0]
        assert res1 == 1
        print("  [PASS] SELECT 1: SUCCESS")
        
        # 2. PostgreSQL Version
        cur1.execute("SELECT version();")
        ver = cur1.fetchone()[0]
        print(f"  [PASS] PostgreSQL Version: {ver}")
        assert "PostgreSQL" in ver
        
        # 3. Temp Table CRUD
        cur1.execute("CREATE TEMP TABLE supabase_p0_crud (id serial primary key, name text);")
        cur1.execute("INSERT INTO supabase_p0_crud (name) VALUES ('flight_test');")
        cur1.execute("SELECT name FROM supabase_p0_crud WHERE id = 1;")
        res_crud = cur1.fetchone()[0]
        assert res_crud == 'flight_test'
        cur1.execute("DROP TABLE supabase_p0_crud;")
        print("  [PASS] Temporary Table CRUD: SUCCESS")
        
        # 4. Transaction + ROLLBACK Test
        cur1.execute("CREATE TEMP TABLE supabase_tx_rollback (id int);")
        cur1.execute("INSERT INTO supabase_tx_rollback VALUES (999);")
        conn1.rollback()
        
        try:
            cur1.execute("SELECT * FROM supabase_tx_rollback;")
            print("  [FAIL] ROLLBACK Test: FAILED (table persisted after rollback)")
            return False
        except Exception:
            conn1.rollback()
            print("  [PASS] Transaction & ROLLBACK: SUCCESS")
            
        # 5. CHECK Constraint Rejection Test (negative seats) -> Error Code 23514
        cur1.execute("CREATE TEMP TABLE supabase_seats_check (seats int check (seats >= 0));")
        err_code = None
        try:
            cur1.execute("INSERT INTO supabase_seats_check (seats) VALUES (-10);")
            print("  [FAIL] CHECK Constraint Test: FAILED (did not raise exception)")
            return False
        except psycopg2.Error as ex:
            err_code = ex.pgcode
            conn1.rollback()
            if err_code == "23514":
                print("  [PASS] CHECK Constraint Rejection: SUCCESS (Error code 23514 check_violation verified!)")
            else:
                print(f"  [FAIL] CHECK Constraint Error Code: Expected 23514, got {err_code}")
                return False
                
        conn1.close()
        conn2.close()
        print("\n--> SUPABASE POSTGRESQL PREFLIGHT: ALL TESTS PASSED (100% VERIFIED)! <--")
        return True
    except Exception as e:
        print(f"  [FAIL] Supabase Test Execution Failed: {type(e).__name__} - {e}")
        return False

if __name__ == "__main__":
    run_supabase_preflight()
