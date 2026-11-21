#!/bin/zsh
cd "$(dirname "$0")"
clear
if command -v python3 >/dev/null 2>&1; then
  python3 launcher_web.py
  status=$?
  if [ $status -ne 0 ]; then
    echo
    echo "图形化启动页启动失败，错误码：$status"
    echo "将尝试使用终端启动器继续启动..."
    echo
    python3 launcher.py
    echo
    read "reply?按回车键退出..."
  fi
else
  echo "未检测到 Python 3。"
  echo "请先安装 Python 3.9 或更高版本，然后重新双击启动。"
  echo "下载地址：https://www.python.org/downloads/"
  echo
  read "reply?按回车键退出..."
fi
