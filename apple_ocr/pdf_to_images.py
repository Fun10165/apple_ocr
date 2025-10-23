import logging
import os
from dataclasses import dataclass
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List

from pdf2image import convert_from_path, pdfinfo_from_path

logger = logging.getLogger("apple_ocr")


def get_pdf_page_count(pdf_path: Path) -> int:
    """获取PDF总页数"""
    info = pdfinfo_from_path(str(pdf_path))
    return int(info.get("Pages", 0))


@dataclass
class PageImage:
    page_index: int
    image_path: str
    width: int
    height: int
    dpi: int
    total_pages: int


def _render_one_page(pdf_path: Path, page_index: int, dpi: int, out_dir: Path) -> PageImage:
    out_dir.mkdir(parents=True, exist_ok=True)
    base = f"page_{page_index:06d}"

    # 仅渲染指定页，实现流式并行
    paths = convert_from_path(
        str(pdf_path),
        dpi=dpi,
        fmt="png",
        output_folder=str(out_dir),
        output_file=base,
        paths_only=True,
        # pdf2image不支持page_numbers，用first_page/last_page指定单页
        first_page=page_index + 1,
        last_page=page_index + 1,
        single_file=True,
    )
    image_path = paths[0]

    # 读取图片尺寸
    try:
        from PIL import Image
        with Image.open(image_path) as im:
            width, height = im.size
    except Exception:
        width = height = 0

    return PageImage(
        page_index=page_index,
        image_path=image_path,
        width=width,
        height=height,
        dpi=dpi,
        total_pages=0,  # 稍后填充
    )


def render_pdf_stream(pdf_path: Path, dpi: int = 300, workers: int = os.cpu_count() or 4, selected_pages: Optional[List[int]] = None):
    """将PDF并行渲染为PNG，300dpi，每页完成即yield。
    使用 pdf2image 的逐页渲染以实现流式。
    
    Args:
        pdf_path: PDF文件路径
        dpi: 渲染DPI
        workers: 并行线程数
        selected_pages: 要渲染的页面索引列表（0-based），None表示所有页面
    """
    info = pdfinfo_from_path(str(pdf_path))
    total_pages = int(info.get("Pages", 0))
    if total_pages == 0:
        raise RuntimeError("无法获取PDF页数")

    # 确定要渲染的页面
    if selected_pages is None:
        pages_to_render = list(range(total_pages))
    else:
        pages_to_render = [p for p in selected_pages if 0 <= p < total_pages]
        if not pages_to_render:
            logger.warning("没有有效的页面需要渲染")
            return

    out_dir = pdf_path.parent / f".{pdf_path.stem}_images"
    logger.info(f"渲染目录: {out_dir}")
    logger.info(f"渲染页面: {len(pages_to_render)}/{total_pages}")

    futures = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for page_index in pages_to_render:
            futures.append(ex.submit(_render_one_page, pdf_path, page_index, dpi, out_dir))

        for fut in as_completed(futures):
            page_img: PageImage = fut.result()
            page_img.total_pages = total_pages
            logger.debug(
                f"渲染完成: page={page_img.page_index} size={page_img.width}x{page_img.height}"
            )
            yield page_img