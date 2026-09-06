/**
 * Centralized API Client Layer for Flight Management System Frontend.
 * Talks directly to authoritative FastAPI REST Engine running at http://127.0.0.1:8000.
 */

const urlParams = typeof window !== "undefined" ? new URLSearchParams(window.location.search) : new URLSearchParams();
const queryApiUrl = urlParams.get("api_url");
if (queryApiUrl && typeof localStorage !== "undefined") {
    localStorage.setItem("API_BASE_URL", queryApiUrl);
}

export const API_BASE_URL = (typeof window !== "undefined" && window.ENV_API_URL) 
    || queryApiUrl 
    || (typeof localStorage !== "undefined" && localStorage.getItem("API_BASE_URL")) 
    || "http://127.0.0.1:8000";

async function request(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;
    const headers = {
        "Content-Type": "application/json",
        ...options.headers,
    };

    try {
        const response = await fetch(url, { ...options, headers });
        const data = await response.json().catch(() => ({}));
        
        if (!response.ok) {
            const errorMsg = data.detail || `HTTP Error ${response.status}: ${response.statusText}`;
            throw new Error(errorMsg);
        }
        return data;
    } catch (err) {
        console.error(`API Error on ${endpoint}:`, err);
        throw err;
    }
}

export const API = {
    // Health Check
    async healthCheck() {
        return request("/health");
    },

    // Flight Search
    async searchFlights(origin = "", destination = "", flightNumber = "") {
        const params = new URLSearchParams();
        if (origin) params.append("origin", origin);
        if (destination) params.append("destination", destination);
        if (flightNumber) params.append("flight_number", flightNumber);
        return request(`/api/v1/flights/search?${params.toString()}`);
    },

    // Admin Flight Creation
    async adminCreateFlight(payload) {
        return request("/api/v1/flights/admin/create", {
            method: "POST",
            body: JSON.stringify(payload),
        });
    },

    // Atomic Seat Hold Creation
    async createSeatHold(payload) {
        return request("/api/v1/holds", {
            method: "POST",
            body: JSON.stringify(payload),
        });
    },

    // Atomic Booking Creation
    async createBooking(payload) {
        return request("/api/v1/bookings", {
            method: "POST",
            body: JSON.stringify(payload),
        });
    },

    // Booking Cancellation
    async cancelBooking(bookingId, reason = "Customer requested cancellation") {
        return request("/api/v1/bookings/cancel", {
            method: "POST",
            body: JSON.stringify({ booking_id: bookingId, reason }),
        });
    },

    // Booking Context & Audit Trail
    async getBookingContext(bookingId) {
        return request(`/api/v1/mcp/get-booking-context?booking_id=${encodeURIComponent(bookingId)}`);
    },

    // RAG Policy Query
    async queryPolicy(queryText) {
        return request("/api/v1/mcp/query-policy", {
            method: "POST",
            body: JSON.stringify({ query: queryText, top_k: 3 }),
        });
    },

    // Deterministic Refund Calculation
    async calculateRefund(bookingId) {
        return request(`/api/v1/mcp/calculate-refund?booking_id=${encodeURIComponent(bookingId)}`);
    },

    // Real-Time Fraud Evaluation
    async evaluateFraud(bookingId) {
        return request(`/api/v1/mcp/evaluate-fraud?booking_id=${encodeURIComponent(bookingId)}`);
    },

    // Read-Only Admin Ops Overview
    async getOpsOverview() {
        return request("/api/v1/admin/ops-overview");
    },

    // Server-Side Process Approval (HITL Rejection / Approval Boundary)
    async processApproval(bookingId, action, reviewerId = "supervisor_admin", reason = "Supervisor decision") {
        return request("/api/v1/admin/process-approval", {
            method: "POST",
            body: JSON.stringify({
                booking_id: bookingId,
                action: action,
                reviewer_id: reviewerId,
                reason: reason
            }),
        });
    }
};
