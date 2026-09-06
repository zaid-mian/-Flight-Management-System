from fastapi import APIRouter, HTTPException, status
from datetime import datetime, timedelta, timezone
from app.database import get_db_cursor
from app.schemas import SeatHoldCreateInput, SeatHoldResponse

router = APIRouter(prefix="/api/v1/holds", tags=["Holds"])

# --- TASK 3.4: ATOMIC SEAT HOLD ENDPOINT ---
@router.post("", response_model=SeatHoldResponse, status_code=status.HTTP_201_CREATED)
def create_seat_hold(hold_in: SeatHoldCreateInput):
    try:
        with get_db_cursor(commit_on_success=True) as (cur, conn):
            # 1. Row Lock using FOR UPDATE on seat_classes
            cur.execute("""
                SELECT id, total_seats, available_seats, booked_seats 
                FROM seat_classes 
                WHERE flight_id = %s AND class_name = %s 
                FOR UPDATE;
            """, (str(hold_in.flight_id), hold_in.class_name.upper()))
            
            sc = cur.fetchone()
            if not sc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Seat class '{hold_in.class_name}' not found for flight '{hold_in.flight_id}'."
                )

            # 2. Inventory check
            if sc["available_seats"] < hold_in.seat_count:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insufficient available seats ({sc['available_seats']} available, {hold_in.seat_count} requested)."
                )

            # 3. Decrement available seats
            cur.execute("""
                UPDATE seat_classes 
                SET available_seats = available_seats - %s, updated_at = NOW()
                WHERE id = %s;
            """, (hold_in.seat_count, sc["id"]))

            # 4. Insert seat_holds record
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=hold_in.hold_duration_minutes)
            cur.execute("""
                INSERT INTO seat_holds (flight_id, class_name, passenger_id, seat_count, expires_at, status)
                VALUES (%s, %s, %s, %s, %s, 'ACTIVE')
                RETURNING id AS hold_id, flight_id, class_name, passenger_id, seat_count, expires_at, status;
            """, (
                str(hold_in.flight_id),
                hold_in.class_name.upper(),
                hold_in.passenger_id,
                hold_in.seat_count,
                expires_at
            ))
            
            hold_res = cur.fetchone()

            # 5. Audit Log
            cur.execute("""
                INSERT INTO audit_logs (actor_type, actor_id, action, entity_name, entity_id, payload_changes)
                VALUES ('FASTAPI_USER', %s, 'SEAT_HOLD_CREATED', 'seat_holds', %s, %s);
            """, (hold_in.passenger_id, str(hold_res["hold_id"]), f'{{"seat_count": {hold_in.seat_count}}}'))

            return SeatHoldResponse(**hold_res)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Atomic seat hold failed: {str(e)}")
