"""ERA Bridge — Vision Agent HTTP client.

Allows ERA (via Bridge) to:
  - Check if Vision is running
  - Start/stop/pause/resume Vision
  - Read the current screen state (what ERA is 'seeing')
  - Read the latest chart analysis
  - Get the action engine status and log

All calls are authenticated with VISION_AGENT_API_KEY.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)


class VisionAgentClient:
    """HTTP client for ERA Vision Agent (runs on port 8200)."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=settings.VISION_AGENT_URL,
            headers={"X-Vision-Agent-Key": settings.VISION_AGENT_API_KEY},
            timeout=10.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Health / Status
    # ------------------------------------------------------------------

    async def is_running(self) -> bool:
        """Quick health check — does not require auth."""
        try:
            resp = await self._client.get("/v1/health", timeout=2.0)
            return resp.status_code == 200
        except httpx.RequestError:
            return False

    async def get_vision_status(self) -> Optional[Dict[str, Any]]:
        """Returns Vision Agent status: mode, frames captured, analyses performed."""
        try:
            resp = await self._client.get("/v1/vision/status")
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, Exception) as exc:
            logger.warning("Vision Agent status check failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Vision lifecycle
    # ------------------------------------------------------------------

    async def start_vision(self) -> Optional[Dict[str, Any]]:
        """Start Vision Agent's screen observation loop."""
        try:
            resp = await self._client.post("/v1/vision/start")
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, Exception) as exc:
            logger.warning("Failed to start Vision Agent: %s", exc)
            return None

    async def stop_vision(self) -> Optional[Dict[str, Any]]:
        """Stop Vision Agent's screen observation."""
        try:
            resp = await self._client.post("/v1/vision/stop")
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, Exception) as exc:
            logger.warning("Failed to stop Vision Agent: %s", exc)
            return None

    async def pause_vision(self) -> Optional[Dict[str, Any]]:
        """Pause Vision Agent (keep loop running, but skip captures)."""
        try:
            resp = await self._client.post("/v1/vision/pause")
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, Exception) as exc:
            logger.warning("Failed to pause Vision Agent: %s", exc)
            return None

    async def resume_vision(self) -> Optional[Dict[str, Any]]:
        """Resume Vision Agent from paused state."""
        try:
            resp = await self._client.post("/v1/vision/resume")
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, Exception) as exc:
            logger.warning("Failed to resume Vision Agent: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Screen context
    # ------------------------------------------------------------------

    async def get_current_screen_state(self) -> Optional[Dict[str, Any]]:
        """Returns the current structured screen state (what ERA is seeing right now).

        Includes: application, summary, visible_elements, errors, important_text,
        chart_detected, current_activity.
        """
        try:
            resp = await self._client.get("/v1/vision/current-state")
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, Exception) as exc:
            logger.warning("Failed to get current screen state: %s", exc)
            return None

    async def get_context_history(self) -> Optional[Dict[str, Any]]:
        """Returns the rolling context history: recent screen states + important events."""
        try:
            resp = await self._client.get("/v1/vision/context")
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, Exception) as exc:
            logger.warning("Failed to get context history: %s", exc)
            return None

    async def set_task_context(self, task_context: Optional[str]) -> bool:
        """Tell Vision what the user is currently doing (helps Gemini analysis)."""
        try:
            resp = await self._client.post(
                "/v1/vision/task-context",
                json={"task_context": task_context},
            )
            resp.raise_for_status()
            return True
        except (httpx.HTTPError, Exception) as exc:
            logger.warning("Failed to set task context: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Chart analysis
    # ------------------------------------------------------------------

    async def get_latest_chart(self) -> Optional[Dict[str, Any]]:
        """Returns the most recent trading chart analysis (trend, levels, prediction)."""
        try:
            resp = await self._client.get("/v1/vision/charts/latest")
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, Exception) as exc:
            logger.warning("Failed to get latest chart: %s", exc)
            return None

    async def get_chart_history(self, limit: int = 5) -> Optional[Dict[str, Any]]:
        """Returns recent chart analysis history."""
        try:
            resp = await self._client.get("/v1/vision/charts", params={"limit": limit})
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, Exception) as exc:
            logger.warning("Failed to get chart history: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Action Engine
    # ------------------------------------------------------------------

    async def get_action_log(self, limit: int = 20) -> Optional[Dict[str, Any]]:
        """Returns the autonomous action log (what ERA Vision has done automatically)."""
        try:
            resp = await self._client.get("/v1/vision/actions", params={"limit": limit})
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, Exception) as exc:
            logger.warning("Failed to get action log: %s", exc)
            return None

    async def get_action_engine_status(self) -> Optional[Dict[str, Any]]:
        """Returns ActionEngine status: enabled, budget, confidence threshold."""
        try:
            resp = await self._client.get("/v1/vision/actions/status")
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, Exception) as exc:
            logger.warning("Failed to get action engine status: %s", exc)
            return None

    async def configure_action_engine(
        self,
        enabled: Optional[bool] = None,
        log_only_mode: Optional[bool] = None,
        confidence_threshold: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """Configure the action engine: enable/disable, set confidence threshold."""
        payload = {}
        if enabled is not None:
            payload["enabled"] = enabled
        if log_only_mode is not None:
            payload["log_only_mode"] = log_only_mode
        if confidence_threshold is not None:
            payload["confidence_threshold"] = confidence_threshold
        try:
            resp = await self._client.post("/v1/vision/actions/config", json=payload)
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, Exception) as exc:
            logger.warning("Failed to configure action engine: %s", exc)
            return None
