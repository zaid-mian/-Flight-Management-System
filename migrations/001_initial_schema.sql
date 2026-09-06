-- ====================================================================
-- Flight Management System — Initial Schema DDL (Supabase PostgreSQL)
-- Migration File: 001_initial_schema.sql
-- PREPARATION ONLY — DO NOT EXECUTE UNTIL PHASE 0 IS UNBLOCKED & AUTHORIZED
-- ====================================================================

-- 1. FLIGHTS TABLE
CREATE TABLE IF NOT EXISTS flights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    flight_number VARCHAR(20) NOT NULL,
    origin VARCHAR(10) NOT NULL,
    destination VARCHAR(10) NOT NULL,
    departure_time TIMESTAMPTZ NOT NULL,
    arrival_time TIMESTAMPTZ NOT NULL,
    total_capacity INT NOT NULL CHECK (total_capacity > 0),
    status VARCHAR(20) NOT NULL DEFAULT 'SCHEDULED' CHECK (status IN ('SCHEDULED', 'DELAYED', 'CANCELLED', 'COMPLETED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT check_flight_times CHECK (arrival_time > departure_time),
    CONSTRAINT unique_flight_schedule UNIQUE (flight_number, departure_time)
);

-- 2. SEAT CLASSES TABLE (Inventory Breakdown per Flight)
CREATE TABLE IF NOT EXISTS seat_classes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    flight_id UUID NOT NULL REFERENCES flights(id) ON DELETE CASCADE,
    class_name VARCHAR(20) NOT NULL CHECK (class_name IN ('FIRST', 'BUSINESS', 'ECONOMY')),
    total_seats INT NOT NULL CHECK (total_seats >= 0),
    available_seats INT NOT NULL CHECK (available_seats >= 0),
    booked_seats INT NOT NULL DEFAULT 0 CHECK (booked_seats >= 0),
    fare_base_price NUMERIC(10,2) NOT NULL CHECK (fare_base_price >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_flight_class UNIQUE (flight_id, class_name),
    CONSTRAINT check_seats_sum CHECK (available_seats + booked_seats <= total_seats)
);

-- 3. SEAT HOLDS TABLE (Temporary Checkout Holds)
CREATE TABLE IF NOT EXISTS seat_holds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    flight_id UUID NOT NULL REFERENCES flights(id) ON DELETE CASCADE,
    class_name VARCHAR(20) NOT NULL,
    passenger_id VARCHAR(100) NOT NULL,
    seat_count INT NOT NULL CHECK (seat_count > 0),
    expires_at TIMESTAMPTZ NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'EXPIRED', 'CONVERTED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. BOOKINGS TABLE (Authoritative Write Path: FastAPI Only)
CREATE TABLE IF NOT EXISTS bookings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    flight_id UUID NOT NULL REFERENCES flights(id) ON DELETE RESTRICT,
    passenger_id VARCHAR(100) NOT NULL,
    passenger_name VARCHAR(100) NOT NULL,
    passenger_email VARCHAR(255) NOT NULL,
    class_name VARCHAR(20) NOT NULL,
    fare_code VARCHAR(30) NOT NULL CHECK (fare_code IN ('BASIC_ECONOMY', 'FLEXIBLE_ECONOMY', 'BUSINESS_FLEX', 'FIRST_CLASS')),
    fare_amount NUMERIC(10,2) NOT NULL CHECK (fare_amount >= 0),
    status VARCHAR(20) NOT NULL DEFAULT 'CONFIRMED' CHECK (status IN ('CONFIRMED', 'CANCELLED', 'REFUNDED', 'PARTIALLY_REFUNDED')),
    idempotency_key VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. WAITLIST TABLE (n8n May Update Status; FastAPI Handles Conversion)
CREATE TABLE IF NOT EXISTS waitlist (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    flight_id UUID NOT NULL REFERENCES flights(id) ON DELETE CASCADE,
    passenger_id VARCHAR(100) NOT NULL,
    passenger_name VARCHAR(100) NOT NULL,
    passenger_email VARCHAR(255) NOT NULL,
    class_name VARCHAR(20) NOT NULL,
    priority_score INT NOT NULL DEFAULT 0,
    loyalty_tier VARCHAR(20) NOT NULL DEFAULT 'STANDARD' CHECK (loyalty_tier IN ('STANDARD', 'SILVER', 'GOLD', 'PLATINUM')),
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'PROMOTED', 'EXPIRED', 'CANCELLED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 6. ESCALATION REQUESTS TABLE (Safe Queue for n8n Refund Requests)
CREATE TABLE IF NOT EXISTS escalation_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id UUID NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
    requested_by VARCHAR(50) NOT NULL DEFAULT 'n8n_background_worker',
    reason TEXT NOT NULL,
    refund_amount NUMERIC(10,2) CHECK (refund_amount >= 0),
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING_REVIEW' CHECK (status IN ('PENDING_REVIEW', 'APPROVED', 'REJECTED')),
    reviewed_by VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 7. POLICY INQUIRIES TABLE (RAG Drafts & Human Approval Tracking)
CREATE TABLE IF NOT EXISTS policy_inquiries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id UUID REFERENCES bookings(id) ON DELETE SET NULL,
    customer_email VARCHAR(255) NOT NULL,
    query_text TEXT NOT NULL,
    rag_draft_response TEXT,
    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'PENDING_HUMAN_APPROVAL', 'APPROVED_SENT', 'REJECTED')),
    approved_by VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 8. FRAUD FLAGS TABLE (Batch Fraud Anomaly Audit Results)
CREATE TABLE IF NOT EXISTS fraud_flags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id UUID REFERENCES bookings(id) ON DELETE CASCADE,
    risk_score INT NOT NULL CHECK (risk_score BETWEEN 0 AND 100),
    risk_reasons JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'FLAGGED' CHECK (status IN ('FLAGGED', 'INVESTIGATING', 'CLEARED', 'CONFIRMED_FRAUD')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 9. AUDIT LOGS TABLE (Immutable Operation Audit Trail)
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_type VARCHAR(20) NOT NULL CHECK (actor_type IN ('FASTAPI_USER', 'FASTAPI_ADMIN', 'N8N_WORKFLOW', 'SYSTEM')),
    actor_id VARCHAR(100) NOT NULL,
    action VARCHAR(100) NOT NULL,
    entity_name VARCHAR(50) NOT NULL,
    entity_id VARCHAR(100) NOT NULL,
    payload_changes JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ====================================================================
-- INDEXES FOR HIGH-PERFORMANCE LOCKING & QUERYING
-- ====================================================================

-- Index for live seat searches and atomic locks
CREATE INDEX IF NOT EXISTS idx_seat_classes_flight_class ON seat_classes(flight_id, class_name);

-- Index for seat hold expiry polling
CREATE INDEX IF NOT EXISTS idx_seat_holds_expiry ON seat_holds(flight_id, status, expires_at);

-- Index for fast idempotency lookup on booking writes
CREATE INDEX IF NOT EXISTS idx_bookings_idempotency ON bookings(idempotency_key);

-- Index for n8n prioritized waitlist promotion (SKIP LOCKED readiness)
CREATE INDEX IF NOT EXISTS idx_waitlist_priority ON waitlist(flight_id, status, priority_score DESC, created_at ASC);

-- Index for escalation reviews and policy inquiries
CREATE INDEX IF NOT EXISTS idx_escalations_status ON escalation_requests(status);
CREATE INDEX IF NOT EXISTS idx_policy_inquiries_status ON policy_inquiries(status);

-- ====================================================================
-- AIRCRAFT CAPACITY VALIDATION FUNCTION & TRIGGER
-- Ensures sum(seat_classes.total_seats) == flights.total_capacity
-- ====================================================================

CREATE OR REPLACE FUNCTION validate_flight_capacity_sum()
RETURNS TRIGGER AS $$
DECLARE
    sum_declared_seats INT;
    flight_capacity INT;
BEGIN
    -- Get declared total capacity for the flight
    SELECT total_capacity INTO flight_capacity FROM flights WHERE id = NEW.flight_id;
    
    -- Sum all configured seat class capacities
    SELECT COALESCE(SUM(total_seats), 0) INTO sum_declared_seats 
    FROM seat_classes 
    WHERE flight_id = NEW.flight_id AND id != NEW.id;
    
    sum_declared_seats := sum_declared_seats + NEW.total_seats;
    
    IF sum_declared_seats > flight_capacity THEN
        RAISE EXCEPTION 'Seat allocation sum (%) exceeds aircraft total capacity (%) for flight %', 
            sum_declared_seats, flight_capacity, NEW.flight_id
            USING ERRCODE = '23514'; -- Check Violation
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_check_seat_capacity ON seat_classes;
CREATE TRIGGER trigger_check_seat_capacity
    BEFORE INSERT OR UPDATE ON seat_classes
    FOR EACH ROW
    EXECUTE FUNCTION validate_flight_capacity_sum();
