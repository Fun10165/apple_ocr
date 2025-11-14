import json
import logging
import os
import queue
import subprocess
import threading
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger("apple_ocr")


@dataclass
class OCRItem:
    text: str
    x: float
    y: float
    w: float
    h: float
    confidence: float


@dataclass
class OCRResult:
    page_index: int
    width: int
    height: int
    items: List[OCRItem]


class SwiftOCRClient:
    def __init__(
        self,
        swift_bin: str,
        languages: Optional[List[str]] = None,
        recognition_level: Optional[str] = None,
        uses_cpu_only: Optional[bool] = None,
        auto_detect_language: Optional[bool] = None,
    ):
        self.swift_bin = swift_bin
        self.proc: subprocess.Popen | None = None
        self._out_thread: threading.Thread | None = None
        self._queue: "queue.Queue[OCRResult | Exception]" = queue.Queue()
        self.default_languages: List[str] = (
            languages if languages is not None else ["zh-Hans", "zh-Hant", "en-US"]
        )
        self.default_recognition_level: str = (
            recognition_level if recognition_level in {"accurate", "fast"} else "accurate"
        )
        self.default_uses_cpu_only: bool = uses_cpu_only if uses_cpu_only is not None else False
        self.default_auto_detect_language: bool = (
            auto_detect_language if auto_detect_language is not None else True
        )

    def start(self):
        if not os.path.exists(self.swift_bin):
            raise RuntimeError(f"Swift OCR 可执行文件不存在: {self.swift_bin}")
        self.proc = subprocess.Popen(
            [self.swift_bin],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._out_thread = threading.Thread(target=self._reader, daemon=True)
        self._out_thread.start()
        logger.info("Swift OCR 进程已启动")

    def stop(self):
        """停止Swift OCR进程并清理资源"""
        if self.proc is None:
            return
        
        # 发送结束信号
        try:
            if self.proc.stdin:
                self.proc.stdin.write(json.dumps({"cmd": "stop"}) + "\n")
                self.proc.stdin.flush()
                self.proc.stdin.close()
        except Exception as e:
            logger.debug(f"发送停止信号时出错: {e}")
        
        # 等待读取线程结束（如果还在运行）
        if self._out_thread and self._out_thread.is_alive():
            # 等待一小段时间让线程处理最后的输出
            self._out_thread.join(timeout=1.0)
        
        # 终止进程
        try:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("进程在5秒内未响应，强制终止")
                self.proc.kill()
                self.proc.wait()
        except Exception as e:
            logger.warning(f"终止进程时出错: {e}")
        
        # 关闭stdout和stderr
        try:
            if self.proc.stdout:
                self.proc.stdout.close()
            if self.proc.stderr:
                self.proc.stderr.close()
        except Exception:
            pass
        
        self.proc = None
        self._out_thread = None
        logger.info("Swift OCR 进程已结束")

    def send_image(self, image_path: str, page_index: int, width: int, height: int, dpi: int):
        if self.proc is None:
            raise RuntimeError("Swift OCR 进程未启动，请先调用 start()")
        if self.proc.stdin is None:
            raise RuntimeError("Swift OCR 进程 stdin 不可用")
        if self.proc.poll() is not None:
            raise RuntimeError(f"Swift OCR 进程已退出，退出码: {self.proc.poll()}")
        
        payload = {
            "cmd": "ocr",
            "image_path": image_path,
            "page_index": page_index,
            "width": width,
            "height": height,
            "dpi": dpi,
            "languages": self.default_languages,
            "recognition_level": self.default_recognition_level,
            "uses_cpu_only": self.default_uses_cpu_only,
            "auto_detect_language": self.default_auto_detect_language,
        }
        line = json.dumps(payload) + "\n"
        try:
            self.proc.stdin.write(line)
            self.proc.stdin.flush()
            logger.debug(f"已发送OCR任务: page={page_index}")
        except (BrokenPipeError, OSError) as e:
            raise RuntimeError(f"无法发送OCR任务到Swift进程: {e}") from e

    def _reader(self):
        if self.proc is None or self.proc.stdout is None:
            logger.error("Swift OCR 进程或 stdout 不可用")
            return
        
        try:
            def _iter_lines(stdout):
                try:
                    for line in stdout:
                        yield line
                except Exception:
                    while True:
                        try:
                            line = stdout.readline()
                        except Exception:
                            break
                        if not line:
                            break
                        yield line

            for line in _iter_lines(self.proc.stdout):
                if not isinstance(line, str):
                    continue
                # 检查进程状态
                if self.proc.poll() is not None:
                    exit_code = self.proc.poll()
                    error_msg = f"Swift OCR 进程意外退出，退出码: {exit_code}"
                    logger.error(error_msg)
                    self._queue.put(RuntimeError(error_msg))
                    break
                
                try:
                    msg = json.loads(line)
                    if msg.get("type") == "result":
                        items = [
                            OCRItem(
                                text=i["text"],
                                x=i["bbox"]["x"],
                                y=i["bbox"]["y"],
                                w=i["bbox"]["w"],
                                h=i["bbox"]["h"],
                                confidence=i.get("confidence", 1.0),
                            )
                            for i in msg["items"]
                        ]
                        res = OCRResult(
                            page_index=msg["page_index"],
                            width=msg["width"],
                            height=msg["height"],
                            items=items,
                        )
                        self._queue.put(res)
                    elif msg.get("type") == "error":
                        self._queue.put(RuntimeError(msg.get("message", "Swift OCR error")))
                except json.JSONDecodeError as e:
                    logger.warning(f"无法解析Swift OCR响应: {e}, 原始行: {line[:100]}")
                    self._queue.put(RuntimeError(f"JSON解析错误: {e}"))
                except Exception as e:
                    logger.error(f"处理Swift OCR响应时出错: {e}")
                    self._queue.put(e)
        except Exception as e:
            logger.error(f"读取Swift OCR输出时出错: {e}")
            self._queue.put(RuntimeError(f"读取进程输出失败: {e}"))
        finally:
            # 如果进程还在运行但stdout关闭，也标记错误
            if self.proc.poll() is None:
                logger.warning("Swift OCR stdout 流已关闭但进程仍在运行")

    def collect_results(self, expected_pages: int, timeout: float = 300.0):
        """
        收集OCR结果
        
        Args:
            expected_pages: 期望的页面数量
            timeout: 单个结果获取的超时时间（秒），默认300秒
            
        Yields:
            OCRResult: OCR识别结果
            
        Raises:
            RuntimeError: 如果进程退出或超时
            queue.Empty: 如果超时未收到结果
        """
        collected = 0
        while collected < expected_pages:
            # 检查进程状态
            if self.proc and self.proc.poll() is not None:
                exit_code = self.proc.poll()
                raise RuntimeError(f"Swift OCR 进程已退出，退出码: {exit_code}")
            
            try:
                item = self._queue.get(timeout=timeout)
            except queue.Empty:
                raise RuntimeError(
                    f"等待OCR结果超时（{timeout}秒）。已收集 {collected}/{expected_pages} 个结果"
                )
            
            if isinstance(item, Exception):
                logger.error(f"OCR错误: {item}")
                raise item
            else:
                collected += 1
                logger.debug(f"收到OCR结果: page={item.page_index} items={len(item.items)}")
                yield item
    
    def is_alive(self) -> bool:
        """检查Swift OCR进程是否还在运行"""
        return self.proc is not None and self.proc.poll() is None
