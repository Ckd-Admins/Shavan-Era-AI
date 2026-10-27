"""Smoke tests and verification script for Era Agent System Controls.

Tests Natural Language Intent Parsing and SystemControlManager execution.
Run with:
    python scripts/test_system_controls.py
"""

import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from controls import IntentParser, SystemControlManager
from commands import registry


def test_intent_parsing():
    print("--- Testing Natural Language Intent Parsing ---")
    test_cases = [
        ("increase brightness", "adjust_display_brightness", {"delta": 15}),
        ("increase brightness by 25%", "adjust_display_brightness", {"delta": 25}),
        ("dim screen", "adjust_display_brightness", {"delta": -15}),
        ("set brightness to 80%", "set_display_brightness", {"level": 80}),
        ("adjust volume to 50", "set_audio_volume", {"level": 50}),
        ("increase volume", "adjust_audio_volume", {"delta": 10}),
        ("turn down volume", "adjust_audio_volume", {"delta": -10}),
        ("mute volume", "toggle_audio_mute", {"mute": True}),
        ("unmute audio", "toggle_audio_mute", {"mute": False}),
        ("turn on bluetooth", "set_bluetooth_state", {"enable": True}),
        ("turn off bluetooth", "set_bluetooth_state", {"enable": False}),
        ("turn off wifi", "set_wifi_state", {"enable": False}),
        ("turn on wifi", "set_wifi_state", {"enable": True}),
        ("keyboard backlight up", "adjust_keyboard_backlight", {"delta": 25}),
        ("set keyboard light 100%", "set_keyboard_backlight", {"level": 100}),
    ]

    passed = 0
    for query, expected_action, expected_params in test_cases:
        intent = IntentParser.parse(query)
        action_ok = intent.action == expected_action
        params_ok = all(intent.params.get(k) == v for k, v in expected_params.items())

        if action_ok and params_ok:
            print(f"  [PASS] '{query}' -> action={intent.action}, params={intent.params}")
            passed += 1
        else:
            print(f"  [FAIL] '{query}' -> got action={intent.action}, params={intent.params} (expected {expected_action}, {expected_params})")

    print(f"\nIntent Parsing Results: {passed}/{len(test_cases)} tests passed.\n")
    assert passed == len(test_cases), "Some intent parsing tests failed."


def test_registry_integration():
    print("--- Testing Command Registry Integration ---")
    registered_cmds = registry.list_commands()
    expected_cmds = [
        "set_display_brightness",
        "adjust_display_brightness",
        "get_display_brightness",
        "set_audio_volume",
        "adjust_audio_volume",
        "toggle_audio_mute",
        "get_audio_volume",
        "set_bluetooth_state",
        "set_wifi_state",
        "get_peripheral_status",
        "set_keyboard_backlight",
        "adjust_keyboard_backlight",
        "process_natural_language_control",
    ]

    for cmd in expected_cmds:
        if cmd in registered_cmds:
            print(f"  [PASS] Command '{cmd}' registered successfully.")
        else:
            print(f"  [FAIL] Command '{cmd}' NOT registered.")
            assert False, f"Missing registered command '{cmd}'"

    print("\nRegistry Integration Results: All system control commands registered.\n")


def test_natural_language_execution():
    print("--- Testing System Control Execution via Natural Language ---")
    nl_queries = [
        "increase brightness",
        "adjust volume to 60%",
        "mute sound",
        "get audio volume",
        "get peripheral status",
    ]

    for q in nl_queries:
        res = registry.execute("process_natural_language_control", query=q)
        print(f"  Query: '{q}' -> Success: {res.success} | Message: {res.message}")

    print("\nExecution Test Complete.\n")


if __name__ == "__main__":
    test_intent_parsing()
    test_registry_integration()
    test_natural_language_execution()
    print("All smoke tests completed successfully!")
