import os
import sys
import json
from datetime import datetime, timezone
from dotenv import dotenv_values
from pinecone import Pinecone
from sentence_transformers import SentenceTransformer
from app.database import get_db_cursor
from app.config import settings

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")
INDEX_NAME = "flight-policies"
MODEL_NAME = "all-MiniLM-L6-v2"

# Lazy-loaded embedding model and Pinecone client
_embedder = None
_pinecone_index = None

def get_embedder():
    global _embedder
    if _embedder is None:
        try:
            _embedder = SentenceTransformer(MODEL_NAME, local_files_only=True)
        except Exception:
            _embedder = SentenceTransformer(MODEL_NAME)
    return _embedder

def get_pinecone_index():
    global _pinecone_index
    if _pinecone_index is None:
        api_key = os.getenv("PINECONE_API_KEY") or os.getenv("PINECORN_APII")
        if not api_key:
            env = dotenv_values(ENV_PATH) if os.path.exists(ENV_PATH) else {}
            api_key = env.get("PINECONE_API_KEY") or env.get("PINECORN_APII")
        if not api_key:
            raise ValueError("PINECONE_API_KEY missing from environment variables or .env file")
        pc = Pinecone(api_key=api_key)
        _pinecone_index = pc.Index(INDEX_NAME)
    return _pinecone_index



def get_booking_context(booking_id: str):
    """Retrieves authoritative booking, passenger, flight, seat class, and audit context."""
    with get_db_cursor(commit_on_success=False) as (cur, conn):
        cur.execute("""
            SELECT 
                b.id AS booking_id,
                b.flight_id,
                b.passenger_id,
                b.passenger_name,
                b.passenger_email,
                b.class_name,
                b.fare_code,
                b.status AS booking_status,
                b.fare_amount,
                b.idempotency_key,
                b.created_at AS booking_created_at,
                f.flight_number,
                f.origin,
                f.destination,
                f.departure_time,
                f.arrival_time,
                f.status AS flight_status,
                sc.fare_base_price
            FROM bookings b
            JOIN flights f ON b.flight_id = f.id
            LEFT JOIN seat_classes sc ON b.flight_id = sc.flight_id AND b.class_name = sc.class_name
            WHERE b.id::text = %s OR b.idempotency_key = %s;
        """, (booking_id, booking_id))
        row = cur.fetchone()
        
        if not row:
            return {"found": False, "error": f"Booking '{booking_id}' not found"}
            
        booking_data = {
            "found": True,
            "booking": {
                "id": str(row["booking_id"]),
                "flight_id": str(row["flight_id"]),
                "passenger_id": str(row["passenger_id"]) if row.get("passenger_id") else None,
                "passenger_name": row["passenger_name"],
                "passenger_email": row["passenger_email"],
                "class_name": row["class_name"],
                "fare_code": row["fare_code"],
                "status": row["booking_status"],
                "fare_amount": float(row["fare_amount"]),
                "idempotency_key": row["idempotency_key"],
                "created_at": row["booking_created_at"].isoformat() if row.get("booking_created_at") else None
            },
            "flight": {
                "flight_number": row["flight_number"],
                "origin": row["origin"],
                "destination": row["destination"],
                "departure_time": row["departure_time"].isoformat() if row.get("departure_time") else None,
                "arrival_time": row["arrival_time"].isoformat() if row.get("arrival_time") else None,
                "status": row["flight_status"]
            },
            "fare_base_price": float(row["fare_base_price"]) if row.get("fare_base_price") is not None else None
        }
        
        # Fetch recent audit logs for this booking
        cur.execute("""
            SELECT id, actor_type, action, entity_name, entity_id, payload_changes, created_at
            FROM audit_logs
            WHERE entity_id::text = %s
            ORDER BY created_at DESC
            LIMIT 5;
        """, (str(row["booking_id"]),))
        audit_rows = cur.fetchall()
        booking_data["audit_history"] = [
            {
                "id": str(r["id"]),
                "actor_type": r["actor_type"],
                "action": r["action"],
                "entity_name": r["entity_name"],
                "entity_id": r["entity_id"],
                "payload_changes": r["payload_changes"],
                "created_at": r["created_at"].isoformat() if r.get("created_at") else None
            } for r in audit_rows
        ]
        
        return booking_data


def query_pinecone_policy(query: str, top_k: int = 3):
    """Embeds policy query and retrieves matching policy chunks from Pinecone."""
    embedder = get_embedder()
    index = get_pinecone_index()
    
    query_vector = embedder.encode(query).tolist()
    res = index.query(vector=query_vector, top_k=top_k, include_metadata=True)
    
    matches = []
    for m in res.matches:
        matches.append({
            "score": round(float(m.score), 4),
            "chunk_id": m.id,
            "source": m.metadata.get("source", ""),
            "category": m.metadata.get("category", ""),
            "text": m.metadata.get("text", ""),
            "version": m.metadata.get("version", "2026.1")
        })
        
    return {
        "query": query,
        "results_count": len(matches),
        "matches": matches,
        "is_sufficient_evidence": len(matches) > 0 and matches[0]["score"] >= 0.40
    }


def calculate_fare_refund_entitlement(booking_id: str):
    """100% deterministic refund calculation engine based on explicit airline policy."""
    context = get_booking_context(booking_id)
    if not context.get("found"):
        return {"error": context.get("error")}
        
    booking = context["booking"]
    flight = context["flight"]
    
    fare_amount = booking["fare_amount"]
    class_name = booking["class_name"].upper()
    fare_code = booking.get("fare_code", "").upper()
    
    # Parse dates
    now = datetime.now(timezone.utc)
    
    booking_created_at = datetime.fromisoformat(booking["created_at"]) if booking["created_at"] else now
    if booking_created_at.tzinfo is None:
        booking_created_at = booking_created_at.replace(tzinfo=timezone.utc)
        
    departure_time = datetime.fromisoformat(flight["departure_time"]) if flight["departure_time"] else now
    if departure_time.tzinfo is None:
        departure_time = departure_time.replace(tzinfo=timezone.utc)
        
    hours_since_purchase = (now - booking_created_at).total_seconds() / 3600.0
    hours_until_departure = (departure_time - now).total_seconds() / 3600.0
    days_until_departure = (departure_time - now).days
    
    eligible_refund = 0.0
    cancellation_fee = 0.0
    rule_applied = ""
    credit_voucher_eligible = False
    voucher_amount = 0.0
    
    # 1. 24-Hour Grace Period
    if hours_since_purchase <= 24.0 and days_until_departure >= 7:
        eligible_refund = fare_amount
        cancellation_fee = 0.0
        rule_applied = "24-Hour Grace Period (100% full cash refund, $0 fee)"
    elif hours_until_departure > 48.0:
        if "FLEX" in class_name or "BUSINESS" in class_name or "FLEX" in fare_code:
            cancellation_fee = 25.0
            eligible_refund = max(0.0, fare_amount - cancellation_fee)
            rule_applied = ">48h Departure - Flex/Business Class (100% refund minus $25 fee)"
        elif "STANDARD" in class_name or "ECONOMY" in class_name:
            cancellation_fee = round(fare_amount * 0.20, 2)
            eligible_refund = round(fare_amount * 0.80, 2)
            rule_applied = ">48h Departure - Standard Economy (80% refund, 20% cancellation fee)"
        else: # BASIC
            cancellation_fee = fare_amount
            eligible_refund = 0.0
            credit_voucher_eligible = True
            voucher_amount = round(fare_amount * 0.50, 2)
            rule_applied = ">48h Departure - Basic Class (0% cash refund, 50% voucher credit)"
    elif 24.0 <= hours_until_departure <= 48.0:
        if "FLEX" in class_name or "BUSINESS" in class_name or "FLEX" in fare_code:
            eligible_refund = round(fare_amount * 0.90, 2)
            cancellation_fee = round(fare_amount * 0.10, 2)
            rule_applied = "24-48h Departure - Flex/Business Class (90% refund, 10% fee)"
        elif "STANDARD" in class_name or "ECONOMY" in class_name:
            eligible_refund = round(fare_amount * 0.50, 2)
            cancellation_fee = round(fare_amount * 0.50, 2)
            rule_applied = "24-48h Departure - Standard Economy (50% refund, 50% fee)"
        else:
            eligible_refund = 0.0
            cancellation_fee = fare_amount
            rule_applied = "24-48h Departure - Basic Class (Non-refundable)"
    else: # < 24 hours
        eligible_refund = 0.0
        cancellation_fee = fare_amount
        rule_applied = "<24h Departure - All Classes (100% penalty, cash non-refundable)"
        
    # Mandatory Supervisor Approval Threshold rule ($500 limit)
    requires_human_approval = eligible_refund > 500.0 or credit_voucher_eligible
    approval_reasons = []
    if eligible_refund > 500.0:
        approval_reasons.append("Eligible refund exceeds $500.00 USD supervisor threshold")
    if credit_voucher_eligible:
        approval_reasons.append("Credit voucher issuance requires review")
        
    return {
        "booking_id": booking["id"],
        "passenger_name": booking["passenger_name"],
        "passenger_email": booking["passenger_email"],
        "fare_amount": fare_amount,
        "class_name": booking["class_name"],
        "fare_code": booking["fare_code"],
        "hours_until_departure": round(hours_until_departure, 1),
        "eligible_refund_amount": eligible_refund,
        "cancellation_fee": cancellation_fee,
        "credit_voucher_eligible": credit_voucher_eligible,
        "voucher_amount": voucher_amount,
        "rule_applied": rule_applied,
        "requires_human_approval": requires_human_approval,
        "approval_reason": "; ".join(approval_reasons) if approval_reasons else "Standard automated calculation"
    }


def evaluate_fraud_risk(booking_id: str):
    """Controlled deterministic fraud/anomaly evaluation tool inspecting database metrics."""
    context = get_booking_context(booking_id)
    if not context.get("found"):
        return {"error": context.get("error")}
        
    booking = context["booking"]
    passenger_email = booking["passenger_email"]
    
    score = 0
    triggered_signals = []
    
    with get_db_cursor(commit_on_success=False) as (cur, conn):
        # Signal 1: Passenger high booking velocity (more than 3 bookings in last 24h)
        cur.execute("""
            SELECT COUNT(*) AS total
            FROM bookings 
            WHERE passenger_email = %s AND created_at > NOW() - INTERVAL '24 hours';
        """, (passenger_email,))
        recent_bookings_count = cur.fetchone()["total"]
        if recent_bookings_count >= 3:
            score += 35
            triggered_signals.append(f"High booking velocity ({recent_bookings_count} bookings in 24h)")
            
        # Signal 2: High cancellation history
        cur.execute("""
            SELECT COUNT(*) AS total 
            FROM bookings 
            WHERE passenger_email = %s AND status = 'CANCELLED';
        """, (passenger_email,))
        cancellations_count = cur.fetchone()["total"]
        if cancellations_count >= 2:
            score += 25
            triggered_signals.append(f"Frequent cancellation history ({cancellations_count} cancelled bookings)")
            
        # Signal 3: High fare transaction (> $800)
        if booking["fare_amount"] >= 800.0:
            score += 20
            triggered_signals.append(f"High-value fare transaction (${booking['fare_amount']:.2f})")
            
        # Signal 4: Rapid booking creation within 1 hour of departure
        flight = context["flight"]
        if flight.get("departure_time") and booking.get("created_at"):
            dep = datetime.fromisoformat(flight["departure_time"])
            b_created = datetime.fromisoformat(booking["created_at"])
            if dep.tzinfo is None:
                dep = dep.replace(tzinfo=timezone.utc)
            if b_created.tzinfo is None:
                b_created = b_created.replace(tzinfo=timezone.utc)
            mins_to_dep = (dep - b_created).total_seconds() / 60.0
            if mins_to_dep < 60:
                score += 30
                triggered_signals.append(f"Last-minute booking created {mins_to_dep:.1f} mins before departure")

    score = min(score, 100)
    if score >= 60:
        risk_level = "HIGH"
        rec = "FLAG_FOR_HUMAN_REVIEW"
        req_review = True
    elif score >= 30:
        risk_level = "MEDIUM"
        rec = "MONITOR_ACTIVITY"
        req_review = False
    else:
        risk_level = "LOW"
        rec = "ALLOW_TRANSACTION"
        req_review = False
        
    return {
        "booking_id": booking["id"],
        "passenger_email": passenger_email,
        "risk_score": score,
        "risk_level": risk_level,
        "triggered_signals": triggered_signals,
        "recommended_action": rec,
        "requires_human_review": req_review,
        "explanation": f"Fraud risk score is {score}/100 based on {len(triggered_signals)} triggered signals."
    }
