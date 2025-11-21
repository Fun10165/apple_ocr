"""
OCR客户端模块的单元测试
"""

import json
import queue
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from apple_ocr.ocr_client import OCRItem, OCRResult, SwiftOCRClient


class TestSwiftOCRClient:
    """SwiftOCRClient测试"""

    def test_client_initialization(self):
        """测试客户端初始化"""
        client = SwiftOCRClient(swift_bin="/fake/path/ocrbridge")
        assert client.swift_bin == "/fake/path/ocrbridge"
        assert client.proc is None
        assert client._out_thread is None

    @patch("apple_ocr.ocr_client.os.path.exists")
    def test_start_file_not_found(self, mock_exists):
        """测试启动时文件不存在"""
        mock_exists.return_value = False
        client = SwiftOCRClient(swift_bin="/fake/path/ocrbridge")

        with pytest.raises(RuntimeError, match="Swift OCR 可执行文件不存在"):
            client.start()

    @patch("apple_ocr.ocr_client.subprocess.Popen")
    @patch("apple_ocr.ocr_client.os.path.exists")
    def test_start_success(self, mock_exists, mock_popen):
        """测试成功启动"""
        mock_exists.return_value = True
        mock_proc = Mock()
        mock_proc.stdin = Mock()
        mock_proc.stdout = Mock()
        mock_proc.poll.return_value = None  # 进程运行中
        mock_popen.return_value = mock_proc

        client = SwiftOCRClient(swift_bin="/fake/path/ocrbridge")
        client.start()

        assert client.proc == mock_proc
        assert client._out_thread is not None
        mock_popen.assert_called_once()

    @patch("apple_ocr.ocr_client.subprocess.Popen")
    @patch("apple_ocr.ocr_client.os.path.exists")
    def test_send_image_process_not_started(self, mock_exists, mock_popen):
        """测试发送图像时进程未启动"""
        mock_exists.return_value = True
        client = SwiftOCRClient(swift_bin="/fake/path/ocrbridge")

        with pytest.raises(RuntimeError, match="Swift OCR 进程未启动"):
            client.send_image("test.png", 0, 100, 100, 0)

    @patch("apple_ocr.ocr_client.subprocess.Popen")
    @patch("apple_ocr.ocr_client.os.path.exists")
    def test_send_image_process_exited(self, mock_exists, mock_popen):
        """测试发送图像时进程已退出"""
        mock_exists.return_value = True
        mock_proc = Mock()
        mock_proc.stdin = Mock()
        mock_proc.poll.return_value = 1  # 进程已退出，退出码1
        mock_popen.return_value = mock_proc

        client = SwiftOCRClient(swift_bin="/fake/path/ocrbridge")
        client.proc = mock_proc

        with pytest.raises(RuntimeError, match="Swift OCR 进程已退出"):
            client.send_image("test.png", 0, 100, 100, 0)

    @patch("apple_ocr.ocr_client.subprocess.Popen")
    @patch("apple_ocr.ocr_client.os.path.exists")
    def test_send_image_success(self, mock_exists, mock_popen):
        """测试成功发送图像"""
        mock_exists.return_value = True
        mock_proc = Mock()
        mock_stdin = Mock()
        mock_proc.stdin = mock_stdin
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        client = SwiftOCRClient(
            swift_bin="/fake/path/ocrbridge",
            languages=["en-US"],
            recognition_level="fast",
            uses_cpu_only=True,
            auto_detect_language=False,
        )
        client.proc = mock_proc

        client.send_image("test.png", 0, 100, 100, 300)

        mock_stdin.write.assert_called_once()
        mock_stdin.flush.assert_called_once()
        # 验证发送的JSON包含正确字段
        call_args = mock_stdin.write.call_args[0][0]
        payload = json.loads(call_args.rstrip("\n"))
        assert payload["cmd"] == "ocr"
        assert payload["image_path"] == "test.png"
        assert payload["page_index"] == 0
        assert payload["width"] == 100
        assert payload["height"] == 100
        assert payload["dpi"] == 300
        assert payload["languages"] == ["en-US"]
        assert payload["recognition_level"] == "fast"
        assert payload["uses_cpu_only"] is True
        assert payload["auto_detect_language"] is False

    def test_is_alive(self):
        """测试进程存活检查"""
        client = SwiftOCRClient(swift_bin="/fake/path/ocrbridge")
        assert client.is_alive() is False

        mock_proc = Mock()
        mock_proc.poll.return_value = None  # 运行中
        client.proc = mock_proc
        assert client.is_alive() is True

        mock_proc.poll.return_value = 0  # 已退出
        assert client.is_alive() is False

    def test_collect_results_success(self):
        """测试成功收集结果"""
        client = SwiftOCRClient(swift_bin="/fake/path/ocrbridge")
        mock_proc = Mock()
        mock_proc.poll.return_value = None
        client.proc = mock_proc

        # 添加测试结果到队列
        result1 = OCRResult(
            page_index=0,
            width=100,
            height=100,
            items=[OCRItem(text="hello", x=0.1, y=0.2, w=0.3, h=0.1, confidence=0.9)],
        )
        result2 = OCRResult(
            page_index=1,
            width=200,
            height=200,
            items=[OCRItem(text="world", x=0.5, y=0.5, w=0.2, h=0.2, confidence=0.95)],
        )

        client._queue.put(result1)
        client._queue.put(result2)

        results = list(client.collect_results(2))
        assert len(results) == 2
        assert results[0].page_index == 0
        assert results[1].page_index == 1

    def test_collect_results_with_exception(self):
        """测试收集结果时遇到异常"""
        client = SwiftOCRClient(swift_bin="/fake/path/ocrbridge")
        mock_proc = Mock()
        mock_proc.poll.return_value = None
        client.proc = mock_proc

        error = RuntimeError("OCR处理失败")
        client._queue.put(error)

        with pytest.raises(RuntimeError, match="OCR处理失败"):
            next(client.collect_results(1))

    def test_collect_results_process_exited(self):
        """测试收集结果时进程退出"""
        client = SwiftOCRClient(swift_bin="/fake/path/ocrbridge")
        mock_proc = Mock()
        mock_proc.poll.return_value = 1  # 进程退出
        client.proc = mock_proc

        with pytest.raises(RuntimeError, match="Swift OCR 进程已退出"):
            next(client.collect_results(1))

    def test_collect_results_timeout(self):
        """测试收集结果超时"""
        client = SwiftOCRClient(swift_bin="/fake/path/ocrbridge")
        mock_proc = Mock()
        mock_proc.poll.return_value = None
        client.proc = mock_proc

        with pytest.raises(RuntimeError, match="等待OCR结果超时"):
            next(client.collect_results(1, timeout=0.1))  # 很短的超时

    @patch("apple_ocr.ocr_client.subprocess.Popen")
    @patch("apple_ocr.ocr_client.os.path.exists")
    def test_stop_with_stdin(self, mock_exists, mock_popen):
        """测试停止进程（有stdin）"""
        mock_exists.return_value = True
        mock_proc = Mock()
        mock_stdin = Mock()
        mock_proc.stdin = mock_stdin
        mock_proc.wait.return_value = None
        mock_popen.return_value = mock_proc

        client = SwiftOCRClient(swift_bin="/fake/path/ocrbridge")
        client.start()
        client.stop()

        mock_stdin.write.assert_called_once()
        mock_stdin.flush.assert_called_once()
        mock_proc.terminate.assert_called_once()
        mock_proc.wait.assert_called_once_with(timeout=5)

    @patch("apple_ocr.ocr_client.subprocess.Popen")
    @patch("apple_ocr.ocr_client.os.path.exists")
    def test_stop_no_stdin(self, mock_exists, mock_popen):
        """测试停止进程（无stdin）"""
        mock_exists.return_value = True
        mock_proc = Mock()
        mock_proc.stdin = None
        mock_proc.wait.return_value = None
        mock_popen.return_value = mock_proc

        client = SwiftOCRClient(swift_bin="/fake/path/ocrbridge")
        client.start()
        client.stop()

        mock_proc.terminate.assert_called_once()
        mock_proc.wait.assert_called_once_with(timeout=5)

    def test_reader_handles_json_error(self):
        """测试读取器处理JSON错误"""
        client = SwiftOCRClient(swift_bin="/fake/path/ocrbridge")
        mock_proc = Mock()
        mock_proc.poll.return_value = None

        # 模拟stdout返回无效JSON
        mock_stdout = MagicMock()
        mock_stdout.__iter__.return_value = iter(["invalid json line\n"])
        mock_proc.stdout = mock_stdout
        client.proc = mock_proc

        # 启动读取器线程
        reader_thread = threading.Thread(target=client._reader, daemon=True)
        reader_thread.start()

        # 等待线程处理
        time.sleep(0.1)

        # 应该有一个异常在队列中
        assert not client._queue.empty()
        item = client._queue.get()
        assert isinstance(item, Exception) or isinstance(item, RuntimeError)
