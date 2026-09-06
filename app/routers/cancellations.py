from fastapi import APIRouter, HTTPException, status
from uuid import UUID
from app.database import get_db_cursor
from app.schemas import BookingCancelInput, CancellationResponse

router = APIRouter(prefix="/api/v1/bookings", tags=["Cancellations"])

# --- TASK 3.6: FLIGHT & BOOKING CANCELLATION ENDPOINT ---
@router.post("/cancel", response_model=CancellationResponse, status_code=status.HTTP_200_OK)
def cancel_booking(cancel_in: BookingCancelInput):
    try:
        with get_db_cursor(commit_on_success=True) as (cur, conn):
            # 1. Lock Target Booking Row using FOR UPDATE
            cur.execute("""
                SELECT id, flight_id, passenger_id, class_name, status, fare_amount 
                FROM bookings 
                WHERE id = %s 
                FOR UPDATE;
            """, (str(cancel_in.booking_id),))
            
            b = cur.fetchone()
            if not b:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Booking '{cancel_in.booking_id}' not found."
                )

            # 2. Check if already cancelled/refunded
            if b["status"] in ['CANCELLED', 'REFUNDED']:
                # Idempotent response: Booking is already cancelled, no duplicate inventory restoration
                # Retrieve last audit log for response
                cur.execute("""
                    SELECT id FROM audit_logs 
                    WHERE entity_id = %s AND action = 'BOOKING_CANCELLED' 
                    ORDER BY created_at DESC LIMIT 1;
                """, (str(b["id"]),))
                audit_row = cur.fetchone()
                audit_id = audit_row["id"] if audit_row else b["id"]

                return CancellationResponse(
                    booking_id=b["id"],
                    flight_id=b["flight_id"],
                    status=b["status"],
                    inventory_restored=False,  # Already restored previously
                    audit_log_id=audit_id
                )

            # 3. Update Booking Status to CANCELLED
            cur.execute("""
                UPDATE bookings 
                SET status = 'CANCELLED', updated_at = NOW() 
                WHERE id = %s;
            """, (str(b["id"]),))

            # 4. Lock & Restore Seat Class Inventory
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

            # 5. Insert Audit Log
            cur.execute("""
                INSERT INTO audit_logs (actor_type, actor_id, action, entity_name, entity_id, payload_changes)
                VALUES ('FASTAPI_USER', %s, 'BOOKING_CANCELLED', 'bookings', %s, %s)
                RETURNING id;
            """, (b["passenger_id"], str(b["id"]), f'{{"reason": "{cancel_in.reason}"}}'))
            
            audit_id = cur.fetchone()["id"]

            return CancellationResponse(
                booking_id=b["id"],
                flight_id=b["flight_id"],
                status="CANCELLED",
                inventory_restored=True,
                audit_log_id=audit_id
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Booking cancellation failed: {str(e)}")
