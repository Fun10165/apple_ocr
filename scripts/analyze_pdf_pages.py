#!/usr/bin/env python3
"""
分析 PDF 页面尺寸与旋转信息，帮助定位覆盖层旋转/坐标映射问题。

用法:
  uv run python scripts/analyze_pdf_pages.py logic.pdf logic_ocr.pdf

输出:
  - 每个输入文件的前两页详细信息（索引、尺寸、旋转、方向、盒子信息）
  - 所有页面的旋转/方向分布统计
"""
import sys
from pathlib import Path
from typing import Dict
from pypdf import PdfReader


def page_info(reader: PdfReader, page_index: int) -> Dict:
    page = reader.pages[page_index]
    # 旋转角度
    try:
        rotate = int(getattr(page, "rotation", 0))
    except Exception:
        rotate = int(page.get("/Rotate", 0) or 0)

    # 盒子与尺寸
    mb = page.mediabox
    cb = getattr(page, "cropbox", None)
    ab = getattr(page, "artbox", None)
    bb = getattr(page, "bleedbox", None)
    width = float(mb.width)
    height = float(mb.height)
    orientation = "landscape" if width > height else "portrait"

    return {
        "index": page_index,
        "rotate": rotate,
        "width": width,
        "height": height,
        "orientation": orientation,
        "mediabox": (float(mb.left), float(mb.bottom), float(mb.right), float(mb.top)),
        "cropbox": tuple(map(float, (cb.left, cb.bottom, cb.right, cb.top))) if cb else None,
        "artbox": tuple(map(float, (ab.left, ab.bottom, ab.right, ab.top))) if ab else None,
        "bleedbox": tuple(map(float, (bb.left, bb.bottom, bb.right, bb.top))) if bb else None,
    }


def summarize(reader: PdfReader):
    rotations = {}
    orientations = {}
    for i in range(len(reader.pages)):
        info = page_info(reader, i)
        rotations[info["rotate"]] = rotations.get(info["rotate"], 0) + 1
        orientations[info["orientation"]] = orientations.get(info["orientation"], 0) + 1
    return rotations, orientations


def print_file_summary(pdf_path: Path):
    print(f"\n=== 文件: {pdf_path} ===")
    reader = PdfReader(str(pdf_path))
    total = len(reader.pages)
    print(f"总页数: {total}")

    first_two = [0, 1] if total >= 2 else [0]
    for idx in first_two:
        info = page_info(reader, idx)
        print(
            f"- 页 {info['index']}: rotate={info['rotate']} size={info['width']}x{info['height']} ({info['orientation']})"
        )
        print(f"  mediabox={info['mediabox']}")
        print(f"  cropbox={info['cropbox']}")
        print(f"  artbox={info['artbox']}")
        print(f"  bleedbox={info['bleedbox']}")

    rotations, orientations = summarize(reader)
    print("旋转分布:")
    for rot, count in sorted(rotations.items()):
        print(f"  rotate={rot}: {count}页")
    print("方向分布:")
    for ori, count in sorted(orientations.items()):
        print(f"  {ori}: {count}页")


def main():
    if len(sys.argv) < 2:
        print("用法: python scripts/analyze_pdf_pages.py <pdf1> [pdf2 ...]")
        sys.exit(1)

    for arg in sys.argv[1:]:
        path = Path(arg)
        if not path.exists():
            print(f"文件不存在: {path}")
            continue
        print_file_summary(path)


if __name__ == "__main__":
    main()