#!/usr/bin/env python3
"""WiFi Handshake Capture - 虚拟机管理工具"""

import os
import sys
import subprocess
import threading
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
import time
import shutil
import atexit

# Windows 下隐藏控制台窗口
if sys.platform == 'win32':
    STARTUPINFO = subprocess.STARTUPINFO()
    STARTUPINFO.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    STARTUPINFO.wShowWindow = subprocess.SW_HIDE
else:
    STARTUPINFO = None

class WiFiCaptureManager:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("WiFi Handshake Capture 管理工具")
        self.root.geometry("500x440")
        self.root.resizable(False, False)
        
        # 设置图标（如果有）
        try:
            self.root.iconbitmap(self.get_resource_path("icon.ico"))
        except:
            pass
        
        # 深色主题
        self.root.configure(bg="#1a1a2e")
        
        self.vm_ip = "10.23.23.23"
        self.vm_port = 5000
        self.vmrun_path = self.find_vmrun()
        self.vmx_path = self.find_vmx()
        self.vm_running = False
        
        self.setup_ui()
        self.check_vm_status()
        
    def get_resource_path(self, filename):
        """获取资源文件路径（支持打包后）"""
        if hasattr(sys, '_MEIPASS'):
            return os.path.join(sys._MEIPASS, filename)
        return os.path.join(os.path.dirname(__file__), filename)
    
    def find_vmrun(self):
        """查找 vmrun.exe"""
        paths = [
            r"C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe",
            r"C:\Program Files\VMware\VMware Workstation\vmrun.exe",
            r"C:\Program Files (x86)\VMware\VMware Player\vmrun.exe",
            r"C:\Program Files\VMware\VMware Player\vmrun.exe",
        ]
        for p in paths:
            if os.path.exists(p):
                return p
        return None
    
    def find_vmx(self):
        """查找 vmx 文件"""
        # 先检查同目录下的 vm 文件夹
        base_dir = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent.parent
        vmx = base_dir / "vm" / "wifi-capture.vmx"
        if vmx.exists():
            return str(vmx)
        
        # 检查当前目录
        vmx = Path("vm") / "wifi-capture.vmx"
        if vmx.exists():
            return str(vmx.absolute())
        
        return None
    
    def setup_ui(self):
        """设置界面"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # 配置样式
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", 16, "bold"), 
                       foreground="#00d4ff", background="#1a1a2e")
        style.configure("Info.TLabel", font=("Microsoft YaHei UI", 10), 
                       foreground="#e0e0e0", background="#1a1a2e")
        style.configure("Status.TLabel", font=("Microsoft YaHei UI", 11), 
                       foreground="#00e676", background="#1a1a2e")
        style.configure("TButton", font=("Microsoft YaHei UI", 11), padding=10)
        style.configure("Green.TButton", font=("Microsoft YaHei UI", 12, "bold"))
        style.configure("Red.TButton", font=("Microsoft YaHei UI", 12, "bold"))
        
        # 主框架
        main_frame = tk.Frame(self.root, bg="#1a1a2e", padx=30, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题
        title_label = ttk.Label(main_frame, text="🛜 WiFi Handshake Capture", style="Title.TLabel")
        title_label.pack(pady=(0, 20))
        
        # 状态框
        status_frame = tk.Frame(main_frame, bg="#16213e", relief=tk.RIDGE, bd=1)
        status_frame.pack(fill=tk.X, pady=10)
        
        status_inner = tk.Frame(status_frame, bg="#16213e", padx=15, pady=15)
        status_inner.pack(fill=tk.X)
        
        # VMware 状态
        vmware_frame = tk.Frame(status_inner, bg="#16213e")
        vmware_frame.pack(fill=tk.X, pady=3)
        ttk.Label(vmware_frame, text="VMware:", style="Info.TLabel", width=12).pack(side=tk.LEFT)
        self.vmware_status = ttk.Label(vmware_frame, text="检测中...", style="Info.TLabel")
        self.vmware_status.pack(side=tk.LEFT)
        
        # VM 状态
        vm_frame = tk.Frame(status_inner, bg="#16213e")
        vm_frame.pack(fill=tk.X, pady=3)
        ttk.Label(vm_frame, text="虚拟机:", style="Info.TLabel", width=12).pack(side=tk.LEFT)
        self.vm_status = ttk.Label(vm_frame, text="检测中...", style="Status.TLabel")
        self.vm_status.pack(side=tk.LEFT)
        
        # IP 地址
        ip_frame = tk.Frame(status_inner, bg="#16213e")
        ip_frame.pack(fill=tk.X, pady=3)
        ttk.Label(ip_frame, text="访问地址:", style="Info.TLabel", width=12).pack(side=tk.LEFT)
        self.ip_label = ttk.Label(ip_frame, text=f"http://{self.vm_ip}:{self.vm_port}", style="Info.TLabel")
        self.ip_label.pack(side=tk.LEFT)
        
        # 按钮区域
        btn_frame = tk.Frame(main_frame, bg="#1a1a2e")
        btn_frame.pack(fill=tk.X, pady=20)
        
        # 启动/停止按钮
        self.start_btn = tk.Button(btn_frame, text="▶ 启动虚拟机", font=("Microsoft YaHei UI", 12, "bold"),
                                   bg="#00e676", fg="#1a1a2e", activebackground="#00c853",
                                   width=18, height=2, cursor="hand2",
                                   command=self.start_vm)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = tk.Button(btn_frame, text="⏹ 停止虚拟机", font=("Microsoft YaHei UI", 12, "bold"),
                                  bg="#ff5252", fg="white", activebackground="#ff1744",
                                  width=18, height=2, cursor="hand2",
                                  command=self.stop_vm, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.RIGHT, padx=5)
        
        # 打开浏览器按钮
        self.browser_btn = tk.Button(main_frame, text="🌐 打开控制面板", font=("Microsoft YaHei UI", 11),
                                     bg="#0066cc", fg="white", activebackground="#0052a3",
                                     width=40, height=2, cursor="hand2",
                                     command=self.open_browser, state=tk.DISABLED)
        self.browser_btn.pack(pady=(10, 20))
        
        # 底部信息
        footer_frame = tk.Frame(main_frame, bg="#1a1a2e")
        footer_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        # GitHub 链接
        github_label = tk.Label(footer_frame, text="GitHub 开源地址", 
                               font=("Microsoft YaHei UI", 9, "underline"),
                               fg="#00d4ff", bg="#1a1a2e", cursor="hand2")
        github_label.pack(side=tk.BOTTOM, pady=(0, 5))
        github_label.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/iambond50-svg/wifi-handshake-capture"))
        
        ttk.Label(footer_frame, text="⚠️ 仅限测试自己拥有或已授权的网络", 
                 style="Info.TLabel", foreground="#ff9800").pack(side=tk.BOTTOM)
        
    def check_vm_status(self):
        """检查各组件状态"""
        # 检查 VMware
        if self.vmrun_path:
            self.vmware_status.config(text="✓ 已安装", foreground="#00e676")
        else:
            self.vmware_status.config(text="✗ 未安装", foreground="#ff5252")
            
        # 检查 VMX
        if not self.vmx_path:
            self.vm_status.config(text="✗ 未找到虚拟机文件", foreground="#ff5252")
            self.start_btn.config(state=tk.DISABLED)
            return
            
        # 检查 VM 运行状态
        self.update_vm_status()
        
    def update_vm_status(self):
        """更新 VM 运行状态 - 通过 ping 检测"""
        def check_ping():
            try:
                # 使用 ping 检测 VM 是否在线
                result = subprocess.run(
                    ["ping", "-n", "1", "-w", "1000", self.vm_ip],
                    capture_output=True, text=True, timeout=3,
                    startupinfo=STARTUPINFO
                )
                return result.returncode == 0
            except:
                return False
        
        # 在后台线程检测避免卡顿
        def do_check():
            is_online = check_ping()
            self.root.after(0, lambda: self.on_status_checked(is_online))
        
        threading.Thread(target=do_check, daemon=True).start()
    
    def on_status_checked(self, is_online):
        """状态检测回调"""
        self.vm_running = is_online
        
        # 如果正在启动中，保持启动状态不变
        if getattr(self, 'vm_starting', False):
            return
        
        if is_online:
            self.vm_status.config(text="● 运行中", foreground="#00e676")
            self.start_btn.config(state=tk.DISABLED, text="▶ 启动虚拟机")
            self.stop_btn.config(state=tk.NORMAL)
            self.browser_btn.config(state=tk.NORMAL)
        else:
            self.vm_status.config(text="○ 已停止", foreground="#ff9800")
            self.start_btn.config(state=tk.NORMAL if self.vmx_path else tk.DISABLED, text="▶ 启动虚拟机")
            self.stop_btn.config(state=tk.DISABLED)
            self.browser_btn.config(state=tk.DISABLED)
            
    def start_vm(self):
        """启动虚拟机"""
        if not self.vmrun_path:
            messagebox.showerror("错误", "未找到 VMware，请先安装 VMware Workstation 或 Player")
            return
            
        if not self.vmx_path:
            messagebox.showerror("错误", "未找到虚拟机文件\n请确保 vm 文件夹与程序在同一目录")
            return
            
        self.start_btn.config(state=tk.DISABLED, text="启动中...")
        self.stop_btn.config(state=tk.DISABLED)
        self.vm_status.config(text="◐ 正在启动...", foreground="#ffeb3b")
        self.vm_starting = True  # 标记正在启动
        
        def do_start():
            try:
                subprocess.run([self.vmrun_path, "start", self.vmx_path, "nogui"],
                              capture_output=True, timeout=60, startupinfo=STARTUPINFO)
                # 等待 VM 启动完成（最多等 60 秒）
                for _ in range(60):
                    if self.check_ping_sync():
                        self.root.after(0, self.on_vm_started)
                        return
                    time.sleep(1)
                # 超时仍未 ping 通
                self.root.after(0, self.on_vm_started)
            except Exception as e:
                self.root.after(0, lambda: self.on_vm_error(str(e)))
                
        threading.Thread(target=do_start, daemon=True).start()
    
    def check_ping_sync(self):
        """同步检查 ping"""
        try:
            result = subprocess.run(
                ["ping", "-n", "1", "-w", "1000", self.vm_ip],
                capture_output=True, text=True, timeout=3,
                startupinfo=STARTUPINFO
            )
            return result.returncode == 0
        except:
            return False
        
    def on_vm_started(self):
        """VM 启动成功回调"""
        self.vm_starting = False
        self.start_btn.config(text="▶ 启动虚拟机")
        self.update_vm_status()
        
    def on_vm_error(self, error):
        """VM 启动失败回调"""
        self.start_btn.config(state=tk.NORMAL, text="▶ 启动虚拟机")
        self.vm_status.config(text="✗ 启动失败", foreground="#ff5252")
        messagebox.showerror("错误", f"虚拟机启动失败:\n{error}")
        
    def stop_vm(self):
        """停止虚拟机"""
        if not messagebox.askyesno("确认", "确定要关闭虚拟机吗？"):
            return
            
        self.stop_btn.config(state=tk.DISABLED, text="停止中...")
        self.vm_status.config(text="◐ 正在关闭...", foreground="#ffeb3b")
        
        def do_stop():
            # 直接使用 vmrun hard 强制关机
            if self.vmrun_path and self.vmx_path:
                try:
                    subprocess.run(
                        [self.vmrun_path, "stop", self.vmx_path, "hard"],
                        capture_output=True, timeout=30, startupinfo=STARTUPINFO
                    )
                except:
                    pass
            
            # 等待关机完成
            time.sleep(3)
            self.root.after(0, self.on_vm_stopped)
                
        threading.Thread(target=do_stop, daemon=True).start()
        
    def on_vm_stopped(self):
        """VM 停止成功回调"""
        self.stop_btn.config(text="⏹ 停止虚拟机")
        self.update_vm_status()
        
    def open_browser(self):
        """打开浏览器"""
        url = f"http://{self.vm_ip}:{self.vm_port}"
        webbrowser.open(url)
        
    def run(self):
        """运行程序"""
        # 定期更新状态
        def periodic_update():
            self.update_vm_status()
            self.root.after(5000, periodic_update)
        self.root.after(5000, periodic_update)
        
        self.root.mainloop()


def cleanup_mei():
    """清理 PyInstaller 临时目录"""
    if hasattr(sys, '_MEIPASS'):
        try:
            mei_dir = sys._MEIPASS
            # 等待其他资源释放
            time.sleep(0.1)
        except:
            pass

if __name__ == "__main__":
    # 注册退出清理
    atexit.register(cleanup_mei)
    
    app = WiFiCaptureManager()
    app.run()
