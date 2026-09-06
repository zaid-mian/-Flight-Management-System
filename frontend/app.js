import { API, API_BASE_URL } from "./api.js";

// GLOBAL STATE
let activeHold = null;
let confirmedBooking = null;
let holdTimerInterval = null;
let currentView = "search";
let selectedSeatNumber = "1A";

// INITIALIZATION
window.addEventListener("DOMContentLoaded", () => {
  console.log("SkyFlow Ops — Flight Control System Initialized.");

  // Register baseline history state for landing page
  if (typeof history !== "undefined" && history.replaceState) {
    history.replaceState({ page: "landing" }, "", window.location.pathname);
  }

  // Guarantee full-screen landing page is visible on every page refresh
  openLandingPage();

  checkHealth();
  loadOpsOverview();
  loadRecentSearches();

  const switchBtn = document.getElementById("btn-switch-workspace");
  if (switchBtn) {
    switchBtn.addEventListener("click", (e) => {
      e.preventDefault();
      window.togglePortalModal(true);
    });
  }
});

// HTML5 BROWSER BACK/FORWARD POPSTATE NAVIGATION HANDLER
window.addEventListener("popstate", (e) => {
  const state = e.state;
  const hash = window.location.hash;

  // Always close any active overlay modal on browser back/forward navigation
  const archModal = document.getElementById("arch-modal-container");
  if (archModal) {
    archModal.classList.remove("active");
    archModal.style.display = "none";
  }

  if (!state || state.page === "landing" || !hash || hash === "" || hash === "#landing") {
    openLandingPage();
  } else if (state.page === "workspace" || hash === "#passenger" || hash === "#admin") {
    const role = (state && state.role) || (hash === "#passenger" ? "passenger" : "admin");
    const landing = document.getElementById("landing-page-container");
    if (landing) landing.style.setProperty("display", "none", "important");
    switchTab(role);
  } else if (state.page === "architecture" || hash === "#architecture") {
    const landing = document.getElementById("landing-page-container");
    if (landing) landing.style.setProperty("display", "none", "important");
    toggleArchModal(true);
  } else {
    openLandingPage();
  }
});

// BUTTON LOADING UTILITY
function setButtonLoading(button, isLoading, loadingText = "Processing...") {
  if (!button) return;
  if (isLoading) {
    button.dataset.originalHtml = button.innerHTML;
    button.disabled = true;
    button.classList.add("disabled");
    button.innerHTML = `<div class="spinner"></div> <span>${loadingText}</span>`;
  } else {
    button.disabled = false;
    button.classList.remove("disabled");
    if (button.dataset.originalHtml) {
      button.innerHTML = button.dataset.originalHtml;
    }
  }
}

// ARCHITECTURE INSPECTOR MODAL TOGGLE & ORIGIN TRACKING
let archModalOpenedFrom = null;

window.toggleArchModal = function (show) {
  const modal = document.getElementById("arch-modal-container");
  if (modal) {
    if (show) {
      modal.classList.add("active");
      modal.style.display = "flex";
    } else {
      modal.classList.remove("active");
      modal.style.display = "none";
      if (archModalOpenedFrom === "landing") {
        archModalOpenedFrom = null;
        openLandingPage();
      }
    }
  }
};

// LANDING PAGE & WORKSPACE SELECTOR HANDLERS
window.selectWorkspace = function (workspaceName) {
  if (typeof history !== "undefined" && history.pushState && window.location.hash !== `#${workspaceName}`) {
    history.pushState({ page: "workspace", role: workspaceName }, "", `#${workspaceName}`);
  }
  const landing = document.getElementById("landing-page-container");
  if (landing) {
    landing.style.setProperty("display", "none", "important");
  }
  if (workspaceName === "passenger") {
    switchTab("passenger");
  } else {
    switchTab("admin");
  }
};

window.openLandingPage = function () {
  const landing = document.getElementById("landing-page-container");
  if (landing) {
    landing.style.setProperty("display", "flex", "important");
  }
  if (window.location.hash && typeof history !== "undefined" && history.pushState) {
    history.pushState({ page: "landing" }, "", window.location.pathname);
  }
};

window.togglePortalModal = function (show) {
  if (show) {
    window.openLandingPage();
  } else {
    const landing = document.getElementById("landing-page-container");
    if (landing) {
      landing.style.setProperty("display", "none", "important");
    }
  }
};

window.openArchitectureFromLanding = function () {
  archModalOpenedFrom = "landing";
  if (typeof history !== "undefined" && history.pushState && window.location.hash !== "#architecture") {
    history.pushState({ page: "architecture" }, "", "#architecture");
  }
  const landing = document.getElementById("landing-page-container");
  if (landing) {
    landing.style.setProperty("display", "none", "important");
  }
  toggleArchModal(true);
};

window.selectPortal = function (portalName) {
  window.selectWorkspace(portalName);
};

// UNIFIED VIEW SWITCHER
window.switchView = function (viewName) {
  currentView = viewName;
  togglePortalModal(false);

  const titles = {
    search: { title: "Flight Search & Live Inventory", desc: "Query live flight schedules from Supabase PostgreSQL and manage atomic seat holds." },
    bookings: { title: "Booking Lookup & Management", desc: "View detailed booking status, passenger info, fare codes, and cancel confirmed bookings." },
    dashboard: { title: "Admin Operations Control Center", desc: "System status metrics, waitlist overview, and pending HITL supervisor queue." },
    "sub-bookings": { title: "Master Bookings & Holds Ledger", desc: "Authoritative transactional record of all confirmed, held, and cancelled flight reservations." },
    flights: { title: "Admin Flight Creator", desc: "Create new flight schedules and allocate seat class capacities directly on Supabase." },
    hitl: { title: "Refund Queue & HITL Approvals", desc: "Review high-value refund requests exceeding $500 threshold with server-side HMAC verification." },
    fraud: { title: "Fraud Risk Assessor", desc: "Real-time automated evaluation of database signals and booking anomalies." },
    rag: { title: "RAG Vector Policy Workbench", desc: "Query Pinecone vector database ('flight-policies') with SentenceTransformers embeddings." },
    ops: { title: "Ops & Audit Ledger", desc: "View prioritized waitlist candidates and immutable system audit logs." }
  };

  if (titles[viewName]) {
    document.getElementById("page-view-title").textContent = titles[viewName].title;
    document.getElementById("page-view-desc").textContent = titles[viewName].desc;
  }

  // Update Sidebar Nav State
  const navIds = ["search", "bookings", "dashboard", "sub-bookings", "flights", "hitl", "fraud", "rag", "ops"];
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

  // Toggle Top-level Tab Containers & Workspace Roles
  const pTab = document.getElementById("tab-passenger");
  const aTab = document.getElementById("tab-admin");
  const pView = document.getElementById("view-passenger");
  const aView = document.getElementById("view-admin");

  const pNavGroup = document.getElementById("nav-group-passenger");
  const aNavGroup = document.getElementById("nav-group-admin");
  const eNavGroup = document.getElementById("nav-group-engineering");

  const pRoleBtn = document.getElementById("role-btn-passenger");
  const aRoleBtn = document.getElementById("role-btn-admin");

  const brandSubtitle = document.getElementById("sidebar-brand-subtitle");
  const badgeAvatar = document.getElementById("user-badge-avatar");
  const badgeName = document.getElementById("user-badge-name");
  const badgeRole = document.getElementById("user-badge-role");

  const isPassengerView = ["search", "bookings"].includes(viewName);

  if (isPassengerView) {
    if (pTab) pTab.classList.add("active");
    if (aTab) aTab.classList.remove("active");
    if (pRoleBtn) pRoleBtn.classList.add("active");
    if (aRoleBtn) aRoleBtn.classList.remove("active");

    if (pNavGroup) pNavGroup.style.display = "block";
    if (aNavGroup) aNavGroup.style.display = "none";
    if (eNavGroup) eNavGroup.style.display = "none";

    if (brandSubtitle) brandSubtitle.textContent = "Customer Booking Portal";
    if (badgeAvatar) badgeAvatar.textContent = "GP";
    if (badgeName) badgeName.textContent = "Guest Passenger";
    if (badgeRole) badgeRole.textContent = "Customer Self-Service";

    pView.style.display = "block";
    aView.style.display = "none";

    if (viewName === "bookings") {
      document.getElementById("subview-search").style.display = "none";
      document.getElementById("subview-bookings").style.display = "block";
    } else {
      document.getElementById("subview-search").style.display = "block";
      document.getElementById("subview-bookings").style.display = "none";
    }
  } else {
    if (aTab) aTab.classList.add("active");
    if (pTab) pTab.classList.remove("active");
    if (aRoleBtn) aRoleBtn.classList.add("active");
    if (pRoleBtn) pRoleBtn.classList.remove("active");

    if (pNavGroup) pNavGroup.style.display = "none";
    if (aNavGroup) aNavGroup.style.display = "block";
    if (eNavGroup) eNavGroup.style.display = "block";

    if (brandSubtitle) brandSubtitle.textContent = "Airline Control Center";
    if (badgeAvatar) badgeAvatar.textContent = "SA";
    if (badgeName) badgeName.textContent = "Supervisor Admin";
    if (badgeRole) badgeRole.textContent = "FastAPI Transactional Writer";

    aView.style.display = "block";
    pView.style.display = "none";

    const targetSub = (viewName === "dashboard" || viewName === "sub-bookings") ? "bookings" : viewName;
    switchSubTab(targetSub);
  }
};

window.switchTab = function (tabName) {
  if (tabName === "passenger") {
    switchView("search");
  } else {
    switchView("dashboard");
  }
};

window.switchSubTab = function (subName) {
  const subviews = ["bookings", "flights", "hitl", "fraud", "rag", "ops"];
  subviews.forEach((sub) => {
    const subContainer = document.getElementById(`admin-subview-${sub}`);
    const subBtn = document.getElementById(`subtab-${sub}`);

    if (subContainer) {
      if (sub === subName) {
        subContainer.style.display = "block";
        if (subBtn) {
          subBtn.classList.remove("btn-secondary");
          subBtn.classList.add("btn-primary");
        }
      } else {
        subContainer.style.display = "none";
        if (subBtn) {
          subBtn.classList.remove("btn-primary");
          subBtn.classList.add("btn-secondary");
        }
      }
    }
  });
};

// HEALTH CHECK & SYSTEM STATUS
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
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span>${message}</span>`;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(12px)";
    setTimeout(() => toast.remove(), 250);
  }, 4500);
};

// FLIGHT INVENTORY SEARCH
window.handleFlightSearch = async function () {
  const origin = document.getElementById("search-origin").value.trim().toUpperCase();
  const destination = document.getElementById("search-destination").value.trim().toUpperCase();
  const container = document.getElementById("search-results-container");
  const searchBtn = document.getElementById("btn-search-flights");

  setButtonLoading(searchBtn, true, "Querying...");
  container.innerHTML = `<p style="color: #64748B;">Querying live flight inventory from Supabase PostgreSQL...</p>`;

  try {
    const flights = await API.searchFlights(origin, destination);
    setButtonLoading(searchBtn, false);

    if (!flights || flights.length === 0) {
      container.innerHTML = `
        <div style="padding: 1.5rem; text-align: center; color: #64748B; background: #F8FAFC; border-radius: var(--radius-md); border: 1px dashed var(--border-color);">
          <div style="font-size: 1.5rem; margin-bottom: 0.5rem;">✈️</div>
          <div style="font-weight: 700; color: #334155;">No Active Flights Found</div>
          <div style="font-size: 0.82rem; margin-top: 0.2rem;">Try searching for origin <strong>JFK</strong> and destination <strong>LHR</strong>.</div>
        </div>`;
      return;
    }

    let html = "";
    flights.forEach((flight) => {
      html += `
        <div class="card" style="border: 1px solid var(--border-color); padding: 1.25rem; margin-bottom: 1rem; background: #FFFFFF; box-shadow: var(--shadow-xs);">
          <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 1rem; margin-bottom: 1rem;">
            <div>
              <div style="font-size: 1.2rem; font-weight: 800; color: var(--primary);" class="font-mono">${flight.flight_number}</div>
              <div style="font-size: 0.95rem; font-weight: 700; color: var(--text-main); margin-top: 0.2rem;">
                ${flight.origin} ➔ ${flight.destination}
              </div>
            </div>
            <div style="text-align: right;">
              <span class="table-pill table-pill-success">${flight.status}</span>
              <div style="font-size: 0.78rem; color: #64748B; margin-top: 0.3rem;">Total Aircraft Capacity: <strong class="tabular-nums">${flight.total_capacity} seats</strong></div>
            </div>
          </div>

          <div style="border-top: 1px solid var(--border-color); padding-top: 1rem;">
            <div style="font-size: 0.78rem; font-weight: 700; text-transform: uppercase; color: #64748B; margin-bottom: 0.75rem; letter-spacing: 0.5px;">
              Available Seat Inventory & Pricing
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 0.85rem;">
      `;

      flight.seat_classes.forEach((sc) => {
        const isAvailable = sc.available_seats > 0;
        html += `
          <div style="background: ${isAvailable ? "#F8FAFC" : "#FEF2F2"}; border: 1px solid ${isAvailable ? "var(--border-color)" : "#FECACA"}; padding: 0.85rem 1rem; border-radius: var(--radius-md); display: flex; align-items: center; justify-content: space-between;">
            <div>
              <div style="font-size: 0.88rem; font-weight: 700; color: var(--text-main);">${sc.class_name} CLASS</div>
              <div style="font-size: 1.1rem; font-weight: 800; color: var(--primary);" class="font-mono tabular-nums">$${sc.fare_base_price}</div>
              <div style="font-size: 0.78rem; color: ${isAvailable ? "#059669" : "#DC2626"}; font-weight: 600; margin-top: 0.2rem;">
                ${sc.available_seats} / ${sc.total_seats} seats available
              </div>
            </div>
            <div>
              ${
                isAvailable
                  ? `<button class="btn btn-primary" style="font-size: 0.8rem; padding: 0.45rem 0.85rem;" onclick="initiateSeatHold('${flight.id}', '${flight.flight_number}', '${flight.origin}', '${flight.destination}', '${sc.class_name}', ${sc.fare_base_price}, ${sc.available_seats}, ${sc.total_seats})">
                      Select Seat & Hold
                    </button>`
                  : `<button class="btn btn-secondary" style="font-size: 0.8rem; padding: 0.45rem 0.85rem;" disabled>Sold Out</button>`
              }
            </div>
          </div>
        `;
      });

      html += `
            </div>
          </div>
        </div>
      `;
    });

    container.innerHTML = html;
  } catch (err) {
    setButtonLoading(searchBtn, false);
    showToast(`Flight search failed: ${err.message}`, "error");
    container.innerHTML = `<p style="color: #DC2626;">Error searching flights: ${err.message}</p>`;
  }
};

// INTERACTIVE CABIN SEAT SELECTOR GENERATOR
function renderCabinSeatGrid(flightId, className, availableSeats, totalSeats) {
  const container = document.getElementById("cabin-seat-grid");
  const titleElem = document.getElementById("seat-map-class-title");

  if (titleElem) {
    titleElem.textContent = `${className.toUpperCase()} CABIN SEAT MAP (${availableSeats} SEATS AVAILABLE)`;
  }

  if (!container) return;

  const seatsPerRow = className.toUpperCase() === "BUSINESS" ? 4 : 6;
  const letters = ["A", "B", "C", "D", "E", "F"];
  const numRows = Math.max(2, Math.ceil(totalSeats / seatsPerRow));

  let html = "";
  let seatCounter = 0;

  for (let r = 1; r <= numRows; r++) {
    html += `<div class="seat-row"><div class="row-label">${r}</div>`;

    for (let c = 0; c < seatsPerRow; c++) {
      if (c === Math.floor(seatsPerRow / 2)) {
        html += `<div class="aisle-gap"></div>`;
      }

      seatCounter++;
      const seatCode = `${r}${letters[c]}`;
      const isBooked = seatCounter > availableSeats + Math.floor(totalSeats * 0.2);
      const isHeld = !isBooked && seatCounter > availableSeats;
      const isAvailable = !isBooked && !isHeld;
      const isSelected = seatCode === selectedSeatNumber;

      let seatClass = "seat-cell";
      if (isSelected) seatClass += " selected";
      else if (isBooked) seatClass += " booked";
      else if (isHeld) seatClass += " held";
      else seatClass += " available";

      html += `
        <div class="${seatClass}" 
             onclick="${isAvailable ? `selectCabinSeat('${seatCode}')` : ''}" 
             title="Seat ${seatCode} (${isAvailable ? 'Available' : isHeld ? 'Active Hold' : 'Booked'})">
          ${seatCode}
        </div>
      `;
    }

    html += `</div>`;
  }

  container.innerHTML = html;
}

window.selectCabinSeat = function (seatCode) {
  selectedSeatNumber = seatCode;
  showToast(`Selected Seat ${seatCode}`, "info");
  if (activeHold) {
    renderCabinSeatGrid(activeHold.flight_id, activeHold.class_name, 5, 12);
  }
};

// INITIATE SEAT HOLD & OPEN RIGHT-SIDE DRAWER (540px DESKTOP)
window.initiateSeatHold = async function (flightId, flightNumber, origin, destination, className, farePrice, availableSeats, totalSeats) {
  try {
    const payload = {
      flight_id: flightId,
      class_name: className,
      passenger_id: "pass_demo_" + Math.floor(Math.random() * 1000),
      seat_count: 1,
      hold_duration_minutes: 10
    };

    const holdData = await API.createSeatHold(payload);
    activeHold = {
      ...holdData,
      flight_number: flightNumber || "HKT-888",
      origin: origin || "JFK",
      destination: destination || "LHR",
      fare_price: farePrice || 250.00
    };

    showToast(`Temporary seat hold active for 10 minutes (Hold ID: ${holdData.hold_id.substring(0, 8)}...)`, "success");

    // Populate Right-Side Drawer Header & Summaries
    document.getElementById("drawer-flight-code").textContent = activeHold.flight_number;
    document.getElementById("drawer-flight-route").textContent = `${activeHold.origin} ➔ ${activeHold.destination}`;
    document.getElementById("drawer-flight-class").textContent = className.toUpperCase();
    document.getElementById("drawer-flight-price").textContent = `$${activeHold.fare_price.toFixed(2)}`;
    document.getElementById("drawer-total-price").textContent = `$${activeHold.fare_price.toFixed(2)}`;
    document.getElementById("hold-id-display").textContent = `Hold ID: ${holdData.hold_id}`;
    document.getElementById("book-idempotency-key").value = `idemp_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`;
    
    // Render 2D Aircraft Cabin Map inside Drawer Body
    renderCabinSeatGrid(flightId, className, availableSeats, totalSeats);

    // Reset panel view states to checkout view
    const checkoutView = document.getElementById("hold-panel-checkout-view");
    const confirmView = document.getElementById("hold-panel-confirmation-view");
    if (checkoutView) checkoutView.style.display = "flex";
    if (confirmView) confirmView.style.display = "none";

    // Open Centered Focused Hold Panel
    const holdPanel = document.getElementById("active-hold-panel");
    if (holdPanel) holdPanel.classList.add("active");

    // Start 10-minute Countdown Timer
    startHoldTimer(new Date(holdData.expires_at));
  } catch (err) {
    showToast(`Seat hold failed: ${err.message}`, "error");
  }
};

// HOLD TIMER COUNTDOWN
function startHoldTimer(expiresAt) {
  if (holdTimerInterval) clearInterval(holdTimerInterval);

  function updateTimer() {
    const now = new Date();
    const diffMs = expiresAt - now;

    if (diffMs <= 0) {
      clearInterval(holdTimerInterval);
      document.getElementById("hold-timer-countdown").textContent = "00:00 EXPIRED";
      showToast("Seat hold has expired.", "warning");
      activeHold = null;
      return;
    }

    const totalSecs = Math.floor(diffMs / 1000);
    const mins = Math.floor(totalSecs / 60);
    const secs = totalSecs % 60;
    const formatted = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    
    const elem = document.getElementById("hold-timer-countdown");
    if (elem) elem.textContent = formatted;
  }

  updateTimer();
  holdTimerInterval = setInterval(updateTimer, 1000);
}

window.closeHoldModal = function () {
  const holdPanel = document.getElementById("active-hold-panel");
  if (holdPanel) {
    holdPanel.classList.remove("active");
    holdPanel.style.display = "none";
  }
};

// POST-BOOKING RECEIPT HELPER ACTIONS
window.copyCurrentBookingId = function () {
  const bId = confirmedBooking ? confirmedBooking.booking_id : document.getElementById("confirm-booking-id").textContent;
  if (bId && bId !== "-") {
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(bId).catch(() => {});
      }
    } catch (e) {}
    showToast("Booking Reference ID copied to clipboard!", "info");
  }
};

window.viewCurrentBookingInLookup = function () {
  const bId = confirmedBooking ? confirmedBooking.booking_id : document.getElementById("confirm-booking-id").textContent;
  closeHoldModal();
  switchView("bookings");
  if (bId && bId !== "-") {
    fillSamplePNR(bId);
  }
};

// ATOMIC BOOKING COMPLETION
window.handleCompleteBooking = async function () {
  if (!activeHold) {
    showToast("No active seat hold found. Please hold a seat first.", "warning");
    return;
  }

  const completeBtn = document.getElementById("btn-complete-booking");
  setButtonLoading(completeBtn, true, "Confirming Booking...");

  const payload = {
    flight_id: activeHold.flight_id,
    passenger_id: document.getElementById("book-passenger-id").value.trim(),
    passenger_name: document.getElementById("book-passenger-name").value.trim(),
    passenger_email: document.getElementById("book-passenger-email").value.trim(),
    class_name: activeHold.class_name,
    fare_code: activeHold.class_name.toUpperCase() === "BUSINESS" ? "BUSINESS_FLEX" : "BASIC_ECONOMY",
    fare_amount: activeHold.fare_price || (activeHold.class_name.toUpperCase() === "BUSINESS" ? 850.00 : 250.00),
    hold_id: activeHold.hold_id,
    idempotency_key: document.getElementById("book-idempotency-key").value.trim()
  };

  try {
    const booking = await API.createBooking(payload);
    setButtonLoading(completeBtn, false);

    // Store confirmed booking state
    confirmedBooking = {
      ...booking,
      flight_number: activeHold.flight_number || "HKT-888",
      origin: activeHold.origin || "JFK",
      destination: activeHold.destination || "LHR",
      seat_number: selectedSeatNumber || "1A",
      class_name: activeHold.class_name
    };

    // Save enriched booking details to LocalStorage under RECENT_BOOKINGS
    saveRecentBooking({
      booking_id: booking.booking_id,
      flight_number: activeHold.flight_number || "HKT-888",
      origin: activeHold.origin || "JFK",
      destination: activeHold.destination || "LHR",
      passenger_name: payload.passenger_name,
      class_name: activeHold.class_name,
      seat_number: selectedSeatNumber || "1A",
      fare_amount: payload.fare_amount,
      created_at: booking.created_at || new Date().toISOString()
    });

    if (holdTimerInterval) clearInterval(holdTimerInterval);

    // Populate Post-Booking Confirmation Receipt UI
    document.getElementById("confirm-booking-id").textContent = booking.booking_id;
    document.getElementById("confirm-flight-route").textContent = `${confirmedBooking.flight_number} (${confirmedBooking.origin} ➔ ${confirmedBooking.destination})`;
    document.getElementById("confirm-seat-details").textContent = `${confirmedBooking.class_name.toUpperCase()} (${confirmedBooking.seat_number})`;
    document.getElementById("confirm-passenger-name").textContent = payload.passenger_name;
    document.getElementById("confirm-passenger-email").textContent = payload.passenger_email;
    document.getElementById("confirm-fare-amount").textContent = `$${payload.fare_amount.toFixed(2)}`;
    document.getElementById("confirm-booking-status").textContent = booking.status || "CONFIRMED";

    // Transition modal state to Confirmation Receipt view
    const checkoutView = document.getElementById("hold-panel-checkout-view");
    const confirmView = document.getElementById("hold-panel-confirmation-view");
    if (checkoutView) checkoutView.style.display = "none";
    if (confirmView) confirmView.style.display = "flex";

    showToast(`Booking Confirmed! (Booking ID: ${booking.booking_id.substring(0, 8)}...)`, "success");

    activeHold = null;

    // Refresh flight search & ops dashboard
    handleFlightSearch();
    loadOpsOverview();
  } catch (err) {
    setButtonLoading(completeBtn, false);
    showToast(`Booking failed: ${err.message}`, "error");
  }
};

// ENRICHED RECENT BOOKINGS SHORTCUTS
function saveRecentBooking(bookingObj) {
  if (!bookingObj || typeof localStorage === "undefined") return;
  try {
    let recent = JSON.parse(localStorage.getItem("RECENT_BOOKINGS") || "[]");
    let obj = typeof bookingObj === "string" ? { booking_id: bookingObj } : bookingObj;
    if (!obj || !obj.booking_id) return;
    recent = recent.filter((b) => b && b.booking_id !== obj.booking_id);
    recent.unshift(obj);
    recent = recent.slice(0, 4);
    localStorage.setItem("RECENT_BOOKINGS", JSON.stringify(recent));
    loadRecentSearches();
  } catch (e) {}
}

function saveRecentSearch(queryOrObj) {
  saveRecentBooking(queryOrObj);
}
window.saveRecentSearch = saveRecentSearch;

function loadRecentSearches() {
  const container = document.getElementById("recent-lookups-bar");
  if (!container || typeof localStorage === "undefined") return;

  try {
    const recentBookings = JSON.parse(localStorage.getItem("RECENT_BOOKINGS") || "[]");
    let html = `
      <button class="shortcut-pill" onclick="fillSamplePNR('demo_sample_1')"><span>🔗 Sample PNR #1</span></button>
      <button class="shortcut-pill" onclick="fillSamplePNR('demo_sample_2')"><span>🔗 Sample PNR #2</span></button>
    `;

    recentBookings.forEach((b) => {
      const shortId = b.booking_id ? b.booking_id.substring(0, 8) : "PNR";
      const name = b.passenger_name ? b.passenger_name.split(" ")[0] : "Passenger";
      const flt = b.flight_number || "FLT";
      html += `
        <button class="shortcut-pill" onclick="fillSamplePNR('${b.booking_id}')">
          <span>🎟️ ${flt} (${name} • ${shortId}...)</span>
        </button>
      `;
    });

    container.innerHTML = html;
  } catch (e) {}
}

window.fillSamplePNR = function (val) {
  const input = document.getElementById("lookup-booking-id");
  if (!input) return;

  if (val === "demo_sample_1") {
    input.value = "b001a000-0000-0000-0000-000000000001";
  } else if (val === "demo_sample_2") {
    input.value = "b002a000-0000-0000-0000-000000000002";
  } else {
    input.value = val;
  }

  handleBookingLookup();
};

window.handleBookingLookup = async function () {
  const query = document.getElementById("lookup-booking-id").value.trim();
  const resultContainer = document.getElementById("booking-lookup-result");
  const lookupBtn = document.getElementById("btn-lookup-booking");

  if (!query) {
    showToast("Please enter a Booking ID or Idempotency Key", "warning");
    return;
  }

  setButtonLoading(lookupBtn, true, "Searching...");
  resultContainer.style.display = "block";
  resultContainer.innerHTML = `<p style="color: #64748B;">Searching booking records...</p>`;

  try {
    const ctx = await API.getBookingContext(query);
    setButtonLoading(lookupBtn, false);

    if (!ctx || !ctx.booking) {
      resultContainer.innerHTML = `<p style="color: #DC2626;">Booking record not found for query '${query}'.</p>`;
      return;
    }

    saveRecentSearch(query);

    const b = ctx.booking;
    const isCancelled = b.status === "CANCELLED" || b.status === "REFUNDED";

    resultContainer.innerHTML = `
      <div class="card" style="border: 1px solid var(--border-color); background: #FFFFFF; padding: 1.25rem;">
        <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 1rem;">
          <div>
            <div style="font-size: 1.1rem; font-weight: 800; color: var(--primary);" class="font-mono">${b.booking_id}</div>
            <div style="font-size: 0.85rem; color: #64748B;">Passenger: <strong>${b.passenger_name}</strong> (${b.passenger_email})</div>
          </div>
          <div>
            <span class="table-pill ${isCancelled ? "table-pill-danger" : "table-pill-success"}">${b.status}</span>
          </div>
        </div>

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin-bottom: 1.25rem; background: #F8FAFC; padding: 1rem; border-radius: var(--radius-md);">
          <div><div style="font-size: 0.72rem; color: #64748B; text-transform: uppercase;">Flight</div><div style="font-weight: 700;" class="font-mono">${b.flight_number || "HKT-888"}</div></div>
          <div><div style="font-size: 0.72rem; color: #64748B; text-transform: uppercase;">Seat Class</div><div style="font-weight: 700;">${b.class_name}</div></div>
          <div><div style="font-size: 0.72rem; color: #64748B; text-transform: uppercase;">Fare Amount</div><div style="font-weight: 800; color: var(--primary);" class="font-mono tabular-nums">$${b.fare_amount}</div></div>
          <div><div style="font-size: 0.72rem; color: #64748B; text-transform: uppercase;">Idempotency Key</div><div style="font-size: 0.75rem;" class="font-mono">${b.idempotency_key}</div></div>
        </div>

        ${
          !isCancelled
            ? `<button class="btn btn-danger" onclick="handleCancelBooking('${b.booking_id}')">
                <span>Cancel Booking & Process Refund</span>
               </button>`
            : `<div style="font-size: 0.82rem; color: #DC2626; font-weight: 600;">This booking is already cancelled/refunded.</div>`
        }
      </div>
    `;
  } catch (err) {
    setButtonLoading(lookupBtn, false);
    showToast(`Booking lookup error: ${err.message}`, "error");
    resultContainer.innerHTML = `<p style="color: #DC2626;">Error: ${err.message}</p>`;
  }
};

window.handleCancelBooking = async function (bookingId) {
  if (!confirm("Are you sure you want to cancel this booking?")) return;

  try {
    const res = await API.cancelBooking(bookingId);
    showToast(`Booking ${bookingId.substring(0, 8)}... Cancelled successfully!`, "success");
    handleBookingLookup();
    loadOpsOverview();
  } catch (err) {
    showToast(`Cancellation failed: ${err.message}`, "error");
  }
};

// ADMIN FLIGHT CREATOR
window.handleAdminCreateFlight = async function () {
  const flightNum = document.getElementById("admin-flight-num").value.trim();
  const origin = document.getElementById("admin-origin").value.trim().toUpperCase();
  const destination = document.getElementById("admin-destination").value.trim().toUpperCase();
  const capacity = parseInt(document.getElementById("admin-capacity").value, 10);
  const econSeats = parseInt(document.getElementById("admin-economy-seats").value, 10);
  const busSeats = parseInt(document.getElementById("admin-business-seats").value, 10);
  const createBtn = document.getElementById("btn-create-flight");

  if (econSeats + busSeats !== capacity) {
    showToast(`Validation Error: Economy (${econSeats}) + Business (${busSeats}) seats must equal total capacity (${capacity}).`, "warning");
    return;
  }

  setButtonLoading(createBtn, true, "Creating Flight...");

  const payload = {
    flight_number: flightNum,
    origin: origin,
    destination: destination,
    departure_time: new Date(Date.now() + 86400000).toISOString(),
    arrival_time: new Date(Date.now() + 86400000 + 25200000).toISOString(),
    total_capacity: capacity,
    seat_classes: [
      { class_name: "ECONOMY", total_seats: econSeats, fare_base_price: 250.00 },
      { class_name: "BUSINESS", total_seats: busSeats, fare_base_price: 850.00 }
    ]
  };

  try {
    const created = await API.adminCreateFlight(payload);
    setButtonLoading(createBtn, false);
    showToast(`Flight ${created.flight_number} created successfully on Supabase!`, "success");
    handleFlightSearch();
  } catch (err) {
    setButtonLoading(createBtn, false);
    showToast(`Flight creation failed: ${err.message}`, "error");
  }
};

// REAL-TIME FRAUD EVALUATION
window.handleEvaluateFraud = async function () {
  const bookingId = document.getElementById("fraud-booking-id").value.trim();
  const container = document.getElementById("fraud-eval-result");
  const evalBtn = document.getElementById("btn-eval-fraud");

  if (!bookingId) {
    showToast("Please enter a Booking UUID to evaluate", "warning");
    return;
  }

  setButtonLoading(evalBtn, true, "Evaluating Risk...");
  container.style.display = "block";
  container.innerHTML = `<p style="color: #64748B;">Evaluating fraud risk indicators against database rules...</p>`;

  try {
    const res = await API.evaluateFraud(bookingId);
    setButtonLoading(evalBtn, false);

    const score = typeof res.risk_score === "number" ? res.risk_score : 0;
    const isHighRisk = score >= 50 || res.risk_level === "HIGH" || res.requires_human_review;
    const recommendation = res.recommended_action || res.recommendation || res.risk_level || "ALLOW_TRANSACTION";

    const rawSignals = res.triggered_signals || res.reasons || [];
    const signalsText = Array.isArray(rawSignals) && rawSignals.length > 0
      ? rawSignals.join(" • ")
      : (res.explanation || "No elevated fraud risk signals detected. Transaction appears normal.");

    container.innerHTML = `
      <div class="card" style="border: 1px solid ${isHighRisk ? "#FECACA" : "#A7F3D0"}; background: ${isHighRisk ? "#FEF2F2" : "#ECFDF5"}; padding: 1.25rem;">
        <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 0.85rem;">
          <div style="font-weight: 700; font-size: 1.05rem; color: ${isHighRisk ? "#991B1B" : "#065F46"};">
            Fraud Risk Score: <span class="font-mono tabular-nums" style="font-size: 1.4rem; font-weight: 800;">${score} / 100</span>
          </div>
          <span class="table-pill ${isHighRisk ? "table-pill-danger" : "table-pill-success"}">${recommendation}</span>
        </div>
        <div style="font-size: 0.85rem; color: #334155; line-height: 1.5;">
          <strong>Risk Signals Evaluated:</strong> ${signalsText}
        </div>
      </div>
    `;
  } catch (err) {
    setButtonLoading(evalBtn, false);
    showToast(`Fraud evaluation failed: ${err.message}`, "error");
    container.innerHTML = `<p style="color: #DC2626;">Error: ${err.message}</p>`;
  }
};

// RAG VECTOR POLICY WORKBENCH
window.handleRAGQuery = async function () {
  const queryText = document.getElementById("rag-query-text").value.trim();
  const container = document.getElementById("rag-result-container");
  const queryBtn = document.getElementById("btn-query-rag");

  if (!queryText) {
    showToast("Please enter a policy question", "warning");
    return;
  }

  setButtonLoading(queryBtn, true, "Searching Vectors...");
  container.style.display = "block";
  container.innerHTML = `<p style="color: #64748B;">Searching 384-dimensional dense vector embeddings in Pinecone ('flight-policies')...</p>`;

  try {
    const res = await API.queryPolicy(queryText);
    setButtonLoading(queryBtn, false);

    let html = `
      <div class="card" style="border: 1px solid var(--border-color); background: #FFFFFF; padding: 1.25rem;">
        <div style="font-weight: 700; color: var(--primary); margin-bottom: 0.75rem; font-size: 1rem;">
          Pinecone Vector Policy Citations (Grounded Context)
        </div>
    `;

    if (res.matches && res.matches.length > 0) {
      res.matches.forEach((m, idx) => {
        html += `
          <div style="background: #F8FAFC; border: 1px solid var(--border-color); padding: 0.85rem 1rem; border-radius: var(--radius-md); margin-bottom: 0.75rem;">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.35rem;">
              <span class="font-mono" style="font-weight: 700; font-size: 0.82rem; color: #334155;">#${idx + 1} Citation: ${m.metadata?.policy_id || 'Policy Document'}</span>
              <span class="table-pill table-pill-info font-mono tabular-nums">Cosine Score: ${(m.score * 100).toFixed(1)}%</span>
            </div>
            <div style="font-size: 0.85rem; color: var(--text-main); line-height: 1.4;">${m.metadata?.text || m.text}</div>
          </div>
        `;
      });
    } else {
      html += `<p style="color: #64748B;">No direct vector policy match found. Policy fallback active.</p>`;
    }

    html += `</div>`;
    container.innerHTML = html;
  } catch (err) {
    setButtonLoading(queryBtn, false);
    showToast(`RAG vector search error: ${err.message}`, "error");
    container.innerHTML = `<p style="color: #DC2626;">Error: ${err.message}</p>`;
  }
};

window.setRAGSample = function (num) {
  const input = document.getElementById("rag-query-text");
  if (num === 1) input.value = "What happens if I cancel my economy ticket 30 hours before departure?";
  else if (num === 2) input.value = "What is the baggage allowance for Business class passengers?";
  else if (num === 3) input.value = "Can I transport hazardous dangerous industrial chemicals on international flights?";
  handleRAGQuery();
};

// READ-ONLY OPS OVERVIEW & FORMATTED DATA TABLES
let allAdminBookings = [];

window.loadOpsOverview = async function () {
  try {
    const data = await API.getOpsOverview();

    const waitlistCount = data.waitlist_candidates ? data.waitlist_candidates.length : (data.waitlist_pending_count || 0);
    const escalationsCount = data.pending_escalations ? data.pending_escalations.length : (data.pending_escalations_count || 0);
    const fraudCount = data.fraud_flags ? data.fraud_flags.length : (data.fraud_flags_count || 0);

    document.getElementById("stat-waitlist-count").textContent = waitlistCount;
    document.getElementById("stat-escalations-count").textContent = escalationsCount;
    document.getElementById("stat-fraud-count").textContent = fraudCount;

    // Render Master Operations & Bookings Ledger Table
    allAdminBookings = data.recent_bookings || [];
    filterAdminLedgerTable();

    const wlContainer = document.getElementById("ops-waitlist-table");
    const waitlistItems = data.waitlist_candidates || data.prioritized_waitlist || [];
    if (waitlistItems.length > 0) {
      let wlHtml = `
        <div class="table-responsive">
          <table class="ops-table">
            <thead>
              <tr>
                <th>Passenger</th>
                <th>Flight ID</th>
                <th>Class</th>
                <th>Loyalty Tier</th>
                <th>Priority Score</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
      `;

      waitlistItems.forEach((w) => {
        const shortFlt = w.flight_id ? w.flight_id.substring(0, 8) : "N/A";
        wlHtml += `
          <tr>
            <td><strong>${w.passenger_name}</strong><br><span style="font-size: 0.72rem; color: #64748B;">${w.passenger_email}</span></td>
            <td class="font-mono" style="font-size: 0.78rem;">${shortFlt}...</td>
            <td><strong>${w.class_name}</strong></td>
            <td><span class="table-pill table-pill-info">${w.loyalty_tier || "STANDARD"}</span></td>
            <td class="font-mono tabular-nums" style="font-weight: 800; color: var(--primary);">${w.priority_score || 0}</td>
            <td><span class="table-pill table-pill-warning">${w.status}</span></td>
          </tr>
        `;
      });

      wlHtml += `</tbody></table></div>`;
      wlContainer.innerHTML = wlHtml;
    } else {
      wlContainer.innerHTML = `<p style="color: #64748B; font-size: 0.85rem;">No active candidates on waitlist queue.</p>`;
    }

    const auditContainer = document.getElementById("ops-audit-table");
    if (data.recent_audit_logs && data.recent_audit_logs.length > 0) {
      let auditHtml = `
        <div class="table-responsive">
          <table class="ops-table">
            <thead>
              <tr>
                <th>Timestamp (UTC)</th>
                <th>Actor</th>
                <th>Action</th>
                <th>Entity</th>
                <th>Payload State</th>
              </tr>
            </thead>
            <tbody>
      `;

      data.recent_audit_logs.forEach((log) => {
        const timeStr = new Date(log.created_at).toISOString().replace("T", " ").substring(0, 19);
        const shortEntityId = log.entity_id ? log.entity_id.substring(0, 8) : "N/A";
        auditHtml += `
          <tr>
            <td class="font-mono tabular-nums" style="font-size: 0.78rem; color: #64748B;">${timeStr}</td>
            <td><span class="table-pill table-pill-info">${log.actor_type}</span></td>
            <td><strong style="color: #0F172A;">${log.action}</strong></td>
            <td class="font-mono" style="font-size: 0.78rem;">${log.entity_name} (${shortEntityId}...)</td>
            <td class="font-mono" style="font-size: 0.75rem; color: #475569;">${JSON.stringify(log.payload_changes || {})}</td>
          </tr>
        `;
      });

      auditHtml += `</tbody></table></div>`;
      auditContainer.innerHTML = auditHtml;
    } else {
      auditContainer.innerHTML = `<p style="color: #64748B; font-size: 0.85rem;">No audit records available.</p>`;
    }

    renderHITLQueue(data.pending_escalations || []);

  } catch (err) {
    console.error("Ops overview error:", err);
  }
};

// MASTER BOOKINGS & HOLDS TABLE FILTERING LOGIC
window.filterAdminLedgerTable = function () {
  const container = document.getElementById("admin-bookings-table-body");
  if (!container) return;

  const searchInput = document.getElementById("admin-ledger-search");
  const statusFilterElem = document.getElementById("admin-ledger-status-filter");

  const query = searchInput ? searchInput.value.trim().toLowerCase() : "";
  const statusFilter = statusFilterElem ? statusFilterElem.value.toUpperCase() : "ALL";

  const filtered = allAdminBookings.filter((b) => {
    const matchesStatus = statusFilter === "ALL" || (b.status && b.status.toUpperCase() === statusFilter);
    const matchesQuery = !query || 
      (b.booking_id && b.booking_id.toLowerCase().includes(query)) ||
      (b.passenger_name && b.passenger_name.toLowerCase().includes(query)) ||
      (b.passenger_email && b.passenger_email.toLowerCase().includes(query)) ||
      (b.flight_number && b.flight_number.toLowerCase().includes(query));
    return matchesStatus && matchesQuery;
  });

  if (filtered.length === 0) {
    container.innerHTML = `
      <tr>
        <td colspan="8" style="text-align: center; color: #64748B; padding: 2rem;">
          No master booking records matching filter criteria.
        </td>
      </tr>
    `;
    return;
  }

  let html = "";
  filtered.forEach((b) => {
    const shortId = b.booking_id ? b.booking_id.substring(0, 8) : "N/A";
    const statusClass = b.status === "CONFIRMED" ? "table-pill-success" : b.status === "CANCELLED" ? "table-pill-danger" : "table-pill-warning";
    const dateStr = b.created_at ? new Date(b.created_at).toLocaleString() : "N/A";
    const routeStr = `${b.flight_number || "FLT"} (${b.origin || "JFK"} ➔ ${b.destination || "LHR"})`;
    const fareStr = b.fare_amount ? `$${Number(b.fare_amount).toFixed(2)}` : "$0.00";

    html += `
      <tr>
        <td>
          <strong class="font-mono" style="color: var(--primary); font-size: 0.84rem;" title="${b.booking_id}">
            ${shortId}...
          </strong>
        </td>
        <td>
          <div class="font-mono" style="font-weight: 700; color: var(--text-main);">${routeStr}</div>
        </td>
        <td>
          <div style="font-weight: 700;">${b.passenger_name}</div>
          <div style="font-size: 0.75rem; color: #64748B;">${b.passenger_email}</div>
        </td>
        <td>
          <span class="table-pill table-pill-info">${b.class_name || "ECONOMY"}</span>
        </td>
        <td>
          <span class="font-mono tabular-nums" style="font-weight: 700;">${fareStr}</span>
        </td>
        <td>
          <span class="table-pill ${statusClass}">${b.status}</span>
        </td>
        <td>
          <span style="font-size: 0.78rem; color: #64748B;">${dateStr}</span>
        </td>
        <td style="text-align: right;">
          <div style="display: flex; gap: 0.35rem; justify-content: flex-end;">
            <button class="btn btn-secondary" style="font-size: 0.75rem; padding: 0.3rem 0.65rem;" onclick="inspectBookingFromAdmin('${b.booking_id}')" title="Inspect Booking Ledger">
              <span>🔍 Inspect</span>
            </button>
            <button class="btn btn-secondary" style="font-size: 0.75rem; padding: 0.3rem 0.65rem;" onclick="evalFraudFromAdmin('${b.booking_id}')" title="Evaluate Anomaly & Fraud Risk">
              <span>🛡️ Fraud</span>
            </button>
          </div>
        </td>
      </tr>
    `;
  });

  container.innerHTML = html;
};

window.resetAdminLedgerFilters = function () {
  const searchInput = document.getElementById("admin-ledger-search");
  const statusFilterElem = document.getElementById("admin-ledger-status-filter");
  if (searchInput) searchInput.value = "";
  if (statusFilterElem) statusFilterElem.value = "ALL";
  filterAdminLedgerTable();
};

window.inspectBookingFromAdmin = function (bookingId) {
  switchView("bookings");
  fillSamplePNR(bookingId);
};

window.evalFraudFromAdmin = function (bookingId) {
  switchView("dashboard");
  switchSubTab("fraud");
  const fraudInput = document.getElementById("fraud-booking-id");
  if (fraudInput) fraudInput.value = bookingId;
  handleEvaluateFraud();
};

// SUPERVISOR REFUND & HITL QUEUE RENDERER
function renderHITLQueue(escalations) {
  const container = document.getElementById("hitl-queue-container");
  if (!container) return;

  if (!escalations || escalations.length === 0) {
    container.innerHTML = `
      <div style="padding: 1.5rem; text-align: center; color: #64748B; background: #F8FAFC; border-radius: var(--radius-md); border: 1px dashed var(--border-color);">
        <div style="font-size: 1.5rem; margin-bottom: 0.4rem;">🛡️</div>
        <div style="font-weight: 700; color: #334155;">Supervisor Queue Clear</div>
        <div style="font-size: 0.82rem; margin-top: 0.2rem;">No pending refund requests currently require human supervisor approval.</div>
      </div>
    `;
    return;
  }

  let html = "";
  escalations.forEach((esc) => {
    html += `
      <div class="card" style="border: 1px solid var(--accent-amber-border); background: var(--accent-amber-bg); padding: 1.25rem; margin-bottom: 1rem;">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.75rem;">
          <div>
            <div style="font-weight: 700; font-size: 1rem; color: #92400E;">High-Value Refund Approval Required (> $500)</div>
            <div style="font-size: 0.8rem; color: #78350F;" class="font-mono">Booking ID: ${esc.booking_id}</div>
          </div>
          <span class="table-pill table-pill-warning">${esc.status}</span>
        </div>
        <div style="font-size: 0.85rem; color: #451A03; margin-bottom: 1rem;">
          <strong>Reason:</strong> ${esc.reason} | <strong>Refund Amount:</strong> <span class="font-mono tabular-nums" style="font-weight: 800; color: #B45309;">$${esc.refund_amount}</span>
        </div>
        <div style="display: flex; gap: 0.75rem;">
          <button class="btn btn-success" onclick="handleProcessApproval('${esc.booking_id}', 'APPROVE')">Approve Refund (HMAC Verified)</button>
          <button class="btn btn-danger" onclick="handleProcessApproval('${esc.booking_id}', 'REJECT')">Reject Refund</button>
        </div>
      </div>
    `;
  });

  container.innerHTML = html;
}

window.handleProcessApproval = async function (bookingId, action) {
  try {
    const res = await API.processApproval(bookingId, action);
    showToast(`Supervisor Action ${action} executed successfully on FastAPI!`, "success");
    loadOpsOverview();
  } catch (err) {
    showToast(`Approval processing error: ${err.message}`, "error");
  }
};
