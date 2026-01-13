#!/usr/bin/env python3
"""WiFi Handshake Capture - Web 控制面板"""

from flask import Flask, render_template, send_from_directory
import os
import atexit

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

# 导入并注册 API 蓝图
from api import api_bp
app.register_blueprint(api_bp, url_prefix='/api')

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')

@app.route('/logos/<path:filename>')
def serve_logo(filename):
    """提供 Logo 文件"""
    return send_from_directory('static/logos', filename)

@app.route('/captures/<path:filename>')
def download_capture(filename):
    """下载捕获文件"""
    capture_dir = os.environ.get('CAPTURE_DIR', '/home/vagrant/captures')
    return send_from_directory(capture_dir, filename, as_attachment=True)

# 清理函数
def cleanup():
    from wifi_scanner import scanner
    scanner.cleanup()

atexit.register(cleanup)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
