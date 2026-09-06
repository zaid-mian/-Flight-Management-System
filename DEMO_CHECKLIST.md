# Flight Management System — Demo Recording Checklist

Use this operational checklist before and during video recording to ensure a smooth, error-free demonstration.

---

## 📋 1. Pre-Recording System Setup

### Services & Servers to Launch
- [ ] **FastAPI REST Backend (Port 8000)**:
  ```bash
  python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
  ```
  *Verify*: Open [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health) and confirm `{"status":"OK","database":{"status":"HEALTHY"}}`.

- [ ] **Frontend Web Server (Port 5173)**:
  ```bash
  python -m http.server 5173 --directory frontend
  ```
  *Verify*: Open [http://127.0.0.1:5173](http://127.0.0.1:5173) and confirm status badge reads `"FastAPI & Supabase Connected"`.

### External Services Active
- [ ] **Supabase Cloud PostgreSQL 17.6**: DSN active on `aws-0-ap-southeast-1.pooler.supabase.com:5432`.
- [ ] **Pinecone Vector Database**: Serverless index `flight-policies` populated with 20 policy vector chunks.
- [ ] **n8n Cloud Workflow Orchestrator**: Workflow `hackthon` (`XARNZIQO8BHQ20h0`) configured with credentials (`groqApi`, `openRouterApi`, `googlePalmApi`, `gmailOAuth2`).

---

## 🖥️ 2. Browser Tabs to Open

1. **Tab 1**: [http://127.0.0.1:5173](http://127.0.0.1:5173) — **Passenger Web Portal** (Main UI Demo)
2. **Tab 2**: [http://127.0.0.1:5173](http://127.0.0.1:5173) — **Admin & Operations Dashboard** (Switched via Tab Header)
3. **Tab 3**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) — **FastAPI Interactive Swagger UI** (Open for technical reference)
4. **Tab 4**: [https://mlengineerss.app.n8n.cloud](https://mlengineerss.app.n8n.cloud) — **n8n Cloud Canvas** (Showing workflow `hackthon`)

---

## 🎥 3. Step-by-Step Recording Sequence

### Step 1: Introduction & Problem (0:00 – 1:00)
- [ ] Display title slide or main Passenger Web Portal screen.
- [ ] Explain overselling risk, AI financial hallucinations, and untrusted client boundaries.

### Step 2: Architecture & Responsibilities (1:00 – 2:15)
- [ ] Show architecture diagram from `README.md` or `DEMO_SCRIPT.md`.
- [ ] Highlight FastAPI as sole transactional writer and n8n as orchestrator.

### Step 3: Passenger Web Portal Demo (2:15 – 4:00)
- [ ] Click **'Search Live Flights'** (Origin `JFK`, Destination `LHR`).
- [ ] Click **'Hold Seat (10m TTL)'** on Business Class. Show active Hold ID banner and **live countdown timer**.
- [ ] Complete booking details and click **'Confirm & Book Seat'**. Show confirmed Booking Reference ID.
- [ ] Paste Booking ID into **'Booking Lookup & Cancellation'**, click **'Lookup Booking'**. Show audit log.
- [ ] Click **'Cancel Booking & Restore Inventory'**. Show status change to `CANCELLED` and inventory restored.

### Step 4: Admin & Operations Dashboard Demo (4:00 – 5:45)
- [ ] Switch to **Admin & Operations Dashboard** tab.
- [ ] Fill flight creation form (`HKT-888`, origin `JFK`, dest `SFO`, capacity `20`, econ `15`, biz `5`), click **'Create Flight'**.
- [ ] Open **RAG Policy Workbench**, enter grounded question: *"What is the baggage allowance for Business class?"*, click **'Search Policy Vectors'**. Show grounded document citation.
- [ ] Click **'Sample: Unrelated Cargo (Fallback)'** (*"Can I transport a live crocodile in hand luggage?"*), click **'Search Policy Vectors'**. Show explicit **`INSUFFICIENT_EVIDENCE` Fallback** container.
- [ ] Open **Real-Time Fraud Assessor**, click **'Evaluate Fraud Risk'**. Show risk score badge.
- [ ] Open **Supervisor Refund Queue**, click **'Approve (HMAC Server Verified)'**. Show server-side HMAC execution.
- [ ] Open **Ops & Audit Ledger**, show live audit log table.

### Step 5: Results & Technical Decisions (5:45 – 7:00)
- [ ] Show verified metrics table (20/20 Master Acceptance PASS, Playwright Browser E2E PASS).
- [ ] Briefly explain the 3 technical decisions & trade-offs (Sole Transactional Writer, $0 LLM Arithmetic Engine, Server-side HMAC Boundary).

### Step 6: Conclusion (7:00 – 7:30)
- [ ] Summarize system status and thank the audience.

---

## 🚫 4. Confidentiality & Screen Safety (DO NOT SHOW)

> [!CAUTION]
> **Strictly avoid revealing the following sensitive information on screen during recording:**

- [ ] **Do NOT open `.env` file** on screen.
- [ ] **Do NOT show raw API keys** (Pinecone, Groq, OpenRouter, Gemini).
- [ ] **Do NOT show database password strings** or connection DSNs.
- [ ] **Do NOT show OAuth Client Secrets** or HMAC signing secret keys.
- [ ] **Do NOT show personal machine file paths** (e.g. `C:\Users\...`). Use relative workspace paths.
- [ ] **Do NOT clean or delete existing demo flights/bookings** in Supabase during the recording.
