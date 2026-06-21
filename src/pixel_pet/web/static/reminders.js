const tabOnce       = document.getElementById("tabOnce");
const tabRecurring  = document.getElementById("tabRecurring");
const onceOptions   = document.getElementById("onceOptions");
const recurringOpts = document.getElementById("recurringOptions");
const timeInput     = document.getElementById("reminderTime");
const dateInput     = document.getElementById("reminderDate");
const labelInput    = document.getElementById("reminderLabel");
const btnSave       = document.getElementById("btnSaveReminder");
const formNote      = document.getElementById("reminderFormNote");
const listEl        = document.getElementById("reminderList");
const countBadge    = document.getElementById("reminderCount");

let currentType  = "once";
let selectedDays = new Set();

// Default date to today
const todayStr = new Date().toISOString().slice(0, 10);
dateInput.min   = todayStr;
dateInput.value = todayStr;

// ── Tab switching ──────────────────────────────────────────────────────────

tabOnce.addEventListener("click", () => {
  currentType = "once";
  tabOnce.classList.add("active");
  tabRecurring.classList.remove("active");
  onceOptions.hidden   = false;
  recurringOpts.hidden = true;
});

tabRecurring.addEventListener("click", () => {
  currentType = "recurring";
  tabRecurring.classList.add("active");
  tabOnce.classList.remove("active");
  onceOptions.hidden   = true;
  recurringOpts.hidden = false;
});

// ── Day chip toggle ────────────────────────────────────────────────────────

document.querySelectorAll(".day-chip").forEach(chip => {
  chip.addEventListener("click", () => {
    const day = parseInt(chip.dataset.day, 10);
    if (selectedDays.has(day)) {
      selectedDays.delete(day);
      chip.classList.remove("selected");
    } else {
      selectedDays.add(day);
      chip.classList.add("selected");
    }
  });
});

// ── Save ───────────────────────────────────────────────────────────────────

btnSave.addEventListener("click", async () => {
  const label = labelInput.value.trim();
  const time  = timeInput.value;

  if (!label) { showNote("Please enter a label.", "error"); return; }
  if (!time)  { showNote("Please set a time.", "error");   return; }

  const body = { label, reminder_type: currentType };

  if (currentType === "once") {
    const date = dateInput.value;
    if (!date) { showNote("Please pick a date.", "error"); return; }
    body.remind_at = `${date}T${time}`;
  } else {
    if (!selectedDays.size) { showNote("Pick at least one day.", "error"); return; }
    body.days_of_week = [...selectedDays].sort((a, b) => a - b).join(",");
    body.time_of_day  = time;
  }

  try {
    const res = await fetch("/api/reminders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json();
      showNote(err.error || "Failed to save.", "error");
      return;
    }
    showNote("Reminder saved!", "success");
    labelInput.value = "";
    selectedDays.clear();
    document.querySelectorAll(".day-chip").forEach(c => c.classList.remove("selected"));
    loadReminders();
  } catch {
    showNote("Failed to save.", "error");
  }
});

function showNote(msg, type) {
  formNote.textContent = msg;
  formNote.className   = `reminder-form-note reminder-form-note--${type}`;
  formNote.hidden      = false;
  setTimeout(() => { formNote.hidden = true; }, 3000);
}

// ── List ───────────────────────────────────────────────────────────────────

async function loadReminders() {
  const res  = await fetch("/api/reminders");
  const data = await res.json();
  renderList(data.reminders || []);
}

function formatTime12(hhmm) {
  if (!hhmm) return "";
  const [h, m] = hhmm.split(":").map(Number);
  const period = h >= 12 ? "PM" : "AM";
  const h12    = h % 12 || 12;
  return `${h12}:${String(m).padStart(2, "0")} ${period}`;
}

const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function formatDays(daysStr) {
  if (!daysStr) return "";
  return daysStr.split(",").map(d => DAY_NAMES[parseInt(d, 10)]).join(", ");
}

function formatOnceDate(remindAt) {
  if (!remindAt) return "";
  const dt = new Date(remindAt);
  if (isNaN(dt)) return remindAt;
  return dt.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

function renderList(reminders) {
  countBadge.hidden      = !reminders.length;
  countBadge.textContent = reminders.length;

  if (!reminders.length) {
    listEl.innerHTML = `<div class="empty-state" style="margin:16px;">No reminders yet. Add one on the left.</div>`;
    return;
  }

  listEl.innerHTML = reminders.map(r => {
    const timeStr = r.reminder_type === "once"
      ? formatTime12((r.remind_at || "").slice(11, 16))
      : formatTime12(r.time_of_day);

    const sub = r.reminder_type === "once"
      ? `Once · ${formatOnceDate(r.remind_at)}`
      : `Every ${formatDays(r.days_of_week)}`;

    const inactive = r.active ? "" : " inactive";

    return `<div class="reminder-item${inactive}" data-id="${r.id}">
  <div class="reminder-item-time">${timeStr}</div>
  <div class="reminder-item-meta">
    <div class="reminder-item-label">${escHtml(r.label)}</div>
    <div class="reminder-item-sub">${escHtml(sub)}</div>
  </div>
  <div class="reminder-item-actions">
    <label class="toggle" title="${r.active ? "Disable" : "Enable"}">
      <input type="checkbox" ${r.active ? "checked" : ""} onchange="toggleR(${r.id}, this.checked)">
      <span class="toggle-track"></span>
    </label>
    <button class="btn-icon-del" onclick="deleteR(${r.id})" title="Delete">
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round">
        <polyline points="2 3.5 12 3.5"/>
        <path d="M5 3.5V2.5h4v1"/>
        <path d="M3 3.5l.7 8h6.6l.7-8"/>
      </svg>
    </button>
  </div>
</div>`;
  }).join("");
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

async function toggleR(id, active) {
  await fetch(`/api/reminders/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ active }),
  });
  loadReminders();
}

async function deleteR(id) {
  await fetch(`/api/reminders/${id}`, { method: "DELETE" });
  loadReminders();
}

loadReminders();
