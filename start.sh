#!/bin/bash

# 服务器资源监控启动脚本
# 自动安装依赖并启动服务

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "  服务器资源监控系统"
echo "========================================"
echo ""

# 检查 Python 是否安装
if ! command -v python &> /dev/null; then
    echo "错误：未找到 Python，请先安装 Python 3.8+"
    exit 1
fi

echo "[1/3] 安装依赖..."
pip install -r requirements.txt -q

echo ""
echo "[2/3] 检查配置..."
if [ ! -f "app/config.py" ]; then
    echo "警告：未找到 config.py，将使用默认配置"
fi

echo ""
echo "[3/3] 启动服务..."
echo "========================================"
echo "访问地址：http://localhost:$(python -c "from app.config import get_service_config; print(get_service_config()['port'])")"
echo "按 Ctrl+C 停止服务"
echo "========================================"
echo ""

# 启动服务（前台运行，便于管理）
python run.py
