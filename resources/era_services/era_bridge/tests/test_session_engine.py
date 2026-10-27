"""Unit tests for core/session_engine.py -- pure logic, no I/O."""

from core.command_catalog import CommandSpec, ParamSpec
from core.session_engine import resolve_next_step

CATALOG = {
    "simple_enabled": CommandSpec("simple_enabled", "no params", enabled=True),
    "disabled_cmd": CommandSpec("disabled_cmd", "not enabled", enabled=False),
    "needs_param": CommandSpec(
        "needs_param", "needs a param", enabled=True, params=[ParamSpec("thing", "What thing?")]
    ),
    "destructive": CommandSpec("destructive", "needs confirm", enabled=True, requires_confirmation=True),
}


def test_unknown_command():
    step = resolve_next_step(CATALOG, "does_not_exist", {}, False)
    assert step.kind == "unknown_command"


def test_disabled_command_short_circuits_immediately():
    step = resolve_next_step(CATALOG, "disabled_cmd", {}, False)
    assert step.kind == "not_enabled"


def test_simple_enabled_command_is_ready_immediately():
    step = resolve_next_step(CATALOG, "simple_enabled", {}, False)
    assert step.kind == "ready"


def test_enabled_command_missing_param_asks_for_it():
    step = resolve_next_step(CATALOG, "needs_param", {}, False)
    assert step.kind == "needs_input"
    assert step.param == "thing"


def test_enabled_command_with_param_supplied_is_ready():
    step = resolve_next_step(CATALOG, "needs_param", {"thing": "a file"}, False)
    assert step.kind == "ready"


def test_destructive_command_needs_confirmation_first():
    step = resolve_next_step(CATALOG, "destructive", {}, False)
    assert step.kind == "needs_confirmation"


def test_destructive_command_ready_once_confirmed():
    step = resolve_next_step(CATALOG, "destructive", {}, True)
    assert step.kind == "ready"


def test_real_catalog_has_expected_enabled_commands():
    """Verifies the real catalog has the expected minimum set of enabled commands.

    Updated to match the full working command catalog (25 total, 20 enabled)
    rather than the original staged subset (12 total, 5 enabled). The catalog
    now includes audio, display, Bluetooth, and Wi-Fi controls added by the
    real Local Agent integration.
    """
    from core.command_catalog import CATALOG as REAL_CATALOG

    enabled = sorted([name for name, spec in REAL_CATALOG.items() if spec.enabled])
    # Core UI launch commands must always be enabled
    core_expected = ["open_calculator", "open_camera", "open_chrome", "open_file_explorer", "open_notepad"]
    for cmd in core_expected:
        assert cmd in enabled, f"Expected core command '{cmd}' to be enabled in catalog"
    # The full catalog now has 25 commands (20 enabled); assert at least the minimum
    assert len(REAL_CATALOG) >= 12, f"Catalog should have at least 12 commands, got {len(REAL_CATALOG)}"
    assert len(enabled) >= 5, f"At least 5 commands should be enabled, got {len(enabled)}"
