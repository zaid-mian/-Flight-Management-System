from fastapi import APIRouter, HTTPException, status
from datetime import datetime, timezone
from uuid import UUID
from app.database import get_db_cursor
from app.schemas import BookingCreateInput, BookingResponse, WaitlistConvertInput

router = APIRouter(prefix="/api/v1/bookings", tags=["Bookings"])

# --- TASK 3.5: ATOMIC BOOKING ENDPOINT (FOR UPDATE + IDEMPOTENCY) ---
@router.post("", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
def create_booking(booking_in: BookingCreateInput):
    try:
        with get_db_cursor(commit_on_success=True) as (cur, conn):
            # 1. Idempotency Check
            cur.execute("""
                SELECT id AS booking_id, flight_id, passenger_id, passenger_name, passenger_email, class_name, fare_code, fare_amount, status, idempotency_key, created_at
                FROM bookings 
                WHERE idempotency_key = %s;
            """, (booking_in.idempotency_key,))
            
            existing = cur.fetchone()
            if existing:
                # Idempotent response: Return existing booking record cleanly
                return BookingResponse(**existing)

            # 2. Check if booking via Hold
            if booking_in.hold_id:
                cur.execute("""
                    SELECT id, flight_id, class_name, seat_count, expires_at, status 
                    FROM seat_holds 
                    WHERE id = %s AND status = 'ACTIVE' 
                    FOR UPDATE;
                """, (str(booking_in.hold_id),))
                
                hold = cur.fetchone()
                if not hold:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Active seat hold '{booking_in.hold_id}' not found or already processed."
                    )
                
                # Check expiration
                now_utc = datetime.now(timezone.utc)
                if hold["expires_at"] < now_utc:
                    # Update hold status to EXPIRED
                    cur.execute("UPDATE seat_holds SET status = 'EXPIRED' WHERE id = %s;", (str(booking_in.hold_id),))
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Seat hold has expired."
                    )

                # Mark hold CONVERTED
                cur.execute("UPDATE seat_holds SET status = 'CONVERTED' WHERE id = %s;", (str(booking_in.hold_id),))
                
                # Increment booked_seats on seat_classes (available_seats was already decremented during hold creation)
                cur.execute("""
                    UPDATE seat_classes 
                    SET booked_seats = booked_seats + 1, updated_at = NOW()
                    WHERE flight_id = %s AND class_name = %s;
                """, (str(booking_in.flight_id), booking_in.class_name.upper()))

            else:
                # Direct booking: Row Lock on seat_classes using FOR UPDATE
                cur.execute("""
                    SELECT id, available_seats, booked_seats 
                    FROM seat_classes 
                    WHERE flight_id = %s AND class_name = %s 
                    FOR UPDATE;
                """, (str(booking_in.flight_id), booking_in.class_name.upper()))
                
                sc = cur.fetchone()
                if not sc:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Seat class '{booking_in.class_name}' not found for flight '{booking_in.flight_id}'."
                    )
                
                if sc["available_seats"] < 1:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="No seats available for booking."
                    )

                # Decrement available_seats, increment booked_seats
                cur.execute("""
                    UPDATE seat_classes 
                    SET available_seats = available_seats - 1, booked_seats = booked_seats + 1, updated_at = NOW()
                    WHERE id = %s;
                """, (sc["id"],))

            # 3. Create Booking Record
            cur.execute("""
                INSERT INTO bookings (flight_id, passenger_id, passenger_name, passenger_email, class_name, fare_code, fare_amount, status, idempotency_key)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'CONFIRMED', %s)
                RETURNING id AS booking_id, flight_id, passenger_id, passenger_name, passenger_email, class_name, fare_code, fare_amount, status, idempotency_key, created_at;
            """, (
                str(booking_in.flight_id),
                booking_in.passenger_id,
                booking_in.passenger_name,
                booking_in.passenger_email,
                booking_in.class_name.upper(),
                booking_in.fare_code,
                booking_in.fare_amount,
                booking_in.idempotency_key
            ))

            booking_res = cur.fetchone()

            # 4. Audit Log Entry
            cur.execute("""
                INSERT INTO audit_logs (actor_type, actor_id, action, entity_name, entity_id, payload_changes)
                VALUES ('FASTAPI_USER', %s, 'BOOKING_CREATED', 'bookings', %s, %s);
            """, (booking_in.passenger_id, str(booking_res["booking_id"]), f'{{"fare_amount": {booking_in.fare_amount}}}'))

            return BookingResponse(**booking_res)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Atomic booking failed: {str(e)}")

# --- PHASE 2.2 CALLBACK BOUNDARY: WAITLIST CONVERSION ENDPOINT ---
@router.post("/convert-waitlist", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
def convert_waitlist_to_booking(convert_in: WaitlistConvertInput):
    try:
        with get_db_cursor(commit_on_success=True) as (cur, conn):
            # 1. Idempotency Check
            cur.execute("""
                SELECT id AS booking_id, flight_id, passenger_id, passenger_name, passenger_email, class_name, fare_code, fare_amount, status, idempotency_key, created_at
                FROM bookings 
                WHERE idempotency_key = %s;
            """, (convert_in.idempotency_key,))
            existing = cur.fetchone()
            if existing:
                return BookingResponse(**existing)

            # 2. Lock Waitlist Entry
            cur.execute("""
                SELECT id, flight_id, passenger_id, passenger_name, passenger_email, class_name, status 
                FROM waitlist 
                WHERE id = %s AND status = 'PROMOTED' 
                FOR UPDATE;
            """, (str(convert_in.waitlist_id),))
            
            wl = cur.fetchone()
            if not wl:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Promoted waitlist entry '{convert_in.waitlist_id}' not found or already processed."
                )

            # 3. Lock Seat Class & Reserve Seat
            cur.execute("""
                SELECT id, available_seats, booked_seats, fare_base_price 
                FROM seat_classes 
                WHERE flight_id = %s AND class_name = %s 
                FOR UPDATE;
            """, (str(wl["flight_id"]), wl["class_name"].upper()))
            
            sc = cur.fetchone()
            if not sc or sc["available_seats"] < 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No seat available for waitlist conversion."
                )

            cur.execute("""
                UPDATE seat_classes 
                SET available_seats = available_seats - 1, booked_seats = booked_seats + 1, updated_at = NOW()
                WHERE id = %s;
            """, (sc["id"],))

            # 4. Insert Booking Record
            cur.execute("""
                INSERT INTO bookings (flight_id, passenger_id, passenger_name, passenger_email, class_name, fare_code, fare_amount, status, idempotency_key)
                VALUES (%s, %s, %s, %s, %s, 'FLEXIBLE_ECONOMY', %s, 'CONFIRMED', %s)
                RETURNING id AS booking_id, flight_id, passenger_id, passenger_name, passenger_email, class_name, fare_code, fare_amount, status, idempotency_key, created_at;
            """, (
                str(wl["flight_id"]),
                wl["passenger_id"],
                wl["passenger_name"],
                wl["passenger_email"],
                wl["class_name"].upper(),
                sc["fare_base_price"],
                convert_in.idempotency_key
            ))

            booking_res = cur.fetchone()

            # 5. Audit Log
            cur.execute("""
                INSERT INTO audit_logs (actor_type, actor_id, action, entity_name, entity_id, payload_changes)
                VALUES ('N8N_WORKFLOW', 'waitlist_promoter', 'WAITLIST_CONVERTED_TO_BOOKING', 'bookings', %s, %s);
            """, (str(booking_res["booking_id"]), f'{{"waitlist_id": "{convert_in.waitlist_id}"}}'))

            return BookingResponse(**booking_res)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Waitlist conversion failed: {str(e)}")
