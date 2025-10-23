# Apple OCR Makefile

.PHONY: help install install-dev test test-cov lint format type-check build swift clean

help:  ## 显示帮助信息
	@echo "Apple OCR 开发工具"
	@echo ""
	@echo "可用命令："
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## 安装项目依赖
	uv sync

install-dev:  ## 安装开发依赖
	uv sync --extra dev --extra test

test:  ## 运行单元测试
	uv run pytest

test-cov:  ## 运行测试并生成覆盖率报告
	uv run pytest --cov=apple_ocr --cov-report=html --cov-report=term

lint:  ## 代码检查
	uv run flake8 apple_ocr tests
	uv run isort --check-only apple_ocr tests

format:  ## 格式化代码
	uv run black apple_ocr tests
	uv run isort apple_ocr tests

type-check:  ## 类型检查
	uv run mypy apple_ocr

swift:  ## 构建Swift OCR模块
	cd swift/OCRBridge && swift build -c release

build:  ## 构建Python包
	uv build

clean:  ## 清理临时文件
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf dist
	rm -rf build
	rm -rf *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .test_*_images

demo:  ## 运行演示
	@echo "创建演示PDF..."
	uv run python scripts/make_test_pdf.py examples/demo.pdf
	@echo "运行OCR处理..."
	uv run apple-ocr --input examples/demo.pdf --output examples/demo_ocr.pdf --pages "1" --verbose
	@echo "验证结果..."
	uv run python scripts/test_ocr_result.py examples/demo_ocr.pdf

demo-pages:  ## 演示页面选择功能
	@echo "创建多页演示PDF..."
	uv run python scripts/make_test_pdf.py examples/demo_multi.pdf
	@echo "处理指定页面 (1,3)..."
	uv run apple-ocr --input examples/demo_multi.pdf --output examples/demo_multi_ocr.pdf --pages "1,3" --verbose

check: lint type-check test  ## 运行所有检查

all: clean install-dev swift check build  ## 完整构建流程