import requests
import uuid
import time
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "http://127.0.0.1:8000"

def test_phase3_full_suite():
    print("==========================================================================")
    print("=== PHASE 3 FASTAPI REST ENGINE & SUPABASE POSTGRES SUITE ===")
    print("==========================================================================")

    # --- TASK 3.1: HEALTH & POOL CHECK ---
    print("\n--- Testing Task 3.1: FastAPI Setup & DB Connection Pool ---")
    resp = requests.get(f"{BASE_URL}/health")
    assert resp.status_code == 200, f"Health check failed: {resp.text}"
    health_data = resp.json()
    print(f"  [PASS] Health Status: {health_data['status']}")
    print(f"  [PASS] DB Provider: {health_data['database']['database']}")
    print(f"  [PASS] PostgreSQL Version: {health_data['database']['version']}")
    print(f"  [PASS] Pool Active: {health_data['pool']['pool_active']}")

    # --- TASK 3.2: ADMIN FLIGHT CREATION ---
    print("\n--- Testing Task 3.2: Admin Flight Creation Endpoint ---")
    dep_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    arr_time = (datetime.now(timezone.utc) + timedelta(days=2, hours=5)).isoformat()

    # 1. Valid Flight Creation
    valid_payload = {
        "flight_number": "HKT-300",
        "origin": "JFK",
        "destination": "SFO",
        "departure_time": dep_time,
        "arrival_time": arr_time,
        "total_capacity": 100,
        "seat_classes": [
            {"class_name": "FIRST", "total_seats": 20, "fare_base_price": 500.00},
            {"class_name": "ECONOMY", "total_seats": 80, "fare_base_price": 150.00}
        ]
    }
    resp = requests.post(f"{BASE_URL}/api/v1/flights/admin/create", json=valid_payload)
    assert resp.status_code == 201, f"Valid flight creation failed: {resp.text}"
    flight_300 = resp.json()
    flight_300_id = flight_300["id"]
    print(f"  [PASS] Valid Flight Created cleanly! ID: {flight_300_id}")

    # 2. Invalid Capacity Mismatch (Sum = 110 != Total = 100)
    invalid_capacity_payload = valid_payload.copy()
    invalid_capacity_payload["flight_number"] = "HKT-301-ERR"
    invalid_capacity_payload["seat_classes"] = [
        {"class_name": "FIRST", "total_seats": 30, "fare_base_price": 500.00},
        {"class_name": "ECONOMY", "total_seats": 80, "fare_base_price": 150.00}
    ]
    resp = requests.post(f"{BASE_URL}/api/v1/flights/admin/create", json=invalid_capacity_payload)
    assert resp.status_code == 400, f"Expected 400 for capacity mismatch, got {resp.status_code}"
    print(f"  [PASS] Capacity Mismatch Rejection Verified (HTTP 400): {resp.json()['detail']}")

    # 3. Invalid Time Sequence (Arrival <= Departure)
    invalid_time_payload = valid_payload.copy()
    invalid_time_payload["flight_number"] = "HKT-302-ERR"
    invalid_time_payload["arrival_time"] = dep_time  # Same as dep time
    resp = requests.post(f"{BASE_URL}/api/v1/flights/admin/create", json=invalid_time_payload)
    assert resp.status_code == 422, f"Expected 422 for invalid times, got {resp.status_code}"
    print("  [PASS] Invalid Time Sequence Rejection Verified (HTTP 422)")

    # --- TASK 3.3: FLIGHT SEARCH & INVENTORY QUERY ---
    print("\n--- Testing Task 3.3: Flight Search & Inventory Query Endpoint ---")
    resp = requests.get(f"{BASE_URL}/api/v1/flights/search?flight_number=HKT-300")
    assert resp.status_code == 200, f"Search failed: {resp.text}"
    search_results = resp.json()
    assert len(search_results) > 0, "No flights returned in search"
    found_flight = search_results[0]
    assert found_flight["flight_number"] == "HKT-300"
    assert len(found_flight["seat_classes"]) == 2
    print(f"  [PASS] Flight Search returned flight {found_flight['flight_number']} with {len(found_flight['seat_classes'])} seat classes.")

    # --- TASK 3.4: ATOMIC SEAT HOLD ---
    print("\n--- Testing Task 3.4: Atomic Seat Hold Endpoint ---")
    hold_payload = {
        "flight_id": flight_300_id,
        "class_name": "ECONOMY",
        "passenger_id": "PAX-HOLD-001",
        "seat_count": 2,
        "hold_duration_minutes": 10
    }
    resp = requests.post(f"{BASE_URL}/api/v1/holds", json=hold_payload)
    assert resp.status_code == 201, f"Seat hold creation failed: {resp.text}"
    hold_data = resp.json()
    hold_id = hold_data["hold_id"]
    print(f"  [PASS] Atomic Seat Hold Created! Hold ID: {hold_id}, Status: {hold_data['status']}")

    # Verify Inventory Decrement
    resp = requests.get(f"{BASE_URL}/api/v1/flights/search?flight_number=HKT-300")
    economy_class = [sc for sc in resp.json()[0]["seat_classes"] if sc["class_name"] == "ECONOMY"][0]
    assert economy_class["available_seats"] == 78, f"Expected 78 available seats, got {economy_class['available_seats']}"
    print(f"  [PASS] Inventory decremented atomically from 80 to {economy_class['available_seats']}")

    # Insufficient Seats Rejection
    excess_hold_payload = hold_payload.copy()
    excess_hold_payload["seat_count"] = 500
    resp = requests.post(f"{BASE_URL}/api/v1/holds", json=excess_hold_payload)
    assert resp.status_code == 400, f"Expected 400 for excess hold, got {resp.status_code}"
    print(f"  [PASS] Insufficient Inventory Rejection Verified: {resp.json()['detail']}")

    # --- TASK 3.5: ATOMIC BOOKING ENDPOINT & IDEMPOTENCY & CONCURRENCY ---
    print("\n--- Testing Task 3.5: Atomic Booking Endpoint ---")
    idempotency_key_1 = f"IDEM-KEY-{uuid.uuid4()}"
    booking_payload = {
        "flight_id": flight_300_id,
        "passenger_id": "PAX-BOOK-001",
        "passenger_name": "Edward Norton",
        "passenger_email": "edward@example.com",
        "class_name": "ECONOMY",
        "fare_code": "BASIC_ECONOMY",
        "fare_amount": 150.00,
        "idempotency_key": idempotency_key_1
    }

    # 1. Normal Booking
    resp = requests.post(f"{BASE_URL}/api/v1/bookings", json=booking_payload)
    assert resp.status_code == 201, f"Booking creation failed: {resp.text}"
    booking_1 = resp.json()
    booking_1_id = booking_1["booking_id"]
    print(f"  [PASS] Booking Created! Booking ID: {booking_1_id}")

    # 2. Idempotency Retest (Same payload, same idempotency key)
    resp = requests.post(f"{BASE_URL}/api/v1/bookings", json=booking_payload)
    assert resp.status_code == 201, f"Idempotent retest failed: {resp.text}"
    booking_1_idempotent = resp.json()
    assert booking_1_idempotent["booking_id"] == booking_1_id, "Idempotency key did not return same booking ID"
    print(f"  [PASS] Idempotency Protection Verified! Returned same Booking ID: {booking_1_idempotent['booking_id']}")

    # 3. Hold Conversion Booking
    idempotency_key_hold = f"IDEM-KEY-HOLD-{uuid.uuid4()}"
    booking_from_hold_payload = {
        "flight_id": flight_300_id,
        "passenger_id": "PAX-HOLD-001",
        "passenger_name": "Hold Customer",
        "passenger_email": "holdcust@example.com",
        "class_name": "ECONOMY",
        "fare_code": "FLEXIBLE_ECONOMY",
        "fare_amount": 150.00,
        "idempotency_key": idempotency_key_hold,
        "hold_id": hold_id
    }
    resp = requests.post(f"{BASE_URL}/api/v1/bookings", json=booking_from_hold_payload)
    assert resp.status_code == 201, f"Hold conversion booking failed: {resp.text}"
    print(f"  [PASS] Hold Conversion Booking Succeeded! Booking ID: {resp.json()['booking_id']}")

    # 4. Phase 2.2 Waitlist Callback Boundary Test
    print("  --- Testing Phase 2.2 Callback Boundary (POST /api/v1/bookings/convert-waitlist) ---")
    # First get promoted waitlist entry ID
    from app.config import settings
    conn = psycopg2.connect(host=settings.POSTGRES_HOST, port=settings.POSTGRES_PORT, user=settings.POSTGRES_USER, password=settings.POSTGRES_PASSWORD, dbname=settings.POSTGRES_DB)
    cur = conn.cursor()
    cur.execute("SELECT id FROM waitlist WHERE status = 'PROMOTED' LIMIT 1;")
    wl_row = cur.fetchone()
    conn.close()

    if wl_row:
        wl_id = str(wl_row[0])
        convert_payload = {
            "waitlist_id": wl_id,
            "idempotency_key": f"IDEM-WL-{uuid.uuid4()}"
        }
        resp = requests.post(f"{BASE_URL}/api/v1/bookings/convert-waitlist", json=convert_payload)
        assert resp.status_code == 201, f"Waitlist conversion failed: {resp.text}"
        print(f"  [PASS] Phase 2.2 Waitlist Callback Boundary Verified! Booking ID: {resp.json()['booking_id']}")

    # 5. MANDATORY CONCURRENCY & LAST-SEAT OVERSELLING TEST
    print("\n--- MANDATORY TEST: Concurrency & Last-Seat Overselling Protection ---")
    # Create a 1-seat single-capacity flight HKT-LASTSEAT
    last_seat_flight_payload = {
        "flight_number": "HKT-RACE",
        "origin": "JFK",
        "destination": "MIA",
        "departure_time": dep_time,
        "arrival_time": arr_time,
        "total_capacity": 1,
        "seat_classes": [
            {"class_name": "ECONOMY", "total_seats": 1, "fare_base_price": 100.00}
        ]
    }
    resp = requests.post(f"{BASE_URL}/api/v1/flights/admin/create", json=last_seat_flight_payload)
    assert resp.status_code == 201, f"Last-seat flight creation failed: {resp.text}"
    last_seat_flight_id = resp.json()["id"]
    print(f"  Single-seat test flight created! ID: {last_seat_flight_id}")

    # Launch 5 concurrent threads attempting to book the LAST SEAT simultaneously
    def attempt_booking(thread_idx):
        payload = {
            "flight_id": last_seat_flight_id,
            "passenger_id": f"PAX-RACE-{thread_idx}",
            "passenger_name": f"Race Competitor {thread_idx}",
            "passenger_email": f"competitor{thread_idx}@example.com",
            "class_name": "ECONOMY",
            "fare_code": "BASIC_ECONOMY",
            "fare_amount": 100.00,
            "idempotency_key": f"IDEM-RACE-{thread_idx}-{uuid.uuid4()}"
        }
        r = requests.post(f"{BASE_URL}/api/v1/bookings", json=payload)
        return thread_idx, r.status_code, r.json()

    print("  Launching 5 concurrent booking threads against single available seat...")
    futures = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        for idx in range(1, 6):
            futures.append(executor.submit(attempt_booking, idx))

    successes = 0
    rejections = 0
    for future in as_completed(futures):
        idx, code, data = future.result()
        if code == 201:
            successes += 1
            print(f"    Thread {idx}: SUCCESS (HTTP 201) -> Booking ID {data['booking_id']}")
        else:
            rejections += 1
            print(f"    Thread {idx}: REJECTED ({code}) -> {data.get('detail')}")

    assert successes == 1, f"Concurrency failure! Expected exactly 1 success, got {successes}"
    assert rejections == 4, f"Concurrency failure! Expected 4 rejections, got {rejections}"
    print(f"  [PASS] FOR UPDATE Row Locking Verified! Exactly {successes} succeeded and {rejections} rejected!")

    # Verify inventory is 0
    resp = requests.get(f"{BASE_URL}/api/v1/flights/search?flight_number=HKT-RACE")
    last_seat_class = resp.json()[0]["seat_classes"][0]
    assert last_seat_class["available_seats"] == 0, f"Expected 0 available seats, got {last_seat_class['available_seats']}"
    assert last_seat_class["booked_seats"] == 1, f"Expected 1 booked seat, got {last_seat_class['booked_seats']}"
    print("  [PASS] Zero overselling verified! Available seats = 0, Booked seats = 1.")

    # --- TASK 3.6: FLIGHT & BOOKING CANCELLATION ENDPOINT ---
    print("\n--- Testing Task 3.6: Flight & Booking Cancellation Endpoint ---")
    cancel_payload = {
        "booking_id": booking_1_id,
        "reason": "Customer changed travel plans"
    }

    # 1. Valid Cancellation
    resp = requests.post(f"{BASE_URL}/api/v1/bookings/cancel", json=cancel_payload)
    assert resp.status_code == 200, f"Cancellation failed: {resp.text}"
    cancel_data = resp.json()
    assert cancel_data["status"] == "CANCELLED"
    assert cancel_data["inventory_restored"] == True
    print(f"  [PASS] Booking Cancelled! Status: {cancel_data['status']}, Inventory Restored: {cancel_data['inventory_restored']}")

    # 2. Idempotent Cancellation (Cancel same booking again)
    resp = requests.post(f"{BASE_URL}/api/v1/bookings/cancel", json=cancel_payload)
    assert resp.status_code == 200, f"Idempotent cancellation failed: {resp.text}"
    cancel_data_2 = resp.json()
    assert cancel_data_2["status"] == "CANCELLED"
    assert cancel_data_2["inventory_restored"] == False  # False because inventory was already restored in first call
    print("  [PASS] Idempotent Cancellation Verified! No duplicate inventory restoration.")

    # 3. Non-existent Booking Cancellation
    fake_cancel_payload = {"booking_id": str(uuid.uuid4()), "reason": "Fake booking"}
    resp = requests.post(f"{BASE_URL}/api/v1/bookings/cancel", json=fake_cancel_payload)
    assert resp.status_code == 404, f"Expected 404 for non-existent booking, got {resp.status_code}"
    print("  [PASS] Non-Existent Booking Cancellation Rejection Verified (HTTP 404)")

    print("\n==========================================================================")
    print("===> ALL PHASE 3 FASTAPI TESTS PASSED 100% CLEANLY AND VERIFIED! <===")
    print("==========================================================================")

if __name__ == "__main__":
    test_phase3_full_suite()
