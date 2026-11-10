"""MP4 / H.264 压缩输出封装器。

复用系统自带的静态 ffmpeg（由 imageio-ffmpeg 提供，无需安装）：
  * 视频：每帧 JPEG 以 image2pipe 方式喂给 libx264，输出 H.264 / yuv420p
  * 音频：录制期写入临时 PCM，最后与视频一起 mux 成 MP4（AAC 编码）
  * 画质由 CRF 控制（越小越清晰、体积越大）

AVI（MJPEG+PCM）路径保持零编码器依赖；MP4 路径是可选的压缩输出。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from typing import Optional, Tuple

from .avi import AudioFormat


def ffmpeg_exe() -> str:
    """返回可用的 ffmpeg 可执行文件路径；找不到抛 RuntimeError。"""
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.isfile(exe):
            return exe
    except Exception:
        pass
    # 回退：系统 PATH 上的 ffmpeg
    found = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if found:
        return found
    raise RuntimeError(
        "未找到 ffmpeg（MP4 输出需要它；可通过 pip install imageio-ffmpeg 自动获取）"
    )


def has_mp4_support() -> bool:
    try:
        ffmpeg_exe()
        return True
    except RuntimeError:
        return False


class Mp4Encoder:
    """攒帧为一小段临时文件，结束时一次性调用 ffmpeg 生成 MP4。

    为避免大分辨率下管道死锁与原始 RGB 占用海量磁盘，视频采用
    各帧 JPEG 拼接的 image2pipe 形式（单临时文件），音频为 PCM 临时文件，
    最后由 ffmpeg 完成 H.264 编码 + AAC 编码 + MP4 封装。
    """

    def __init__(
        self,
        path: str,
        fps: int,
        audio: Optional[AudioFormat] = None,
        crf: int = 23,
    ) -> None:
        self.path = path
        self.fps = max(1, int(fps))
        self.audio = audio
        self.crf = max(0, min(51, int(crf)))
        self._tmp = tempfile.mkdtemp(prefix="oshen_mp4_")
        self._video = open(os.path.join(self._tmp, "video.mjpeg"), "wb")
        self._audio = (
            open(os.path.join(self._tmp, "audio.pcm"), "wb") if audio else None
        )
        self.frames = 0
        self.audio_samples = 0
        self.error: Optional[str] = None

    def add_frame(self, jpeg_bytes: bytes) -> None:
        if not jpeg_bytes:
            return
        self._video.write(jpeg_bytes)
        self.frames += 1

    def add_audio(self, pcm_bytes: bytes) -> None:
        if self._audio and pcm_bytes:
            self._audio.write(pcm_bytes)
            if self.audio:
                self.audio_samples += len(pcm_bytes) // self.audio.block_align

    def close(self) -> None:
        try:
            self._video.close()
            if self._audio:
                self._audio.close()
            self._mux()
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"
        finally:
            shutil.rmtree(self._tmp, ignore_errors=True)

    def _mux(self) -> None:
        if self.frames == 0:
            raise RuntimeError("没有写入任何视频帧")
        exe = ffmpeg_exe()
        cmd = [
            exe, "-y",
            "-f", "image2pipe", "-framerate", str(self.fps),
            "-i", os.path.join(self._tmp, "video.mjpeg"),
        ]
        if self._audio and self.audio:
            cmd += [
                "-f", "s16le",
                "-ar", str(self.audio.sample_rate),
                "-ac", str(self.audio.channels),
                "-i", os.path.join(self._tmp, "audio.pcm"),
            ]
        cmd += [
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-crf", str(self.crf),
            "-preset", "veryfast",
        ]
        if self._audio and self.audio:
            cmd += ["-c:a", "aac", "-b:a", "192k"]
        else:
            cmd += ["-an"]
        cmd += ["-movflags", "+faststart", self.path]

        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        _out, err = proc.communicate(timeout=600)
        if proc.returncode != 0:
            snippet = (err or b"").decode("utf-8", "replace")[-1500:]
            raise RuntimeError(f"ffmpeg 返回 {proc.returncode}: {snippet}")

    @property
    def bytes_written(self) -> int:
        try:
            return os.path.getsize(self.path)
        except OSError:
            return 0
