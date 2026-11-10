# o神套装-屏幕录制 · OShen Screen Recorder

> A from-scratch, fully self-owned Windows screen recorder. All features are free, with no VIP / payment / license check.

| Field | Value |
| --- | --- |
| Software | o神套装-屏幕录制 (OShen Screen Recorder) |
| Version | V0.5 |
| Copyright | Copyright (C) 2026 |
| Author / Org | o神套装 |
| License | All features free to use; all rights reserved (see `LICENSE`) |

By design this project has **no** "VIP unlock", "payment control", "license verification", or any feature gate — every implemented feature is available to everyone unconditionally, with no activation, login, or trial limit.

**Docs**: [Chinese (this file's counterpart)](README.md) · [English](README.en.md) · [Contributing (zh)](CONTRIBUTING.md) · [Contributing (en)](CONTRIBUTING.en.md) · [LICENSE](LICENSE)

---

## Features (V0.5)

**Capture region**
- Full-screen or selected-region recording
- **Mouse drag selection**: a transparent full-screen overlay; hold left button and drag to select; `Esc` / right-click cancels
- **Window capture**: press `W` inside the overlay to switch to window mode; hovering highlights the topmost window under the cursor and a single click selects that window's rectangle (taskbar / desktop shell windows are skipped automatically). Also available via the "窗口捕获" button on the main UI
- **Fullscreen quick button**: one click sets the region to full screen (clearing the region box also means full screen)

**Video & audio**
- Adjustable frame rate (1–30 fps) and JPEG quality (30–95)
- **Dual-source audio mixing**: system sound (WASAPI loopback) + microphone, independently toggleable; microphone gain adjustable 0–3×
- Multiple sources are captured independently, time-aligned by sample frames, then mixed and written; `tanh` soft-clipping avoids clipping on summation; a failed source auto-degrades
- Standard **AVI output: Motion-JPEG video + uncompressed PCM audio**, interleaved by time, openable by common players

**Output format (choose one)**
- `AVI`: MJPEG + PCM, **zero encoder dependency**, lossless but large
- `MP4`: **H.264 (yuv420p) + AAC** compression, much smaller (CRF 18–30 adjustable)

**Recording control (new in V0.5)**
- **Main window auto-minimizes on record start**, so it is not captured into the video
- **Global hotkey `Ctrl+Shift+Alt+Z` to pause / resume**: implemented via a Win32 global-hotkey thread, so it works even when the window is minimized (Tk key bindings stop working when minimized)
- **Window minimizes again after clicking "继续" (resume)**, keeping it out of the recording
- Live status: start / stop, real-time frame count and duration, audio status, output file size

**Misc**
- Original application icon (`.ico` drawn from scratch with Pillow via `make_icon.py`, embedded in the exe and title bar)
- **DPI aware**: the process declares Per-Monitor DPI Awareness so selection coordinates match `ImageGrab` physical pixels (verified at 125% scaling)

Tech stack: **Python 3.9 + tkinter + Pillow + soundcard**. The AVI container is hand-written by this project in `o_shen_recorder/avi.py` (full RIFF / `avih` / two `strl` / `strf` / `movi` / `idx1` field fill), **zero encoder dependency**. The MP4 path reuses a static `ffmpeg` (bundled by `imageio-ffmpeg`, no system install needed): each video frame's JPEG is encoded by libx264 and audio by AAC, then muxed into MP4.

> Scope note: AVI is large (example: 2560×1600 / 5 fps / 5 frames with audio ≈ 1.4 MB); MP4 under the same conditions is ≈ 24 KB (very high compression). No hardware acceleration, camera, or multi-monitor stitching. Microphone mixing is off by default; MP4 requires `imageio-ffmpeg` (bundled in the build).

## Main window layout

The main window (`580×560`, non-resizable) is organized into 5 titled group boxes:

| Group | Controls |
| --- | --- |
| **Output** | Output file entry + Browse button, format dropdown (AVI / MP4), format note, MP4 quality (CRF) slider |
| **Video & quality** | Frame rate (fps) spinbox, JPEG quality slider |
| **Recording region** | Region entry (x,y,w,h), fullscreen / drag-select / window-capture buttons, hint text |
| **Audio** | Record system sound (WASAPI loopback) checkbox, mix microphone checkbox, mic gain slider |
| **Recording control** | Start / Pause / Stop / About buttons, status text, progress bar |

Entries and sliders stretch within their group; the window auto-minimizes on record start and restores on stop.

## Keyboard shortcuts

| Action | Shortcut / Method |
| --- | --- |
| Start recording | "开始录制" button |
| Pause / resume | `Ctrl+Shift+Alt+Z` (global, works while minimized) |
| Stop recording | "停止录制" button |
| Cancel selection (in overlay) | `Esc` or right-click |
| Toggle window capture (in overlay) | `W` |

## Directory

```
oshen-recorder/
├── main.py                    entry point (with --selftest)
├── run.bat                    launch from source (pythonw, no console)
├── make_icon.py               generate the original icon assets/app.ico
├── build_exe.bat              package into an onedir standalone program
├── selftest.py                headless self-test: dual-stream AVI + MP4/H.264 validation
├── README.md                 Chinese documentation
├── README.en.md              English documentation
├── CONTRIBUTING.md           contribution & push guide (Chinese)
├── CONTRIBUTING.en.md        contribution & push guide (English)
├── LICENSE                   software license
├── assets/app.ico            original icon (7 sizes)
├── o_shen_recorder/
│   ├── __init__.py
│   ├── app_info.py           brand / version / copyright / no-paywall statement / asset path
│   ├── avi.py                hand-written AVI muxer (dual stream) + probe_avi validator
│   ├── encoder.py            MP4 / H.264 (ffmpeg) muxer
│   ├── recorder.py           capture thread + multi-source mix thread + interleaved write + pause/resume
│   ├── region_selector.py    mouse-drag / window-capture overlay + box normalization
│   ├── hotkey.py             Win32 global hotkey (Ctrl+Shift+Alt+Z pause/resume) thread
│   ├── dpi.py                DPI awareness (coordinate alignment)
│   └── ui.py                 tkinter UI
└── recordings/               default output folder (created at runtime, gitignored)
```

## Run

Double-click **`dist\OShenScreenRecorder\OShenScreenRecorder.exe`** (packaged build, no Python install needed).
Or from source:

```bat
run.bat                        :: or: python main.py
python selftest.py             :: headless self-test; all PASS means the environment is OK
```

Source run requires Python 3.9+ plus `Pillow`, `soundcard`, `imageio-ffmpeg`
(`pip install Pillow soundcard imageio-ffmpeg`). tkinter ships with the standard library.

## Build (onedir)

Double-click **`build_exe.bat`**. It will:

1. Create an isolated virtual environment `.buildenv\` (does not touch system Python);
2. Install PyInstaller + Pillow + soundcard + imageio-ffmpeg inside the venv;
3. Generate `assets/app.ico` if missing;
4. Package with `--onedir` (including `--collect-all soundcard` and `--collect-all imageio_ffmpeg`,
   the latter bundles the static ffmpeg so MP4 works out of the box), producing `dist\OShenScreenRecorder\`.

> Why a venv: the system Anaconda has an outdated `pathlib` backport (1.0.1) that PyInstaller refuses.
> The isolated venv does not, and does not alter the system. Why onedir: no per-launch extraction, faster
> startup; the cost is a directory output (≈ 77 MB / 1000+ files). The scripts are pure ASCII to avoid
> cmd's OEM codepage mangling Chinese comments.

Verify the packaged build:

```bat
dist\OShenScreenRecorder\OShenScreenRecorder.exe --selftest
```

It performs a headless real capture with system sound + microphone for several frames, builds a dual-stream
AVI and validates its structure; then synthesizes frames + PCM through `Mp4Encoder` to produce an MP4 and
validates the H.264 video track + AAC audio track. Both results are written to `%TEMP%\oshen_selftest.txt`
(a result-file path may also be passed as the second argument); `OVERALL: PASS` at the end means both paths pass.

## Self-test results (verified locally)

`python selftest.py` → **37 checks all PASS**, covering:

- AVI dual stream: `vids`/`auds` headers, `avih.dwStreams=2`, dimensions, frame rate, `dwTotalFrames`,
  video frame count, audio chunk count, `idx1` entry count, `WAVEFORMATEX` (PCM 2ch 48000Hz 16bit),
  each video frame is a complete decodable JPEG, each PCM segment length valid;
- Box normalization `normalize_box` (forward / reversed / odd-aligned / too-small);
- Window enumeration `enum_top_windows` (valid rects, hit-testing);
- Format-label mapping `fmt_code` (AVI→avi / MP4→mp4);
- **MP4 path**: ffmpeg available, MP4 produced, H.264 video track, AAC audio track, duration present,
  compressed size < 1/3 of the equivalent AVI;
- **Pause / resume**: `pause()` sets `paused=True` and freezes frame writes; `resume()` clears it and
  continues producing frames and file;
- **Window-minimize behavior**: after record start and after clicking "继续" (resume) the window enters
  `iconic` (minimized) state.

Packaged `--selftest`: `AVI: PASS` (real capture + system sound + mic dual stream),
`MP4: PASS` (H.264 + AAC), `OVERALL: PASS`.

GUI verified to launch with the V0.5 title, original icon, 5 group boxes (Output / Video & quality /
Recording region / Audio / Recording control), fullscreen / drag-select / window-capture buttons,
system-sound / microphone checkboxes, mic gain slider, format selector, MP4 quality (CRF),
pause button, and copyright info all present.

## Roadmap

- Multi-monitor stitching, recording preview, mouse-click highlight
- Optional: finer video-quality presets, WebM/VP9 output, hardware-accelerated encoding

---

Copyright (C) 2026 o神套装. This project is an original self-owned implementation; all implemented
features are free to use. Unauthorized commercial redistribution or claiming the work as your own original
is prohibited. See `LICENSE`.
