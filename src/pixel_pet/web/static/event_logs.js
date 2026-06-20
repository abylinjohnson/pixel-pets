const eventList = document.querySelector("#eventList");

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll("\"", "&quot;")
    .replaceAll("'", "&#039;");
}

function badgeClass(eventType) {
  if (eventType.startsWith("active_window")) return "type-window";
  if (eventType.startsWith("user_idle") || eventType.startsWith("user_active") ||
      eventType.startsWith("user_absent") || eventType.startsWith("user_present")) return "type-idle";
  if (eventType.startsWith("camera")) return "type-camera";
  return "type-default";
}

function formatEventLabel(eventType) {
  return eventType.replace(/_/g, " ");
}

async function loadEvents() {
  const response = await fetch("/api/events?limit=100");
  const data = await response.json();

  if (data.events.length === 0) {
    eventList.innerHTML = `
      <div class="empty-state">
        No events captured yet. Start using your computer to see activity here.
      </div>`;
    return;
  }

  eventList.innerHTML = data.events
    .map((event) => {
      const date = new Date(event.timestamp);
      const timeStr = date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
      const payload = JSON.stringify(event.payload, null, 2);
      const cls = badgeClass(event.event_type);

      return `
        <div class="event-row">
          <div class="event-row-meta">
            <span class="event-time">${escapeHtml(timeStr)}</span>
            <span class="event-badge ${cls}">${escapeHtml(formatEventLabel(event.event_type))}</span>
          </div>
          <pre class="event-payload">${escapeHtml(payload)}</pre>
        </div>`;
    })
    .join("");
}

loadEvents();
window.setInterval(loadEvents, 5000);
