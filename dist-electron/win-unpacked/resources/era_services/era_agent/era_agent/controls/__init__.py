"""Modular System Control Package for Era Agent.

Exports hardware automation controllers and intent parser for Windows system functions.
"""

from .audio import AudioControl
from .display import DisplayControl
from .intent_parser import IntentParser, SystemIntent
from .keyboard import KeyboardControl
from .manager import SystemControlManager
from .peripherals import PeripheralControl
from .phone_link import PhoneLinkControl

__all__ = [
    "SystemControlManager",
    "AudioControl",
    "DisplayControl",
    "PeripheralControl",
    "KeyboardControl",
    "PhoneLinkControl",
    "IntentParser",
    "SystemIntent",
]

