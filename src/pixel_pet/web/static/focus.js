/* ── State ──────────────────────────────────────────────────────── */

const state = {
  phase: "setup",
  sessionId: null,
  task: "",
  goal: "",
  plannedSeconds: 0,
  remainingSeconds: 0,
  startedAt: null,
  timerId: null,
  viewingPast: false,
};

/* ── DOM refs ───────────────────────────────────────────────────── */

const phaseSetup  = document.getElementById("phaseSetup");
const phaseActive = document.getElementById("phaseActive");
const phaseDone   = document.getElementById("phaseDone");

const setupForm    = document.getElementById("setupForm");
const setupTask    = document.getElementById("setupTask");
const setupGoal    = document.getElementById("setupGoal");
const setupMinutes = document.getElementById("setupMinutes");
const presetBtns   = document.querySelectorAll(".preset-btn");

const bigTimer             = document.getElementById("bigTimer");
const timerStatus          = document.getElementById("timerStatus");
const btnStartPause        = document.getElementById("btnStartPause");
const btnEnd               = document.getElementById("btnEnd");
const activeTask           = document.getElementById("activeTask");
const activeGoal           = document.getElementById("activeGoal");
const activeGoalRow        = document.getElementById("activeGoalRow");
const distractionCount     = document.getElementById("distractionCount");
const distractionList      = document.getElementById("distractionList");
const sessionProgressFill  = document.getElementById("sessionProgressFill");
const elapsedLabel         = document.getElementById("elapsedLabel");
const remainingLabel       = document.getElementById("remainingLabel");

const doneTitle        = document.getElementById("doneTitle");
const doneDuration     = document.getElementById("doneDuration");
const aiSummaryText    = document.getElementById("aiSummaryText");
const statFocus        = document.getElementById("statFocus");
const statProductive   = document.getElementById("statProductive");
const statDistractions = document.getElementById("statDistractions");
const statDuration     = document.getElementById("statDuration");
const sessionWindows   = document.getElementById("sessionWindows");
const sessionTimeline  = document.getElementById("sessionTimeline");
const btnNewSession    = document.getElementById("btnNewSession");
const btnBackToHistory = document.getElementById("btnBackToHistory");

// History
const sessionHistory      = document.getElementById("sessionHistory");
const sessionHistoryList  = document.getElementById("sessionHistoryList");
const sessionHistoryCount = document.getElementById("sessionHistoryCount");

/* ── Helpers ────────────────────────────────────────────────────── */

function formatTimer(seconds) {
  const m = Math.floor(seconds / 60).toString().padStart(2, "0");
  const s = (seconds % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

function formatMinutes(minutes) {
  const n = Math.round(minutes);
  if (n < 60) return `${n}m`;
  const h = Math.floor(n / 60);
  const m = n % 60;
  return m === 0 ? `${h}h` : `${h}h ${m}m`;
}

function formatRelative(isoString) {
  if (!isoString) return "—";
  const diff = Date.now() - new Date(isoString).getTime();
  const mins  = Math.floor(diff / 60000);
  const hours = Math.floor(mins / 60);
  const days  = Math.floor(hours / 24);
  if (days > 0)  return `${days}d ago`;
  if (hours > 0) return `${hours}h ago`;
  if (mins > 1)  return `${mins}m ago`;
  return "just now";
}

function escapeHtml(v) {
  return String(v)
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;").replaceAll('"', "&quot;");
}

/* ── Phase switching ────────────────────────────────────────────── */

function showPhase(phase) {
  phaseSetup.hidden  = phase !== "setup";
  phaseActive.hidden = phase !== "active" && phase !== "paused";
  phaseDone.hidden   = phase !== "done";
  if (sessionHistory) sessionHistory.hidden = phase !== "setup";
  state.phase = phase;
}

/* ── Session history ────────────────────────────────────────────── */

async function loadSessionHistory() {
  try {
    const res  = await fetch("/api/focus-sessions/recent?limit=10");
    const data = await res.json();
    renderSessionHistory(data.sessions || []);
  } catch (_) {}
}

function renderSessionHistory(sessions) {
  if (!sessions.length) return;

  sessionHistory.hidden = state.phase !== "setup";
  sessionHistoryCount.textContent = `${sessions.length} session${sessions.length !== 1 ? "s" : ""}`;

  sessionHistoryList.innerHTML = sessions.map((s) => {
    const when     = formatRelative(s.created_at);
    const duration = s.started_at && s.ended_at
      ? formatMinutes(Math.round((new Date(s.ended_at) - new Date(s.started_at)) / 60000))
      : formatMinutes(s.planned_minutes) + " planned";
    const isActive   = s.status === "active" && !s.ended_at;
    const isComplete = s.status === "completed" && s.ended_at;

    const badge = isActive
      ? `<span class="sh-badge sh-badge--active">Active</span>`
      : isComplete
        ? `<span class="sh-badge sh-badge--done">Done</span>`
        : `<span class="sh-badge">Planned</span>`;

    return `
      <div class="sh-row" data-id="${s.id}" data-active="${isActive}" role="button" tabindex="0">
        <div class="sh-row-main">
          <div class="sh-task">${escapeHtml(s.task)}</div>
          ${s.goal ? `<div class="sh-goal">${escapeHtml(s.goal)}</div>` : ""}
        </div>
        <div class="sh-row-meta">
          ${badge}
          <span class="sh-duration">${duration}</span>
          <span class="sh-when">${when}</span>
          ${isActive
            ? `<button class="sh-resume-btn" data-id="${s.id}" data-task="${escapeHtml(s.task)}" data-goal="${escapeHtml(s.goal || "")}" data-planned="${s.planned_minutes}" data-started="${s.started_at || ""}">Resume</button>`
            : isComplete
              ? `<svg class="sh-chevron" width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 5 7 8 10 5"/></svg>`
              : ""
          }
        </div>
      </div>
    `;
  }).join("");

  sessionHistoryList.querySelectorAll(".sh-row").forEach((row) => {
    const handler = (e) => {
      if (e.target.classList.contains("sh-resume-btn")) return;
      const id = Number(row.dataset.id);
      if (row.dataset.active === "true") return;
      viewPastSession(id);
    };
    row.addEventListener("click", handler);
    row.addEventListener("keydown", (e) => { if (e.key === "Enter") handler(e); });
  });

  sessionHistoryList.querySelectorAll(".sh-resume-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      resumeSession({
        id:      Number(btn.dataset.id),
        task:    btn.dataset.task,
        goal:    btn.dataset.goal,
        planned: Number(btn.dataset.planned),
        started: btn.dataset.started,
      });
    });
  });
}

function resumeSession({ id, task, goal, planned, started }) {
  const plannedSeconds  = planned * 60;
  const elapsedSeconds  = started
    ? Math.floor((Date.now() - new Date(started).getTime()) / 1000)
    : 0;
  const remaining = Math.max(0, plannedSeconds - elapsedSeconds);

  state.sessionId        = id;
  state.task             = task;
  state.goal             = goal;
  state.plannedSeconds   = plannedSeconds;
  state.remainingSeconds = remaining;
  state.startedAt        = started ? new Date(started) : new Date();

  activeTask.textContent = task;
  if (goal) {
    activeGoal.textContent = goal;
    activeGoalRow.hidden = false;
  } else {
    activeGoalRow.hidden = true;
  }

  renderTimer();
  renderProgress();
  showPhase("active");

  if (remaining > 0) {
    startTimer(false);
  } else {
    timerStatus.textContent = "Time was up — session ended.";
    btnStartPause.disabled = true;
  }
}

/* ── Past session view (replaces drawer) ───────────────────────── */

async function viewPastSession(sessionId) {
  state.viewingPast = true;

  doneTitle.textContent    = "Session Review";
  doneDuration.textContent = "Loading…";
  aiSummaryText.textContent = "Loading…";
  statFocus.textContent        = "—";
  statProductive.textContent   = "—";
  statDistractions.textContent = "—";
  statDuration.textContent     = "—";
  sessionWindows.innerHTML     = "";
  sessionTimeline.innerHTML    = "";

  btnNewSession.hidden    = true;
  btnBackToHistory.hidden = false;

  showPhase("done");

  try {
    const res  = await fetch(`/api/focus-sessions/${sessionId}/analytics`);
    const data = await res.json();
    const a    = data.analytics;

    doneDuration.textContent = a.session.task;

    renderAnalytics(a, {
      focusEl: statFocus, productiveEl: statProductive,
      distractionsEl: statDistractions, durationEl: statDuration,
      windowsEl: sessionWindows, timelineEl: sessionTimeline,
    });

    if (a.session.summary) {
      aiSummaryText.textContent = a.session.summary;
    } else {
      requestSummary(sessionId, aiSummaryText);
    }
  } catch (_) {
    doneDuration.textContent  = "Could not load session.";
    aiSummaryText.textContent = "";
  }
}

/* ── Setup form ─────────────────────────────────────────────────── */

presetBtns.forEach((btn) => {
  btn.addEventListener("click", () => { setupMinutes.value = btn.dataset.minutes; });
});

setupForm.addEventListener("submit", async (e) => {
  e.preventDefault();

  const task           = setupTask.value.trim();
  const goal           = setupGoal.value.trim();
  const plannedMinutes = Number(setupMinutes.value);

  if (!task) { setupTask.focus(); return; }

  const res  = await fetch("/api/focus-sessions", {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify({ task, goal, planned_minutes: plannedMinutes }),
  });
  const data = await res.json();
  const session = data.session;

  state.sessionId        = session.id;
  state.task             = session.task;
  state.goal             = session.goal || "";
  state.plannedSeconds   = session.planned_minutes * 60;
  state.remainingSeconds = state.plannedSeconds;
  state.startedAt        = null;

  activeTask.textContent = state.task;
  if (state.goal) {
    activeGoal.textContent = state.goal;
    activeGoalRow.hidden = false;
  } else {
    activeGoalRow.hidden = true;
  }

  renderTimer();
  renderProgress();
  showPhase("active");

  setTimeout(() => startTimer(true), 350);
});

/* ── Timer ──────────────────────────────────────────────────────── */

async function startTimer(notifyServer = true) {
  if (!state.startedAt) {
    state.startedAt = new Date();
    if (notifyServer) await setFocusActive(true);
  }

  if (state.timerId) return;

  state.phase  = "active";
  state.timerId = window.setInterval(tick, 1000);
  btnStartPause.textContent = "Pause";
  timerStatus.textContent   = `Working on: ${state.task}`;
}

function pauseTimer() {
  window.clearInterval(state.timerId);
  state.timerId = null;
  state.phase   = "paused";
  btnStartPause.textContent = "Resume";
  timerStatus.textContent   = "Paused";
}

function tick() {
  state.remainingSeconds = Math.max(0, state.remainingSeconds - 1);
  renderTimer();
  renderProgress();

  if (state.remainingSeconds <= 0) {
    window.clearInterval(state.timerId);
    state.timerId = null;
    timerStatus.textContent = "Time's up!";
    endSession(true);
  }
}

function renderTimer() {
  bigTimer.textContent = formatTimer(state.remainingSeconds);
}

function renderProgress() {
  const elapsed = state.plannedSeconds - state.remainingSeconds;
  const pct     = state.plannedSeconds > 0
    ? Math.min(100, Math.round((elapsed / state.plannedSeconds) * 100))
    : 0;
  sessionProgressFill.style.width = `${pct}%`;
  elapsedLabel.textContent   = formatMinutes(elapsed / 60) + " elapsed";
  remainingLabel.textContent = formatMinutes(state.remainingSeconds / 60) + " left";
}

btnStartPause.addEventListener("click", () => {
  if (state.timerId) pauseTimer();
  else startTimer(true);
});

btnEnd.addEventListener("click", () => {
  if (!confirm("End this session now and see your analytics?")) return;
  if (state.timerId) { window.clearInterval(state.timerId); state.timerId = null; }
  endSession(false);
});

/* ── Focus state sync ───────────────────────────────────────────── */

async function setFocusActive(active) {
  try {
    await fetch("/api/focus-sessions/active", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({
        active,
        session_id: state.sessionId,
        task:       state.task,
        goal:       state.goal,
      }),
    });
  } catch (_) {}
}

/* ── Session end ────────────────────────────────────────────────── */

async function endSession(natural) {
  await setFocusActive(false);

  state.viewingPast = false;
  doneTitle.textContent = "Session complete";
  btnNewSession.hidden    = false;
  btnBackToHistory.hidden = true;

  const elapsed = state.plannedSeconds - state.remainingSeconds;
  doneDuration.textContent = natural
    ? `Completed ${formatMinutes(state.plannedSeconds)} session`
    : `Ended after ${formatMinutes(Math.floor(elapsed / 60))}`;

  aiSummaryText.textContent = "Generating summary…";

  showPhase("done");

  if (state.sessionId) {
    try {
      const res  = await fetch(`/api/focus-sessions/${state.sessionId}/analytics`);
      const data = await res.json();
      const a    = data.analytics;

      renderAnalytics(a, {
        focusEl: statFocus, productiveEl: statProductive,
        distractionsEl: statDistractions, durationEl: statDuration,
        windowsEl: sessionWindows, timelineEl: sessionTimeline,
      });

      if (a.session.summary) {
        aiSummaryText.textContent = a.session.summary;
      } else {
        requestSummary(state.sessionId, aiSummaryText);
      }
    } catch (_) {
      aiSummaryText.textContent = "Analytics unavailable.";
    }
  }
}

/* ── Analytics rendering ────────────────────────────────────────── */

function renderAnalytics(a, els) {
  const { focusEl, productiveEl, distractionsEl, durationEl, windowsEl, timelineEl } = els;

  if (focusEl)        focusEl.textContent        = `${a.focus_percentage}%`;
  if (productiveEl)   productiveEl.textContent   = formatMinutes(a.productive_minutes);
  if (distractionsEl) distractionsEl.textContent = String(a.distraction_count);
  if (durationEl)     durationEl.textContent     = formatMinutes(a.duration_minutes);

  if (windowsEl) {
    if (a.windows && a.windows.length > 0) {
      const maxMin = Math.max(...a.windows.map((w) => w.minutes), 1);
      windowsEl.innerHTML = a.windows.map((w) => {
        const pct = Math.max(6, Math.round((w.minutes / maxMin) * 100));
        const isDistract = a.timeline.some((t) => t.title === w.name && t.bucket === "nonproductive");
        return `
          <div class="chart-row">
            <div class="chart-meta">
              <strong title="${escapeHtml(w.name)}">${escapeHtml(w.name)}</strong>
              <span>${formatMinutes(w.minutes)}</span>
            </div>
            <div class="usage-track ${isDistract ? "track-distract" : ""}">
              <span style="width:${pct}%"></span>
            </div>
          </div>`;
      }).join("");
    } else {
      windowsEl.innerHTML = `<div class="empty-state">No window data recorded.</div>`;
    }
  }

  if (timelineEl) {
    if (a.timeline && a.timeline.length > 0) {
      timelineEl.innerHTML = a.timeline.map((t) => {
        const time = new Date(t.started_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
        return `
          <div class="timeline-row ${t.bucket}">
            <span>${time}</span>
            <div>
              <strong>${escapeHtml(t.process_name)}</strong>
              <p>${escapeHtml(t.title)}</p>
            </div>
            <em>${formatMinutes(t.minutes)}</em>
          </div>`;
      }).join("");
    } else {
      timelineEl.innerHTML = `<div class="empty-state">No timeline data.</div>`;
    }
  }
}

async function requestSummary(sessionId, el) {
  if (!el) return;
  try {
    const res  = await fetch(`/api/focus-sessions/${sessionId}/summary`, { method: "POST" });
    const data = await res.json();
    el.textContent = data.summary || "Great work completing your session!";
  } catch (_) {
    el.textContent = "Great work completing your session!";
  }
}

/* ── Done phase actions ─────────────────────────────────────────── */

btnNewSession.addEventListener("click", () => {
  state.viewingPast = false;
  setupTask.value    = "";
  setupGoal.value    = "";
  setupMinutes.value = "25";
  state.sessionId    = null;
  distractionList.innerHTML = `<div class="empty-state">No distractions yet. Keep it up.</div>`;
  distractionCount.textContent = "0";
  btnNewSession.hidden    = false;
  btnBackToHistory.hidden = true;
  showPhase("setup");
  loadSessionHistory();
});

btnBackToHistory.addEventListener("click", () => {
  state.viewingPast = false;
  btnNewSession.hidden    = false;
  btnBackToHistory.hidden = true;
  showPhase("setup");
});

/* ── Boot ───────────────────────────────────────────────────────── */

async function boot() {
  showPhase("setup");
  await loadSessionHistory();
}

boot();
