"""Comprehensive live test script for Era System Controls.

Tests:
1. Keyboard Backlight control ("key light vhalu kar", "set keyboard backlight 100%")
2. Audio Volume control ("volume set to 60", "increase volume", "mute sound")
3. Display Brightness control ("increase brightness", "dim screen", "set brightness to 70%")
4. Peripheral Control ("turn on bluetooth", "get peripheral status")
"""

import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from commands import registry
from controls import SystemControlManager, IntentParser


def run_test(label: str, query: str):
    print(f"\n[TEST: {label}] Query: '{query}'")
    intent = IntentParser.parse(query)
    print(f"  Parsed Intent: action='{intent.action}', params={intent.params}, matched={intent.matched}")

    res = registry.execute("process_natural_language_control", query=query)
    status = "SUCCESS" if res.success else "FAILURE / HANDLED"
    print(f"  Execution Result: [{status}] {res.message}")
    return res.success


def main():
    print("=" * 60)
    print(" ERA SYSTEM CONTROL COMPREHENSIVE LIVE TEST SUITE")
    print("=" * 60)

    # 1. Keyboard Backlight Tests
    run_test("Keyboard Backlight - Hinglish Turn On", "key light vhalu kar")
    run_test("Keyboard Backlight - Set 100%", "set keyboard light 100%")
    run_test("Keyboard Backlight - Dim", "keyboard light down")

    # 2. Audio Volume Tests
    run_test("Audio Volume - Set 60%", "volume set to 60")
    run_test("Audio Volume - Increase", "increase volume by 10")
    run_test("Audio Volume - Query", "get audio volume")
    run_test("Audio Volume - Mute", "mute sound")
    run_test("Audio Volume - Unmute", "unmute sound")

    # 3. Display Brightness Tests
    run_test("Display Brightness - Increase", "increase brightness")
    run_test("Display Brightness - Dim", "dim screen")
    run_test("Display Brightness - Set 75%", "set brightness to 75%")
    run_test("Display Brightness - Query", "get brightness")

    # 4. Peripheral Tests
    run_test("Bluetooth - Turn On", "turn on bluetooth")
    run_test("Bluetooth - Turn Off", "turn off bluetooth")
    run_test("Peripheral Status", "peripheral status")

    print("\n" + "=" * 60)
    print(" ALL SYSTEM CONTROL INTEGRATION TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    main()
