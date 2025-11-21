"""
CLI模块的单元测试
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from apple_ocr.cli import main, setup_logging


class TestCLI:
    """CLI测试"""

    def test_setup_logging_verbose(self):
        """测试详细日志设置"""
        with patch("apple_ocr.cli.logging.basicConfig") as mock_config:
            setup_logging(verbose=True)
            mock_config.assert_called_once()
            args, kwargs = mock_config.call_args
            assert kwargs["level"] == 10  # DEBUG level

    def test_setup_logging_normal(self):
        """测试普通日志设置"""
        with patch("apple_ocr.cli.logging.basicConfig") as mock_config:
            setup_logging(verbose=False)
            mock_config.assert_called_once()
            args, kwargs = mock_config.call_args
            assert kwargs["level"] == 20  # INFO level

    @patch("apple_ocr.cli.process_one")
    @patch("apple_ocr.cli.sys.argv")
    def test_main_single_file(self, mock_argv, mock_process):
        """测试单文件处理"""
        with tempfile.TemporaryDirectory() as temp_dir:
            input_pdf = Path(temp_dir) / "input.pdf"
            output_pdf = Path(temp_dir) / "output.pdf"

            # 创建虚拟输入文件
            input_pdf.touch()

            mock_argv.__getitem__.side_effect = [
                "apple-ocr",
                "--input",
                str(input_pdf),
                "--output",
                str(output_pdf),
                "--dpi",
                "300",
                "--workers",
                "4",
            ]

            with patch(
                "apple_ocr.cli.argparse.ArgumentParser.parse_args"
            ) as mock_parse:
                args = Mock()
                args.input = str(input_pdf)
                args.output = str(output_pdf)
                args.dpi = 300
                args.workers = 4
                args.verbose = False
                args.pages = None
                args.swift_bin = "test_bin"
                mock_parse.return_value = args

                main()

                mock_process.assert_called_once()

    @patch("apple_ocr.cli.process_one")
    @patch("apple_ocr.cli.sys.argv")
    def test_main_directory_processing(self, mock_argv, mock_process):
        """测试目录批量处理"""
        with tempfile.TemporaryDirectory() as temp_dir:
            input_dir = Path(temp_dir) / "input"
            output_dir = Path(temp_dir) / "output"
            input_dir.mkdir()

            # 创建测试PDF文件
            (input_dir / "test1.pdf").touch()
            (input_dir / "test2.pdf").touch()

            with patch(
                "apple_ocr.cli.argparse.ArgumentParser.parse_args"
            ) as mock_parse:
                args = Mock()
                args.input = str(input_dir)
                args.output = str(output_dir)
                args.dpi = 300
                args.workers = 4
                args.verbose = False
                args.pages = None
                args.swift_bin = "test_bin"
                mock_parse.return_value = args

                main()

                # 应该处理两个PDF文件
                assert mock_process.call_count == 2

    @patch("apple_ocr.cli.sys.exit")
    def test_main_no_pdf_files(self, mock_exit):
        """测试目录中没有PDF文件的情况"""
        with tempfile.TemporaryDirectory() as temp_dir:
            input_dir = Path(temp_dir) / "input"
            output_dir = Path(temp_dir) / "output"
            input_dir.mkdir()

            # 创建非PDF文件
            (input_dir / "test.txt").touch()

            with patch(
                "apple_ocr.cli.argparse.ArgumentParser.parse_args"
            ) as mock_parse:
                args = Mock()
                args.input = str(input_dir)
                args.output = str(output_dir)
                args.dpi = 300
                args.workers = 4
                args.verbose = False
                args.pages = None
                args.swift_bin = "test_bin"
                mock_parse.return_value = args

                main()

                mock_exit.assert_called_once_with(1)

    @patch("apple_ocr.cli.get_pdf_page_count")
    @patch("apple_ocr.cli.parse_pages")
    @patch("apple_ocr.cli.format_pages")
    @patch("apple_ocr.cli.ocrmypdf")
    def test_process_one_with_pages(
        self, mock_ocr, mock_format, mock_parse, mock_count
    ):
        """测试带页面选择（ocrmypdf 引擎）"""
        from apple_ocr.cli import process_one

        mock_count.return_value = 10
        mock_parse.return_value = [0, 2, 4]  # 选择第1,3,5页（0-based）
        mock_format.return_value = "1,3,5"  # 转为1-based字符串

        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "test.pdf"
            output_path = Path(temp_dir) / "output.pdf"
            pdf_path.touch()

            args = Mock()
            args.pages = "1,3,5"
            args.engine = "ocrmypdf"
            args.no_progress = False

            process_one(pdf_path, output_path, args)

            mock_count.assert_called_once_with(pdf_path)
            mock_parse.assert_called_once_with("1,3,5", 10)
            mock_format.assert_called_once()

            assert mock_ocr.ocr.called
            call_args = mock_ocr.ocr.call_args
            assert call_args.kwargs.get("input_file") == str(pdf_path)
            assert call_args.kwargs.get("output_file") == str(output_path)
            assert call_args.kwargs.get("pages") == "1,3,5"

    @patch("apple_ocr.cli.sys.exit")
    @patch("apple_ocr.cli.get_pdf_page_count")
    @patch("apple_ocr.cli.parse_pages")
    def test_process_one_invalid_pages(self, mock_parse, mock_count, mock_exit):
        """测试无效页面范围处理"""
        from apple_ocr.cli import process_one

        mock_count.return_value = 10
        mock_parse.side_effect = ValueError("页面号超出范围")

        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "test.pdf"
            output_path = Path(temp_dir) / "output.pdf"

            args = Mock()
            args.pages = "15"  # 超出范围
            args.dpi = 300
            args.workers = 4
            args.swift_bin = "test_bin"
            args.engine = "ocrmypdf"

            process_one(pdf_path, output_path, args)

            mock_exit.assert_called_once_with(1)
