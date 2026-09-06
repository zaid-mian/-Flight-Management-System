from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from datetime import datetime, timezone
from uuid import UUID

# --- SEAT CLASS SCHEMAS ---
class SeatClassInput(BaseModel):
    class_name: str = Field(..., description="FIRST, BUSINESS, or ECONOMY")
    total_seats: int = Field(..., ge=0, description="Total seats allocated to this class")
    fare_base_price: float = Field(..., ge=0, description="Base price for this seat class")

    @field_validator('class_name')
    def validate_class_name(cls, v):
        allowed = ['FIRST', 'BUSINESS', 'ECONOMY']
        if v.upper() not in allowed:
            raise ValueError(f"class_name must be one of {allowed}")
        return v.upper()

class SeatClassResponse(BaseModel):
    id: UUID
    flight_id: UUID
    class_name: str
    total_seats: int
    available_seats: int
    booked_seats: int
    fare_base_price: float

# --- FLIGHT SCHEMAS ---
class AdminFlightCreateInput(BaseModel):
    flight_number: str = Field(..., min_length=2, max_length=20)
    origin: str = Field(..., min_length=2, max_length=10)
    destination: str = Field(..., min_length=2, max_length=10)
    departure_time: datetime
    arrival_time: datetime
    total_capacity: int = Field(..., gt=0)
    seat_classes: List[SeatClassInput]

    @field_validator('arrival_time')
    def validate_times(cls, arrival_time, values):
        departure_time = values.data.get('departure_time')
        if departure_time and arrival_time <= departure_time:
            raise ValueError("arrival_time must be strictly after departure_time")
        return arrival_time

class FlightResponse(BaseModel):
    id: UUID
    flight_number: str
    origin: str
    destination: str
    departure_time: datetime
    arrival_time: datetime
    total_capacity: int
    status: str
    seat_classes: List[SeatClassResponse] = []

# --- HOLD SCHEMAS ---
class SeatHoldCreateInput(BaseModel):
    flight_id: UUID
    class_name: str
    passenger_id: str = Field(..., min_length=1)
    seat_count: int = Field(1, gt=0)
    hold_duration_minutes: int = Field(10, gt=0, le=60)

class SeatHoldResponse(BaseModel):
    hold_id: UUID
    flight_id: UUID
    class_name: str
    passenger_id: str
    seat_count: int
    expires_at: datetime
    status: str

# --- BOOKING SCHEMAS ---
class BookingCreateInput(BaseModel):
    flight_id: UUID
    passenger_id: str = Field(..., min_length=1)
    passenger_name: str = Field(..., min_length=1)
    passenger_email: str = Field(..., min_length=3)
    class_name: str
    fare_code: str
    fare_amount: float = Field(..., ge=0)
    idempotency_key: str = Field(..., min_length=5)
    hold_id: Optional[UUID] = None

class BookingResponse(BaseModel):
    booking_id: UUID
    flight_id: UUID
    passenger_id: str
    passenger_name: str
    passenger_email: str
    class_name: str
    fare_code: str
    fare_amount: float
    status: str
    idempotency_key: str
    created_at: datetime

# --- WAITLIST CONVERSION SCHEMA (Phase 2.2 Callback Compatible) ---
class WaitlistConvertInput(BaseModel):
    waitlist_id: UUID
    idempotency_key: str = Field(..., min_length=5)

# --- CANCELLATION SCHEMA ---
class BookingCancelInput(BaseModel):
    booking_id: UUID
    reason: Optional[str] = "Customer cancellation request"

class CancellationResponse(BaseModel):
    booking_id: UUID
    flight_id: UUID
    status: str
    inventory_restored: bool
    audit_log_id: UUID
