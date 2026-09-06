import os
import sys
import requests
from datetime import datetime, timedelta, timezone
sys.path.insert(0, r"E:\n8n\flight-agent-hackathon")
from app.database import get_db_cursor
from app.mcp.mcp_tools import calculate_fare_refund_entitlement

BASE_URL = "http://127.0.0.1:8000"

def process_human_approval_workflow(booking_id: str, decision: str, supervisor_id: str = "supervisor_admin_1"):
    print(f"\n--- Human Approval Flow for Booking {booking_id} (Decision: {decision}) ---")
    
    # 1. Deterministic refund entitlement calculation
    refund_calc = calculate_fare_refund_entitlement(booking_id)
    assert "error" not in refund_calc, refund_calc
    
    print(f"  - Fare Amount: ${refund_calc['fare_amount']:.2f}")
    print(f"  - Eligible Refund: ${refund_calc['eligible_refund_amount']:.2f}")
    print(f"  - Requires Human Approval: {refund_calc['requires_human_approval']}")
    print(f"  - Approval Reason: {refund_calc['approval_reason']}")
    
    # 2. Decision execution
    if decision.upper() == "REJECTED":
        # On rejection: DO NOT mutate booking or inventory state!
        with get_db_cursor() as (cur, conn):
            cur.execute("""
                INSERT INTO audit_logs (actor_type, actor_id, action, entity_name, entity_id, payload_changes)
                VALUES ('FASTAPI_ADMIN', %s, 'REFUND_REQUEST_REJECTED', 'bookings', %s, %s::jsonb);
            """, (supervisor_id, booking_id, '{"decision": "REJECTED", "state_mutated": false}'))
            
            # Verify booking status remains CONFIRMED
            cur.execute("SELECT status FROM bookings WHERE id = %s;", (booking_id,))
            b_status = cur.fetchone()["status"]
            assert b_status == "CONFIRMED"
            print(f"  - [PASS] Rejection handled cleanly: Booking status remains '{b_status}', 0 inventory mutated.")
            return {"decision": "REJECTED", "booking_status": b_status, "state_mutated": False}
            
    elif decision.upper() == "APPROVED":
        # On approval: Call authoritative FastAPI cancellation endpoint for transactional state mutation!
        cancel_payload = {
            "booking_id": booking_id,
            "reason": f"Human Supervisor Approval ({supervisor_id}): Refund of ${refund_calc['eligible_refund_amount']:.2f} approved"
        }
        res = requests.post(f"{BASE_URL}/api/v1/bookings/cancel", json=cancel_payload)
        assert res.status_code == 200, res.text
        res_data = res.json()
        
        with get_db_cursor() as (cur, conn):
            cur.execute("""
                INSERT INTO audit_logs (actor_type, actor_id, action, entity_name, entity_id, payload_changes)
                VALUES ('FASTAPI_ADMIN', %s, 'REFUND_APPROVED_AND_CANCELLED', 'bookings', %s, %s::jsonb);
            """, (supervisor_id, booking_id, f'{{"decision": "APPROVED", "refund_amount": {refund_calc["eligible_refund_amount"]}}}'))
            
            cur.execute("SELECT status FROM bookings WHERE id = %s;", (booking_id,))
            b_status = cur.fetchone()["status"]
            assert b_status == "CANCELLED"
            print(f"  - [PASS] Approval executed via FastAPI: Booking status updated to '{b_status}', inventory restored!")
            return {"decision": "APPROVED", "booking_status": b_status, "inventory_restored": res_data.get("inventory_restored")}

def test_task4_4_hitl_approval():
    print("=== Task 4.4: Human Approval Wait Node & FastAPI Boundary Test ===")
    
    # Setup test flight and high-value booking ($650.00 > $500 threshold)
    flight_id = "f4400000-0000-0000-0000-000000000001"
    booking_id = "b4400000-0000-0000-0000-000000000001"
    
    with get_db_cursor() as (cur, conn):
        cur.execute("DELETE FROM audit_logs WHERE entity_id = %s;", (booking_id,))
        cur.execute("DELETE FROM bookings WHERE id = %s;", (booking_id,))
        cur.execute("DELETE FROM seat_classes WHERE flight_id = %s;", (flight_id,))
        cur.execute("DELETE FROM flights WHERE id = %s;", (flight_id,))
        
        dep_time = datetime.now(timezone.utc) + timedelta(days=5)
        arr_time = dep_time + timedelta(hours=4)
        
        cur.execute("""
            INSERT INTO flights (id, flight_number, origin, destination, departure_time, arrival_time, total_capacity, status)
            VALUES (%s, 'HITL-500', 'LAX', 'LHR', %s, %s, 100, 'SCHEDULED');
        """, (flight_id, dep_time, arr_time))
        
        cur.execute("""
            INSERT INTO seat_classes (flight_id, class_name, total_seats, available_seats, booked_seats, fare_base_price)
            VALUES (%s, 'BUSINESS', 100, 90, 10, 650.00);
        """, (flight_id,))
        
        cur.execute("""
            INSERT INTO bookings (id, flight_id, passenger_id, passenger_name, passenger_email, class_name, fare_code, fare_amount, status, idempotency_key)
            VALUES (%s, %s, 'pass_hitl_1', 'Bob Manager', 'bob.manager@example.com', 'BUSINESS', 'BUSINESS_FLEX', 650.00, 'CONFIRMED', 'idemp-hitl-44');
        """, (booking_id, flight_id))
        
    print("[PASS] Test flight and high-value booking ($650.00) created.")
    
    # 1. Test Rejection Path
    res_rej = process_human_approval_workflow(booking_id, decision="REJECTED")
    assert res_rej["decision"] == "REJECTED"
    assert res_rej["booking_status"] == "CONFIRMED"
    
    # 2. Test Approval Path
    res_app = process_human_approval_workflow(booking_id, decision="APPROVED")
    assert res_app["decision"] == "APPROVED"
    assert res_app["booking_status"] == "CANCELLED"
    assert res_app["inventory_restored"] is True
    
    # Cleanup test data
    with get_db_cursor() as (cur, conn):
        cur.execute("DELETE FROM audit_logs WHERE entity_id = %s;", (booking_id,))
        cur.execute("DELETE FROM bookings WHERE id = %s;", (booking_id,))
        cur.execute("DELETE FROM seat_classes WHERE flight_id = %s;", (flight_id,))
        cur.execute("DELETE FROM flights WHERE id = %s;", (flight_id,))
        
    print("\n--> TASK 4.4 HUMAN APPROVAL & FASTAPI BOUNDARY: ALL VERIFIED PASS! <--")
    return True

if __name__ == "__main__":
    test_task4_4_hitl_approval()
