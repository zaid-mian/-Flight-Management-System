from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from app.database import get_db_cursor
from app.mcp.approval_security import generate_approval_token, verify_approval_token

router = APIRouter(prefix="/api/v1/admin", tags=["Admin Operations & HITL Boundary"])

# --- SCHEMAS ---
class ApprovalProcessInput(BaseModel):
    booking_id: str = Field(..., description="Target booking ID")
    action: str = Field(..., description="APPROVE or REJECT")
    reviewer_id: Optional[str] = Field("supervisor_admin", description="Reviewer actor identifier")
    reason: Optional[str] = Field("Supervisor review completed", description="Decision rationale")

class OpsOverviewResponse(BaseModel):
    waitlist_candidates: List[Dict[str, Any]]
    pending_escalations: List[Dict[str, Any]]
    fraud_flags: List[Dict[str, Any]]
    recent_audit_logs: List[Dict[str, Any]]

# --- READ-ONLY OPS OVERVIEW ENDPOINT ---
@router.get("/ops-overview", response_model=OpsOverviewResponse)
def get_ops_overview():
    """Read-only operational overview fetching waitlist, escalations, fraud flags, and audit trail."""
    try:
        with get_db_cursor(commit_on_success=False) as (cur, conn):
            # 1. Waitlist Candidates
            cur.execute("""
                SELECT id::text, flight_id::text, passenger_id, passenger_name, passenger_email, class_name, priority_score, loyalty_tier, status, created_at
                FROM waitlist
                ORDER BY priority_score DESC, created_at ASC
                LIMIT 20;
            """)
            waitlist_rows = cur.fetchall()
            waitlist_list = [
                {
                    "id": r["id"],
                    "flight_id": r["flight_id"],
                    "passenger_id": r["passenger_id"],
                    "passenger_name": r["passenger_name"],
                    "passenger_email": r["passenger_email"],
                    "class_name": r["class_name"],
                    "priority_score": r["priority_score"],
                    "loyalty_tier": r["loyalty_tier"],
                    "status": r["status"],
                    "created_at": r["created_at"].isoformat() if r.get("created_at") else None
                } for r in waitlist_rows
            ]

            # 2. Escalations / Refund Requests
            cur.execute("""
                SELECT e.id::text, e.booking_id::text, e.requested_by, e.reason, e.refund_amount, e.status, e.created_at, b.passenger_name, b.passenger_email, b.fare_amount
                FROM escalation_requests e
                LEFT JOIN bookings b ON e.booking_id = b.id
                ORDER BY e.created_at DESC
                LIMIT 20;
            """)
            escalation_rows = cur.fetchall()
            escalations_list = [
                {
                    "id": r["id"],
                    "booking_id": r["booking_id"],
                    "requested_by": r["requested_by"],
                    "reason": r["reason"],
                    "refund_amount": float(r["refund_amount"]) if r.get("refund_amount") is not None else 0.0,
                    "status": r["status"],
                    "passenger_name": r.get("passenger_name") or "N/A",
                    "passenger_email": r.get("passenger_email") or "N/A",
                    "created_at": r["created_at"].isoformat() if r.get("created_at") else None
                } for r in escalation_rows
            ]

            # 3. Fraud Flags
            cur.execute("""
                SELECT f.id::text, f.booking_id::text, b.passenger_email, f.risk_score, f.risk_reasons, f.status, f.created_at
                FROM fraud_flags f
                LEFT JOIN bookings b ON f.booking_id = b.id
                ORDER BY f.created_at DESC
                LIMIT 20;
            """)
            fraud_rows = cur.fetchall()
            fraud_list = [
                {
                    "id": r["id"],
                    "booking_id": r["booking_id"],
                    "passenger_email": r.get("passenger_email") or "N/A",
                    "risk_score": r["risk_score"],
                    "risk_reasons": r["risk_reasons"],
                    "status": r["status"],
                    "created_at": r["created_at"].isoformat() if r.get("created_at") else None
                } for r in fraud_rows
            ]

            # 4. Recent Audit Logs
            cur.execute("""
                SELECT id::text, actor_type, actor_id, action, entity_name, entity_id::text, payload_changes, created_at
                FROM audit_logs
                ORDER BY created_at DESC
                LIMIT 25;
            """)
            audit_rows = cur.fetchall()
            audit_list = [
                {
                    "id": r["id"],
                    "actor_type": r["actor_type"],
                    "actor_id": r["actor_id"],
                    "action": r["action"],
                    "entity_name": r["entity_name"],
                    "entity_id": r["entity_id"],
                    "payload_changes": r["payload_changes"],
                    "created_at": r["created_at"].isoformat() if r.get("created_at") else None
                } for r in audit_rows
            ]

            return OpsOverviewResponse(
                waitlist_candidates=waitlist_list,
                pending_escalations=escalations_list,
                fraud_flags=fraud_list,
                recent_audit_logs=audit_list
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve ops overview: {str(e)}")

# --- AUTHORITATIVE HITL REVIEWER APPROVAL / REJECTION BOUNDARY ---
@router.post("/process-approval")
def process_human_approval(input_data: ApprovalProcessInput):
    """Authoritative backend boundary for supervisor HITL refund approval/rejection. Verifies HMAC token server-side."""
    booking_id = input_data.booking_id
    action_type = input_data.action.upper()
    reviewer = input_data.reviewer_id or "supervisor_admin"
    reason = input_data.reason or "Supervisor decision"

    if action_type not in ["APPROVE", "REJECT"]:
        raise HTTPException(status_code=400, detail="Action must be 'APPROVE' or 'REJECT'")

    try:
        with get_db_cursor(commit_on_success=True) as (cur, conn):
            # 1. Lock Target Booking
            cur.execute("""
                SELECT id, flight_id, passenger_id, passenger_name, passenger_email, class_name, status, fare_amount
                FROM bookings
                WHERE id::text = %s
                FOR UPDATE;
            """, (booking_id,))
            b = cur.fetchone()
            if not b:
                raise HTTPException(status_code=404, detail=f"Booking '{booking_id}' not found.")

            if action_type == "REJECT":
                # Rejection Path: 0 database booking/inventory mutations!
                cur.execute("""
                    UPDATE escalation_requests
                    SET status = 'REJECTED', reviewed_by = %s, updated_at = NOW()
                    WHERE booking_id::text = %s;
                """, (reviewer, str(b["id"])))

                cur.execute("""
                    INSERT INTO audit_logs (actor_type, actor_id, action, entity_name, entity_id, payload_changes)
                    VALUES ('HUMAN_SUPERVISOR', %s, 'REFUND_REQUEST_REJECTED', 'bookings', %s, %s);
                """, (reviewer, str(b["id"]), f'{{"reason": "{reason}"}}'))

                return {
                    "booking_id": str(b["id"]),
                    "action": "REJECTED",
                    "status": b["status"],
                    "inventory_restored": False,
                    "message": "Refund request rejected by supervisor. Booking remains active."
                }

            else:  # APPROVE
                # Generate and verify HMAC token server-side
                server_token = generate_approval_token(booking_id=str(b["id"]), action="REFUND")
                verify_res = verify_approval_token(server_token, expected_booking_id=str(b["id"]), expected_action="REFUND")
                if not verify_res.get("valid"):
                    raise HTTPException(status_code=403, detail=f"Security verification failed: {verify_res.get('reason')}")

                # Check if already cancelled
                if b["status"] in ['CANCELLED', 'REFUNDED']:
                    return {
                        "booking_id": str(b["id"]),
                        "action": "APPROVED",
                        "status": b["status"],
                        "inventory_restored": False,
                        "message": "Booking is already cancelled. Zero duplicate inventory restoration."
                    }

                # Update booking status to CANCELLED
                cur.execute("""
                    UPDATE bookings
                    SET status = 'CANCELLED', updated_at = NOW()
                    WHERE id = %s;
                """, (b["id"],))

                # Update escalation requests
                cur.execute("""
                    UPDATE escalation_requests
                    SET status = 'APPROVED', reviewed_by = %s, updated_at = NOW()
                    WHERE booking_id = %s;
                """, (reviewer, b["id"]))

                # Restore seat class inventory
                cur.execute("""
                    SELECT id, available_seats, booked_seats
                    FROM seat_classes
                    WHERE flight_id = %s AND class_name = %s
                    FOR UPDATE;
                """, (str(b["flight_id"]), b["class_name"].upper()))
                sc = cur.fetchone()
                if sc:
                    cur.execute("""
                        UPDATE seat_classes
                        SET available_seats = available_seats + 1,
                            booked_seats = GREATEST(0, booked_seats - 1),
                            updated_at = NOW()
                        WHERE id = %s;
                    """, (sc["id"],))

                # Audit Log
                cur.execute("""
                    INSERT INTO audit_logs (actor_type, actor_id, action, entity_name, entity_id, payload_changes)
                    VALUES ('HUMAN_SUPERVISOR', %s, 'REFUND_APPROVED_AND_CANCELLED', 'bookings', %s, %s);
                """, (reviewer, str(b["id"]), f'{{"reason": "{reason}", "hmac_verified": true}}'))

                return {
                    "booking_id": str(b["id"]),
                    "action": "APPROVED",
                    "status": "CANCELLED",
                    "inventory_restored": True,
                    "message": "Refund approved by supervisor. Booking cancelled and inventory restored."
                }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process approval: {str(e)}")
