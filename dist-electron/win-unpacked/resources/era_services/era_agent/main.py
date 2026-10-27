"""Era Agent for Windows — entry point.

A local agent that executes simple, safe system commands. This first
version runs standalone from the command line, driven by typed text
commands. A future version will connect this agent to "Era" (an
assistant built in Google AI Studio) so that Era can send commands
here over an API for the agent to execute — the command registry in
`commands/` is designed to make that swap easy, since `main.py` only
needs a command name string to run any registered command.

Run with:
    python main.py
"""

from __future__ import annotations

from commands import registry
from commands.registry import CommandResult


def print_banner() -> None:
    print("=" * 50)
    print(" Era Agent for Windows — v0.1")
    print(" Local command execution agent")
    print("=" * 50)


def print_available_commands() -> None:
    print("\nAvailable commands:")
    for name, description in registry.list_commands().items():
        print(f"  - {name:<20} {description}")
    print("  - help                 Show this list again")
    print("  - exit / quit          Close the agent\n")


def format_result(command_name: str, result: CommandResult) -> str:
    """Formats a CommandResult into a single clear status line."""
    status = "SUCCESS" if result.success else "FAILURE"
    return f"[{status}] {command_name}: {result.message}"


def run() -> None:
    """Main interactive loop: read a command, execute it, show the result."""
    print_banner()
    print_available_commands()

    while True:
        try:
            user_input = input("era> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting Era Agent. Goodbye.")
            break

        if not user_input:
            continue

        command_name = user_input.lower()

        if command_name in ("exit", "quit"):
            print("Exiting Era Agent. Goodbye.")
            break

        if command_name == "help":
            print_available_commands()
            continue

        result = registry.execute(command_name)
        print(format_result(command_name, result))


if __name__ == "__main__":
    run()
