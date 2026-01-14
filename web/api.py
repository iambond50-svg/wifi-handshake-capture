#!/usr/bin/env python3
"""API 路由"""

from flask import Blueprint, jsonify, request, Response, send_file
import json
import time
import os

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
    hidden_cache = scanner.get_hidden_ssid_cache()
    return jsonify({
        'networks': networks,
        'count': len(networks),
        'is_scanning': scanner.is_scanning,
        'hidden_ssid_count': len(hidden_cache),
        'hidden_ssid_cache': hidden_cache
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

@api_bp.route('/captures/download/<filename>')
def download_capture(filename):
    """下载捕获文件"""
    format_type = request.args.get('format', 'cap')
    
    # 查找原始 cap 文件
    cap_path = scanner.capture_dir / filename
    if not cap_path.exists():
        return jsonify({'error': '文件不存在'}), 404
    
    if format_type == 'cap':
        return send_file(
            str(cap_path),
            as_attachment=True,
            download_name=filename
        )
    
    # 转换为其他格式
    converted_file = scanner.convert_capture(str(cap_path), format_type)
    if converted_file and os.path.exists(converted_file):
        download_name = filename.rsplit('.', 1)[0] + '.' + format_type
        return send_file(
            converted_file,
            as_attachment=True,
            download_name=download_name
        )
    else:
        return jsonify({'error': f'无法转换为 {format_type} 格式'}), 400

@api_bp.route('/captures/convert/<filename>', methods=['POST'])
def convert_capture(filename):
    """转换捕获文件格式"""
    data = request.json or {}
    format_type = data.get('format', 'hc22000')
    
    cap_path = scanner.capture_dir / filename
    if not cap_path.exists():
        return jsonify({'success': False, 'message': '文件不存在'}), 404
    
    converted_file = scanner.convert_capture(str(cap_path), format_type)
    if converted_file:
        return jsonify({
            'success': True,
            'message': f'转换成功',
            'file': os.path.basename(converted_file)
        })
    else:
        return jsonify({'success': False, 'message': '转换失败'}), 400

@api_bp.route('/captures/<filename>', methods=['DELETE'])
def delete_capture(filename):
    """删除捕获文件"""
    deleted = scanner.delete_capture(filename)
    if deleted:
        return jsonify({'success': True, 'message': '文件已删除'})
    else:
        return jsonify({'success': False, 'message': '删除失败'}), 400

@api_bp.route('/cleanup', methods=['POST'])
def cleanup_files():
    """清理旧文件"""
    deleted_count = scanner.cleanup_old_files()
    return jsonify({
        'success': True,
        'message': f'已清理 {deleted_count} 个文件',
        'deleted_count': deleted_count
    })

@api_bp.route('/hidden-ssid/<bssid>', methods=['GET'])
def reveal_hidden_ssid(bssid):
    """尝试揭示隐藏网络 SSID"""
    ssid = scanner.reveal_hidden_ssid(bssid)
    if ssid:
        return jsonify({
            'success': True,
            'bssid': bssid,
            'ssid': ssid
        })
    else:
        return jsonify({
            'success': False,
            'message': '未能获取隐藏 SSID，请等待设备连接'
        })

@api_bp.route('/hidden-ssid', methods=['GET'])
def get_hidden_ssid_cache():
    """获取所有已发现的隐藏 SSID"""
    cache = scanner.get_hidden_ssid_cache()
    return jsonify({
        'success': True,
        'cache': cache,
        'count': len(cache)
    })

@api_bp.route('/stream')
def event_stream():
    """SSE 实时事件流"""
    def generate():
        while True:
            status = scanner.get_status()
            networks = scanner.get_networks()
            networks = oui_db.enrich_networks(networks)
            
            hidden_cache = scanner.get_hidden_ssid_cache()
            data = {
                'status': status,
                'networks': networks[:20],  # 只发送前 20 个
                'timestamp': time.time(),
                'hidden_ssid_count': len(hidden_cache)
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
