#!/usr/bin/env python3
"""o神套装-屏幕录制 — 入口。

    python main.py              # 启动 GUI
    python main.py --selftest   # 无头自测（打包版也可这样验证）
    pythonw main.pyw            # 无控制台，见 run.bat
"""

import os
import sys


def enable_dpi() -> None:
    """必须在创建任何 tkinter 窗口前调用，保证框选坐标 = 抓屏物理像素。"""
    from o_shen_recorder.dpi import enable_dpi_awareness
    enable_dpi_awareness()


def _selftest_mp4() -> str:
    """合成帧 + PCM，走 Mp4Encoder，校验 H.264 视频轨 + AAC 音频轨 + 压缩比。

    返回形如 "MP4:  PASS ..." 的单行报告（打包版无控制台，结果会写入文件）。
    """
    try:
        import io
        import math
        import struct
        import subprocess
        import tempfile

        from PIL import Image, ImageDraw

        from o_shen_recorder.avi import AudioFormat
        from o_shen_recorder.encoder import (
            Mp4Encoder, ffmpeg_exe, has_mp4_support,
        )

        if not has_mp4_support():
            return "MP4:  FAIL 未找到 ffmpeg（MP4 输出需要 imageio-ffmpeg）"

        w, h, fps, n = 320, 240, 10, 8
        af = AudioFormat(48000, 2, 16)

        def make_frame(idx: int) -> bytes:
            img = Image.new("RGB", (w, h), (24 + idx * 8, 60, 120))
            d = ImageDraw.Draw(img)
            d.rectangle((10 + idx * 4, 10, 110 + idx * 4, 60), fill=(240, 200, 40))
            d.text((14, 70), f"MP4 selftest {idx}", fill=(255, 255, 255))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=82)
            return buf.getvalue()

        def make_pcm(k: int) -> bytes:
            frames = bytearray()
            for i in range(4800):
                v = int(12000 * math.sin(2 * math.pi * 440 * i / af.sample_rate + k))
                frames += struct.pack("<hh", v, v)
            return bytes(frames)

        mp4 = os.path.join(tempfile.gettempdir(), "oshen_exe_selftest.mp4")
        enc = Mp4Encoder(mp4, fps=fps, audio=af, crf=23)
        for i in range(n):
            enc.add_frame(make_frame(i))
            enc.add_audio(make_pcm(i))
        enc.close()
        if enc.error:
            return f"MP4:  FAIL 编码错误 {enc.error}"

        if not (os.path.isfile(mp4) and os.path.getsize(mp4) > 0):
            return "MP4:  FAIL 未生成 MP4 文件"

        # 用 ffmpeg 回读校验轨类型
        probe = subprocess.run([ffmpeg_exe(), "-hide_banner", "-i", mp4],
                               capture_output=True, text=True).stderr
        has_h264 = "Video: h264" in probe
        has_aac = "Audio: aac" in probe
        ok = has_h264 and has_aac
        detail = (f"bytes={os.path.getsize(mp4)} "
                  f"h264={has_h264} aac={has_aac}")
        if os.path.isfile(mp4):
            os.remove(mp4)
        return f"MP4:  {'PASS' if ok else 'FAIL'} {detail}"
    except Exception as exc:
        return f"MP4:  FAIL exception={type(exc).__name__}: {exc}"


def main() -> int:
    if "--selftest" in sys.argv:
        # --windowed 版没有控制台，结果写入文件；路径可由第二个参数指定。
        import os
        import tempfile
        import time
        from o_shen_recorder.avi import probe_avi
        from o_shen_recorder.recorder import ScreenRecorder, RecorderConfig

        report = (sys.argv[sys.argv.index("--selftest") + 1]
                  if len(sys.argv) > sys.argv.index("--selftest") + 1
                  and not sys.argv[sys.argv.index("--selftest") + 1].startswith("-")
                  else os.path.join(tempfile.gettempdir(), "oshen_selftest.txt"))

        lines = []
        ok_all = True

        # ---- 1) AVI 实时录制（视频 + 音频双流） ----
        out = os.path.join(tempfile.gettempdir(), "oshen_exe_selftest.avi")
        try:
            rec = ScreenRecorder(RecorderConfig(output_path=out, fps=5,
                                                quality=70, max_frames=5,
                                                record_audio=True,
                                                record_mic=True))
            rec.start()
            while rec.state.running:
                time.sleep(0.1)
            st = rec.state
            if st.error:
                ok = False
                detail = f"error={st.error}"
            else:
                info = probe_avi(out)
                ok = (info["streams"] == 2
                      and info["movi_video_frames"] == 5
                      and info["movi_audio_chunks"] >= 1
                      and info["avih_total_frames"] == 5
                      and info["idx1_entries"] == info["movi_video_frames"] + info["movi_audio_chunks"]
                      and st.width > 0 and st.height > 0
                      and st.audio_active)
                detail = (f"frames={st.frames} size={st.width}x{st.height} "
                          f"streams={info['streams']} "
                          f"audio_chunks={info['movi_audio_chunks']} "
                          f"samples={st.audio_samples} "
                          f"sources={'+'.join(st.sources)} mic={st.mic_active} "
                          f"idx={info['idx1_entries']} bytes={info['bytes']}")
            if not ok:
                ok_all = False
            lines.append(f"AVI:  {'PASS' if ok else 'FAIL'} {detail}")
        except Exception as exc:
            ok_all = False
            lines.append(f"AVI:  FAIL exception={type(exc).__name__}: {exc}")
        finally:
            if os.path.isfile(out):
                os.remove(out)

        # ---- 2) MP4 / H.264 压缩输出（合成帧 + PCM，无需音频设备） ----
        mp4_line = _selftest_mp4()
        lines.append(mp4_line)
        if "FAIL" in mp4_line:
            ok_all = False

        result = ("\n".join(lines) + "\n"
                  + ("OVERALL: PASS" if ok_all else "OVERALL: FAIL") + "\n")
        with open(report, "w", encoding="utf-8") as f:
            f.write(result)
        return 0 if ok_all else 1

    enable_dpi()
    from o_shen_recorder.ui import main as ui_main
    ui_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
