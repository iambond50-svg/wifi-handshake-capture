/**
 * WiFi Handshake Capture - 前端控制脚本
 */

// 全局状态
const state = {
    networks: [],
    captures: [],
    isScanning: false,
    isCapturing: false,
    isAutoCapturing: false,
    currentTarget: null,
    eventSource: null,
    captureTimer: null,
    captureStartTime: null,
    handshakeNotified: false,  // 防止重复通知
    autoCapture: {
        total: 0,
        completed: 0,
        captured: 0,
        failed: 0,
        currentTarget: null
    }
};

// 攻击状态映射
const attackStatusLabels = {
    'none': { text: '', icon: '', class: '' },
    'queued': { text: '排队中', icon: '⏳', class: 'status-queued' },
    'attacking': { text: '攻击中', icon: '⚡', class: 'status-attacking' },
    'captured': { text: '已捕获', icon: '✅', class: 'status-captured' },
    'failed': { text: '失败', icon: '❌', class: 'status-failed' },
    'skipped': { text: '跳过', icon: '⏭️', class: 'status-skipped' }
};

// DOM 元素
const elements = {
    btnScan: document.getElementById('btn-scan'),
    btnStopScan: document.getElementById('btn-stop-scan'),
    btnAutoCapture: document.getElementById('btn-auto-capture'),
    btnStopAuto: document.getElementById('btn-stop-auto'),
    scanProgress: document.getElementById('scan-progress'),
    progressFill: document.getElementById('progress-fill'),
    progressText: document.getElementById('progress-text'),
    autoCaptureProgress: document.getElementById('auto-capture-progress'),
    autoProgressStats: document.getElementById('auto-progress-stats'),
    autoProgressFill: document.getElementById('auto-progress-fill'),
    autoCurrentTarget: document.getElementById('auto-current-target'),
    autoCapturedCount: document.getElementById('auto-captured-count'),
    autoFailedCount: document.getElementById('auto-failed-count'),
    wifiList: document.getElementById('wifi-list'),
    networkCount: document.getElementById('network-count'),
    captureSection: document.getElementById('capture-section'),
    captureEssid: document.getElementById('capture-essid'),
    captureBssid: document.getElementById('capture-bssid'),
    captureTime: document.getElementById('capture-time'),
    attackStatus: document.getElementById('attack-status'),
    handshakeStatus: document.getElementById('handshake-status'),
    captureFiles: document.getElementById('capture-files'),
    captureCount: document.getElementById('capture-count'),
    interfaceStatus: document.getElementById('interface-status'),
    scanStatus: document.getElementById('scan-status'),
    filterEncryption: document.getElementById('filter-encryption'),
    filterAttackStatus: document.getElementById('filter-attack-status'),
    notifications: document.getElementById('notifications')
};

// 攻击类型映射
const attackTypeNames = {
    'deauth_broadcast': '广播 Deauth',
    'deauth_targeted': '定向 Deauth',
    'disassoc': 'Disassoc',
    'deauth_burst': '爆发 Deauth',
    'none': '等待中'
};

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    initEventStream();
    loadCaptures();
    updateStatus();
});

// 初始化 SSE 连接
function initEventStream() {
    if (state.eventSource) {
        state.eventSource.close();
    }
    
    state.eventSource = new EventSource('/api/stream');
    
    state.eventSource.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleStreamData(data);
        } catch (e) {
            console.error('Error parsing stream data:', e);
        }
    };
    
    state.eventSource.onerror = () => {
        console.log('SSE connection error, reconnecting...');
        setTimeout(initEventStream, 5000);
    };
}

// 处理实时数据
function handleStreamData(data) {
    // 更新状态
    if (data.status) {
        updateStatusDisplay(data.status);
    }
    
    // 更新网络列表
    if (data.networks) {
        state.networks = data.networks;
        if (state.isScanning || state.isAutoCapturing) {
            renderNetworks();
        }
    }
    
    // 更新批量捕获状态
    if (data.auto_capture) {
        updateAutoCaptureDisplay(data.auto_capture);
    }
    
    // 检查握手包捕获
    if (data.status && data.status.current_target) {
        const target = data.status.current_target;
        if (target.handshake && target.status === 'success' && !state.handshakeNotified) {
            state.handshakeNotified = true;
            if (!state.isAutoCapturing) {
                showNotification('成功捕获握手包！已自动停止监听', 'success');
            }
            loadCaptures();
            
            // 自动清理前端状态
            if (!state.isAutoCapturing) {
                state.isCapturing = false;
                state.currentTarget = null;
                if (state.captureTimer) {
                    clearInterval(state.captureTimer);
                    state.captureTimer = null;
                }
                elements.captureSection.style.display = 'none';
            }
        }
    }
}

// 更新批量捕获显示
function updateAutoCaptureDisplay(autoCapture) {
    state.isAutoCapturing = autoCapture.is_running;
    state.autoCapture = autoCapture.progress || state.autoCapture;
    
    // 更新按钮状态
    if (elements.btnAutoCapture) {
        elements.btnAutoCapture.style.display = autoCapture.is_running ? 'none' : '';
    }
    if (elements.btnStopAuto) {
        elements.btnStopAuto.style.display = autoCapture.is_running ? '' : 'none';
    }
    
    // 更新进度面板
    if (elements.autoCaptureProgress) {
        elements.autoCaptureProgress.style.display = autoCapture.is_running ? 'block' : 'none';
    }
    
    if (autoCapture.is_running && autoCapture.progress) {
        const p = autoCapture.progress;
        
        if (elements.autoProgressStats) {
            elements.autoProgressStats.textContent = `${p.completed}/${p.total}`;
        }
        if (elements.autoProgressFill) {
            const percent = p.total > 0 ? (p.completed / p.total) * 100 : 0;
            elements.autoProgressFill.style.width = `${percent}%`;
        }
        if (elements.autoCurrentTarget) {
            elements.autoCurrentTarget.textContent = p.current_target 
                ? `${p.current_target.essid} (CH ${p.current_target.channel})`
                : '--';
        }
        if (elements.autoCapturedCount) {
            elements.autoCapturedCount.textContent = p.captured;
        }
        if (elements.autoFailedCount) {
            elements.autoFailedCount.textContent = p.failed;
        }
    }
}

// 更新状态显示
function updateStatusDisplay(status) {
    // 接口状态
    const interfaceDot = elements.interfaceStatus.querySelector('.dot');
    const interfaceText = elements.interfaceStatus.querySelector('span:last-child');
    
    if (status.mon_interface) {
        interfaceDot.className = 'dot active';
        interfaceText.textContent = `接口: ${status.mon_interface}`;
    } else if (status.interface) {
        interfaceDot.className = 'dot';
        interfaceText.textContent = `接口: ${status.interface}`;
    } else {
        interfaceDot.className = 'dot';
        interfaceText.textContent = '接口: 未检测到';
    }
    
    // 扫描状态
    const scanDot = elements.scanStatus.querySelector('.dot');
    const scanText = elements.scanStatus.querySelector('span:last-child');
    
    if (status.is_capturing) {
        scanDot.className = 'dot capturing';
        scanText.textContent = '捕获中';
    } else if (status.is_scanning) {
        scanDot.className = 'dot scanning';
        scanText.textContent = '扫描中';
    } else {
        scanDot.className = 'dot';
        scanText.textContent = '空闲';
    }
    
    state.isScanning = status.is_scanning;
    state.isCapturing = status.is_capturing;
    
    // 更新按钮状态
    elements.btnScan.disabled = state.isScanning || state.isCapturing;
    elements.btnStopScan.disabled = !state.isScanning;
    
    // 更新捕获状态
    if (status.current_target && status.is_capturing) {
        state.currentTarget = status.current_target;
        showCaptureSection();
        
        // 更新攻击状态
        if (status.attack_running && status.attack_type) {
            const attackName = attackTypeNames[status.attack_type] || status.attack_type;
            elements.attackStatus.textContent = `${attackName} (第${status.attack_count}轮)`;
            elements.attackStatus.style.color = 'var(--warning)';
        } else {
            elements.attackStatus.textContent = '等待中';
            elements.attackStatus.style.color = 'var(--text-secondary)';
        }
    }
}

// 开始扫描
async function startScan() {
    try {
        elements.btnScan.disabled = true;
        elements.scanProgress.style.display = 'flex';
        elements.progressFill.style.width = '0%';
        
        const response = await fetch('/api/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ duration: 30 })
        });
        
        const data = await response.json();
        
        if (data.success) {
            state.isScanning = true;
            elements.btnStopScan.disabled = false;
            showNotification('开始扫描周围网络...', 'info');
            
            // 进度动画
            let progress = 0;
            const interval = setInterval(() => {
                progress += 3.33;
                elements.progressFill.style.width = `${Math.min(progress, 100)}%`;
                elements.progressText.textContent = `扫描中 ${Math.min(Math.round(progress), 100)}%`;
                
                if (progress >= 100) {
                    clearInterval(interval);
                    setTimeout(() => {
                        elements.scanProgress.style.display = 'none';
                        loadNetworks();
                    }, 1000);
                }
            }, 1000);
        } else {
            showNotification(data.message || '扫描失败', 'error');
            elements.scanProgress.style.display = 'none';
        }
    } catch (error) {
        console.error('Scan error:', error);
        showNotification('扫描请求失败', 'error');
        elements.scanProgress.style.display = 'none';
    }
}

// 停止扫描
async function stopScan() {
    try {
        await fetch('/api/scan', { method: 'DELETE' });
        state.isScanning = false;
        elements.btnScan.disabled = false;
        elements.btnStopScan.disabled = true;
        elements.scanProgress.style.display = 'none';
        showNotification('扫描已停止', 'info');
        loadNetworks();
    } catch (error) {
        console.error('Stop scan error:', error);
    }
}

// 加载网络列表
async function loadNetworks() {
    try {
        const response = await fetch('/api/networks');
        const data = await response.json();
        state.networks = data.networks || [];
        renderNetworks();
    } catch (error) {
        console.error('Load networks error:', error);
    }
}

// 渲染网络列表
function renderNetworks() {
    const encFilter = elements.filterEncryption ? elements.filterEncryption.value : 'all';
    const statusFilter = elements.filterAttackStatus ? elements.filterAttackStatus.value : 'all';
    let networks = state.networks;
    
    // 过滤加密类型
    if (encFilter !== 'all') {
        networks = networks.filter(n => {
            if (encFilter === 'OPN') return !n.encryption || n.encryption === 'OPN';
            return n.encryption && n.encryption.includes(encFilter);
        });
    }
    
    // 过滤攻击状态
    if (statusFilter !== 'all') {
        networks = networks.filter(n => n.attack_status === statusFilter);
    }
    
    elements.networkCount.textContent = networks.length;
    
    if (networks.length === 0) {
        elements.wifiList.innerHTML = `
            <div class="empty-state">
                <svg viewBox="0 0 24 24"><path d="M1 9l2 2c4.97-4.97 13.03-4.97 18 0l2-2C16.93 2.93 7.08 2.93 1 9zm8 8l3 3 3-3c-1.65-1.66-4.34-1.66-6 0zm-4-4l2 2c2.76-2.76 7.24-2.76 10 0l2-2C15.14 9.14 8.87 9.14 5 13z"/></svg>
                <p>${state.isScanning ? '正在扫描...' : '点击"扫描网络"开始发现周围的 WiFi'}</p>
            </div>
        `;
        return;
    }
    
    elements.wifiList.innerHTML = networks.map(network => createNetworkCard(network)).join('');
}

// 创建网络卡片
function createNetworkCard(network) {
    const signalLevel = getSignalLevel(network.power);
    const encryptionClass = getEncryptionClass(network.encryption);
    const vendorInitial = (network.vendor || 'U')[0].toUpperCase();
    
    // 攻击状态标识
    const attackStatus = network.attack_status || 'none';
    const statusInfo = attackStatusLabels[attackStatus] || attackStatusLabels['none'];
    let attackBadge = '';
    if (attackStatus !== 'none') {
        attackBadge = `<span class="attack-badge ${statusInfo.class}" title="${statusInfo.text}">${statusInfo.icon}</span>`;
    }
    
    // 隐藏网络标识
    let essidDisplay = escapeHtml(network.essid);
    let hiddenBadge = '';
    
    if (network.is_hidden) {
        if (network.revealed) {
            hiddenBadge = '<span class="hidden-badge revealed" title="已揭示的隐藏网络">🔓</span>';
        } else {
            hiddenBadge = `<span class="hidden-badge" title="隐藏网络 - 点击尝试揭示" onclick="event.stopPropagation(); revealHiddenSSID('${network.bssid}')"><span>🔒</span>`;
        }
    }
    
    // 卡片样式类
    let cardClass = 'wifi-card';
    if (network.is_hidden) cardClass += ' hidden-network';
    if (attackStatus === 'captured') cardClass += ' captured';
    if (attackStatus === 'attacking') cardClass += ' attacking';
    
    return `
        <div class="${cardClass}" data-bssid="${network.bssid}" onclick="selectNetwork(this, '${network.bssid}')">
            <div class="vendor-logo">
                ${network.logo && network.logo !== 'unknown.svg' 
                    ? `<img src="/logos/${network.logo}" alt="${network.vendor}" onerror="this.parentElement.innerHTML='<span class=\\'vendor-initial\\'>${vendorInitial}</span>'">`
                    : `<span class="vendor-initial">${vendorInitial}</span>`
                }
            </div>
            <div class="network-info">
                <div class="essid">${attackBadge}${hiddenBadge}${essidDisplay}</div>
                <div class="details">
                    <span class="encryption-badge ${encryptionClass}">${network.encryption || 'OPN'}</span>
                    <span>📡 CH ${network.channel}</span>
                    <span>🏭 ${network.vendor || 'Unknown'}</span>
                    <span title="${network.bssid}">📍 ${network.bssid}</span>
                </div>
            </div>
            <div class="signal-strength">
                <div class="signal-bars">
                    <div class="bar ${signalLevel >= 1 ? 'active' : ''}"></div>
                    <div class="bar ${signalLevel >= 2 ? 'active' : ''}"></div>
                    <div class="bar ${signalLevel >= 3 ? 'active' : ''}"></div>
                    <div class="bar ${signalLevel >= 4 ? 'active' : ''}"></div>
                </div>
                <span style="font-size: 0.75rem; color: var(--text-secondary)">${network.power} dBm</span>
            </div>
            <button class="capture-btn" onclick="event.stopPropagation(); captureNetwork('${network.bssid}', ${network.channel}, '${escapeHtml(network.essid)}')" ${attackStatus === 'attacking' ? 'disabled' : ''}>
                ${attackStatus === 'captured' ? '已捕获' : (attackStatus === 'attacking' ? '攻击中' : '捕获')}
            </button>
        </div>
    `;
}

// 选择网络
function selectNetwork(element, bssid) {
    document.querySelectorAll('.wifi-card').forEach(card => card.classList.remove('selected'));
    element.classList.add('selected');
}

// 开始捕获
async function captureNetwork(bssid, channel, essid) {
    if (state.isCapturing) {
        showNotification('正在进行捕获，请先停止', 'warning');
        return;
    }
    
    try {
        const response = await fetch('/api/capture', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ bssid, channel, essid })
        });
        
        const data = await response.json();
        
        if (data.success) {
            state.isCapturing = true;
            state.currentTarget = { bssid, channel, essid };
            state.captureStartTime = Date.now();
            state.handshakeNotified = false;  // 重置通知标志
            showCaptureSection();
            startCaptureTimer();
            showNotification(`开始捕获 ${essid}`, 'info');
        } else {
            showNotification(data.message || '捕获启动失败', 'error');
        }
    } catch (error) {
        console.error('Capture error:', error);
        showNotification('捕获请求失败', 'error');
    }
}

// 显示捕获状态区域
function showCaptureSection() {
    elements.captureSection.style.display = 'block';
    if (state.currentTarget) {
        elements.captureEssid.textContent = state.currentTarget.essid || '--';
        elements.captureBssid.textContent = state.currentTarget.bssid || '--';
    }
    elements.handshakeStatus.textContent = '等待中...';
    elements.handshakeStatus.style.color = 'var(--warning)';
}

// 捕获计时器
function startCaptureTimer() {
    if (state.captureTimer) clearInterval(state.captureTimer);
    
    state.captureTimer = setInterval(() => {
        if (!state.captureStartTime) return;
        
        const elapsed = Math.floor((Date.now() - state.captureStartTime) / 1000);
        const minutes = Math.floor(elapsed / 60).toString().padStart(2, '0');
        const seconds = (elapsed % 60).toString().padStart(2, '0');
        elements.captureTime.textContent = `${minutes}:${seconds}`;
    }, 1000);
}

// 停止捕获
async function stopCapture() {
    try {
        await fetch('/api/capture', { method: 'DELETE' });
        state.isCapturing = false;
        state.currentTarget = null;
        
        if (state.captureTimer) {
            clearInterval(state.captureTimer);
            state.captureTimer = null;
        }
        
        elements.captureSection.style.display = 'none';
        showNotification('捕获已停止', 'info');
        loadCaptures();
    } catch (error) {
        console.error('Stop capture error:', error);
    }
}

// 发送 Deauth
async function sendDeauth() {
    if (!state.currentTarget) return;
    
    try {
        const response = await fetch('/api/deauth', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                bssid: state.currentTarget.bssid,
                count: 5
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showNotification('已发送 Deauth 包', 'warning');
        } else {
            showNotification(data.message || '发送失败', 'error');
        }
    } catch (error) {
        console.error('Deauth error:', error);
    }
}

// 加载已捕获文件
async function loadCaptures() {
    try {
        const response = await fetch('/api/captures');
        const data = await response.json();
        state.captures = data.captures || [];
        renderCaptures();
    } catch (error) {
        console.error('Load captures error:', error);
    }
}

// 渲染捕获文件列表
function renderCaptures() {
    elements.captureCount.textContent = state.captures.length;
    
    if (state.captures.length === 0) {
        elements.captureFiles.innerHTML = `
            <div class="empty-state small">
                <p>暂无捕获文件</p>
            </div>
        `;
        return;
    }
    
    elements.captureFiles.innerHTML = state.captures.map(file => {
        const ssid = extractSSID(file.filename);
        return `
        <div class="capture-file">
            <div class="file-icon">
                <svg viewBox="0 0 24 24"><path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/></svg>
            </div>
            <div class="file-info">
                <div class="file-name" title="${file.filename}">${ssid}</div>
                <div class="file-meta">${formatFileSize(file.size)} · ${formatDate(file.created)}</div>
            </div>
            <span class="handshake-indicator ${file.has_handshake ? 'success' : 'pending'}">
                ${file.has_handshake ? '✓' : '×'}
            </span>
            <div class="format-btns">
                <button class="format-btn" onclick="downloadCapture('${file.filename}', 'cap')" title="下载 CAP 格式">CAP</button>
                <button class="format-btn" onclick="downloadCapture('${file.filename}', 'hc22000')" title="下载 Hashcat 格式">HC</button>
            </div>
            <button class="delete-btn" onclick="deleteCapture('${file.filename}')" title="删除">
                <svg viewBox="0 0 24 24"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>
            </button>
        </div>
    `}).join('');
}

// 从文件名提取 SSID
function extractSSID(filename) {
    // handshake_SSID_20260114_111340-01.cap
    const match = filename.match(/handshake_(.+?)_\d{8}_\d{6}/);
    if (match) {
        return decodeURIComponent(match[1]);
    }
    return truncateFilename(filename);
}

// 删除捕获文件
async function deleteCapture(filename) {
    if (!confirm(`确定要删除 ${extractSSID(filename)} 的捕获文件吗？`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/captures/${filename}`, {
            method: 'DELETE'
        });
        const data = await response.json();
        
        if (data.success) {
            showNotification('文件已删除', 'success');
            loadCaptures();
        } else {
            showNotification(data.message || '删除失败', 'error');
        }
    } catch (error) {
        console.error('Delete error:', error);
        showNotification('删除请求失败', 'error');
    }
}

// 清理旧文件
async function cleanupFiles() {
    if (!confirm('确定要清理无握手包的捕获文件和旧扫描文件吗？')) {
        return;
    }
    
    try {
        const response = await fetch('/api/cleanup', {
            method: 'POST'
        });
        const data = await response.json();
        
        if (data.success) {
            showNotification(`已清理 ${data.deleted_count} 个文件`, 'success');
            loadCaptures();
        } else {
            showNotification(data.message || '清理失败', 'error');
        }
    } catch (error) {
        console.error('Cleanup error:', error);
        showNotification('清理请求失败', 'error');
    }
}

// 下载捕获文件
function downloadCapture(filename, format = 'cap') {
    closeAllDownloadMenus();
    window.location.href = `/api/captures/download/${filename}?format=${format}`;
}

// 切换下载菜单
function toggleDownloadMenu(event, filename) {
    event.stopPropagation();
    const menuId = 'menu-' + filename.replace(/[^a-zA-Z0-9]/g, '_');
    const menu = document.getElementById(menuId);
    const wasVisible = menu.classList.contains('show');
    
    closeAllDownloadMenus();
    
    if (!wasVisible) {
        menu.classList.add('show');
    }
}

// 关闭所有下载菜单
function closeAllDownloadMenus() {
    document.querySelectorAll('.download-menu').forEach(menu => {
        menu.classList.remove('show');
    });
}

// 点击其他地方关闭菜单
document.addEventListener('click', () => {
    closeAllDownloadMenus();
});

// 过滤网络
function filterNetworks() {
    renderNetworks();
}

// ==================== 批量自动捕获 ====================

// 启动自动捕获全部
async function startAutoCapture() {
    if (state.isCapturing) {
        showNotification('正在进行单独捕获，请先停止', 'warning');
        return;
    }
    
    if (state.isAutoCapturing) {
        showNotification('批量捕获已在进行中', 'warning');
        return;
    }
    
    // 获取参数
    const skipAttacked = true;  // 跳过已攻击的
    const minPower = -90;       // 最小信号强度
    
    try {
        const response = await fetch('/api/auto-capture', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                skip_attacked: skipAttacked,
                min_power: minPower
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            state.isAutoCapturing = true;
            showNotification(`开始批量捕获 ${data.total_targets} 个目标`, 'info');
        } else {
            showNotification(data.message || '批量捕获启动失败', 'error');
        }
    } catch (error) {
        console.error('Auto capture error:', error);
        showNotification('批量捕获请求失败', 'error');
    }
}

// 停止自动捕获
async function stopAutoCapture() {
    try {
        const response = await fetch('/api/auto-capture', {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success) {
            state.isAutoCapturing = false;
            showNotification('批量捕获已停止', 'info');
            loadCaptures();
        } else {
            showNotification(data.message || '停止失败', 'error');
        }
    } catch (error) {
        console.error('Stop auto capture error:', error);
        showNotification('停止请求失败', 'error');
    }
}

// 清除攻击历史
async function clearAttackHistory() {
    if (!confirm('确定要清除所有攻击历史记录吗？清除后已攻击的网络可以被重新攻击。')) {
        return;
    }
    
    try {
        const response = await fetch('/api/attack-history', {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showNotification('攻击历史已清除', 'success');
            // 刷新网络列表以更新状态
            if (state.networks.length > 0) {
                renderNetworks();
            }
        } else {
            showNotification(data.message || '清除失败', 'error');
        }
    } catch (error) {
        console.error('Clear history error:', error);
        showNotification('清除请求失败', 'error');
    }
}

// 更新状态
async function updateStatus() {
    try {
        const response = await fetch('/api/status');
        const status = await response.json();
        updateStatusDisplay(status);
    } catch (error) {
        console.error('Update status error:', error);
    }
}

// 显示通知
function showNotification(message, type = 'info') {
    const icons = {
        success: '<svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>',
        error: '<svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>',
        warning: '<svg viewBox="0 0 24 24"><path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/></svg>',
        info: '<svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/></svg>'
    };
    
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.innerHTML = `
        ${icons[type]}
        <span>${message}</span>
    `;
    
    elements.notifications.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideIn 0.3s ease reverse';
        setTimeout(() => notification.remove(), 300);
    }, 4000);
}

// 辅助函数
function getSignalLevel(power) {
    if (power >= -50) return 4;
    if (power >= -60) return 3;
    if (power >= -70) return 2;
    return 1;
}

function getEncryptionClass(encryption) {
    if (!encryption || encryption === 'OPN') return 'open';
    if (encryption.includes('WPA2')) return 'wpa2';
    if (encryption.includes('WPA')) return 'wpa';
    if (encryption.includes('WEP')) return 'wep';
    return '';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function truncateFilename(filename, maxLength = 25) {
    if (filename.length <= maxLength) return filename;
    return filename.substring(0, maxLength - 3) + '...';
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function formatDate(isoString) {
    const date = new Date(isoString);
    return date.toLocaleString('zh-CN', { 
        month: '2-digit', 
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// 尝试揭示隐藏 SSID
async function revealHiddenSSID(bssid) {
    try {
        showNotification('正在尝试揭示隐藏网络...', 'info');
        
        const response = await fetch(`/api/hidden-ssid/${bssid}`);
        const data = await response.json();
        
        if (data.success && data.ssid) {
            showNotification(`揭示成功: ${data.ssid}`, 'success');
            // 重新加载网络列表以更新显示
            loadNetworks();
        } else {
            showNotification(data.message || '未能揭示，请等待设备重连', 'warning');
        }
    } catch (error) {
        console.error('Reveal hidden SSID error:', error);
        showNotification('揭示请求失败', 'error');
    }
}

// 模态框函数
function closeModal() {
    document.getElementById('modal').style.display = 'none';
}
