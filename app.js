const LEGACY_STORAGE_KEY = "mini-it-support-tickets";
const VALID_PRIORITIES = ["Critical", "High", "Medium", "Low"];
const VALID_STATUSES = ["Open", "In Progress", "Resolved"];
const PREVIEW_LIMIT = 4;

const ticketForm = document.querySelector("#ticket-form");
const ticketList = document.querySelector("#ticket-list");
const ticketSearch = document.querySelector("#ticket-search");
const queuePriority = document.querySelector("#queue-priority");
const triagePriority = document.querySelector("#triage-priority");
const notice = document.querySelector("#notice");
const lookupForm = document.querySelector("#lookup-form");
const lookupInput = document.querySelector("#lookup-id");
const lookupFeedback = document.querySelector("#lookup-feedback");
const formFields = [
  document.querySelector("#ticket-title"),
  document.querySelector("#requester"),
  document.querySelector("#category"),
  document.querySelector("#priority"),
  document.querySelector("#description")
];

let tickets = [];
let refreshTimer;
let ticketRequestSequence = 0;
let searchTimer;

function makeElement(tagName, className = "", text) {
  const element = document.createElement(tagName);
  if (className) {
    element.className = className;
  }
  if (text !== undefined) {
    element.textContent = text;
  }
  return element;
}

function showNotice(message, isError = false) {
  notice.textContent = message;
  notice.hidden = false;
  notice.classList.toggle("is-error", isError);
  notice.setAttribute("role", isError ? "alert" : "status");
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options
  });
  if (!response.ok) {
    let detail = `Request failed (${response.status}).`;
    try {
      const payload = await response.json();
      if (typeof payload.detail === "string") {
        detail = payload.detail;
      }
    } catch (error) {
      console.error("The API returned an unreadable error response.", error);
    }
    throw new Error(detail);
  }
  if (response.status === 204) {
    return null;
  }
  return response.json();
}

function setHealthState(state, message) {
  const health = document.querySelector("#system-health");
  health.classList.remove("is-checking", "is-healthy", "is-unavailable");
  health.classList.add(state);
  document.querySelector("#health-label").textContent = message;
  health.setAttribute("aria-label", `API and database status: ${message}`);
}

async function refreshHealth() {
  try {
    const health = await requestJson("/api/health");
    setHealthState("is-healthy", `API & SQLite connected · ${health.uptime_seconds}s`);
    return true;
  } catch (error) {
    console.error("Unable to check API health.", error);
    setHealthState("is-unavailable", "API or database unavailable");
    return false;
  }
}

function isLegacyTicket(value) {
  return value !== null
    && typeof value === "object"
    && typeof value.id === "string"
    && typeof value.title === "string"
    && typeof value.requester === "string"
    && typeof value.category === "string"
    && ["Low", "Medium", "High", "Critical"].includes(value.priority)
    && VALID_STATUSES.includes(value.status)
    && typeof value.description === "string"
    && typeof value.createdAt === "string"
    && !Number.isNaN(Date.parse(value.createdAt));
}

async function importLegacyTickets() {
  let storedTickets;
  try {
    const storedValue = localStorage.getItem(LEGACY_STORAGE_KEY);
    if (storedValue === null) {
      return;
    }
    storedTickets = JSON.parse(storedValue);
  } catch (error) {
    console.error("Unable to read legacy browser tickets.", error);
    showNotice("Previous browser-stored tickets could not be read. They have not been removed.", true);
    return;
  }

  if (!Array.isArray(storedTickets)) {
    showNotice("Previous browser-stored ticket data has an unexpected format. It has not been removed.", true);
    return;
  }

  const validTickets = storedTickets.filter(isLegacyTicket);
  if (validTickets.length !== storedTickets.length) {
    showNotice("Some previous browser tickets were invalid and could not be imported. Original browser data is retained.", true);
  }
  if (validTickets.length === 0) {
    return;
  }

  const result = await requestJson("/api/tickets/import-legacy", {
    method: "POST",
    body: JSON.stringify({ tickets: validTickets })
  });
  if (result.imported_count > 0) {
    showNotice(`${result.imported_count} previous ticket${result.imported_count === 1 ? "" : "s"} imported. The original browser data remains as a backup.`);
  }
}

function currentFilters() {
  const parameters = new URLSearchParams();
  const search = ticketSearch.value.trim();
  if (search) {
    parameters.set("search", search);
  }
  if (queuePriority.value) {
    parameters.set("priority", queuePriority.value);
  }
  return parameters;
}

async function loadTickets(focusTicketId = null, focusSearch = false) {
  const requestSequence = ++ticketRequestSequence;
  const parameters = currentFilters();
  const loadedTickets = await requestJson(`/api/tickets?${parameters.toString()}`);
  if (requestSequence !== ticketRequestSequence) {
    return;
  }
  tickets = loadedTickets;
  renderTicketList(focusTicketId, focusSearch);
  renderTriagePreview();
}

function renderStatusCounts(metrics) {
  document.querySelector("#open-count").textContent = metrics.open_count;
  document.querySelector("#progress-count").textContent = metrics.in_progress_count;
  document.querySelector("#resolved-count").textContent = metrics.resolved_count;
  document.querySelector("#ticket-total").textContent = metrics.total_tickets;
}

function formatMinutes(value) {
  if (value === null || value === undefined) {
    return "—";
  }
  const minutes = Number(value);
  return `${Number.isInteger(minutes) ? minutes : minutes.toFixed(1)} min`;
}

function renderMetrics(metrics) {
  document.querySelector("#metric-response").textContent = formatMinutes(metrics.median_first_response_minutes);
  document.querySelector("#metric-sla").textContent = metrics.sla_compliance_rate === null
    ? "—"
    : `${metrics.sla_compliance_rate}%`;
  document.querySelector("#metric-resolved").textContent = metrics.resolved_this_month;

  const mode = document.querySelector("#telemetry-mode");
  const note = document.querySelector("#telemetry-note");
  if (metrics.is_illustrative_demo_content) {
    mode.textContent = "Illustrative Demo Content";
    mode.classList.add("is-demo");
    note.textContent = "Live SQL aggregations include seeded sample records. Figures are illustrative, not operational results.";
  } else {
    mode.textContent = "Live SQL telemetry";
    mode.classList.remove("is-demo");
    note.textContent = "Metrics are calculated from persisted tickets. Response and SLA measures appear when eligible timestamps are recorded.";
  }
  renderStatusCounts(metrics);
}

async function refreshMetrics() {
  const metrics = await requestJson("/api/metrics");
  renderMetrics(metrics);
}

function createPriorityBadge(priority) {
  const labels = {
    Critical: { label: "CRITICAL", description: "Priority: Critical incident" },
    High: { label: "HIGH PRIORITY", description: "Priority: High" },
    Medium: { label: "MEDIUM", description: "Priority: Medium" },
    Low: { label: "LOW", description: "Priority: Low" }
  };
  const details = labels[priority] || labels.Medium;
  const badge = makeElement("span", `priority-badge priority-${priority.toLowerCase()}`);
  badge.setAttribute("role", "img");
  badge.setAttribute("aria-label", details.description);
  const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  icon.setAttribute("viewBox", "0 0 16 16");
  icon.setAttribute("aria-hidden", "true");
  icon.setAttribute("focusable", "false");
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  const iconPaths = {
    Critical: "M8 1.5 14.5 13H1.5L8 1.5Zm0 4v3.4m0 1.9v.1",
    High: "M8 1.5 14.5 8 8 14.5 1.5 8 8 1.5Zm0 3.1v4.4m0 1.8v.1",
    Medium: "M2.5 5.2h11m-11 5.6h11",
    Low: "M3 8h10"
  };
  path.setAttribute("d", iconPaths[priority] || iconPaths.Medium);
  icon.append(path);
  badge.append(icon, makeElement("span", "", details.label));
  return badge;
}

function createStatusSelect(ticket, className = "status-select") {
  const select = makeElement("select", className);
  select.setAttribute("aria-label", `Update status for ${ticket.title}`);
  select.dataset.ticketId = ticket.id;
  for (const status of VALID_STATUSES) {
    const option = makeElement("option", "", status);
    option.value = status;
    option.selected = status === ticket.status;
    select.append(option);
  }
  select.addEventListener("change", () => updateTicket(ticket.id, { status: select.value }));
  return select;
}

function createPrioritySelect(ticket) {
  const select = makeElement("select", "ticket-priority-select");
  select.setAttribute("aria-label", `Change priority for ${ticket.title}`);
  select.dataset.ticketId = ticket.id;
  for (const priority of VALID_PRIORITIES) {
    const option = makeElement("option", "", priority);
    option.value = priority;
    option.selected = priority === ticket.priority;
    select.append(option);
  }
  select.addEventListener("change", () => updateTicket(ticket.id, { priority: select.value }));
  return select;
}

function createTicketCard(ticket) {
  const card = makeElement("article", "ticket-card");
  card.classList.toggle("is-unresolved", ticket.status !== "Resolved");
  card.classList.toggle("is-high-priority", ticket.priority === "High");
  card.classList.toggle("is-critical-priority", ticket.priority === "Critical");

  const topLine = makeElement("div", "ticket-topline");
  const reference = makeElement("span", "ticket-reference", ticket.id);
  const time = makeElement("time", "", new Date(ticket.createdAt).toLocaleString());
  time.dateTime = ticket.createdAt;
  topLine.append(reference, time);

  const heading = makeElement("h3", "", ticket.title);
  const requester = makeElement("p", "ticket-requester");
  requester.append("Requested by ", makeElement("strong", "", ticket.requester));
  const description = makeElement("p", "ticket-description", ticket.description);
  const badges = makeElement("div", "ticket-badges");
  badges.append(createPriorityBadge(ticket.priority), makeElement("span", "ticket-category", ticket.category));
  if (ticket.isDemo) {
    badges.append(makeElement("span", "demo-tag", "DEMO"));
  }

  const controls = makeElement("div", "ticket-control");
  const assignment = makeElement("span", "assignee-chip", ticket.assignedTo || "Unassigned");
  assignment.setAttribute("aria-label", `Assignee: ${ticket.assignedTo || "Unassigned"}`);
  controls.append(assignment, createPrioritySelect(ticket), createStatusSelect(ticket));

  const actions = makeElement("div", "ticket-actions");
  const deleteButton = makeElement("button", "delete-button", "Delete");
  deleteButton.type = "button";
  deleteButton.setAttribute("aria-label", `Delete ticket ${ticket.id}: ${ticket.title}`);
  deleteButton.addEventListener("click", () => deleteTicket(ticket));
  actions.append(badges, controls, deleteButton);
  card.append(topLine, heading, requester, description, actions);
  return card;
}

function createEmptyState(isFiltered, messageTarget) {
  const emptyState = makeElement("div", "empty-state");
  const heading = makeElement("h3", "", isFiltered ? "No matching tickets" : "Nothing in the queue yet");
  const copy = makeElement(
    "p",
    "",
    isFiltered
      ? "Try another search or priority, or clear the filters."
      : "Create a request to give the support team a clear place to start."
  );
  emptyState.append(heading, copy);
  if (isFiltered) {
    const clearButton = makeElement("button", "text-button", "Clear filters");
    clearButton.type = "button";
    clearButton.addEventListener("click", clearFilters);
    emptyState.append(clearButton);
  } else {
    const createLink = makeElement("a", "text-button", "Create a ticket");
    createLink.href = "#ticket-title";
    emptyState.append(createLink);
  }
  messageTarget.append(emptyState);
}

function renderTicketList(focusTicketId = null, focusSearch = false) {
  ticketList.replaceChildren();
  if (tickets.length === 0) {
    createEmptyState(Boolean(ticketSearch.value.trim() || queuePriority.value), ticketList);
    return;
  }

  const fragment = document.createDocumentFragment();
  for (const ticket of tickets) {
    fragment.append(createTicketCard(ticket));
  }
  ticketList.append(fragment);

  if (focusTicketId) {
    ticketList.querySelector(`[data-ticket-id="${CSS.escape(focusTicketId)}"].status-select`)?.focus();
  } else if (focusSearch) {
    ticketSearch.focus();
  }
}

function renderTriagePreview() {
  const list = document.querySelector("#triage-list");
  list.replaceChildren();
  document.querySelector("#preview-total").textContent = tickets.length;

  if (tickets.length === 0) {
    createEmptyState(Boolean(ticketSearch.value.trim() || queuePriority.value), list);
    return;
  }

  for (const ticket of tickets.slice(0, PREVIEW_LIMIT)) {
    const row = makeElement("article", "triage-row");
    row.classList.toggle("is-high-priority", ticket.priority === "High");
    row.classList.toggle("is-critical-priority", ticket.priority === "Critical");
    const id = makeElement("span", "triage-id", ticket.id);
    const info = makeElement("div", "triage-info");
    info.append(makeElement("strong", "triage-title", ticket.title));
    info.append(makeElement("span", "triage-requester", ticket.requester));
    const badges = makeElement("div", "triage-badges");
    badges.append(createPriorityBadge(ticket.priority));
    if (ticket.isDemo) {
      badges.append(makeElement("span", "demo-tag", "DEMO"));
    }
    const controls = makeElement("div", "triage-controls");
    controls.append(createStatusSelect(ticket, "triage-status-select"));
    row.append(id, info, badges, controls);
    list.append(row);
  }

  if (tickets.length > PREVIEW_LIMIT) {
    list.append(makeElement("p", "preview-more", `${tickets.length - PREVIEW_LIMIT} more ticket${tickets.length - PREVIEW_LIMIT === 1 ? "" : "s"} in the queue below.`));
  }
}

async function refreshViews(focusTicketId = null, focusSearch = false) {
  await Promise.all([loadTickets(focusTicketId, focusSearch), refreshMetrics()]);
}

async function updateTicket(ticketId, changes) {
  try {
    await requestJson(`/api/tickets/${encodeURIComponent(ticketId)}`, {
      method: "PATCH",
      body: JSON.stringify(changes)
    });
    await refreshViews(ticketId);
    showNotice("Ticket updated and audit history recorded.");
  } catch (error) {
    console.error("Unable to update ticket.", error);
    showNotice(`Ticket update failed: ${error.message}`, true);
    await loadTickets(ticketId).catch((loadError) => {
      console.error("Unable to restore ticket view after update failure.", loadError);
    });
  }
}

async function deleteTicket(ticket) {
  if (!window.confirm(`Delete ${ticket.id} — "${ticket.title}"? The ticket will be removed from the active queue.`)) {
    return;
  }
  try {
    await requestJson(`/api/tickets/${encodeURIComponent(ticket.id)}`, { method: "DELETE" });
    await refreshViews(null, true);
    showNotice("Ticket removed from the active queue. Its audit history is retained.");
  } catch (error) {
    console.error("Unable to delete ticket.", error);
    showNotice(`Ticket deletion failed: ${error.message}`, true);
  }
}

function validateForm() {
  let firstBlankField = null;
  for (const field of formFields) {
    const isBlank = field.value.trim() === "";
    field.setCustomValidity(isBlank ? "Complete this field before creating the ticket." : "");
    if (isBlank && firstBlankField === null) {
      firstBlankField = field;
    }
  }
  if (firstBlankField) {
    firstBlankField.reportValidity();
    return false;
  }
  return ticketForm.reportValidity();
}

function createLookupResult(ticket) {
  const result = makeElement("div", "lookup-ticket");
  result.classList.toggle("is-high-priority", ticket.priority === "High");
  result.classList.toggle("is-critical-priority", ticket.priority === "Critical");
  const reference = makeElement("span", "ticket-reference", ticket.id);
  const title = makeElement("strong", "lookup-ticket-title", ticket.title);
  const requester = makeElement("span", "lookup-ticket-requester", `Requested by ${ticket.requester}`);
  const details = makeElement("div", "lookup-ticket-details");
  details.append(createPriorityBadge(ticket.priority));
  details.append(makeElement("span", "status-label", ticket.status));
  result.append(reference, title, requester, details);
  return result;
}

async function lookUpTicket(event) {
  event.preventDefault();
  lookupFeedback.hidden = false;
  lookupFeedback.className = "lookup-feedback";
  lookupFeedback.textContent = "Looking up ticket…";
  try {
    const reference = lookupInput.value.trim();
    const ticket = await requestJson(`/api/tickets/${encodeURIComponent(reference)}`);
    lookupFeedback.replaceChildren(createLookupResult(ticket));
  } catch (error) {
    console.error("Ticket lookup failed.", error);
    lookupFeedback.classList.add("is-error");
    lookupFeedback.textContent = error.message === "Ticket not found."
      ? "No active ticket matches that ID. Check the reference and try again."
      : `Ticket lookup failed: ${error.message}`;
  }
}

async function createTicket(event) {
  event.preventDefault();
  if (!validateForm()) {
    return;
  }

  const formData = new FormData(ticketForm);
  const payload = Object.fromEntries(formData.entries());
  try {
    const ticket = await requestJson("/api/tickets", {
      method: "POST",
      body: JSON.stringify(payload)
    });
    ticketForm.reset();
    queuePriority.value = "";
    triagePriority.value = "";
    ticketSearch.value = "";
    await refreshViews();
    showNotice(`Ticket ${ticket.id} created and saved in SQLite.`);
    formFields[0].focus();
  } catch (error) {
    console.error("Unable to create ticket.", error);
    showNotice(`Ticket creation failed: ${error.message}`, true);
  }
}

function clearFilters() {
  ticketSearch.value = "";
  queuePriority.value = "";
  triagePriority.value = "";
  loadTickets().catch((error) => {
    console.error("Unable to clear ticket filters.", error);
    showNotice(`Unable to refresh the queue: ${error.message}`, true);
  });
}

function initializeGatewayFlow() {
  const canvas = document.querySelector("#gateway-flow");
  const hero = canvas?.parentElement;
  const context = canvas?.getContext("2d");
  if (!canvas || !hero || !context) {
    console.error("Unable to initialize the decorative gateway flow canvas.");
    return;
  }

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const streams = Array.from({ length: 30 }, (_, index) => ({
    side: index % 2 === 0 ? "left" : "right",
    start: Math.floor(index / 2) / 14,
    particle: (index * 0.173) % 1,
    speed: 0.000018 + (index % 5) * 0.000003
  }));
  let width = 0;
  let height = 0;
  let frameId = 0;
  let previousTime = 0;
  let isVisible = false;
  let isDisposed = false;

  function resizeCanvas() {
    const bounds = hero.getBoundingClientRect();
    const pixelRatio = Math.min(window.devicePixelRatio || 1, 1.5);
    width = bounds.width;
    height = bounds.height;
    canvas.width = Math.round(width * pixelRatio);
    canvas.height = Math.round(height * pixelRatio);
    context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
    drawFrame();
  }

  function getCurve(stream) {
    const centerX = width * 0.52;
    const centerY = height * 0.49;
    const fromLeft = stream.side === "left";
    const startY = (stream.start * 1.42 - 0.2) * height;
    return {
      startX: fromLeft ? 0 : width,
      startY,
      controlOneX: fromLeft ? width * 0.19 : width * 0.81,
      controlOneY: startY + height * 0.07,
      controlTwoX: fromLeft ? width * 0.4 : width * 0.64,
      controlTwoY: centerY,
      endX: centerX,
      endY: centerY
    };
  }

  function drawFrame(timestamp = 0) {
    context.clearRect(0, 0, width, height);
    const elapsed = previousTime ? Math.min(timestamp - previousTime, 50) : 0;
    previousTime = timestamp;

    for (const stream of streams) {
      const curve = getCurve(stream);
      context.beginPath();
      context.moveTo(curve.startX, curve.startY);
      context.bezierCurveTo(
        curve.controlOneX,
        curve.controlOneY,
        curve.controlTwoX,
        curve.controlTwoY,
        curve.endX,
        curve.endY
      );
      context.strokeStyle = "rgba(183, 205, 235, 0.16)";
      context.lineWidth = 1;
      context.setLineDash([1, 7]);
      context.stroke();

      const t = stream.particle;
      const inverse = 1 - t;
      const particleX = inverse ** 3 * curve.startX
        + 3 * inverse ** 2 * t * curve.controlOneX
        + 3 * inverse * t ** 2 * curve.controlTwoX
        + t ** 3 * curve.endX;
      const particleY = inverse ** 3 * curve.startY
        + 3 * inverse ** 2 * t * curve.controlOneY
        + 3 * inverse * t ** 2 * curve.controlTwoY
        + t ** 3 * curve.endY;
      context.setLineDash([]);
      context.fillStyle = "rgba(222, 235, 252, 0.7)";
      context.fillRect(particleX - 1, particleY - 1, 2, 2);

      if (!reducedMotion.matches) {
        stream.particle = (stream.particle + elapsed * stream.speed) % 1;
      }
    }
  }

  function updateAnimation() {
    if (frameId) {
      window.cancelAnimationFrame(frameId);
      frameId = 0;
    }
    previousTime = 0;
    drawFrame();
    if (isVisible && !document.hidden && !reducedMotion.matches && !isDisposed) {
      frameId = window.requestAnimationFrame(animate);
    }
  }

  function animate(timestamp) {
    if (!isVisible || document.hidden || reducedMotion.matches || isDisposed) {
      frameId = 0;
      return;
    }
    drawFrame(timestamp);
    frameId = window.requestAnimationFrame(animate);
  }

  const visibilityObserver = new IntersectionObserver(([entry]) => {
    isVisible = entry.isIntersecting;
    updateAnimation();
  });
  visibilityObserver.observe(hero);
  window.addEventListener("resize", resizeCanvas);
  document.addEventListener("visibilitychange", updateAnimation);
  reducedMotion.addEventListener("change", updateAnimation);
  window.addEventListener("pagehide", () => {
    isDisposed = true;
    visibilityObserver.disconnect();
    window.removeEventListener("resize", resizeCanvas);
    document.removeEventListener("visibilitychange", updateAnimation);
    reducedMotion.removeEventListener("change", updateAnimation);
    if (frameId) {
      window.cancelAnimationFrame(frameId);
    }
  }, { once: true });
  resizeCanvas();
}

async function applyPriorityFilter(value) {
  queuePriority.value = value;
  triagePriority.value = value;
  try {
    await loadTickets();
  } catch (error) {
    console.error("Unable to filter tickets by priority.", error);
    showNotice(`Priority filter failed: ${error.message}`, true);
  }
}

ticketForm.addEventListener("submit", createTicket);
ticketForm.addEventListener("input", (event) => event.target.setCustomValidity(""));
ticketSearch.addEventListener("input", () => {
  window.clearTimeout(searchTimer);
  searchTimer = window.setTimeout(() => {
    loadTickets().catch((error) => {
      console.error("Ticket search failed.", error);
      showNotice(`Ticket search failed: ${error.message}`, true);
    });
  }, 160);
});
queuePriority.addEventListener("change", () => applyPriorityFilter(queuePriority.value));
triagePriority.addEventListener("change", () => applyPriorityFilter(triagePriority.value));
lookupForm.addEventListener("submit", lookUpTicket);

async function initializeApp() {
  const isHealthy = await refreshHealth();
  if (!isHealthy) {
    showNotice("The ticket service is unavailable. Start the FastAPI server, then reload this page.", true);
  }
  refreshTimer = window.setInterval(refreshHealth, 30000);
  if (!isHealthy) {
    return;
  }
  try {
    await importLegacyTickets();
    await refreshViews();
  } catch (error) {
    console.error("Unable to initialize the support workspace.", error);
    showNotice(`The ticket workspace could not load: ${error.message}`, true);
  }
}

window.addEventListener("pagehide", () => window.clearInterval(refreshTimer), { once: true });
initializeGatewayFlow();
initializeApp();
