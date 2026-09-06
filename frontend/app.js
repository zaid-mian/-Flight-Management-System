import { API, API_BASE_URL } from "./api.js";


// GLOBAL STATE
let activeHold = null;
let holdTimerInterval = null;
let currentView = "search";

// INITIALIZATION
window.addEventListener("DOMContentLoaded", () => {
  console.log("Flight Management System Frontend Initialized.");
  checkHealth();
  loadOpsOverview(); // Preload admin ops
});

// UNIFIED VIEW SWITCHER
window.switchView = function (viewName) {
  currentView = viewName;

  // View Titles Map
  const titles = {
    search: { title: "Flight Search & Inventory Query", desc: "Query live flight availability from Supabase PostgreSQL and execute atomic seat holds." },
    bookings: { title: "Booking Lookup & Management", desc: "View detailed booking status, passenger info, fare codes, and cancel confirmed bookings." },
    dashboard: { title: "Admin Operations Dashboard", desc: "System status metrics, waitlist overview, and pending HITL approval queue." },
    flights: { title: "Admin Flight Creator", desc: "Create new flight schedules and allocate seat class capacities directly on Supabase." },
    hitl: { title: "Refund Queue & HITL Approvals", desc: "Review high-value refund requests exceeding $500 threshold with server-side HMAC verification." },
    fraud: { title: "Fraud Risk Assessor", desc: "Real-time automated evaluation of database signals and booking anomalies." },
    rag: { title: "RAG Vector Policy Workbench", desc: "Query Pinecone vector database (`flight-policies`) with SentenceTransformers embeddings." },
    ops: { title: "Ops & Audit Ledger", desc: "View prioritized waitlist candidates and immutable system audit logs." }
  };

  if (titles[viewName]) {
    document.getElementById("page-view-title").textContent = titles[viewName].title;
    document.getElementById("page-view-desc").textContent = titles[viewName].desc;
  }

  // Update Sidebar Nav State
  const navIds = ["search", "bookings", "dashboard", "flights", "hitl", "fraud", "rag", "ops"];
  navIds.forEach((id) => {
    const navBtn = document.getElementById(`nav-${id}`);
    if (navBtn) {
      if (id === viewName) {
        navBtn.classList.add("active");
      } else {
        navBtn.classList.remove("active");
      }
    }
  });

  // Toggle Top-level Tab Containers
  const pTab = document.getElementById("tab-passenger");
  const aTab = document.getElementById("tab-admin");
  const pView = document.getElementById("view-passenger");
  const aView = document.getElementById("view-admin");

  const isPassengerView = ["search", "bookings"].includes(viewName);

  if (isPassengerView) {
    pTab.classList.add("active");
    aTab.classList.remove("active");
    pView.style.display = "block";
    aView.style.display = "none";

    // Ensure both cards are visible in passenger view for Playwright & scrolling
    document.getElementById("subview-search").style.display = "block";
    document.getElementById("subview-bookings").style.display = "block";

    if (viewName === "bookings") {
      document.getElementById("subview-bookings").scrollIntoView({ behavior: "smooth" });
    } else {
      document.getElementById("subview-search").scrollIntoView({ behavior: "smooth" });
    }
  } else {
    aTab.classList.add("active");
    pTab.classList.remove("active");
    aView.style.display = "block";
    pView.style.display = "none";

    // Toggle Admin Subviews
    const targetSub = viewName === "dashboard" ? "hitl" : viewName;
    const subtabs = ["flights", "hitl", "fraud", "rag", "ops"];
    
    subtabs.forEach((st) => {
      const btn = document.getElementById(`subtab-${st}`);
      const view = document.getElementById(`admin-subview-${st}`);
      
      if (btn && view) {
        if (st === targetSub) {
          btn.classList.add("btn-primary");
          btn.classList.remove("btn-secondary");
          view.style.display = "block";
        } else {
          btn.classList.remove("btn-primary");
          btn.classList.add("btn-secondary");
          view.style.display = "none";
        }
      }
    });

    loadOpsOverview();
  }
};

// TAB SWITCHER COMPATIBILITY FOR TEST SUITE
window.switchTab = function (tabName) {
  if (tabName === "passenger") {
    switchView("search");
  } else {
    switchView("dashboard");
  }
};

window.switchSubTab = function (subtabName) {
  switchView(subtabName);
};

// HEALTH CHECK
async function checkHealth() {
  try {
    const data = await API.healthCheck();
    const statusText = document.getElementById("system-status-text");
    if (data.status === "OK" && data.database?.status === "HEALTHY") {
      statusText.textContent = `FastAPI & ${data.database.database} Connected`;
    } else {
      statusText.textContent = "System Degraded";
    }
  } catch (err) {
    const statusText = document.getElementById("system-status-text");
    statusText.textContent = "API Disconnected";
    showToast(`Cannot connect to FastAPI backend at ${API_BASE_URL}`, "error");
  }
}

// TOAST NOTIFICATIONS
window.showToast = function (message, type = "info") {
  const container = document.getElementById("toast-container");
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  
  const icon = type === "success" ? "✅" : type === "error" ? "❌" : "ℹ️";
  toast.innerHTML = `<div>${icon}</div><div>${message}</div>`;
  
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
};

// -------------------------------------------------------------------
// PASSENGER PORTAL HANDLERS
// -------------------------------------------------------------------

// 1. FLIGHT SEARCH
window.handleFlightSearch = async function () {
  const origin = document.getElementById("search-origin").value.trim();
  const destination = document.getElementById("search-destination").value.trim();
  const container = document.getElementById("search-results-container");

  container.innerHTML = `<p style="color: var(--text-muted); padding: 1rem 0;">Searching live Supabase inventory...</p>`;

  try {
    const flights = await API.searchFlights(origin, destination);

    if (!flights || flights.length === 0) {
      container.innerHTML = `<p style="color: var(--accent-amber); padding: 1rem 0;">No flights found matching '${origin}' to '${destination}'. Try clearing filters or create a flight in Admin tab.</p>`;
      return;
    }

    let html = `<div class="flights-grid">`;
    flights.forEach((f) => {
      const dep = new Date(f.departure_time).toLocaleString();
      const arr = new Date(f.arrival_time).toLocaleString();
      
      html += `
        <div class="flight-card">
          <div class="flight-card-header">
            <div class="flight-route">
              <span class="flight-num">${f.flight_number}</span>
              <span class="route-airports">${f.origin} <span class="arrow">➔</span> ${f.destination}</span>
            </div>
            <span class="badge badge-active">${f.status}</span>
          </div>

          <div class="flight-meta-grid">
            <div class="meta-item">
              <span class="meta-label">DEPARTURE</span>
              <span class="meta-value">🛫 ${dep}</span>
            </div>
            <div class="meta-item">
              <span class="meta-label">ARRIVAL</span>
              <span class="meta-value">🛬 ${arr}</span>
            </div>
            <div class="meta-item">
              <span class="meta-label">TOTAL CAPACITY</span>
              <span class="meta-value">📊 ${f.total_capacity} seats</span>
            </div>
          </div>

          <div class="seat-classes-grid">
      `;

      f.seat_classes.forEach((sc) => {
        const isAvail = sc.available_seats > 0;
        const badgeClass = !isAvail ? "badge-soldout" : (sc.available_seats <= 2 ? "badge-pending" : "badge-confirmed");
        const badgeText = !isAvail ? "SOLD OUT" : (sc.available_seats <= 2 ? "LIMITED" : "AVAILABLE");

        html += `
          <div class="seat-class-card">
            <div class="class-header">
              <span class="class-name">${sc.class_name}</span>
              <span class="class-price">$${sc.fare_base_price.toFixed(2)}</span>
            </div>
            <div class="class-availability">
              <span class="badge ${badgeClass}">${badgeText}</span>
              <span class="seats-count">${sc.available_seats} / ${sc.total_seats} seats left</span>
            </div>
            <button class="btn btn-primary" style="width: 100%; font-size: 0.85rem;" 
                    ${!isAvail ? 'disabled' : ''} 
                    onclick="handleHoldSeat('${f.id}', '${sc.class_name}', ${sc.fare_base_price}, this)">
              ${isAvail ? 'Hold Seat (10m TTL)' : 'Sold Out'}
            </button>
          </div>
        `;
      });

      html += `</div></div>`;
    });

    html += `</div>`;
    container.innerHTML = html;
  } catch (err) {
    container.innerHTML = `<p style="color: var(--accent-rose);">Error searching flights: ${err.message}</p>`;
    showToast(err.message, "error");
  }
};

// 2. CREATE SEAT HOLD
window.handleHoldSeat = async function (flightId, className, basePrice, btnElement) {
  if (btnElement) {
    btnElement.disabled = true;
  }

  try {
    const payload = {
      flight_id: flightId,
      class_name: className,
      passenger_id: "pass_demo_01",
      seat_count: 1,
      hold_duration_minutes: 10
    };

    const res = await API.createSeatHold(payload);
    activeHold = {
      hold_id: res.hold_id,
      flight_id: res.flight_id,
      class_name: res.class_name,
      expires_at: new Date(res.expires_at),
      fare_base_price: basePrice
    };

window.closeHoldModal = function () {
  const holdBox = document.getElementById("active-hold-container");
  if (holdBox) {
    holdBox.style.display = "none";
  }
};

    showToast(`Seat hold created! Hold ID: ${res.hold_id}`, "success");

    // Display Active Hold Box & Start Timer
    const holdBox = document.getElementById("active-hold-container");
    document.getElementById("hold-id-display").textContent = `Hold ID: ${res.hold_id} | Class: ${res.class_name}`;
    document.getElementById("book-idempotency-key").value = `book-key-${crypto.randomUUID()}`;
    holdBox.style.display = "flex";

    startHoldTimer(activeHold.expires_at);
    handleFlightSearch(); // Refresh search results to show decremented inventory
  } catch (err) {
    if (btnElement) {
      btnElement.disabled = false;
    }
    showToast(`Hold creation failed: ${err.message}`, "error");
  }
};

// HOLD TIMER COUNTDOWN
function startHoldTimer(expiresAt) {
  if (holdTimerInterval) clearInterval(holdTimerInterval);

  function updateDisplay() {
    const now = new Date();
    const diffMs = expiresAt - now;

    if (diffMs <= 0) {
      clearInterval(holdTimerInterval);
      document.getElementById("hold-timer-countdown").textContent = "EXPIRED";
      document.getElementById("hold-timer-countdown").style.color = "var(--accent-rose)";
      showToast("Seat hold has expired! Create a new hold to book.", "error");
      return;
    }

    const mins = Math.floor(diffMs / 60000);
    const secs = Math.floor((diffMs % 60000) / 1000);
    document.getElementById("hold-timer-countdown").textContent = `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }

  updateDisplay();
  holdTimerInterval = setInterval(updateDisplay, 1000);
}

// 3. COMPLETE BOOKING
window.handleCompleteBooking = async function () {
  if (!activeHold) {
    showToast("No active seat hold found. Please hold a seat first.", "error");
    return;
  }

  const btn = document.getElementById("btn-complete-booking");
  if (btn) {
    btn.disabled = true;
  }

  const passengerId = document.getElementById("book-passenger-id").value.trim();
  const passengerName = document.getElementById("book-passenger-name").value.trim();
  const passengerEmail = document.getElementById("book-passenger-email").value.trim();
  const idempotencyKey = document.getElementById("book-idempotency-key").value.trim();

  try {
    const payload = {
      flight_id: activeHold.flight_id,
      class_name: activeHold.class_name,
      passenger_id: passengerId,
      passenger_name: passengerName,
      passenger_email: passengerEmail,
      fare_code: activeHold.class_name === "BUSINESS" ? "BUSINESS_FLEX" : "BASIC_ECONOMY",
      fare_amount: activeHold.fare_base_price,
      hold_id: activeHold.hold_id,
      idempotency_key: idempotencyKey
    };

    const bookingRes = await API.createBooking(payload);
    showToast(`Booking Confirmed! ID: ${bookingRes.booking_id}`, "success");

    if (btn) {
      btn.disabled = false;
    }

    // Clear active hold state
    if (holdTimerInterval) clearInterval(holdTimerInterval);
    document.getElementById("active-hold-container").style.display = "none";
    activeHold = null;

    // Load booking details in lookup card
    document.getElementById("lookup-booking-id").value = bookingRes.booking_id;
    handleBookingLookup();
    handleFlightSearch(); // Refresh search
  } catch (err) {
    if (btn) {
      btn.disabled = false;
    }
    showToast(`Booking failed: ${err.message}`, "error");
  }
};

// 4. BOOKING LOOKUP
window.handleBookingLookup = async function () {
  const bookingId = document.getElementById("lookup-booking-id").value.trim();
  const container = document.getElementById("booking-lookup-result");
  const btn = document.getElementById("btn-lookup-booking");

  if (!bookingId) {
    showToast("Please enter a Booking ID or Idempotency Key", "error");
    return;
  }

  if (btn) {
    btn.disabled = true;
  }

  container.style.display = "block";
  container.innerHTML = `<p style="color: var(--text-muted);">Fetching authoritative booking context from Supabase...</p>`;

  try {
    const ctx = await API.getBookingContext(bookingId);
    if (btn) {
      btn.disabled = false;
    }

    const b = ctx.booking;
    const f = ctx.flight;

    const isConfirmed = b.status === "CONFIRMED";
    const statusBadgeBg = isConfirmed ? "#DEF7EC" : "#FDE8E8";
    const statusBadgeColor = isConfirmed ? "#03543F" : "#9B1C1C";
    const statusBadgeBorder = isConfirmed ? "#BCF0DA" : "#FBD5D5";
    const statusDotColor = isConfirmed ? "#10B981" : "#EF4444";

    let html = `
      <div class="booking-detail-card" style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 1.75rem; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05), 0 2px 4px -2px rgba(0,0,0,0.02); margin-top: 1rem;">
        
        <!-- HEADER ROW -->
        <div style="display: flex; justify-content: space-between; align-items: center; padding-bottom: 1rem; margin-bottom: 1.25rem; border-bottom: 1px solid #E2E8F0; flex-wrap: wrap; gap: 0.75rem;">
          <div>
            <div style="font-size: 1.2rem; font-weight: 800; color: #0F172A; display: flex; align-items: center; gap: 0.5rem;">
              <span>🎫 Booking</span>
              <span style="font-family: 'JetBrains Mono', monospace; color: #0052FF; font-size: 1.05rem;">#${b.id}</span>
            </div>
            <div style="font-size: 0.85rem; color: #64748B; margin-top: 0.25rem; display: flex; align-items: center; gap: 0.4rem;">
              <span>📅 Created: ${new Date(b.created_at).toLocaleString()}</span>
            </div>
          </div>
          <div style="background: ${statusBadgeBg}; color: ${statusBadgeColor}; border: 1px solid ${statusBadgeBorder}; font-weight: 700; font-size: 0.8rem; padding: 0.35rem 0.85rem; border-radius: 9999px; display: inline-flex; align-items: center; gap: 0.4rem; text-transform: uppercase; letter-spacing: 0.03em;">
            <span style="width: 8px; height: 8px; border-radius: 50%; background: ${statusDotColor}; display: inline-block;"></span>
            ${b.status}
          </div>
        </div>

        <!-- 3-COLUMN DETAILS GRID -->
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem; margin-bottom: 1.5rem;">
          
          <!-- PASSENGER PANEL -->
          <div style="background: #F8FAFC; border: 1px solid #F1F5F9; border-radius: 8px; padding: 1rem;">
            <div style="font-size: 0.725rem; font-weight: 700; color: #64748B; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.4rem; display: flex; align-items: center; gap: 0.35rem;">
              <span>👤</span> PASSENGER
            </div>
            <div style="font-weight: 700; font-size: 0.95rem; color: #0F172A; display: flex; align-items: center; gap: 0.4rem; flex-wrap: wrap;">
              <span>${b.passenger_name}</span>
              <span style="background: #E2E8F0; color: #334155; font-size: 0.725rem; font-weight: 600; padding: 2px 6px; border-radius: 4px; font-family: monospace;">${b.passenger_id}</span>
            </div>
            <div style="font-size: 0.825rem; color: #64748B; margin-top: 0.3rem;">✉️ ${b.passenger_email}</div>
          </div>

          <!-- FLIGHT DETAILS PANEL -->
          <div style="background: #F8FAFC; border: 1px solid #F1F5F9; border-radius: 8px; padding: 1rem;">
            <div style="font-size: 0.725rem; font-weight: 700; color: #64748B; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.4rem; display: flex; align-items: center; gap: 0.35rem;">
              <span>✈️</span> FLIGHT DETAILS
            </div>
            <div style="font-weight: 700; font-size: 0.95rem; color: #0F172A;">
              ${f.flight_number} <span style="color: #0052FF;">(${f.origin} ➔ ${f.destination})</span>
            </div>
            <div style="font-size: 0.825rem; color: #64748B; margin-top: 0.3rem;">🕒 ${new Date(f.departure_time).toLocaleString()}</div>
          </div>

          <!-- FARE & CLASS PANEL -->
          <div style="background: #F8FAFC; border: 1px solid #F1F5F9; border-radius: 8px; padding: 1rem;">
            <div style="font-size: 0.725rem; font-weight: 700; color: #64748B; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.4rem; display: flex; align-items: center; gap: 0.35rem;">
              <span>💳</span> FARE & CLASS
            </div>
            <div style="font-weight: 700; font-size: 0.925rem; color: #0F172A;">${b.class_name} · <span style="color: #64748B; font-weight: 500;">${b.fare_code}</span></div>
            <div style="font-weight: 800; color: #059669; font-size: 1.15rem; margin-top: 0.2rem;">$${b.fare_amount.toFixed(2)} USD</div>
          </div>

        </div>
    `;

    if (b.status === "CONFIRMED") {
      html += `
        <!-- ACTION BUTTONS -->
        <div style="display: flex; gap: 0.85rem; align-items: center; border-top: 1px solid #E2E8F0; padding-top: 1.25rem; flex-wrap: wrap;">
          <button class="btn btn-danger" style="background: #DC2626; color: #FFFFFF; font-weight: 600; padding: 0.6rem 1.2rem; border-radius: 8px; border: none; cursor: pointer; display: inline-flex; align-items: center; gap: 0.4rem; transition: all 0.15s ease;" 
                  onmouseover="this.style.background='#B91C1C'" onmouseout="this.style.background='#DC2626'"
                  onclick="handleCancelBooking('${b.id}')">
            🚫 Cancel Booking & Restore Inventory
          </button>
          <button class="btn btn-warning" style="background: #D97706; color: #FFFFFF; font-weight: 600; padding: 0.6rem 1.2rem; border-radius: 8px; border: none; cursor: pointer; display: inline-flex; align-items: center; gap: 0.4rem; transition: all 0.15s ease;"
                  onmouseover="this.style.background='#B45309'" onmouseout="this.style.background='#D97706'"
                  onclick="handleCalculateRefund('${b.id}')">
            💰 Check Refund Entitlement
          </button>
        </div>
      `;
    }

    // AUDIT HISTORY
    if (ctx.audit_history && ctx.audit_history.length > 0) {
      html += `
        <div style="margin-top: 1.25rem; border-top: 1px solid #E2E8F0; padding-top: 1.25rem;">
          <div style="font-size: 0.75rem; font-weight: 700; color: #64748B; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.75rem; display: flex; align-items: center; gap: 0.35rem;">
            <span>📜</span> AUTHORITATIVE AUDIT HISTORY
          </div>
          <div style="display: flex; flex-direction: column; gap: 0.5rem;">
      `;
      ctx.audit_history.forEach(a => {
        const actorIdStr = a.actor_id ? ` (${a.actor_id})` : '';
        html += `
          <div style="background: #F8FAFC; border: 1px solid #F1F5F9; border-radius: 6px; padding: 0.65rem 0.85rem; font-size: 0.85rem; color: #334155; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.5rem;">
            <div style="display: flex; align-items: center; gap: 0.5rem;">
              <span style="background: #EFF6FF; color: #1D4ED8; font-weight: 700; font-size: 0.75rem; padding: 2px 8px; border-radius: 4px; font-family: monospace;">${a.action}</span>
              <span>by <strong style="color: #0F172A;">${a.actor_type}</strong>${actorIdStr}</span>
            </div>
            <div style="font-size: 0.775rem; color: #64748B;">🕒 ${new Date(a.created_at).toLocaleTimeString()}</div>
          </div>
        `;
      });
      html += `</div></div>`;
    }

    html += `</div>`;
    container.innerHTML = html;
  } catch (err) {
    if (btn) {
      btn.disabled = false;
    }
    container.innerHTML = `<p style="color: var(--accent-rose);">Lookup error: ${err.message}</p>`;
  }
};

// 5. CANCELLATION
window.handleCancelBooking = async function (bookingId) {
  if (!confirm(`Are you sure you want to cancel booking ${bookingId}? Inventory will be restored.`)) return;

  try {
    const res = await API.cancelBooking(bookingId, "Passenger portal request");
    showToast(`Booking Cancelled! Inventory Restored: ${res.inventory_restored}`, "success");
    handleBookingLookup(); // Refresh details
    handleFlightSearch(); // Refresh available inventory
    loadOpsOverview();
  } catch (err) {
    showToast(`Cancellation failed: ${err.message}`, "error");
  }
};

// CHECK REFUND ENTITLEMENT
window.handleCalculateRefund = async function (bookingId) {
  try {
    const res = await API.calculateRefund(bookingId);
    alert(`DETERMINISTIC REFUND RESULT:\n\nEligible Refund: $${res.eligible_refund_amount.toFixed(2)}\nCancellation Fee: $${res.cancellation_fee.toFixed(2)}\nRule Applied: ${res.rule_applied}\nRequires Supervisor Approval: ${res.requires_human_approval}`);
  } catch (err) {
    showToast(`Refund calculation failed: ${err.message}`, "error");
  }
};

// -------------------------------------------------------------------
// ADMIN & OPERATIONS DASHBOARD HANDLERS
// -------------------------------------------------------------------

// 1. ADMIN CREATE FLIGHT
window.handleAdminCreateFlight = async function () {
  const flightNum = document.getElementById("admin-flight-num").value.trim();
  const origin = document.getElementById("admin-origin").value.trim();
  const destination = document.getElementById("admin-destination").value.trim();
  const capacity = parseInt(document.getElementById("admin-capacity").value);
  const econSeats = parseInt(document.getElementById("admin-economy-seats").value);
  const busSeats = parseInt(document.getElementById("admin-business-seats").value);
  const btn = document.getElementById("btn-create-flight");

  if (econSeats + busSeats !== capacity) {
    showToast(`Validation Error: Sum of seats (${econSeats + busSeats}) must equal Total Capacity (${capacity})`, "error");
    return;
  }

  if (btn) {
    btn.disabled = true;
  }

  const dep = new Date(Date.now() + 86400000 * 2).toISOString();
  const arr = new Date(Date.now() + 86400000 * 2 + 3600000 * 8).toISOString();

  const payload = {
    flight_number: flightNum,
    origin: origin,
    destination: destination,
    departure_time: dep,
    arrival_time: arr,
    total_capacity: capacity,
    seat_classes: [
      { class_name: "ECONOMY", total_seats: econSeats, fare_base_price: 450.00 },
      { class_name: "BUSINESS", total_seats: busSeats, fare_base_price: 1200.00 }
    ]
  };

  try {
    const res = await API.adminCreateFlight(payload);
    if (btn) {
      btn.disabled = false;
    }
    showToast(`Flight ${res.flight_number} created successfully! ID: ${res.id}`, "success");
    handleFlightSearch();
    loadOpsOverview();
  } catch (err) {
    if (btn) {
      btn.disabled = false;
    }
    showToast(`Flight creation failed: ${err.message}`, "error");
  }
};

// 2. LOAD OPS OVERVIEW
window.loadOpsOverview = async function () {
  try {
    const ops = await API.getOpsOverview();
    
    document.getElementById("stat-waitlist-count").textContent = ops.waitlist_candidates?.length || 0;
    document.getElementById("stat-escalations-count").textContent = ops.pending_escalations?.length || 0;
    document.getElementById("stat-fraud-count").textContent = ops.fraud_flags?.length || 0;

    // Render HITL Queue
    const hitlContainer = document.getElementById("hitl-queue-container");
    if (!ops.pending_escalations || ops.pending_escalations.length === 0) {
      hitlContainer.innerHTML = `<p style="color: var(--accent-emerald); font-weight: 500;">No pending refund escalation requests. All clear!</p>`;
    } else {
      let html = `<div style="display: grid; gap: 1rem;">`;
      ops.pending_escalations.forEach(e => {
        html += `
          <div style="background: rgba(30, 41, 59, 0.8); border: 1px solid var(--border-color); border-radius: var(--radius-md); padding: 1.25rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
            <div>
              <div style="font-weight: 700; font-size: 1.05rem;">Booking #${e.booking_id}</div>
              <div style="font-size: 0.85rem; color: var(--text-muted);">Passenger: ${e.passenger_name} (${e.passenger_email})</div>
              <div style="font-size: 0.9rem; color: var(--accent-amber); font-weight: 600; margin-top: 0.25rem;">Refund Requested: $${e.refund_amount.toFixed(2)} | Reason: ${e.reason}</div>
            </div>
            <div style="display: flex; gap: 0.5rem;">
              <button class="btn btn-success btn-approve-refund" style="font-size: 0.85rem;" onclick="handleProcessApproval('${e.booking_id}', 'APPROVE')">Approve (HMAC Server Verified)</button>
              <button class="btn btn-danger" style="font-size: 0.85rem;" onclick="handleProcessApproval('${e.booking_id}', 'REJECT')">Reject</button>
            </div>
          </div>
        `;
      });
      html += `</div>`;
      hitlContainer.innerHTML = html;
    }

    // Render Waitlist Table
    const wlContainer = document.getElementById("ops-waitlist-table");
    if (!ops.waitlist_candidates || ops.waitlist_candidates.length === 0) {
      wlContainer.innerHTML = `<p style="color: var(--text-muted);">No waitlisted passengers.</p>`;
    } else {
      let html = `
        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th>Priority</th>
                <th>Passenger</th>
                <th>Class</th>
                <th>Loyalty Tier</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
      `;
      ops.waitlist_candidates.forEach(w => {
        html += `
          <tr>
            <td><strong style="color: var(--accent-amber);">${w.priority_score}</strong></td>
            <td>${w.passenger_name} (${w.passenger_email})</td>
            <td>${w.class_name}</td>
            <td>${w.loyalty_tier}</td>
            <td><span class="badge badge-${w.status.toLowerCase()}">${w.status}</span></td>
          </tr>
        `;
      });
      html += `</tbody></table></div>`;
      wlContainer.innerHTML = html;
    }

    // Render Audit Table
    const auditContainer = document.getElementById("ops-audit-table");
    if (ops.recent_audit_logs) {
      let html = `
        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Actor</th>
                <th>Action</th>
                <th>Entity</th>
              </tr>
            </thead>
            <tbody>
      `;
      ops.recent_audit_logs.forEach(a => {
        html += `
          <tr>
            <td>${new Date(a.created_at).toLocaleTimeString()}</td>
            <td>${a.actor_type} (${a.actor_id})</td>
            <td><strong style="color: var(--accent-indigo);">${a.action}</strong></td>
            <td>${a.entity_name} #${a.entity_id.slice(0, 8)}...</td>
          </tr>
        `;
      });
      html += `</tbody></table></div>`;
      auditContainer.innerHTML = html;
    }

  } catch (err) {
    console.error("Ops overview error:", err);
  }
};

// 3. SERVER-SIDE PROCESS APPROVAL BOUNDARY
window.handleProcessApproval = async function (bookingId, action) {
  if (!confirm(`Confirm ${action} for booking ${bookingId}?`)) return;

  try {
    const res = await API.processApproval(bookingId, action, "supervisor_admin", "Supervisor decision via Ops Dashboard");
    showToast(`${res.message}`, action === "APPROVE" ? "success" : "info");
    loadOpsOverview();
    handleFlightSearch();
  } catch (err) {
    showToast(`Approval processing failed: ${err.message}`, "error");
  }
};

// 4. FRAUD EVALUATION
window.handleEvaluateFraud = async function () {
  const bookingId = document.getElementById("fraud-booking-id").value.trim();
  const container = document.getElementById("fraud-eval-result");
  const btn = document.getElementById("btn-eval-fraud");

  if (!bookingId) {
    showToast("Enter a Booking ID to evaluate fraud risk", "error");
    return;
  }

  if (btn) {
    btn.disabled = true;
  }

  container.style.display = "block";
  container.innerHTML = `<p style="color: var(--text-muted);">Evaluating database fraud signals...</p>`;

  try {
    const res = await API.evaluateFraud(bookingId);
    if (btn) {
      btn.disabled = false;
    }

    const isHigh = res.risk_score >= 60;
    
    let html = `
      <div style="background: rgba(30, 41, 59, 0.9); border: 1px solid ${isHigh ? 'var(--accent-rose)' : 'var(--border-color)'}; border-radius: var(--radius-md); padding: 1.5rem;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem;">
          <div>
            <span style="font-weight: 800; font-size: 1.15rem;">Fraud Risk Evaluation</span>
            <div style="font-size: 0.85rem; color: var(--text-muted); margin-top: 0.2rem;">Target Email: ${res.passenger_email}</div>
          </div>
          <div style="text-align: right;">
            <div style="font-size: 1.75rem; font-weight: 800; color: ${isHigh ? 'var(--accent-rose)' : 'var(--accent-emerald)'}; font-family: 'JetBrains Mono', monospace;">${res.risk_score} / 100</div>
            <span class="badge badge-${isHigh ? 'cancelled' : 'confirmed'}">${res.risk_level} RISK</span>
          </div>
        </div>

        <div style="margin-bottom: 1rem; font-size: 0.95rem;">
          <strong>Recommended Action:</strong> <span style="color: var(--accent-amber); font-weight: 600;">${res.recommended_action}</span>
        </div>
    `;

    if (res.triggered_signals && res.triggered_signals.length > 0) {
      html += `
        <div style="font-size: 0.85rem; color: var(--accent-rose); font-weight: 700; margin-bottom: 0.5rem; text-transform: uppercase;">TRIGGERED SIGNALS:</div>
        <ul style="font-size: 0.85rem; color: var(--text-muted); padding-left: 1.2rem; display: flex; flex-direction: column; gap: 0.25rem;">
      `;
      res.triggered_signals.forEach(s => html += `<li>${s}</li>`);
      html += `</ul>`;
    } else {
      html += `<div style="font-size: 0.85rem; color: var(--accent-emerald); font-weight: 500;">No suspicious anomaly signals detected.</div>`;
    }

    html += `</div>`;
    container.innerHTML = html;
  } catch (err) {
    if (btn) {
      btn.disabled = false;
    }
    container.innerHTML = `<p style="color: var(--accent-rose);">Evaluation error: ${err.message}</p>`;
  }
};

// 5. RAG POLICY QUERY
window.handleRAGQuery = async function () {
  const queryText = document.getElementById("rag-query-text").value.trim();
  const container = document.getElementById("rag-result-container");
  const btn = document.getElementById("btn-query-rag");

  if (!queryText) {
    showToast("Enter a policy question", "error");
    return;
  }

  if (btn) {
    btn.disabled = true;
  }

  container.style.display = "block";
  container.innerHTML = `<p style="color: var(--text-muted);">Querying Pinecone vector database (` + "`flight-policies`" + `)...</p>`;

  try {
    const res = await API.queryPolicy(queryText);
    if (btn) {
      btn.disabled = false;
    }
    
    let html = `
      <div style="background: rgba(30, 41, 59, 0.9); border: 1px solid var(--border-color); border-radius: var(--radius-md); padding: 1.5rem;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem; flex-wrap: wrap; gap: 0.5rem;">
          <div style="font-weight: 800; font-size: 1.15rem;">Pinecone RAG Search Results</div>
          <span class="badge badge-${res.is_sufficient_evidence ? 'confirmed' : 'cancelled'}">
            ${res.is_sufficient_evidence ? 'GROUNDED EVIDENCE FOUND' : 'INSUFFICIENT EVIDENCE FALLBACK'}
          </span>
        </div>
    `;

    if (!res.is_sufficient_evidence) {
      html += `
        <div style="background: rgba(244, 63, 94, 0.12); border-left: 4px solid var(--accent-rose); padding: 1rem 1.25rem; border-radius: var(--radius-sm); margin-bottom: 1.25rem; color: #fecdd3; font-size: 0.9rem;">
          <strong>⚠️ Insufficient Evidence Fallback:</strong> The airline vector policy database does not contain sufficient verified documentation to answer this question. Refusing to hallucinate policy details.
        </div>
      `;
    }

    if (res.matches && res.matches.length > 0) {
      html += `<div style="font-weight: 700; font-size: 0.85rem; color: var(--text-dim); text-transform: uppercase; margin-bottom: 0.6rem;">TOP RETRIEVED POLICY VECTORS:</div>`;
      res.matches.forEach((m, idx) => {
        html += `
          <div class="evidence-box" style="margin-bottom: 0.85rem;">
            <div style="display: flex; justify-content: space-between; font-weight: 700; margin-bottom: 0.35rem; font-size: 0.85rem;">
              <span>#${idx + 1} Source: ${m.source} (${m.category})</span>
              <span style="color: var(--accent-cyan); font-family: 'JetBrains Mono', monospace;">Score: ${m.score}</span>
            </div>
            <div style="color: var(--text-main); font-style: italic; font-size: 0.9rem; line-height: 1.4;">"${m.text}"</div>
          </div>
        `;
      });
    }

    html += `</div>`;
    container.innerHTML = html;
  } catch (err) {
    if (btn) {
      btn.disabled = false;
    }
    container.innerHTML = `<p style="color: var(--accent-rose);">RAG Query error: ${err.message}</p>`;
  }
};

window.setRAGSample = function (num) {
  const input = document.getElementById("rag-query-text");
  if (num === 1) input.value = "What happens if I cancel my economy ticket 30 hours before departure?";
  if (num === 2) input.value = "What is the baggage allowance for Business class?";
  if (num === 3) input.value = "What is the airline policy for radioactive cargo particles?";
  handleRAGQuery();
};
