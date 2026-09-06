# Flight Management System — Web Frontend (Phase 6)

## Overview
The web frontend is a presentation-only single-page application (SPA) built using Vanilla JavaScript (ES Modules) and Glassmorphic CSS. It serves as an interactive demonstration interface for the Flight Management System backend engine.

## Non-Negotiable Security & Architectural Safeguards
1. **Presentation / Client Only**: The browser contains zero business logic, fare calculation rules, or state mutators.
2. **FastAPI Sole Transactional Writer**: All seat holds, bookings, cancellations, flight creations, fraud risk evaluations, and RAG policy queries are handled authoritatively by the FastAPI backend at `http://127.0.0.1:8000`.
3. **Zero Secrets in Browser**: No Supabase database credentials, service role keys, Pinecone API keys, or HMAC signing secrets exist in frontend environment variables or JavaScript code.
4. **Server-Side Approval Boundary**: For Human-In-The-Loop (HITL) supervisor refund decisions, the browser calls `POST /api/v1/admin/process-approval`. HMAC token generation and verification take place exclusively on the FastAPI server boundary.

---

## User Interfaces

### 1. Passenger Web Portal (Task 6.1)
- **Flight Search**: Live search querying Supabase flight inventory by origin/destination.
- **Seat Class Selector**: Economy and Business class selector with real-time base fare pricing.
- **Atomic Seat Hold**: Creates 10-minute seat holds (`POST /api/v1/holds`) with a live JavaScript countdown timer (`MM:SS`).
- **Idempotency Booking**: Converts active hold to confirmed booking (`POST /api/v1/bookings`) with automatic client-generated idempotency UUIDs.
- **Booking Lookup & Cancellation**: Authoritative lookup (`GET /api/v1/mcp/get-booking-context`) and cancellation (`POST /api/v1/bookings/cancel`) with automatic inventory restoration.

### 2. Admin & Operations Dashboard (Task 6.2)
- **Flight Creation & Capacity**: Admin flight creation endpoint (`POST /api/v1/flights/admin/create`) declaring seat capacities per class.
- **Grounded Policy AI Workbench (RAG)**: Form to query Pinecone vector database (`POST /api/v1/mcp/query-policy`). Features automatic `INSUFFICIENT_EVIDENCE` fallback indicators for unsupported/unrelated queries.
- **Real-Time Fraud Risk Assessor**: Evaluates booking fraud risk score and anomaly signals (`GET /api/v1/admin/ops-overview`).
- **Supervisor HITL Refund Queue**: Renders pending refund requests exceeding $500 threshold with server-side HMAC approved/rejected action triggers (`POST /api/v1/admin/process-approval`).
- **Live Operations & Audit Ledger**: Live view of waitlist candidates, refund escalations, system status, and immutable audit logs (`GET /api/v1/admin/ops-overview`).

---

## Running Locally

1. **Start FastAPI Backend (Port 8000)**:
   ```bash
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

2. **Start Frontend Static HTTP Server (Port 5173)**:
   ```bash
   python -m http.server 5173 --directory frontend
   ```

3. **Open in Browser**:
   Navigate to [http://127.0.0.1:5173](http://127.0.0.1:5173).

---

## E2E Automated Verification
Run Playwright browser automation suite to verify all user flows:
```bash
python scratch/real_browser_e2e_test.py
```
Screenshots are saved under artifacts `screenshots/`:
- `p6_01_booking_confirmed.png`
- `p6_02_booking_cancelled.png`
- `p6_03_admin_dashboard.png`
