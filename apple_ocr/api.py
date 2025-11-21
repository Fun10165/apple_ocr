"""
Apple OCR API接口

提供简单易用的编程接口，方便其他程序调用OCR功能。
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .ocr_client import OCRResult, SwiftOCRClient
from .overlay_builder import OverlayComposer
from .page_parser import format_pages, parse_pages
from .pdf_to_images import get_pdf_page_count, render_pdf_stream

ocrmypdf: Any | None = None
try:
    ocrmypdf = __import__("ocrmypdf")
except Exception:
    ocrmypdf = None


logger = logging.getLogger("apple_ocr")


class AppleOCR:
    """Apple OCR主类，提供简单的API接口"""

    def __init__(
        self,
        swift_bin: Optional[str] = None,
        dpi: Optional[int] = None,
        workers: Optional[int] = None,
        languages: Optional[List[str]] = None,
        recognition_level: Optional[str] = None,
        uses_cpu_only: Optional[bool] = None,
        auto_detect_language: Optional[bool] = None,
    ):
        """
        初始化Apple OCR

        Args:
            swift_bin: Swift OCR可执行文件路径，None使用默认路径
            dpi: 渲染DPI，None或0表示图像直出模式（默认），>0表示渲染模式
            workers: 并行线程数，None使用CPU核心数
        """
        if swift_bin is None:
            swift_bin = str(
                Path(__file__).parent.parent
                / "swift"
                / "OCRBridge"
                / ".build"
                / "release"
                / "ocrbridge"
            )

        if workers is None:
            import os

            workers = os.cpu_count() or 4

        self.swift_bin = swift_bin
        self.dpi = dpi
        self.workers = workers
        self.languages = languages
        self.recognition_level = recognition_level
        self.uses_cpu_only = uses_cpu_only
        self.auto_detect_language = auto_detect_language

    def extract_text(
        self, pdf_path: str | Path, pages: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        从PDF提取文本，返回结构化数据

        Args:
            pdf_path: PDF文件路径
            pages: 页面范围，如 "1,3,5-10"，None表示所有页面

        Returns:
            提取的文本数据列表，每个元素包含：
            - page_index: 页面索引（0-based）
            - items: 文本项列表，每项包含text, x, y, w, h, confidence
        """
        pdf_path = Path(pdf_path)

        # 解析页面范围
        selected_pages = None
        if pages:
            total_pages = get_pdf_page_count(pdf_path)
            selected_pages = parse_pages(pages, total_pages)

        # 初始化OCR客户端
        ocr_client = SwiftOCRClient(
            swift_bin=self.swift_bin,
            languages=self.languages,
            recognition_level=self.recognition_level,
            uses_cpu_only=self.uses_cpu_only,
            auto_detect_language=self.auto_detect_language,
        )
        ocr_client.start()

        try:
            # 渲染页面
            rendered_pages = []
            for page in render_pdf_stream(
                pdf_path,
                dpi=self.dpi,
                workers=self.workers,
                selected_pages=selected_pages,
            ):
                rendered_pages.append(page)
                # 发送OCR任务
                ocr_client.send_image(
                    image_path=page.image_path,
                    page_index=page.page_index,
                    width=page.width,
                    height=page.height,
                    dpi=page.dpi,
                )

            if not rendered_pages:
                return []

            # 收集OCR结果
            results = []
            for result in ocr_client.collect_results(
                expected_pages=len(rendered_pages)
            ):
                page_data = {
                    "page_index": result.page_index,
                    "width": result.width,
                    "height": result.height,
                    "items": [
                        {
                            "text": item.text,
                            "x": item.x,
                            "y": item.y,
                            "w": item.w,
                            "h": item.h,
                            "confidence": item.confidence,
                        }
                        for item in result.items
                    ],
                }
                results.append(page_data)

            # 按页面索引排序
            results.sort(key=lambda x: x["page_index"])
            return results

        finally:
            ocr_client.stop()

    def create_searchable_pdf(
        self,
        input_pdf: str | Path,
        output_pdf: str | Path,
        pages: Optional[str] = None,
        language: Optional[str] = None,
    ) -> None:
        """
        创建可搜索的PDF（使用OCRmyPDF）

        Args:
            input_pdf: 输入PDF路径
            output_pdf: 输出PDF路径
            pages: 页面范围，如 "1,3,5-10"，None表示所有页面
        """
        input_pdf = Path(input_pdf)
        output_pdf = Path(output_pdf)

        if ocrmypdf is None:
            raise RuntimeError("ocrmypdf 未安装或导入失败，请安装依赖后再试")

        pages_str = None
        if pages:
            total_pages = get_pdf_page_count(input_pdf)
            selected_pages = parse_pages(pages, total_pages)
            pages_str = format_pages(selected_pages)

        # 直接调用 ocrmypdf 进行 OCR 处理并生成“sandwich” PDF
        ocrmypdf.ocr(
            input_file=str(input_pdf),
            output_file=str(output_pdf),
            pages=pages_str,
            progress_bar=False,
            plugins=["ocrmypdf_appleocr"],
            language=language,
        )

    def get_page_count(self, pdf_path: str | Path) -> int:
        """获取PDF总页数"""
        return get_pdf_page_count(Path(pdf_path))

    # 新增：图片批量OCR
    def extract_text_from_images(
        self, image_paths: List[str | Path]
    ) -> List[Dict[str, Any]]:
        """
        从多张图片提取文本，返回JSON友好的结构化数据列表。

        Args:
            image_paths: 图片路径列表（支持png/jpg/jpeg/tiff/bmp等）

        Returns:
            每个图片的识别结果字典，包含：
            - image: 图片文件名
            - width: 图片宽度（像素）
            - height: 图片高度（像素）
            - items: 文本项列表，每项包含text, x, y, w, h, confidence（坐标为归一化0-1）
        """
        if not image_paths:
            return []

        # 读取尺寸信息
        from PIL import Image  # 依赖 Pillow

        indexed_images: List[tuple[int, Path, int, int]] = []
        for idx, p in enumerate(image_paths):
            path = Path(p)
            if not path.exists() or not path.is_file():
                logger.warning(f"图片不存在或不是文件: {path}")
                continue
            try:
                with Image.open(path) as im:
                    width, height = im.size
            except Exception as e:
                logger.warning(f"无法读取图片尺寸: {path} ({e})")
                width = 0
                height = 0
            indexed_images.append((idx, path, width, height))

        if not indexed_images:
            return []

        # 初始化OCR客户端
        ocr_client = SwiftOCRClient(
            swift_bin=self.swift_bin,
            languages=self.languages,
            recognition_level=self.recognition_level,
            uses_cpu_only=self.uses_cpu_only,
            auto_detect_language=self.auto_detect_language,
        )
        ocr_client.start()

        try:
            # 发送任务（dpi=0表示图像直出，无需缩放）
            for idx, path, width, height in indexed_images:
                ocr_client.send_image(
                    image_path=str(path),
                    page_index=idx,
                    width=width,
                    height=height,
                    dpi=0,
                )

            # 收集结果并组装JSON友好结构
            results: List[Dict[str, Any]] = []
            for res in ocr_client.collect_results(expected_pages=len(indexed_images)):
                # 找回对应图片名
                img_name = next(
                    (p.name for (i, p, _, _) in indexed_images if i == res.page_index),
                    None,
                )
                page_data = {
                    "image": img_name or str(res.page_index),
                    "width": res.width,
                    "height": res.height,
                    "items": [
                        {
                            "text": item.text,
                            "x": item.x,
                            "y": item.y,
                            "w": item.w,
                            "h": item.h,
                            "confidence": item.confidence,
                        }
                        for item in res.items
                    ],
                }
                results.append(page_data)

            # 保持原始顺序（按发送时的索引排序）
            name_order = {p.name: i for (i, p, _, _) in indexed_images}
            results.sort(key=lambda x: name_order.get(x["image"], 0))
            return results
        finally:
            ocr_client.stop()

    def extract_text_from_image_dir(
        self, dir_path: str | Path, exts: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        从目录批量提取图片文本。

        Args:
            dir_path: 图片目录
            exts: 允许的扩展名列表（不含点），默认["png","jpg","jpeg","tiff","bmp"]

        Returns:
            与extract_text_from_images相同的结构化结果列表。
        """
        d = Path(dir_path)
        if not d.is_dir():
            raise ValueError(f"不是有效目录: {dir_path}")
        allow = (
            ["png", "jpg", "jpeg", "tiff", "bmp"]
            if not exts
            else [e.lower() for e in exts]
        )
        files = sorted(
            [
                p
                for p in d.iterdir()
                if p.is_file() and p.suffix.lower().lstrip(".") in allow
            ]
        )
        from typing import cast
        return self.extract_text_from_images(cast(list[str | Path], files))


# 便捷函数
def extract_text_from_pdf(
    pdf_path: str | Path, pages: Optional[str] = None, dpi: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    便捷函数：从PDF提取文本

    Args:
        pdf_path: PDF文件路径
        pages: 页面范围，如 "1,3,5-10"
        dpi: 渲染DPI，None或0表示图像直出模式（默认），>0表示渲染模式

    Returns:
        提取的文本数据
    """
    ocr = AppleOCR(dpi=dpi)
    return ocr.extract_text(pdf_path, pages)


def create_searchable_pdf(
    input_pdf: str | Path,
    output_pdf: str | Path,
    pages: Optional[str] = None,
    dpi: Optional[int] = None,
    language: Optional[str] = None,
) -> None:
    """
    便捷函数：创建可搜索PDF

    Args:
        input_pdf: 输入PDF路径
        output_pdf: 输出PDF路径
        pages: 页面范围，如 "1,3,5-10"
        dpi: 渲染DPI，None或0表示图像直出模式（默认），>0表示渲染模式
    """
    ocr = AppleOCR(dpi=dpi)
    ocr.create_searchable_pdf(input_pdf, output_pdf, pages, language=language)


# 新增：图片便捷函数
def extract_text_from_images(
    image_paths: List[str | Path], dpi: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    便捷函数：从多张图片提取文本（返回JSON友好结构）

    Args:
        image_paths: 图片路径列表
        dpi: 兼容参数（未使用，图片模式下使用dpi=0）
    """
    ocr = AppleOCR(dpi=dpi)
    return ocr.extract_text_from_images(image_paths)


def extract_text_from_image_dir(
    dir_path: str | Path,
    exts: Optional[List[str]] = None,
    dpi: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    便捷函数：从目录批量提取图片文本

    Args:
        dir_path: 图片目录
        exts: 扩展名白名单
        dpi: 兼容参数（未使用）
    """
    ocr = AppleOCR(dpi=dpi)
    return ocr.extract_text_from_image_dir(dir_path, exts)
