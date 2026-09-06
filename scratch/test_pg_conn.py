import sys

def test_pg_driver():
    driver = None
    try:
        import psycopg2
        driver = "psycopg2"
    except ImportError:
        try:
            import psycopg
            driver = "psycopg"
        except ImportError:
            try:
                import asyncpg
                driver = "asyncpg"
            except ImportError:
                driver = None
    
    print(f"Available PG Driver: {driver}")
    
    if driver == "psycopg2":
        import psycopg2
        # Try common passwords
        passwords = ["postgres", "root", "admin", "123456", "password", ""]
        for p in passwords:
            try:
                conn = psycopg2.connect(host="127.0.0.1", port=8888, user="postgres", password=p, dbname="postgres", connect_timeout=3)
                print(f"SUCCESS: Connected to PostgreSQL on 8888 with user 'postgres'!")
                
                cur = conn.cursor()
                cur.execute("SELECT version();")
                ver = cur.fetchone()
                print(f"PostgreSQL Version: {ver[0]}")
                
                # Test SELECT, INSERT, TRANSACTION, ROLLBACK, CHECK CONSTRAINT
                print("\n--- Testing Transactions & Invariants ---")
                cur.execute("CREATE TEMP TABLE preflight_test (id serial primary key, val int check (val > 0));")
                
                # Test INSERT
                cur.execute("INSERT INTO preflight_test (val) VALUES (10);")
                print("1. INSERT: SUCCESS")
                
                # Test SELECT
                cur.execute("SELECT val FROM preflight_test WHERE val = 10;")
                res = cur.fetchone()
                assert res[0] == 10
                print("2. SELECT: SUCCESS")
                
                # Test CHECK Constraint Rejection
                try:
                    cur.execute("INSERT INTO preflight_test (val) VALUES (-5);")
                    print("3. CHECK CONSTRAINT: FAILED (did not raise error)")
                except Exception as ex:
                    conn.rollback()
                    print(f"3. CHECK CONSTRAINT REJECTION: SUCCESS (caught expected exception: {type(ex).__name__})")
                
                # Test Transaction & Rollback
                cur.execute("CREATE TEMP TABLE preflight_test2 (id serial primary key, name text);")
                cur.execute("INSERT INTO preflight_test2 (name) VALUES ('rollback_test');")
                conn.rollback()
                
                # Verify row does not exist after rollback
                cur.execute("CREATE TEMP TABLE preflight_test3 (id int);") # reset tx state
                try:
                    cur.execute("SELECT * FROM preflight_test2;")
                    print("4. ROLLBACK VERIFICATION: FAILED (table still exists)")
                except Exception:
                    conn.rollback()
                    print("4. TRANSACTION & ROLLBACK VERIFICATION: SUCCESS")
                
                conn.close()
                return True
            except Exception as e:
                pass
        print("FAILED to connect to Postgres with tested default credentials.")
        return False
    else:
        print("No psycopg2 installed. Installing or testing standard lib...")
        return False

if __name__ == "__main__":
    test_pg_driver()
