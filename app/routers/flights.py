from fastapi import APIRouter, HTTPException, Query, status
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from app.database import get_db_cursor
from app.schemas import AdminFlightCreateInput, FlightResponse, SeatClassResponse

router = APIRouter(prefix="/api/v1/flights", tags=["Flights"])

# --- TASK 3.2: ADMIN FLIGHT CREATION ENDPOINT ---
@router.post("/admin/create", response_model=FlightResponse, status_code=status.HTTP_201_CREATED)
def admin_create_flight(flight_in: AdminFlightCreateInput):
    # 1. Validate sum(seat_class.total_seats) == flight.total_capacity
    declared_sum = sum(sc.total_seats for sc in flight_in.seat_classes)
    if declared_sum != flight_in.total_capacity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Seat class capacities sum ({declared_sum}) must exactly equal flight total_capacity ({flight_in.total_capacity})."
        )
    
    # 2. Database Transaction for atomic creation
    try:
        with get_db_cursor(commit_on_success=True) as (cur, conn):
            # Insert Flight
            cur.execute("""
                INSERT INTO flights (flight_number, origin, destination, departure_time, arrival_time, total_capacity, status)
                VALUES (%s, %s, %s, %s, %s, %s, 'SCHEDULED')
                RETURNING id, flight_number, origin, destination, departure_time, arrival_time, total_capacity, status;
            """, (
                flight_in.flight_number,
                flight_in.origin,
                flight_in.destination,
                flight_in.departure_time,
                flight_in.arrival_time,
                flight_in.total_capacity
            ))
            flight_data = cur.fetchone()
            flight_id = flight_data["id"]

            seat_classes_res = []
            # Insert Seat Classes
            for sc in flight_in.seat_classes:
                cur.execute("""
                    INSERT INTO seat_classes (flight_id, class_name, total_seats, available_seats, booked_seats, fare_base_price)
                    VALUES (%s, %s, %s, %s, 0, %s)
                    RETURNING id, flight_id, class_name, total_seats, available_seats, booked_seats, fare_base_price;
                """, (
                    flight_id,
                    sc.class_name,
                    sc.total_seats,
                    sc.total_seats,  # Available = Total at creation
                    sc.fare_base_price
                ))
                sc_data = cur.fetchone()
                seat_classes_res.append(SeatClassResponse(**sc_data))

            # Audit Log
            cur.execute("""
                INSERT INTO audit_logs (actor_type, actor_id, action, entity_name, entity_id, payload_changes)
                VALUES ('FASTAPI_ADMIN', 'admin_user', 'FLIGHT_CREATED', 'flights', %s, %s);
            """, (str(flight_id), f'{{"flight_number": "{flight_in.flight_number}"}}'))

            return FlightResponse(
                id=flight_data["id"],
                flight_number=flight_data["flight_number"],
                origin=flight_data["origin"],
                destination=flight_data["destination"],
                departure_time=flight_data["departure_time"],
                arrival_time=flight_data["arrival_time"],
                total_capacity=flight_data["total_capacity"],
                status=flight_data["status"],
                seat_classes=seat_classes_res
            )
    except Exception as e:
        err_msg = str(e)
        if "unique_flight_schedule" in err_msg:
            raise HTTPException(status_code=400, detail=f"Flight schedule collision: Flight {flight_in.flight_number} already scheduled for this departure time.")
        if "23514" in err_msg:
            raise HTTPException(status_code=400, detail=f"Database constraint violation: {err_msg}")
        raise HTTPException(status_code=400, detail=f"Flight creation failed: {err_msg}")

# --- TASK 3.3: FLIGHT SEARCH & INVENTORY QUERY ENDPOINT ---
@router.get("/search", response_model=List[FlightResponse])
def search_flights(
    origin: Optional[str] = Query(None, description="Origin airport code"),
    destination: Optional[str] = Query(None, description="Destination airport code"),
    flight_number: Optional[str] = Query(None, description="Flight number")
):
    try:
        with get_db_cursor(commit_on_success=False) as (cur, conn):
            query = "SELECT id, flight_number, origin, destination, departure_time, arrival_time, total_capacity, status FROM flights WHERE 1=1"
            params = []

            if origin:
                query += " AND origin = %s"
                params.append(origin.upper())
            if destination:
                query += " AND destination = %s"
                params.append(destination.upper())
            if flight_number:
                query += " AND flight_number = %s"
                params.append(flight_number.upper())

            query += " ORDER BY departure_time ASC;"
            cur.execute(query, tuple(params))
            flights = cur.fetchall()

            res = []
            for f in flights:
                cur.execute("""
                    SELECT id, flight_id, class_name, total_seats, available_seats, booked_seats, fare_base_price
                    FROM seat_classes WHERE flight_id = %s ORDER BY class_name ASC;
                """, (f["id"],))
                scs = cur.fetchall()
                sc_responses = [SeatClassResponse(**sc) for sc in scs]

                res.append(FlightResponse(
                    id=f["id"],
                    flight_number=f["flight_number"],
                    origin=f["origin"],
                    destination=f["destination"],
                    departure_time=f["departure_time"],
                    arrival_time=f["arrival_time"],
                    total_capacity=f["total_capacity"],
                    status=f["status"],
                    seat_classes=sc_responses
                ))

            return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Flight search query failed: {str(e)}")
