#!/bin/bash
# Insight Agent Web UI — 一键启动
# 用于分享后的接收方，双击或运行: bash web.sh

# 回到项目根目录
cd "$(dirname "$0")/.." || exit 1

echo ""
echo "╔══════════════════════════════════════╗"
echo "║   Insight Agent · Web UI                ║"
echo "║   http://127.0.0.1:9527             ║"
echo "╚══════════════════════════════════════╝"
echo ""

python3 webui/webui_manager.py
