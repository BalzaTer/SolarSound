"""Windows startup registration for SolarSound."""

import os
import sys


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "SolarSound"


def _command() -> str:
    if getattr(sys, "frozen", False):
        executable = os.path.abspath(sys.executable)
        return f'"{executable}" --startup'
    executable = os.path.abspath(sys.executable)
    script = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "main.py"))
    return f'"{executable}" "{script}" --startup'


def set_launch_at_startup(enabled: bool) -> bool:
    """Enable or disable the current-user Windows startup entry."""
    if os.name != "nt":
        return False
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            RUN_KEY,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            if enabled:
                winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, _command())
            else:
                try:
                    winreg.DeleteValue(key, RUN_VALUE)
                except FileNotFoundError:
                    pass
        return True
    except (OSError, ImportError):
        return False
