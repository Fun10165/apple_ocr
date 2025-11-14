# Apple OCR

面向生产的 PDF / 图片 OCR 工具链：
- PDF 路径默认使用 `ocrmypdf` + `ocrmypdf-appleocr` 插件（已内置启用）。
- 图片路径使用 Swift Vision（原生 Apple Vision），批量导出 JSON。
- 不引入 LLM，不引入脆弱依赖。目标是简单、稳健、可维护。

## 为什么这样设计（Linus式解释）
- 数据结构优先：PDF 走 `ocrmypdf.ocr()`，图片走 Swift，互不污染，消除特殊情况。
- Never break userspace：保留旧图片管线与 CLI 兼容行为；PDF 改为更可靠的库调用。
- 简洁执念：CLI/API 只做一件事并做好，选项最小化但足够表达核心意图。

## 安装
```bash
# 同步全部依赖（推荐）
uv sync

# 如需单独安装 Apple OCR 插件
uv add ocrmypdf-appleocr

# 系统依赖（macOS）
brew install tesseract ghostscript jbig2enc pngquant
```

## 快速开始
- 单个 PDF（中文识别）：
```bash
uv run apple-ocr --input input.pdf --output output_ocr.pdf --lang chi_sim
```
- PDF 已含文本但需要重做 OCR：
```bash
uv run apple-ocr --input input.pdf --output output_ocr.pdf --lang eng+chi_sim --force-ocr
```
- 仅处理无文本页面：
```bash
uv run apple-ocr --input input.pdf --output output_ocr.pdf --skip-text
```
- 指定页面（示例：1,3,5-10）：
```bash
uv run apple-ocr --input input.pdf --output output_ocr.pdf --pages "1,3,5-10"
```
- 图片目录 → JSON（坐标归一化到 0-1）：
```bash
uv run apple-ocr --input /path/to/images --output result.json --images
```

## 语言支持与参数
- PDF（ocrmypdf/Tesseract）：使用 Tesseract 语言代码
  - 常用：`eng`、`chi_sim`（简体）、`chi_tra`（繁体）
  - 多语言：用 `+` 连接，例如 `eng+chi_sim`
  - CLI 示例：`--lang eng+chi_sim`

- 图片/Swift Vision：使用地区语言代码
  - 常用：`en-US`、`zh-Hans`、`zh-Hant`
  - CLI 新增：`--swift-languages zh-Hans,en-US`
  - 若仅提供 `--lang` 且 `--engine swift`，会自动映射：`eng -> en-US`、`chi_sim -> zh-Hans`、`chi_tra -> zh-Hant`

- Swift OCR 识别参数（仅在 `--engine swift` 或 `--images` 模式下）：
  - `--recognition-level`：`accurate`（默认）或 `fast`
  - `--uses-cpu-only`：仅使用 CPU（默认关闭，允许 GPU/ANE）
  - `--auto-detect-language`：自动语言检测（默认启用）

## CLI 选项说明
- `--lang`：OCR 语言，默认英语；中文请使用 `chi_sim` 或 `chi_tra`。
- `--force-ocr`：无条件重做 OCR（即使页面已有文本）。
- `--skip-text`：跳过已有文本的页面，仅处理空白页面。
- `--pages`：页面选择（例：`1,3,5-10`）。
- `--plugins`：默认启用 `ocrmypdf_appleocr`，一般无需修改。
- `--engine`：默认 `ocrmypdf`；`swift` 为旧图片管线保留项。
 - `--swift-languages`：Swift Vision 语言列表（逗号分隔，示例：`zh-Hans,en-US`）。
 - `--recognition-level` / `--uses-cpu-only` / `--auto-detect-language`：Swift OCR 参数。

## Python API
```python
from apple_ocr.api import create_searchable_pdf

create_searchable_pdf(
    input_pdf="input.pdf",
    output_pdf="output_ocr.pdf",
    pages="1-5",
    language="chi_sim",
)
```

## 页面范围语法
- `1` 单页；`1,3,5` 多页；`1-5` 连续；支持混合：`1,3,5-10,15`。

## 常见错误与处理
- “page already has text!”：根据需求选择 `--force-ocr` 或 `--skip-text`。
- 语言代码错误：报不支持时检查是否使用了地区码（改为 `chi_sim` / `chi_tra`）。

## 开发与测试
```bash
# 运行测试（使用 uv）
uv run pytest -q

# 覆盖率报告
uv run pytest --cov=apple_ocr --cov-report=term --cov-report=html

# 清理构建/测试产物
make clean
```

## 发布与版本
- 安装与测试：`uv sync && uv run pytest -q`
- 构建 Swift：`cd swift/OCRBridge && swift build -c release`
- 构建 Python 包：`uv build`
- 版本：语义化版本（如 `v0.3.0`），与 `pyproject.toml` 同步
- 打 Tag：`git tag v0.3.0 && git push --tags`
- GitHub Release：依赖 Actions 自动上传 `dist/*` 构件（见 `.github/workflows/release.yml`）

## 参与贡献
- 阅读 `CONTRIBUTING.md` 获取提交流程与规范
- 遵守 `CODE_OF_CONDUCT.md` 与 `SECURITY.md`
- 变更记录：`CHANGELOG.md`；发布说明：`RELEASE_NOTES.md`

## 目录结构（已简化）
- `apple_ocr/`：核心代码（CLI、API、渲染、覆盖层）。
- `examples/`：演示用 PDF/脚本（小体积）。
- `scripts/`：辅助脚本（生成/分析 PDF）。
- 已清理：大型 `images/` 数据集、历史覆盖率目录 `htmlcov/`、根目录 `test.pdf`。

## 许可证
MIT，详见 `LICENSE`。
