#!/bin/sh
# WiFi Capture - Alpine Linux 系统配置脚本
set -e

echo "=========================================="
echo "  WiFi Capture - 系统配置"
echo "=========================================="

# 配置 APK 源
cat > /etc/apk/repositories << 'EOF'
https://dl-cdn.alpinelinux.org/alpine/v3.19/main
https://dl-cdn.alpinelinux.org/alpine/v3.19/community
EOF

# 更新包管理器
apk update && apk upgrade

# 安装核心工具
echo "[*] 安装 aircrack-ng 套件..."
apk add --no-cache \
    aircrack-ng \
    wireless-tools \
    iw \
    macchanger \
    tcpdump \
    hcxtools \
    hcxdumptool

# 安装 Python 和 Flask
echo "[*] 安装 Python 和 Flask..."
apk add --no-cache \
    python3 \
    py3-pip \
    py3-flask

# 安装系统工具
echo "[*] 安装系统工具..."
apk add --no-cache \
    bash \
    curl \
    wget \
    vim \
    htop \
    openrc \
    openssh \
    sudo

# 安装 USB 相关
apk add --no-cache \
    usbutils \
    linux-firmware-other

# 创建应用目录
mkdir -p /opt/wifi-capture/{web,data,captures,scripts}
mkdir -p /var/log/wifi-capture

# 设置时区
setup-timezone -z Asia/Shanghai

echo "[+] 系统配置完成"
