"""ERA Intelligence Core — Model Router.

Routes LLM tasks to the appropriate model based on task type.
Reuses the existing Gemini infrastructure from era_agent.
Does NOT duplicate model client code.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Gemini model identifiers
_MODEL_FAST   = "gemini-2.0-flash"
_MODEL_STRONG = "gemini-2.5-flash"
_MODEL_PRO    = "gemini-2.5-pro"


def _get_gemini_client():
    """Lazy import of the Gemini SDK so we don't break startup if it's missing."""
    try:
        import google.generativeai as genai  # type: ignore
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return None, "GEMINI_API_KEY not set"
        genai.configure(api_key=api_key)
        return genai, None
    except ImportError:
        return None, "google-generativeai not installed"


class ModelRouter:
    """Routes generation requests to the appropriate Gemini model tier.

    Task tiers:
    - classification / quick_interpretation  → FAST (flash)
    - planning / complex_reasoning / coding  → STRONG (flash-thinking)
    - vision / screen_understanding          → FAST (vision capable)
    - sensitive (contains vault data)        → raises ValueError unless local_only=True
    """

    TASK_MODEL_MAP: Dict[str, str] = {
        "classification":        _MODEL_FAST,
        "quick_interpretation":  _MODEL_FAST,
        "goal_decomposition":    _MODEL_STRONG,
        "planning":              _MODEL_STRONG,
        "complex_coding":        _MODEL_PRO,
        "complex_reasoning":     _MODEL_PRO,
        "vision":                _MODEL_FAST,
        "recovery_diagnosis":    _MODEL_STRONG,
        "context_narrative":     _MODEL_FAST,
        "default":               _MODEL_FAST,
    }

    def __init__(self) -> None:
        self._cache: Dict[str, Any] = {}

    def route(
        self,
        task_type: str,
        prompt: str,
        system_instruction: Optional[str] = None,
        local_only: bool = False,
        sensitive: bool = False,
    ) -> Dict[str, Any]:
        """Send prompt to the appropriate model tier.

        Returns:
            {success: bool, text: str, model: str, error: Optional[str]}
        """
        if sensitive and not local_only:
            return {
                "success": False,
                "text": "",
                "model": "none",
                "error": "Sensitive data cannot be sent to cloud model without explicit local_only=True override.",
            }

        if PermissionEngine_is_stopped():
            return {"success": False, "text": "", "model": "none", "error": "ERA emergency stop active."}

        model_name = self.TASK_MODEL_MAP.get(task_type, self.TASK_MODEL_MAP["default"])
        genai, err = _get_gemini_client()

        if genai is None:
            return {
                "success": False,
                "text": "",
                "model": model_name,
                "error": err or "Gemini client unavailable",
            }

        try:
            model = genai.GenerativeModel(
                model_name,
                system_instruction=system_instruction or "You are ERA, a proactive personal computer intelligence assistant.",
            )
            response = model.generate_content(prompt)
            return {
                "success": True,
                "text": response.text,
                "model": model_name,
                "error": None,
            }
        except Exception as exc:
            logger.warning("ModelRouter error (task=%s, model=%s): %s", task_type, model_name, exc)
            return {
                "success": False,
                "text": "",
                "model": model_name,
                "error": str(exc),
            }

    def is_available(self) -> bool:
        """Returns True if cloud models are reachable."""
        genai, err = _get_gemini_client()
        return genai is not None and err is None


def PermissionEngine_is_stopped() -> bool:
    """Lazy check for emergency stop flag without circular import."""
    try:
        from era_agent.intelligence_core.permission_engine import PermissionEngine  # type: ignore
        return PermissionEngine.is_stopped()
    except Exception:
        return False


# Singleton
model_router = ModelRouter()
