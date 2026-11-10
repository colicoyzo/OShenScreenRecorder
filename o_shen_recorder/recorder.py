"""屏幕录制核心：抓屏 → JPEG，多音源 PCM 混音 → 交错写入 MJPEG+PCM AVI。

音频源（可任意组合，失败自动降级）：
  * 系统声音：WASAPI loopback（默认扬声器回环）
  * 麦克风：默认麦克风
两路独立时钟，按采样帧对齐后混合，用 tanh 软限幅避免叠加削波。

AVI 封装由本项目的 avi.py 手写实现；不依赖 ffmpeg / OpenCV / 编码器。
"""

from __future__ import annotations

import io
import os
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from PIL import ImageGrab

from .avi import AudioFormat, MjpegAviWriter
from .encoder import Mp4Encoder

AUDIO_SAMPLE_RATE = 48000
AUDIO_CHANNELS = 2
AUDIO_BLOCK = 1024  # 每次从设备读取的采样帧数
MIX_GAIN = 0.8      # 混音后软限幅前的增益


@dataclass
class RecorderConfig:
    output_path: str
    fps: int = 10
    quality: int = 80
    region: Optional[Tuple[int, int, int, int]] = None  # 选区；None = 全屏
    record_audio: bool = True   # 系统声音 (WASAPI loopback)
    record_mic: bool = False    # 麦克风（与系统声音混合）
    mic_gain: float = 1.0       # 麦克风音量倍率
    format: str = "avi"         # "avi" = MJPEG+PCM 无依赖；"mp4" = H.264+AAC (需 ffmpeg)
    h264_crf: int = 23          # MP4 画质：越小越清晰体积越大 (0-51)
    max_frames: int = 0         # 0 = 不限；自测时可设上限


@dataclass
class RecorderState:
    running: bool = False
    frames: int = 0
    audio_samples: int = 0
    audio_active: bool = False
    mic_active: bool = False
    sources: List[str] = field(default_factory=list)
    audio_note: str = ""
    started_at: float = 0.0
    error: Optional[str] = None
    output_path: str = ""
    width: int = 0
    height: int = 0
    format: str = "avi"
    paused: bool = False


class _AudioSource:
    """单个音频设备的后台采集线程，持续产出 float32 (N, 2) 数据块。"""

    def __init__(self, label: str, fmt: AudioFormat, mic_name: Optional[str] = None) -> None:
        self.label = label
        self.fmt = fmt
        self.mic_name = mic_name  # None = loopback；否则具体麦克风名
        self.q: "queue.Queue" = queue.Queue()
        self.stop_event = threading.Event()
        self.thread: Optional[threading.Thread] = None
        self.error: Optional[str] = None
        self.started = threading.Event()

    def start(self) -> None:
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        self.started.wait(3.0)

    def _run(self) -> None:
        try:
            import warnings
            import numpy as np
            import soundcard as sc
            from soundcard.mediafoundation import SoundcardRuntimeWarning

            # 静音时设备会报 "data discontinuity"，属正常，抑制避免刷屏
            warnings.simplefilter("ignore", SoundcardRuntimeWarning)

            if self.mic_name is None:
                speaker = sc.default_speaker()
                dev = sc.get_microphone(id=str(speaker.name), include_loopback=True)
            else:
                dev = sc.get_microphone(id=self.mic_name, include_loopback=False)

            with dev.recorder(
                samplerate=self.fmt.sample_rate,
                channels=self.fmt.channels,
                blocksize=AUDIO_BLOCK,
            ) as rec:
                self.started.set()
                while not self.stop_event.is_set():
                    data = rec.record(numframes=AUDIO_BLOCK)  # float32
                    self.q.put(np.asarray(data, dtype="float32"))
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"
            self.started.set()

    def drain(self):
        """取出当前所有数据块并拼成一个 (N, C) 数组。"""
        import numpy as np
        blocks = []
        while True:
            try:
                blocks.append(self.q.get_nowait())
            except queue.Empty:
                break
        if not blocks:
            return np.zeros((0, self.fmt.channels), dtype="float32")
        data = np.concatenate(blocks, axis=0)
        if data.ndim == 1:
            data = data[:, None]
        if data.shape[1] == 1 and self.fmt.channels == 2:  # 单声道 → 双声道
            data = np.repeat(data, 2, axis=1)
        elif data.shape[1] > self.fmt.channels:
            data = data[:, : self.fmt.channels]
        return data.astype("float32", copy=False)

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=3.0)
        return self.drain()


class _AudioMixer:
    """管理多个 _AudioSource，按采样帧对齐混合，保留未消费的余量。"""

    def __init__(self, fmt: AudioFormat, mic_gain: float = 1.0) -> None:
        self.fmt = fmt
        self.mic_gain = mic_gain
        self.sources: List[_AudioSource] = []
        self._pending: Dict[str, object] = {}
        self.failed: List[str] = []

    def add(self, label: str, mic_name: Optional[str]) -> None:
        src = _AudioSource(label, self.fmt, mic_name)
        try:
            src.start()
            if src.error:
                raise RuntimeError(src.error)
            self.sources.append(src)
            self._pending[label] = src.drain()
        except Exception as exc:
            self.failed.append(f"{label}: {exc}")
            try:
                src.stop()
            except Exception:
                pass

    @property
    def active(self) -> bool:
        return bool(self.sources)

    @property
    def labels(self) -> List[str]:
        return [s.label for s in self.sources]

    def _collect(self) -> bytes:
        """对齐各源到相同帧数，混合并转成 int16 PCM。"""
        import numpy as np
        arrays = []
        for s in self.sources:
            buffered = self._pending.get(s.label)
            if buffered is None or len(buffered) == 0:
                buffered = np.zeros((0, self.fmt.channels), dtype="float32")
            fresh = s.drain()
            data = (np.concatenate((buffered, fresh), axis=0)
                    if len(fresh) else buffered)
            arrays.append(data)

        n = min(len(a) for a in arrays) if arrays else 0
        if n <= 0:
            # 没有新数据：把已取到的存回，不产生音频块
            for s, a in zip(self.sources, arrays):
                self._pending[s.label] = a
            return b""

        mixed = np.zeros((n, self.fmt.channels), dtype="float32")
        for s, a in zip(self.sources, arrays):
            gain = self.mic_gain if s.mic_name is not None else 1.0
            mixed += a[:n] * gain
            self._pending[s.label] = a[n:]  # 未对齐的余量留到下次

        # 软限幅：tanh 比硬 clip 更不容易产生削波失真
        mixed = np.tanh(mixed * MIX_GAIN)
        pcm = (np.clip(mixed, -1.0, 1.0) * 32767.0).astype("<i2")
        return pcm.tobytes()

    def drain(self) -> bytes:
        return self._collect()

    def stop(self) -> bytes:
        """停止所有源，并把剩余数据按最短长度混合输出。"""
        import numpy as np
        for s in self.sources:
            tail = s.stop()
            prev = self._pending.get(s.label)
            if prev is None or len(prev) == 0:
                self._pending[s.label] = tail
            elif len(tail):
                self._pending[s.label] = np.concatenate((prev, tail), axis=0)
        arrays = [self._pending.get(s.label) for s in self.sources]
        arrays = [a if a is not None else np.zeros((0, self.fmt.channels), dtype="float32")
                  for a in arrays]
        n = min(len(a) for a in arrays) if arrays else 0
        if n <= 0:
            return b""
        mixed = np.zeros((n, self.fmt.channels), dtype="float32")
        for s, a in zip(self.sources, arrays):
            gain = self.mic_gain if s.mic_name is not None else 1.0
            mixed += a[:n] * gain
        mixed = np.tanh(mixed * MIX_GAIN)
        return (np.clip(mixed, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()

    def hard_stop(self) -> None:
        for s in self.sources:
            try:
                s.stop_event.set()
                if s.thread:
                    s.thread.join(timeout=1.0)
            except Exception:
                pass


class ScreenRecorder:
    """在后台线程录制；主线程通过 state / on_update 观察进度。"""

    def __init__(
        self,
        config: RecorderConfig,
        on_update: Optional[Callable[[RecorderState], None]] = None,
    ) -> None:
        self.config = config
        self.state = RecorderState(output_path=config.output_path)
        self._on_update = on_update
        self._stop = threading.Event()
        self._pause = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            raise RuntimeError("recorder already running")
        if self.config.format not in ("avi", "mp4"):
            raise ValueError("format 只支持 avi / mp4")
        self._stop.clear()
        self.state = RecorderState(running=True, started_at=time.time(),
                                   output_path=self.config.output_path,
                                   format=self.config.format)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._emit()

    def stop(self, timeout: float = 10.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=timeout)

    def pause(self) -> None:
        """暂停：停止抓取新帧（音频缓冲一并丢弃），录制线程保留。"""
        if self.state.running and not self._pause.is_set():
            self._pause.set()
            self.state.paused = True
            self._emit()

    def resume(self) -> None:
        """继续：恢复抓取。"""
        if self.state.running and self._pause.is_set():
            self._pause.clear()
            self.state.paused = False
            self._emit()

    def _emit(self) -> None:
        if self._on_update:
            self._on_update(self.state)

    def _run(self) -> None:
        cfg = self.config
        avi = None
        mixer: Optional[_AudioMixer] = None
        fmt = AudioFormat(AUDIO_SAMPLE_RATE, AUDIO_CHANNELS, 16)
        try:
            out_dir = os.path.dirname(os.path.abspath(cfg.output_path))
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)

            # 音频源：系统声音（可选）+ 麦克风（可选），各自失败自动降级
            if cfg.record_audio or cfg.record_mic:
                mixer = _AudioMixer(fmt, mic_gain=cfg.mic_gain)
                if cfg.record_audio:
                    mixer.add("系统声音", None)
                if cfg.record_mic:
                    try:
                        import soundcard as sc
                        mic_name = str(sc.default_microphone().name)
                    except Exception as exc:
                        mic_name = None
                        mixer.failed.append(f"麦克风: 未找到设备 ({exc})")
                    if mic_name is not None:
                        mixer.add("麦克风", mic_name)

                self.state.audio_active = mixer.active
                self.state.mic_active = any("麦克风" in x for x in mixer.labels)
                self.state.sources = list(mixer.labels)
                failures = list(mixer.failed)
                if mixer.active:
                    self.state.audio_note = " + ".join(mixer.labels) + "（混音）"
                    if failures:
                        self.state.audio_note += "；部分音源不可用：" + "，".join(failures)
                else:
                    self.state.audio_note = "音频不可用，已静音录制：" + "，".join(failures)
                    mixer = None
            else:
                self.state.audio_note = "未启用音频"

            # 选区含负坐标（多显示器）时必须 all_screens=True 才能正确抓取
            neg = cfg.region is not None and (cfg.region[0] < 0 or cfg.region[1] < 0)
            grab_kw = {"all_screens": True} if neg else {}
            first = ImageGrab.grab(bbox=cfg.region, **grab_kw)
            w, h = first.size
            self.state.width, self.state.height = w, h
            w -= w & 1  # MJPEG 要求偶数宽高
            h -= h & 1
            if w <= 0 or h <= 0:
                raise ValueError("capture area is too small")

            if cfg.format == "mp4":
                avi = Mp4Encoder(cfg.output_path, cfg.fps,
                                audio=fmt if mixer else None,
                                crf=cfg.h264_crf)
            else:
                avi = MjpegAviWriter(cfg.output_path, w, h, cfg.fps,
                                     audio=fmt if mixer else None)
            interval = 1.0 / cfg.fps
            next_tick = time.perf_counter()

            while not self._stop.is_set():
                if cfg.max_frames and self.state.frames >= cfg.max_frames:
                    break

                # 暂停：丢弃累计音频避免缓冲膨胀，等待继续；不写新帧
                if self._pause.is_set():
                    if mixer:
                        mixer.drain()
                    if self._stop.wait(0.05):
                        break
                    continue

                img = ImageGrab.grab(bbox=cfg.region, **grab_kw).crop((0, 0, w, h)).convert("RGB")
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=cfg.quality)
                avi.add_frame(buf.getvalue())
                self.state.frames += 1

                # 交错：每写完一帧视频，把这段时间混合好的音频写成一个 01wb
                if mixer:
                    pcm = mixer.drain()
                    if pcm:
                        usable = len(pcm) - (len(pcm) % fmt.block_align)
                        if usable:
                            avi.add_audio(pcm[:usable])
                            self.state.audio_samples += usable // fmt.block_align

                if self.state.frames % max(1, cfg.fps // 2) == 0:
                    self._emit()

                next_tick += interval
                delay = next_tick - time.perf_counter()
                if delay > 0:
                    self._stop.wait(delay)
                else:
                    next_tick = time.perf_counter()

            # 收尾：停止采集并写尽剩余音频
            if mixer:
                tail = mixer.stop()
                if tail:
                    usable = len(tail) - (len(tail) % fmt.block_align)
                    if usable:
                        avi.add_audio(tail[:usable])
                        self.state.audio_samples += usable // fmt.block_align
                mixer = None

        except Exception as exc:
            self.state.error = f"{type(exc).__name__}: {exc}"
        finally:
            if mixer:
                try:
                    mixer.hard_stop()
                except Exception:
                    pass
            if avi is not None:
                try:
                    avi.close()
                except Exception as exc:
                    self.state.error = (self.state.error or "") + f"; close: {exc}"
            self.state.running = False
            self._emit()
