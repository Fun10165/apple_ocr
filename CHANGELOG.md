# 变更日志

## v0.3.0
- 暴露 Swift OCR 参数：`--swift-languages`、`--recognition-level`、`--uses-cpu-only`、`--auto-detect-language`。
- 统一语言代码策略（Tesseract vs Swift）与 README 更新。
- CLI 图片模式与 Swift 进程交互改进，增强测试健壮性。
- CI 在 macOS 上构建 Swift 并运行测试。

## v0.2.0
- 初始 Python + Swift 管线，支持 ocrmypdf 与图片 JSON 导出。
