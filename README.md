# WiFi Handshake Capture Tool

自动捕获周围 WiFi WPA/WPA2 握手包的轻量级工具。

## ⚠️ 法律声明

**本工具仅限用于：**
- 测试你自己拥有的网络
- 已获得书面授权的网络安全测试
- 教育和学习目的

**未经授权捕获他人网络的握手包是违法的！**

## 系统要求

### Windows 主机
- Windows 10/11
- VirtualBox 6.x+ (需安装 Extension Pack)
- Vagrant 2.x+
- 支持监听模式的 USB 无线网卡

### 推荐的 USB 无线网卡
- Alfa AWUS036ACH (RTL8812AU)
- Alfa AWUS036NHA (AR9271)
- TP-Link TL-WN722N v1 (AR9271)
- Panda PAU09 (RT5572)

## 快速开始

### 1. 安装依赖

```powershell
# 安装 VirtualBox
winget install Oracle.VirtualBox

# 安装 Vagrant
winget install HashiCorp.Vagrant

# 重启终端后验证
vagrant --version
```

### 2. 安装 VirtualBox Extension Pack

1. 下载: https://www.virtualbox.org/wiki/Downloads
2. 双击安装 Extension Pack（用于 USB 3.0 支持）

### 3. 启动虚拟机

```powershell
cd "C:\Users\Administrator\Desktop\个人项目\wifi-handshake-capture"
vagrant up
```

首次启动会自动：
- 下载 Alpine Linux (~50MB)
- 配置 USB 直通
- 安装 aircrack-ng 等工具

### 4. 连接 USB 无线网卡

1. 插入 USB 无线网卡
2. VirtualBox 会自动将其连接到虚拟机

### 5. 进入虚拟机并运行

```powershell
vagrant ssh
```

```bash
# 在虚拟机中运行捕获脚本
sudo bash /home/vagrant/scripts/auto_capture.sh
```

## 使用说明

### 交互模式

运行脚本后会显示菜单：

```
请选择操作:
  1) 扫描周围 WiFi 网络
  2) 捕获指定网络握手包
  3) 自动捕获所有 WPA/WPA2 网络
  4) 查看已捕获的握手包
  5) 退出
```

### 命令行模式

编辑 `config/config.conf` 指定目标：

```bash
TARGET_BSSID="AA:BB:CC:DD:EE:FF"
TARGET_CHANNEL="6"
TARGET_ESSID="MyNetwork"
```

### 捕获结果

握手包保存在 `captures/` 目录，格式为：
- `handshake_<ESSID>_<时间戳>.cap` - PCAP 格式握手包

这些文件会自动同步到 Windows 主机的 `captures/` 文件夹。

## 配置选项

编辑 `config/config.conf`：

| 选项 | 默认值 | 说明 |
|------|--------|------|
| SCAN_TIME | 30 | 扫描时间（秒）|
| CAPTURE_TIME | 120 | 每个网络捕获时间（秒）|
| AUTO_DEAUTH | false | 是否发送 Deauth 包 |
| DEAUTH_COUNT | 5 | Deauth 包数量 |

## 常见问题

### Q: 虚拟机看不到 USB 网卡？

1. 确保已安装 VirtualBox Extension Pack
2. 检查 USB 网卡是否被 Windows 占用
3. 手动添加 USB 过滤器：VirtualBox → 设置 → USB → 添加

### Q: 无法启用监听模式？

- 确保网卡支持监听模式
- 尝试不同的 USB 口
- 更新网卡固件

### Q: 长时间捕获不到握手包？

- 目标网络可能没有活跃客户端
- 尝试启用 `AUTO_DEAUTH=true`（仅限自己的网络）
- 靠近目标 AP

## 常用命令

```bash
# 启动虚拟机
vagrant up

# 进入虚拟机
vagrant ssh

# 关闭虚拟机
vagrant halt

# 销毁虚拟机
vagrant destroy

# 重新配置
vagrant provision
```

## 项目结构

```
wifi-handshake-capture/
├── Vagrantfile           # 虚拟机配置
├── README.md             # 本文档
├── scripts/
│   ├── setup.sh          # 环境安装脚本
│   └── auto_capture.sh   # 主捕获脚本
├── config/
│   └── config.conf       # 配置文件
└── captures/             # 捕获的握手包
```

## 后续步骤

捕获到握手包后，可以使用以下工具进行分析/测试：

```bash
# 验证握手包
aircrack-ng captures/handshake_*.cap

# 使用字典测试（仅限自己的网络）
aircrack-ng -w wordlist.txt captures/handshake_*.cap

# 转换为 hashcat 格式
aircrack-ng -j output captures/handshake_*.cap
```

## License

MIT License - 仅供教育目的使用
