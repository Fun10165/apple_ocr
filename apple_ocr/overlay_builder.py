import io
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict

from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import portrait
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

logger = logging.getLogger("apple_ocr")


@dataclass
class BBoxItem:
    text: str
    x: float  # 归一化坐标（0-1），左下角x
    y: float  # 归一化坐标（0-1），左下角y
    w: float
    h: float


class OverlayComposer:
    def __init__(self, output_pdf: Path):
        self.output_pdf = output_pdf
        self.writer = PdfWriter()
        self.reader: PdfReader | None = None
        self.total_pages: int = 0
        self.overlays: Dict[int, bytes] = {}
        self.chinese_font = self._setup_chinese_font()
    
    def _setup_chinese_font(self) -> str:
        """设置支持中文的字体"""
        try:
            # 尝试多个macOS中文字体路径
            font_paths = [
                '/System/Library/Fonts/PingFang.ttc',
                '/System/Library/Fonts/Hiragino Sans GB.ttc', 
                '/System/Library/Fonts/STHeiti Light.ttc',
                '/Library/Fonts/Arial Unicode MS.ttf'
            ]
            for font_path in font_paths:
                try:
                    pdfmetrics.registerFont(TTFont('ChineseFont', font_path))
                    logger.debug(f"使用中文字体: {font_path}")
                    return 'ChineseFont'
                except Exception:
                    continue
        except Exception:
            pass
        logger.warning("无法加载中文字体，使用Helvetica（可能无法显示中文）")
        return 'Helvetica'

    @staticmethod
    def _norm_to_points(x: float, y: float, w: float, h: float, width_px: int, height_px: int, dpi: int):
        # Vision坐标为归一化且原点在左下；PDF单位为points（72/inch）
        x_px = x * width_px
        y_px = y * height_px
        w_px = w * width_px
        h_px = h * height_px
        scale = 72.0 / dpi
        return x_px * scale, y_px * scale, w_px * scale, h_px * scale

    def _build_overlay_page(self, page_width_pt: float, page_height_pt: float, items: List[BBoxItem], width_px: int, height_px: int, dpi: int) -> bytes:
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=portrait((page_width_pt, page_height_pt)))
        try:
            c.setFillAlpha(0.0)  # 透明文本
        except Exception:
            # 某些版本reportlab不支持alpha，退化为非常浅灰
            try:
                c.setFillColorRGB(1, 1, 1, alpha=0.01)  # 近似透明
            except Exception:
                pass

        try:
            c.setStrokeAlpha(0.0)
        except Exception:
            pass
        c.setFont(self.chinese_font, 10)

        for item in items:
            x_pt, y_pt, w_pt, h_pt = self._norm_to_points(
                item.x, item.y, item.w, item.h, width_px, height_px, dpi
            )
            # 用bbox高度近似字号，避免选区过小
            font_size = max(6, min(48, int(h_pt)))
            c.setFont(self.chinese_font, font_size)
            # 将文本原点设为bbox左下角略微上移，尽量覆盖区域
            try:
                c.drawString(x_pt, y_pt + max(0, 0.2 * h_pt), item.text)
            except Exception as e:
                logger.warning(f"无法绘制文本 '{item.text}': {e}")
                # 尝试用Helvetica绘制（可能是纯英文/数字）
                try:
                    c.setFont("Helvetica", font_size)
                    c.drawString(x_pt, y_pt + max(0, 0.2 * h_pt), item.text)
                    c.setFont(self.chinese_font, font_size)  # 恢复中文字体
                except Exception:
                    logger.warning(f"完全无法绘制文本: '{item.text}'")

        c.showPage()
        c.save()
        return buf.getvalue()

    def add_page_overlay(self, pdf_path: Path, page_index: int, dpi: int, width_px: int, height_px: int, items: List):
        if self.reader is None:
            self.reader = PdfReader(str(pdf_path))
            self.total_pages = len(self.reader.pages)
        assert self.reader is not None
        page = self.reader.pages[page_index]
        page_width_pt = float(page.mediabox.width)
        page_height_pt = float(page.mediabox.height)

        bbox_items = [BBoxItem(text=i.text, x=i.x, y=i.y, w=i.w, h=i.h) for i in items]
        overlay_pdf_bytes = self._build_overlay_page(
            page_width_pt, page_height_pt, bbox_items, width_px, height_px, dpi
        )
        self.overlays[page_index] = overlay_pdf_bytes

    def write_final(self, original_pdf: Path):
        # 顺序写出，确保页面结构与顺序与原始一致
        if self.reader is None:
            self.reader = PdfReader(str(original_pdf))
            self.total_pages = len(self.reader.pages)
        assert self.reader is not None

        for idx in range(self.total_pages):
            page = self.reader.pages[idx]
            if idx in self.overlays:
                overlay_reader = PdfReader(io.BytesIO(self.overlays[idx]))
                overlay_page = overlay_reader.pages[0]
                page.merge_page(overlay_page)
            self.writer.add_page(page)

        # 保留元数据
        try:
            if self.reader.metadata:
                self.writer.add_metadata(self.reader.metadata)
        except Exception:
            logger.warning("元数据复制失败，继续处理")

        with open(self.output_pdf, "wb") as f:
            self.writer.write(f)
        logger.info(f"写出OCR合成PDF: {self.output_pdf}")