# Apple OCR

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8.1+](https://img.shields.io/badge/python-3.8.1+-blue.svg)](https://www.python.org/downloads/)
[![macOS](https://img.shields.io/badge/platform-macOS-lightgrey.svg)](https://www.apple.com/macos/)

高质量中英文OCR工具：Python + Swift Vision，支持Apple Silicon GPU加速。

## 功能特性

✅ **高质量中英文OCR**：
- 支持简体中文、繁体中文、英文混合识别
- 使用Apple Vision框架，准确度高
- 自动语言检测，智能识别文本语言

✅ **Apple Silicon GPU加速**：
- 利用Neural Engine/GPU加速OCR处理
- 单页A4文档处理时间 < 1秒
- 多核并行渲染与OCR，最大化性能

✅ **高保真PDF处理**：
- 300dpi高质量图片渲染
- 透明文本层精确坐标映射
- 保持原始PDF视觉效果与元数据

✅ **灵活页面选择**：
- 支持复杂页面范围：`1,3,5-10,15,20-25`
- 节省处理时间，只处理需要的页面
- 智能页面范围解析和验证

✅ **易用API接口**：
- 简单的Python API，方便程序调用
- 支持文本提取和可搜索PDF生成
- 完整的类型注解和文档

## 快速开始

### 1. 环境准备
```bash
# 安装依赖
brew install poppler  # pdf2image需要
# 确保已安装 uv 包管理器
```

### 2. 项目构建
```bash
# 克隆项目后
cd apple_ocr
uv sync  # 安装Python依赖

# 构建Swift OCR模块
cd swift/OCRBridge
swift build -c release
cd ../..
```

### 3. 使用示例

#### CLI命令行使用
```bash
# 处理单个PDF
uv run apple-ocr --input input.pdf --output output.pdf --dpi 300 --workers 4

# 批量处理目录
uv run apple-ocr --input /path/to/pdfs/ --output /path/to/output/ --workers 8

# 选择特定页面处理
uv run apple-ocr --input input.pdf --output output.pdf --pages "1,3,5-10,15"

# 详细日志
uv run apple-ocr --input test.pdf --output test_ocr.pdf --verbose
```

#### Python API使用
```python
from apple_ocr.api import AppleOCR, extract_text_from_pdf, create_searchable_pdf

# 方法1：提取文本
text_data = extract_text_from_pdf("input.pdf", pages="1,3,5")
for page in text_data:
    print(f"页面 {page['page_index']}: {len(page['items'])} 个文本项")

# 方法2：创建可搜索PDF
create_searchable_pdf("input.pdf", "output.pdf", pages="1-10")

# 方法3：使用类接口
ocr = AppleOCR(dpi=300, workers=8)
ocr.create_searchable_pdf("input.pdf", "output.pdf", pages="1,5-10")
```

## 项目结构
- `apple_ocr/` - Python主包（CLI、渲染、IPC、合成）
- `swift/OCRBridge/` - Swift Vision OCR模块
- `scripts/` - 测试与调试工具
- `examples/` - 示例文件

## 性能指标
- **处理速度**：A4单页 < 1秒（Apple Silicon M系列）
- **内存占用**：≤ 5x 原PDF大小
- **识别准确度**：中英文混合文档 > 95%
- **并行处理**：支持多核CPU + GPU加速

## 页面范围语法
支持灵活的页面选择语法：
- `1` - 单页
- `1,3,5` - 多个单页
- `1-5` - 连续范围
- `1,3,5-10,15` - 混合格式
- `1-3,5,8-10,15,20-25` - 复杂范围

## 开发和测试
```bash
# 安装开发依赖
make install-dev

# 运行测试
make test

# 代码检查
make lint

# 格式化代码
make format

# 构建Swift模块
make swift

# 运行演示
make demo
```

## API参考
详细的API文档请参考：
- `apple_ocr.api.AppleOCR` - 主要OCR类
- `apple_ocr.api.extract_text_from_pdf()` - 文本提取函数
- `apple_ocr.api.create_searchable_pdf()` - PDF生成函数
- `apple_ocr.page_parser` - 页面范围解析

## 系统要求
- **操作系统**: macOS 12.0+ (支持Apple Vision框架)
- **Python**: 3.8.1+
- **Swift**: 5.8+ (用于构建OCR模块)
- **依赖**: poppler (通过Homebrew安装)

## 贡献
欢迎提交Issue和Pull Request！

1. Fork本项目
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建Pull Request

## 许可证
本项目采用MIT许可证 - 详见 [LICENSE](LICENSE) 文件。

## 致谢
- Apple Vision框架提供强大的OCR能力
- pdf2image和reportlab库支持PDF处理
- 所有贡献者的支持和反馈