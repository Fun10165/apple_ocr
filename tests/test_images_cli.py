"""
CLI图片批处理到JSON的单元测试
"""

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from apple_ocr.cli import process_images


def _make_image(path: Path, size=(100, 50)):
    from PIL import Image

    img = Image.new("RGB", size, color=(255, 255, 255))
    img.save(path)


@patch("apple_ocr.cli.SwiftOCRClient")
def test_process_images_outputs_json(mock_client_class):
    """验证图片模式能写出聚合JSON文件（无需真实OCR）。"""
    with tempfile.TemporaryDirectory() as temp_dir:
        d = Path(temp_dir)
        img1 = d / "a.png"
        img2 = d / "b.jpg"
        _make_image(img1, size=(120, 80))
        _make_image(img2, size=(200, 60))

        out_json = d / "out.json"

        # 构造假OCR结果
        item1 = SimpleNamespace(
            text="hello", x=0.1, y=0.2, w=0.3, h=0.1, confidence=0.9
        )
        item2 = SimpleNamespace(
            text="world", x=0.5, y=0.5, w=0.2, h=0.2, confidence=0.95
        )

        res0 = SimpleNamespace(page_index=0, width=120, height=80, items=[item1])
        res1 = SimpleNamespace(page_index=1, width=200, height=60, items=[item2])

        mock_client = Mock()
        mock_client.collect_results.return_value = [res0, res1]
        mock_client_class.return_value = mock_client

        args = Mock()
        args.swift_bin = "test_swift_bin"
        args.image_exts = "png,jpg"
        args.no_progress = True

        process_images(d, out_json, args)

        assert out_json.exists(), "JSON输出文件应存在"
        data = json.loads(out_json.read_text(encoding="utf-8"))
        assert isinstance(data, list) and len(data) == 2
        assert data[0]["image"] == img1.name
        assert data[1]["image"] == img2.name
        assert "items" in data[0] and "items" in data[1]
        assert data[0]["items"][0]["text"] == "hello"
        assert data[1]["items"][0]["text"] == "world"
