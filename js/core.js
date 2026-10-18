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
    THEME: 'yuexiang_theme',
    LARGE_TEXT: 'yuexiang_large_text',
    NOTIF: 'yuexiang_notif_enabled'
};

// 全局状态
const AppState = {
    currentTab: TABS.AGRICULTURE,
    currentDialect: 'cantonese',
    // 上次选择的农产品（由 localStorage 持久化，详见 script.js setupProductSelection）
    currentProduct: (function () {
        try {
            return localStorage.getItem('yuexiang_farming_product') || 'lychee';
        } catch (e) {
            return 'lychee';
        }
    })(),
    currentCraft: 'embroidery',
    // 注：此处原有 calendarYear，但全项目 0 处引用（日历按年周期模板复现、前端只传 month），
    // 已随 A7 移除。calendarMonth 保留：它是日历翻页与取数的实际状态（0-indexed）。
    calendarMonth: new Date().getMonth(),
    user: null,
    sessionId: null,
    recognition: null,
    isRecording: false
};

// 默认取页面自身的源：页面由哪个端口serve，API 就打哪个端口。
// 各页面在此之前注入 window.APP_CONFIG = { apiBaseUrl: '' } 走同源相对路径；
// 只有漏注入的页面会用到这个回退值，写死端口会让它打到别的实例上。
const API_BASE_URL = window.APP_CONFIG?.apiBaseUrl ?? window.location.origin;
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
    if (!resp.ok) {
        // 小清理（2026-10-05）：失败时带上 HTTP 状态与服务端 code，
        // 让调用方可以按 `err.status === 429` / `err.code === 'rate_limited'` 给出针对性提示，
        // 而不是一律「请求失败，请稍后重试」（此前 voice 被限流只显示通用文案）。
        let code = null;
        try {
            const body = await resp.json();
            code = body && body.code ? body.code : null;
        } catch (e) { /* 非 JSON 错误体（如 HTML 400）忽略 */ }
        const err = new Error(`HTTP ${resp.status}`);
        err.status = resp.status;
        err.code = code;
        throw err;
    }
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
                <button class="btn btn-outline btn-sm" id="onboarding-skip">跳过引导</button>
                <button class="btn btn-primary" id="onboarding-next">下一步 <i class="fas fa-arrow-right"></i></button>
            </div>
            <p style="margin-top:14px;font-size:0.75rem;color:var(--text-secondary);opacity:0.7;">提示：点击空白处或按 ESC 也可关闭</p>
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

    const closeOnboarding = () => {
        overlay.remove();
        localStorage.setItem('yuexiang_onboarding_done', '1');
        document.removeEventListener('keydown', onKeydown);
    };

    // 点击遮罩空白处关闭（点击卡片内容不关闭）
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) closeOnboarding();
    });

    // ESC 键关闭
    const onKeydown = (e) => {
        if (e.key === 'Escape') closeOnboarding();
    };
    document.addEventListener('keydown', onKeydown);

    document.getElementById('onboarding-skip').addEventListener('click', closeOnboarding);

    document.getElementById('onboarding-next').addEventListener('click', () => {
        if (currentStep < steps.length - 1) {
            currentStep++;
            updateContent();
        } else {
            closeOnboarding();
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
// 已移除：原硬编码 SOLAR_TERMS（仅覆盖 2024-01 ~ 2025-12，2026 年起永远查不到）。
// 节气现由后端 Meeus 太阳黄经算法计算，随农时日历接口 /api/agriculture/calendar/<id> 的
// solar_terms 字段下发（含 date / day / name），支持任意年份。

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

// ==================== 门户下滑转场 ====================
// 2026-10-18 学员走查：门户页往下滑自动进入农业技能页，要平滑弹性过渡；
// 五个板块页往上滑不回门户。规则只对 index.html（body[data-page="index"]）生效。
//
// 为什么用整页跳转而不是滚动劫持做「假滚动」：
//   · 板块页是独立页面，正文远比一屏长，劫持滚轮会让用户无法正常阅读；
//   · 门户 hero 本身就是满屏，下滑手势天然是「我要看下面的内容」。
//
// ⚠️ 必须监听 wheel/touch，**不能**监听 scroll：门户 hero 是 min-height:100vh 且
//    页面没有溢出内容，scrollHeight === clientHeight，window.scrollY 恒为 0，
//    scroll 事件一次都不触发（2026-10-18 实测）。
// 转场由 CSS 动画（.scroll-nav-leaving/.scroll-nav-entering）承担，JS 只做判定与计时，
// 动画时长写死在 TRANSITION_MS，两处必须一致（CSS 见 styles.css 末尾）。
const SCROLL_NAV = {
    TARGET: 'agriculture.html',
    // 2026-10-18 第二轮走查：60px 太灵敏，鼠标轻碰/触控板一抖就跳走。
    // 提到 220px（约一次明显的下滑幅度），并要求 500ms 内完成 —— 慢速滚动浏览
    // 不会被中途劫走，快速下滑才视为「我要去下面的板块」。
    THRESHOLD: 220,       // 累计下滑像素，低于此值视为误触/回弹
    GESTURE_MS: 500,      // 手势时长上限：超过则视为在浏览，放弃本次触发
    COOLDOWN_MS: 1200,    // 防止一次手势触发多次跳转
    TRANSITION_MS: 420    // 与 styles.css 的 portalSwipeOut 时长对齐
};

function setupScrollNavigation() {
    // 只在门户页启用：板块页需要正常滚动，绝不能被劫持
    if (document.body.dataset.page !== 'index') return;
    const hint = document.querySelector('.scroll-nav-hint');
    let firedAt = 0;     // 上次触发时间，做冷却
    let travel = 0;      // 本段手势累计下滑量（像素）
    let startedAt = 0;   // 本段手势开始时间（用于区分「快滑」与「慢滚」）

    const go = () => {
        if (Date.now() - firedAt < SCROLL_NAV.COOLDOWN_MS) return;
        firedAt = Date.now();
        document.body.classList.add('scroll-nav-leaving');
        setTimeout(() => { window.location.href = SCROLL_NAV.TARGET; }, SCROLL_NAV.TRANSITION_MS);
    };

    // dy > 0 表示向下。上滑（dy<0）立刻放弃本次手势，不允许「先上后下」凑够阈值。
    const onMove = (dy) => {
        if (dy < 0) { travel = 0; startedAt = 0; return; }
        if (!startedAt) startedAt = Date.now();
        travel += dy;
        if (hint) document.body.classList.toggle('scroll-nav-hint-gone', travel > 20);
        if (travel < SCROLL_NAV.THRESHOLD) return;
        // 慢速滚动（浏览意图）不触发：只有短时间内的快速下滑才算「滑走」手势
        if (Date.now() - startedAt > SCROLL_NAV.GESTURE_MS) { travel = 0; startedAt = 0; return; }
        go();
    };

    // 触屏：下滑手势
    let lastTouchY = null;
    document.addEventListener('touchstart', (e) => {
        lastTouchY = e.touches[0] ? e.touches[0].clientY : null;
        travel = 0;
        startedAt = 0;
    }, { passive: true });
    document.addEventListener('touchmove', (e) => {
        if (lastTouchY === null) return;
        const y = e.touches[0] ? e.touches[0].clientY : lastTouchY;
        onMove(lastTouchY - y);
        lastTouchY = y;
    }, { passive: true });
    document.addEventListener('touchend', () => { lastTouchY = null; }, { passive: true });

    // 桌面：滚轮向下（passive，不 preventDefault，不阻塞合成器线程）
    let wheelArmed = false;
    window.addEventListener('wheel', (e) => {
        if (e.deltaY < 0) { travel = 0; wheelArmed = false; startedAt = 0; return; }
        if (!wheelArmed) { wheelArmed = true; travel = 0; startedAt = 0; }
        onMove(e.deltaY);
    }, { passive: true });
    window.addEventListener('wheelend', () => { wheelArmed = false; travel = 0; startedAt = 0; });

    // 键盘也给同样待遇（无障碍：PageDown / 空格 / 下方向）
    window.addEventListener('keydown', (e) => {
        if (e.key === 'PageDown' || e.key === 'ArrowDown' || e.key === ' ') go();
    });
}

// ==================== BewlyCat 风格左侧导航栏 ====================
// 2026-10-18 学员走查：板块页左侧要一个能快速定位的侧栏，样式对标 BewlyCat
// （E:\Project\BewlyCat 的 src/components/SideBar/SideBar.vue）。移植要点：
//   ① 毛玻璃底 + 40px 圆钮，悬停上浮；
//   ② 图标项悬停从右侧滑出文字标签（BewlyCat 用 Tooltip，这里用纯 CSS）；
//   ③ 收起/展开由顶栏左侧按钮手动控制（位置与图标对齐 admin.html 的
//      .admin-sidebar-toggle），状态存 localStorage 跨页面保持。
// 只在板块页注入；门户页不注入，避免与 hero 全屏视觉冲突。
//
// 三轮走查修正记录：
//   · 锚点必须是页面真实存在的 card-section 容器 id，图标与标题一致，不缺项；
//   · 去掉与顶栏重复的主题/大字按钮和「本页」这类无信息量标签；
//   · 侧栏 top 从导航栏下方开始，不再与 72px 顶栏重叠；
//   · 去掉「自动隐藏」开关：与顶栏按钮功能重叠，且 BewlyCat 的靠近自动唤出
//     依赖 Shadow DOM + Vue 过渡，本项目做不到，留一个半成品不如不做；
//   · 锚点滚动定位到区块**标题**而不是容器顶边（容器有 72px margin-bottom，
//     直接贴容器顶会把标题推到导航栏下面）。

// 每页的锚点 = 该页真实存在的 card-section 容器 id（与页面里的 h3.card-section-title 一一对应）。
// 缺项自动跳过，所以新增板块时只要在这里补一行。
const SIDEBAR_SECTIONS = {
    agriculture: [
        { id: 'product-select-section',     label: '选择农产品',     icon: 'fa-tags' },
        { id: 'farming-calendar-section',   label: '农时智能日历',   icon: 'fa-calendar' },
        { id: 'agriculture-qa-section',     label: 'AI 农技问答',    icon: 'fa-robot' },
        { id: 'pest-diagnosis-section',     label: '病虫害 AI 诊断', icon: 'fa-bug' },
        { id: 'pest-guide-section',         label: '常见病虫害速查', icon: 'fa-book-medical' }
    ],
    ecommerce: [
        { id: 'live-simulation',            label: '直播带货实训',   icon: 'fa-video' },
        { id: 'copywriting-section',        label: '商品文案创作',   icon: 'fa-edit' },
        { id: 'customer-service-section',   label: '客户服务模拟',   icon: 'fa-headset' }
    ],
    crafts: [
        { id: 'craft-select-section',       label: '选择手工艺',     icon: 'fa-palette' },
        { id: 'craft-video-section',        label: '视频教学',       icon: 'fa-video' },
        { id: 'craft-3d-section',           label: '3D 互动教学',    icon: 'fa-cube' },
        { id: 'materials-section',          label: '材料采购指南',   icon: 'fa-shopping-basket' }
    ],
    resources: [
        { id: 'dialect-section',            label: '方言语音交互',   icon: 'fa-microphone' },
        { id: 'cases-section',              label: '本地成功案例',   icon: 'fa-trophy' },
        { id: 'policy-section',             label: '政策信息推送',   icon: 'fa-file-alt' }
    ],
    employment: [
        // 就业页是「页签切换」而不是「一页平铺」：.emp-panel 只有 active 的可见，
        // 其余 display:none。所以这三项除了滚动，还要先点对应的 .emp-tab 把面板切出来，
        // 否则 scrollIntoView 对隐藏元素无效（点了没反应）。
        { id: 'emp-jobs-panel',             label: '全部职位',       icon: 'fa-briefcase',     tab: 'jobs' },
        { id: 'emp-resume-panel',           label: '我的简历',       icon: 'fa-file-lines',    tab: 'resume' },
        { id: 'emp-applications-panel',     label: '我的求职',       icon: 'fa-paper-plane',   tab: 'applications' },
        { id: 'emp-saved-panel',            label: '收藏职位',       icon: 'fa-heart',         tab: 'saved' }
    ]
};

function buildBewlySidebar() {
    // 门户页（index.html）不注入侧栏：hero 是满屏视觉，左侧固定条会破坏构图
    if (document.body.dataset.page === 'index') return;

    const sections = (SIDEBAR_SECTIONS[document.body.dataset.page] || [])
        .filter(s => document.getElementById(s.id));
    if (!sections.length) return;   // 本页没有可用锚点，不注入空壳

    const bar = document.createElement('aside');
    bar.className = 'bewly-sidebar';
    bar.id = 'bewly-sidebar';
    bar.setAttribute('aria-label', '页面内导航');
    bar.innerHTML = sections.map(s => `
        <a class="bewly-nav-item" href="#${s.id}" data-anchor="${s.id}"
           ${s.tab ? `data-tab="${s.tab}"` : ''}
           title="${s.label}" aria-label="${s.label}">
            <i class="fas ${s.icon}" aria-hidden="true"></i>
            <span class="bewly-nav-tip">${s.label}</span>
        </a>
    `).join('');
    document.body.appendChild(bar);

    // 锚点点击：滚到目标区块的**标题**处。
    // ⚠️ 必须用标题而不是 card-section 容器本身：容器自带 margin-bottom:72px，
    //    scrollIntoView(block:'start') 只把容器顶边贴到视口顶，标题会被顶到
    //    导航栏下面去，看起来「没对准」（2026-10-18 三轮走查）。
    bar.querySelectorAll('[data-anchor]').forEach(a => {
        a.addEventListener('click', e => {
            const sec = document.getElementById(a.dataset.anchor);
            if (!sec) return;
            e.preventDefault();
            // 就业页是页签切换：先把对应面板切出来（隐藏面板滚动无效）
            const tab = a.dataset.tab;
            if (tab) {
                const tabBtn = document.querySelector(`.emp-tab[data-emp-tab="${tab}"]`);
                if (tabBtn && !tabBtn.classList.contains('active')) tabBtn.click();
            }
            const title = sec.querySelector('.card-section-title, .panel-header h3, h2, h3');
            // 就业页的面板没有标题（内容直接挂在 .emp-panel 下，标题是上方的页签栏）。
            // 这种页面滚到页签栏，让用户看到「当前停在哪个页签」+ 面板开头，
            // 比滚到一个没有视觉标识的容器顶边更有意义。
            const target = title
                || (tab ? document.querySelector('.emp-tabs') : null)
                || sec;
            (title || sec).scrollIntoView({
                behavior: prefersReducedMotion ? 'auto' : 'smooth',
                block: 'start'
            });
            // 页签刚切换出来时面板内容可能还没渲染完，等一帧再补一次滚动，
            // 否则滚到的是空面板的高度、目标位置偏上。
            if (tab) requestAnimationFrame(() => {
                const t2 = sec.querySelector('.card-section-title, .panel-header h3, h2, h3');
                (t2 || document.querySelector('.emp-tabs') || sec)
                    .scrollIntoView({ behavior: prefersReducedMotion ? 'auto' : 'smooth', block: 'start' });
            });
        });
    });
}

// 侧栏收起状态：跨页面记住用户选择
const SIDEBAR_COLLAPSED_KEY = 'yuexiang_bewly_sidebar_collapsed';

function setBewlySidebarCollapsed(collapsed) {
    const bar = document.getElementById('bewly-sidebar');
    if (!bar) return;
    bar.classList.toggle('hide', collapsed);
    const btn = document.getElementById('bewly-nav-toggle');
    if (btn) {
        btn.title = collapsed ? '展开侧栏' : '收起侧栏';
        btn.setAttribute('aria-label', btn.title);
        btn.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
        const icon = btn.querySelector('i');
        if (icon) icon.className = 'fas ' + (collapsed ? 'fa-angles-right' : 'fa-angles-left');
    }
    try { localStorage.setItem(SIDEBAR_COLLAPSED_KEY, collapsed ? '1' : '0'); } catch (e) { /* 隐私模式忽略 */ }
}

// 顶栏左侧的侧栏开关：位置与图标对齐 admin.html 的 .admin-sidebar-toggle
// （同一个视觉语言，用户不用重新学）。纯手动控制，无自动隐藏。
function setupBewlyNavToggle() {
    if (document.body.dataset.page === 'index') return;
    const nav = document.querySelector('.navbar .nav-container');
    if (!nav || document.getElementById('bewly-nav-toggle')) return;

    // 与 admin.html 完全同构：开关和徽标一起放进 .bewly-nav-left，
    // 由 CSS 绝对定位到顶栏左侧。不直接 insertBefore 到 nav 首位的理由：
    // 前台 .nav-container 是 space-between 布局，多一个子项会把徽标和导航项
    // 一起挤位（2026-10-18 三轮走查实测）。
    let left = nav.querySelector('.bewly-nav-left');
    if (!left) {
        left = document.createElement('div');
        left.className = 'bewly-nav-left';
        nav.insertBefore(left, nav.firstChild);
    }

    const btn = document.createElement('button');
    btn.className = 'bewly-nav-toggle';
    btn.id = 'bewly-nav-toggle';
    btn.type = 'button';
    btn.title = '收起侧栏';
    btn.setAttribute('aria-label', '收起侧栏');
    btn.setAttribute('aria-expanded', 'true');
    btn.innerHTML = '<i class="fas fa-angles-left" aria-hidden="true"></i>';
    left.appendChild(btn);

    btn.addEventListener('click', () => {
        const bar = document.getElementById('bewly-sidebar');
        if (!bar) return;
        setBewlySidebarCollapsed(!bar.classList.contains('hide'));
    });

    // 恢复上次状态
    try { setBewlySidebarCollapsed(localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === '1'); }
    catch (e) { /* 隐私模式忽略 */ }
}
