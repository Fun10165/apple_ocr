import io
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from pypdf import PdfReader, PdfWriter, Transformation
from reportlab.lib.pagesizes import portrait
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

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
                "/System/Library/Fonts/PingFang.ttc",
                "/System/Library/Fonts/Hiragino Sans GB.ttc",
                "/System/Library/Fonts/STHeiti Light.ttc",
                "/Library/Fonts/Arial Unicode MS.ttf",
            ]
            for font_path in font_paths:
                try:
                    pdfmetrics.registerFont(TTFont("ChineseFont", font_path))
                    logger.debug(f"使用中文字体: {font_path}")
                    return "ChineseFont"
                except Exception:
                    continue
        except Exception:
            pass
        logger.warning("无法加载中文字体，使用Helvetica（可能无法显示中文）")
        return "Helvetica"

    @staticmethod
    def _norm_to_points(
        x: float,
        y: float,
        w: float,
        h: float,
        width_px: int,
        height_px: int,
        dpi: Optional[int],
    ):
        # Vision坐标为归一化且原点在左下；PDF单位为points（72/inch）
        x_px = x * width_px
        y_px = y * height_px
        w_px = w * width_px
        h_px = h * height_px

        # 图像直出模式下，dpi可能为None，使用默认值72
        if dpi is None or dpi == 0:
            scale = 1.0
        else:
            scale = 72.0 / dpi

        return x_px * scale, y_px * scale, w_px * scale, h_px * scale

    def _build_overlay_page(
        self,
        page_width_pt: float,
        page_height_pt: float,
        items: List[BBoxItem],
        width_px: int,
        height_px: int,
        dpi: Optional[int],
    ) -> bytes:
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
            # 字号以bbox高度为准，保证垂直尺寸贴合（透明文本不影响视觉）
            font_size = max(6, int(h_pt))
            c.setFont(self.chinese_font, font_size)

            # 计算文本原始宽度，并按bbox宽度进行水平拉伸，使长度精确贴合
            try:
                measured_w = pdfmetrics.stringWidth(
                    item.text or "", self.chinese_font, font_size
                )
            except Exception:
                # 回退到Helvetica测量
                measured_w = pdfmetrics.stringWidth(
                    item.text or "", "Helvetica", font_size
                )

            scale_x = 1.0
            if measured_w and measured_w > 0:
                scale_x = w_pt / measured_w

            # 基线微调：将原点设为bbox左下，略微上移以贴合文本框
            baseline_adjust = max(0.0, 0.15 * h_pt)

            try:
                # 保存状态，水平缩放，再绘制，使长度与bbox匹配
                c.saveState()
                c.translate(x_pt, y_pt + baseline_adjust)
                c.scale(scale_x, 1.0)
                c.drawString(0, 0, item.text)
                c.restoreState()
            except Exception as e:
                logger.warning(f"无法绘制文本 '{item.text}': {e}")
                try:
                    c.saveState()
                    c.translate(x_pt, y_pt + baseline_adjust)
                    c.scale(scale_x, 1.0)
                    c.setFont("Helvetica", font_size)
                    c.drawString(0, 0, item.text)
                    c.restoreState()
                    c.setFont(self.chinese_font, font_size)
                except Exception:
                    logger.warning(f"完全无法绘制文本: '{item.text}'")

        c.showPage()
        c.save()
        return buf.getvalue()

    def add_page_overlay(
        self,
        pdf_path: Path,
        page_index: int,
        dpi: int,
        width_px: int,
        height_px: int,
        items: List,
    ):
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
                # 针对旋转页面，预先逆向旋转并平移overlay，使显示时与原文方向一致
                try:
                    rotate = int(getattr(page, "rotation", 0))
                except Exception:
                    rotate = int(page.get("/Rotate", 0) or 0)
                if rotate in (90, 180, 270):
                    w = float(page.mediabox.width)
                    h = float(page.mediabox.height)
                    if rotate == 90:
                        trans = Transformation().rotate(-90).translate(0, h)
                    elif rotate == 180:
                        trans = Transformation().rotate(-180).translate(w, h)
                    else:  # 270
                        trans = Transformation().rotate(-270).translate(w, 0)
                    # 兼容不同版本的PyPDF2：优先使用新API，否则回退旧API方案
                    if hasattr(page, "merge_transformed_page"):
                        page.merge_transformed_page(overlay_page, trans)
                    else:
                        if hasattr(overlay_page, "add_transformation"):
                            overlay_page.add_transformation(trans)
                            page.merge_page(overlay_page)
                        else:
                            method = getattr(page, "mergeTransformedPage", None)
                            if callable(method):
                                method(overlay_page, trans)
                            else:
                                page.merge_page(overlay_page)
                else:
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
