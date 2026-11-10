"""手写 RIFF/AVI 封装器 —— 纯标准库，不依赖 ffmpeg / OpenCV。

支持两种流：
  * 视频：Motion-JPEG（每帧一张独立 JPEG，无需视频编码器）
  * 音频（可选）：未压缩 PCM（WAVEFORMATEX）

    RIFF <size> 'AVI '
      LIST <size> 'hdrl'
        avih  56B  AVIMAINHEADER
        LIST <size> 'strl'   视频流: strh('vids'/'MJPG') + strf(BITMAPINFOHEADER)
        LIST <size> 'strl'   音频流: strh('auds')       + strf(WAVEFORMATEX)  [可选]
      LIST <size> 'movi'
        '00dc' <JPEG>  '01wb' <PCM>  ...   (按时间交错)
      idx1 <size> (16B x N)

录制结束时回填所有长度 / 帧数 / 采样数字段。
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import BinaryIO, List, Optional, Tuple

AVIF_HASINDEX = 0x00000010
AVIIF_KEYFRAME = 0x00000010
VIDEO_CHUNK_ID = b"00dc"
AUDIO_CHUNK_ID = b"01wb"


@dataclass(frozen=True)
class AudioFormat:
    """AVI 音频流格式（PCM）。"""
    sample_rate: int = 48000
    channels: int = 2
    bits_per_sample: int = 16

    @property
    def block_align(self) -> int:
        return self.channels * self.bits_per_sample // 8

    @property
    def avg_bytes_per_sec(self) -> int:
        return self.sample_rate * self.block_align


def _chunk(fourcc: bytes, payload: bytes) -> bytes:
    """写一个 RIFF chunk；size 不含补齐字节，奇数长度补 1 字节 0。"""
    out = fourcc + struct.pack("<I", len(payload)) + payload
    if len(payload) & 1:
        out += b"\x00"
    return out


class MjpegAviWriter:
    """把 JPEG 帧（及可选 PCM 音频）写成 .avi 文件。

        with MjpegAviWriter(path, w, h, fps, audio=AudioFormat()) as avi:
            avi.add_frame(jpeg_bytes)
            avi.add_audio(pcm_bytes)
    """

    def __init__(
        self,
        path: str,
        width: int,
        height: int,
        fps: int,
        audio: Optional[AudioFormat] = None,
    ) -> None:
        if width <= 0 or height <= 0 or fps <= 0:
            raise ValueError("width/height/fps must be positive")
        self.width = width
        self.height = height
        self.fps = fps
        self.audio = audio
        self._f: BinaryIO = open(path, "wb")
        self._video_frames = 0
        self._audio_samples = 0
        self._max_video_size = 0
        self._max_audio_size = 0
        self._index: List[Tuple[bytes, int, int]] = []  # (ckid, offset, size)
        self._closed = False

        f = self._f
        f.write(b"RIFF" + struct.pack("<I", 0) + b"AVI ")

        # ---------------- hdrl ----------------
        hdrl_start = f.tell()
        f.write(b"LIST" + struct.pack("<I", 0) + b"hdrl")

        # avih
        self._avih_pos = f.tell()
        micro_sec = int(1_000_000 / fps)
        avih = struct.pack(
            "<14I",
            micro_sec,
            0,                 # dwMaxBytesPerSec   (回填)
            0,                 # dwPaddingGranularity
            AVIF_HASINDEX,
            0,                 # dwTotalFrames      (回填)
            0,                 # dwInitialFrames
            2 if audio else 1, # dwStreams
            0,                 # dwSuggestedBufferSize (回填)
            width,
            height,
            0, 0, 0, 0,
        )
        f.write(_chunk(b"avih", avih))

        # ---------------- strl (video) ----------------
        self._strh_video_pos = self._write_strl_video()

        # ---------------- strl (audio) ----------------
        self._strh_audio_pos: Optional[int] = None
        if audio is not None:
            self._strh_audio_pos = self._write_strl_audio(audio)

        hdrl_end = f.tell()
        self._patch_u32(hdrl_start + 4, hdrl_end - hdrl_start - 8)

        # ---------------- movi ----------------
        self._movi_start = f.tell()
        f.write(b"LIST" + struct.pack("<I", 0) + b"movi")
        self._movi_data_start = f.tell()

    # ---- header helpers ----
    def _write_strl_video(self) -> int:
        f = self._f
        start = f.tell()
        f.write(b"LIST" + struct.pack("<I", 0) + b"strl")

        strh_pos = f.tell()
        strh = struct.pack(
            "<4s4sIHHIIIIIIIIhhhh",
            b"vids", b"MJPG",
            0, 0, 0,
            0,                 # dwInitialFrames
            1,                 # dwScale
            self.fps,          # dwRate
            0,                 # dwStart
            0,                 # dwLength (回填)
            0,                 # dwSuggestedBufferSize (回填)
            0xFFFFFFFF,
            0,                 # dwSampleSize
            0, 0, self.width, self.height,
        )
        assert len(strh) == 56, len(strh)
        f.write(_chunk(b"strh", strh))

        strf = struct.pack(
            "<IiiHH4sIiiII",
            40, self.width, self.height, 1, 24, b"MJPG",
            self.width * self.height * 3, 0, 0, 0, 0,
        )
        assert len(strf) == 40, len(strf)
        f.write(_chunk(b"strf", strf))

        end = f.tell()
        self._patch_u32(start + 4, end - start - 8)
        return strh_pos

    def _write_strl_audio(self, a: AudioFormat) -> int:
        f = self._f
        start = f.tell()
        f.write(b"LIST" + struct.pack("<I", 0) + b"strl")

        strh_pos = f.tell()
        strh = struct.pack(
            "<4s4sIHHIIIIIIIIhhhh",
            b"auds", b"\x00\x00\x00\x00",
            0, 0, 0,
            0,                       # dwInitialFrames
            a.block_align,           # dwScale  = bytes per sample frame
            a.avg_bytes_per_sec,     # dwRate
            0,                       # dwStart
            0,                       # dwLength = total sample frames (回填)
            0,                       # dwSuggestedBufferSize (回填)
            0xFFFFFFFF,
            a.block_align,           # dwSampleSize
            0, 0, 0, 0,
        )
        assert len(strh) == 56, len(strh)
        f.write(_chunk(b"strh", strh))

        # WAVEFORMATEX (18 bytes, PCM)
        strf = struct.pack(
            "<HHIIHHH",
            1,                   # wFormatTag = WAVE_FORMAT_PCM
            a.channels,
            a.sample_rate,
            a.avg_bytes_per_sec,
            a.block_align,
            a.bits_per_sample,
            0,                   # cbSize
        )
        assert len(strf) == 18, len(strf)
        f.write(_chunk(b"strf", strf))

        end = f.tell()
        self._patch_u32(start + 4, end - start - 8)
        return strh_pos

    def _patch_u32(self, offset: int, value: int) -> None:
        """保存并恢复当前位置：回填长度字段不能改变后续写入点。"""
        saved = self._f.tell()
        self._f.flush()
        self._f.seek(offset)
        self._f.write(struct.pack("<I", value & 0xFFFFFFFF))
        self._f.flush()
        self._f.seek(saved)

    # ---- data ----
    def _write_chunk(self, ckid: bytes, payload: bytes) -> None:
        offset = self._f.tell() - self._movi_data_start + 4
        self._f.write(_chunk(ckid, payload))
        self._index.append((ckid, offset, len(payload)))

    def add_frame(self, jpeg: bytes) -> None:
        if self._closed:
            raise RuntimeError("writer already closed")
        if not (jpeg[:2] == b"\xff\xd8" and jpeg[-2:] == b"\xff\xd9"):
            raise ValueError("frame is not a complete JPEG (SOI/EOI missing)")
        self._write_chunk(VIDEO_CHUNK_ID, jpeg)
        self._video_frames += 1
        self._max_video_size = max(self._max_video_size, len(jpeg))

    def add_audio(self, pcm: bytes) -> None:
        """追加一段 PCM；长度应为 block_align 的整数倍。"""
        if self._closed:
            raise RuntimeError("writer already closed")
        if self.audio is None:
            raise RuntimeError("writer has no audio stream")
        if not pcm or len(pcm) % self.audio.block_align:
            raise ValueError("pcm length must be a positive multiple of block_align")
        self._write_chunk(AUDIO_CHUNK_ID, pcm)
        self._audio_samples += len(pcm) // self.audio.block_align
        self._max_audio_size = max(self._max_audio_size, len(pcm))

    # ---- finalize ----
    def close(self) -> None:
        if self._closed:
            return
        f = self._f
        movi_end = f.tell()
        self._patch_u32(self._movi_start + 4, movi_end - self._movi_start - 8)

        idx = bytearray()
        for ckid, offset, size in self._index:
            idx += ckid + struct.pack("<III", AVIIF_KEYFRAME, offset, size)
        f.seek(0, 2)
        f.write(_chunk(b"idx1", bytes(idx)))

        file_end = f.tell()
        self._patch_u32(4, file_end - 8)

        max_chunk = max(self._max_video_size, self._max_audio_size)
        avih_data = self._avih_pos + 8
        self._patch_u32(avih_data + 4, max_chunk * self.fps)
        self._patch_u32(avih_data + 16, self._video_frames)
        self._patch_u32(avih_data + 28, max_chunk)

        strh_v = self._strh_video_pos + 8
        self._patch_u32(strh_v + 32, self._video_frames)
        self._patch_u32(strh_v + 36, self._max_video_size)

        if self._strh_audio_pos is not None:
            strh_a = self._strh_audio_pos + 8
            self._patch_u32(strh_a + 32, self._audio_samples)
            self._patch_u32(strh_a + 36, self._max_audio_size)

        f.flush()
        f.close()
        self._closed = True

    def __enter__(self) -> "MjpegAviWriter":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    @property
    def video_frames(self) -> int:
        return self._video_frames

    @property
    def audio_samples(self) -> int:
        return self._audio_samples


# ---------------------------------------------------------------------------
# 结构校验（自测用）
# ---------------------------------------------------------------------------
def _walk_chunks(b: bytes, start: int, end: int):
    i = start
    while i + 8 <= end:
        fourcc = b[i : i + 4]
        size = struct.unpack_from("<I", b, i + 4)[0]
        data = i + 8
        yield fourcc, data, size
        i = data + size + (size & 1)


def probe_avi(path: str) -> dict:
    """按 RIFF 结构遍历并校验 AVI，返回结构摘要（支持单流 / 双流）。"""
    b = open(path, "rb").read()
    if b[:4] != b"RIFF" or b[8:12] != b"AVI ":
        raise ValueError("not a RIFF/AVI file")
    riff_size = struct.unpack_from("<I", b, 4)[0]
    if riff_size != len(b) - 8:
        raise ValueError(f"RIFF size mismatch: {riff_size} vs {len(b) - 8}")

    info: dict = {"bytes": len(b)}
    video_sizes: List[int] = []
    audio_sizes: List[int] = []
    idx_entries = 0
    strh_list: List[dict] = []

    for fourcc, data, size in _walk_chunks(b, 12, len(b)):
        if fourcc == b"LIST" and b[data : data + 4] == b"hdrl":
            for sub, d2, s2 in _walk_chunks(b, data + 4, data + size):
                if sub == b"avih":
                    info["avih_total_frames"] = struct.unpack_from("<I", b, d2 + 16)[0]
                    info["streams"] = struct.unpack_from("<I", b, d2 + 24)[0]
                    info["width"] = struct.unpack_from("<I", b, d2 + 32)[0]
                    info["height"] = struct.unpack_from("<I", b, d2 + 36)[0]
                elif sub == b"LIST" and b[d2 : d2 + 4] == b"strl":
                    sh: dict = {}
                    for s3, d3, s3sz in _walk_chunks(b, d2 + 4, d2 + s2):
                        if s3 == b"strh":
                            sh["type"] = b[d3 : d3 + 4].decode("latin1")
                            sh["handler"] = b[d3 + 4 : d3 + 8]
                            sh["scale"] = struct.unpack_from("<I", b, d3 + 20)[0]
                            sh["rate"] = struct.unpack_from("<I", b, d3 + 24)[0]
                            sh["length"] = struct.unpack_from("<I", b, d3 + 32)[0]
                            sh["sample_size"] = struct.unpack_from("<I", b, d3 + 44)[0]
                        elif s3 == b"strf":
                            sh["strf_size"] = s3sz
                            sh["strf_offset"] = d3
                    strh_list.append(sh)
        elif fourcc == b"LIST" and b[data : data + 4] == b"movi":
            for fc, d2, s2 in _walk_chunks(b, data + 4, data + size):
                if fc == VIDEO_CHUNK_ID:
                    jpeg = b[d2 : d2 + s2]
                    if jpeg[:2] != b"\xff\xd8" or jpeg[-2:] != b"\xff\xd9":
                        raise ValueError(f"video frame {len(video_sizes)} is not a complete JPEG")
                    video_sizes.append(s2)
                elif fc == AUDIO_CHUNK_ID:
                    audio_sizes.append(s2)
        elif fourcc == b"idx1":
            idx_entries = size // 16
            ckids = []
            for n in range(idx_entries):
                off = data + n * 16
                ckid = b[off : off + 4]
                flags, chunk_off, chunk_len = struct.unpack_from("<III", b, off + 4)
                if ckid not in (VIDEO_CHUNK_ID, AUDIO_CHUNK_ID) or not (flags & AVIIF_KEYFRAME):
                    raise ValueError(f"bad idx1 entry {n}")
                ckids.append((ckid, chunk_len))
            # 顺序与长度必须与 movi 中的 chunk 一致
            # 按 movi 里实际交错顺序重建期望的 (ckid, size) 序列
            expected = []
            vi = ai = 0
            for ckid, _l in ckids:
                if ckid == VIDEO_CHUNK_ID:
                    expected.append((ckid, video_sizes[vi])); vi += 1
                else:
                    expected.append((ckid, audio_sizes[ai])); ai += 1
            if ckids != expected[:len(ckids)]:
                raise ValueError("idx1 does not match movi chunks")

    info["movi_video_frames"] = len(video_sizes)
    info["movi_audio_chunks"] = len(audio_sizes)
    info["idx1_entries"] = idx_entries
    info["video_sizes"] = video_sizes
    info["audio_sizes"] = audio_sizes
    info["strh"] = strh_list
    return info
