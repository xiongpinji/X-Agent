#!/bin/bash
# X-Agent 插件市场部署启动脚本

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

echo "=========================================="
echo "X-Agent 插件市场部署启动"
echo "=========================================="
echo "项目根目录: $PROJECT_ROOT"
echo "后端目录: $BACKEND_DIR"
echo "前端目录: $FRONTEND_DIR"
echo ""

# 检查Python版本
echo "检查Python版本..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python版本: $python_version"

# 检查Node版本
echo "检查Node版本..."
node_version=$(node --version)
echo "Node版本: $node_version"

# 安装后端依赖
echo ""
echo "安装后端依赖..."
cd "$BACKEND_DIR"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -q -r ../requirements.txt
echo "✅ 后端依赖安装完成"

# 安装前端依赖
echo ""
echo "安装前端依赖..."
cd "$FRONTEND_DIR"
if [ ! -d "node_modules" ]; then
    npm install -q
fi
echo "✅ 前端依赖安装完成"

# 运行测试
echo ""
echo "运行部署测试..."
cd "$PROJECT_ROOT"
python3 scripts/test_plugin_market_deployment.py

echo ""
echo "=========================================="
echo "✅ 部署启动完成！"
echo "=========================================="
echo ""
echo "启动后端服务:"
echo "  cd $BACKEND_DIR"
echo "  source venv/bin/activate"
echo "  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "启动前端服务:"
echo "  cd $FRONTEND_DIR"
echo "  npm run dev"
echo ""
