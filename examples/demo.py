#!/usr/bin/env python3
"""
Apple OCR 演示脚本

展示如何使用API接口进行OCR处理
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from apple_ocr.api import AppleOCR, extract_text_from_pdf, create_searchable_pdf


def demo_api_usage():
    """演示API使用方法"""
    print("🚀 Apple OCR API 演示")
    print("=" * 50)
    
    # 创建测试PDF
    test_pdf = Path(__file__).parent / "test_chinese.pdf"
    if not test_pdf.exists():
        print(f"❌ 测试文件不存在: {test_pdf}")
        print("请先运行: uv run python scripts/make_test_pdf.py examples/test_chinese.pdf")
        return
    
    print(f"📄 使用测试文件: {test_pdf}")
    
    # 方法1：使用便捷函数提取文本
    print("\n📝 方法1：提取文本内容")
    print("-" * 30)
    
    try:
        text_data = extract_text_from_pdf(test_pdf, pages="1")
        
        for page_data in text_data:
            print(f"页面 {page_data['page_index'] + 1}:")
            for i, item in enumerate(page_data['items'], 1):
                print(f"  {i}. '{item['text']}' (置信度: {item['confidence']:.2f})")
        
        print(f"\n✅ 成功提取 {len(text_data)} 页文本")
        
    except Exception as e:
        print(f"❌ 文本提取失败: {e}")
        return
    
    # 方法2：使用类接口创建可搜索PDF
    print("\n📚 方法2：创建可搜索PDF")
    print("-" * 30)
    
    try:
        output_pdf = Path(__file__).parent / "demo_searchable.pdf"
        
        # 创建OCR实例
        ocr = AppleOCR(dpi=300)
        
        # 创建可搜索PDF
        ocr.create_searchable_pdf(test_pdf, output_pdf, pages="1")
        
        print(f"✅ 可搜索PDF已创建: {output_pdf}")
        
        # 验证结果
        from apple_ocr.pdf_to_images import get_pdf_page_count
        page_count = get_pdf_page_count(output_pdf)
        print(f"📊 输出PDF页数: {page_count}")
        
    except Exception as e:
        print(f"❌ PDF创建失败: {e}")
        return
    
    # 方法3：使用便捷函数创建可搜索PDF
    print("\n🔧 方法3：便捷函数创建可搜索PDF")
    print("-" * 30)
    
    try:
        output_pdf2 = Path(__file__).parent / "demo_convenient.pdf"
        
        create_searchable_pdf(test_pdf, output_pdf2, pages="1", dpi=300)
        
        print(f"✅ 便捷方式PDF已创建: {output_pdf2}")
        
    except Exception as e:
        print(f"❌ 便捷方式失败: {e}")
    
    print("\n🎉 演示完成！")
    print("\n💡 提示：")
    print("- 使用 extract_text_from_pdf() 仅提取文本")
    print("- 使用 create_searchable_pdf() 创建可搜索PDF")
    print("- 使用 AppleOCR 类获得更多控制")
    print("- 页面范围支持: '1', '1,3,5', '1-5', '1,3,5-10'")


def demo_page_ranges():
    """演示页面范围功能"""
    print("\n📖 页面范围演示")
    print("=" * 50)
    
    from apple_ocr.page_parser import parse_pages, format_pages
    
    test_cases = [
        ("1", 10),
        ("1,3,5", 10),
        ("1-5", 10),
        ("1,3,5-7,10", 15),
        ("1-3,5,8-10,15", 20)
    ]
    
    for page_spec, total_pages in test_cases:
        try:
            parsed = parse_pages(page_spec, total_pages)
            formatted = format_pages(parsed)
            print(f"输入: '{page_spec}' (总页数: {total_pages})")
            print(f"  解析结果: {parsed}")
            print(f"  格式化: '{formatted}'")
            print()
        except ValueError as e:
            print(f"❌ 错误: '{page_spec}' -> {e}")


if __name__ == "__main__":
    demo_api_usage()
    demo_page_ranges()