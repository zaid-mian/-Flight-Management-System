import psycopg2
import uuid
from datetime import datetime, timedelta, timezone

def seed_data():
    from app.config import settings
    conn = psycopg2.connect(host=settings.POSTGRES_HOST, port=settings.POSTGRES_PORT, user=settings.POSTGRES_USER, password=settings.POSTGRES_PASSWORD, dbname=settings.POSTGRES_DB, connect_timeout=10)
    cur = conn.cursor()

    # 1. Clean previous test seed data if exists
    cur.execute("DELETE FROM waitlist WHERE passenger_id LIKE 'TEST-W%';")
    cur.execute("DELETE FROM escalation_requests WHERE requested_by LIKE '%test%';")
    cur.execute("DELETE FROM audit_logs WHERE actor_id LIKE '%TEST%';")
    cur.execute("DELETE FROM bookings WHERE passenger_id LIKE 'TEST-P%';")
    cur.execute("DELETE FROM flights WHERE flight_number = 'HKT-200';")
    conn.commit()

    # 2. Insert Test Flight HKT-200 (Departure 24 hours from now)
    dep_time = datetime.now(timezone.utc) + timedelta(hours=24)
    arr_time = dep_time + timedelta(hours=4)
    cur.execute("""
        INSERT INTO flights (flight_number, origin, destination, departure_time, arrival_time, total_capacity, status)
        VALUES ('HKT-200', 'JFK', 'LAX', %s, %s, 150, 'SCHEDULED')
        RETURNING id;
    """, (dep_time, arr_time))
    flight_id = cur.fetchone()[0]

    # 3. Insert Seat Class ECONOMY (Fare base price = $150.00)
    cur.execute("""
        INSERT INTO seat_classes (flight_id, class_name, total_seats, available_seats, booked_seats, fare_base_price)
        VALUES (%s, 'ECONOMY', 150, 100, 50, 150.00)
        RETURNING id;
    """, (flight_id,))

    # 4. Insert Test Confirmed Booking (Paid $200.00 earlier, current base fare $150.00 => qualifying price drop!)
    cur.execute("""
        INSERT INTO bookings (flight_id, passenger_id, passenger_name, passenger_email, class_name, fare_code, fare_amount, status, idempotency_key)
        VALUES (%s, 'TEST-P001', 'Alice Johnson', 'mlengineer44@gmail.com', 'ECONOMY', 'FLEXIBLE_ECONOMY', 200.00, 'CONFIRMED', %s)
        RETURNING id;
    """, (flight_id, str(uuid.uuid4())))
    booking_id_confirmed = cur.fetchone()[0]

    # 5. Insert Test Cancelled Booking (For refund escalation test)
    cur.execute("""
        INSERT INTO bookings (flight_id, passenger_id, passenger_name, passenger_email, class_name, fare_code, fare_amount, status, idempotency_key)
        VALUES (%s, 'TEST-P002', 'Bob Smith', 'mlengineer44@gmail.com', 'ECONOMY', 'FLEXIBLE_ECONOMY', 250.00, 'CANCELLED', %s)
        RETURNING id;
    """, (flight_id, str(uuid.uuid4())))
    booking_id_cancelled = cur.fetchone()[0]

    # 6. Insert Test Waitlist Candidates (Priority score 10 and 5)
    cur.execute("""
        INSERT INTO waitlist (flight_id, passenger_id, passenger_name, passenger_email, class_name, priority_score, loyalty_tier, status)
        VALUES 
        (%s, 'TEST-W001', 'Charlie Brown', 'mlengineer44@gmail.com', 'ECONOMY', 10, 'GOLD', 'PENDING'),
        (%s, 'TEST-W002', 'David Miller', 'mlengineer44@gmail.com', 'ECONOMY', 5, 'SILVER', 'PENDING');
    """, (flight_id, flight_id))

    conn.commit()
    print("Seed data inserted successfully!")
    print(f"Flight ID: {flight_id}")
    print(f"Confirmed Booking ID: {booking_id_confirmed}")
    print(f"Cancelled Booking ID: {booking_id_cancelled}")

    conn.close()

if __name__ == "__main__":
    seed_data()
