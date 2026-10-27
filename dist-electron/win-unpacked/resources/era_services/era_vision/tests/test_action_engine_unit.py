"""Unit tests for ActionEngine and ChartAnalysis using standard unittest."""

import unittest
from unittest.mock import MagicMock, patch

from config import Settings
from vision.action_engine import ActionEngine
from vision.analyzer import Analyzer
from vision.context_manager import ContextManager
from vision.events import EventBus, ERROR_DETECTED, ACTION_DECIDED, CHART_DETECTED
from vision.models import ActionDecision, ActionOutcome, ChartAnalysis, ChartTrend, ScreenState, WindowInfo, ContextEntry


class TestActionEngine(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(
            action_engine_enabled=True,
            action_confidence_threshold=0.6,
            era_bridge_url="http://127.0.0.1:8100",
            era_bridge_api_key="test_key",
            action_log_only_mode=True, # Dry run for testing
        )
        self.events = EventBus()
        self.context = ContextManager(history_size=10, ttl_seconds=600.0)
        self.analyzer = MagicMock(spec=Analyzer)
        self.analyzer.provider_name = "mock_provider"
        self.analyzer.provider_configured = True
        
        self.engine = ActionEngine(
            settings=self.settings,
            analyzer=self.analyzer,
            context=self.context,
            events=self.events,
        )

    def test_status_initialization(self):
        status = self.engine.get_status()
        self.assertFalse(status["running"])
        self.assertTrue(status["enabled"])
        self.assertTrue(status["log_only_mode"])
        self.assertEqual(status["confidence_threshold"], 0.6)

    def test_on_error_detected_below_threshold(self):
        # Set context with error
        entry = ContextEntry(
            window=WindowInfo(title="Test App", process_name="test.exe"),
            state=ScreenState(application="TestApp", errors=["NullPointerError"]),
            trigger="pixel_change",
        )
        self.context.add_observation(entry)
        
        # Mock analyzer to return low confidence decision
        low_conf_decision = ActionDecision(
            command="click_screen",
            params={"x": 100, "y": 200},
            confidence=0.4, # < 0.6 threshold
            reasoning="Not sure",
        )
        self.analyzer.analyze_for_action.return_value = low_conf_decision
        
        # Patch _grab_frame so it doesn't try real MSS screen capture
        with patch.object(self.engine, "_grab_frame", return_value=MagicMock()):
            self.engine._on_error_detected("NullPointerError")
        
        logs = self.engine.get_action_log()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].outcome, ActionOutcome.SKIPPED)

    def test_chart_analysis_flow(self):
        entry = ContextEntry(
            window=WindowInfo(title="Binance - BTC/USDT", process_name="chrome.exe"),
            state=ScreenState(application="Binance", chart_detected=True),
            trigger="window_change",
        )
        self.context.add_observation(entry)
        
        chart_result = ChartAnalysis(
            chart_type="candlestick",
            asset="BTC/USDT",
            timeframe="15m",
            current_trend=ChartTrend.BULLISH,
            trend_strength="strong",
            bullish_probability=0.8,
            bearish_probability=0.2,
            summary="Strong upward trend with support at 65000",
            confidence=0.9,
        )
        self.analyzer.analyze_chart.return_value = chart_result
        
        with patch.object(self.engine, "_grab_frame", return_value=MagicMock()):
            self.engine._handle_chart(entry)
        
        charts = self.engine.get_chart_history()
        self.assertEqual(len(charts), 1)
        self.assertEqual(charts[0].asset, "BTC/USDT")
        self.assertEqual(charts[0].current_trend, ChartTrend.BULLISH)


if __name__ == "__main__":
    unittest.main()
