#!/usr/bin/env python3
"""API 路由"""

from flask import Blueprint, jsonify, request, Response
import json
import time

from wifi_scanner import scanner
from oui_database import oui_db

api_bp = Blueprint('api', __name__)

@api_bp.route('/status')
def get_status():
    """获取系统状态"""
    return jsonify(scanner.get_status())

@api_bp.route('/scan', methods=['POST'])
def start_scan():
    """开始扫描"""
    duration = request.json.get('duration', 30) if request.json else 30
    
    if scanner.start_scan(duration=duration):
        return jsonify({'success': True, 'message': '扫描已开始'})
    else:
        return jsonify({'success': False, 'message': '无法开始扫描'}), 400

@api_bp.route('/scan', methods=['DELETE'])
def stop_scan():
    """停止扫描"""
    scanner.stop_scan()
    return jsonify({'success': True, 'message': '扫描已停止'})

@api_bp.route('/networks')
def get_networks():
    """获取网络列表"""
    networks = scanner.get_networks()
    networks = oui_db.enrich_networks(networks)
    return jsonify({
        'networks': networks,
        'count': len(networks),
        'is_scanning': scanner.is_scanning
    })

@api_bp.route('/capture', methods=['POST'])
def start_capture():
    """开始捕获"""
    data = request.json
    if not data:
        return jsonify({'success': False, 'message': '缺少参数'}), 400
    
    bssid = data.get('bssid')
    channel = data.get('channel')
    essid = data.get('essid', 'Unknown')
    
    if not bssid or not channel:
        return jsonify({'success': False, 'message': '缺少 BSSID 或信道'}), 400
    
    if scanner.start_capture(bssid, channel, essid):
        return jsonify({'success': True, 'message': '捕获已开始'})
    else:
        return jsonify({'success': False, 'message': '无法开始捕获'}), 400

@api_bp.route('/capture', methods=['DELETE'])
def stop_capture():
    """停止捕获"""
    scanner.stop_capture()
    return jsonify({'success': True, 'message': '捕获已停止'})

@api_bp.route('/deauth', methods=['POST'])
def send_deauth():
    """发送 Deauth 包"""
    data = request.json
    if not data:
        return jsonify({'success': False, 'message': '缺少参数'}), 400
    
    bssid = data.get('bssid')
    count = data.get('count', 5)
    
    if not bssid:
        return jsonify({'success': False, 'message': '缺少 BSSID'}), 400
    
    if scanner.send_deauth(bssid, count):
        return jsonify({'success': True, 'message': f'已发送 {count} 个 Deauth 包'})
    else:
        return jsonify({'success': False, 'message': '发送失败'}), 400

@api_bp.route('/captures')
def get_captures():
    """获取已捕获的文件列表"""
    captures = scanner.get_captures()
    return jsonify({
        'captures': captures,
        'count': len(captures)
    })

@api_bp.route('/stream')
def event_stream():
    """SSE 实时事件流"""
    def generate():
        while True:
            status = scanner.get_status()
            networks = scanner.get_networks()
            networks = oui_db.enrich_networks(networks)
            
            data = {
                'status': status,
                'networks': networks[:20],  # 只发送前 20 个
                'timestamp': time.time()
            }
            
            yield f"data: {json.dumps(data)}\n\n"
            time.sleep(2)
    
    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )
