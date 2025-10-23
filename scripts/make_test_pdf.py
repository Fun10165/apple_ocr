from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import sys

outfile = sys.argv[1] if len(sys.argv) > 1 else "examples/test.pdf"

c = canvas.Canvas(outfile, pagesize=A4)
width, height = A4

# 使用系统中文字体以确保中文正确显示
chinese_font = 'Helvetica'  # 默认字体
try:
    # 尝试多个macOS中文字体路径
    font_paths = [
        '/System/Library/Fonts/PingFang.ttc',
        '/System/Library/Fonts/Hiragino Sans GB.ttc',
        '/System/Library/Fonts/STHeiti Light.ttc',
        '/Library/Fonts/Arial Unicode MS.ttf'
    ]
    for font_path in font_paths:
        try:
            pdfmetrics.registerFont(TTFont('ChineseFont', font_path))
            chinese_font = 'ChineseFont'
            print(f"使用字体: {font_path}")
            break
        except:
            continue
except:
    pass

c.setFont(chinese_font, 18)
c.drawString(72, height - 100, "你好世界！Apple Vision OCR 测试")
c.setFont(chinese_font, 16)
c.drawString(72, height - 130, "这是一个中英文混合文档")
c.drawString(72, height - 160, "This is a mixed Chinese-English document")
c.setFont(chinese_font, 14)
c.drawString(72, height - 190, "简体中文：人工智能、机器学习、深度学习")
c.drawString(72, height - 220, "繁體中文：人工智慧、機器學習、深度學習")
c.drawString(72, height - 250, "English: Artificial Intelligence, Machine Learning")
c.drawString(72, height - 280, "数字测试：12345 67890")
c.drawString(72, height - 310, "符号测试：！@#￥%……&*（）")

c.showPage()
c.save()
print(f"Wrote {outfile}")