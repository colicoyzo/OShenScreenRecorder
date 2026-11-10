"""DPI 感知：保证 tkinter 的鼠标/窗口坐标与 ImageGrab 抓屏的物理像素一致。

必须在创建任何 tkinter 窗口之前调用。Windows 有缩放（本机 125%）时，
DPI-unaware 进程的逻辑坐标会被缩放，导致框选区域与实际抓屏偏移。
"""

from __future__ import annotations

import ctypes
import sys

_applied = False


def enable_dpi_awareness() -> bool:
    """设为 Per-Monitor DPI Aware v2；返回是否成功。"""
    global _applied
    if _applied or sys.platform != "win32":
        return _applied
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        # PER_MONITOR_AWARE_V2 = (DPI_AWARENESS_CONTEXT)(-4)
        if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            _applied = True
            return True
    except Exception:
        pass
    try:
        # 回退：Windows 8.1+ 的 per-monitor aware
        if ctypes.WinDLL("shcore").SetProcessDpiAwareness(2) == 0:
            _applied = True
            return True
    except Exception:
        pass
    try:
        if ctypes.WinDLL("user32").SetProcessDPIAware():
            _applied = True
    except Exception:
        pass
    return _applied
