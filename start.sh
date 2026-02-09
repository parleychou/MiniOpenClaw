#!/bin/bash
# start.sh - Linux/Mac 启动脚本

set -e

echo "============================================"
echo "  飞书 Agent Bridge 服务启动器"
echo "============================================"
echo ""

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到Python3，请先安装Python 3.10+"
    exit 1
fi

echo "[OK] Python 版本: $(python3 --version)"

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "[INFO] 创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
if [ -f "requirements.txt" ]; then
    echo "[INFO] 检查依赖..."
    pip install -r requirements.txt -q
fi

# 检查配置文件
if [ ! -f "config/config.yaml" ]; then
    echo "[错误] 配置文件不存在: config/config.yaml"
    echo "请复制 config/config.yaml.example 并填写配置:"
    echo "  cp config/config.yaml.example config/config.yaml"
    echo "  然后编辑 config/config.yaml 填写真实的配置信息"
    exit 1
fi

# 检查Claude Code或OpenCode是否可用
if command -v claude &> /dev/null; then
    echo "[OK] Claude Code CLI 可用: $(which claude)"
else
    echo "[警告] Claude Code CLI 未找到"
fi

if command -v opencode &> /dev/null; then
    echo "[OK] OpenCode CLI 可用: $(which opencode)"
else
    echo "[警告] OpenCode CLI 未找到"
fi

echo ""
echo "[INFO] 启动服务..."
echo ""

# 启动服务
python3 src/main.py "$@"
