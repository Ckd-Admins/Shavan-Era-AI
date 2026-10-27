"""Bridges capture + context into provider calls and back into validated models.

Three analysis modes:
  analyze()            → ScreenState (what is on screen right now)
  analyze_for_action() → ActionDecision (what ERA should do in response)
  analyze_chart()      → ChartAnalysis (deep technical analysis of a chart)

This is the only place that constructs the prompts sent to a vision provider.
"""

from __future__ import annotations

import logging

from vision.capture import Frame
from vision.models import ActionDecision, ChartAnalysis, ScreenState, WindowInfo
from vision.providers.base import ProviderError
from vision.providers.gemini_provider import GeminiProvider

logger = logging.getLogger("era_vision.analyzer")


def _build_prompt(window: WindowInfo, task_context: str | None, trigger: str) -> str:
    lines = [
        f"Active window title: {window.title!r}" if window.title else "Active window title: (unavailable)",
        f"Active process: {window.process_name or '(unknown)'}",
        f"Trigger for this observation: {trigger}",
    ]
    if task_context:
        lines.append(f"Current user task (for context only, do not assume it is complete): {task_context}")
    lines.append(
        "Describe the application, the important visible UI elements, any visible "
        "error messages, and the important visible text. Return JSON matching the "
        "provided schema. Also set chart_detected=true if any financial/trading chart is visible."
    )
    return "\n".join(lines)


def _build_screen_description(state: ScreenState, window: WindowInfo) -> str:
    """Build a natural-language description of current screen state for action analysis."""
    parts = [
        f"Application: {state.application}",
        f"Window title: {window.title or '(unknown)'}",
        f"Summary: {state.summary}",
    ]
    if state.errors:
        parts.append(f"Visible errors: {', '.join(state.errors)}")
    if state.current_activity:
        parts.append(f"Current activity: {state.current_activity}")
    if state.important_text:
        parts.append(f"Important text on screen: {'; '.join(state.important_text[:5])}")
    return "\n".join(parts)


class Analyzer:
    def __init__(self, provider: GeminiProvider) -> None:
        self._provider = provider

    @property
    def provider_configured(self) -> bool:
        return self._provider.is_configured()

    @property
    def provider_name(self) -> str:
        return self._provider.name

    def analyze(
        self,
        frame: Frame,
        window: WindowInfo,
        *,
        trigger: str,
        roi_bbox: tuple[int, int, int, int] | None = None,
        task_context: str | None = None,
    ) -> ScreenState:
        """Analyze a captured screen frame and return a structured ScreenState.

        This is the core perception call — called continuously by VisionService.
        """
        prompt = _build_prompt(window, task_context, trigger)
        roi_image = frame.crop(roi_bbox).image if roi_bbox is not None else None
        try:
            return self._provider.analyze(frame.image, prompt=prompt, roi_image=roi_image)
        except ProviderError:
            raise

    def analyze_for_action(
        self,
        frame: Frame,
        state: ScreenState,
        window: WindowInfo,
        trigger_description: str,
    ) -> ActionDecision:
        """Decide what ERA Agent action to take given the current screen state.

        Called by ActionEngine when an error or important event is detected.
        Returns ActionDecision with command=None if no action is needed.
        """
        screen_description = _build_screen_description(state, window)
        try:
            return self._provider.analyze_for_action(
                frame.image,
                screen_description=screen_description,
                trigger_description=trigger_description,
            )
        except ProviderError:
            raise

    def analyze_chart(
        self,
        frame: Frame,
        state: ScreenState,
        window: WindowInfo,
    ) -> ChartAnalysis:
        """Perform deep technical analysis of a trading chart on screen.

        Called by ActionEngine when chart_detected=True in the ScreenState.
        Returns ChartAnalysis with trend, support/resistance, indicators, patterns, and predictions.
        """
        context = _build_screen_description(state, window)
        try:
            return self._provider.analyze_chart(frame.image, context=context)
        except ProviderError:
            raise
