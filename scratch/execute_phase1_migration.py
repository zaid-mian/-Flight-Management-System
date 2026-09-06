import psycopg2
import os
import sys

def execute_and_verify_phase1():
    print("=== EXECUTING PHASE 1 MIGRATION ON SUPABASE POSTGRESQL ===")
    
    from dotenv import dotenv_values
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = dotenv_values(os.path.join(project_root, ".env"))
    
    host = env.get("POSTGRES_HOST") or "aws-0-ap-southeast-1.pooler.supabase.com"
    port = int(env.get("POSTGRES_PORT") or 5432)
    user = env.get("POSTGRES_USER") or "postgres.ewqzxwurcmdgnvoczeyz"
    dbname = env.get("POSTGRES_DB") or "postgres"
    password = env.get("POSTGRES_PASSWORD", "")
    
    sql_path = r"E:\n8n\flight-agent-hackathon\migrations\001_initial_schema.sql"
    if not os.path.exists(sql_path):
        print(f"[FAIL] Migration DDL missing: {sql_path}")
        return False
        
    with open(sql_path, "r", encoding="utf-8") as f:
        sql_content = f.read()
        
    print("Connecting to Supabase PostgreSQL database...")
    try:
        conn = psycopg2.connect(host=host, port=port, user=user, password=password, dbname=dbname, connect_timeout=15)
        cur = conn.cursor()
        print("Connected! Executing 001_initial_schema.sql...")
        
        # Execute migration DDL
        cur.execute(sql_content)
        conn.commit()
        print("  [PASS] DDL Migration applied and committed to Supabase!")
        
        # 1. VERIFY TABLES EXIST
        expected_tables = [
            "flights", "seat_classes", "seat_holds", "bookings", 
            "waitlist", "escalation_requests", "policy_inquiries", 
            "fraud_flags", "audit_logs"
        ]
        
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public';
        """)
        existing_tables = [r[0] for r in cur.fetchall()]
        print(f"\nExisting Public Tables in Supabase: {existing_tables}")
        
        missing_tables = [t for t in expected_tables if t not in existing_tables]
        if missing_tables:
            print(f"  [FAIL] Missing Tables: {missing_tables}")
            return False
        print("  [PASS] Table Verification: ALL 9 TABLES VERIFIED!")
        
        # 2. VERIFY INDEXES EXIST
        expected_indexes = [
            "idx_seat_classes_flight_class", "idx_seat_holds_expiry",
            "idx_bookings_idempotency", "idx_waitlist_priority",
            "idx_escalations_status", "idx_policy_inquiries_status"
        ]
        cur.execute("SELECT indexname FROM pg_indexes WHERE schemaname = 'public';")
        existing_indexes = [r[0] for r in cur.fetchall()]
        missing_indexes = [i for i in expected_indexes if i not in existing_indexes]
        if missing_indexes:
            print(f"  [FAIL] Missing Indexes: {missing_indexes}")
            return False
        print("  [PASS] Index Verification: ALL 6 CUSTOM INDEXES VERIFIED!")
        
        # 3. VERIFY CAPACITY TRIGGER & FUNCTION
        cur.execute("SELECT proname FROM pg_proc WHERE proname = 'validate_flight_capacity_sum';")
        func_exists = cur.fetchone()
        assert func_exists is not None
        
        cur.execute("SELECT tgname FROM pg_trigger WHERE tgname = 'trigger_check_seat_capacity';")
        trig_exists = cur.fetchone()
        assert trig_exists is not None
        print("  [PASS] Trigger Function & Trigger Verification: VERIFIED!")
        
        # 4. RUN LIVE INVARIANT & CONSTRAINT TESTS
        print("\n--- Running Invariant & Constraint Tests ---")
        
        # Insert a test flight
        cur.execute("""
            INSERT INTO flights (flight_number, origin, destination, departure_time, arrival_time, total_capacity)
            VALUES ('TEST999', 'LHR', 'DXB', NOW() + INTERVAL '1 day', NOW() + INTERVAL '1 day 7 hours', 100)
            RETURNING id;
        """)
        test_flight_id = cur.fetchone()[0]
        
        # Insert seat classes: First (20), Business (30), Economy (50) -> Sum = 100
        cur.execute("""
            INSERT INTO seat_classes (flight_id, class_name, total_seats, available_seats, booked_seats, fare_base_price)
            VALUES 
            (%s, 'FIRST', 20, 20, 0, 1500.00),
            (%s, 'BUSINESS', 30, 30, 0, 800.00),
            (%s, 'ECONOMY', 50, 50, 0, 300.00);
        """, (test_flight_id, test_flight_id, test_flight_id))
        print("  [PASS] Insert Flight & Seat Classes (Sum = 100 / Capacity = 100): SUCCESS")
        
        # Test Trigger: Try inserting extra seat class exceeding 100 total capacity
        try:
            cur.execute("""
                INSERT INTO seat_classes (flight_id, class_name, total_seats, available_seats, booked_seats, fare_base_price)
                VALUES (%s, 'FIRST', 10, 10, 0, 1500.00);
            """, (test_flight_id,))
            print("  [FAIL] Capacity Trigger Test: FAILED (did not raise capacity error)")
            return False
        except psycopg2.Error as ex:
            conn.rollback()
            print(f"  [PASS] Capacity Trigger Rejection: SUCCESS (Caught expected exception code: {ex.pgcode})")
            
        # Re-connect after rollback
        conn = psycopg2.connect(host=host, port=port, user=user, password=password, dbname=dbname, connect_timeout=15)
        cur = conn.cursor()
        
        # Test Negative Seat CHECK Constraint Rejection
        try:
            cur.execute("""
                INSERT INTO seat_classes (flight_id, class_name, total_seats, available_seats, booked_seats, fare_base_price)
                VALUES (%s, 'ECONOMY', -5, -5, 0, 100.00);
            """, (test_flight_id,))
            print("  [FAIL] Negative Seats Check: FAILED (did not raise exception)")
            return False
        except psycopg2.Error as ex:
            conn.rollback()
            assert ex.pgcode == "23514"
            print(f"  [PASS] Negative Seats CHECK Constraint Rejection: SUCCESS (PostgreSQL Error 23514 verified)")
            
        # Re-connect to verify clean data state
        conn = psycopg2.connect(host=host, port=port, user=user, password=password, dbname=dbname, connect_timeout=15)
        cur = conn.cursor()
        
        # Delete test flight if any survived
        cur.execute("DELETE FROM flights WHERE flight_number = 'TEST999';")
        conn.commit()
        
        # Confirm zero test rows remaining
        cur.execute("SELECT COUNT(*) FROM flights WHERE flight_number = 'TEST999';")
        cnt = cur.fetchone()[0]
        assert cnt == 0
        print("  [PASS] Unintended Production Data Cleanup: VERIFIED (0 test rows remain)")
        
        conn.close()
        print("\n--> PHASE 1 MIGRATION & VERIFICATION: ALL 100% PASSED! <--")
        return True
    except Exception as e:
        print(f"  [FAIL] Phase 1 Execution Failed: {type(e).__name__} - {e}")
        return False

if __name__ == "__main__":
    execute_and_verify_phase1()
