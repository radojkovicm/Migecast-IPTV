"""Tiny startup profiler.

``mark(name)`` records the time elapsed since the process was created, so the
log shows how long each startup phase took (PyInstaller bootstrap, Qt import,
window shown, database ready, playlist loaded, ...).
"""
import json
import logging
import os
import sys
import time

logger = logging.getLogger(__name__)

_T0 = time.perf_counter()
_WALL0 = time.time()
_marks = []


def _process_start_offset_ms() -> float:
    """Milliseconds between process creation and this module's import."""
    if sys.platform != "win32":
        return 0.0
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        # Declare types: the process handle is 64-bit; the default ctypes
        # "int" would truncate it and the call would silently fail.
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        kernel32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        kernel32.GetProcessTimes.restype = wintypes.BOOL
        creation, exit_, kernel, user = (wintypes.FILETIME() for _ in range(4))
        handle = kernel32.GetCurrentProcess()
        ok = kernel32.GetProcessTimes(
            handle, ctypes.byref(creation), ctypes.byref(exit_),
            ctypes.byref(kernel), ctypes.byref(user))
        if not ok:
            return 0.0
        ticks = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
        created_unix = ticks / 10_000_000 - 11_644_473_600
        return max(0.0, (_WALL0 - created_unix) * 1000.0)
    except Exception:
        return 0.0


_OFFSET_MS = _process_start_offset_ms()


def elapsed_ms() -> float:
    return _OFFSET_MS + (time.perf_counter() - _T0) * 1000.0


def mark(name: str) -> float:
    value = round(elapsed_ms(), 1)
    _marks.append((name, value))
    logger.info("[startup] %-28s %8.1f ms", name, value)
    return value


def marks() -> dict:
    result = {"process_to_python_ms": round(_OFFSET_MS, 1)}
    for name, value in _marks:
        result.setdefault(name, value)
    return result


def write_report(path: str) -> None:
    try:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(marks(), handle, indent=2)
    except OSError as exc:
        logger.warning("Could not write startup report: %s", exc)


def env_report_path():
    return os.environ.get("MIGECAST_STARTUP_REPORT")
