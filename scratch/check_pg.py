import socket
import os
import sys

def check_postgres():
    print("=== POSTGRES PREFLIGHT CHECK ===")
    
    # Check env vars
    pg_url = os.environ.get("POSTGRES_URL") or os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    print(f"Env POSTGRES_URL / DATABASE_URL: {'FOUND' if pg_url else 'NOT SET IN ENV'}")
    
    # Check port 5432 on localhost
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)
    try:
        result = s.connect_ex(('localhost', 5432))
        if result == 0:
            print("Localhost:5432 is OPEN and listening (Local Postgres/Supabase running).")
        else:
            print(f"Localhost:5432 connection result: {result} (Closed/Not listening).")
    except Exception as e:
        print(f"Error checking localhost:5432: {e}")
    finally:
        s.close()

if __name__ == "__main__":
    check_postgres()
