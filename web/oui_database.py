#!/usr/bin/env python3
"""OUI Database - 根据 MAC 地址识别路由器厂商"""

import json
from pathlib import Path

class OUIDatabase:
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = Path(__file__).parent.parent / "data" / "oui.json"
        
        self.db_path = Path(db_path)
        self.vendors = {}
        self.default = {"name": "Unknown", "logo": "unknown.svg"}
        self._load_database()
    
    def _load_database(self):
        """加载 OUI 数据库"""
        try:
            if self.db_path.exists():
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.vendors = data.get('vendors', {})
                    self.default = data.get('default', self.default)
        except Exception as e:
            print(f"Error loading OUI database: {e}")
    
    def lookup(self, mac_address):
        """根据 MAC 地址查找厂商信息"""
        if not mac_address:
            return self.default.copy()
        
        # 标准化 MAC 地址格式
        mac = mac_address.upper().replace('-', ':')
        
        # 取前 3 个字节 (OUI)
        parts = mac.split(':')
        if len(parts) >= 3:
            oui = ':'.join(parts[:3])
            
            if oui in self.vendors:
                return self.vendors[oui].copy()
        
        return self.default.copy()
    
    def get_vendor_name(self, mac_address):
        """获取厂商名称"""
        return self.lookup(mac_address)['name']
    
    def get_logo(self, mac_address):
        """获取厂商 Logo 文件名"""
        return self.lookup(mac_address)['logo']
    
    def enrich_networks(self, networks):
        """为网络列表添加厂商信息"""
        for network in networks:
            vendor_info = self.lookup(network.get('bssid', ''))
            network['vendor'] = vendor_info['name']
            network['logo'] = vendor_info['logo']
        return networks


# 全局实例
oui_db = OUIDatabase()
