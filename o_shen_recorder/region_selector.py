"""全屏半透明覆盖层：鼠标拖拽框选录制区域，或按 W 切换为「窗口捕获」。

坐标是物理屏幕像素（调用前需 enable_dpi_awareness()），与 ImageGrab 一致。
返回 (left, top, right, bottom)，recorder 内部会再做偶数宽高对齐。

    RegionSelector.select(parent, on_done)   # on_done(box) 或 on_done(None) 取消

两种模式：
  * 拖拽框选（默认）：按住左键拖矩形，松开确认。
  * 窗口捕获（按 W 进入）：移动鼠标高亮其下的顶层窗口，单击选中该窗口矩形。
Esc / 右键随时取消；窗口捕获模式下再按一次 W 返回框选。
"""

from __future__ import annotations

import ctypes
import tkinter as tk
from ctypes import wintypes
from typing import Callable, Optional, Tuple

Box = Tuple[int, int, int, int]
TRANSPARENT_COLOR = "#0b0c0d"  # 将此颜色设为完全透明，桌面可见而矩形不透明

DRAG_TIP = "按住左键拖拽选择区域 · 松开确认 · Esc/右键取消 · [W] 窗口捕获"
WIN_TIP = "移动鼠标高亮窗口 · 单击选中 · [W] 返回框选 · Esc/右键取消"

# 需要从窗口枚举里剔除的桌面外壳窗口（避免点空白选中整个桌面）
_SHELL_CLASSES = ("Progman", "WorkerW", "Shell_SecondaryTrayWnd", "Shell_TrayWnd")


def screen_size() -> Tuple[int, int, int, int]:
    """虚拟桌面物理像素范围 (x, y, w, h)，含多显示器负坐标。"""
    u = ctypes.WinDLL("user32", use_last_error=True)
    # SM_XVIRTUALSCREEN=76, SM_YVIRTUALSCREEN=77,
    # SM_CXVIRTUALSCREEN=78, SM_CYVIRTUALSCREEN=79
    x, y = u.GetSystemMetrics(76), u.GetSystemMetrics(77)
    w, h = u.GetSystemMetrics(78), u.GetSystemMetrics(79)
    return (x, y, w, h)


def normalize_box(x0: int, y0: int, x1: int, y1: int) -> Optional[Box]:
    """规整拖拽矩形：处理反向拖拽、去掉过小选区、宽高取偶数。"""
    left, right = min(x0, x1), max(x0, x1)
    top, bottom = min(y0, y1), max(y0, y1)
    w, h = right - left, bottom - top
    if w < 8 or h < 8:
        return None
    w -= w & 1
    h -= h & 1
    return (left, top, left + w, top + h)


def enum_top_windows(exclude_hwnd: int = 0) -> list:
    """枚举顶层可见窗口，返回按 z 序（顶在前）的列表：

        [(hwnd, left, top, right, bottom, title), ...]

    自动跳过工具窗口、不可见窗口、零尺寸窗口、桌面外壳窗口，
    以及调用方传入的 exclude_hwnd（通常是本覆盖层自身）。
    """
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    GWL_EXSTYLE = -20
    WS_EX_TOOLWINDOW = 0x00000080
    rect = wintypes.RECT()
    cls_buf = ctypes.create_unicode_buffer(260)
    results: list = []

    def cb(hwnd, _lparam) -> bool:
        if hwnd == exclude_hwnd:
            return True
        if user32.GetWindowLongW(hwnd, GWL_EXSTYLE) & WS_EX_TOOLWINDOW:
            return True
        if not user32.IsWindowVisible(hwnd):
            return True
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return True
        if rect.right - rect.left <= 0 or rect.bottom - rect.top <= 0:
            return True
        user32.GetClassNameW(hwnd, cls_buf, 260)
        if cls_buf.value in _SHELL_CLASSES:
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        title_buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, title_buf, n + 1)
        results.append((hwnd, rect.left, rect.top, rect.right, rect.bottom,
                        title_buf.value))
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    try:
        user32.EnumWindows(WNDENUMPROC(cb), 0)
    except Exception:
        pass
    return results


def _window_at_point(windows: list, sx: int, sy: int):
    """在枚举结果里找包含点 (sx,sy) 的「最上层」窗口（结果已按 z 序排列）。"""
    for hwnd, l, t, r, b, title in windows:
        if l <= sx <= r and t <= sy <= b:
            return (l, t, r, b, title)
    return None


class RegionSelector:
    """模态覆盖窗口。

    默认拖拽框选；按 W 切换到窗口捕获：高亮鼠标下窗口、单击选中。
    Esc / 右键取消。
    """

    def __init__(self, parent: tk.Misc, on_done: Callable[[Optional[Box]], None],
                 initial_mode: str = "drag") -> None:
        self.on_done = on_done
        self.mode = "window" if initial_mode == "window" else "drag"
        vx, vy, vw, vh = screen_size()

        self.win = tk.Toplevel(parent)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.geometry(f"{vw}x{vh}+{vx}+{vy}")
        self.win.configure(bg=TRANSPARENT_COLOR, cursor="crosshair")
        try:
            self.win.attributes("-alpha", 0.3)  # 半透明覆盖层：既能看清桌面，又能捕获全部鼠标事件
        except tk.TclError:
            self.win.attributes("-transparentcolor", TRANSPARENT_COLOR)  # 极少数系统回退
        self.win.grab_set()
        self.win.focus_force()
        self._hwnd = self.win.winfo_id()

        self.canvas = tk.Canvas(self.win, width=vw, height=vh,
                                highlightthickness=0, bg=TRANSPARENT_COLOR,
                                cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)
        # Canvas 坐标是窗口相对 (0..vw)，绝对屏幕坐标 = canvas 坐标 + 虚拟桌面原点
        self._ox, self._oy = vx, vy
        self._vw, self._vh = vw, vh

        self.tip = self.canvas.create_text(
            vw // 2, 40, text=(WIN_TIP if self.mode == "window" else DRAG_TIP),
            fill="white", font=("Microsoft YaHei UI", 13, "bold"),
        )
        self.size_text = self.canvas.create_text(
            vw // 2, 68, text="", fill="#ffe66d",
            font=("Microsoft YaHei UI", 12, "bold"),
        )
        self.rect = None
        self.start: Optional[Tuple[int, int]] = None  # canvas 相对坐标

        # 统一在画布上派发，按模式分支
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Motion>", self._on_motion)
        self.win.bind("<KeyPress-w>", self._toggle_mode)
        self.win.bind("<KeyPress-W>", self._toggle_mode)
        self.win.bind("<Escape>", lambda _e: self._cancel())
        self.win.bind("<ButtonPress-3>", lambda _e: self._cancel())
        self.win.protocol("WM_DELETE_WINDOW", self._cancel)

    # ---------------- 绘制辅助 ----------------
    def _show_rect(self, l: int, t: int, r: int, b: int,
                   color: str, fill: str, stipple: str = "") -> None:
        c = self.canvas
        coords = (l - self._ox, t - self._oy, r - self._ox, b - self._oy)
        if self.rect is None:
            self.rect = c.create_rectangle(*coords, outline=color, width=3,
                                           fill=fill, stipple=stipple)
        else:
            c.coords(self.rect, *coords)
            c.itemconfigure(self.rect, outline=color, width=3,
                            fill=fill, stipple=stipple)
        c.itemconfigure(self.rect, state="normal")

    def _hide_rect(self) -> None:
        if self.rect is not None:
            self.canvas.itemconfigure(self.rect, state="hidden")

    def _set_tip(self, text: str) -> None:
        self.canvas.itemconfigure(self.tip, text=text)

    # ---------------- 模式切换 ----------------
    def _toggle_mode(self, _e=None) -> None:
        if self.mode == "drag":
            self.mode = "window"
            self._set_tip(WIN_TIP)
            self._hide_rect()
            self.canvas.itemconfigure(self.size_text, text="")
        else:
            self.mode = "drag"
            self._set_tip(DRAG_TIP)
            self._hide_rect()
            self.canvas.itemconfigure(self.size_text, text="")

    # ---------------- 事件 ----------------
    def _on_press(self, event) -> None:
        if self.mode == "window":
            self._pick_window(event)
            return
        # 拖拽框选
        self.start = (event.x, event.y)
        self._show_rect(event.x, event.y, event.x, event.y,
                        "#4da3ff", "#4da3ff", stipple="gray50")

    def _on_drag(self, event) -> None:
        if self.mode != "drag" or self.rect is None or self.start is None:
            return
        self.canvas.coords(self.rect, self.start[0], self.start[1],
                           event.x, event.y)
        w, h = abs(event.x - self.start[0]), abs(event.y - self.start[1])
        self.canvas.itemconfigure(self.size_text, text=f"{w} × {h} 像素")

    def _on_motion(self, event) -> None:
        if self.mode != "window":
            return
        sx, sy = event.x + self._ox, event.y + self._oy
        win = _window_at_point(enum_top_windows(exclude_hwnd=self._hwnd), sx, sy)
        if win:
            l, t, r, b, title = win
            self._show_rect(l, t, r, b, "#39d353", "", stipple="")
            self.canvas.itemconfigure(
                self.size_text,
                text=f"{title or '(无标题)'}   {r - l} × {b - t} 像素")
        else:
            self._hide_rect()
            self.canvas.itemconfigure(self.size_text, text="")

    def _pick_window(self, event) -> None:
        sx, sy = event.x + self._ox, event.y + self._oy
        win = _window_at_point(enum_top_windows(exclude_hwnd=self._hwnd), sx, sy)
        if not win:
            return  # 点在桌面空白处：保持窗口模式，等待移到窗口上
        box = (win[0], win[1], win[2], win[3])  # (left, top, right, bottom)
        self._close()
        self.on_done(box)

    def _on_release(self, event) -> None:
        if self.mode != "drag" or self.start is None:
            return
        # 转成绝对屏幕坐标（与 ImageGrab bbox 一致）
        x0 = self.start[0] + self._ox
        y0 = self.start[1] + self._oy
        x1 = event.x + self._ox
        y1 = event.y + self._oy
        box = normalize_box(x0, y0, x1, y1)
        self._close()
        self.on_done(box)

    def _cancel(self) -> None:
        self._close()
        self.on_done(None)

    def _close(self) -> None:
        try:
            self.win.grab_release()
        except tk.TclError:
            pass
        self.win.destroy()

    @staticmethod
    def select(parent: tk.Misc,
               on_done: Callable[[Optional[Box]], None],
               initial_mode: str = "drag") -> "RegionSelector":
        return RegionSelector(parent, on_done, initial_mode=initial_mode)
