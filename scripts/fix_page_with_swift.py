#!/usr/bin/env python3
"""
使用 Swift 引擎处理有问题的页面，然后合并回原PDF

这个脚本可以：
1. 使用 ocrmypdf 处理大部分页面
2. 使用 swift 引擎处理有问题的页面
3. 合并结果
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from apple_ocr.cli import process_one
from apple_ocr.pdf_to_images import get_pdf_page_count
from apple_ocr.page_parser import parse_pages, format_pages
from types import SimpleNamespace


def merge_pdfs_with_page_replacement(original_pdf, ocrmypdf_result, swift_result, problem_pages, output_pdf):
    """合并PDF，用swift处理的结果替换问题页面"""
    try:
        from pypdf import PdfReader, PdfWriter
        
        reader_ocr = PdfReader(str(ocrmypdf_result))
        reader_swift = PdfReader(str(swift_result))
        writer = PdfWriter()
        
        # 获取swift处理的页面
        swift_pages_dict = {}
        for page_idx in problem_pages:
            if page_idx < len(reader_swift.pages):
                swift_pages_dict[page_idx] = reader_swift.pages[page_idx]
        
        # 合并页面
        for i in range(len(reader_ocr.pages)):
            if i in swift_pages_dict:
                # 使用swift处理的页面
                writer.add_page(swift_pages_dict[i])
                print(f"  使用 Swift 引擎的页面: {i+1}")
            else:
                # 使用ocrmypdf处理的页面
                writer.add_page(reader_ocr.pages[i])
        
        # 保留元数据
        if reader_ocr.metadata:
            writer.add_metadata(reader_ocr.metadata)
        
        with open(output_pdf, 'wb') as f:
            writer.write(f)
        
        print(f"✅ 合并完成: {output_pdf}")
        return True
    except Exception as e:
        print(f"❌ 合并失败: {e}")
        return False


def process_pdf_with_fallback(pdf_path: Path, output_pdf: Path, problem_pages: list, args):
    """使用混合方法处理PDF：ocrmypdf处理大部分页面，swift处理问题页面"""
    print(f"处理 PDF: {pdf_path.name}")
    print(f"问题页面: {[p+1 for p in problem_pages]} (1-based)")
    
    total_pages = get_pdf_page_count(pdf_path)
    all_pages = set(range(total_pages))
    problem_pages_set = set(problem_pages)
    normal_pages = sorted(list(all_pages - problem_pages_set))
    
    print(f"正常页面数: {len(normal_pages)}, 问题页面数: {len(problem_pages)}")
    
    # 创建临时输出文件
    temp_ocr = output_pdf.parent / f"{output_pdf.stem}_temp_ocr.pdf"
    temp_swift = output_pdf.parent / f"{output_pdf.stem}_temp_swift.pdf"
    
    try:
        # 1. 使用 ocrmypdf 处理正常页面
        if normal_pages:
            print(f"\n步骤1: 使用 ocrmypdf 处理 {len(normal_pages)} 个正常页面...")
            normal_pages_str = format_pages(normal_pages)
            
            args_ocr = SimpleNamespace(**vars(args))
            args_ocr.pages = normal_pages_str
            args_ocr.engine = "ocrmypdf"
            
            try:
                process_one(pdf_path, temp_ocr, args_ocr)
                print("✅ ocrmypdf 处理完成")
            except Exception as e:
                print(f"❌ ocrmypdf 处理失败: {e}")
                # 如果失败，尝试只处理前几个页面
                if len(normal_pages) > 10:
                    print("尝试分批处理...")
                    # 这里可以实现分批逻辑，暂时跳过
                return False
        else:
            temp_ocr = None
        
        # 2. 使用 swift 引擎处理问题页面
        if problem_pages:
            print(f"\n步骤2: 使用 Swift 引擎处理 {len(problem_pages)} 个问题页面...")
            problem_pages_str = format_pages(problem_pages)
            
            args_swift = SimpleNamespace(**vars(args))
            args_swift.pages = problem_pages_str
            args_swift.engine = "swift"
            
            try:
                process_one(pdf_path, temp_swift, args_swift)
                print("✅ Swift 引擎处理完成")
            except Exception as e:
                print(f"❌ Swift 引擎处理失败: {e}")
                return False
        
        # 3. 合并结果
        if temp_ocr and temp_swift.exists():
            print(f"\n步骤3: 合并结果...")
            return merge_pdfs_with_page_replacement(
                pdf_path, temp_ocr, temp_swift, problem_pages, output_pdf
            )
        elif temp_ocr and temp_ocr.exists():
            # 只有正常页面，直接复制
            import shutil
            shutil.copy(temp_ocr, output_pdf)
            print(f"✅ 完成（仅正常页面）: {output_pdf}")
            return True
        else:
            print("❌ 没有可用的处理结果")
            return False
            
    finally:
        # 清理临时文件
        for f in [temp_ocr, temp_swift]:
            if f and f.exists():
                try:
                    f.unlink()
                except:
                    pass


if __name__ == "__main__":
    print("这个脚本需要手动集成到主流程中")
    print("当前仅作为概念验证")
    print("\n建议：")
    print("1. 先跳过第24页，处理其他页面")
    print("2. 使用 --pages 参数排除问题页面")
    print("3. 或者考虑升级 ocrmypdf-appleocr 插件")

