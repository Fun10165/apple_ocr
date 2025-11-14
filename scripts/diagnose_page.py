#!/usr/bin/env python3
"""
诊断PDF特定页面的OCR问题

用于检查特定页面OCR结果，查找可能导致HOCR XML格式问题的字符
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from apple_ocr.api import AppleOCR
import json


def diagnose_page(pdf_path: str, page_num: int):
    """诊断指定页面的OCR问题"""
    pdf_path = Path(pdf_path)
    page_num = int(page_num)
    
    print(f"正在诊断 PDF: {pdf_path.name}, 页面: {page_num}")
    print("=" * 60)
    
    # 使用 Swift OCR 提取文本（避免 ocrmypdf 的问题）
    ocr = AppleOCR()
    try:
        results = ocr.extract_text(pdf_path, pages=str(page_num))
        
        if not results:
            print("❌ 未获取到OCR结果")
            return
        
        result = results[0]  # 应该只有一个页面
        print(f"\n✅ 成功识别 {len(result['items'])} 个文本项\n")
        
        # 检查每个文本项是否有可疑字符
        suspicious_items = []
        all_text = ""
        
        for i, item in enumerate(result['items']):
            text = item['text']
            all_text += text + " "
            
            # 检查是否包含可能导致XML问题的字符
            suspicious_chars = []
            for char in text:
                # XML 非法字符：控制字符（除了 \t, \n, \r）和某些 Unicode 字符
                if ord(char) < 32 and char not in ['\t', '\n', '\r']:
                    suspicious_chars.append((char, ord(char), f"\\x{ord(char):02x}"))
                elif ord(char) in [0x7F, 0x8, 0xC, 0x1A]:  # DEL, BS, FF, SUB
                    suspicious_chars.append((char, ord(char), f"\\x{ord(char):02x}"))
                elif 0xD800 <= ord(char) <= 0xDFFF:  # 代理对
                    suspicious_chars.append((char, ord(char), f"U+{ord(char):04X}"))
            
            if suspicious_chars:
                suspicious_items.append({
                    'index': i,
                    'text': text,
                    'chars': suspicious_chars,
                    'position': (item['x'], item['y'])
                })
        
        # 显示统计信息
        print(f"总文本长度: {len(all_text)} 字符")
        print(f"可疑文本项: {len(suspicious_items)}\n")
        
        # 显示前10个文本项示例
        print("前10个识别的文本项:")
        print("-" * 60)
        for i, item in enumerate(result['items'][:10]):
            text_repr = repr(item['text'][:50])  # 使用repr显示特殊字符
            print(f"  {i+1}. {text_repr}")
            if len(item['text']) > 50:
                print(f"     ... (共 {len(item['text'])} 字符)")
        
        # 显示可疑字符详情
        if suspicious_items:
            print("\n" + "=" * 60)
            print("⚠️  发现可疑字符（可能导致XML格式问题）:")
            print("=" * 60)
            for item in suspicious_items[:5]:  # 只显示前5个
                print(f"\n文本项 #{item['index']}:")
                print(f"  位置: ({item['position'][0]:.3f}, {item['position'][1]:.3f})")
                print(f"  文本: {repr(item['text'])}")
                print(f"  可疑字符:")
                for char, code, repr_code in item['chars']:
                    print(f"    - 字符: {repr(char)} | Unicode: U+{code:04X} ({repr_code})")
            
            if len(suspicious_items) > 5:
                print(f"\n  ... 还有 {len(suspicious_items) - 5} 个文本项包含可疑字符")
        
        # 保存详细结果到JSON
        output_file = pdf_path.parent / f"{pdf_path.stem}_page{page_num}_diagnosis.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'page': page_num,
                'total_items': len(result['items']),
                'suspicious_items_count': len(suspicious_items),
                'suspicious_items': suspicious_items[:20],  # 保存前20个
                'all_items': result['items']
            }, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ 详细结果已保存到: {output_file}")
        
        # 提供建议
        if suspicious_items:
            print("\n" + "=" * 60)
            print("💡 修复建议:")
            print("=" * 60)
            print("1. 这些字符需要在生成HOCR XML时进行转义或过滤")
            print("2. 可能需要在 ocrmypdf-appleocr 插件中处理这些字符")
            print("3. 或者预处理PDF，清理这些特殊字符")
            print("\n建议检查 ocrmypdf-appleocr 插件的源码，")
            print("看看是否有字符清理或转义的逻辑。")
        else:
            print("\n✅ 未发现明显的可疑字符")
            print("   问题可能在其他地方，建议检查 ocrmypdf-appleocr 插件的HOCR生成逻辑")
        
    except Exception as e:
        print(f"❌ 诊断失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("用法: python scripts/diagnose_page.py <pdf文件> <页码>")
        print("示例: python scripts/diagnose_page.py test.pdf 24")
        sys.exit(1)
    
    diagnose_page(sys.argv[1], sys.argv[2])

