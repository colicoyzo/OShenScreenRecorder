"""品牌与版本信息（本项目的唯一来源）。

这是全新自有项目：名称、版本号、版权年份、作者均由本项目自行定义。
本项目从设计上不包含任何授权校验、VIP 等级、付费墙或功能闸门，
因此「所有涉及付费的功能都关闭付费控制」在此是天然成立的，
而不是去修改任何第三方软件。
"""

APP_NAME = "o神套装-屏幕录制"
APP_NAME_ASCII = "OShen Screen Recorder"

VERSION = "V0.5"
VERSION_TUPLE = (0, 5, 0, 0)  # 供 PE/VS_VERSION_INFO 等使用

COPYRIGHT = "Copyright (C) 2026"
COMPANY = "o神套装"
PRODUCT_NAME = "o神套装-屏幕录制"

# 本项目没有任何受限功能：不设 VIP、不设试用、不设激活码、不设功能开关。
# 所有已实现功能对所有人无条件开放。
FEATURE_GATES = ()
LICENSE_MODEL = "all-features-unrestricted"

FEATURE_POLICY = (
    "本项目为全新自有项目，未使用任何第三方商业软件的代码或二进制。\n"
    "所有功能默认开放：无 VIP、无付费墙、无授权校验、无功能闸门。\n"
    "V0.2：系统声音录制（WASAPI loopback）、自有图标、onedir 打包。\n"
    "V0.3：麦克风混音（可调音量）、鼠标拖拽框选录制区域、DPI 感知坐标对齐。\n"
    "V0.4：新增 MP4/H.264 压缩输出（ffmpeg，AAC 音频），可选替代 AVI。\n"
    "V0.5：开始录制后窗体自动最小化；全局热键 Ctrl+Shift+Alt+Z 暂停/继续（窗体最小化也有效）；点击继续后再次最小化。"
)


def asset_path(name: str) -> str:
    """解析 assets/ 下的文件：源码运行与 PyInstaller onedir 打包都可用。"""
    import sys
    import os
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        return os.path.join(base, "assets", name)
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "assets", name,
    )


def about_text() -> str:
    return (
        f"{APP_NAME}\n"
        f"版本：{VERSION}\n"
        f"{COPYRIGHT} {COMPANY}\n"
        f"\n{FEATURE_POLICY}"
    )
