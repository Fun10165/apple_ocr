import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Any, cast

from pdf2image import convert_from_path, pdfinfo_from_path

try:
    fitz = cast(Any, __import__("fitz"))
except Exception:
    fitz = None

logger = logging.getLogger("apple_ocr")


def get_pdf_page_count(pdf_path: Path) -> int:
    """获取PDF总页数"""
    info = pdfinfo_from_path(str(pdf_path))
    return int(info.get("Pages", 0))


def _extract_embedded_images(
    pdf_path: Path, page_index: int, out_dir: Path
) -> Optional["PageImage"]:
    """
    提取PDF页面中的嵌入图像（图像直出模式）

    Args:
        pdf_path: PDF文件路径
        page_index: 页面索引（0-based）
        out_dir: 输出目录

    Returns:
        PageImage对象，如果页面没有嵌入图像则返回None
    """
    if fitz is None:
        logger.warning("PyMuPDF未安装，无法使用图像直出功能")
        return None

    doc = None
    try:
        doc = fitz.open(pdf_path)
        page = doc.load_page(page_index)

        # 获取页面中的嵌入图像
        image_infos = page.get_images(full=True)
        if not image_infos:
            doc.close()
            return None

        # 选择最大的图像
        def get_image_area(info):
            width = info[2] if len(info) > 2 else 0
            height = info[3] if len(info) > 3 else 0
            return width * height

        largest_image_info = max(image_infos, key=get_image_area)
        xref = largest_image_info[0]

        # 提取图像数据
        image_data = doc.extract_image(xref)
        image_bytes = image_data.get("image")
        ext = image_data.get("ext", "png")

        if not image_bytes:
            doc.close()
            return None

        # 保存图像文件
        out_dir.mkdir(parents=True, exist_ok=True)
        image_path = out_dir / f"page_{page_index:06d}.{ext}"

        with open(image_path, "wb") as f:
            f.write(image_bytes)

        # 获取图像尺寸
        import io

        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size
        img.close()  # 确保图像文件句柄关闭

        logger.debug(
            f"图像直出: 页 {page_index} -> {image_path.name} ({width}x{height})"
        )

        result = PageImage(
            page_index=page_index,
            image_path=str(image_path),
            width=width,
            height=height,
            dpi=0,  # 图像直出模式，DPI为0
            total_pages=0,
        )
        doc.close()  # 成功时关闭文档
        return result

    except Exception as e:
        logger.warning(f"图像直出失败（页 {page_index}）: {e}")
        return None
    finally:
        # 确保文档在所有情况下都被关闭
        if doc is not None:
            try:
                doc.close()
            except Exception:
                pass  # 忽略关闭时的错误


@dataclass
class PageImage:
    page_index: int
    image_path: str
    width: int
    height: int
    dpi: int
    total_pages: int


def _render_one_page(
    pdf_path: Path, page_index: int, dpi: int, out_dir: Path
) -> PageImage:
    out_dir.mkdir(parents=True, exist_ok=True)
    base = f"page_{page_index:06d}"

    # 仅渲染指定页，实现流式并行
    paths = cast(List[str], convert_from_path(
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
    ))
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


def render_pdf_stream(
    pdf_path: Path,
    dpi: Optional[int] = None,
    workers: int = os.cpu_count() or 4,
    selected_pages: Optional[List[int]] = None,
):
    """将PDF并行渲染为PNG，支持图像直出模式。

    - 当dpi为None或0时，使用图像直出模式（直接提取PDF中的嵌入图像）
    - 当dpi>0时，使用传统的渲染模式

    Args:
        pdf_path: PDF文件路径
        dpi: 渲染DPI，None或0表示图像直出模式
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

    # 图像直出模式
    if dpi is None or dpi == 0:
        logger.info(f"图像直出模式: {pdf_path}")
        logger.info(f"处理页面: {len(pages_to_render)}/{total_pages}")

        futures = []
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for page_index in pages_to_render:
                futures.append(
                    ex.submit(_extract_embedded_images, pdf_path, page_index, out_dir)
                )

            for fut in as_completed(futures):
                page_img_opt: Optional[PageImage] = fut.result()
                if page_img_opt is not None:
                    page_img_val = page_img_opt
                    page_img_val.total_pages = total_pages
                    logger.debug(
                        f"图像直出完成: page={page_img_val.page_index} size={page_img_val.width}x{page_img_val.height}"
                    )
                    yield page_img_val
                else:
                    # 如果图像直出失败，回退到默认渲染
                    logger.debug(
                        f"页面 {futures.index(fut)} 无嵌入图像，回退到渲染模式"
                    )
                    # 这里可以添加回退逻辑，但为了简化，我们暂时跳过
                    continue
    else:
        # 传统渲染模式
        logger.info(f"渲染模式 (DPI={dpi}): {pdf_path}")
        logger.info(f"渲染页面: {len(pages_to_render)}/{total_pages}")

        futures = []
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for page_index in pages_to_render:
                futures.append(
                    ex.submit(_render_one_page, pdf_path, page_index, dpi, out_dir)
                )

            for fut in as_completed(futures):
                page_img_res: PageImage = cast(PageImage, fut.result())
                page_img_res.total_pages = total_pages
                logger.debug(
                    f"渲染完成: page={page_img_res.page_index} size={page_img_res.width}x{page_img_res.height}"
                )
                yield page_img_res
