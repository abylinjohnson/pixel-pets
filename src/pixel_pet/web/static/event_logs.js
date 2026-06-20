const eventList = document.querySelector("#eventList");


function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll("\"", "&quot;")
    .replaceAll("'", "&#039;");
}


async function loadEvents() {
  const response = await fetch("/api/events?limit=100");
  const data = await response.json();

  if (data.events.length === 0) {
    eventList.innerHTML = "<div class=\"event-row\">No events captured yet.</div>";
    return;
  }

  eventList.innerHTML = data.events
    .map((event) => {
      const timestamp = new Date(event.timestamp).toLocaleString();
      const payload = JSON.stringify(event.payload, null, 2);

      return `
        <div class="event-row">
          <span>${timestamp}</span>
          <strong>${escapeHtml(event.event_type)}</strong>
          <code>${escapeHtml(payload)}</code>
        </div>
      `;
    })
    .join("");
}


loadEvents();
window.setInterval(loadEvents, 5000);
