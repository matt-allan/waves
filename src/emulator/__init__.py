"""Python Game Boy emulator bindings (direct ctypes to libsameboy)."""

from .core import Button, Emulator

__all__ = ["Emulator", "Button"]
