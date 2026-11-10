# Contributing & Push Guide

This project, `o神套装-屏幕录制 / OShen Screen Recorder`, is a from-scratch, self-owned
Windows screen recorder. Issues and PRs are welcome. Below is the standard workflow for local
development, self-testing, packaging, and pushing to
`github.com/colicoyzo/OShenScreenRecorder`.

> Current version: **V0.5**. The version is defined in `o_shen_recorder/app_info.py` as `VERSION`
> (maintained together with `VERSION_TUPLE` and `FEATURE_POLICY`). When changing user-visible behavior
> (hotkeys, defaults, window behavior, etc.), please update `VERSION` and `README.md` so all three stay consistent.

---

## 1. Environment setup

- **Python 3.9+** (tkinter ships with the standard library, no extra install)
- Source dependencies:

  ```bat
  pip install Pillow soundcard imageio-ffmpeg
  ```

- Packaging (exe build) needs PyInstaller, which `build_exe.bat` installs automatically into an
  isolated venv — **no manual pre-install required**.

---

## 2. Run & self-test locally

```bat
python main.py              :: launch the UI (or double-click run.bat, which uses pythonw, no console)
python selftest.py          :: headless self-test; all PASS means the environment is OK
```

- `selftest.py` performs a real screen capture with system sound + microphone for several frames and
  validates the AVI dual stream and MP4/H.264 structure — **37 checks**, all PASS means OK.
- After editing `recorder.py` / `avi.py` / `encoder.py` / `region_selector.py` / `ui.py` / `hotkey.py`,
  **always run `python selftest.py` first** to confirm no regression.

---

## 3. Build verification

```bat
build_exe.bat               :: package into onedir inside a .buildenv\ isolated venv
dist\OShenScreenRecorder\OShenScreenRecorder.exe --selftest   :: verify the packaged build
```

- Output is at `dist\OShenScreenRecorder\` (already in `.gitignore`, **not tracked**).
- After changing packaging-related code (entry point, `build_exe.bat`, icon), rebuild and run `--selftest`.

---

## 4. Commit guidelines

- Commit messages may be in Chinese or English; prefer one summary line + bullet points.
- Do **not** commit (excluded by `.gitignore`): `dist/`, `build/`, `.buildenv/`, `recordings/`,
  `build_log.txt`, `*.spec`, `__pycache__/`, `*.py[cod]`.
- When adding dependencies, update the `pip install` note (README "Run" section or §1 above).
- If you change user-visible behavior (hotkeys, defaults, window behavior), update `README.md` and
  `o_shen_recorder/app_info.py` (`VERSION` / `FEATURE_POLICY`) so the version stays consistent.

---

## 5. Push to GitHub

This repo's default branch is **`main`**; the remote is configured as the SSH URL
`git@github.com:colicoyzo/OShenScreenRecorder.git`.

### SSH pre-check (before first push)

Before pushing over SSH, make sure your machine's **SSH public key is added to your GitHub account**
(GitHub → Settings → SSH and GPG keys), and verify connectivity:

```bat
ssh -T git@github.com
```

- On first connect you'll be asked to confirm the host fingerprint — type `yes`;
- Success shows `Hi <username>! You've successfully authenticated...`;
- If you see `Permission denied (publickey)`, no SSH key is configured yet:
  generate one (`ssh-keygen -t ed25519 -C "your-email"`) and add the contents of
  `~/.ssh/id_ed25519.pub` to your GitHub account.

Once connectivity is confirmed, push:

```bat
cd d:\AIspace\o-luping\oshen-recorder
git push -u origin main
```

- If the remote repo was created on the web with an initial commit (e.g. a README / LICENSE was checked),
  `push` is rejected (non-fast-forward). Merge first:

  ```bat
  git pull --rebase origin main
  git push -u origin main
  ```

  Only use `git push -u origin main --force` when you intentionally want to overwrite the remote.
- Recommended workflow: branch off `main` → commit → `git push -u origin <branch>` → open a PR into `main`.
  Direct pushes to `main` are fine too, but please complete self-test and `--selftest` before pushing.

---

## 6. Reporting issues

When filing an Issue, please include:

- OS version, scaling (DPI), Python version
- Region selection method (fullscreen / mouse drag / window capture), output format (AVI / MP4)
- Audio settings (system sound / microphone toggles, mic gain)
- `python selftest.py` output, or the contents of `%TEMP%\oshen_selftest.txt` after
  `dist\...\OShenScreenRecorder.exe --selftest`
- Steps to reproduce and expected behavior

---

Copyright (C) 2026 o神套装. All implemented features are free to use; unauthorized commercial
redistribution or claiming the work as your own original is prohibited. See `LICENSE`.
