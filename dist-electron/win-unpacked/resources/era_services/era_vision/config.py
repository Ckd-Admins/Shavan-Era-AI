"""
Configuration for the ERA Vision Agent.

All configuration comes from environment variables (optionally loaded from
a local `.env` file). Nothing here is hard-coded. Two secrets exist and are
kept completely separate:

  VISION_AGENT_API_KEY  - authenticates callers (ERA / Bridge) -> this agent
  GEMINI_API_KEY         - authenticates this agent -> Gemini

`Settings.summary()` is the only way settings are logged, and it always
redacts both keys. Never log `Settings` fields directly.
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv_if_present(path: Path) -> None:
    """Minimal .env loader (no external dependency). Does not override
    variables that are already set in the real environment."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _bool_env(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    val = os.environ.get(name)
    if val is None or not val.strip():
        return default
    try:
        return int(val)
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    val = os.environ.get(name)
    if val is None or not val.strip():
        return default
    try:
        return float(val)
    except ValueError:
        return default


@dataclass
class Settings:
    # --- Network binding: loopback only, always ---
    host: str = "127.0.0.1"
    port: int = 8200

    # --- Secrets (kept separate; never interchange these) ---
    vision_agent_api_key: str = ""
    gemini_api_key: str = ""

    # --- CORS: explicit allow-list, never "*" ---
    allowed_origins: tuple[str, ...] = ("http://127.0.0.1:8100", "http://localhost:8100")

    # --- Vision lifecycle ---
    vision_enabled_on_start: bool = False
    vision_autostart_on_boot: bool = True  # Automatically start vision observation loop on service boot

    # --- Capture / change detection ---
    capture_interval_seconds: float = 1.0
    idle_capture_interval_seconds: float = 3.0
    change_threshold: float = 0.02          # fraction of grid cells changed to count as "meaningful"
    grid_cols: int = 16
    grid_rows: int = 9
    min_seconds_between_analysis: float = 2.0
    debounce_seconds: float = 0.6           # wait for screen to "settle" before capturing

    # --- Gemini analysis budget ---
    gemini_model: str = "gemini-2.5-flash"
    max_gemini_calls_per_hour: int = 120
    gemini_timeout_seconds: float = 20.0
    gemini_max_retries: int = 2

    # --- Visual context memory ---
    context_history_size: int = 10
    context_ttl_seconds: float = 600.0      # 10 minutes; expired context is dropped, not just hidden

    # --- Privacy ---
    excluded_process_names: tuple[str, ...] = (
        "keepass.exe", "1password.exe", "bitwarden.exe", "lastpass.exe",
    )
    excluded_title_keywords: tuple[str, ...] = (
        "password", "private browsing", "incognito",
    )
    store_screenshots_to_disk: bool = False  # default OFF; Phase 2 requirement
    screenshot_dir: str = "data/frames"      # only used if store_screenshots_to_disk is True

    # --- Resource monitoring ---
    max_cpu_percent_sustained: float = 35.0
    max_rss_mb: float = 600.0
    resource_check_interval_seconds: float = 5.0

    # --- Logging ---
    log_dir: str = "logs"
    log_level: str = "INFO"
    log_max_bytes: int = 1_000_000
    log_backup_count: int = 5

    # --- Event replay buffer ---
    event_buffer_size: int = 200

    # --- Action Engine (Phase 3) ---
    # Connection to ERA Bridge (which connects to ERA Local Agent)
    era_bridge_url: str = "http://127.0.0.1:8100"
    era_bridge_api_key: str = ""
    # Safety: action engine must be explicitly enabled; OFF by default
    action_engine_enabled: bool = False
    # Only take action if confidence >= this threshold (0.0–1.0)
    action_confidence_threshold: float = 0.65
    # Seconds to wait before verifying that action worked
    action_verify_delay_seconds: float = 3.0
    # Max autonomous actions per hour (budget guard)
    max_actions_per_hour: int = 30
    # Seconds to wait between repeated actions on the same error
    action_cooldown_seconds: float = 15.0
    # Whether action engine should announce decisions even when not acting
    action_log_only_mode: bool = False  # True = log decisions but don't execute

    # --- Chart Analysis (Phase 3) ---
    # Automatically analyze charts when detected on screen
    chart_analysis_enabled: bool = True
    # Auto-scroll to see more chart data (uses ERA Agent scroll_screen command)
    chart_auto_scroll_enabled: bool = True
    # How many scroll clicks to use when exploring chart history
    chart_scroll_clicks: int = 5
    # Minimum seconds between chart analyses of same chart
    chart_analysis_cooldown_seconds: float = 5.0
    # Keep last N chart analyses in memory
    chart_history_size: int = 20

    def __post_init__(self) -> None:
        if self.host not in ("127.0.0.1", "localhost", "::1"):
            raise ValueError(
                f"Refusing to bind to non-loopback host {self.host!r}. "
                "The Vision Agent must stay on 127.0.0.1 only."
            )

    @property
    def vision_key_configured(self) -> bool:
        return bool(self.vision_agent_api_key)

    @property
    def gemini_key_configured(self) -> bool:
        return bool(self.gemini_api_key)

    def summary(self) -> dict:
        """Safe-to-log snapshot. Never include raw key values."""
        return {
            "host": self.host,
            "port": self.port,
            "vision_agent_api_key_set": self.vision_key_configured,
            "gemini_api_key_set": self.gemini_key_configured,
            "gemini_model": self.gemini_model,
            "allowed_origins": list(self.allowed_origins),
            "vision_autostart_on_boot": self.vision_autostart_on_boot,
            "store_screenshots_to_disk": self.store_screenshots_to_disk,
            "capture_interval_seconds": self.capture_interval_seconds,
            "context_ttl_seconds": self.context_ttl_seconds,
            "max_gemini_calls_per_hour": self.max_gemini_calls_per_hour,
            # Action engine
            "era_bridge_url": self.era_bridge_url,
            "era_bridge_api_key_set": bool(self.era_bridge_api_key),
            "action_engine_enabled": self.action_engine_enabled,
            "action_confidence_threshold": self.action_confidence_threshold,
            "max_actions_per_hour": self.max_actions_per_hour,
            "action_log_only_mode": self.action_log_only_mode,
            # Chart analysis
            "chart_analysis_enabled": self.chart_analysis_enabled,
            "chart_auto_scroll_enabled": self.chart_auto_scroll_enabled,
        }


def load_settings(env_path: str | Path = ".env") -> Settings:
    _load_dotenv_if_present(Path(env_path))

    vision_key = os.environ.get("VISION_AGENT_API_KEY", "").strip()
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()

    origins_raw = os.environ.get("ALLOWED_ORIGINS", "").strip()
    allowed_origins = (
        tuple(o.strip() for o in origins_raw.split(",") if o.strip())
        if origins_raw
        else ("http://127.0.0.1:8100", "http://localhost:8100")
    )

    excluded_proc_raw = os.environ.get("EXCLUDED_PROCESS_NAMES", "").strip()
    excluded_processes = (
        tuple(p.strip().lower() for p in excluded_proc_raw.split(",") if p.strip())
        if excluded_proc_raw
        else Settings.excluded_process_names
    )

    return Settings(
        host=os.environ.get("VISION_AGENT_HOST", "127.0.0.1").strip() or "127.0.0.1",
        port=_int_env("VISION_AGENT_PORT", 8200),
        vision_agent_api_key=vision_key,
        gemini_api_key=gemini_key,
        allowed_origins=allowed_origins,
        vision_autostart_on_boot=_bool_env("VISION_AUTOSTART_ON_BOOT", True),
        capture_interval_seconds=_float_env("CAPTURE_INTERVAL_SECONDS", 1.0),
        idle_capture_interval_seconds=_float_env("IDLE_CAPTURE_INTERVAL_SECONDS", 3.0),
        change_threshold=_float_env("CHANGE_THRESHOLD", 0.02),
        min_seconds_between_analysis=_float_env("MIN_SECONDS_BETWEEN_ANALYSIS", 2.0),
        debounce_seconds=_float_env("DEBOUNCE_SECONDS", 0.6),
        gemini_model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash",
        max_gemini_calls_per_hour=_int_env("MAX_GEMINI_CALLS_PER_HOUR", 120),
        gemini_timeout_seconds=_float_env("GEMINI_TIMEOUT_SECONDS", 20.0),
        gemini_max_retries=_int_env("GEMINI_MAX_RETRIES", 2),
        context_history_size=_int_env("CONTEXT_HISTORY_SIZE", 10),
        context_ttl_seconds=_float_env("CONTEXT_TTL_SECONDS", 600.0),
        excluded_process_names=excluded_processes,
        store_screenshots_to_disk=_bool_env("STORE_SCREENSHOTS_TO_DISK", False),
        max_cpu_percent_sustained=_float_env("MAX_CPU_PERCENT_SUSTAINED", 35.0),
        max_rss_mb=_float_env("MAX_RSS_MB", 600.0),
        log_level=os.environ.get("LOG_LEVEL", "INFO").strip() or "INFO",
        # --- Action Engine ---
        era_bridge_url=os.environ.get("ERA_BRIDGE_URL", "http://127.0.0.1:8100").strip() or "http://127.0.0.1:8100",
        era_bridge_api_key=os.environ.get("ERA_BRIDGE_API_KEY", "").strip(),
        action_engine_enabled=_bool_env("ACTION_ENGINE_ENABLED", False),
        action_confidence_threshold=_float_env("ACTION_CONFIDENCE_THRESHOLD", 0.65),
        action_verify_delay_seconds=_float_env("ACTION_VERIFY_DELAY_SECONDS", 3.0),
        max_actions_per_hour=_int_env("MAX_ACTIONS_PER_HOUR", 30),
        action_cooldown_seconds=_float_env("ACTION_COOLDOWN_SECONDS", 15.0),
        action_log_only_mode=_bool_env("ACTION_LOG_ONLY_MODE", False),
        # --- Chart Analysis ---
        chart_analysis_enabled=_bool_env("CHART_ANALYSIS_ENABLED", True),
        chart_auto_scroll_enabled=_bool_env("CHART_AUTO_SCROLL_ENABLED", True),
        chart_scroll_clicks=_int_env("CHART_SCROLL_CLICKS", 5),
        chart_analysis_cooldown_seconds=_float_env("CHART_ANALYSIS_COOLDOWN_SECONDS", 5.0),
        chart_history_size=_int_env("CHART_HISTORY_SIZE", 20),
    )


def generate_api_key() -> str:
    """Used by scripts/ to mint a new random key for either secret."""
    return secrets.token_urlsafe(32)
