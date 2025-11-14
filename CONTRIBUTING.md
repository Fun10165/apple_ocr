# 贡献指南

感谢你对 Apple OCR 的关注！欢迎通过 Issue、Pull Request 参与贡献。

## 提交流程
- Fork 仓库并创建特性分支：`feature/<topic>`。
- 代码风格：通过 `make format` 与 `make lint`。
- 测试覆盖：`make test`，必要时补充用例。
- 提交信息：采用约定式提交（如 `feat: add swift languages option`）。
- PR 说明：清晰描述目的、改动范围、影响面与验证方式。

## 分支与版本
- 主分支：`main`；开发分支：`develop`；特性分支：`feature/*`。
- 遵循语义化版本：`MAJOR.MINOR.PATCH`。

## 行为准则
- 请遵守 `CODE_OF_CONDUCT.md`。

## 开发提示
- 构建 Swift：`cd swift/OCRBridge && swift build -c release`。
- 测试：`uv sync --extra test && make test-cov`。
