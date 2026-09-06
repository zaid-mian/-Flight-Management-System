import psycopg2
import os

def validate_sql():
    print("=== VALIDATING PHASE 1 MIGRATION DDL SYNTAX ===")
    sql_path = r"E:\n8n\flight-agent-hackathon\migrations\001_initial_schema.sql"
    if not os.path.exists(sql_path):
        print(f"[FAIL] Migration file missing: {sql_path}")
        return False
        
    with open(sql_path, "r", encoding="utf-8") as f:
        sql_content = f.read()
        
    print(f"Loaded migration file: {sql_path} ({len(sql_content)} bytes)")
    
    # Connect to local test Postgres or Supabase to test DDL syntax in a transaction that is IMMEDIATELY ROLLED BACK
    try:
        conn = psycopg2.connect(host="127.0.0.1", port=8888, user="postgres", password=os.getenv("POSTGRES_PASSWORD", "postgres"), dbname="postgres")
        cur = conn.cursor()
        
        # Execute DDL statements in transaction
        cur.execute(sql_content)
        print("  [PASS] DDL SQL Syntax & Invariants Parsing: SUCCESSFUL!")
        
        # IMMEDIATELY ROLL BACK TO PRESERVE CLEAN DATABASE STATE
        conn.rollback()
        print("  [PASS] Transaction ROLLED BACK cleanly — zero production changes applied.")
        conn.close()
        return True
    except Exception as e:
        print(f"  [FAIL] DDL Validation Error: {type(e).__name__} - {e}")
        return False

if __name__ == "__main__":
    validate_sql()
