#!/bin/sh
# WiFi Handshake Capture - 环境安装脚本
# 适用于 Alpine Linux

set -e

echo "=========================================="
echo "  WiFi Handshake Capture - 环境配置"
echo "=========================================="

# 更新包管理器
echo "[*] 更新软件源..."
apk update

# 安装必要工具
echo "[*] 安装 aircrack-ng 套件..."
apk add --no-cache \
    aircrack-ng \
    wireless-tools \
    iw \
    macchanger \
    tcpdump \
    bash \
    coreutils \
    grep \
    sed \
    procps

# 安装可选工具
echo "[*] 安装辅助工具..."
apk add --no-cache hcxtools hcxdumptool 2>/dev/null || echo "[!] hcxtools 不可用，跳过"

# 安装 Python 和 Flask (Web 控制面板)
echo "[*] 安装 Python 和 Flask..."
apk add --no-cache python3 py3-pip py3-flask

# 设置脚本权限
chmod +x /home/vagrant/scripts/*.sh 2>/dev/null || true
chmod +x /home/vagrant/web/*.py 2>/dev/null || true

echo ""
echo "=========================================="
echo "  安装完成！"
echo "=========================================="
echo ""
echo "使用方法："
echo "  1. 插入 USB 无线网卡"
echo "  2. 启动 Web 控制面板: sudo python3 /home/vagrant/web/app.py"
echo "  3. 在浏览器访问: http://localhost:5000"
echo ""
echo "或者使用命令行: sudo bash /home/vagrant/scripts/auto_capture.sh"
echo ""
