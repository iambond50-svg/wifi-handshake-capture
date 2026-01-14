#!/bin/sh
# WiFi Capture - 开机自启配置
set -e

echo "=========================================="
echo "  WiFi Capture - 开机自启配置"
echo "=========================================="

# 创建 OpenRC 服务文件
cat > /etc/init.d/wifi-capture << 'INITEOF'
#!/sbin/openrc-run

name="WiFi Capture Web Panel"
description="WiFi Handshake Capture Web Control Panel"

command="/usr/bin/python3"
command_args="/opt/wifi-capture/web/app.py"
command_background="yes"
pidfile="/run/wifi-capture.pid"
output_log="/var/log/wifi-capture/app.log"
error_log="/var/log/wifi-capture/error.log"

depend() {
    need net
    after firewall
}

start_pre() {
    checkpath --directory --owner root:root --mode 0755 /var/log/wifi-capture
    checkpath --directory --owner root:root --mode 0755 /opt/wifi-capture/captures
}

start() {
    ebegin "Starting WiFi Capture Web Panel"
    start-stop-daemon --start --background \
        --make-pidfile --pidfile "$pidfile" \
        --stdout "$output_log" --stderr "$error_log" \
        --exec $command -- $command_args
    eend $?
}

stop() {
    ebegin "Stopping WiFi Capture Web Panel"
    start-stop-daemon --stop --pidfile "$pidfile"
    eend $?
}
INITEOF

chmod +x /etc/init.d/wifi-capture

# 启用开机自启
rc-update add wifi-capture default

# 创建启动脚本（手动使用）
cat > /opt/wifi-capture/start.sh << 'EOF'
#!/bin/sh
echo "Starting WiFi Capture..."
cd /opt/wifi-capture
python3 /opt/wifi-capture/web/app.py &
echo "Web panel started at http://192.168.200.10:5000"
EOF
chmod +x /opt/wifi-capture/start.sh

# 创建停止脚本
cat > /opt/wifi-capture/stop.sh << 'EOF'
#!/bin/sh
echo "Stopping WiFi Capture..."
pkill -f "python3.*app.py" || true
echo "Stopped"
EOF
chmod +x /opt/wifi-capture/stop.sh

# 创建欢迎信息
cat > /etc/motd << 'EOF'
 __        ___ _____ _    ____            _                  
 \ \      / (_)  ___(_)  / ___|__ _ _ __ | |_ _   _ _ __ ___ 
  \ \ /\ / /| | |_  | | | |   / _` | '_ \| __| | | | '__/ _ \
   \ V  V / | |  _| | | | |__| (_| | |_) | |_| |_| | | |  __/
    \_/\_/  |_|_|   |_|  \____\__,_| .__/ \__|\__,_|_|  \___|
                                   |_|                       
═══════════════════════════════════════════════════════════
  Web 控制面板: http://192.168.200.10:5000
  
  手动启动: /opt/wifi-capture/start.sh
  手动停止: /opt/wifi-capture/stop.sh
  
  ⚠️  仅用于测试自己的网络
═══════════════════════════════════════════════════════════
EOF

# 配置自动登录控制台（可选）
# sed -i 's/tty1::respawn.*/tty1::respawn:\/bin\/login -f root/' /etc/inittab

echo "[+] 开机自启配置完成"
