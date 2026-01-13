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
apk add --no-cache \
    hcxtools \
    hcxdumptool \
    || echo "[!] hcxtools 不可用，跳过"

# 设置脚本权限
chmod +x /home/vagrant/scripts/*.sh 2>/dev/null || true

echo ""
echo "=========================================="
echo "  安装完成！"
echo "=========================================="
echo ""
echo "使用方法："
echo "  1. 插入 USB 无线网卡"
echo "  2. 运行: sudo bash /home/vagrant/scripts/auto_capture.sh"
echo ""
