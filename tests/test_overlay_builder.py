"""
PDF透明文本层构建器的单元测试
"""

import io
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from apple_ocr.overlay_builder import BBoxItem, OverlayComposer


class TestOverlayComposer:
    """透明文本层构建器测试"""

    def test_bbox_item_creation(self):
        """测试BBoxItem创建"""
        item = BBoxItem(text="测试", x=0.1, y=0.2, w=0.3, h=0.4)
        assert item.text == "测试"
        assert item.x == 0.1
        assert item.y == 0.2
        assert item.w == 0.3
        assert item.h == 0.4

    def test_norm_to_points_conversion(self):
        """测试归一化坐标到points的转换"""
        # 测试基本转换
        x_pt, y_pt, w_pt, h_pt = OverlayComposer._norm_to_points(
            x=0.5, y=0.5, w=0.2, h=0.1, width_px=1000, height_px=1000, dpi=300
        )

        # 300 DPI时，scale = 72/300 = 0.24
        expected_scale = 72.0 / 300
        assert x_pt == 0.5 * 1000 * expected_scale  # 120.0
        assert y_pt == 0.5 * 1000 * expected_scale  # 120.0
        assert w_pt == 0.2 * 1000 * expected_scale  # 48.0
        assert h_pt == 0.1 * 1000 * expected_scale  # 24.0

    def test_chinese_font_setup(self):
        """测试中文字体设置"""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_pdf = Path(temp_dir) / "test.pdf"
            composer = OverlayComposer(output_pdf)

            # 应该有字体设置（可能是中文字体或Helvetica）
            assert composer.chinese_font in ["ChineseFont", "Helvetica"]

    @patch("apple_ocr.overlay_builder.pdfmetrics.registerFont")
    def test_chinese_font_fallback(self, mock_register):
        """测试中文字体回退机制"""
        # 模拟字体注册失败
        mock_register.side_effect = Exception("Font not found")

        with tempfile.TemporaryDirectory() as temp_dir:
            output_pdf = Path(temp_dir) / "test.pdf"
            composer = OverlayComposer(output_pdf)

            # 应该回退到Helvetica
            assert composer.chinese_font == "Helvetica"

    def test_overlay_composer_initialization(self):
        """测试OverlayComposer初始化"""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_pdf = Path(temp_dir) / "test.pdf"
            composer = OverlayComposer(output_pdf)

            assert composer.output_pdf == output_pdf
            assert composer.reader is None
            assert composer.total_pages == 0
            assert len(composer.overlays) == 0
            assert composer.chinese_font is not None

    def test_build_overlay_page(self):
        """测试构建overlay页面"""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_pdf = Path(temp_dir) / "test.pdf"
            composer = OverlayComposer(output_pdf)

            # 创建测试数据
            items = [
                BBoxItem(text="Hello", x=0.1, y=0.8, w=0.2, h=0.05),
                BBoxItem(text="世界", x=0.1, y=0.7, w=0.15, h=0.05),
            ]

            # 构建overlay
            overlay_bytes = composer._build_overlay_page(
                page_width_pt=612,
                page_height_pt=792,
                items=items,
                width_px=2000,
                height_px=2600,
                dpi=300,
            )

            # 应该返回PDF字节数据
            assert isinstance(overlay_bytes, bytes)
            assert len(overlay_bytes) > 0
            assert overlay_bytes.startswith(b"%PDF")

    def test_empty_items_overlay(self):
        """测试空文本项的overlay"""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_pdf = Path(temp_dir) / "test.pdf"
            composer = OverlayComposer(output_pdf)

            # 空项目列表
            overlay_bytes = composer._build_overlay_page(
                page_width_pt=612,
                page_height_pt=792,
                items=[],
                width_px=2000,
                height_px=2600,
                dpi=300,
            )

            # 应该仍然返回有效的PDF
            assert isinstance(overlay_bytes, bytes)
            assert len(overlay_bytes) > 0
            assert overlay_bytes.startswith(b"%PDF")

    def test_special_characters_handling(self):
        """测试特殊字符处理"""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_pdf = Path(temp_dir) / "test.pdf"
            composer = OverlayComposer(output_pdf)

            # 包含特殊字符的文本
            items = [
                BBoxItem(text="测试中文", x=0.1, y=0.8, w=0.2, h=0.05),
                BBoxItem(text="English", x=0.1, y=0.7, w=0.2, h=0.05),
                BBoxItem(text="123!@#", x=0.1, y=0.6, w=0.2, h=0.05),
                BBoxItem(text="", x=0.1, y=0.5, w=0.2, h=0.05),  # 空文本
            ]

            # 应该能处理各种字符而不崩溃
            overlay_bytes = composer._build_overlay_page(
                page_width_pt=612,
                page_height_pt=792,
                items=items,
                width_px=2000,
                height_px=2600,
                dpi=300,
            )

            assert isinstance(overlay_bytes, bytes)
            assert len(overlay_bytes) > 0

    def test_coordinate_edge_cases(self):
        """测试坐标边界情况"""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_pdf = Path(temp_dir) / "test.pdf"
            composer = OverlayComposer(output_pdf)

            # 边界坐标
            items = [
                BBoxItem(text="左上", x=0.0, y=1.0, w=0.1, h=0.05),
                BBoxItem(text="右下", x=0.9, y=0.0, w=0.1, h=0.05),
                BBoxItem(text="中心", x=0.5, y=0.5, w=0.1, h=0.05),
            ]

            overlay_bytes = composer._build_overlay_page(
                page_width_pt=612,
                page_height_pt=792,
                items=items,
                width_px=2000,
                height_px=2600,
                dpi=300,
            )

            assert isinstance(overlay_bytes, bytes)
            assert len(overlay_bytes) > 0
