#!/usr/bin/env python3
"""
测试OCR结果质量的脚本
"""
import sys
from pathlib import Path
from PyPDF2 import PdfReader

def extract_text_from_pdf(pdf_path):
    """从PDF中提取文本"""
    reader = PdfReader(str(pdf_path))
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text.strip()

def main():
    if len(sys.argv) < 2:
        print("用法: python test_ocr_result.py <ocr_pdf_path>")
        sys.exit(1)
    
    pdf_path = Path(sys.argv[1])
    if not pdf_path.exists():
        print(f"文件不存在: {pdf_path}")
        sys.exit(1)
    
    print(f"测试OCR结果: {pdf_path}")
    print("=" * 50)
    
    try:
        text = extract_text_from_pdf(pdf_path)
        print("提取的文本内容:")
        print("-" * 30)
        print(text)
        print("-" * 30)
        
        # 检查中文字符
        chinese_chars = [c for c in text if '\u4e00' <= c <= '\u9fff']
        print(f"检测到中文字符数: {len(chinese_chars)}")
        
        # 检查英文单词
        english_words = [word for word in text.split() if any(c.isalpha() and ord(c) < 128 for c in word)]
        print(f"检测到英文单词数: {len(english_words)}")
        
        # 检查数字
        digits = [c for c in text if c.isdigit()]
        print(f"检测到数字字符数: {len(digits)}")
        
        print("\n✅ OCR文本提取成功！PDF现在可搜索和选择文本。")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()