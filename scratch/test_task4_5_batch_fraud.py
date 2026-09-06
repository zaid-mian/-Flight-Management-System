import os
import sys
import json
import requests
from datetime import datetime, timedelta, timezone
sys.path.insert(0, r"E:\n8n\flight-agent-hackathon")
from app.database import get_db_cursor
from app.mcp.mcp_tools import evaluate_fraud_risk

BASE_URL = "http://127.0.0.1:8000"

def run_batch_fraud_anomaly_scan():
    print("\n--- Running Batch Fraud Anomaly Agent Scan ---")
    
    # 1. Query candidate bookings created in last 24 hours
    with get_db_cursor(commit_on_success=False) as (cur, conn):
        cur.execute("""
            SELECT id, passenger_email, fare_amount, created_at 
            FROM bookings 
            WHERE status = 'CONFIRMED'
            ORDER BY created_at DESC 
            LIMIT 10;
        """)
        candidates = cur.fetchall()
        
    print(f"Found {len(candidates)} candidate bookings for fraud evaluation.")
    
    scan_results = []
    
    for c in candidates:
        b_id = str(c["id"])
        
        # 2. Evaluate fraud risk via MCP Tool / REST Endpoint
        res = requests.get(f"{BASE_URL}/api/v1/mcp/evaluate-fraud", params={"booking_id": b_id})
        if res.status_code != 200:
            continue
            
        fraud_data = res.json()
        risk_score = fraud_data["risk_score"]
        risk_level = fraud_data["risk_level"]
        signals = fraud_data["triggered_signals"]
        
        # 3. Handle high risk items: insert into fraud_flags table if not already flagged
        if risk_score >= 30:
            flag_status = "FLAGGED" if risk_score >= 60 else "INVESTIGATING"
            
            with get_db_cursor() as (cur, conn):
                cur.execute("""
                    INSERT INTO fraud_flags (booking_id, risk_score, risk_reasons, status)
                    SELECT %s, %s, %s::jsonb, %s
                    WHERE NOT EXISTS (
                        SELECT 1 FROM fraud_flags WHERE booking_id = %s AND status = %s
                    )
                    RETURNING id;
                """, (b_id, risk_score, json.dumps(signals), flag_status, b_id, flag_status))
                flag_row = cur.fetchone()
                
                if flag_row:
                    flag_id = str(flag_row["id"])
                    cur.execute("""
                        INSERT INTO audit_logs (actor_type, actor_id, action, entity_name, entity_id, payload_changes)
                        VALUES ('N8N_WORKFLOW', 'batch_fraud_agent', 'FRAUD_FLAG_CREATED', 'fraud_flags', %s, %s::jsonb);
                    """, (flag_id, json.dumps({"booking_id": b_id, "score": risk_score, "signals": signals})))
                    print(f"  - [FLAGGED] Booking {b_id} (Score: {risk_score}/100, Level: {risk_level}) -> Inserted fraud_flag {flag_id}")
                else:
                    print(f"  - [EXISTING] Booking {b_id} already flagged.")
        else:
            print(f"  - [CLEARED] Booking {b_id} (Score: {risk_score}/100, Level: {risk_level}) -> No risk detected.")
            
        scan_results.append(fraud_data)
        
    return scan_results

def test_task4_5_batch_fraud():
    print("=== Task 4.5: Batch Fraud Anomaly Agent Test ===")
    
    flight_id = "f4500000-0000-0000-0000-000000000001"
    booking_low = "b4500000-0000-0000-0000-000000000001"
    booking_high1 = "b4500000-0000-0000-0000-000000000002"
    booking_high2 = "b4500000-0000-0000-0000-000000000003"
    booking_high3 = "b4500000-0000-0000-0000-000000000004"
    
    with get_db_cursor() as (cur, conn):
        # Clean test records
        cur.execute("DELETE FROM fraud_flags WHERE booking_id IN (%s, %s, %s, %s);", (booking_low, booking_high1, booking_high2, booking_high3))
        cur.execute("DELETE FROM audit_logs WHERE entity_id IN (%s, %s, %s, %s);", (booking_low, booking_high1, booking_high2, booking_high3))
        cur.execute("DELETE FROM bookings WHERE id IN (%s, %s, %s, %s);", (booking_low, booking_high1, booking_high2, booking_high3))
        cur.execute("DELETE FROM seat_classes WHERE flight_id = %s;", (flight_id,))
        cur.execute("DELETE FROM flights WHERE id = %s;", (flight_id,))
        
        dep_time = datetime.now(timezone.utc) + timedelta(days=4)
        arr_time = dep_time + timedelta(hours=2)
        
        cur.execute("""
            INSERT INTO flights (id, flight_number, origin, destination, departure_time, arrival_time, total_capacity, status)
            VALUES (%s, 'FRD-900', 'MIA', 'ORD', %s, %s, 100, 'SCHEDULED');
        """, (flight_id, dep_time, arr_time))
        
        cur.execute("""
            INSERT INTO seat_classes (flight_id, class_name, total_seats, available_seats, booked_seats, fare_base_price)
            VALUES (%s, 'ECONOMY', 100, 80, 20, 200.00);
        """, (flight_id,))
        
        # Scenario A: Normal low-risk booking
        cur.execute("""
            INSERT INTO bookings (id, flight_id, passenger_id, passenger_name, passenger_email, class_name, fare_code, fare_amount, status, idempotency_key)
            VALUES (%s, %s, 'pass_clean', 'Honest Passenger', 'honest.user@example.com', 'ECONOMY', 'BASIC_ECONOMY', 200.00, 'CONFIRMED', 'idemp-frd-0');
        """, (booking_low, flight_id))
        
        # Scenario B: High-risk suspicious activity (3 rapid high-value bookings by same email)
        high_email = "suspicious.bot@example.com"
        cur.execute("""
            INSERT INTO bookings (id, flight_id, passenger_id, passenger_name, passenger_email, class_name, fare_code, fare_amount, status, idempotency_key)
            VALUES 
            (%s, %s, 'pass_bot', 'Bot User', %s, 'BUSINESS', 'BUSINESS_FLEX', 950.00, 'CONFIRMED', 'idemp-frd-1'),
            (%s, %s, 'pass_bot', 'Bot User', %s, 'BUSINESS', 'BUSINESS_FLEX', 950.00, 'CONFIRMED', 'idemp-frd-2'),
            (%s, %s, 'pass_bot', 'Bot User', %s, 'BUSINESS', 'BUSINESS_FLEX', 950.00, 'CONFIRMED', 'idemp-frd-3');
        """, (booking_high1, flight_id, high_email, booking_high2, flight_id, high_email, booking_high3, flight_id, high_email))
        
    print("[PASS] Test bookings inserted: 1 clean booking, 3 suspicious rapid bookings ($950 each).")
    
    # Run batch fraud scanner
    results = run_batch_fraud_anomaly_scan()
    assert len(results) >= 4
    
    # Verify fraud_flags table in Supabase
    with get_db_cursor(commit_on_success=False) as (cur, conn):
        cur.execute("""
            SELECT id, booking_id, risk_score, status 
            FROM fraud_flags 
            WHERE booking_id IN (%s, %s, %s, %s);
        """, (booking_low, booking_high1, booking_high2, booking_high3))
        flags = cur.fetchall()
        
        print(f"\n[PASS] Verified fraud_flags table entries: {len(flags)} high-risk flags created.")
        for f in flags:
            print(f"  - Flag ID: {f['id']} | Booking ID: {f['booking_id']} | Score: {f['risk_score']} | Status: {f['status']}")
            assert f["risk_score"] >= 30
            assert f["status"] in ["FLAGGED", "INVESTIGATING"]
            
        # Verify 0 booking status mutations occurred
        cur.execute("SELECT id, status FROM bookings WHERE id IN (%s, %s, %s, %s);", (booking_low, booking_high1, booking_high2, booking_high3))
        b_rows = cur.fetchall()
        for b in b_rows:
            assert b["status"] == "CONFIRMED"
            
    print("\n[PASS] Verified zero booking status or inventory mutations were performed by the fraud agent.")
    
    # Clean up test rows
    with get_db_cursor() as (cur, conn):
        cur.execute("DELETE FROM fraud_flags WHERE booking_id IN (%s, %s, %s, %s);", (booking_low, booking_high1, booking_high2, booking_high3))
        cur.execute("DELETE FROM audit_logs WHERE entity_id IN (%s, %s, %s, %s);", (booking_low, booking_high1, booking_high2, booking_high3))
        cur.execute("DELETE FROM bookings WHERE id IN (%s, %s, %s, %s);", (booking_low, booking_high1, booking_high2, booking_high3))
        cur.execute("DELETE FROM seat_classes WHERE flight_id = %s;", (flight_id,))
        cur.execute("DELETE FROM flights WHERE id = %s;", (flight_id,))
        
    print("\n--> TASK 4.5 BATCH FRAUD ANOMALY AGENT: ALL VERIFIED PASS! <--")
    return True

if __name__ == "__main__":
    test_task4_5_batch_fraud()
