#!/bin/sh
# WiFi Capture - 网络配置脚本（固定 IP）
set -e

echo "=========================================="
echo "  WiFi Capture - 网络配置"
echo "=========================================="

# 配置固定 IP（eth0）
# 使用 192.168.200.x 网段，避免与常见网络冲突
cat > /etc/network/interfaces << 'EOF'
auto lo
iface lo inet loopback

# 主网卡 - 固定 IP
auto eth0
iface eth0 inet static
    address 192.168.200.10
    netmask 255.255.255.0
    gateway 192.168.200.1

# 备用 DHCP（如果静态 IP 不工作）
# auto eth0
# iface eth0 inet dhcp
EOF

# 配置 DNS
cat > /etc/resolv.conf << 'EOF'
nameserver 8.8.8.8
nameserver 114.114.114.114
EOF

# 配置主机名
echo "wifi-capture" > /etc/hostname
hostname wifi-capture

# 配置 hosts
cat > /etc/hosts << 'EOF'
127.0.0.1       localhost
192.168.200.10  wifi-capture
EOF

# 启用网络服务
rc-update add networking boot

# 启用 SSH
rc-update add sshd default

# 配置 SSH（允许 root 登录，仅用于开发环境）
sed -i 's/#PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config
sed -i 's/#PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config

echo "[+] 网络配置完成"
echo "    固定 IP: 192.168.200.10"
