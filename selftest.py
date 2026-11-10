#!/usr/bin/env python3
"""无头自测：生成含音视频双流的 AVI，逐层校验 RIFF/AVI 结构与索引一致性。

    python selftest.py
不依赖 GUI，也不需要人工交互。
"""

from __future__ import annotations

import io
import os
import struct
import tempfile
import time

from PIL import Image, ImageDraw, ImageGrab

from o_shen_recorder.app_info import APP_NAME, VERSION
from o_shen_recorder.avi import AudioFormat, MjpegAviWriter, probe_avi
from o_shen_recorder.region_selector import normalize_box, enum_top_windows, _window_at_point
from o_shen_recorder.ui import fmt_code
from o_shen_recorder.recorder import _AudioMixer, _AudioSource, MIX_GAIN
from o_shen_recorder.encoder import Mp4Encoder, has_mp4_support, ffmpeg_exe


def make_frame(idx: int, size: tuple[int, int]) -> bytes:
    img = Image.new("RGB", size, (24 + idx * 6, 60, 120))
    d = ImageDraw.Draw(img)
    d.rectangle((10 + idx * 4, 10, 110 + idx * 4, 60), fill=(240, 200, 40))
    # 默认位图字体仅支持 latin-1
    d.text((14, 70), f"OShen Recorder {VERSION} frame {idx}", fill=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=82)
    return buf.getvalue()


def make_pcm(n_samples: int, af: AudioFormat) -> bytes:
    """合成 440Hz 正弦 PCM，确保音频轨有真实数据。"""
    import math
    frames = bytearray()
    for i in range(n_samples):
        v = int(12000 * math.sin(2 * math.pi * 440 * i / af.sample_rate))
        frames += struct.pack("<hh", v, v)  # 2ch int16
    return bytes(frames)


def check(cond: bool, label: str) -> bool:
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}")
    return cond


def main() -> int:
    ok = True
    print(f"selftest: {APP_NAME} {VERSION} (video + audio)")
    print("-" * 64)

    try:
        shot = ImageGrab.grab()
        ok &= check(shot.size[0] > 0 and shot.size[1] > 0,
                    f"屏幕抓取可用 ({shot.size[0]}x{shot.size[1]})")
    except Exception as exc:
        ok &= check(False, f"屏幕抓取失败: {exc}")
        return 1

    w, h, fps, n = 320, 240, 10, 12
    af = AudioFormat(48000, 2, 16)
    path = os.path.join(tempfile.gettempdir(), "oshen_selftest.avi")

    # 交错写入：每帧视频后跟一段音频
    with MjpegAviWriter(path, w, h, fps, audio=af) as avi:
        for i in range(n):
            avi.add_frame(make_frame(i, (w, h)))
            avi.add_audio(make_pcm(4800, af))  # 0.1s @48kHz = 1 frame @10fps
    print("-" * 64)

    info = probe_avi(path)
    vids = [s for s in info["strh"] if s["type"] == "vids"]
    ok &= check(bool(vids) and vids[0]["handler"] == b"MJPG",
                "视频流为 MJPG")
    ok &= check(info["streams"] == 2, f"avih.dwStreams = {info['streams']} (期望 2)")
    ok &= check(info["width"] == w and info["height"] == h,
                f"尺寸 {info['width']}x{info['height']} (期望 {w}x{h})")
    ok &= check(info["movi_video_frames"] == n,
                f"movi 视频帧数 {info['movi_video_frames']} (期望 {n})")
    ok &= check(info["movi_audio_chunks"] == n,
                f"movi 音频块数 {info['movi_audio_chunks']} (期望 {n})")
    ok &= check(info["avih_total_frames"] == n,
                f"avih.dwTotalFrames {info['avih_total_frames']} (期望 {n})")
    ok &= check(info["idx1_entries"] == 2 * n,
                f"idx1 条目 {info['idx1_entries']} (期望 {2 * n})")
    ok &= check(all(s > 0 for s in info["video_sizes"]),
                f"每帧 JPEG 完整 (最小 {min(info['video_sizes'])} B)")
    ok &= check(all(s > 0 and s % af.block_align == 0 for s in info["audio_sizes"]),
                f"每段 PCM 长度合规 (最小 {min(info['audio_sizes'])} B)")

    # 流头校验
    types = [s["type"] for s in info["strh"]]
    ok &= check("vids" in types and "auds" in types, f"两种流头: {types}")
    for s in info["strh"]:
        if s["type"] == "vids":
            ok &= check(s["rate"] == fps, f"视频 strh.dwRate = {s['rate']} (期望 {fps})")
            ok &= check(s["length"] == n, f"视频 strh.dwLength = {s['length']} (期望 {n})")
        elif s["type"] == "auds":
            ok &= check(s["rate"] == af.avg_bytes_per_sec,
                        f"音频 strh.dwRate = {s['rate']} (期望 {af.avg_bytes_per_sec})")
            ok &= check(s["length"] == n * 4800,
                        f"音频 strh.dwLength = {s['length']} 采样帧 (期望 {n * 4800})")
            ok &= check(s["sample_size"] == af.block_align,
                        f"音频 dwSampleSize = {s['sample_size']} (期望 {af.block_align})")
            # strf = WAVEFORMATEX
            off = s["strf_offset"]
            blob = open(path, "rb").read()
            tag, ch, sr, abps, ba, bits, cbsize = struct.unpack_from("<HHIIHHH", blob, off)
            ok &= check((tag, ch, sr, bits) == (1, 2, 48000, 16),
                        f"WAVEFORMATEX PCM {ch}ch {sr}Hz {bits}bit")

    # 从 AVI 抽第一帧 JPEG 真实解码
    with open(path, "rb") as f:
        blob = f.read()
    pos = blob.find(b"00dc")
    if pos >= 0:
        size = struct.unpack_from("<I", blob, pos + 4)[0]
        jpeg = blob[pos + 8: pos + 8 + size]
        decoded = Image.open(io.BytesIO(jpeg)).convert("RGB")
        ok &= check(decoded.size == (w, h), f"AVI 内 JPEG 可解码 {decoded.size}")
    else:
        ok &= check(False, "未找到 00dc 帧")

    os.remove(path)
    print("-" * 64)

    # 鼠标框选：normalize_box 处理反向拖拽、过小选区、偶数对齐
    print("鼠标框选 (normalize_box):")
    ok &= check(normalize_box(100, 100, 500, 300) == (100, 100, 500, 300),
                "正向拖拽 (100,100)-(500,300)")
    ok &= check(normalize_box(500, 300, 100, 100) == (100, 100, 500, 300),
                "反向拖拽自动规整")
    ok &= check(normalize_box(0, 0, 101, 201) == (0, 0, 100, 200),
                "奇数宽高对齐为偶数 (101x201 -> 100x200)")
    ok &= check(normalize_box(10, 10, 15, 15) is None,
                "过小选区 (<8px) 返回 None")

    # 输出格式下拉文案 -> RecorderConfig 规范值（防回归：GUI 曾误传整段文案导致录制失败）
    ok &= check(fmt_code("AVI (无损 MJPEG)") == "avi",
                "格式文案映射 AVI -> avi")
    ok &= check(fmt_code("MP4 (H.264 压缩)") == "mp4",
                "格式文案映射 MP4 -> mp4")

    # 窗口捕获：枚举顶层窗口 + 命中测试
    wins = enum_top_windows()
    ok &= check(len(wins) > 0, f"枚举到 {len(wins)} 个顶层窗口")
    ok &= check(all(len(w) == 6 and w[1] < w[3] and w[2] < w[4] for w in wins),
                "每个窗口有合法矩形 (left<right, top<bottom)")
    if wins:
        cx = (wins[0][1] + wins[0][3]) // 2
        cy = (wins[0][2] + wins[0][4]) // 2
        hit = _window_at_point(wins, cx, cy)
        ok &= check(hit is not None, "命中测试能找到点所在的窗口")

    print("-" * 64)
    print(f"文件大小 {info['bytes']} B（{n} 帧 + {n} 段音频 / {w}x{h}）")
    print("RESULT:", "PASS" if ok else "FAIL")

    # ---- MP4 / H.264 压缩输出 ----
    print("-" * 64)
    print("MP4 / H.264 输出:")
    if not has_mp4_support():
        ok &= check(False, "未安装 ffmpeg（MP4 输出需要 imageio-ffmpeg）")
        print("RESULT:", "PASS" if ok else "FAIL")
        return 0 if ok else 1

    ok &= check(True, f"ffmpeg 可用 ({os.path.basename(ffmpeg_exe())})")

    mp4 = os.path.join(tempfile.gettempdir(), "oshen_selftest.mp4")
    enc = Mp4Encoder(mp4, fps=10, audio=af, crf=23)
    for i in range(n):
        enc.add_frame(make_frame(i, (w, h)))
        enc.add_audio(make_pcm(4800, af))
    enc.close()
    ok &= check(enc.error is None, f"编码无错误 ({enc.error})")
    ok &= check(os.path.isfile(mp4) and os.path.getsize(mp4) > 0,
                f"生成 MP4 ({os.path.getsize(mp4)} B)")
    # 用 ffmpeg 回读校验轨：H.264 视频 + AAC 音频
    import subprocess
    probe = subprocess.run([ffmpeg_exe(), "-hide_banner", "-i", mp4],
                           capture_output=True, text=True).stderr
    ok &= check("Video: h264" in probe, "视频轨为 H.264")
    ok &= check("Audio: aac" in probe, "音频轨为 AAC")
    ok &= check("Duration" in probe, "MP4 含时长信息")
    # MP4 体积应明显小于等效 AVI（压缩生效）
    ok &= check(os.path.getsize(mp4) < info["bytes"] // 3,
                f"压缩生效：MP4 {os.path.getsize(mp4)} B < AVI {info['bytes']} B 的 1/3")
    try:
        os.remove(mp4)
    except OSError:
        pass

    # 暂停 / 继续（录制线程保留，不写新帧）
    from o_shen_recorder.recorder import ScreenRecorder, RecorderConfig
    pout = os.path.join(tempfile.gettempdir(), "oshen_pause_test.avi")
    pcfg = RecorderConfig(output_path=pout, fps=10, quality=80,
                         region=(0, 0, 120, 90), record_audio=False,
                         record_mic=False, max_frames=40)
    prec = ScreenRecorder(pcfg)
    prec.start()
    time.sleep(0.3)
    prec.pause()
    ok &= check(prec.state.paused, "pause() 置 paused=True")
    f_pause = prec.state.frames
    time.sleep(0.3)
    prec.resume()
    ok &= check(not prec.state.paused, "resume() 清 paused")
    time.sleep(0.3)
    prec.stop()
    ok &= check(os.path.isfile(pout) and prec.state.frames > f_pause,
                "暂停/继续后仍能产出更多帧与文件")

    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
