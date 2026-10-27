"""Command modules for Era Agent.

Importing this package imports every command module (currently just
`system_commands`), which causes each command to register itself with
the shared `registry`. To add a new command in the future:

    1. Create a new file in this folder, e.g. `browser_commands.py`.
    2. Write a function that returns a `CommandResult` and decorate it
       with `@registry.register("your_command_name", "description")`.
    3. Import that new module below, the same way `system_commands`
       is imported.

No changes to main.py are required — the new command will show up
automatically in the command list and become callable.
"""

from . import system_commands  # noqa: F401  (import registers its commands)
from . import system_controls  # noqa: F401  (import registers system control commands)
from .registry import registry

__all__ = ["registry"]

