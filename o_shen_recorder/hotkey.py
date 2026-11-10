"""全局热键（Windows）：即使主窗口最小化也能响应。

用 Win32 RegisterHotKey 在独立消息泵线程里注册，避免依赖 Tk 的焦点/可见性。
默认组合：Ctrl + Shift + Alt + Z（暂停/继续录制）。
"""

from __future__ import annotations

import ctypes
import threading
import tkinter as tk
from ctypes import wintypes
from typing import Callable, Optional

user32 = ctypes.windll.user32

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012

# 默认：Ctrl + Shift + Alt + Z
DEFAULT_MOD = MOD_CONTROL | MOD_SHIFT | MOD_ALT
DEFAULT_VK = 0x5A  # 'Z'


class HotkeyManager:
    """在专用线程里泵消息并捕获全局热键，触发时切回主线程调用 callback。"""

    def __init__(self, root: tk.Misc, callback: Callable[[], None]) -> None:
        self.root = root
        self.callback = callback
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._mod = DEFAULT_MOD
        self._vk = DEFAULT_VK

    def start(self, mod: int = DEFAULT_MOD, vk: int = DEFAULT_VK) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._mod, self._vk = mod, vk
        self._stop.clear()
        self._thread = threading.Thread(target=self._pump, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        try:
            user32.UnregisterHotKey(0, 1)
        except Exception:
            pass
        # 让阻塞在 GetMessageW 的泵线程退出
        if self._thread is not None:
            try:
                user32.PostThreadMessageW(self._thread.ident, WM_QUIT, 0, 0)
            except Exception:
                pass

    def _pump(self) -> None:
        if not user32.RegisterHotKey(0, 1, self._mod, self._vk):
            return  # 注册失败（如被其他程序占用）就静默放弃
        msg = wintypes.MSG()
        while not self._stop.is_set():
            ret = user32.GetMessageW(ctypes.byref(msg), 0, 0, 0)
            if ret == 0 or ret == -1:  # WM_QUIT / 错误
                break
            if msg.message == WM_HOTKEY:
                try:
                    self.root.after(0, self.callback)
                except Exception:
                    pass
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        try:
            user32.UnregisterHotKey(0, 1)
        except Exception:
            pass
