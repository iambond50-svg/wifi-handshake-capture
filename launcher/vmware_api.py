"""
VMware Workstation API 封装
使用 vmrun 命令行工具控制虚拟机
"""

import subprocess
import os
import time
import json
from pathlib import Path
from typing import Optional, List, Dict

class VMwareAPI:
    def __init__(self, vmrun_path: str = None):
        """
        初始化 VMware API
        
        Args:
            vmrun_path: vmrun.exe 路径，默认自动查找
        """
        self.vmrun_path = vmrun_path or self._find_vmrun()
        self.vm_path: Optional[str] = None
        
    def _find_vmrun(self) -> str:
        """自动查找 vmrun.exe"""
        possible_paths = [
            r"C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe",
            r"C:\Program Files\VMware\VMware Workstation\vmrun.exe",
            r"C:\Program Files (x86)\VMware\VMware Player\vmrun.exe",
            r"C:\Program Files\VMware\VMware Player\vmrun.exe",
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        # 尝试从 PATH 环境变量查找
        try:
            result = subprocess.run(["where", "vmrun"], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip().split('\n')[0]
        except:
            pass
        
        raise FileNotFoundError("未找到 vmrun.exe，请确保已安装 VMware Workstation")
    
    def _run_vmrun(self, *args, timeout: int = 60) -> tuple:
        """
        执行 vmrun 命令
        
        Returns:
            (success: bool, output: str)
        """
        cmd = [self.vmrun_path] + list(args)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "命令执行超时"
        except Exception as e:
            return False, str(e)
    
    def list_running_vms(self) -> List[str]:
        """列出正在运行的虚拟机"""
        success, output = self._run_vmrun("list")
        if success:
            lines = output.strip().split('\n')
            # 第一行是 "Total running VMs: X"
            return [line.strip() for line in lines[1:] if line.strip()]
        return []
    
    def is_vm_running(self, vmx_path: str = None) -> bool:
        """检查虚拟机是否正在运行"""
        vmx = vmx_path or self.vm_path
        if not vmx:
            return False
        running_vms = self.list_running_vms()
        return any(vmx.lower() in vm.lower() for vm in running_vms)
    
    def start_vm(self, vmx_path: str = None, gui: bool = True) -> tuple:
        """
        启动虚拟机
        
        Args:
            vmx_path: .vmx 文件路径
            gui: True 显示界面，False 后台运行
        """
        vmx = vmx_path or self.vm_path
        if not vmx:
            return False, "未指定虚拟机路径"
        
        if self.is_vm_running(vmx):
            return True, "虚拟机已在运行"
        
        mode = "gui" if gui else "nogui"
        return self._run_vmrun("start", vmx, mode, timeout=120)
    
    def stop_vm(self, vmx_path: str = None, hard: bool = False) -> tuple:
        """
        停止虚拟机
        
        Args:
            vmx_path: .vmx 文件路径
            hard: True 强制关机，False 正常关机
        """
        vmx = vmx_path or self.vm_path
        if not vmx:
            return False, "未指定虚拟机路径"
        
        if not self.is_vm_running(vmx):
            return True, "虚拟机未在运行"
        
        mode = "hard" if hard else "soft"
        return self._run_vmrun("stop", vmx, mode, timeout=60)
    
    def suspend_vm(self, vmx_path: str = None) -> tuple:
        """挂起虚拟机"""
        vmx = vmx_path or self.vm_path
        if not vmx:
            return False, "未指定虚拟机路径"
        return self._run_vmrun("suspend", vmx, timeout=60)
    
    def reset_vm(self, vmx_path: str = None) -> tuple:
        """重启虚拟机"""
        vmx = vmx_path or self.vm_path
        if not vmx:
            return False, "未指定虚拟机路径"
        return self._run_vmrun("reset", vmx, "soft", timeout=120)
    
    def get_ip_address(self, vmx_path: str = None) -> Optional[str]:
        """获取虚拟机 IP 地址"""
        vmx = vmx_path or self.vm_path
        if not vmx:
            return None
        
        success, output = self._run_vmrun("getGuestIPAddress", vmx, "-wait", timeout=60)
        if success:
            ip = output.strip()
            if ip and not ip.startswith("Error"):
                return ip
        return None
    
    def run_script_in_guest(self, script: str, vmx_path: str = None, 
                           username: str = "root", password: str = "wifi-capture") -> tuple:
        """
        在虚拟机中执行脚本
        
        Args:
            script: 要执行的脚本内容
            vmx_path: .vmx 文件路径
            username: 虚拟机用户名
            password: 虚拟机密码
        """
        vmx = vmx_path or self.vm_path
        if not vmx:
            return False, "未指定虚拟机路径"
        
        return self._run_vmrun(
            "-gu", username, "-gp", password,
            "runScriptInGuest", vmx, "/bin/sh", script,
            timeout=120
        )
    
    def copy_file_to_guest(self, host_path: str, guest_path: str,
                          vmx_path: str = None,
                          username: str = "root", password: str = "wifi-capture") -> tuple:
        """复制文件到虚拟机"""
        vmx = vmx_path or self.vm_path
        if not vmx:
            return False, "未指定虚拟机路径"
        
        return self._run_vmrun(
            "-gu", username, "-gp", password,
            "copyFileFromHostToGuest", vmx, host_path, guest_path,
            timeout=120
        )
    
    def import_ova(self, ova_path: str, target_dir: str = None) -> tuple:
        """
        导入 OVA 文件
        
        注意：vmrun 不直接支持导入 OVA，需要使用 ovftool
        """
        ovftool_paths = [
            r"C:\Program Files (x86)\VMware\VMware Workstation\OVFTool\ovftool.exe",
            r"C:\Program Files\VMware\VMware Workstation\OVFTool\ovftool.exe",
        ]
        
        ovftool = None
        for path in ovftool_paths:
            if os.path.exists(path):
                ovftool = path
                break
        
        if not ovftool:
            return False, "未找到 ovftool.exe"
        
        if not target_dir:
            target_dir = os.path.join(os.path.dirname(ova_path), "vm")
        
        os.makedirs(target_dir, exist_ok=True)
        
        try:
            result = subprocess.run(
                [ovftool, "--acceptAllEulas", ova_path, target_dir],
                capture_output=True, text=True, timeout=300
            )
            
            if result.returncode == 0:
                # 查找生成的 .vmx 文件
                for f in Path(target_dir).rglob("*.vmx"):
                    self.vm_path = str(f)
                    return True, f"导入成功: {self.vm_path}"
                return False, "导入完成但未找到 .vmx 文件"
            else:
                return False, result.stderr
        except Exception as e:
            return False, str(e)
    
    def configure_usb_passthrough(self, vmx_path: str = None, 
                                  vendor_ids: List[str] = None) -> tuple:
        """
        配置 USB 直通
        
        Args:
            vmx_path: .vmx 文件路径
            vendor_ids: USB 设备厂商 ID 列表
        """
        vmx = vmx_path or self.vm_path
        if not vmx:
            return False, "未指定虚拟机路径"
        
        if not vendor_ids:
            # 常见无线网卡厂商 ID
            vendor_ids = ["148f", "0bda", "0cf3", "0e8d", "2357"]
        
        try:
            with open(vmx, 'r') as f:
                content = f.read()
            
            # 添加 USB 配置
            usb_config = """
# USB Passthrough Configuration
usb.present = "TRUE"
usb.generic.autoconnect = "TRUE"
ehci.present = "TRUE"
"""
            # 添加 USB 过滤器
            for i, vid in enumerate(vendor_ids):
                usb_config += f'usb.autoConnect.device{i} = "vid:{vid}"\n'
            
            if "usb.present" not in content:
                content += usb_config
                with open(vmx, 'w') as f:
                    f.write(content)
                return True, "USB 直通配置已添加"
            else:
                return True, "USB 直通已配置"
        except Exception as e:
            return False, str(e)
    
    def configure_host_only_network(self, vmx_path: str = None, 
                                   vmnet: str = "vmnet1") -> tuple:
        """配置 Host-Only 网络"""
        vmx = vmx_path or self.vm_path
        if not vmx:
            return False, "未指定虚拟机路径"
        
        try:
            with open(vmx, 'r') as f:
                lines = f.readlines()
            
            # 修改网络配置
            new_lines = []
            for line in lines:
                if line.startswith("ethernet0.connectionType"):
                    new_lines.append(f'ethernet0.connectionType = "hostonly"\n')
                elif line.startswith("ethernet0.vnet"):
                    new_lines.append(f'ethernet0.vnet = "{vmnet}"\n')
                else:
                    new_lines.append(line)
            
            with open(vmx, 'w') as f:
                f.writelines(new_lines)
            
            return True, f"网络已配置为 {vmnet}"
        except Exception as e:
            return False, str(e)


def get_vmware_api() -> VMwareAPI:
    """获取 VMware API 实例"""
    return VMwareAPI()
