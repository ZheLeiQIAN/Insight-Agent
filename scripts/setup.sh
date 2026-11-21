#!/bin/bash
# ==========================================
#  Insight Agent — 一键安装脚本
#  接收方解压后运行: bash setup.sh
# ==========================================

set -e
RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo -e "${CYAN}"
echo "╔══════════════════════════════════════╗"
echo "║   Insight Agent 安装程序     ║"
echo "║   洞见 · Prism                       ║"
echo "╚══════════════════════════════════════╝"
echo -e "${NC}"

# 1. Python 依赖
echo -e "\n${CYAN}[1/4] 安装 Python 依赖...${NC}"
pip3 install -r "$PROJECT_DIR/requirements.txt" -q 2>&1 | tail -1
echo -e "${GREEN}  ✅ 依赖安装完成${NC}"

# 2. Playwright 浏览器（爬虫需要）
echo -e "\n${CYAN}[2/4] 安装浏览器自动化...${NC}"
python3 -m playwright install chromium 2>/dev/null && \
    echo -e "${GREEN}  ✅ Chromium 浏览器安装完成${NC}" || \
    echo -e "  ⚠️  跳过（如需使用知乎/小红书/抖音/京东/天猫爬虫，请手动执行: python3 -m playwright install chromium）"

# 3. 全局命令
echo -e "\n${CYAN}[3/4] 创建全局命令...${NC}"
LAUNCHER=""
for dir in /opt/homebrew/bin /usr/local/bin ~/.local/bin; do
    if [ -d "$dir" ] && [ -w "$dir" ]; then
        LAUNCHER="$dir/insight"
        break
    fi
done

if [ -n "$LAUNCHER" ]; then
    cat > "$LAUNCHER" << LAUNCHEREOF
#!/bin/bash
cd "$PROJECT_DIR" || exit 1
exec python3 main.py "\$@"
LAUNCHEREOF
    chmod +x "$LAUNCHER"

    # 同时创建 web 启动命令
    WEB_LAUNCHER="${LAUNCHER}-web"
    cat > "$WEB_LAUNCHER" << WEBEOF
#!/bin/bash
cd "$PROJECT_DIR" || exit 1
exec python3 webui/webui_manager.py
WEBEOF
    chmod +x "$WEB_LAUNCHER"

    echo -e "${GREEN}  ✅ 全局命令已创建: insight / insight-web${NC}"
else
    echo -e "  ⚠️  无写入权限，请手动添加到 ~/.zshrc 或 ~/.bashrc:"
    echo -e "     ${CYAN}alias insight='cd $PROJECT_DIR && python3 main.py'${NC}"
fi

# 4. 验证
echo -e "\n${CYAN}[4/4] 验证安装...${NC}"
python3 -c "
import sys; sys.path.insert(0, '$PROJECT_DIR')
from main import main
from chat import AnalystSession
from analysis.quantitative import auto_detect_fields
print('  ✅ 所有模块正常')
" 2>/dev/null && echo -e "${GREEN}  ✅ 验证通过${NC}" || echo -e "${RED}  ⚠️  验证失败，请检查 Python 环境${NC}"

echo ""
echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         安装完成！                   ║${NC}"
echo -e "${GREEN}║         启动命令: ${CYAN}insight${GREEN}              ║${NC}"
echo -e "${GREEN}║         项目目录: ${PROJECT_DIR}${NC}"
echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
