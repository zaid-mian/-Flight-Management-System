import os
import sys
sys.path.insert(0, r"E:\n8n\flight-agent-hackathon")
import requests
from datetime import datetime, timedelta, timezone
from app.database import get_db_cursor
from app.mcp.mcp_tools import (
    get_booking_context,
    query_pinecone_policy,
    calculate_fare_refund_entitlement,
    evaluate_fraud_risk
)

BASE_URL = "http://127.0.0.1:8000"

def test_task4_2_mcp_tools():
    print("=== Task 4.2: MCP Tools & Endpoints Verification ===")
    
    # 1. Setup test flight and booking in database for evaluation
    with get_db_cursor() as (cur, conn):
        flight_id = "f4200000-0000-0000-0000-000000000001"
        booking_id = "b4200000-0000-0000-0000-000000000001"
        
        # Clean existing test rows
        cur.execute("DELETE FROM audit_logs WHERE entity_id = %s;", (booking_id,))
        cur.execute("DELETE FROM bookings WHERE id = %s;", (booking_id,))
        cur.execute("DELETE FROM seat_classes WHERE flight_id = %s;", (flight_id,))
        cur.execute("DELETE FROM flights WHERE id = %s;", (flight_id,))
        
        # Insert test flight departing in 3 days (72h)
        dep_time = datetime.now(timezone.utc) + timedelta(days=3)
        arr_time = dep_time + timedelta(hours=3)
        
        cur.execute("""
            INSERT INTO flights (id, flight_number, origin, destination, departure_time, arrival_time, total_capacity, status)
            VALUES (%s, 'MCP-400', 'SFO', 'JFK', %s, %s, 100, 'SCHEDULED');
        """, (flight_id, dep_time, arr_time))
        
        cur.execute("""
            INSERT INTO seat_classes (flight_id, class_name, total_seats, available_seats, booked_seats, fare_base_price)
            VALUES (%s, 'ECONOMY', 100, 95, 5, 450.00);
        """, (flight_id,))
        
        cur.execute("""
            INSERT INTO bookings (id, flight_id, passenger_id, passenger_name, passenger_email, class_name, fare_code, fare_amount, status, idempotency_key)
            VALUES (%s, %s, 'pass_mcp_1', 'Alice Tester', 'alice.mcp@example.com', 'ECONOMY', 'FLEXIBLE_ECONOMY', 450.00, 'CONFIRMED', 'idemp-mcp-42');
        """, (booking_id, flight_id))
        
        cur.execute("""
            INSERT INTO audit_logs (actor_type, actor_id, action, entity_name, entity_id, payload_changes)
            VALUES ('SYSTEM', 'mcp_test', 'BOOKING_CREATED', 'bookings', %s, '{"test": true}'::jsonb);
        """, (booking_id,))

    print("[PASS] Test flight and booking created in database.")
    
    # --- Tool 1: get_booking_context ---
    print("\n--- Testing Tool 1: get_booking_context ---")
    ctx = get_booking_context(booking_id)
    assert ctx.get("found") is True
    assert ctx["booking"]["passenger_email"] == "alice.mcp@example.com"
    assert ctx["flight"]["flight_number"] == "MCP-400"
    print(f"  - Programmatic get_booking_context: PASS")
    
    # Test REST endpoint
    res = requests.get(f"{BASE_URL}/api/v1/mcp/get-booking-context", params={"booking_id": booking_id})
    assert res.status_code == 200, res.text
    assert res.json()["booking"]["id"] == booking_id
    print(f"  - REST API GET /api/v1/mcp/get-booking-context: PASS")
    
    # --- Tool 2: query_pinecone_policy ---
    print("\n--- Testing Tool 2: query_pinecone_policy ---")
    pol_res = query_pinecone_policy("What is the checked baggage weight limit for Economy Standard?", top_k=2)
    assert pol_res["results_count"] > 0
    assert "baggage" in pol_res["matches"][0]["category"].lower() or "baggage" in pol_res["matches"][0]["text"].lower()
    print(f"  - Policy Query: '{pol_res['query']}'")
    print(f"  - Top Match: {pol_res['matches'][0]['chunk_id']} (Score: {pol_res['matches'][0]['score']})")
    print(f"  - Programmatic query_pinecone_policy: PASS")
    
    # Test REST endpoint
    res = requests.post(f"{BASE_URL}/api/v1/mcp/query-policy", json={"query": "baggage allowance", "top_k": 2})
    assert res.status_code == 200, res.text
    assert len(res.json()["matches"]) > 0
    print(f"  - REST API POST /api/v1/mcp/query-policy: PASS")
    
    # --- Tool 3: calculate_fare_refund_entitlement ---
    print("\n--- Testing Tool 3: calculate_fare_refund_entitlement (100% Deterministic) ---")
    ref_res = calculate_fare_refund_entitlement(booking_id)
    print(f"  - Booking Fare: ${ref_res['fare_amount']:.2f}")
    print(f"  - Eligible Refund: ${ref_res['eligible_refund_amount']:.2f}")
    print(f"  - Cancellation Fee: ${ref_res['cancellation_fee']:.2f}")
    print(f"  - Rule Applied: {ref_res['rule_applied']}")
    print(f"  - Requires Human Approval: {ref_res['requires_human_approval']}")
    assert ref_res["eligible_refund_amount"] == 425.00  # Flex economy >48h ($450 - $25 fee)
    assert ref_res["cancellation_fee"] == 25.00
    print(f"  - Programmatic calculate_fare_refund_entitlement: PASS")
    
    # Test REST endpoint
    res = requests.get(f"{BASE_URL}/api/v1/mcp/calculate-refund", params={"booking_id": booking_id})
    assert res.status_code == 200, res.text
    assert res.json()["eligible_refund_amount"] == 425.00
    print(f"  - REST API GET /api/v1/mcp/calculate-refund: PASS")
    
    # --- Tool 4: evaluate_fraud_risk ---
    print("\n--- Testing Tool 4: evaluate_fraud_risk ---")
    fraud_res = evaluate_fraud_risk(booking_id)
    print(f"  - Passenger: {fraud_res['passenger_email']}")
    print(f"  - Risk Score: {fraud_res['risk_score']}/100")
    print(f"  - Risk Level: {fraud_res['risk_level']}")
    print(f"  - Triggered Signals: {fraud_res['triggered_signals']}")
    assert "risk_score" in fraud_res
    print(f"  - Programmatic evaluate_fraud_risk: PASS")
    
    # Test REST endpoint
    res = requests.get(f"{BASE_URL}/api/v1/mcp/evaluate-fraud", params={"booking_id": booking_id})
    assert res.status_code == 200, res.text
    assert res.json()["risk_level"] in ["LOW", "MEDIUM", "HIGH"]
    print(f"  - REST API GET /api/v1/mcp/evaluate-fraud: PASS")
    
    # Clean up test rows
    with get_db_cursor() as (cur, conn):
        cur.execute("DELETE FROM audit_logs WHERE entity_id = %s;", (booking_id,))
        cur.execute("DELETE FROM bookings WHERE id = %s;", (booking_id,))
        cur.execute("DELETE FROM seat_classes WHERE flight_id = %s;", (flight_id,))
        cur.execute("DELETE FROM flights WHERE id = %s;", (flight_id,))
        
    print("\n--> TASK 4.2 MCP TOOLS & REST API ENDPOINTS: ALL VERIFIED PASS! <--")
    return True

if __name__ == "__main__":
    test_task4_2_mcp_tools()
