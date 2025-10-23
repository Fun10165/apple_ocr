import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from .pdf_to_images import render_pdf_stream, get_pdf_page_count
from .ocr_client import SwiftOCRClient
from .overlay_builder import OverlayComposer
from .page_parser import parse_pages, format_pages

logger = logging.getLogger("apple_ocr")


def setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def main():
    parser = argparse.ArgumentParser(
        description="Apple Vision OCR pipeline: PDF->PNG->OCR->Overlay PDF"
    )
    parser.add_argument("--input", required=True, help="输入PDF或目录")
    parser.add_argument("--output", required=True, help="输出PDF文件或目录")
    parser.add_argument("--dpi", type=int, default=300, help="渲染DPI，默认300")
    parser.add_argument(
        "--workers", type=int, default=os.cpu_count() or 4, help="并行渲染/处理线程数"
    )
    parser.add_argument(
        "--swift-bin",
        type=str,
        default=str(Path(__file__).parent.parent / "swift" / "OCRBridge" / 
                    ".build" / "release" / "ocrbridge"),
        help="Swift OCR 可执行文件路径",
    )
    parser.add_argument("--verbose", action="store_true", help="启用详细日志")
    parser.add_argument(
        "--pages", 
        type=str, 
        help="指定要处理的页面范围，如：1,3,5-10,15 （1-based页码）"
    )
    parser.add_argument(
        "--recognition-level",
        choices=["accurate", "fast"],
        default="accurate",
        help="识别速度/精度：accurate更准，fast更快",
    )
    parser.add_argument(
        "--uses-cpu-only",
        action="store_true",
        help="仅使用CPU运行OCR（默认关闭，允许GPU/ANE）",
    )
    parser.add_argument(
        "--auto-detect-language",
        action="store_true",
        help="自动检测语言（未指定languages时建议开启）",
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    input_path = Path(args.input)
    output_path = Path(args.output)

    if input_path.is_dir():
        output_path.mkdir(parents=True, exist_ok=True)
        pdf_files = sorted([p for p in input_path.glob("*.pdf")])
        if not pdf_files:
            logger.error("输入目录中未找到PDF文件")
            sys.exit(1)
        for pdf in pdf_files:
            out_pdf = output_path / f"{pdf.stem}_ocr.pdf"
            process_one(pdf, out_pdf, args)
    else:
        process_one(input_path, output_path, args)


def process_one(pdf_path: Path, output_pdf: Path, args):
    logger.info(f"处理: {pdf_path} -> {output_pdf}")

    # 解析页面范围
    selected_pages: Optional[List[int]] = None
    if args.pages:
        try:
            total_pages = get_pdf_page_count(pdf_path)
            selected_pages = parse_pages(args.pages, total_pages)
            logger.info(f"选择页面: {format_pages(selected_pages)} (共{len(selected_pages)}页)")
        except ValueError as e:
            logger.error(f"页面范围解析错误: {e}")
            sys.exit(1)

    # Swift OCR client
    ocr_client = SwiftOCRClient(swift_bin=args.swift_bin)
    ocr_client.start()

    composer = OverlayComposer(output_pdf)

    try:
        rendered_pages = []
        for page in render_pdf_stream(pdf_path, dpi=args.dpi, workers=args.workers, selected_pages=selected_pages):
            rendered_pages.append(page)
            # 将已渲染图片发送给Swift OCR（流式）
            ocr_client.send_image(
                image_path=page.image_path,
                page_index=page.page_index,
                width=page.width,
                height=page.height,
                dpi=page.dpi,
            )

        if not rendered_pages:
            logger.warning("没有页面被渲染")
            return

        # 接收OCR结果并合成透明文本层
        expected_pages = len(rendered_pages)
        for result in ocr_client.collect_results(expected_pages=expected_pages):
            composer.add_page_overlay(
                pdf_path=pdf_path,
                page_index=result.page_index,
                dpi=args.dpi,
                width_px=result.width,
                height_px=result.height,
                items=result.items,
            )

        composer.write_final(pdf_path)
        logger.info(f"完成: {output_pdf}")
    finally:
        ocr_client.stop()


if __name__ == "__main__":
    main()