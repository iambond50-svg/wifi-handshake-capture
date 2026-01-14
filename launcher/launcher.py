#!/usr/bin/env python3
"""
WiFi Capture Launcher
一键启动 WiFi 握手包捕获环境
"""

import os
import sys
import json
import time
import webbrowser
import subprocess
from pathlib import Path
from typing import Optional

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from vmware_api import VMwareAPI

class WiFiCaptureLauncher:
    """WiFi Capture 启动器"""
    
    DEFAULT_CONFIG = {
        "vm_name": "wifi-capture",
        "vm_ip": "192.168.200.10",
        "web_port": 5000,
        "vm_username": "root",
        "vm_password": "wifi-capture",
        "ova_path": "",
        "vmx_path": "",
        "auto_open_browser": True,
        "vmnet": "vmnet1"
    }
    
    def __init__(self, config_path: str = None):
        """初始化启动器"""
        self.config_path = config_path or Path(__file__).parent / "config.json"
        self.config = self._load_config()
        self.vmware: Optional[VMwareAPI] = None
        
        # 尝试初始化 VMware API
        try:
            self.vmware = VMwareAPI()
            print(f"✓ VMware 已找到: {self.vmware.vmrun_path}")
        except FileNotFoundError as e:
            print(f"✗ {e}")
    
    def _load_config(self) -> dict:
        """加载配置文件"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 合并默认配置
                    return {**self.DEFAULT_CONFIG, **config}
            except:
                pass
        return self.DEFAULT_CONFIG.copy()
    
    def _save_config(self):
        """保存配置文件"""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
    
    def find_vm(self) -> Optional[str]:
        """查找虚拟机文件"""
        # 优先使用配置中的路径
        if self.config.get("vmx_path") and os.path.exists(self.config["vmx_path"]):
            return self.config["vmx_path"]
        
        # 搜索常见位置
        search_paths = [
            Path(__file__).parent.parent / "build" / "output",
            Path.home() / "Documents" / "Virtual Machines",
            Path(r"C:\Users\Public\Documents\Virtual Machines"),
        ]
        
        for search_path in search_paths:
            if search_path.exists():
                for vmx in search_path.rglob("wifi-capture*.vmx"):
                    return str(vmx)
        
        return None
    
    def import_ova(self, ova_path: str = None) -> bool:
        """导入 OVA 镜像"""
        if not self.vmware:
            print("✗ VMware 未初始化")
            return False
        
        ova = ova_path or self.config.get("ova_path")
        if not ova or not os.path.exists(ova):
            print("✗ 未找到 OVA 文件")
            return False
        
        print(f"正在导入 OVA: {ova}")
        success, msg = self.vmware.import_ova(ova)
        
        if success:
            print(f"✓ {msg}")
            self.config["vmx_path"] = self.vmware.vm_path
            self._save_config()
            return True
        else:
            print(f"✗ 导入失败: {msg}")
            return False
    
    def start(self) -> bool:
        """启动虚拟机和服务"""
        if not self.vmware:
            print("✗ VMware 未初始化")
            return False
        
        # 查找虚拟机
        vmx_path = self.find_vm()
        if not vmx_path:
            print("✗ 未找到虚拟机，请先导入 OVA 或指定 vmx_path")
            return False
        
        self.vmware.vm_path = vmx_path
        print(f"虚拟机路径: {vmx_path}")
        
        # 配置 USB 直通
        print("配置 USB 直通...")
        self.vmware.configure_usb_passthrough()
        
        # 启动虚拟机
        if self.vmware.is_vm_running():
            print("✓ 虚拟机已在运行")
        else:
            print("正在启动虚拟机...")
            success, msg = self.vmware.start_vm(gui=True)
            if not success:
                print(f"✗ 启动失败: {msg}")
                return False
            print("✓ 虚拟机已启动")
        
        # 等待虚拟机就绪
        print("等待系统启动...")
        time.sleep(10)
        
        # 获取 IP 地址
        ip = self.vmware.get_ip_address()
        if ip:
            print(f"✓ 虚拟机 IP: {ip}")
            self.config["vm_ip"] = ip
        else:
            ip = self.config["vm_ip"]
            print(f"使用预设 IP: {ip}")
        
        # 等待 Web 服务就绪
        url = f"http://{ip}:{self.config['web_port']}"
        print(f"等待 Web 服务就绪: {url}")
        
        for i in range(30):
            if self._check_web_service(ip, self.config["web_port"]):
                print("✓ Web 服务已就绪")
                break
            time.sleep(2)
            print(".", end="", flush=True)
        else:
            print("\n⚠ Web 服务未响应，可能需要手动启动")
        
        # 打开浏览器
        if self.config.get("auto_open_browser"):
            print(f"正在打开浏览器: {url}")
            webbrowser.open(url)
        
        print("\n" + "=" * 50)
        print(f"  WiFi Capture 已启动")
        print(f"  控制面板: {url}")
        print("=" * 50)
        
        return True
    
    def stop(self) -> bool:
        """停止虚拟机"""
        if not self.vmware:
            print("✗ VMware 未初始化")
            return False
        
        vmx_path = self.find_vm()
        if not vmx_path:
            print("✗ 未找到虚拟机")
            return False
        
        if not self.vmware.is_vm_running(vmx_path):
            print("虚拟机未在运行")
            return True
        
        print("正在停止虚拟机...")
        success, msg = self.vmware.stop_vm(vmx_path)
        
        if success:
            print("✓ 虚拟机已停止")
            return True
        else:
            print(f"✗ 停止失败: {msg}")
            return False
    
    def status(self) -> dict:
        """获取状态"""
        result = {
            "vmware_available": self.vmware is not None,
            "vm_found": False,
            "vm_running": False,
            "web_available": False,
            "vm_path": None,
            "vm_ip": None
        }
        
        if not self.vmware:
            return result
        
        vmx_path = self.find_vm()
        if vmx_path:
            result["vm_found"] = True
            result["vm_path"] = vmx_path
            result["vm_running"] = self.vmware.is_vm_running(vmx_path)
            
            if result["vm_running"]:
                ip = self.vmware.get_ip_address(vmx_path)
                if ip:
                    result["vm_ip"] = ip
                    result["web_available"] = self._check_web_service(ip, self.config["web_port"])
        
        return result
    
    def _check_web_service(self, ip: str, port: int) -> bool:
        """检查 Web 服务是否可用"""
        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except:
            return False


def print_banner():
    """打印横幅"""
    print("""
 __        ___ _____ _    ____            _                  
 \\ \\      / (_)  ___(_)  / ___|__ _ _ __ | |_ _   _ _ __ ___ 
  \\ \\ /\\ / /| | |_  | | | |   / _` | '_ \\| __| | | | '__/ _ \\
   \\ V  V / | |  _| | | | |__| (_| | |_) | |_| |_| | | |  __/
    \\_/\\_/  |_|_|   |_|  \\____\\__,_| .__/ \\__|\\__,_|_|  \\___|
                                   |_|                       
    """)


def main():
    """主函数"""
    print_banner()
    
    launcher = WiFiCaptureLauncher()
    
    if len(sys.argv) < 2:
        # 默认启动
        launcher.start()
        input("\n按 Enter 键退出...")
        return
    
    command = sys.argv[1].lower()
    
    if command == "start":
        launcher.start()
    elif command == "stop":
        launcher.stop()
    elif command == "status":
        status = launcher.status()
        print("\n状态:")
        print(f"  VMware 可用: {'是' if status['vmware_available'] else '否'}")
        print(f"  虚拟机已找到: {'是' if status['vm_found'] else '否'}")
        print(f"  虚拟机运行中: {'是' if status['vm_running'] else '否'}")
        print(f"  Web 服务可用: {'是' if status['web_available'] else '否'}")
        if status['vm_path']:
            print(f"  虚拟机路径: {status['vm_path']}")
        if status['vm_ip']:
            print(f"  虚拟机 IP: {status['vm_ip']}")
    elif command == "import":
        if len(sys.argv) > 2:
            launcher.import_ova(sys.argv[2])
        else:
            print("用法: launcher.py import <ova_path>")
    else:
        print(f"""
用法: launcher.py [命令]

命令:
  start   启动虚拟机和 Web 服务（默认）
  stop    停止虚拟机
  status  查看状态
  import  导入 OVA 镜像

示例:
  launcher.py start
  launcher.py import wifi-capture.ova
        """)


if __name__ == "__main__":
    main()
