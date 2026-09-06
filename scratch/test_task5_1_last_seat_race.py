import os
import sys
import time
import requests
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, r"E:\n8n\flight-agent-hackathon")
from app.database import get_db_cursor

BASE_URL = "http://127.0.0.1:8000"

def test_task5_1_last_seat_race():
    print("=== Task 5.1: Last-Seat Overselling Race Condition Test (10 Concurrent Workers) ===")
    
    # 1. Create temporary test flight with capacity = 1 via FastAPI Admin endpoint
    flight_number = "RACE-510"
    dep_time = datetime.now(timezone.utc) + timedelta(days=2)
    arr_time = dep_time + timedelta(hours=2)
    
    admin_payload = {
        "flight_number": flight_number,
        "origin": "SFO",
        "destination": "ORD",
        "departure_time": dep_time.isoformat(),
        "arrival_time": arr_time.isoformat(),
        "total_capacity": 1,
        "seat_classes": [
            {
                "class_name": "ECONOMY",
                "total_seats": 1,
                "fare_base_price": 299.99
            }
        ]
    }
    
    res = requests.post(f"{BASE_URL}/api/v1/flights/admin/create", json=admin_payload)
    assert res.status_code == 201, f"Failed to create test flight: {res.text}"
    flight_id = res.json()["id"]
    print(f"[PASS] Created test flight '{flight_number}' (ID: {flight_id}) with exactly 1 available seat.")
    
    # 2. Prepare 10 concurrent competing booking requests
    num_workers = 10
    
    def send_booking_request(worker_idx: int):
        payload = {
            "flight_id": flight_id,
            "passenger_id": f"pass_race_{worker_idx}",
            "passenger_name": f"Racer {worker_idx}",
            "passenger_email": f"racer_{worker_idx}@example.com",
            "class_name": "ECONOMY",
            "fare_code": "BASIC_ECONOMY",
            "fare_amount": 299.99,
            "idempotency_key": f"idemp-race-51-{worker_idx}-{time.time_ns()}"
        }
        start_t = time.perf_counter()
        r = requests.post(f"{BASE_URL}/api/v1/bookings", json=payload)
        latency_ms = (time.perf_counter() - start_t) * 1000.0
        return {
            "worker_idx": worker_idx,
            "status_code": r.status_code,
            "latency_ms": round(latency_ms, 2),
            "response": r.json() if r.headers.get("content-type") == "application/json" else r.text
        }
        
    print(f"\n---> Firing {num_workers} concurrent threads at single available seat on flight '{flight_number}'...")
    results = []
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(send_booking_request, i) for i in range(num_workers)]
        for fut in as_completed(futures):
            results.append(fut.result())
            
    # 3. Analyze HTTP responses
    successes = [r for r in results if r["status_code"] == 201]
    rejections = [r for r in results if r["status_code"] == 400]
    others = [r for r in results if r["status_code"] not in [201, 400]]
    
    print("\n--- Concurrency Test Results ---")
    print(f"  - Total Parallel Workers: {num_workers}")
    print(f"  - Successful Bookings (HTTP 201): {len(successes)}")
    print(f"  - Rejected Requests (HTTP 400): {len(rejections)}")
    print(f"  - Unexpected Statuses: {len(others)}")
    
    for r in results:
        print(f"  Worker {r['worker_idx']:02d} | Status: {r['status_code']} | Latency: {r['latency_ms']} ms | Res: {r['response']}")
        
    assert len(successes) == 1, f"EXPECTED EXACTLY 1 SUCCESSFUL BOOKING, GOT {len(successes)}"
    assert len(rejections) == 9, f"EXPECTED EXACTLY 9 REJECTIONS, GOT {len(rejections)}"
    assert len(others) == 0, f"UNEXPECTED HTTP RESPONSES RETURNED: {others}"
    
    # 4. Direct Supabase Database Invariant Verification
    print("\n--- Direct Supabase Database Invariant Verification ---")
    with get_db_cursor(commit_on_success=False) as (cur, conn):
        # Verify seat_classes inventory
        cur.execute("SELECT total_seats, available_seats, booked_seats FROM seat_classes WHERE flight_id = %s AND class_name = 'ECONOMY';", (flight_id,))
        sc_row = cur.fetchone()
        
        total_s = sc_row["total_seats"]
        avail_s = sc_row["available_seats"]
        booked_s = sc_row["booked_seats"]
        
        print(f"  - seat_classes Inventory: total={total_s}, available={avail_s}, booked={booked_s}")
        assert avail_s == 0, f"available_seats should be 0, got {avail_s}"
        assert booked_s == 1, f"booked_seats should be 1, got {booked_s}"
        assert avail_s + booked_s == total_s, f"Inventory invariant broken: {avail_s} + {booked_s} != {total_s}"
        
        # Verify booking table count
        cur.execute("SELECT COUNT(*) AS total FROM bookings WHERE flight_id = %s;", (flight_id,))
        b_count = cur.fetchone()["total"]
        print(f"  - Total Booking Records in Database: {b_count}")
        assert b_count == 1, f"Database has {b_count} bookings for test flight, expected exactly 1!"
        
        # Verify audit_logs entry
        cur.execute("SELECT COUNT(*) AS total FROM audit_logs WHERE entity_id = %s;", (flight_id,))
        audit_count = cur.fetchone()["total"]
        print(f"  - Total Audit Trail Records for Flight: {audit_count}")

    print("\n[PASS] Database Invariants Verified: 0 overselling, 0 negative inventory, exactly 1 booking recorded.")
    
    # 5. Cleanup test records
    with get_db_cursor() as (cur, conn):
        cur.execute("DELETE FROM audit_logs WHERE entity_id = %s;", (flight_id,))
        cur.execute("DELETE FROM bookings WHERE flight_id = %s;", (flight_id,))
        cur.execute("DELETE FROM seat_classes WHERE flight_id = %s;", (flight_id,))
        cur.execute("DELETE FROM flights WHERE id = %s;", (flight_id,))
        
    print("[PASS] Temporary race test data cleaned up safely from Supabase.")
    print("\n--> TASK 5.1 LAST-SEAT OVERSELLING RACE CONDITION TEST: 100% VERIFIED PASS! <--")
    return True

if __name__ == "__main__":
    test_task5_1_last_seat_race()
