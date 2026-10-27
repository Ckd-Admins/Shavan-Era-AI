"""Structured data models shared across the Vision Agent.

Includes:
- Core screen observation models (ScreenState, WindowInfo, ContextEntry)
- Action engine models (ActionDecision, ActionLog, ActionOutcome)
- Chart analysis models (ChartAnalysis, ChartTrend) for trading/graph understanding
"""

from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class VisionMode(str, Enum):
    OFF = "off"
    RUNNING = "running"
    PAUSED = "paused"


class WindowInfo(BaseModel):
    """Active/foreground window, from Win32 (or a stub off-Windows)."""

    title: str = ""
    process_name: str = ""
    pid: int | None = None
    is_excluded: bool = False


class UIElement(BaseModel):
    label: str
    element_type: str = Field(description="button, field, menu, tab, link, dialog, checkbox, dropdown, etc.")
    approx_location: str | None = Field(
        default=None, description="Coarse location, e.g. 'center-right', 'top toolbar'."
    )


class ScreenState(BaseModel):
    """Structured description of what is currently on screen.

    This is intentionally tolerant of a partially-conforming model response:
    every field has a safe default, and `analyzer.py` treats a state that
    fails validation as a failed observation rather than crashing the loop.
    """

    application: str = "unknown"
    window_title: str = ""
    summary: str = ""
    visible_elements: list[UIElement] = Field(default_factory=list)
    important_text: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    current_activity: str = ""
    confidence: float = 0.0
    # Set to True when a chart/graph is detected on screen (triggers ChartAnalysis)
    chart_detected: bool = False

    @field_validator("confidence")
    @classmethod
    def _clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, v))


class ContextEntry(BaseModel):
    """One entry in the rolling visual-context history."""

    entry_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = Field(default_factory=time.time)
    window: WindowInfo
    state: ScreenState
    trigger: str = Field(description="what caused this observation: window_change, pixel_change, manual, etc.")
    provider: str = ""

    def is_expired(self, ttl_seconds: float, now: float | None = None) -> bool:
        now = now if now is not None else time.time()
        return (now - self.timestamp) > ttl_seconds


class ImportantEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = Field(default_factory=time.time)
    kind: str  # e.g. "error_detected", "app_opened", "app_closed"
    description: str


class ChangeResult(BaseModel):
    changed: bool
    changed_fraction: float = 0.0
    changed_bbox: tuple[int, int, int, int] | None = None  # x0, y0, x1, y1 in source-frame pixels
    reason: str = ""


class VisionStatus(BaseModel):
    mode: VisionMode
    started_at: float | None = None
    last_observation_at: float | None = None
    frames_captured: int = 0
    analyses_performed: int = 0
    analyses_this_hour: int = 0
    max_analyses_per_hour: int = 0
    excluded_active: bool = False
    provider: str = ""
    provider_configured: bool = False


class DiagnosticsReport(BaseModel):
    """Backing model for GET /v1/vision/diagnostics."""

    agent_running: bool = True
    vision_mode: VisionMode
    capture_ok: bool
    capture_error: str | None = None
    active_window_detection_ok: bool
    active_window_error: str | None = None
    change_detector_ok: bool
    gemini_provider_configured: bool
    gemini_provider_reachable: bool | None = None  # None = not tested (no live call made)
    context_present: bool
    context_entry_count: int
    resource_ok: bool
    cpu_percent: float | None = None
    rss_mb: float | None = None
    timestamp: float = Field(default_factory=time.time)


class EventEnvelope(BaseModel):
    event: str
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)
    seq: int = 0


# ---------------------------------------------------------------------------
# Action Engine Models
# ---------------------------------------------------------------------------

class ActionDecision(BaseModel):
    """What the Action Engine decided to do in response to a screen event."""
    command: str | None = None           # ERA Agent command name, or None = no action
    params: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0             # 0.0–1.0
    reasoning: str = ""                  # Why this decision was made
    trigger_event: str = ""              # Which event triggered this (e.g. "ERROR_DETECTED")
    trigger_description: str = ""        # Human-readable description of what was seen
    should_scroll_first: bool = False    # Whether to scroll to see more context before acting
    scroll_direction: Literal["up", "down", "none"] = "none"
    scroll_clicks: int = 3

    @field_validator("confidence")
    @classmethod
    def _clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, v))


class ActionOutcome(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"       # Below confidence threshold
    UNVERIFIED = "unverified" # Action ran but could not verify result
    VERIFIED = "verified"     # Action ran and Vision confirmed it worked


class ActionLog(BaseModel):
    """Complete record of one autonomous action cycle."""
    action_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = Field(default_factory=time.time)
    trigger_event: str = ""
    trigger_description: str = ""
    decision: ActionDecision | None = None
    outcome: ActionOutcome = ActionOutcome.SKIPPED
    outcome_detail: str = ""
    verified_screen_changed: bool = False
    error_still_present: bool = False


# ---------------------------------------------------------------------------
# Chart Analysis Models
# ---------------------------------------------------------------------------

class ChartTrend(str, Enum):
    BULLISH = "bullish"         # Upward trend
    BEARISH = "bearish"         # Downward trend
    SIDEWAYS = "sideways"       # Range-bound / consolidation
    VOLATILE = "volatile"       # High volatility, no clear direction
    BREAKOUT_UP = "breakout_up"
    BREAKOUT_DOWN = "breakout_down"
    UNKNOWN = "unknown"


class PriceLevel(BaseModel):
    """A support or resistance level detected in the chart."""
    level_type: Literal["support", "resistance", "pivot"] = "support"
    price_label: str = ""        # e.g. "1920.50" or "~1920"
    strength: Literal["strong", "moderate", "weak"] = "moderate"
    description: str = ""


class ChartAnalysis(BaseModel):
    """Deep analysis of a trading chart or financial graph visible on screen.

    Produced by Analyzer.analyze_chart() when chart_detected=True.
    """
    chart_type: str = "unknown"           # e.g. "candlestick", "line", "bar"
    asset: str = ""                        # e.g. "BTC/USD", "NIFTY50", "AAPL"
    timeframe: str = ""                    # e.g. "1h", "15m", "daily"
    current_trend: ChartTrend = ChartTrend.UNKNOWN
    trend_strength: Literal["strong", "moderate", "weak"] = "moderate"
    trend_description: str = ""            # Human-readable trend explanation

    # Price levels
    support_levels: list[PriceLevel] = Field(default_factory=list)
    resistance_levels: list[PriceLevel] = Field(default_factory=list)

    # Prediction
    short_term_prediction: str = ""        # e.g. "likely to bounce from support"
    bullish_probability: float = 0.5       # 0.0–1.0
    bearish_probability: float = 0.5       # 0.0–1.0
    key_levels_text: list[str] = Field(default_factory=list)

    # Indicators visible
    visible_indicators: list[str] = Field(default_factory=list)  # e.g. ["RSI", "MACD", "Bollinger Bands"]
    indicator_signals: list[str] = Field(default_factory=list)   # e.g. ["RSI oversold", "MACD bullish crossover"]

    # Patterns
    patterns_detected: list[str] = Field(default_factory=list)   # e.g. ["head and shoulders", "double bottom"]

    # Scroll recommendation
    should_scroll_for_more_data: bool = False  # True if more historical data might be visible by scrolling
    scroll_direction: Literal["left", "right", "up", "down", "none"] = "none"

    confidence: float = 0.5
    summary: str = ""

    @field_validator("bullish_probability", "bearish_probability", "confidence")
    @classmethod
    def _clamp(cls, v: float) -> float:
        return max(0.0, min(1.0, v))
