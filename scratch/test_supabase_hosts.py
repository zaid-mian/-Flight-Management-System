import socket
import psycopg2

def test_hosts():
    print("=== TESTING SUPABASE POOLERS & HOSTS ===")
    
    # Try project ref ewqzxwurcmdgnvoczeyz
    ref = "ewqzxwurcmdgnvoczeyz"
    passw = "w+jH*8AT?VjUP@?"
    
    hosts_to_try = [
        f"db.{ref}.supabase.co",
        f"aws-0-us-east-1.pooler.supabase.com",
        f"aws-0-us-west-1.pooler.supabase.com",
        f"aws-0-eu-central-1.pooler.supabase.com",
        f"aws-0-ap-southeast-1.pooler.supabase.com",
        f"aws-0-ap-south-1.pooler.supabase.com"
    ]
    
    for h in hosts_to_try:
        try:
            ip = socket.gethostbyname(h)
            print(f"Host '{h}' resolved to {ip}")
            # Try connecting on port 5432 and 6543
            for port in [5432, 6543]:
                try:
                    # User format for pooler: postgres.ewqzxwurcmdgnvoczeyz or postgres
                    user = f"postgres.{ref}" if "pooler" in h else "postgres"
                    conn = psycopg2.connect(host=h, port=port, user=user, password=passw, dbname="postgres", connect_timeout=4)
                    print(f"  [SUCCESS!!!] Connected to Supabase at {h}:{port} as user '{user}'!")
                    cur = conn.cursor()
                    cur.execute("SELECT version();")
                    ver = cur.fetchone()[0]
                    print(f"  [Version]: {ver[:60]}")
                    conn.close()
                    return True
                except Exception as ex:
                    print(f"  Port {port} connect failed: {type(ex).__name__} - {ex}")
        except Exception as e:
            print(f"Host '{h}' DNS failed: {e}")

if __name__ == "__main__":
    test_hosts()
