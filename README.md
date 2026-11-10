# o神套装-屏幕录制 · OShen Screen Recorder

> English version: [README.en.md](README.en.md)
> 一个从零自研、完全自有的 Windows 屏幕录制工具。全部功能免费开放，无 VIP / 付费 / 授权校验。

| 项 | 值 |
| --- | --- |
| 软件名称 | o神套装-屏幕录制 (OShen Screen Recorder) |
| 版本 | V0.5 |
| 版权 | Copyright (C) 2026 |
| 作者 / 组织 | o神套装 |
| 许可模式 | 全部功能免费开放，无 VIP / 付费 / 授权校验 |

本项目从设计上就不存在「开通 VIP」「付费控制」「授权校验」或任何功能闸门 ——
所有已实现功能对所有人无条件开放，无需激活、无需登录、无试用限制。

**文档索引**：[中文说明（本文）](README.md) · [英文说明](README.en.md) · [贡献与推送（中）](CONTRIBUTING.md) · [贡献与推送（英）](CONTRIBUTING.en.md) · [许可协议](LICENSE)

---

## 功能（V0.5）

**录制区域**
- 全屏或指定区域录制
- **鼠标拖拽框选**：透明全屏覆盖层，按住左键拖拽即选区，`Esc` / 右键取消
- **窗口捕获**：框选层内按 `W` 切换窗口模式，移动鼠标高亮其下的顶层窗口、单击即选中该窗口矩形（自动跳过任务栏 / 桌面外壳窗口）；也可在主界面点「窗口捕获」按钮
- **全屏快捷按钮**：一键将录制区域设为全屏（清空选区输入框即代表全屏）

**画面与音频**
- 可调帧率（1–30 fps）与 JPEG 质量（30–95）
- **音频双源混音**：系统声音（WASAPI loopback）+ 麦克风，可分别开关；麦克风音量 0–3× 可调
- 多音源独立采集、按采样帧对齐混合后写入，用 `tanh` 软限幅避免叠加削波；单路失败自动降级
- 输出标准 **AVI：Motion-JPEG 视频 + 未压缩 PCM 音频**，音视频按时间交错，可用常见播放器打开

**输出格式（二选一）**
- `AVI`：MJPEG + PCM，**零编码器依赖**，无损但体积大
- `MP4`：**H.264（yuv420p）+ AAC** 压缩输出，体积显著更小（CRF 18–30 可调）

**录制控制（V0.5 新增）**
- **开始录制后主窗体自动最小化**，避免自身被录进画面
- **全局热键 `Ctrl+Shift+Alt+Z` 暂停 / 继续**：通过 Win32 全局热键线程实现，即使窗体已最小化也能响应（Tk 键盘绑定在最小化时失效）
- **点击「继续」后窗体再次最小化**，保持录制期间不被录进画面
- 开始 / 停止、实时帧数与时长、音频状态、输出文件大小回显

**其它**
- 自有程序图标（`.ico` 由 `make_icon.py` 用 Pillow 原创绘制，嵌入 exe 与窗口标题栏）
- **DPI 感知**：进程声明 Per-Monitor DPI Aware，使框选坐标与 `ImageGrab` 物理像素一致（本机 125% 缩放已验证）

技术栈：**Python 3.9 + tkinter + Pillow + soundcard**；AVI 容器由本项目
`o_shen_recorder/avi.py` 手写实现（RIFF / `avih` / 两条 `strl` / `strf` / `movi` / `idx1`
全字段回填），**零编码器依赖**。MP4 路径复用静态 `ffmpeg`（由 `imageio-ffmpeg` 随包提供，
无需系统安装），视频每帧 JPEG 经 libx264 编码、音频经 AAC 编码后封装 MP4。

> 范围说明：AVI 体积较大（示例：2560×1600 / 5 fps / 5 帧 含音视频约 1.4 MB），
> 改用 MP4 同条件下约 24 KB（压缩率极高）。不含硬件加速、摄像头、多显示器拼接。
> 麦克风混音默认关闭，MP4 需 `imageio-ffmpeg`（已随构建打包）。

## 主界面布局

主窗口（`580×560`，不可缩放）按功能分为 5 个带标题的分组框：

| 分组 | 包含控件 |
| --- | --- |
| **输出** | 输出文件输入框 + 浏览按钮、输出格式下拉（AVI / MP4）、格式说明、MP4 画质(CRF) 滑块 |
| **画面与质量** | 帧率(fps) 数字框、JPEG 质量滑块 |
| **录制区域** | 区域输入框（x,y,w,h）、全屏 / 鼠标框选 / 窗口捕获 三个按钮、操作提示文字 |
| **音频** | 录制系统声音（WASAPI loopback）复选框、同时混音麦克风复选框、麦克风音量滑块 |
| **录制控制** | 开始录制 / 暂停 / 停止录制 / 关于 按钮、状态文字、进度条 |

输入框与滑块在分组内自适应拉伸；开始录制后窗口自动最小化，停止后恢复。

## 快捷键

| 操作 | 快捷键 / 方式 |
| --- | --- |
| 开始录制 | 主界面「开始录制」按钮 |
| 暂停 / 继续 | `Ctrl+Shift+Alt+Z`（全局，窗体最小化也有效） |
| 停止录制 | 主界面「停止录制」按钮 |
| 框选时取消选择 | `Esc` 或 右键 |
| 框选时切换窗口捕获 | `W` |

## 目录

```
oshen-recorder/
├── main.py                    入口（含 --selftest）
├── run.bat                    源码方式启动（pythonw，无控制台）
├── make_icon.py               生成自有图标 assets/app.ico
├── build_exe.bat              打包成 onedir 独立程序
├── selftest.py                无头自测：音视频双流 AVI + MP4/H.264 结构校验
├── README.md                  中文文档（本文件）
├── README.en.md               英文文档
├── CONTRIBUTING.md            贡献与推送说明（中文）
├── CONTRIBUTING.en.md         贡献与推送说明（英文）
├── LICENSE                    软件许可协议（自由使用、保留所有权利）
├── assets/app.ico             自有图标（7 种尺寸）
├── o_shen_recorder/
│   ├── __init__.py
│   ├── app_info.py            品牌 / 版本 / 版权 / 无付费声明 / 资源路径
│   ├── avi.py                 手写 AVI 封装器（双流）+ probe_avi 校验器
│   ├── encoder.py             MP4 / H.264 (ffmpeg) 封装器
│   ├── recorder.py            抓屏线程 + 多音源混音线程 + 交错写入 + 暂停/继续
│   ├── region_selector.py     鼠标拖拽框选 / 窗口捕获覆盖层 + 选区规整
│   ├── hotkey.py              Win32 全局热键（Ctrl+Shift+Alt+Z 暂停/继续）线程
│   ├── dpi.py                 DPI 感知（坐标对齐用）
│   └── ui.py                  tkinter 界面
└── recordings/                默认输出目录（运行后生成，已 gitignore）
```

## 运行

双击 **`dist\OShenScreenRecorder\OShenScreenRecorder.exe`**（打包版，无需安装 Python）。
或源码方式：

```bat
run.bat                        :: 或 python main.py
python selftest.py             :: 无头自测，全部 PASS 即环境正常
```

源码运行需要 Python 3.9+ 与 `Pillow`、`soundcard`、`imageio-ffmpeg`
（`pip install Pillow soundcard imageio-ffmpeg`）。tkinter 为 Python 标准库自带。

## 打包（onedir）

双击 **`build_exe.bat`**。它会：

1. 在项目内创建隔离虚拟环境 `.buildenv\`（不动系统 Python）；
2. 在 venv 里安装 PyInstaller + Pillow + soundcard + imageio-ffmpeg；
3. 生成 `assets/app.ico`（若不存在）；
4. 用 `--onedir` 打包（含 `--collect-all soundcard` 与 `--collect-all imageio_ffmpeg`，
   后者把静态 ffmpeg 一并打进目录，使 MP4 输出开箱即用），
   产物为 `dist\OShenScreenRecorder\` 目录。

> 为什么用 venv：本机系统 Anaconda 装了过时的 `pathlib` backport（1.0.1），
> PyInstaller 会直接拒绝运行。隔离 venv 没有这个包，且不会改动系统环境。
> 为什么用 onedir：免每次启动解压，启动更快；代价是产物为一个目录（约 77 MB / 1000+ 文件）。
> 脚本保持纯 ASCII，避免 cmd 的 OEM 代码页把中文注释解析坏。

验证打包版：

```bat
dist\OShenScreenRecorder\OShenScreenRecorder.exe --selftest
```

会无头真实抓屏并采集系统声音 + 麦克风若干帧，生成含音视频双流的 AVI 并校验结构；
随后再合成帧 + PCM 走 `Mp4Encoder` 生成 MP4，校验 H.264 视频轨 + AAC 音频轨。
两段结果都写到 `%TEMP%\oshen_selftest.txt`（也可把结果文件路径作为第二个参数传入），
末尾 `OVERALL: PASS` 表示两条路径均通过。

## 自测结果（本机实测）

`python selftest.py` → **37 项全部 PASS**，覆盖：

- AVI 双流：头 `vids`/`auds`、`avih.dwStreams=2`、尺寸、帧率、`dwTotalFrames`、
  视频帧数、音频块数、`idx1` 条目数、`WAVEFORMATEX`（PCM 2ch 48000Hz 16bit）、
  每帧 JPEG 完整可解码、每段 PCM 长度合规；
- 框选规整 `normalize_box`（正向 / 反向 / 奇数对齐 / 过小）；
- 窗口枚举 `enum_top_windows`（合法矩形、命中测试）；
- 格式文案映射 `fmt_code`（AVI→avi / MP4→mp4）；
- **MP4 路径**：ffmpeg 可用、生成 MP4、视频轨 H.264、音频轨 AAC、含时长信息、压缩后体积 < 等效 AVI 的 1/3；
- **暂停 / 继续**：`pause()` 置 `paused=True`、录制线程冻结不落帧、`resume()` 清标志、恢复后继续产出帧与文件。
- **窗体最小化行为**：开始录制与点击「继续」后窗体均进入 `iconic`（最小化）状态。

打包版 `--selftest` 实测：`AVI: PASS`（真实抓屏 + 系统声音 + 麦克风混音双流）、
`MP4: PASS`（H.264 + AAC）、`OVERALL: PASS`。

GUI 实测启动，V0.5 标题、自有图标、5 个分组框（输出 / 画面与质量 / 录制区域 / 音频 / 录制控制）、
全屏 / 鼠标框选 / 窗口捕获按钮、系统声音 / 麦克风复选框、麦克风音量滑块、格式选择、MP4 画质(CRF)、
暂停按钮、版权信息齐全。

## 路线图

- 多显示器拼接、录制预览、鼠标点击高亮
- 可选：更细的视频质量预设、WebM/VP9 输出、硬件加速编码

---

版权与许可：Copyright (C) 2026 o神套装。本项目为自有原创实现，全部已实现功能免费开放使用；
未经授权不得将本项目用于商业再分发或声称原创。
