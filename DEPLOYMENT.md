# Flight Management System — Production Deployment Guide

This guide provides step-by-step instructions for deploying the Flight Management System backend engine, database schema, vector index, n8n workflows, and web frontend to cloud infrastructure.

---

## 🏗️ 1. Required Services Architecture

| Service | Hosting Model | Component Purpose |
| :--- | :--- | :--- |
| **FastAPI REST Backend** | Docker / Render / Railway / Linux VM | Sole authoritative transactional writer & REST API engine. |
| **Supabase PostgreSQL** | Supabase Cloud (PostgreSQL 17.6) | Authoritative database ledger with row locks & CHECK constraints. |
| **n8n Workflow Engine** | n8n Cloud / Docker Self-Hosted | Asynchronous workflow & AI agent orchestrator. |
| **Pinecone Vector DB** | Pinecone Serverless (AWS `us-east-1`) | Vector database holding embedded policy documents (`flight-policies`). |
| **Web Frontend SPA** | Static Host / Vercel / Netlify / Nginx | Untrusted client presentation layer (Vanilla JS / Glassmorphic CSS). |

---

## 🔑 2. Required Environment Variables

Configure the following environment variables in your production environment (e.g. Render/Railway environment variables or Kubernetes secrets):

```ini
# Supabase PostgreSQL Database Connection
POSTGRES_HOST=aws-0-ap-southeast-1.pooler.supabase.com
POSTGRES_PORT=5432
POSTGRES_USER=postgres.your_supabase_project_ref
POSTGRES_PASSWORD=your_supabase_postgres_password
POSTGRES_DB=postgres

# FastAPI Application Configuration
API_HOST=0.0.0.0
API_PORT=8000
APPROVAL_TOKEN_SECRET=your_secure_random_hmac_secret_key

# Pinecone Vector Database
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_INDEX_NAME=flight-policies
EMBEDDING_MODEL_NAME=all-MiniLM-L6-v2

# LLM Providers (for n8n & Python agents)
GROQ_API_KEY=your_groq_api_key
OPENROUTER_API_KEY=your_openrouter_api_key
GEMINI_API_KEY=your_gemini_api_key
```

> [!CAUTION]
> Never commit production `.env` files to git. Use secrets management in your cloud provider.

---

## 🗄️ 3. Database Setup (Supabase Cloud PostgreSQL)

1. **Connect to Supabase PostgreSQL DSN**:
   Obtain your connection string from the Supabase Dashboard under **Project Settings -> Database -> Connection string**.
2. **Apply Migration DDL**:
   Execute the migration SQL script against Supabase:
   ```bash
   psql -h <POSTGRES_HOST> -p 5432 -U <POSTGRES_USER> -d postgres -f migrations/001_initial_schema.sql
   ```
3. **Verify Database Objects**:
   Confirm that all 9 tables (`flights`, `seat_classes`, `seat_holds`, `bookings`, `waitlist`, `escalation_requests`, `fraud_flags`, `audit_logs`, `flight_policies`) and the PL/pgSQL capacity trigger `trg_enforce_flight_capacity` are present.

---

## 🌲 4. Pinecone Vector Database Ingestion

1. **Initialize Pinecone Index**:
   Ensure index `flight-policies` exists with **dimension=384** and **metric=cosine** (AWS `us-east-1`).
2. **Run Ingestion Script**:
   Execute the ingestion script from the repository root:
   ```bash
   python app/rag/ingest_policies.py
   ```
   *Verification*: Confirm 20 policy chunks from `data/policies/*.md` are embedded using `all-MiniLM-L6-v2` and upserted into Pinecone.

---

## 🚀 5. FastAPI Backend Deployment

### Option A: Docker Deployment (Recommended)
Build and run the production container:
```bash
docker build -t flight-management-api:latest .
docker run -d -p 8000:8000 --env-file .env --name flight-api flight-management-api:latest
```

### Option B: Render / Railway Deployment
1. Connect your GitHub repository to Render or Railway.
2. Select **Docker Runtime** (uses root `Dockerfile`) or **Python Runtime** with start command:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
3. Set environment variables listed in Section 2.
4. Set Health Check path to `/health`.

---

## 🌐 6. Web Frontend Deployment (Vercel / Netlify / Static Host)

1. Deploy the contents of the `frontend/` directory to your static web host (Vercel, Netlify, Cloudflare Pages, or Nginx).
2. **Production API URL Configuration**:
   Inject the production FastAPI backend URL into `frontend/index.html` before `<script type="module" src="app.js"></script>`:
   ```html
   <script>
     window.ENV_API_URL = "https://your-fastapi-backend.onrender.com";
   </script>
   ```
3. **Update CORS in FastAPI**:
   In `app/main.py`, ensure `CORSMiddleware` allows your frontend production domain:
   ```python
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["https://your-frontend-domain.vercel.app", "http://127.0.0.1:5173"],
       allow_credentials=True,
       allow_methods=["*"],
       allow_headers=["*"],
   )
   ```

---

## ⚙️ 7. n8n Cloud / Self-Hosted Configuration

1. **Import Workflow**:
   Import `hackthon` workflow (`XARNZIQO8BHQ20h0`) into your n8n instance.
2. **Configure Credentials in n8n**:
   - `googlePalmApi`: Google Gemini API Key
   - `groqApi`: Groq API Key
   - `openRouterApi`: OpenRouter API Key
   - `gmailOAuth2`: Gmail OAuth2 Credential
3. **Update Webhook & Callback URLs**:
   - Replace any localhost target URLs in n8n HTTP Request nodes with your deployed production FastAPI URL (e.g. `https://your-fastapi-backend.onrender.com/api/v1/bookings/convert-waitlist`).
   - Copy production Webhook URLs from n8n Webhook Trigger nodes for external integrations.

---

## 📧 8. Gmail OAuth Setup

1. Configure a Web Application OAuth 2.0 Client in Google Cloud Console.
2. Set authorized redirect URI to your n8n instance OAuth callback URL:
   `https://<your-n8n-domain>/rest/oauth2-credential/callback`
3. Connect `gmailOAuth2` credential inside n8n.
4. **Manual Activation**: Complete the Google OAuth user authorization prompt in the n8n UI for initial token exchange.

---

## 🩺 9. Post-Deployment Smoke Checks

Run these post-deployment HTTP smoke checks:

1. **Health Check**:
   ```bash
   curl -i https://<your-fastapi-url>/health
   ```
   *Expected Response*: `HTTP 200 OK` with `{"status":"OK","database":{"status":"HEALTHY"}}`.

2. **Flight Search**:
   ```bash
   curl -i "https://<your-fastapi-url>/api/v1/flights/search?origin=JFK&destination=LHR"
   ```
   *Expected Response*: `HTTP 200 OK` with array of active flights and seat class availability.

3. **Pinecone Vector Query**:
   ```bash
   curl -i -X POST "https://<your-fastapi-url>/api/v1/mcp/query-policy" \
     -H "Content-Type: application/json" \
     -d '{"query": "What is the baggage allowance for Business class?"}'
   ```
   *Expected Response*: `HTTP 200 OK` with grounded policy citation.

---

## 🚨 10. Common Deployment Errors & Fixes

| Issue | Cause | Resolution |
| :--- | :--- | :--- |
| **`Errno 10048` / Port in use** | Another process is bound to port 8000. | Kill existing uvicorn process or change `PORT` env variable. |
| **`CORS Error` in Browser** | FastAPI `CORSMiddleware` missing frontend domain. | Add production frontend URL to `allow_origins` list in `app/main.py`. |
| **`23514 Check Violation`** | DB capacity or negative seat constraint triggered. | Ensure seat class totals equal flight capacity during creation. |
| **`PINECONE_API_KEY missing`** | Env variable key name typo (`PINECORN_APII`). | Set `PINECONE_API_KEY` in environment secrets. |
| **`GMAIL OAUTH required`** | OAuth token expired or fresh n8n instance. | Click authorize in n8n credential settings to refresh token. |
