#!/bin/bash
# Apple OCR 发布准备脚本

set -e

echo "🚀 准备发布 Apple OCR 到 GitHub..."

# 检查是否在git仓库中
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "❌ 错误：不在git仓库中"
    exit 1
fi

# 检查工作目录是否干净
if ! git diff-index --quiet HEAD --; then
    echo "❌ 错误：工作目录有未提交的更改"
    echo "请先提交或暂存所有更改"
    exit 1
fi

echo "✅ Git仓库状态检查通过"

# 运行测试
echo "🧪 运行测试..."
if command -v uv &> /dev/null; then
    uv run pytest
else
    echo "⚠️  警告：未找到uv，跳过测试"
fi

# 构建Swift模块
echo "🔨 构建Swift OCR模块..."
cd swift/OCRBridge
swift build -c release
cd ../..

echo "✅ Swift模块构建完成"

# 检查重要文件是否存在
required_files=(
    "README.md"
    "LICENSE"
    ".gitignore"
    "pyproject.toml"
    "Makefile"
    ".github/workflows/test.yml"
)

for file in "${required_files[@]}"; do
    if [[ ! -f "$file" ]]; then
        echo "❌ 错误：缺少必要文件 $file"
        exit 1
    fi
done

echo "✅ 所有必要文件检查通过"

# 显示将要提交的文件
echo "📋 将要提交的文件："
git status --porcelain

echo ""
echo "🎉 发布准备完成！"
echo ""
echo "下一步操作："
echo "1. 检查上述文件列表"
echo "2. 运行: git commit -m 'chore: prepare release vX.Y.Z'"
echo "3. 运行: git remote add origin <your-github-repo-url>"
echo "4. 运行: git push -u origin main"
echo "5. 打 Tag: git tag vX.Y.Z && git push --tags"
echo "6. GitHub 创建 Release（或等待 Actions 自动上传 dist 构件）"
echo ""
echo "GitHub仓库创建后的建议操作："
echo "- 添加项目描述和标签"
echo "- 启用Issues和Discussions"
echo "- 设置分支保护规则"
echo "- 添加贡献者指南"
