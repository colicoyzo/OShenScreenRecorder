# 贡献与推送说明（CONTRIBUTING）

> English version: [CONTRIBUTING.en.md](CONTRIBUTING.en.md)

本项目 `o神套装-屏幕录制 / OShen Screen Recorder` 为自有原创实现的 Windows 屏幕录制工具。
欢迎提交 Issue 与 PR。以下为本地开发、自测、打包与推送到 `github.com/colicoyzo/OShenScreenRecorder` 的标准流程。

> 当前版本：**V0.5**。版本号定义于 `o_shen_recorder/app_info.py` 的 `VERSION`（与 `VERSION_TUPLE`、`FEATURE_POLICY` 一并维护）；
> 修改用户可见行为（快捷键、默认参数、窗体行为等）时，请同步更新 `VERSION` 与 `README.md`，保持三者一致。

---

## 1. 环境准备

- **Python 3.9+**（tkinter 为标准库自带，无需额外安装）
- 源码运行依赖：

  ```bat
  pip install Pillow soundcard imageio-ffmpeg
  ```

- 打包（生成 exe）依赖 PyInstaller，由 `build_exe.bat` 在隔离 venv 中自动安装，**无需手动预装**。

---

## 2. 本地运行与自测

```bat
python main.py              :: 启动主界面（或双击 run.bat，用 pythonw 无控制台）
python selftest.py          :: 无头自测，全部 PASS 即环境正常
```

- `selftest.py` 会真实抓屏并采集系统声音 + 麦克风若干帧，校验 AVI 双流与 MP4/H.264 结构，
  共 **37 项**检查，全 PASS 即正常。
- 修改 `recorder.py` / `avi.py` / `encoder.py` / `region_selector.py` / `ui.py` / `hotkey.py` 后，
  **务必先跑一遍 `python selftest.py`** 确认无回归。

---

## 3. 打包验证

```bat
build_exe.bat               :: 在 .buildenv\ 隔离 venv 中打包成 onedir
dist\OShenScreenRecorder\OShenScreenRecorder.exe --selftest   :: 验证打包产物
```

- 产物位于 `dist\OShenScreenRecorder\`（已写入 `.gitignore`，**不纳入版本库**）。
- 修改打包相关（入口、`build_exe.bat`、图标）后，应重新打包并跑 `--selftest`。

---

## 4. 提交规范

- 提交信息用中文或英文均可，建议一句概括 + 多行要点说明改动。
- 不应提交的内容（已在 `.gitignore` 排除）：`dist/`、`build/`、`.buildenv/`、
  `recordings/`、`build_log.txt`、`*.spec`、`__pycache__/`、`*.py[cod]`。
- 新增依赖请同步更新对应 `pip install` 说明（README 的「运行」小节或本文件第 1 节）。
- 若改动用户可见行为（如快捷键、默认参数、窗体行为），请同步更新 `README.md` 与
  `o_shen_recorder/app_info.py` 的 `VERSION` / `FEATURE_POLICY`，保持版本号一致。

---

## 5. 推送到 GitHub

本仓库默认分支为 **`main`**，远程已配置为 SSH 地址
`git@github.com:colicoyzo/OShenScreenRecorder.git`。

### SSH 前置检查（首次推送前）

使用 SSH 推送前，需确保本机 **SSH 公钥已添加到 GitHub 账户**
（GitHub → Settings → SSH and GPG keys），并验证连通性：

```bat
ssh -T git@github.com
```

- 首次连接会提示确认主机指纹，输入 `yes` 即可；
- 成功会显示 `Hi <用户名>! You've successfully authenticated...`；
- 若提示 `Permission denied (publickey)`，说明尚未配置 SSH key：
  先生成（`ssh-keygen -t ed25519 -C "你的邮箱"`），再把
  `~/.ssh/id_ed25519.pub` 的内容添加到 GitHub 账户。

确认连通后推送：

```bat
cd d:\AIspace\o-luping\oshen-recorder
git push -u origin main
```

- 若远程仓库在网页端创建时已带有初始提交（如勾选了 README / LICENSE），
  `push` 会被拒绝（non-fast-forward）。此时先合并再推送：

  ```bat
  git pull --rebase origin main
  git push -u origin main
  ```

  仅在确认要用本地覆盖远端时，才使用 `git push -u origin main --force`。

- 推荐工作流：从 `main` 切出特性分支 → 提交 → `git push -u origin <分支>` → 开 PR 合入 `main`。
  直接推 `main` 也可，但请在推送前完成自测与 `--selftest`。

---

## 6. 报告问题

提交 Issue 时请尽量包含：

- 操作系统版本、缩放比例（DPI）、Python 版本
- 录制区域选择方式（全屏 / 鼠标框选 / 窗口捕获）、输出格式（AVI / MP4）
- 音频设置（系统声音 / 麦克风开关、麦克风增益）
- `python selftest.py` 的输出，或 `dist\...\OShenScreenRecorder.exe --selftest` 后
  `%TEMP%\oshen_selftest.txt` 的内容
- 复现步骤与期望行为

---

版权与许可：Copyright (C) 2026 o神套装。全部已实现功能免费开放使用；
未经授权不得将本项目用于商业再分发或声称原创。
