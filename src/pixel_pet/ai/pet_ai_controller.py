import json
import os
import random
import threading
import time
from collections import deque

from src.pixel_pet.state import FocusState


DISTRACTION_KEYWORDS = (
    # Social media
    "instagram",
    "facebook",
    "twitter",
    "x.com",
    "reddit",
    "tiktok",
    "snapchat",
    "pinterest",
    "tumblr",
    "9gag",
    "buzzfeed",
    "linkedin",
    # Streaming / video
    "netflix",
    "twitch",
    "hulu",
    "disney+",
    "disney plus",
    "prime video",
    "amazon prime",
    "peacock",
    "paramount",
    "apple tv+",
    # Games (title keywords)
    "steam",
    "epic games",
    "minecraft",
    "fortnite",
    "valorant",
    "roblox",
    "league of legends",
    "dota",
    "counter-strike",
    "overwatch",
    # Messaging / chat
    "whatsapp",
    "telegram",
    # Catch-all
    "meme",
    "news feed",
    "trending",
    "shorts",
)

AMBIGUOUS_MEDIA_KEYWORDS = (
    "youtube",
    "twitch.tv",
)

BROWSER_PROCESS_KEYWORDS = (
    "chrome",
    "msedge",
    "firefox",
    "brave",
    "opera",
    "browser",
)

# Process names that are inherently distracting regardless of window title
DISTRACTION_PROCESS_KEYWORDS = (
    "steam",
    "epicgameslauncher",
    "robloxplayerbeta",
    "leagueclient",
    "fortnite",
    "minecraft",
    "discord",
    "valorant",
    "csgo",
    "cs2",
)

CODING_KEYWORDS = (
    "code",
    "visual studio",
    "vscode",
    "pycharm",
    "intellij",
    "cursor",
    "sublime",
    "notepad++",
    "atom",
    "vim",
    "nvim",
    "terminal",
    "powershell",
    "cmd",
    "python",
    "github",
    "git",
)

# Gentle nudge fallbacks shown when a distraction is detected during focus mode.
# These are playful, not harsh — the cat is a companion, not a critic.
NUDGE_FALLBACKS = (
    "hey, that's not quite the plan.",
    "oops, little detour happening.",
    "found something fun? fair enough.",
    "just a gentle heads-up...",
    "that's not what we said we'd do.",
    "hmm, interesting choice.",
    "*soft stare*",
    "whenever you're ready, the work is here.",
    "no judgment. well, a tiny bit.",
    "i noticed. just saying.",
    "the task is still waiting, patiently.",
    "this is fine. totally fine.",
)

# Random idle chatter the cat says unprompted — pure personality, zero judgment.
IDLE_CHATTER = (
    "psst. still here.",
    "did you drink water today?",
    "just sitting here. no reason.",
    "you've been staring at that for a while.",
    "take a breath.",
    "i'm watching over you. you're welcome.",
    "have you stretched recently?",
    "i see everything from up here.",
    "blink. you forgot.",
    "*yawns* don't mind me.",
    "your posture could be better.",
    "i approve of this workspace.",
    "just popping in to say hi.",
    "meow. that was important.",
    "you're doing great.",
    "i had a thought. it passed.",
    "how long have we been sitting here?",
    "this is a nice spot.",
    "you should eat something.",
    "just checking you're still here.",
    "*stares into the distance*",
    "five more minutes then a break?",
    "don't forget to stand up sometimes.",
    "i believe in you.",
    "what are we working on again?",
    "remember to save your work.",
    "i'm comfortable here. just so you know.",
    "cozy in here.",
    "you're very focused today.",
    "i like it when you're around.",
)


class PetAiController:
    _SAME_TITLE_COOLDOWN = 300   # seconds before same exact title nudges again
    _MIN_GAP = 30                # minimum seconds between any two interruptions
    _IDLE_INTERVAL_MIN = 600     # 10 min minimum between idle chatter messages
    _IDLE_INTERVAL_MAX = 1200    # 20 min maximum

    def __init__(
        self,
        pet_handler,
        history_size=12,
        action_cooldown_seconds=12,
        ai_request_cooldown_seconds=25,
        logger=None,
    ):
        self.pet_handler = pet_handler
        self.history = deque(maxlen=history_size)
        self.action_cooldown_seconds = action_cooldown_seconds
        self.ai_request_cooldown_seconds = ai_request_cooldown_seconds
        self.last_action_key = None
        self.last_action_time = 0.0
        self.last_ai_request_time = 0.0
        self._interrupted_titles: dict[str, float] = {}
        self._last_any_interruption_time = 0.0
        self._active_distraction_key: str | None = None
        self.last_coding_relaxed_time = 0.0
        self.sleep_until = 0.0
        self._title_classification_cache = {}
        # Context-aware cache: (title, process, task, goal) → "productive"|"nonproductive"
        self._context_classification_cache: dict[str, str] = {}
        self._lock = threading.Lock()
        self._random = random.Random()
        self._logger = logger or print
        self._model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        # Hard cap on every OpenAI call so a slow request can't stall the
        # tracker poll thread (decisions run synchronously on that thread).
        self._request_timeout = float(os.getenv("OPENAI_TIMEOUT", "6"))
        # Remember the last few spoken lines so the cat doesn't repeat itself.
        self._recent_messages: deque[str] = deque(maxlen=6)
        self._client = self._create_openai_client()

        # Background thread: makes the cat say random things even when idle.
        self._idle_stop = threading.Event()
        self._idle_thread = threading.Thread(target=self._idle_loop, daemon=True)
        self._idle_thread.start()

    # ── Public interface ──────────────────────────────────────────────────────

    def __call__(self, event):
        with self._lock:
            self.history.append(self._event_to_dict(event))
            decision = self._decide_action(event)

            if not decision:
                return

            behavior_key = decision["behavior_key"]
            force = decision.get("force", False)

            if not self._can_perform(behavior_key, force=force):
                return

            self.pet_handler.perform_behavior(behavior_key)

            message = decision.get("message")
            if message:
                self.pet_handler.show_speech(message)

            self.last_action_key = behavior_key
            self.last_action_time = time.time()

    # ── Decision logic ────────────────────────────────────────────────────────

    def _decide_action(self, event):
        event_type = getattr(event.event_type, "value", str(event.event_type))
        payload = event.payload
        session_active = FocusState.is_active()

        # AFK / presence events always trigger animations regardless of session state.
        if event_type in ("user_idle", "user_absent"):
            self.sleep_until = max(self.sleep_until, time.time() + 180)
            return {"behavior_key": "sleep_sequence"}

        if event_type in ("user_active", "user_present"):
            if self._is_sleeping():
                return None
            return {"behavior_key": "return_greeting"}

        if event_type == "active_window_changed":
            # When no focus session is running, observe silently — no API calls,
            # no interruptions, just let the data flow to the DB.
            if not session_active:
                return None

            title_lower = payload.get("title", "").lower()
            title_display = payload.get("title", "something")
            process_name = payload.get("process_name", "").lower()
            url = payload.get("url", "") or ""

            # Our own pet window ("Desktop Cat") isn't a tab the user chose to open —
            # never treat the companion app as a distraction or burn an API call on it.
            if self._is_self_window(title_lower):
                return None

            context = FocusState.get_context()
            attention_state = self._classify_window_attention(
                title_lower, process_name,
                context.get("task", ""),
                context.get("goal", ""),
                url,
            )

            if attention_state == "nonproductive":
                self.sleep_until = 0.0
                now = time.time()

                # Global minimum gap — stops double-fires when the OS sends
                # several window-change events in quick succession.
                if now - self._last_any_interruption_time < self._MIN_GAP:
                    return None

                # Per-title cooldown — the same page won't interrupt again for
                # 5 minutes, but switching to a different distracting title
                # (Netflix → YouTube, YouTube home → F1 video) fires immediately.
                title_key = self._distraction_key(title_lower, process_name, url)
                if now - self._interrupted_titles.get(title_key, 0.0) < self._SAME_TITLE_COOLDOWN:
                    return None

                self._interrupted_titles[title_key] = now
                self._last_any_interruption_time = now
                self._active_distraction_key = title_key
                message = self._get_nudge_message(
                    title_display,
                    context.get("task", ""),
                    context.get("goal", ""),
                    url,
                )
                return {
                    "behavior_key": "distraction_nudge",
                    "message": message,
                    "force": True,
                }

            # User switched to a productive window — clear the cooldown stamp for
            # whatever distraction they just left so the next visit to it fires again.
            if self._active_distraction_key:
                self._interrupted_titles.pop(self._active_distraction_key, None)
                self._active_distraction_key = None

            if self._is_sleeping():
                return None

            if self._is_coding_context(title_lower, process_name):
                relaxed = self._pick_coding_relaxed_action()
                if relaxed:
                    self.sleep_until = time.time() + 180
                    return {"behavior_key": relaxed}

            return {"behavior_key": "focus_groom"}

        return None

    # ── Idle chatter (fires even outside focus mode) ──────────────────────────

    def _idle_loop(self):
        """Background thread: occasionally makes the cat say something unprompted."""
        # Small startup delay so the cat doesn't speak the instant the app opens.
        self._idle_stop.wait(90)
        while not self._idle_stop.wait(
            self._random.uniform(self._IDLE_INTERVAL_MIN, self._IDLE_INTERVAL_MAX)
        ):
            self._maybe_show_idle_chatter()

    def _maybe_show_idle_chatter(self):
        with self._lock:
            if self._is_sleeping():
                return
            # Don't overlap with a recent nudge or previous chatter.
            if time.time() - self._last_any_interruption_time < 90:
                return
            self._last_any_interruption_time = time.time()
            message = self._fresh_message(self._random.choice(IDLE_CHATTER), IDLE_CHATTER)

        self._logger(f"[pet-ai] Idle chatter: {message}")
        self.pet_handler.show_speech(message, duration=8.0)

    # ── Focus-mode nudge via OpenAI ───────────────────────────────────────────

    def _get_nudge_message(self, title_display: str, task: str = "", goal: str = "", url: str = "") -> str:
        """Return a gentle, playful nudge that knows what the user *should* be doing.

        Calls OpenAI when available (with the focus task/goal/URL for context) and
        falls back to a static pool. Either way, avoids repeating a recent line.
        """
        now = time.time()

        if not self._client:
            return self._fresh_message(self._random.choice(NUDGE_FALLBACKS), NUDGE_FALLBACKS)

        if now - self.last_ai_request_time < self.ai_request_cooldown_seconds:
            self._logger("[pet-ai] Nudge message rate-limited; using fallback.")
            return self._fresh_message(self._random.choice(NUDGE_FALLBACKS), NUDGE_FALLBACKS)

        try:
            self._logger(f"[pet-ai] Requesting nudge message for: {title_display}")
            user_context = {"opened": title_display, "url": url, "task": task, "goal": goal}
            response = self._client.responses.create(
                model=self._model,
                input=[
                    {
                        "role": "system",
                        "content": (
                            "You are a small, caring desktop cat companion watching over "
                            "someone who is trying to focus. They just opened something that "
                            "looks off-task. Write ONE gentle, warm nudge of at most 12 words. "
                            "When you know their task, gently tie the nudge back to it "
                            "(e.g. 'the login page misses you'). "
                            "Be playful and kind, never judgmental or harsh. "
                            "No quotes, no emojis. Just the single line."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(user_context),
                    },
                ],
            )
            self.last_ai_request_time = now
            text = response.output_text.strip()

            if text:
                self._logger(f"[pet-ai] Nudge message: {text}")
                self._recent_messages.append(text.lower())
                return text

        except Exception as error:
            self._logger(f"[pet-ai] Nudge message failed: {error}")

        return self._fresh_message(self._random.choice(NUDGE_FALLBACKS), NUDGE_FALLBACKS)

    def _fresh_message(self, candidate: str, pool) -> str:
        """Pick a line that wasn't said recently, so the cat doesn't repeat itself."""
        if candidate.lower() not in self._recent_messages:
            self._recent_messages.append(candidate.lower())
            return candidate

        options = [line for line in pool if line.lower() not in self._recent_messages]
        chosen = self._random.choice(options) if options else candidate
        self._recent_messages.append(chosen.lower())
        return chosen

    # ── Window classification ─────────────────────────────────────────────────

    def _classify_window_attention(self, title, process_name, task="", goal="", url=""):
        # Game / entertainment launchers — always block, no context check needed.
        if any(keyword in process_name for keyword in DISTRACTION_PROCESS_KEYWORDS):
            return "nonproductive"

        # The URL (when we have it) is far more reliable than the page title, so
        # fold it into the haystack used by every keyword check below.
        haystack = f"{title} {url}".lower()

        # When the session has a task + goal, ask the LLM whether this window is
        # needed for that specific work before falling back to keyword matching.
        if task and goal and self._client:
            result = self._classify_with_session_context(title, process_name, task, goal, url)
            if result:
                return result

        # Keyword-based fallback (no LLM, or LLM returned nothing).
        if any(keyword in haystack for keyword in DISTRACTION_KEYWORDS):
            return "nonproductive"

        if any(keyword in haystack for keyword in AMBIGUOUS_MEDIA_KEYWORDS):
            return self._classify_ambiguous_title(title, process_name)

        return "productive"

    def _classify_with_session_context(self, title, process_name, task, goal, url=""):
        """Ask the LLM whether this window is actually needed for the user's task/goal."""
        cache_key = f"{process_name[:20]}|{title[:60]}|{url[:80]}|{task[:40]}|{goal[:40]}"
        if cache_key in self._context_classification_cache:
            return self._context_classification_cache[cache_key]

        try:
            self._logger(
                f"[pet-ai] Context check: '{title}' ({url[:40]}) vs task='{task[:30]}'"
            )
            response = self._client.responses.create(
                model=self._model,
                input=[
                    {
                        "role": "system",
                        "content": (
                            "You are a focus assistant inside a desktop pet app called "
                            "'Desktop Cat'. The user is in a focus session with a stated task "
                            "and goal. Decide whether the current window/tab is plausibly part "
                            "of that work.\n\n"
                            "Principles:\n"
                            "1. Window titles and URLs are often vague, generic or incomplete "
                            "(e.g. 'Home', 'skill', 'watch'). Missing keywords is NOT evidence "
                            "of distraction — it just means the data is insufficient.\n"
                            "2. Judge by TOPIC and CONCEPTUAL relevance, not literal keyword "
                            "overlap. A page about a sub-topic, feature, tool or concept of the "
                            "goal is on-task even if it never names the goal. Example: goal "
                            "'learn Claude Code' + a video titled 'skills' is on-task, because "
                            "skills are a Claude Code feature.\n"
                            "3. Learning material — tutorials, docs, videos, articles, forums, "
                            "Q&A — on anything reasonably connected to the task is productive.\n"
                            "4. Mark needed=false ONLY when the content is clearly unrelated "
                            "leisure: entertainment, social media, gaming, sports, shopping or "
                            "memes with no plausible link to the task.\n"
                            "5. If the evidence is insufficient or ambiguous, ALWAYS choose "
                            "needed=true. Prefer the URL over the title. The app's own windows "
                            "('Desktop Cat', 'Pixel Pets') are never distractions.\n\n"
                            "Return strict JSON: {\"needed\": true|false, \"reason\": \"<=10 words\"}."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps({
                            "task":         task,
                            "goal":         goal,
                            "window_title": title,
                            "url":          url,
                            "process":      process_name,
                        }),
                    },
                ],
            )
            parsed = json.loads(response.output_text.strip())
            result = "productive" if parsed.get("needed", True) else "nonproductive"
            self._context_classification_cache[cache_key] = result
            self._logger(
                f"[pet-ai] Context result: {result} ({parsed.get('reason', '')})"
            )
            return result

        except Exception as error:
            self._logger(f"[pet-ai] Context classification failed: {error}")
            return None

    def _classify_ambiguous_title(self, title, process_name):
        cache_key = f"{process_name}|{title}".strip()

        if cache_key in self._title_classification_cache:
            return self._title_classification_cache[cache_key]

        if self._client:
            result = self._classify_title_with_openai(title, process_name)

            if result:
                self._title_classification_cache[cache_key] = result
                return result

        result = self._classify_title_with_rules(title)
        self._title_classification_cache[cache_key] = result
        return result

    def _classify_title_with_openai(self, title, process_name):
        try:
            self._logger(
                f"[pet-ai] Classifying title: {process_name}: {title}"
            )
            response = self._client.responses.create(
                model=self._model,
                input=[
                    {
                        "role": "system",
                        "content": (
                            "Classify whether a browser tab title is productive "
                            "or nonproductive for a coding/productivity desktop pet. "
                            "Return strict JSON with key classification and value "
                            "'productive' or 'nonproductive'."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {"process_name": process_name, "title": title}
                        ),
                    },
                ],
            )
            payload = json.loads(response.output_text.strip())
            classification = payload.get("classification")

            if classification in ("productive", "nonproductive"):
                self._logger(f"[pet-ai] Title classified as {classification}")
                return classification

        except Exception as error:
            self._logger(f"[pet-ai] Title classification failed: {error}")

        return None

    def _classify_title_with_rules(self, title):
        productive_keywords = (
            "tutorial",
            "learn",
            "lesson",
            "course",
            "python",
            "javascript",
            "react",
            "flask",
            "coding",
            "programming",
            "fix",
            "debug",
            "documentation",
            "guide",
        )

        if any(keyword in title for keyword in productive_keywords):
            return "productive"

        return "nonproductive"

    # ── Helpers ───────────────────────────────────────────────────────────────

    # Titles belonging to this companion app itself — never a distraction.
    _SELF_WINDOW_HINTS = ("desktop cat",)

    def _is_self_window(self, title_lower: str) -> bool:
        return any(hint in title_lower for hint in self._SELF_WINDOW_HINTS)

    def _distraction_key(self, title: str, process_name: str, url: str = "") -> str:
        """Return a stable key for this distraction so per-title cooldowns work correctly.

        Process-name matches use the process name; keyword matches use the matched keyword
        so that different pages on the same service (YouTube home vs F1 video) each get
        their own key and can each trigger an alert independently. The URL is folded in
        so the key reflects the actual page, not just its (often vague) title.
        """
        haystack = f"{title} {url}".lower()
        for kw in DISTRACTION_PROCESS_KEYWORDS:
            if kw in process_name:
                return f"proc:{kw}"
        for kw in DISTRACTION_KEYWORDS:
            if kw in haystack:
                return f"kw:{kw}"
        # Ambiguous (YouTube etc.) — key on the URL when we have it (so each video/search
        # gets its own cooldown), otherwise the title.
        identifier = (url or title)[:80]
        for kw in AMBIGUOUS_MEDIA_KEYWORDS:
            if kw in haystack:
                return f"page:{identifier}"
        return f"page:{identifier}"

    def _can_perform(self, action_key, force=False):
        now = time.time()

        if force:
            return True

        if now - self.last_action_time < self.action_cooldown_seconds:
            return False

        if action_key == self.last_action_key and now - self.last_action_time < 30:
            return False

        return True

    def _is_coding_context(self, title, process_name):
        haystack = f"{title} {process_name}"
        return any(keyword in haystack for keyword in CODING_KEYWORDS)

    def _pick_coding_relaxed_action(self):
        now = time.time()

        if now - self.last_coding_relaxed_time < 180:
            return None

        self.last_coding_relaxed_time = now
        return "sleep_sequence"

    def _is_sleeping(self):
        return time.time() < self.sleep_until

    def _is_browser_context(self, process_name):
        return any(keyword in process_name for keyword in BROWSER_PROCESS_KEYWORDS)

    def _event_to_dict(self, event):
        return {
            "event_type": getattr(event.event_type, "value", str(event.event_type)),
            "source": event.source,
            "timestamp": event.timestamp.isoformat(),
            "payload": event.payload,
        }

    def _create_openai_client(self):
        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            self._logger("[pet-ai] OpenAI client disabled: API key not found.")
            return None

        try:
            from openai import OpenAI
        except ImportError:
            self._logger("[pet-ai] OpenAI package not installed.")
            return None

        self._logger(f"[pet-ai] OpenAI client enabled with model {self._model}.")
        try:
            return OpenAI(
                api_key=api_key,
                timeout=self._request_timeout,
                max_retries=1,
            )
        except TypeError:
            # Older SDKs without timeout/max_retries kwargs.
            return OpenAI(api_key=api_key)
