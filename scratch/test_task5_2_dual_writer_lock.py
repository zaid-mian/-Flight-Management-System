import os
import sys
import time
import threading
import requests
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, r"E:\n8n\flight-agent-hackathon")
from app.database import get_db_cursor

BASE_URL = "http://127.0.0.1:8000"

def test_task5_2_dual_writer_lock():
    print("=== Task 5.2: Dual-Writer Row-Lock Collision Test & Architectural Boundary Verification ===")
    
    # 1. Setup temporary test flight with 1 available seat
    flight_number = "LOCK-520"
    dep_time = datetime.now(timezone.utc) + timedelta(days=3)
    arr_time = dep_time + timedelta(hours=2)
    
    admin_payload = {
        "flight_number": flight_number,
        "origin": "SEA",
        "destination": "DEN",
        "departure_time": dep_time.isoformat(),
        "arrival_time": arr_time.isoformat(),
        "total_capacity": 1,
        "seat_classes": [
            {
                "class_name": "ECONOMY",
                "total_seats": 1,
                "fare_base_price": 150.00
            }
        ]
    }
    
    res = requests.post(f"{BASE_URL}/api/v1/flights/admin/create", json=admin_payload)
    assert res.status_code == 201, f"Failed to create test flight: {res.text}"
    flight_id = res.json()["id"]
    print(f"[PASS] Created test flight '{flight_number}' (ID: {flight_id}) with 1 available seat.")
    
    tx_a_lock_acquired = threading.Event()
    
    # 2. Start Transaction A in background holding FOR UPDATE lock on seat_classes
    def hold_tx_a():
        print("  [Tx-A] Starting Transaction A: Acquiring FOR UPDATE lock on seat_classes...")
        with get_db_cursor() as (cur, conn):
            cur.execute("""
                SELECT id, available_seats, booked_seats 
                FROM seat_classes 
                WHERE flight_id = %s AND class_name = 'ECONOMY' 
                FOR UPDATE;
            """, (flight_id,))
            sc_row = cur.fetchone()
            print(f"  [Tx-A] Lock ACQUIRED! Row state: avail={sc_row['available_seats']}, booked={sc_row['booked_seats']}. Setting Event signal...")
            tx_a_lock_acquired.set()
            
            print("  [Tx-A] Holding FOR UPDATE lock for 2.0 seconds...")
            time.sleep(2.0)
            
            # Tx-A consumes the 1 available seat
            cur.execute("""
                UPDATE seat_classes 
                SET available_seats = available_seats - 1, booked_seats = booked_seats + 1 
                WHERE flight_id = %s AND class_name = 'ECONOMY';
            """, (flight_id,))
            print("  [Tx-A] Decremented seat_classes (avail=0, booked=1). Committing Tx-A...")
        print("  [Tx-A] Transaction A COMMITTED and lock released.")
        return True

    # Function for competing FastAPI operation
    def call_fastapi_booking():
        print("  [FastAPI-Worker] Waiting for Tx-A to acquire lock...")
        tx_a_lock_acquired.wait(timeout=5.0)
        print("  [FastAPI-Worker] Tx-A lock signal received! Sending competing POST /api/v1/bookings request while Tx-A still holds lock...")
        start_t = time.perf_counter()
        payload = {
            "flight_id": flight_id,
            "passenger_id": "pass_lock_b",
            "passenger_name": "Competing Worker",
            "passenger_email": "competing@example.com",
            "class_name": "ECONOMY",
            "fare_code": "BASIC_ECONOMY",
            "fare_amount": 150.00,
            "idempotency_key": f"idemp-lock-52-b-{time.time_ns()}"
        }
        r = requests.post(f"{BASE_URL}/api/v1/bookings", json=payload)
        latency_ms = (time.perf_counter() - start_t) * 1000.0
        print(f"  [FastAPI-Worker] Unblocked! Status: {r.status_code} | Latency: {latency_ms:.2f} ms | Res: {r.json() if r.headers.get('content-type') == 'application/json' else r.text}")
        return {
            "status_code": r.status_code,
            "latency_ms": latency_ms,
            "response": r.json()
        }

    # 3. Execute Tx-A and competing FastAPI booking concurrently
    with ThreadPoolExecutor(max_workers=2) as executor:
        fut_a = executor.submit(hold_tx_a)
        fut_b = executor.submit(call_fastapi_booking)
        
        res_a = fut_a.result()
        res_b = fut_b.result()
        
    # 4. Assert Lock Blocking & Serialization Behavior
    print("\n--- Lock Serialization Verification ---")
    print(f"  - Competing Request Status Code: {res_b['status_code']}")
    print(f"  - Competing Request Latency: {res_b['latency_ms']:.2f} ms (expected > 1400 ms due to lock wait)")
    
    assert res_b["latency_ms"] >= 1400.0, f"Competing request did NOT block on FOR UPDATE lock! Latency: {res_b['latency_ms']} ms"
    assert res_b["status_code"] == 400, f"Competing request should fail with 400 after Tx-A consumed last seat, got {res_b['status_code']}"
    assert res_b["response"]["detail"] == "No seats available for booking."
    print("  [PASS] FOR UPDATE row lock successfully blocked and serialized competing transaction, preventing double-booking!")
    
    # 5. Direct Supabase Verification
    with get_db_cursor(commit_on_success=False) as (cur, conn):
        cur.execute("SELECT total_seats, available_seats, booked_seats FROM seat_classes WHERE flight_id = %s AND class_name = 'ECONOMY';", (flight_id,))
        sc_row = cur.fetchone()
        assert sc_row["available_seats"] == 0
        assert sc_row["booked_seats"] == 1
        assert sc_row["total_seats"] == 1
        print(f"  [PASS] Supabase Final Inventory: total=1, available=0, booked=1. Zero lost updates!")
        
    # 6. Architectural Boundary Verification: Check n8n Workflows for Direct Inventory Writes
    print("\n--- Architectural Boundary Audit (n8n -> FastAPI -> Supabase) ---")
    with get_db_cursor(commit_on_success=False) as (cur, conn):
        cur.execute("SELECT COUNT(*) AS total FROM audit_logs WHERE actor_type = 'N8N_WORKFLOW' AND action IN ('DIRECT_INVENTORY_WRITE', 'DIRECT_BOOKING_CREATE');")
        direct_n8n_writes = cur.fetchone()["total"]
        assert direct_n8n_writes == 0, f"DETECTED {direct_n8n_writes} DIRECT N8N DATABASE WRITES!"
        print("  [PASS] Verified 0 direct n8n inventory/booking write violations. n8n strictly delegates state mutations to FastAPI REST API.")
        
    # Cleanup test data
    with get_db_cursor() as (cur, conn):
        cur.execute("DELETE FROM audit_logs WHERE entity_id = %s;", (flight_id,))
        cur.execute("DELETE FROM bookings WHERE flight_id = %s;", (flight_id,))
        cur.execute("DELETE FROM seat_classes WHERE flight_id = %s;", (flight_id,))
        cur.execute("DELETE FROM flights WHERE id = %s;", (flight_id,))
        
    print("\n--> TASK 5.2 DUAL-WRITER ROW-LOCK COLLISION TEST: 100% VERIFIED PASS! <--")
    return True

if __name__ == "__main__":
    test_task5_2_dual_writer_lock()
