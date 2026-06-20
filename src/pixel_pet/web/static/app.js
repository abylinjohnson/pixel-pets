const clockTimeEl  = document.querySelector("#clockTime");
const clockDateEl  = document.querySelector("#clockDate");
const clockDateSub = document.querySelector("#clockDateSub");
const greetingEl   = document.querySelector("#greeting");

const goalForm = document.querySelector("#goalForm");
const goalText = document.querySelector("#goalText");
const goalHours = document.querySelector("#goalHours");
const goalRing = document.querySelector("#goalRing");
const goalRingText = document.querySelector("#goalRingText");
const goalStatus = document.querySelector("#goalStatus");
const goalSummary = document.querySelector("#goalSummary");
const goalProgressBar = document.querySelector("#goalProgressBar");
const goalProgressDetail = document.querySelector("#goalProgressDetail");
const goalProgressFill = document.querySelector("#goalProgressFill");
const goalProgressText = document.querySelector("#goalProgressText");
const historyRange = document.querySelector("#historyRange");
const historyList = document.querySelector("#historyList");
const topTitles = document.querySelector("#topTitles");
const timelineGraph = document.querySelector("#timelineGraph");
const timelineList = document.querySelector("#timelineList");
const focusScore = document.querySelector("#focusScore");
const focusStreak = document.querySelector("#focusStreak");
const productiveTime = document.querySelector("#productiveTime");
const nonProductiveTime = document.querySelector("#nonProductiveTime");
const productiveSplit = document.querySelector("#productiveSplit");
let currentGoal = null;

function formatMinutes(minutes) {
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;

  if (hours === 0) {
    return `${mins}m`;
  }

  return `${hours}h ${mins}m`;
}

function formatDate(dateText) {
  const date = new Date(`${dateText}T00:00:00`);

  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll("\"", "&quot;")
    .replaceAll("'", "&#039;");
}

async function loadGoal() {
  const response = await fetch("/api/goals/today");
  const data = await response.json();

  renderGoal(data.goal);
}

function renderGoal(goal) {
  currentGoal = goal;

  if (!goal) {
    goalStatus.textContent = "No goal set";
    goalSummary.textContent = "Set a goal to guide today's focus.";
    renderGoalProgress(0);
    return;
  }

  goalText.value = goal.text;
  goalHours.value = goal.target_minutes / 60;
  goalStatus.textContent = `${formatMinutes(goal.target_minutes)} goal set`;
  goalSummary.textContent = goal.text;
}

async function loadSummary() {
  const days = historyRange.value;
  const response = await fetch(`/api/summary?days=${days}`);
  const summary = await response.json();

  renderSummary(summary);
}

function renderSummary(summary) {
  const today = summary.today;
  const totalToday = today.productive + today.nonproductive;

  focusScore.textContent = summary.focus_score;
  focusStreak.textContent = `${summary.focus_streak} days`;
  productiveTime.textContent = formatMinutes(today.productive);
  nonProductiveTime.textContent = formatMinutes(today.nonproductive);

  productiveSplit.textContent = totalToday
    ? `${summary.focus_score}% of tracked time.`
    : "No tracked activity yet.";
  renderGoalProgress(today.productive);

  historyList.innerHTML = summary.history
    .map((row) => {
      const rowTotal = row.productive + row.nonproductive;
      const productiveWidth = rowTotal
        ? Math.round((row.productive / rowTotal) * 100)
        : 0;
      const nonProductiveWidth = rowTotal ? 100 - productiveWidth : 0;

      return `
        <div class="history-row">
          <div class="history-date">${formatDate(row.date)}</div>
          <div class="stacked-bar" aria-label="${row.date} activity split">
            <span
              class="productive-bar"
              style="width: ${productiveWidth}%"
            ></span>
            <span
              class="nonproductive-bar"
              style="width: ${nonProductiveWidth}%"
            ></span>
          </div>
          <div class="history-totals">
            ${formatMinutes(row.productive)} productive / ${formatMinutes(row.nonproductive)} not
          </div>
        </div>
      `;
    })
    .join("");

  renderUsageChart(topTitles, summary.top_titles, "No tab or window data yet.");
  renderTimelineGraph(summary.timeline_graph);
  renderTimeline(summary.timeline);
}

function renderGoalProgress(productiveMinutes) {
  if (!currentGoal) {
    goalRing.style.setProperty("--progress", "0deg");
    goalRing.setAttribute("aria-valuenow", "0");
    goalRingText.textContent = "0%";
    goalProgressText.textContent = "0%";
    goalProgressFill.style.width = "0%";
    goalProgressBar.setAttribute("aria-valuenow", "0");
    goalProgressDetail.textContent = "Set a goal to track progress.";
    return;
  }

  const targetMinutes = currentGoal.target_minutes;
  const progress = Math.min(
    100,
    Math.round((productiveMinutes / targetMinutes) * 100),
  );
  const remainingMinutes = Math.max(0, targetMinutes - productiveMinutes);

  goalProgressText.textContent = `${progress}%`;
  goalRing.style.setProperty("--progress", `${progress * 3.6}deg`);
  goalRing.setAttribute("aria-valuenow", String(progress));
  goalRingText.textContent = `${progress}%`;
  goalProgressFill.style.width = `${progress}%`;
  goalProgressBar.setAttribute("aria-valuenow", String(progress));

  if (remainingMinutes === 0) {
    goalProgressDetail.textContent = `${formatMinutes(productiveMinutes)} logged. Goal completed.`;
    return;
  }

  goalProgressDetail.textContent = `${formatMinutes(productiveMinutes)} of ${formatMinutes(targetMinutes)} completed. ${formatMinutes(remainingMinutes)} remaining.`;
}

function renderUsageChart(container, rows, emptyMessage) {
  if (!rows || rows.length === 0) {
    container.innerHTML = `<div class="empty-state">${emptyMessage}</div>`;
    return;
  }

  const maxMinutes = Math.max(...rows.map((row) => row.minutes), 1);

  container.innerHTML = rows
    .map((row) => {
      const width = Math.max(6, Math.round((row.minutes / maxMinutes) * 100));

      return `
        <div class="chart-row">
          <div class="chart-meta">
            <strong title="${escapeHtml(row.name)}">${escapeHtml(row.name)}</strong>
            <span>${formatMinutes(row.minutes)}</span>
          </div>
          <div class="usage-track">
            <span style="width: ${width}%"></span>
          </div>
        </div>
      `;
    })
    .join("");
}

function renderTimeline(rows) {
  if (!rows || rows.length === 0) {
    timelineList.innerHTML = "<div class=\"empty-state\">No timeline data yet.</div>";
    return;
  }

  timelineList.innerHTML = rows
    .map((item) => {
      const timestamp = new Date(item.timestamp).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      });

      if (item.type === "window") {
        return `
          <div class="timeline-row ${item.bucket}">
            <span>${timestamp}</span>
            <div>
              <strong>${escapeHtml(item.process_name)}</strong>
              <p>${escapeHtml(item.title)}</p>
            </div>
            <em>${formatMinutes(item.minutes)}</em>
          </div>
        `;
      }

      return `
        <div class="timeline-row status">
          <span>${timestamp}</span>
          <div>
            <strong>${formatEventType(item.event_type)}</strong>
            <p>${escapeHtml(JSON.stringify(item.payload))}</p>
          </div>
          <em>Status</em>
        </div>
      `;
    })
    .join("");
}

function renderTimelineGraph(graph) {
  if (!graph || !graph.segments || graph.segments.length === 0) {
    timelineGraph.innerHTML = "<div class=\"empty-state\">No AFK or active work data yet.</div>";
    return;
  }

  const totalMinutes = graph.segments.reduce(
    (total, segment) => total + segment.minutes,
    0,
  );

  timelineGraph.innerHTML = `
    <div class="timeline-legend">
      <span class="legend productive">Productive</span>
      <span class="legend nonproductive">Non productive</span>
      <span class="legend afk">AFK</span>
    </div>
    <div class="timeline-segments">
      ${graph.segments
        .map((segment) => {
          const width = Math.max(
            3,
            Math.round((segment.minutes / totalMinutes) * 100),
          );
          const title = `${segment.label} - ${formatMinutes(segment.minutes)}`;

          return `
            <span
              class="timeline-segment ${segment.type}"
              style="width: ${width}%"
              title="${escapeHtml(title)}"
            ></span>
          `;
        })
        .join("")}
    </div>
    <div class="timeline-scale">
      <span>${formatGraphTime(graph.started_at)}</span>
      <span>${formatGraphTime(graph.ended_at)}</span>
    </div>
  `;
}

function formatGraphTime(value) {
  if (!value) {
    return "--";
  }

  return new Date(value).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatEventType(eventType) {
  return eventType
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

goalForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const targetMinutes = Math.round(Number(goalHours.value) * 60);
  const response = await fetch("/api/goals/today", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      text: goalText.value.trim(),
      target_minutes: targetMinutes,
    }),
  });
  const data = await response.json();

  renderGoal(data.goal);
  await loadSummary();
});

historyRange.addEventListener("change", loadSummary);

function updateClock() {
  const now = new Date();
  const hour = now.getHours();

  if (clockTimeEl) {
    clockTimeEl.textContent = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  const fullDate = now.toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" });
  const shortDate = now.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" });

  if (clockDateEl)  clockDateEl.textContent  = fullDate;
  if (clockDateSub) clockDateSub.textContent = shortDate;

  if (greetingEl) {
    const greet = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
    greetingEl.textContent = greet;
  }
}

async function boot() {
  updateClock();
  window.setInterval(updateClock, 30000);

  await loadGoal();
  await loadSummary();
  window.setInterval(loadSummary, 15000);
}

boot();
