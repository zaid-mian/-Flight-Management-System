from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_db_pool, close_db_pool
from app.routers import health, flights, holds, bookings, cancellations, mcp, admin_ops

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Supabase PostgreSQL connection pool
    init_db_pool()
    yield
    # Shutdown: Close connection pool cleanly
    close_db_pool()

app = FastAPI(
    title="Flight Management System — Transactional REST Engine",
    description="Authoritative Transactional Writer for Live Bookings, Seat Holds, Inventory, and Cancellations against Supabase PostgreSQL.",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for local dev frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(health.router)
app.include_router(flights.router)
app.include_router(holds.router)
app.include_router(bookings.router)
app.include_router(cancellations.router)
app.include_router(mcp.router)
app.include_router(admin_ops.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
