#!/usr/bin/env python3
"""WiFi Scanner - 封装 airodump-ng 扫描功能"""

import subprocess
import os
import csv
import json
import time
import signal
import threading
from datetime import datetime
from pathlib import Path

class WiFiScanner:
    def __init__(self, capture_dir="/home/vagrant/captures"):
        self.capture_dir = Path(capture_dir)
        self.capture_dir.mkdir(parents=True, exist_ok=True)
        self.interface = None
        self.mon_interface = None
        self.scan_process = None
        self.capture_process = None
        self.is_scanning = False
        self.is_capturing = False
        self.current_target = None
        self.networks = []
        self.scan_file = None
        
    def find_interface(self):
        """查找无线网卡"""
        try:
            result = subprocess.run(
                ["iw", "dev"],
                capture_output=True,
                text=True,
                timeout=10
            )
            for line in result.stdout.split('\n'):
                if 'Interface' in line:
                    self.interface = line.split()[-1]
                    return self.interface
        except Exception as e:
            print(f"Error finding interface: {e}")
        return None
    
    def enable_monitor_mode(self):
        """启用监听模式"""
        if not self.interface:
            if not self.find_interface():
                return False
        
        try:
            # 停止干扰进程
            subprocess.run(["airmon-ng", "check", "kill"], 
                         capture_output=True, timeout=30)
            
            # 启用监听模式
            subprocess.run(["airmon-ng", "start", self.interface],
                         capture_output=True, timeout=30)
            
            # 确定监听接口名称
            self.mon_interface = f"{self.interface}mon"
            
            # 验证
            result = subprocess.run(["iw", "dev"], capture_output=True, text=True)
            if self.mon_interface not in result.stdout:
                self.mon_interface = self.interface
                
            return True
        except Exception as e:
            print(f"Error enabling monitor mode: {e}")
            return False
    
    def disable_monitor_mode(self):
        """禁用监听模式"""
        if self.mon_interface:
            try:
                subprocess.run(["airmon-ng", "stop", self.mon_interface],
                             capture_output=True, timeout=30)
            except:
                pass
    
    def start_scan(self, duration=30):
        """开始扫描"""
        if self.is_scanning:
            return False
            
        if not self.mon_interface:
            if not self.enable_monitor_mode():
                return False
        
        self.is_scanning = True
        self.scan_file = self.capture_dir / f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        def scan_thread():
            try:
                self.scan_process = subprocess.Popen(
                    ["airodump-ng",
                     "--write", str(self.scan_file),
                     "--write-interval", "3",
                     "--output-format", "csv",
                     self.mon_interface],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                time.sleep(duration)
            finally:
                self.stop_scan()
        
        thread = threading.Thread(target=scan_thread, daemon=True)
        thread.start()
        return True
    
    def stop_scan(self):
        """停止扫描"""
        if self.scan_process:
            try:
                self.scan_process.terminate()
                self.scan_process.wait(timeout=5)
            except:
                self.scan_process.kill()
            self.scan_process = None
        self.is_scanning = False
        self._parse_scan_results()
    
    def _parse_scan_results(self):
        """解析扫描结果"""
        self.networks = []
        csv_file = f"{self.scan_file}-01.csv"
        
        if not os.path.exists(csv_file):
            return
        
        try:
            with open(csv_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # 分割 AP 和客户端部分
            parts = content.split('\r\n\r\n')
            if not parts:
                return
            
            ap_section = parts[0]
            lines = ap_section.strip().split('\n')
            
            for line in lines[2:]:  # 跳过标题行
                fields = line.split(',')
                if len(fields) >= 14:
                    bssid = fields[0].strip()
                    if not bssid or ':' not in bssid:
                        continue
                    
                    try:
                        channel = int(fields[3].strip()) if fields[3].strip() else 0
                        power = int(fields[8].strip()) if fields[8].strip() else -100
                    except:
                        channel = 0
                        power = -100
                    
                    if channel <= 0 or channel > 165:
                        continue
                    
                    network = {
                        'bssid': bssid.upper(),
                        'channel': channel,
                        'power': power,
                        'encryption': fields[5].strip() if len(fields) > 5 else '',
                        'cipher': fields[6].strip() if len(fields) > 6 else '',
                        'auth': fields[7].strip() if len(fields) > 7 else '',
                        'essid': fields[13].strip() if len(fields) > 13 else '<Hidden>',
                        'clients': 0
                    }
                    
                    if network['essid'] == '':
                        network['essid'] = '<Hidden>'
                    
                    self.networks.append(network)
            
            # 按信号强度排序
            self.networks.sort(key=lambda x: x['power'], reverse=True)
            
        except Exception as e:
            print(f"Error parsing scan results: {e}")
    
    def get_networks(self):
        """获取扫描到的网络列表"""
        if self.is_scanning:
            self._parse_scan_results()
        return self.networks
    
    def start_capture(self, bssid, channel, essid):
        """开始捕获握手包"""
        if self.is_capturing:
            return False
        
        if not self.mon_interface:
            if not self.enable_monitor_mode():
                return False
        
        self.is_capturing = True
        self.current_target = {
            'bssid': bssid,
            'channel': channel,
            'essid': essid,
            'start_time': datetime.now().isoformat(),
            'status': 'capturing',
            'handshake': False
        }
        
        safe_essid = "".join(c for c in essid if c.isalnum() or c in "._-")
        capture_file = self.capture_dir / f"handshake_{safe_essid}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.current_target['file'] = str(capture_file)
        
        def capture_thread():
            try:
                # 锁定信道
                subprocess.run(["iwconfig", self.mon_interface, "channel", str(channel)],
                             capture_output=True, timeout=5)
                
                self.capture_process = subprocess.Popen(
                    ["airodump-ng",
                     "--bssid", bssid,
                     "--channel", str(channel),
                     "--write", str(capture_file),
                     "--output-format", "pcap,csv",
                     self.mon_interface],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                
                # 监控握手包
                while self.is_capturing:
                    time.sleep(5)
                    cap_file = f"{capture_file}-01.cap"
                    if os.path.exists(cap_file):
                        result = subprocess.run(
                            ["aircrack-ng", cap_file],
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        if "1 handshake" in result.stdout:
                            self.current_target['handshake'] = True
                            self.current_target['status'] = 'success'
                            break
                            
            except Exception as e:
                print(f"Capture error: {e}")
                self.current_target['status'] = 'error'
            finally:
                self.stop_capture()
        
        thread = threading.Thread(target=capture_thread, daemon=True)
        thread.start()
        return True
    
    def stop_capture(self):
        """停止捕获"""
        if self.capture_process:
            try:
                self.capture_process.terminate()
                self.capture_process.wait(timeout=5)
            except:
                self.capture_process.kill()
            self.capture_process = None
        
        if self.current_target and self.current_target['status'] == 'capturing':
            self.current_target['status'] = 'stopped'
        
        self.is_capturing = False
    
    def send_deauth(self, bssid, count=5):
        """发送 deauth 包"""
        if not self.mon_interface:
            return False
        
        try:
            subprocess.Popen(
                ["aireplay-ng", "--deauth", str(count), "-a", bssid, self.mon_interface],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return True
        except:
            return False
    
    def get_captures(self):
        """获取已捕获的握手包列表"""
        captures = []
        for f in self.capture_dir.glob("handshake_*-01.cap"):
            # 检查是否包含握手包
            try:
                result = subprocess.run(
                    ["aircrack-ng", str(f)],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                has_handshake = "1 handshake" in result.stdout
            except:
                has_handshake = False
            
            stat = f.stat()
            captures.append({
                'filename': f.name,
                'path': str(f),
                'size': stat.st_size,
                'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                'has_handshake': has_handshake
            })
        
        captures.sort(key=lambda x: x['created'], reverse=True)
        return captures
    
    def get_status(self):
        """获取当前状态"""
        return {
            'interface': self.interface,
            'mon_interface': self.mon_interface,
            'is_scanning': self.is_scanning,
            'is_capturing': self.is_capturing,
            'current_target': self.current_target,
            'network_count': len(self.networks)
        }
    
    def cleanup(self):
        """清理资源"""
        self.stop_scan()
        self.stop_capture()
        self.disable_monitor_mode()
        
        # 重启网络服务
        try:
            subprocess.run(["service", "NetworkManager", "start"],
                         capture_output=True, timeout=10)
        except:
            pass


# 全局实例
scanner = WiFiScanner()
