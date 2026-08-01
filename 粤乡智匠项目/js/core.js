// 粤乡智匠 — 核心模块（常量、状态、工具函数、API封装）
// 此文件必须在 script.js 之前加载

// ==================== 常量 ====================

const TABS = {
    AGRICULTURE: 'agriculture',
    ECOMMERCE: 'ecommerce',
    CRAFTS: 'crafts',
    SIMULATION: 'simulation',
    RESOURCES: 'resources',
    EMPLOYMENT: 'employment',
    TEACHER: 'teacher'
};

const STORAGE_KEYS = {
    SESSION: 'yuexiang_session',
    THEME: 'yuexiang_theme'
};

// 全局状态
const AppState = {
    currentTab: TABS.AGRICULTURE,
    currentDialect: 'cantonese',
    currentProduct: 'lychee',
    currentCraft: 'embroidery',
    calendarYear: new Date().getFullYear(),
    calendarMonth: new Date().getMonth(),
    user: null,
    sessionId: null,
    recognition: null,
    isRecording: false
};

const API_BASE_URL = window.APP_CONFIG?.apiBaseUrl ?? 'http://localhost:5000';
const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// ==================== API调用封装 ====================

async function apiCall(endpoint, method = 'GET', body = null) {
    const options = {
        method,
        headers: { 'Content-Type': 'application/json' }
    };
    if (AppState.sessionId) {
        options.headers['X-Session-Id'] = AppState.sessionId;
    }
    if (body) {
        options.body = JSON.stringify(body);
    }
    const resp = await fetch(`${API_BASE_URL}${endpoint}`, options);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return resp.json();
}

// ==================== iOS 100vh 修复 ====================

function fixIOSViewport() {
    const setVH = () => {
        document.documentElement.style.setProperty('--vh', `${window.innerHeight * 0.01}px`);
    };
    setVH();
    window.addEventListener('resize', debounce(setVH, 150));
    window.addEventListener('orientationchange', () => setTimeout(setVH, 100));
}

// ==================== Service Worker ====================

function registerServiceWorker() {
    if (!('serviceWorker' in navigator)) return;
    navigator.serviceWorker.register('/sw.js').catch(() => {
        // 静默失败 — SW 不是关键路径
    });
}

// ==================== 新手引导 ====================

function checkOnboarding() {
    if (localStorage.getItem('yuexiang_onboarding_done')) return;
    setTimeout(showOnboarding, 800);
}

function showOnboarding() {
    const steps = [
        { icon: 'fa-leaf', title: '农业技能', desc: '选择农产品后，AI智能推送农时管理要点和病虫害防治方案' },
        { icon: 'fa-shopping-cart', title: '电商运营', desc: '模拟直播带货，AI生成话术文案，学习电商运营全流程' },
        { icon: 'fa-paint-brush', title: '手工传承', desc: '非遗手工艺3D步骤拆解，材料采购指南，让传统技艺数字化' },
        { icon: 'fa-robot', title: 'AI助力', desc: 'AI农技问答、AI文案生成、AI病虫害诊断，智能技术为乡村赋能' }
    ];

    let currentStep = 0;
    const overlay = document.createElement('div');
    overlay.className = 'onboarding-overlay';
    overlay.innerHTML = `
        <div class="onboarding-card">
            <div class="onboarding-header">
                <i class="fas fa-seedling"></i>
                <span>欢迎使用粤乡智匠</span>
            </div>
            <div class="onboarding-progress">
                ${steps.map((_, i) => `<span class="onboarding-dot${i === 0 ? ' active' : ''}"></span>`).join('')}
            </div>
            <div class="onboarding-content" id="onboarding-content">
                <div class="onboarding-icon">
                    <i class="fas ${steps[0].icon}"></i>
                </div>
                <h3>${steps[0].title}</h3>
                <p>${steps[0].desc}</p>
            </div>
            <div class="onboarding-actions">
                <button class="btn btn-text" id="onboarding-skip">跳过</button>
                <button class="btn btn-primary" id="onboarding-next">下一步 <i class="fas fa-arrow-right"></i></button>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);

    const updateContent = () => {
        const s = steps[currentStep];
        document.getElementById('onboarding-content').innerHTML = `
            <div class="onboarding-icon">
                <i class="fas ${s.icon}"></i>
            </div>
            <h3>${s.title}</h3>
            <p>${s.desc}</p>
        `;
        overlay.querySelectorAll('.onboarding-dot').forEach((d, i) => {
            d.classList.toggle('active', i === currentStep);
        });
        const nextBtn = document.getElementById('onboarding-next');
        if (currentStep === steps.length - 1) {
            nextBtn.innerHTML = '开始探索 <i class="fas fa-check"></i>';
        } else {
            nextBtn.innerHTML = '下一步 <i class="fas fa-arrow-right"></i>';
        }
    };

    document.getElementById('onboarding-skip').addEventListener('click', () => {
        overlay.remove();
        localStorage.setItem('yuexiang_onboarding_done', '1');
    });

    document.getElementById('onboarding-next').addEventListener('click', () => {
        if (currentStep < steps.length - 1) {
            currentStep++;
            updateContent();
        } else {
            overlay.remove();
            localStorage.setItem('yuexiang_onboarding_done', '1');
        }
    });
}

// ==================== 工具函数 ====================

function escapeHtml(str) {
    if (typeof str !== 'string') return String(str ?? '');
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
}

function debounce(fn, delay = 300) {
    let timer;
    return function(...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
    };
}

async function apiCallWithLoading(endpoint, method, body, loadingMessage = '加载中...') {
    showLoading(loadingMessage);
    try {
        const data = await apiCall(endpoint, method, body);
        hideLoading();
        return data;
    } catch(e) {
        hideLoading();
        throw e;
    }
}

function showSkeleton(container, type = 'card', count = 3) {
    const templates = {
        card: '<div class="skeleton skeleton-card"></div>',
        text: '<div class="skeleton skeleton-text"></div><div class="skeleton skeleton-text short"></div>',
        row: '<div style="display:flex;gap:12px;align-items:center;padding:12px;"><div class="skeleton skeleton-avatar"></div><div style="flex:1;"><div class="skeleton skeleton-text"></div><div class="skeleton skeleton-text short"></div></div></div>'
    };
    container.innerHTML = Array(count).fill(templates[type] || templates.card).join('');
}

function showEmptyState(container, icon, title, message) {
    container.innerHTML = `<div class="empty-state"><i class="fas ${escapeHtml(icon)}"></i><h4>${escapeHtml(title)}</h4><p>${escapeHtml(message)}</p></div>`;
}

function showErrorState(container, message, retryFn) {
    container.innerHTML = `<div class="error-state"><i class="fas fa-exclamation-circle"></i><p>${escapeHtml(message)}</p>${retryFn ? '<button class="btn btn-outline btn-sm retry-btn">重试</button>' : ''}</div>`;
    if (retryFn) {
        container.querySelector('.retry-btn')?.addEventListener('click', retryFn);
    }
}

function typewriterEffect(container, text, speed = 15) {
    container.textContent = '';
    let i = 0;
    return new Promise(resolve => {
        function type() {
            if (i < text.length) {
                container.textContent += text.charAt(i);
                i++;
                setTimeout(type, speed);
            } else {
                resolve();
            }
        }
        type();
    });
}

// 24节气数据
const SOLAR_TERMS = {
    '2024-01-06': '小寒', '2024-01-20': '大寒', '2024-02-04': '立春', '2024-02-19': '雨水',
    '2024-03-05': '惊蛰', '2024-03-20': '春分', '2024-04-04': '清明', '2024-04-19': '谷雨',
    '2024-05-05': '立夏', '2024-05-20': '小满', '2024-06-05': '芒种', '2024-06-21': '夏至',
    '2024-07-07': '小暑', '2024-07-22': '大暑', '2024-08-07': '立秋', '2024-08-22': '处暑',
    '2024-09-07': '白露', '2024-09-22': '秋分', '2024-10-08': '寒露', '2024-10-23': '霜降',
    '2024-11-07': '立冬', '2024-11-22': '小雪', '2024-12-07': '大雪', '2024-12-22': '冬至',
    '2025-01-05': '小寒', '2025-01-20': '大寒', '2025-02-03': '立春', '2025-02-18': '雨水',
    '2025-03-05': '惊蛰', '2025-03-20': '春分', '2025-04-05': '清明', '2025-04-20': '谷雨',
    '2025-05-05': '立夏', '2025-05-21': '小满', '2025-06-05': '芒种', '2025-06-21': '夏至',
    '2025-07-07': '小暑', '2025-07-22': '大暑', '2025-08-07': '立秋', '2025-08-23': '处暑',
    '2025-09-07': '白露', '2025-09-23': '秋分', '2025-10-08': '寒露', '2025-10-23': '霜降',
    '2025-11-07': '立冬', '2025-11-22': '小雪', '2025-12-07': '大雪', '2025-12-22': '冬至'
};

function setupSelectionHandler(selector, activeClass, stateKey, callback) {
    document.querySelectorAll(selector).forEach(card => {
        card.addEventListener('click', function() {
            document.querySelectorAll(selector).forEach(c => c.classList.remove(activeClass));
            this.classList.add(activeClass);
            if (stateKey) {
                const key = stateKey.replace(/-([a-z])/g, (_, c) => c.toUpperCase());
                AppState[key] = this.dataset.product || this.dataset.craft || this.dataset.dialect || '';
            }
            const label = this.querySelector('h4')?.textContent || this.querySelector('.dialect-name')?.textContent || '';
            if (label) showNotification(`已选择: ${label}`, 'info');
            if (callback) callback(this);
        });
    });
}
