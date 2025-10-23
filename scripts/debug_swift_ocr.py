#!/usr/bin/env python3
"""
直接测试Swift OCR输出的调试脚本
"""
import json
import subprocess
import sys
from pathlib import Path

def test_swift_ocr_directly():
    swift_bin = Path(__file__).parent.parent / "swift" / "OCRBridge" / ".build" / "release" / "ocrbridge"
    
    if not swift_bin.exists():
        print(f"Swift OCR可执行文件不存在: {swift_bin}")
        return
    
    # 使用测试图片
    test_image = Path(__file__).parent.parent / ".test_2_images" / "page_000000.png"
    if not test_image.exists():
        print(f"测试图片不存在: {test_image}")
        return
    
    print(f"测试Swift OCR直接输出...")
    print(f"图片路径: {test_image}")
    
    # 启动Swift进程
    proc = subprocess.Popen(
        [str(swift_bin)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    
    # 发送OCR请求
    request = {
        "cmd": "ocr",
        "image_path": str(test_image),
        "page_index": 0,
        "width": 2481,
        "height": 3508,
        "dpi": 300,
        "languages": ["zh-Hans", "zh-Hant", "en-US"]
    }
    
    try:
        # 发送请求
        input_data = json.dumps(request) + "\n" + json.dumps({"cmd": "stop"}) + "\n"
        
        # 读取输出
        stdout, stderr = proc.communicate(input=input_data, timeout=10)
        
        print("Swift OCR 输出:")
        print("=" * 50)
        for line in stdout.strip().split('\n'):
            if line.strip():
                try:
                    result = json.loads(line)
                    if result.get("type") == "result":
                        print(f"页面 {result['page_index']} 识别结果:")
                        for i, item in enumerate(result.get("items", [])):
                            print(f"  {i+1}. 文本: '{item['text']}'")
                            print(f"     坐标: x={item['bbox']['x']:.3f}, y={item['bbox']['y']:.3f}")
                            print(f"     尺寸: w={item['bbox']['w']:.3f}, h={item['bbox']['h']:.3f}")
                            print(f"     置信度: {item.get('confidence', 0):.3f}")
                            print()
                    elif result.get("type") == "error":
                        print(f"错误: {result.get('message')}")
                except json.JSONDecodeError:
                    print(f"无法解析JSON: {line}")
        
        if stderr:
            print("错误输出:")
            print(stderr)
            
    except subprocess.TimeoutExpired:
        proc.kill()
        print("Swift OCR 超时")
    except Exception as e:
        print(f"测试失败: {e}")

if __name__ == "__main__":
    test_swift_ocr_directly()