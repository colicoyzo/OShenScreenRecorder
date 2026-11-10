#!/usr/bin/env python3
"""生成项目自有图标 assets/app.ico —— 纯 Pillow 绘制，不使用任何第三方图标。

设计：深蓝圆角方块 + 白色录制圆点 + 右下角红色 REC 条，呼应「o神套装-屏幕录制」。
输出多尺寸 ICO（16/24/32/48/64/128/256），供 exe 与窗口标题栏共用。

    python make_icon.py
"""

from __future__ import annotations

import os
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "assets", "app.ico")
SIZES = (16, 24, 32, 48, 64, 128, 256)

BG = (26, 42, 74, 255)       # 深蓝
RING = (108, 168, 255, 255)  # 亮蓝环
DOT = (245, 248, 255, 255)   # 中心白点
REC = (232, 64, 72, 255)     # 红


def draw(size: int) -> Image.Image:
    s = size * 4  # 超采样抗锯齿
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    m = int(s * 0.06)
    r = int(s * 0.22)
    d.rounded_rectangle((m, m, s - m, s - m), radius=r, fill=BG)

    # 外环（摄像机光圈感）
    cx = cy = s // 2
    ro = int(s * 0.29)
    ri = int(s * 0.215)
    d.ellipse((cx - ro, cy - ro, cx + ro, cy + ro), outline=RING, width=max(2, s // 40))
    d.ellipse((cx - ri, cy - ri, cx + ri, cy + ri), fill=(36, 60, 104, 255))

    # 中心录制点
    rp = int(s * 0.135)
    d.ellipse((cx - rp, cy - rp, cx + rp, cy + rp), fill=DOT)

    # 右下角 REC 红条
    bw, bh = int(s * 0.40), int(s * 0.17)
    bx, by = s - m - bw, s - m - bh
    d.rounded_rectangle((bx, by, bx + bw, by + bh), radius=int(bh * 0.35), fill=REC)

    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    base = draw(SIZES[-1])
    ico_images = [draw(n) for n in SIZES[:-1]] + [base]
    base.save(OUT, format="ICO", sizes=[(n, n) for n in SIZES], append_images=ico_images)
    print("icon written:", OUT, os.path.getsize(OUT), "bytes", "sizes", SIZES)


if __name__ == "__main__":
    main()
