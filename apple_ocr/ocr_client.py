import json
import logging
import os
import queue
import subprocess
import threading
from dataclasses import dataclass
from typing import List

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
    def __init__(self, swift_bin: str):
        self.swift_bin = swift_bin
        self.proc: subprocess.Popen | None = None
        self._out_thread: threading.Thread | None = None
        self._queue: "queue.Queue[OCRResult | Exception]" = queue.Queue()

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
        try:
            if self.proc and self.proc.stdin:
                # 发送结束信号
                self.proc.stdin.write(json.dumps({"cmd": "stop"}) + "\n")
                self.proc.stdin.flush()
        except Exception:
            pass
        if self.proc:
            self.proc.terminate()
            self.proc.wait(timeout=5)
        logger.info("Swift OCR 进程已结束")

    def send_image(self, image_path: str, page_index: int, width: int, height: int, dpi: int):
        payload = {
            "cmd": "ocr",
            "image_path": image_path,
            "page_index": page_index,
            "width": width,
            "height": height,
            "dpi": dpi,
            "languages": ["zh-Hans", "zh-Hant", "en-US"],  # 简体中文、繁体中文、英文
        }
        line = json.dumps(payload) + "\n"
        assert self.proc and self.proc.stdin
        self.proc.stdin.write(line)
        self.proc.stdin.flush()
        logger.debug(f"已发送OCR任务: page={page_index}")

    def _reader(self):
        assert self.proc and self.proc.stdout
        for line in self.proc.stdout:
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
            except Exception as e:
                self._queue.put(e)

    def collect_results(self, expected_pages: int):
        collected = 0
        while collected < expected_pages:
            item = self._queue.get()
            if isinstance(item, Exception):
                logger.error(f"OCR错误: {item}")
                raise item
            else:
                collected += 1
                logger.debug(f"收到OCR结果: page={item.page_index} items={len(item.items)}")
                yield item