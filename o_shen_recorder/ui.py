"""tkinter 图形界面（仅用 Python 标准库）。"""

from __future__ import annotations

import os
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Optional, Tuple

from .app_info import APP_NAME, VERSION, COPYRIGHT, COMPANY, about_text, asset_path
from .recorder import RecorderConfig, RecorderState, ScreenRecorder
from .region_selector import RegionSelector
from .hotkey import HotkeyManager

ICON_PATH = asset_path("app.ico")


def fmt_code(label: str) -> str:
    """把输出格式下拉框的显示文案映射为 RecorderConfig 需要的规范值。"""
    return "mp4" if "MP4" in label else "avi"


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME}  {VERSION}")
        self.geometry("560x520")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        if os.path.isfile(ICON_PATH):
            try:
                self.iconbitmap(ICON_PATH)
            except tk.TclError:
                pass

        self.recorder: Optional[ScreenRecorder] = None
        self._poll_job: Optional[str] = None
        self._worker: Optional[threading.Thread] = None
        self.hotkey = HotkeyManager(self, self._toggle_pause)

        self._build()
        self._set_idle()

    # ---------------- UI ----------------
    def _build(self) -> None:
        pad = {"padx": 10, "pady": 5}
        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True, padx=12, pady=10)

        ttk.Label(frm, text=APP_NAME, font=("Microsoft YaHei UI", 14, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 2)
        )
        ttk.Label(
            frm, text=f"{VERSION}   {COPYRIGHT} {COMPANY}   全部功能免费开放",
            foreground="#666666",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 8))

        # 输出文件
        ttk.Label(frm, text="输出文件").grid(row=2, column=0, sticky="w", **pad)
        self.var_out = tk.StringVar(value=self._default_output())
        ttk.Entry(frm, textvariable=self.var_out, width=38).grid(
            row=2, column=1, sticky="we", **pad
        )
        ttk.Button(frm, text="浏览…", command=self._choose_output, width=8).grid(
            row=2, column=2, **pad
        )

        # 帧率 / 质量
        ttk.Label(frm, text="帧率 (fps)").grid(row=3, column=0, sticky="w", **pad)
        self.var_fps = tk.IntVar(value=10)
        ttk.Spinbox(frm, from_=1, to=30, textvariable=self.var_fps, width=8).grid(
            row=3, column=1, sticky="w", **pad
        )

        ttk.Label(frm, text="JPEG 质量").grid(row=4, column=0, sticky="w", **pad)
        self.var_quality = tk.IntVar(value=80)
        ttk.Scale(frm, from_=30, to=95, variable=self.var_quality,
                  orient="horizontal").grid(row=4, column=1, sticky="we", **pad)
        self.lbl_quality = ttk.Label(frm, text="80")
        self.lbl_quality.grid(row=4, column=2, **pad)
        self.var_quality.trace_add("write", self._on_quality)

        # 输出格式：AVI (无依赖) / MP4 (H.264 压缩)
        ttk.Label(frm, text="输出格式").grid(row=5, column=0, sticky="w", **pad)
        self.var_fmt = tk.StringVar(value="AVI (无损 MJPEG)")
        fmt_box = ttk.Combobox(frm, textvariable=self.var_fmt, width=16,
                               state="readonly",
                               values=["AVI (无损 MJPEG)", "MP4 (H.264 压缩)"])
        fmt_box.grid(row=5, column=1, sticky="w", **pad)
        fmt_box.bind("<<ComboboxSelected>>", self._on_format)
        self.lbl_fmt_note = ttk.Label(frm, text="", foreground="#666666")
        self.lbl_fmt_note.grid(row=5, column=2, sticky="w", **pad)

        # 选区：手动输入 + 鼠标框选 / 窗口捕获
        ttk.Label(frm, text="录制区域").grid(row=6, column=0, sticky="w", **pad)
        self.var_region = tk.StringVar(value="")
        ttk.Entry(frm, textvariable=self.var_region, width=38).grid(
            row=6, column=1, sticky="we", **pad
        )
        reg_btns = ttk.Frame(frm)
        reg_btns.grid(row=6, column=2, **pad)
        ttk.Button(reg_btns, text="全屏", command=self._pick_fullscreen,
                   width=6).pack(side="left", padx=2)
        ttk.Button(reg_btns, text="鼠标框选", command=self._pick_region,
                   width=10).pack(side="left", padx=2)
        ttk.Button(reg_btns, text="窗口捕获", command=self._pick_window,
                   width=10).pack(side="left", padx=2)
        ttk.Label(frm, text="留空 = 全屏；可手填 x,y,w,h，或点「全屏」/「鼠标框选」/「窗口捕获」",
                  foreground="#666666").grid(
            row=7, column=0, columnspan=3, sticky="w", padx=10
        )

        # 音频：系统声音 + 麦克风混音
        self.var_audio = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            frm, text="录制系统声音 (WASAPI loopback)", variable=self.var_audio
        ).grid(row=8, column=0, columnspan=2, sticky="w", **pad)
        self.var_mic = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            frm, text="同时混音麦克风", variable=self.var_mic
        ).grid(row=8, column=2, sticky="w", **pad)

        ttk.Label(frm, text="麦克风音量").grid(row=9, column=0, sticky="w", **pad)
        self.var_mic_gain = tk.DoubleVar(value=1.0)
        ttk.Scale(frm, from_=0.0, to=3.0, variable=self.var_mic_gain,
                  orient="horizontal").grid(row=9, column=1, sticky="we", **pad)
        self.lbl_gain = ttk.Label(frm, text="1.0x")
        self.lbl_gain.grid(row=9, column=2, **pad)
        self.var_mic_gain.trace_add("write", self._on_gain)

        # MP4 画质 (CRF)
        ttk.Label(frm, text="MP4 画质").grid(row=10, column=0, sticky="w", **pad)
        self.var_crf = tk.IntVar(value=23)
        ttk.Scale(frm, from_=18, to=30, variable=self.var_crf,
                  orient="horizontal").grid(row=10, column=1, sticky="we", **pad)
        self.lbl_crf = ttk.Label(frm, text="23 (CRF)")
        self.lbl_crf.grid(row=10, column=2, **pad)
        self.var_crf.trace_add("write", self._on_crf)

        # 按钮
        btns = ttk.Frame(frm)
        btns.grid(row=11, column=0, columnspan=3, pady=(12, 4))
        self.btn_start = ttk.Button(btns, text="开始录制", command=self._start, width=14)
        self.btn_start.pack(side="left", padx=6)
        self.btn_pause = ttk.Button(btns, text="暂停", command=self._toggle_pause, width=10)
        self.btn_pause.pack(side="left", padx=6)
        self.btn_stop = ttk.Button(btns, text="停止录制", command=self._stop, width=14)
        self.btn_stop.pack(side="left", padx=6)
        ttk.Button(btns, text="关于", command=self._about, width=8).pack(side="left", padx=6)

        # 状态
        self.var_status = tk.StringVar(value="就绪")
        ttk.Label(frm, textvariable=self.var_status, foreground="#0a6").grid(
            row=12, column=0, columnspan=3, sticky="w", **pad
        )
        self.progress = ttk.Progressbar(frm, mode="indeterminate", length=480)
        self.progress.grid(row=13, column=0, columnspan=3, sticky="we", **pad)
        frm.columnconfigure(1, weight=1)
        self._on_format()

    def _default_output(self) -> str:
        d = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "recordings")
        stamp = time.strftime("%Y%m%d_%H%M%S")
        return os.path.join(d, f"recording_{stamp}.avi")

    def _choose_output(self) -> None:
        p = filedialog.asksaveasfilename(
            defaultextension=".avi", filetypes=[("AVI 视频", "*.avi"), ("所有文件", "*.*")],
            initialfile=os.path.basename(self.var_out.get()),
        )
        if p:
            self.var_out.set(p)

    def _on_quality(self, *_a) -> None:
        try:
            self.lbl_quality.config(text=str(int(self.var_quality.get())))
        except tk.TclError:
            pass

    def _on_gain(self, *_a) -> None:
        try:
            self.lbl_gain.config(text=f"{self.var_mic_gain.get():.1f}x")
        except tk.TclError:
            pass

    def _on_crf(self, *_a) -> None:
        try:
            self.lbl_crf.config(text=f"{int(self.var_crf.get())} (CRF)")
        except tk.TclError:
            pass

    def _on_format(self, *_a) -> None:
        label = self.var_fmt.get()
        fmt = fmt_code(label)
        note = "H.264 压缩，体积小" if fmt == "mp4" else "MJPEG+PCM，无损但体积大"
        # 同步默认输出扩展名
        cur = self.var_out.get()
        base, _ = os.path.splitext(cur)
        self.var_out.set(base + "." + fmt)
        self.lbl_fmt_note.config(text=note)

    def _pick_region(self) -> None:
        """隐藏主窗口后弹出全屏框选层（拖拽模式），结果回填 x,y,w,h。"""
        self._launch_selector("drag")

    def _pick_fullscreen(self) -> None:
        """清空区域输入框 = 全屏录制。"""
        self.var_region.set("")
        self.var_status.set("已选择：全屏")

    def _pick_window(self) -> None:
        """隐藏主窗口后弹出框选层并直接进入窗口捕获模式。"""
        self._launch_selector("window")

    def _launch_selector(self, initial_mode: str) -> None:
        """隐藏主窗口后弹出框选层（指定初始模式），结果回填 x,y,w,h。"""
        self.withdraw()
        self.update_idletasks()

        def done(box) -> None:
            self.deiconify()
            if box is None:
                self.var_status.set("已取消选择，区域保持不变")
                return
            x0, y0, x1, y1 = box
            self.var_region.set(f"{x0},{y0},{x1 - x0},{y1 - y0}")
            kind = "窗口" if initial_mode == "window" else "区域"
            self.var_status.set(f"已选择{kind}：{x0},{y0}  {x1 - x0}x{y1 - y0}")

        # 稍延迟，确保主窗口已真正隐藏，否则会被覆盖层一起盖住
        self.after(120, lambda: RegionSelector.select(
            self, done, initial_mode=initial_mode))

    def _parse_region(self) -> Optional[Tuple[int, int, int, int]]:
        s = self.var_region.get().strip()
        if not s:
            return None
        parts = [int(x) for x in s.replace("，", ",").split(",")]
        if len(parts) != 4:
            raise ValueError("请填写 x,y,w,h 四个数字")
        x, y, w, h = parts
        if w <= 0 or h <= 0:
            raise ValueError("宽高必须为正数")
        return (x, y, x + w, y + h)

    # ---------------- 控制 ----------------
    def _start(self) -> None:
        try:
            out = self.var_out.get().strip()
            if not out:
                raise ValueError("请指定输出文件")
            cfg = RecorderConfig(
                output_path=out,
                fps=max(1, min(30, int(self.var_fps.get()))),
                quality=max(30, min(95, int(self.var_quality.get()))),
                region=self._parse_region(),
                record_audio=bool(self.var_audio.get()),
                record_mic=bool(self.var_mic.get()),
                mic_gain=float(self.var_mic_gain.get()),
                format=fmt_code(self.var_fmt.get()),
                h264_crf=int(self.var_crf.get()),
            )
        except (ValueError, tk.TclError) as exc:
            messagebox.showerror("参数错误", str(exc))
            return

        self.var_status.set("正在录制…  (Ctrl+Shift+Alt+Z 暂停)")
        self.progress.start(80)
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.btn_pause.config(state="normal")
        self.btn_pause.config(text="暂停")

        self._worker = threading.Thread(
            target=self._record_worker, args=(cfg,), daemon=True
        )
        self._worker.start()
        self.hotkey.start()      # 全局热键：即使窗口最小化也能暂停/继续
        self._poll()
        self.iconify()            # 开始录制后最小化，避免被录进画面

    def _record_worker(self, cfg: RecorderConfig) -> None:
        rec = ScreenRecorder(cfg)
        self.recorder = rec
        rec.start()
        while rec.state.running:
            time.sleep(0.1)
        # 录制结束（用户停止或出错）由 _poll 收尾

    def _stop(self) -> None:
        if self.recorder:
            self.recorder.stop(timeout=0.5)  # 发信号，线程自行收尾

    def _poll(self) -> None:
        rec = self.recorder
        if rec is None:
            self._poll_job = self.after(100, self._poll)
            return
        st: RecorderState = rec.state
        if st.running:
            if st.paused:
                self.var_status.set("已暂停  (Ctrl+Shift+Alt+Z 继续)")
            else:
                elapsed = time.time() - st.started_at
                audio = "  ♪ 音频" if st.audio_active else ""
                fmt = f" [{st.format.upper()}]" if st.format else ""
                self.var_status.set(
                    f"录制中{fmt}  {elapsed:5.1f}s   帧 {st.frames}   {st.width}x{st.height}{audio}"
                )
            self.btn_pause.config(text="继续" if st.paused else "暂停")
            self._poll_job = self.after(200, self._poll)
        else:
            self._finish(st)

    def _toggle_pause(self) -> None:
        rec = self.recorder
        if rec is None or not rec.state.running:
            return
        if rec.state.paused:
            rec.resume()
            self.btn_pause.config(text="暂停")
            self.iconify()            # 继续录制后再次最小化，避免被录进画面
        else:
            rec.pause()
            self.btn_pause.config(text="继续")

    def _finish(self, st: RecorderState) -> None:
        self.progress.stop()
        self.hotkey.stop()
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
        except tk.TclError:
            pass
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.btn_pause.config(state="disabled")
        self.btn_pause.config(text="暂停")
        size = ""
        try:
            if os.path.isfile(st.output_path):
                size = f"  ({os.path.getsize(st.output_path) / 1024:.0f} KB)"
        except OSError:
            pass
        if st.error:
            self.var_status.set(f"录制出错：{st.error}")
            messagebox.showerror("录制出错", st.error)
        else:
            audio = (f"  音频 {st.audio_samples} 采样帧" if st.audio_samples else "")
            self.var_status.set(
                f"完成：{st.frames} 帧{audio}{size}  →  {st.output_path}"
            )
            if st.audio_note and "不可用" in st.audio_note:
                self.var_status.set(self.var_status.get() + f"\n{st.audio_note}")
        self.recorder = None
        self._poll_job = None

    def _set_idle(self) -> None:
        self.btn_stop.config(state="disabled")
        self.btn_pause.config(state="disabled")
        self.btn_pause.config(text="暂停")

    def _about(self) -> None:
        messagebox.showinfo("关于", about_text())

    def _on_close(self) -> None:
        self.hotkey.stop()
        if self.recorder and self.recorder.state.running:
            if not messagebox.askyesno("确认", "正在录制，确定退出吗？"):
                return
            self.recorder.stop(timeout=0.5)
        self.destroy()


def main() -> None:
    App().mainloop()
