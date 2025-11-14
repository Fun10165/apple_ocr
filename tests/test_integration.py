"""
集成测试：测试完整的工作流程
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

from apple_ocr.api import AppleOCR, extract_text_from_pdf, create_searchable_pdf
from apple_ocr.ocr_client import SwiftOCRClient, OCRItem, OCRResult
from apple_ocr.pdf_to_images import render_pdf_stream, get_pdf_page_count


class TestIntegration:
    """集成测试"""

    @patch('apple_ocr.api.SwiftOCRClient')
    @patch('apple_ocr.api.render_pdf_stream')
    @patch('apple_ocr.api.get_pdf_page_count')
    def test_extract_text_from_pdf_integration(self, mock_count, mock_render, mock_client_class):
        """测试PDF文本提取的完整流程"""
        # 模拟PDF有2页
        mock_count.return_value = 2
        
        # 模拟页面渲染结果
        from apple_ocr.pdf_to_images import PageImage
        page1 = PageImage(
            page_index=0,
            image_path="/tmp/page_000000.png",
            width=100,
            height=100,
            dpi=300,
            total_pages=2
        )
        page2 = PageImage(
            page_index=1,
            image_path="/tmp/page_000001.png",
            width=200,
            height=200,
            dpi=300,
            total_pages=2
        )
        mock_render.return_value = iter([page1, page2])
        
        # 模拟OCR客户端
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # 模拟OCR结果
        result1 = OCRResult(
            page_index=0,
            width=100,
            height=100,
            items=[OCRItem(text="Hello", x=0.1, y=0.2, w=0.3, h=0.1, confidence=0.9)]
        )
        result2 = OCRResult(
            page_index=1,
            width=200,
            height=200,
            items=[OCRItem(text="World", x=0.5, y=0.5, w=0.2, h=0.2, confidence=0.95)]
        )
        mock_client.collect_results.return_value = iter([result1, result2])
        
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "test.pdf"
            pdf_path.touch()
            
            ocr = AppleOCR()
            results = ocr.extract_text(pdf_path, pages="1-2")
            
            assert len(results) == 2
            assert results[0]["page_index"] == 0
            assert results[0]["items"][0]["text"] == "Hello"
            assert results[1]["page_index"] == 1
            assert results[1]["items"][0]["text"] == "World"
            
            mock_client.start.assert_called_once()
            mock_client.stop.assert_called_once()

    @patch('apple_ocr.api.SwiftOCRClient')
    def test_extract_text_from_images_integration(self, mock_client_class):
        """测试图片批量处理的完整流程"""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        result1 = OCRResult(
            page_index=0,
            width=100,
            height=100,
            items=[OCRItem(text="Test1", x=0.1, y=0.2, w=0.3, h=0.1, confidence=0.9)]
        )
        result2 = OCRResult(
            page_index=1,
            width=200,
            height=200,
            items=[OCRItem(text="Test2", x=0.5, y=0.5, w=0.2, h=0.2, confidence=0.95)]
        )
        mock_client.collect_results.return_value = iter([result1, result2])
        
        with tempfile.TemporaryDirectory() as temp_dir:
            img1 = Path(temp_dir) / "test1.png"
            img2 = Path(temp_dir) / "test2.png"
            img1.touch()
            img2.touch()
            
            ocr = AppleOCR()
            results = ocr.extract_text_from_images([img1, img2])
            
            assert len(results) == 2
            assert results[0]["image"] == "test1.png"
            assert results[1]["image"] == "test2.png"
            
            mock_client.start.assert_called_once()
            mock_client.stop.assert_called_once()

    @patch('apple_ocr.api.ocrmypdf')
    @patch('apple_ocr.api.get_pdf_page_count')
    def test_create_searchable_pdf_integration(self, mock_count, mock_ocr):
        """测试创建可搜索PDF的完整流程"""
        mock_count.return_value = 5
        
        with tempfile.TemporaryDirectory() as temp_dir:
            input_pdf = Path(temp_dir) / "input.pdf"
            output_pdf = Path(temp_dir) / "output.pdf"
            input_pdf.touch()
            
            ocr = AppleOCR()
            ocr.create_searchable_pdf(input_pdf, output_pdf, pages="1-3", language="chi_sim")
            
            # 验证ocrmypdf被正确调用
            mock_ocr.ocr.assert_called_once()
            call_kwargs = mock_ocr.ocr.call_args.kwargs
            assert call_kwargs["input_file"] == str(input_pdf)
            assert call_kwargs["output_file"] == str(output_pdf)
            assert call_kwargs["language"] == "chi_sim"
            assert "ocrmypdf_appleocr" in call_kwargs["plugins"]

    def test_page_parser_integration(self):
        """测试页面解析器在实际场景中的应用"""
        from apple_ocr.page_parser import parse_pages, format_pages
        
        # 模拟PDF有10页
        total_pages = 10
        
        # 测试各种页面范围
        test_cases = [
            ("1-3", [0, 1, 2]),
            ("1,3,5", [0, 2, 4]),
            ("1-3,5,8-10", [0, 1, 2, 4, 7, 8, 9]),
        ]
        
        for page_spec, expected in test_cases:
            parsed = parse_pages(page_spec, total_pages)
            assert parsed == expected, f"页面范围 '{page_spec}' 解析错误"
            
            # 测试往返转换
            formatted = format_pages(parsed)
            reparsed = parse_pages(formatted, total_pages)
            assert reparsed == parsed, f"页面范围 '{page_spec}' 往返转换失败"

    @patch('apple_ocr.cli.process_one')
    @patch('apple_ocr.cli.sys.argv')
    def test_cli_image_mode_integration(self, mock_argv, mock_process_one):
        """测试CLI图片模式的完整流程"""
        from apple_ocr.cli import main, process_images
        
        with tempfile.TemporaryDirectory() as temp_dir:
            img_dir = Path(temp_dir) / "images"
            img_dir.mkdir()
            (img_dir / "test1.png").touch()
            (img_dir / "test2.jpg").touch()
            
            output_json = Path(temp_dir) / "output.json"
            
            args = Mock()
            args.swift_bin = "/fake/path"
            args.image_exts = "png,jpg"
            args.no_progress = True
            
            # Mock API调用
            with patch('apple_ocr.cli.AppleOCR') as mock_ocr_class:
                mock_ocr = Mock()
                mock_ocr_class.return_value = mock_ocr
                mock_ocr.extract_text_from_images.return_value = [
                    {"image": "test1.png", "width": 100, "height": 100, "items": []},
                    {"image": "test2.jpg", "width": 200, "height": 200, "items": []}
                ]
                
                process_images(img_dir, output_json, args)
                
                assert output_json.exists()
                with open(output_json, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    assert len(data) == 2

    @patch('apple_ocr.ocr_client.subprocess.Popen')
    @patch('apple_ocr.ocr_client.os.path.exists')
    def test_ocr_client_lifecycle(self, mock_exists, mock_popen):
        """测试OCR客户端完整生命周期"""
        mock_exists.return_value = True
        mock_proc = Mock()
        mock_proc.stdin = Mock()
        mock_proc.stdout = MagicMock()
        mock_proc.stdout.__iter__.return_value = iter([])
        mock_proc.poll.return_value = None
        mock_proc.wait.return_value = None
        mock_popen.return_value = mock_proc
        
        client = SwiftOCRClient(swift_bin="/fake/path")
        
        # 启动
        client.start()
        assert client.is_alive()
        
        # 发送任务
        client.send_image("test.png", 0, 100, 100, 300)
        
        # 停止
        client.stop()
        assert not client.is_alive()
        mock_proc.terminate.assert_called_once()
