"""
Apple OCR API接口

提供简单易用的编程接口，方便其他程序调用OCR功能。
"""

import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

from .pdf_to_images import render_pdf_stream, get_pdf_page_count
from .ocr_client import SwiftOCRClient, OCRResult
from .overlay_builder import OverlayComposer
from .page_parser import parse_pages


logger = logging.getLogger("apple_ocr")


class AppleOCR:
    """Apple OCR主类，提供简单的API接口"""
    
    def __init__(
        self,
        swift_bin: Optional[str] = None,
        dpi: int = 300,
        workers: Optional[int] = None
    ):
        """
        初始化Apple OCR
        
        Args:
            swift_bin: Swift OCR可执行文件路径，None使用默认路径
            dpi: 渲染DPI，默认300
            workers: 并行线程数，None使用CPU核心数
        """
        if swift_bin is None:
            swift_bin = str(Path(__file__).parent.parent / "swift" / "OCRBridge" / 
                           ".build" / "release" / "ocrbridge")
        
        if workers is None:
            import os
            workers = os.cpu_count() or 4
            
        self.swift_bin = swift_bin
        self.dpi = dpi
        self.workers = workers
        
    def extract_text(
        self,
        pdf_path: str | Path,
        pages: Optional[str] = None
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
        ocr_client = SwiftOCRClient(swift_bin=self.swift_bin)
        ocr_client.start()
        
        try:
            # 渲染页面
            rendered_pages = []
            for page in render_pdf_stream(
                pdf_path, 
                dpi=self.dpi, 
                workers=self.workers, 
                selected_pages=selected_pages
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
            for result in ocr_client.collect_results(expected_pages=len(rendered_pages)):
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
                            "confidence": item.confidence
                        }
                        for item in result.items
                    ]
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
        pages: Optional[str] = None
    ) -> None:
        """
        创建可搜索的PDF
        
        Args:
            input_pdf: 输入PDF路径
            output_pdf: 输出PDF路径
            pages: 页面范围，如 "1,3,5-10"，None表示所有页面
        """
        input_pdf = Path(input_pdf)
        output_pdf = Path(output_pdf)
        
        # 解析页面范围
        selected_pages = None
        if pages:
            total_pages = get_pdf_page_count(input_pdf)
            selected_pages = parse_pages(pages, total_pages)
        
        # 初始化组件
        ocr_client = SwiftOCRClient(swift_bin=self.swift_bin)
        ocr_client.start()
        
        composer = OverlayComposer(output_pdf)
        
        try:
            # 渲染和OCR
            rendered_pages = []
            for page in render_pdf_stream(
                input_pdf, 
                dpi=self.dpi, 
                workers=self.workers, 
                selected_pages=selected_pages
            ):
                rendered_pages.append(page)
                ocr_client.send_image(
                    image_path=page.image_path,
                    page_index=page.page_index,
                    width=page.width,
                    height=page.height,
                    dpi=page.dpi,
                )
            
            if not rendered_pages:
                logger.warning("没有页面被处理")
                return
            
            # 合成透明文本层
            for result in ocr_client.collect_results(expected_pages=len(rendered_pages)):
                composer.add_page_overlay(
                    pdf_path=input_pdf,
                    page_index=result.page_index,
                    dpi=self.dpi,
                    width_px=result.width,
                    height_px=result.height,
                    items=result.items,
                )
            
            # 写出最终PDF
            composer.write_final(input_pdf)
            
        finally:
            ocr_client.stop()
    
    def get_page_count(self, pdf_path: str | Path) -> int:
        """获取PDF总页数"""
        return get_pdf_page_count(Path(pdf_path))


# 便捷函数
def extract_text_from_pdf(
    pdf_path: str | Path,
    pages: Optional[str] = None,
    dpi: int = 300
) -> List[Dict[str, Any]]:
    """
    便捷函数：从PDF提取文本
    
    Args:
        pdf_path: PDF文件路径
        pages: 页面范围，如 "1,3,5-10"
        dpi: 渲染DPI
        
    Returns:
        提取的文本数据
    """
    ocr = AppleOCR(dpi=dpi)
    return ocr.extract_text(pdf_path, pages)


def create_searchable_pdf(
    input_pdf: str | Path,
    output_pdf: str | Path,
    pages: Optional[str] = None,
    dpi: int = 300
) -> None:
    """
    便捷函数：创建可搜索PDF
    
    Args:
        input_pdf: 输入PDF路径
        output_pdf: 输出PDF路径
        pages: 页面范围，如 "1,3,5-10"
        dpi: 渲染DPI
    """
    ocr = AppleOCR(dpi=dpi)
    ocr.create_searchable_pdf(input_pdf, output_pdf, pages)