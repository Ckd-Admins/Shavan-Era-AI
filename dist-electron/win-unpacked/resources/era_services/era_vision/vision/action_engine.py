"""ERA Vision Action Engine — Phase 3.

ERA ki "aankhein" hain Vision, aur "haath" hain Local Agent.
Yeh engine unhe jodhta hai:

    Screen dekhna → Samajhna → Action decide karna → Execute karna → Verify karna

Loop:
  1. EventBus se ANALYSIS_COMPLETED / ERROR_DETECTED events listen karo
  2. Jab koi error/event aaye:
       a. Gemini se puchho: "Kya karna chahiye?" (analyze_for_action)
       b. Confidence check karo (threshold >= settings.action_confidence_threshold)
       c. ERA Bridge ko HTTP call karo command execute karne ke liye
       d. action_verify_delay_seconds baad phir screen check karo
       e. ActionLog mein result store karo
  3. Jab chart detect ho (chart_detected=True):
       a. Deep chart analysis karo (analyze_chart)
       b. Agar scroll chahiye to ERA Agent ko scroll_screen command bhejo
       c. ChartAnalysis events publish karo

Safety guardrails:
  - action_engine_enabled must be True (default: False)
  - confidence threshold check (default: 0.65)
  - max_actions_per_hour budget
  - action_cooldown_seconds between same-error actions
  - action_log_only_mode: log decisions without executing (dry run)
  - No destructive commands allowed (hardcoded blocklist)
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections import deque
from typing import Any, Deque, Dict, Optional

import httpx

from config import Settings
from vision.analyzer import Analyzer
from vision.capture import CaptureWorker, Frame
from vision.context_manager import ContextManager
from vision.events import (
    ACTION_DECIDED,
    ACTION_EXECUTED,
    ACTION_FAILED,
    ACTION_SKIPPED,
    ACTION_VERIFIED,
    ANALYSIS_COMPLETED,
    CHART_ANALYZED,
    CHART_DETECTED,
    CHART_SCROLL_REQUESTED,
    ERROR_DETECTED,
    EventBus,
)
from vision.models import (
    ActionDecision,
    ActionLog,
    ActionOutcome,
    ChartAnalysis,
    ContextEntry,
)

logger = logging.getLogger("era_vision.action_engine")

# Commands that must never be sent by the action engine regardless of AI decision
_BLOCKED_COMMANDS = frozenset({
    "shutdown_pc",
    "restart_pc",
    "cancel_shutdown",
    "edit_file_at_path",
    "delete_file",
    "format_disk",
})

# Maximum number of ActionLogs to keep in memory
_MAX_LOG_SIZE = 500


class ActionEngine:
    """Connects ERA Vision perception to ERA Agent actions.

    Lifecycle:
        start()  → subscribes to EventBus, begins processing events
        stop()   → unsubscribes, stops processing

    All blocking work (HTTP calls, Gemini calls) runs in a background
    thread pool so the EventBus and FastAPI event loop are never blocked.
    """

    def __init__(
        self,
        settings: Settings,
        analyzer: Analyzer,
        context: ContextManager,
        events: EventBus,
        capture_worker_factory=CaptureWorker,
    ) -> None:
        self._settings = settings
        self._analyzer = analyzer
        self._context = context
        self._events = events
        self._capture_worker_factory = capture_worker_factory

        # State
        self._running = False
        self._lock = threading.Lock()

        # Budget tracking
        self._action_timestamps: Deque[float] = deque(maxlen=1000)
        self._chart_analysis_timestamps: Deque[float] = deque(maxlen=1000)
        self._last_action_time_per_error: Dict[str, float] = {}

        # Log of all actions taken
        self._action_log: Deque[ActionLog] = deque(maxlen=_MAX_LOG_SIZE)
        self._chart_history: Deque[ChartAnalysis] = deque(
            maxlen=settings.chart_history_size
        )

        # Background thread for processing events
        self._event_queue: Deque[Dict[str, Any]] = deque(maxlen=200)
        self._event_available = threading.Event()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # Bridge HTTP client (created lazily)
        self._bridge_client: httpx.Client | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self._stop_event.clear()
            self._bridge_client = httpx.Client(
                base_url=self._settings.era_bridge_url,
                headers={"Authorization": f"Bearer {self._settings.era_bridge_api_key}"},
                timeout=15.0,
            )
            # Subscribe to EventBus events
            self._events.subscribe_callback(self._on_event)
            self._thread = threading.Thread(
                target=self._process_loop,
                name="action-engine-loop",
                daemon=True,
            )
            self._thread.start()
            logger.info(
                "ActionEngine started. enabled=%s log_only=%s confidence_threshold=%.2f",
                self._settings.action_engine_enabled,
                self._settings.action_log_only_mode,
                self._settings.action_confidence_threshold,
            )

    def stop(self) -> None:
        with self._lock:
            if not self._running:
                return
            self._running = False
            self._stop_event.set()
            self._event_available.set()  # Wake up the loop so it can exit
            self._events.unsubscribe_callback(self._on_event)
            if self._bridge_client:
                try:
                    self._bridge_client.close()
                except Exception:
                    pass
                self._bridge_client = None
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None
        logger.info("ActionEngine stopped.")

    # ------------------------------------------------------------------
    # Event subscription callback
    # ------------------------------------------------------------------

    def _on_event(self, envelope) -> None:
        """Called by EventBus (may be from any thread). Queue for processing."""
        if envelope.event in (ANALYSIS_COMPLETED, ERROR_DETECTED):
            self._event_queue.append({"event": envelope.event, "data": envelope.data})
            self._event_available.set()

    # ------------------------------------------------------------------
    # Background processing loop
    # ------------------------------------------------------------------

    def _process_loop(self) -> None:
        while not self._stop_event.is_set():
            self._event_available.wait(timeout=1.0)
            self._event_available.clear()
            while self._event_queue:
                try:
                    item = self._event_queue.popleft()
                    self._handle_event(item["event"], item["data"])
                except Exception:
                    logger.exception("Unhandled error in ActionEngine._process_loop")

    def _handle_event(self, event: str, data: dict) -> None:
        """Route event to appropriate handler."""
        if event == ERROR_DETECTED:
            self._on_error_detected(data.get("description", ""))
        elif event == ANALYSIS_COMPLETED:
            self._on_analysis_completed(data)

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    def _on_error_detected(self, error_description: str) -> None:
        """Respond to an error seen on screen."""
        if not self._settings.action_engine_enabled:
            logger.debug("ActionEngine disabled — skipping error response for: %s", error_description)
            return

        # Cooldown check: don't spam actions for the same error
        now = time.time()
        last = self._last_action_time_per_error.get(error_description, 0.0)
        if now - last < self._settings.action_cooldown_seconds:
            logger.debug(
                "Error cooldown active for %r (%.1fs remaining). Skipping.",
                error_description,
                self._settings.action_cooldown_seconds - (now - last),
            )
            return

        # Get current screen context
        entry = self._context.get_current()
        if entry is None:
            logger.debug("No current screen context — cannot decide action for error.")
            return

        logger.info("Error detected: %r — asking Gemini what to do...", error_description)

        # Capture a fresh frame for action analysis
        frame = self._grab_frame()
        if frame is None:
            logger.warning("Could not grab frame for action analysis.")
            return

        # Ask Gemini to decide action
        try:
            decision = self._analyzer.analyze_for_action(
                frame,
                entry.state,
                entry.window,
                trigger_description=f"Error on screen: {error_description}",
            )
        except Exception as exc:
            logger.warning("analyze_for_action failed: %s", exc)
            self._log_action(
                trigger_event=ERROR_DETECTED,
                trigger_description=error_description,
                decision=None,
                outcome=ActionOutcome.FAILURE,
                outcome_detail=f"Gemini call failed: {exc}",
            )
            return

        decision.trigger_event = ERROR_DETECTED
        decision.trigger_description = error_description

        self._events.publish(ACTION_DECIDED, {
            "command": decision.command,
            "confidence": decision.confidence,
            "reasoning": decision.reasoning,
            "trigger": error_description,
        })

        # Execute the decision
        self._execute_decision(decision, entry)

    # ------------------------------------------------------------------
    # Analysis completed handler (chart detection + general events)
    # ------------------------------------------------------------------

    def _on_analysis_completed(self, data: dict) -> None:
        """Called after every successful Gemini analysis."""
        entry = self._context.get_current()
        if entry is None:
            return

        # Chart analysis
        if entry.state.chart_detected and self._settings.chart_analysis_enabled:
            self._handle_chart(entry)

    def _handle_chart(self, entry: ContextEntry) -> None:
        """Analyze a chart detected on screen."""
        # Rate limit chart analysis
        now = time.time()
        if self._chart_analysis_timestamps:
            last_chart = self._chart_analysis_timestamps[-1]
            if now - last_chart < self._settings.chart_analysis_cooldown_seconds:
                return

        self._events.publish(CHART_DETECTED, {
            "application": entry.state.application,
            "window_title": entry.window.title,
        })

        frame = self._grab_frame()
        if frame is None:
            return

        try:
            chart = self._analyzer.analyze_chart(frame, entry.state, entry.window)
        except Exception as exc:
            logger.warning("analyze_chart failed: %s", exc)
            return

        self._chart_history.append(chart)
        self._chart_analysis_timestamps.append(time.time())

        logger.info(
            "Chart analyzed: asset=%r trend=%s bullish=%.0f%% bearish=%.0f%% confidence=%.2f",
            chart.asset,
            chart.current_trend.value,
            chart.bullish_probability * 100,
            chart.bearish_probability * 100,
            chart.confidence,
        )

        self._events.publish(CHART_ANALYZED, {
            "asset": chart.asset,
            "timeframe": chart.timeframe,
            "trend": chart.current_trend.value,
            "trend_strength": chart.trend_strength,
            "bullish_probability": chart.bullish_probability,
            "bearish_probability": chart.bearish_probability,
            "patterns": chart.patterns_detected,
            "indicators": chart.visible_indicators,
            "indicator_signals": chart.indicator_signals,
            "support_levels": [s.model_dump() for s in chart.support_levels],
            "resistance_levels": [r.model_dump() for r in chart.resistance_levels],
            "short_term_prediction": chart.short_term_prediction,
            "summary": chart.summary,
            "confidence": chart.confidence,
        })

        # Auto-scroll to see more chart data if recommended
        if (
            chart.should_scroll_for_more_data
            and self._settings.chart_auto_scroll_enabled
            and self._settings.action_engine_enabled
        ):
            direction = chart.scroll_direction
            if direction in ("left", "up"):
                scroll_clicks = -abs(self._settings.chart_scroll_clicks)
            else:
                scroll_clicks = abs(self._settings.chart_scroll_clicks)

            self._events.publish(CHART_SCROLL_REQUESTED, {
                "direction": direction,
                "clicks": scroll_clicks,
            })
            logger.info("Chart needs more data — scrolling %s (%d clicks)", direction, scroll_clicks)

            if not self._settings.action_log_only_mode:
                self._call_bridge("scroll_screen", {"clicks": scroll_clicks})

    # ------------------------------------------------------------------
    # Decision execution
    # ------------------------------------------------------------------

    def _execute_decision(self, decision: ActionDecision, entry: ContextEntry) -> None:
        """Execute an ActionDecision: confidence check → budget check → execute → verify."""
        threshold = self._settings.action_confidence_threshold

        # Confidence gate
        if decision.command is None or decision.confidence < threshold:
            logger.info(
                "Action skipped: command=%r confidence=%.2f (threshold=%.2f) reason=%s",
                decision.command,
                decision.confidence,
                threshold,
                decision.reasoning,
            )
            self._events.publish(ACTION_SKIPPED, {
                "command": decision.command,
                "confidence": decision.confidence,
                "reasoning": decision.reasoning,
            })
            self._log_action(
                trigger_event=decision.trigger_event,
                trigger_description=decision.trigger_description,
                decision=decision,
                outcome=ActionOutcome.SKIPPED,
                outcome_detail=f"Confidence {decision.confidence:.2f} < threshold {threshold:.2f}",
            )
            return

        # Safety blocklist
        if decision.command in _BLOCKED_COMMANDS:
            logger.warning("Blocked command %r — it is in the safety blocklist.", decision.command)
            self._log_action(
                trigger_event=decision.trigger_event,
                trigger_description=decision.trigger_description,
                decision=decision,
                outcome=ActionOutcome.FAILURE,
                outcome_detail=f"Command {decision.command!r} is in the safety blocklist.",
            )
            return

        # Budget guard
        if not self._check_action_budget():
            logger.warning(
                "Action budget exceeded (%d actions/hour limit). Skipping.",
                self._settings.max_actions_per_hour,
            )
            self._log_action(
                trigger_event=decision.trigger_event,
                trigger_description=decision.trigger_description,
                decision=decision,
                outcome=ActionOutcome.SKIPPED,
                outcome_detail="Hourly action budget exceeded.",
            )
            return

        # Scroll first if needed (to see more context)
        if decision.should_scroll_first and decision.scroll_direction != "none":
            scroll_clicks = (
                -abs(decision.scroll_clicks)
                if decision.scroll_direction == "down"
                else abs(decision.scroll_clicks)
            )
            logger.info("Scrolling first (%d clicks) before main action.", scroll_clicks)
            if not self._settings.action_log_only_mode:
                self._call_bridge("scroll_screen", {"clicks": scroll_clicks})
            time.sleep(1.0)  # Let screen settle

        # Execute the action
        logger.info(
            "Executing action: command=%r params=%s confidence=%.2f",
            decision.command,
            decision.params,
            decision.confidence,
        )
        self._events.publish(ACTION_EXECUTED, {
            "command": decision.command,
            "params": decision.params,
            "confidence": decision.confidence,
            "log_only": self._settings.action_log_only_mode,
        })

        self._action_timestamps.append(time.time())
        self._last_action_time_per_error[decision.trigger_description] = time.time()

        bridge_ok = False
        bridge_message = ""
        if self._settings.action_log_only_mode:
            logger.info("[LOG-ONLY MODE] Would have executed: %r with params %s", decision.command, decision.params)
            bridge_ok = True
            bridge_message = "log_only_mode — not executed"
        else:
            result = self._call_bridge(decision.command, decision.params)
            bridge_ok = result.get("success", False) if result else False
            bridge_message = result.get("message", "no response") if result else "bridge_unreachable"

        if not bridge_ok:
            logger.warning("Action execution failed: %s", bridge_message)
            self._events.publish(ACTION_FAILED, {
                "command": decision.command,
                "reason": bridge_message,
            })
            self._log_action(
                trigger_event=decision.trigger_event,
                trigger_description=decision.trigger_description,
                decision=decision,
                outcome=ActionOutcome.FAILURE,
                outcome_detail=bridge_message,
            )
            return

        # Verification: wait then check if error is gone
        time.sleep(self._settings.action_verify_delay_seconds)
        verified, error_still_present = self._verify_action(decision.trigger_description)

        outcome = ActionOutcome.VERIFIED if verified else ActionOutcome.UNVERIFIED
        self._events.publish(ACTION_VERIFIED, {
            "command": decision.command,
            "verified": verified,
            "error_still_present": error_still_present,
        })
        self._log_action(
            trigger_event=decision.trigger_event,
            trigger_description=decision.trigger_description,
            decision=decision,
            outcome=outcome,
            outcome_detail=f"Verified={verified} error_still_present={error_still_present}",
            verified_screen_changed=verified,
            error_still_present=error_still_present,
        )
        logger.info(
            "Action verification: command=%r verified=%s error_still_present=%s",
            decision.command,
            verified,
            error_still_present,
        )

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------

    def _verify_action(self, original_error: str) -> tuple[bool, bool]:
        """Check if the screen changed and whether the original error is still present.

        Returns (screen_changed: bool, error_still_present: bool).
        """
        entry = self._context.get_current()
        if entry is None:
            return False, True

        # Check if the error is still in the screen state's error list
        error_still_present = any(
            original_error.lower() in err.lower() for err in entry.state.errors
        )
        # Consider "verified" if the error is no longer present
        screen_changed = not error_still_present
        return screen_changed, error_still_present

    # ------------------------------------------------------------------
    # Bridge HTTP client
    # ------------------------------------------------------------------

    def _call_bridge(
        self, command: str, params: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """POST /v1/execute to ERA Bridge → ERA Local Agent.

        Returns the response dict, or None if unreachable.
        """
        if self._bridge_client is None:
            logger.warning("Bridge client not initialized.")
            return None

        payload: Dict[str, Any] = {"command": command}
        if params:
            payload["params"] = params

        try:
            response = self._bridge_client.post("/v1/execute", json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Bridge returned HTTP %d for command %r: %s",
                exc.response.status_code,
                command,
                exc.response.text[:200],
            )
            return {"success": False, "message": f"HTTP {exc.response.status_code}"}
        except httpx.RequestError as exc:
            logger.warning("Bridge unreachable for command %r: %s", command, exc)
            return {"success": False, "message": f"Bridge unreachable: {exc}"}

    # ------------------------------------------------------------------
    # Frame grabbing
    # ------------------------------------------------------------------

    def _grab_frame(self) -> Optional[Frame]:
        """Grab a single screen frame for analysis."""
        try:
            worker = self._capture_worker_factory()
            frame = worker.grab()
            worker.close()
            return frame
        except Exception as exc:
            logger.warning("Could not grab frame: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Budget / logging helpers
    # ------------------------------------------------------------------

    def _check_action_budget(self) -> bool:
        """Returns True if we are within the hourly action budget."""
        now = time.time()
        cutoff = now - 3600.0  # last 1 hour
        # Prune old timestamps
        while self._action_timestamps and self._action_timestamps[0] < cutoff:
            self._action_timestamps.popleft()
        return len(self._action_timestamps) < self._settings.max_actions_per_hour

    def _log_action(
        self,
        trigger_event: str,
        trigger_description: str,
        decision: Optional[ActionDecision],
        outcome: ActionOutcome,
        outcome_detail: str = "",
        verified_screen_changed: bool = False,
        error_still_present: bool = False,
    ) -> None:
        log = ActionLog(
            trigger_event=trigger_event,
            trigger_description=trigger_description,
            decision=decision,
            outcome=outcome,
            outcome_detail=outcome_detail,
            verified_screen_changed=verified_screen_changed,
            error_still_present=error_still_present,
        )
        self._action_log.append(log)

    # ------------------------------------------------------------------
    # Public read API
    # ------------------------------------------------------------------

    def get_action_log(self, limit: int = 50) -> list[ActionLog]:
        """Return the most recent ActionLog entries."""
        logs = list(self._action_log)
        return logs[-limit:]

    def get_chart_history(self, limit: int = 10) -> list[ChartAnalysis]:
        """Return the most recent ChartAnalysis entries."""
        charts = list(self._chart_history)
        return charts[-limit:]

    def get_status(self) -> dict:
        """Return a status summary for the /v1/vision/actions/status endpoint."""
        now = time.time()
        cutoff = now - 3600.0
        recent_actions = sum(1 for t in self._action_timestamps if t > cutoff)
        return {
            "running": self._running,
            "enabled": self._settings.action_engine_enabled,
            "log_only_mode": self._settings.action_log_only_mode,
            "confidence_threshold": self._settings.action_confidence_threshold,
            "actions_this_hour": recent_actions,
            "max_actions_per_hour": self._settings.max_actions_per_hour,
            "action_log_count": len(self._action_log),
            "chart_analyses_stored": len(self._chart_history),
            "chart_analysis_enabled": self._settings.chart_analysis_enabled,
            "chart_auto_scroll_enabled": self._settings.chart_auto_scroll_enabled,
            "bridge_url": self._settings.era_bridge_url,
            "bridge_key_configured": bool(self._settings.era_bridge_api_key),
        }
